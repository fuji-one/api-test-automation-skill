# 传输加密适配层，统一处理确认过的客户端 data envelope 契约。
from __future__ import annotations

import copy
import base64
import hashlib
import json
from typing import Any, Dict, Iterable, Optional

from requests import Response
try:
    from core.security_redaction import redact
except ModuleNotFoundError:
    # The codec is also used through file-based inspection without a core package.
    import importlib.util
    from pathlib import Path
    _spec = importlib.util.spec_from_file_location("_codec_redaction", Path(__file__).with_name("security_redaction.py"))
    assert _spec and _spec.loader
    _module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_module)
    redact = _module.redact




class TransportEncryptionPolicy:
    """读取环境配置中的加密策略，负责判断哪些请求需要传输加密。"""

    SUPPORTED_MODES = {"aes_256_ecb_pkcs7_data_envelope"}

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self.enabled = bool(self.config.get("enabled", False))
        self.mode = self.config.get("mode") or self.config.get("default_policy") or ""
        if self.enabled and self.mode not in self.SUPPORTED_MODES:
            raise ValueError(f"不支持的传输加密模式：{self.mode}")
        self.request_envelope_field = (
            self.config.get("request_envelope_field")
            or ((self.config.get("request_envelope") or {}).get("ciphertext_field"))
            or "data"
        )
        self.response_decrypt_field = (
            self.config.get("response_decrypt_field")
            or ((self.config.get("response_envelope") or {}).get("ciphertext_field"))
            or "data"
        )
        self.public_key = self.config.get("public_key") or ""
        self.encrypt_methods = self._upper_set(self.config.get("encrypt_methods") or ["POST"])
        self.auth_paths = set(self.config.get("auth_paths") or [])
        self.no_encrypt_paths = set(self.config.get("no_encrypt_paths") or self.config.get("confirmed_no_encrypt_interfaces") or [])
        self.default_query = self.config.get("default_query") or {}
        self.common_fields = self.config.get("common_fields") or {}
        self.default_device_id = self.config.get("default_device_id") or "api-framework-device"

    def should_encrypt(self, method: str, path: str) -> bool:
        if not self.enabled:
            return False
        if method.upper() not in self.encrypt_methods:
            return False
        return path not in self.no_encrypt_paths

    def is_login_path(self, path: str) -> bool:
        if path in self.auth_paths:
            return True
        normalized = path.lower()
        return "/auth/" in normalized and "login" in normalized

    def merge_default_query(self, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        merged = dict(self.default_query)
        merged.update(params or {})
        return merged

    def build_common_fields(self, auth_context: Dict[str, Any]) -> Dict[str, Any]:
        common: Dict[str, Any] = {}
        for field_name, rule in self.common_fields.items():
            common[field_name] = self._resolve_common_field(rule, auth_context)
        return common

    def _resolve_common_field(self, rule: Any, auth_context: Dict[str, Any]) -> Any:
        if not isinstance(rule, dict):
            return copy.deepcopy(rule)
        source = rule.get("source")
        if source == "auth_user_id_or_null":
            return auth_context.get("user_id")
        if source == "auth_token_or_empty":
            return auth_context.get("token_value") or ""
        if source == "auth_device_id_or_default":
            return auth_context.get("device_id") or rule.get("default") or self.default_device_id
        raise ValueError(f"不支持的公共加密字段来源：{source}")

    @staticmethod
    def _upper_set(values: Iterable[Any]) -> set[str]:
        return {str(value).upper() for value in values}


class AesDataEnvelopeCodec:
    """AES-256-ECB-PKCS7 编解码器，密文通过配置声明的字段传输。"""

    def __init__(self, policy: TransportEncryptionPolicy) -> None:
        self.policy = policy
        from core.dependency_check import DependencyChecker
        DependencyChecker.check_crypto_required()
        self._validate_key(self.policy.public_key, "public_key")

    def hash_user_id(self, user_id: Any) -> str:
        return hashlib.md5(f"{user_id}-{self.policy.public_key}".encode("utf-8")).hexdigest()

    def encode_request_json(self, method: str, path: str, body: Any, auth_context: Dict[str, Any]) -> tuple[Any, Dict[str, Any]]:
        if not self.policy.should_encrypt(method, path):
            return body, {}
        if body is None:
            body = {}
        if not isinstance(body, dict):
            raise TypeError("data envelope 仅支持对象型 JSON 请求体")
        common_fields = self.policy.build_common_fields(auth_context)
        plaintext_body = {**common_fields, **copy.deepcopy(body)}
        key = self._request_key(path, auth_context)
        encrypted_text = self._openssl_aes_256_ecb(compact_json(plaintext_body), key, decrypt=False)
        if auth_context.get("enabled") and not self.policy.is_login_path(path):
            user_id = auth_context.get("user_id")
            if user_id is None:
                raise ValueError("已登录加密请求缺少 user_id，无法追加用户哈希后缀")
            encrypted_text = f"{encrypted_text}{self.hash_user_id(user_id)}"
        return {self.policy.request_envelope_field: encrypted_text}, plaintext_body

    def decode_response(self, method: str, path: str, response: Response, auth_context: Dict[str, Any]) -> Response:
        if not self.policy.should_encrypt(method, path) or not response.text:
            return response
        outer = response.json()
        decrypt_field = self.policy.response_decrypt_field
        if not isinstance(outer, dict) or not isinstance(outer.get(decrypt_field), str):
            return response
        key = self._response_key(path, auth_context)
        decrypted = self._openssl_aes_256_ecb(outer[decrypt_field], key, decrypt=True)
        decoded_data = json.loads(decrypted)
        if outer.get("code") is not None and (
            not isinstance(decoded_data, dict) or decoded_data.get("code") is None
        ):
            decoded_payload = dict(outer)
            decoded_payload[decrypt_field] = decoded_data
        else:
            decoded_payload = decoded_data
        # 统一替换为解密后的响应体，断言和变量抽取只消费明文。
        response._content = compact_json(decoded_payload).encode("utf-8")
        response.headers["X-Transport-Crypto-Decoded"] = "true"
        return response

    def _request_key(self, path: str, auth_context: Dict[str, Any]) -> str:
        if auth_context.get("enabled") and not self.policy.is_login_path(path):
            session_secret = auth_context.get("session_secret")
            if not session_secret:
                raise ValueError("已登录加密请求缺少 sessionSecret，不能执行真实业务请求")
            self._validate_key(str(session_secret), "sessionSecret")
            return str(session_secret)
        return self.policy.public_key

    def _response_key(self, path: str, auth_context: Dict[str, Any]) -> str:
        return self._request_key(path, auth_context)

    def _openssl_aes_256_ecb(self, text: str, key: str, decrypt: bool) -> str:
        # Keep the existing AES-256-ECB/PKCS7 + Base64 wire protocol.
        # The historical method name remains for generated-adapter compatibility.
        from cryptography.hazmat.primitives import padding
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        self._validate_key(key, "key")
        cipher = Cipher(algorithms.AES(key.encode("utf-8")), modes.ECB())
        try:
            if decrypt:
                decryptor = cipher.decryptor()
                payload = base64.b64decode("".join(text.split()), validate=True)
                padded = decryptor.update(payload) + decryptor.finalize()
                unpadder = padding.PKCS7(128).unpadder()
                return (unpadder.update(padded) + unpadder.finalize()).decode("utf-8").strip()
            padder = padding.PKCS7(128).padder()
            padded = padder.update(text.encode("utf-8")) + padder.finalize()
            encryptor = cipher.encryptor()
            return base64.b64encode(encryptor.update(padded) + encryptor.finalize()).decode("ascii")
        except (ValueError, UnicodeError):
            raise ValueError(f"data envelope {'解密' if decrypt else '加密'}失败：输入或密钥不符合已确认协议") from None

    @staticmethod
    def _validate_key(key: str, key_name: str) -> None:
        if len(str(key).encode("utf-8")) != 32:
            raise ValueError(f"{key_name} 必须是 32 字节字符串")


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


