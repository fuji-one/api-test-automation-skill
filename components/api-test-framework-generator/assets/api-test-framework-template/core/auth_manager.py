# 鉴权管理层，负责静态 token、动态 token 和按请求方式注入 token。
from typing import Any, Dict

import allure

from core.assertor import Assertor
from core.extractor import Extractor
from core.runtime_context import resolve_runtime_value


class AuthManager:
    """统一封装 token 获取和鉴权注入配置。"""

    DEFAULT_TOKEN_NAME = "Authorization"
    DEFAULT_NON_HEADER_TOKEN_NAME = "token"
    DEFAULT_TOKEN_PREFIX = "Bearer"
    DEFAULT_PLACEMENT = "header"
    SUPPORTED_PLACEMENTS = {"header", "query", "body", "cookie"}

    @staticmethod
    def build_auth_headers(auth_config: Dict[str, Any], api_client: Any, runtime_context: Dict[str, Any]) -> Dict[str, str]:
        # 兼容旧模板：默认 header token 仍可作为公共请求头注入。
        auth_context = AuthManager.build_auth_context(auth_config, api_client, runtime_context)
        if not auth_context.get("enabled"):
            return {}
        if auth_context["placement"] != "header":
            return {}
        return {auth_context["token_name"]: auth_context["token_text"]}

    @staticmethod
    def build_auth_context(auth_config: Dict[str, Any], api_client: Any, runtime_context: Dict[str, Any]) -> Dict[str, Any]:
        # 未启用鉴权时返回关闭态上下文，由业务用例直接使用匿名 client。
        if not auth_config.get("enabled", False):
            return {"enabled": False}

        token_value = auth_config.get("token_value")
        login_payload: Dict[str, Any] = {}
        # 优先使用显式 token；未提供时才按来源配置动态请求 token。
        if not token_value:
            login_payload = AuthManager._request_token(auth_config, api_client, runtime_context)
            token_value = login_payload["token"]

        # token 写入运行时上下文，供后续变量链路或调试定位使用。
        runtime_context["auth_token"] = token_value
        session_secret = login_payload.get("session_secret") or auth_config.get("session_secret_value")
        user_id = login_payload.get("user_id") or auth_config.get("user_id")
        device_id = login_payload.get("device_id") or auth_config.get("device_id")
        if session_secret:
            runtime_context["session_secret"] = session_secret
        if user_id is not None:
            runtime_context["login_user_id"] = user_id
            runtime_context["appUserId"] = user_id
            runtime_context["userId"] = user_id
        if device_id:
            runtime_context["deviceId"] = device_id
        hash_user_id = ""
        if user_id is not None and hasattr(api_client, "crypto_codec"):
            hash_user_id = api_client.crypto_codec.hash_user_id(user_id)
            runtime_context["hash_user_id"] = hash_user_id
        placement = AuthManager._normalize_placement(auth_config.get("placement") or AuthManager.DEFAULT_PLACEMENT)
        token_name = auth_config.get("token_name") or AuthManager._default_token_name(placement)
        token_prefix = auth_config.get("token_prefix", AuthManager.DEFAULT_TOKEN_PREFIX)
        token_text = f"{token_prefix} {token_value}".strip()
        method_overrides = AuthManager._normalize_method_overrides(auth_config.get("method_overrides") or {})
        return {
            "enabled": True,
            "type": auth_config.get("type", "bearer"),
            "token_name": token_name,
            "token_value": token_value,
            "token_prefix": token_prefix,
            "token_text": token_text,
            "placement": placement,
            "method_overrides": method_overrides,
            "session_secret": session_secret,
            "user_id": user_id,
            "device_id": device_id,
            "hash_user_id": hash_user_id,
        }

    @staticmethod
    def _request_token(auth_config: Dict[str, Any], api_client: Any, runtime_context: Dict[str, Any]) -> Dict[str, Any]:
        token_request = auth_config.get("token_request") or {}
        resolved_token_request = resolve_runtime_value(token_request, runtime_context)
        method = resolved_token_request.get("method")
        path = resolved_token_request.get("path")
        extract_path = resolved_token_request.get("extract_path")
        expected_status = resolved_token_request.get("expected_status")
        if not method or not path or not extract_path or expected_status is None:
            raise ValueError("动态获取 token 时必须配置 method、path、expected_status 和 extract_path")

        with allure.step("获取接口鉴权 token"):
            # token 请求同样走统一 client，保证日志、Allure 附件和超时策略一致。
            previous_auth_context = getattr(api_client, "auth_context", {"enabled": False})
            api_client.set_auth_context({"enabled": False})
            try:
                response = api_client.request(
                    method=method,
                    path=path,
                    module=resolved_token_request.get("module"),
                    headers=resolved_token_request.get("headers") or {},
                    params=resolved_token_request.get("params") or {},
                    json=resolved_token_request.get("json") or {},
                )
            finally:
                api_client.set_auth_context(previous_auth_context)
            Assertor.status_code(response, expected_status)
            # token 提取路径必须来自执行配置，不能在脚本里临时猜测。
            payload = response.json()
            token_value = Extractor.extract_json_value(payload, extract_path)
            if not token_value:
                raise ValueError(f"token 提取结果为空：{extract_path}")
            result = {"token": str(token_value)}
            session_secret_path = resolved_token_request.get("session_secret_extract_path")
            if session_secret_path:
                result["session_secret"] = str(Extractor.extract_json_value(payload, session_secret_path))
            user_id_path = resolved_token_request.get("user_id_extract_path")
            if user_id_path:
                result["user_id"] = Extractor.extract_json_value(payload, user_id_path)
            device_id_path = resolved_token_request.get("device_id_extract_path")
            if device_id_path:
                result["device_id"] = str(Extractor.extract_json_value(payload, device_id_path))
            return result

    @staticmethod
    def apply_login_step_context(
        role: str,
        extracted_values: Dict[str, Any],
        api_client: Any,
        runtime_context: Dict[str, Any],
        auth_contexts: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """把显式登录步骤的语义化抽取值写回账号组鉴权上下文。"""

        if not role or role == "none":
            raise ValueError("登录步骤必须声明有效的 account_context.role 或 session_role")
        token_value = extracted_values.get("token")
        if not token_value:
            raise ValueError(f"登录步骤未抽取到 token：{role}")

        role_configs = runtime_context.get("auth_role_configs") or {}
        resolved_role = AuthManager._resolve_role_name(role, role_configs)
        role_config = AuthManager._role_config(resolved_role, role_configs)
        context = auth_contexts.get(resolved_role) or auth_contexts.get(role) or {"enabled": False}
        placement = AuthManager._normalize_placement(
            context.get("placement") or role_config.get("placement") or AuthManager.DEFAULT_PLACEMENT
        )
        if context.get("token_prefix") is not None:
            token_prefix = context["token_prefix"]
        elif "token_prefix" in role_config:
            token_prefix = role_config["token_prefix"]
        else:
            token_prefix = AuthManager.DEFAULT_TOKEN_PREFIX
        token_name = context.get("token_name") or role_config.get("token_name") or AuthManager._default_token_name(placement)
        session_secret = extracted_values.get("session_secret") or extracted_values.get("sessionSecret")
        user_id = extracted_values.get("user_id")
        if user_id is None:
            user_id = extracted_values.get("userId")
        device_id = extracted_values.get("device_id") or extracted_values.get("deviceId")
        hash_user_id = ""
        if user_id is not None and hasattr(api_client, "crypto_codec"):
            hash_user_id = api_client.crypto_codec.hash_user_id(user_id)

        context.update(
            {
                "enabled": True,
                "token_name": token_name,
                "token_value": str(token_value),
                "token_prefix": token_prefix,
                "token_text": f"{token_prefix} {token_value}".strip(),
                "placement": placement,
                "method_overrides": AuthManager._normalize_method_overrides(
                    context.get("method_overrides") or role_config.get("method_overrides") or {}
                ),
                "session_secret": str(session_secret) if session_secret else None,
                "user_id": user_id,
                "device_id": str(device_id) if device_id else None,
                "hash_user_id": hash_user_id,
            }
        )
        expected_user_id = role_config.get("expected_user_id")
        if expected_user_id is not None and str(user_id) != str(expected_user_id):
            raise ValueError(
                f"账号角色 {resolved_role} 登录身份不匹配："
                f"期望 userId={expected_user_id}，实际 userId={user_id}"
            )

        for related_role in AuthManager._related_roles(resolved_role, role_configs):
            auth_contexts[related_role] = context
            AuthManager.publish_role_runtime_context(runtime_context, related_role, context)
        runtime_context["auth_roles"] = auth_contexts
        return context

    @staticmethod
    def publish_role_runtime_context(
        runtime_context: Dict[str, Any],
        role: str,
        auth_context: Dict[str, Any],
    ) -> None:
        role_context = {
            "auth_token": auth_context.get("token_value"),
            "session_secret": auth_context.get("session_secret"),
            "hash_user_id": auth_context.get("hash_user_id"),
            "deviceId": auth_context.get("device_id"),
        }
        user_id = auth_context.get("user_id")
        if user_id is not None:
            role_context.update(
                {
                    "login_user_id": user_id,
                    "appUserId": user_id,
                    "userId": user_id,
                }
            )
            runtime_context[f"{role}_user_id"] = user_id
        runtime_context[f"{role}_context"] = role_context

    @staticmethod
    def _resolve_role_name(role: str, role_configs: Dict[str, Any]) -> str:
        if role not in role_configs:
            if role_configs:
                raise ValueError(f"登录步骤声明了未配置的目标角色：{role}")
            return role
        target_role = role
        visited_roles = set()
        while isinstance(role_configs.get(target_role), str):
            if target_role in visited_roles:
                raise ValueError(f"auth_roles 存在循环引用：{role}")
            visited_roles.add(target_role)
            target_role = role_configs[target_role]
            if target_role not in role_configs:
                raise ValueError(f"auth_roles.{role} 引用了不存在的角色：{target_role}")
        return target_role

    @staticmethod
    def _role_config(role: str, role_configs: Dict[str, Any]) -> Dict[str, Any]:
        role_config = role_configs.get(role) or {}
        if not isinstance(role_config, dict):
            raise TypeError(f"auth_roles.{role} 必须是对象或角色别名")
        return role_config

    @staticmethod
    def _related_roles(resolved_role: str, role_configs: Dict[str, Any]) -> list[str]:
        if not role_configs:
            return [resolved_role]
        return [
            role
            for role in role_configs
            if AuthManager._resolve_role_name(role, role_configs) == resolved_role
        ]

    @staticmethod
    def _normalize_placement(placement: str) -> str:
        normalized = str(placement or "").lower()
        if normalized not in AuthManager.SUPPORTED_PLACEMENTS:
            raise ValueError(f"不支持的 token 注入位置：{placement}")
        return normalized

    @staticmethod
    def _default_token_name(placement: str) -> str:
        if placement == "header":
            return AuthManager.DEFAULT_TOKEN_NAME
        return AuthManager.DEFAULT_NON_HEADER_TOKEN_NAME

    @staticmethod
    def _normalize_method_overrides(method_overrides: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
        normalized_overrides: Dict[str, Dict[str, str]] = {}
        for method, override in method_overrides.items():
            method_name = str(method).upper()
            if not isinstance(override, dict):
                raise ValueError(f"auth.method_overrides.{method_name} 必须是对象")
            normalized = dict(override)
            if "placement" in normalized:
                normalized["placement"] = AuthManager._normalize_placement(normalized["placement"])
            normalized_overrides[method_name] = normalized
        return normalized_overrides
