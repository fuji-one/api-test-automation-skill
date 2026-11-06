# HTTP 客户端封装层，统一处理 base_url、请求头、加密传输、Allure 附件和请求日志。
import logging
from typing import Any, Dict, Optional

import allure
from requests import Response, Session

from core.transport_crypto import AesDataEnvelopeCodec, TransportEncryptionPolicy, compact_json, redact
from core.security_redaction import SecretRedactor


DEFAULT_ATTACHMENT_TEXT_CHARS = 20000
MAX_ATTACHMENT_TEXT_CHARS = 200000


class HttpClient:
    """统一封装 requests 请求能力。"""

    def __init__(self, base_url: str, timeout: int, headers: Optional[Dict[str, str]] = None, modules: Optional[Dict[str, Any]] = None, transport_config: Optional[Dict[str, Any]] = None) -> None:
        # base_url 缺失说明环境配置未闭环，禁止拼出错误请求地址。
        if not base_url:
            raise ValueError("base_url 不能为空")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers = headers or {}
        self.modules = modules or {}
        self.transport_config = transport_config or {}
        self.transport_policy = TransportEncryptionPolicy(self.transport_config)
        diagnostics_config = self.transport_config.get("diagnostics") or {}
        self.max_attachment_text_chars = _bounded_attachment_limit(
            diagnostics_config.get("max_attachment_text_chars", DEFAULT_ATTACHMENT_TEXT_CHARS)
        )
        if self.transport_policy.enabled:
            self.crypto_codec = AesDataEnvelopeCodec(self.transport_policy)
        self.auth_context: Dict[str, Any] = {"enabled": False}
        # 复用 Session 保留连接池和公共请求状态，降低重复连接成本。
        self.session = Session()
        self.redactor = SecretRedactor(self.headers, self.transport_config)

    def set_headers(self, headers: Dict[str, str]) -> None:
        """设置后续请求默认请求头。"""

        self.headers.update(headers)
        self.redactor.register(headers)

    def set_auth_context(self, auth_context: Dict[str, Any]) -> None:
        """设置 token 鉴权上下文，后续请求会按方法自动注入。"""

        self.auth_context = auth_context or {"enabled": False}
        self.redactor.register(self.auth_context)

    def request(self, method: str, path: str, **kwargs: Any) -> Response:
        module = kwargs.pop("module", None)
        url = self._build_url(path, module)
        method_name = method.upper()
        # 合并框架默认请求头和单次请求请求头，单次请求优先生效。
        request_headers = dict(self.headers)
        request_headers.update(kwargs.pop("headers", {}) or {})
        kwargs["headers"] = request_headers
        self._inject_auth(method_name, kwargs)
        self.redactor.register(kwargs)
        crypto_plaintext_body: Dict[str, Any] = {}
        if self.transport_policy.should_encrypt(method_name, path):
            kwargs["params"] = self.transport_policy.merge_default_query(kwargs.get("params") or {})
            encrypted_body, crypto_plaintext_body = self.crypto_codec.encode_request_json(
                method_name,
                path,
                kwargs.get("json"),
                self.auth_context,
            )
            kwargs["json"] = encrypted_body
        # 每次请求都写入 Allure 步骤，便于报告中定位接口调用。
        safe_path = str(self.redactor.redact(path))
        with allure.step(f"请求接口：{method_name} {safe_path}"):
            if crypto_plaintext_body:
                allure.attach(
                    compact_json(self.redactor.redact(crypto_plaintext_body)),
                    name="请求明文（加密前，已脱敏）",
                    attachment_type=allure.attachment_type.JSON,
                )
                allure.attach(
                    compact_json({self.transport_policy.request_envelope_field: "__redacted_ciphertext__"}),
                    name="加密传输体结构",
                    attachment_type=allure.attachment_type.JSON,
                )
            response = self.session.request(
                method=method_name,
                url=url,
                timeout=self.timeout,
                **kwargs,
            )
            if self.transport_policy.should_encrypt(method_name, path):
                self._attach_transport_raw_response(response)
                try:
                    response = self.crypto_codec.decode_response(method_name, path, response, self.auth_context)
                except Exception as exc:
                    self._attach_transport_decode_failure(method_name, path, response, exc)
                    logging.error("接口响应解密失败：%s %s -> %s", method_name, self.redactor.redact(url), response.status_code)
                    raise ValueError(
                        f"加密响应解码失败：{method_name} {safe_path} HTTP {response.status_code}，"
                        "请查看 Allure 中的解密前响应证据"
                    ) from None
            logging.info("接口响应：%s %s -> %s", method_name, self.redactor.redact(url), response.status_code)
            allure.attach(self._redact_response_text(response), name="响应正文", attachment_type=allure.attachment_type.TEXT)
            return response

    def _build_url(self, path: str, module: str | None = None) -> str:
        # 强制 path 使用相对路径，避免用例绕过环境 base_url。
        if not path.startswith("/"):
            raise ValueError("接口路径必须以 / 开头")
        base_url = self.base_url
        if module:
            base_url = ((self.modules.get(module) or {}).get("base_url") or base_url).rstrip("/")
        if not base_url:
            raise ValueError(f"模块缺少 base_url：{module}")
        return f"{base_url}{path}"

    def _inject_auth(self, method_name: str, kwargs: Dict[str, Any]) -> None:
        if not self.auth_context.get("enabled"):
            return
        rule = self._select_auth_rule(method_name)
        placement = rule["placement"]
        token_name = rule["token_name"]
        token_value = self.auth_context["token_text"] if placement == "header" or rule.get("use_prefix") else self.auth_context["token_value"]
        if placement == "header":
            kwargs.setdefault("headers", {}).setdefault(token_name, token_value)
            return
        if placement == "query":
            kwargs["params"] = kwargs.get("params") or {}
            kwargs["params"].setdefault(token_name, token_value)
            return
        if placement == "body":
            kwargs["json"] = kwargs.get("json") or {}
            kwargs["json"].setdefault(token_name, token_value)
            return
        if placement == "cookie":
            kwargs["cookies"] = kwargs.get("cookies") or {}
            kwargs["cookies"].setdefault(token_name, token_value)
            return
        raise ValueError(f"不支持的 token 注入位置：{placement}")

    def _redact_response_text(self, response: Response) -> str:
        try:
            self.redactor.register(response.json())
            response_text = compact_json(self.redactor.redact(response.json()))
        except ValueError:
            response_text = str(self.redactor.redact(response.text))
        return _truncate_text(response_text, self.max_attachment_text_chars)

    def _attach_transport_raw_response(self, response: Response) -> None:
        allure.attach(
            compact_json(
                redact(
                    {
                        "status_code": response.status_code,
                        "headers": dict(response.headers),
                        "body_length": len(response.content or b""),
                    }
                )
            ),
            name="响应元信息（解密前，已脱敏）",
            attachment_type=allure.attachment_type.JSON,
        )
        allure.attach(
            self._redact_response_text(response),
            name="响应原文（解密前，已脱敏）",
            attachment_type=allure.attachment_type.TEXT,
        )

    def _attach_transport_decode_failure(
        self,
        method_name: str,
        path: str,
        response: Response,
        error: Exception,
    ) -> None:
        error_message = _truncate_text(str(self.redactor.redact(str(error))), self.max_attachment_text_chars)
        allure.attach(
            compact_json(
                self.redactor.redact({
                    "method": method_name,
                    "path": path,
                    "status_code": response.status_code,
                    "content_type": response.headers.get("Content-Type", ""),
                    "error_type": error.__class__.__name__,
                    "error_message": error_message,
                })
            ),
            name="响应解密失败上下文",
            attachment_type=allure.attachment_type.JSON,
        )

    def _select_auth_rule(self, method_name: str) -> Dict[str, Any]:
        method_overrides = self.auth_context.get("method_overrides") or {}
        override = method_overrides.get(method_name) or {}
        placement = override.get("placement") or self.auth_context.get("placement", "header")
        token_name = override.get("token_name") or self.auth_context.get("token_name")
        if not token_name:
            token_name = "Authorization" if placement == "header" else "token"
        return {
            "placement": placement,
            "token_name": token_name,
            "use_prefix": override.get("use_prefix", placement == "header"),
        }


def _bounded_attachment_limit(value: Any) -> int:
    limit = int(value)
    if limit <= 0:
        raise ValueError("diagnostics.max_attachment_text_chars 必须大于 0")
    return min(limit, MAX_ATTACHMENT_TEXT_CHARS)


def _truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}\n... 响应内容过长，已截断 ..."
