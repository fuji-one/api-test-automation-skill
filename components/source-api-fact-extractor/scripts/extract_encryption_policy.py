from __future__ import annotations

import re
from typing import Any


UNKNOWN = "UNKNOWN"

HEALTH_PATH_PATTERNS = (
    re.compile(r"^/health$"),
    re.compile(r"^/actuator(?:/.*)?$"),
)
INTERNAL_PATH_PATTERNS = (
    re.compile(r"^/app/internal(?:/.*)?$"),
    re.compile(r"^/internal(?:/.*)?$"),
    re.compile(r"^/api/[^/]+/internal(?:/.*)?$"),
    re.compile(r".*/internal(?:/.*)?$"),
)
AUTH_LOGIN_PATH_PATTERNS = (
    re.compile(r"^/api/[^/]+/auth/(?:login|thirdLogin|token|logout)(?:/.*)?$", re.IGNORECASE),
    re.compile(r"^/api/[^/]+/login(?:/.*)?$", re.IGNORECASE),
)
APP_API_PATH_PATTERN = re.compile(r"^/api/[^/]+/.+")
CALLBACK_NAME_PATTERN = re.compile(r"(callback|callBack|notify|webhook)", re.IGNORECASE)
INTERNAL_NAME_PATTERN = re.compile(r"(internal|inner)", re.IGNORECASE)


def build_encryption_policy(inventory: list[dict[str, Any]], classes: dict[str, Any]) -> dict[str, Any]:
    policy_items = [classify_api(item, classes) for item in inventory]
    summary: dict[str, int] = {}
    for item in policy_items:
        hint = item.get("policy_hint", UNKNOWN)
        summary[hint] = summary.get(hint, 0) + 1
    return {
        "schema_version": 1,
        "source": "source_api_fact_extractor",
        "policy_source_status": "source_inferred",
        "default_policy": "app_public_interfaces_require_transport_encryption_when_project_gateway_enables_it",
        "confirmation_required": True,
        "classification_rules": [
            {
                "rule_id": "TRANSPORT-ENC-HEALTH",
                "channel_type": "health_check",
                "policy_hint": "no_encrypt_candidate",
                "description": "健康检查和监控探活入口通常不走 App 业务传输加解密，需结合网关或用户确认最终放行。",
            },
            {
                "rule_id": "TRANSPORT-ENC-INTERNAL",
                "channel_type": "internal_service_api",
                "policy_hint": "no_encrypt_candidate",
                "description": "内部服务、Feign 或 internal 路径入口优先识别为非 App 客户端流量，需结合调用方和网关策略确认。",
            },
            {
                "rule_id": "TRANSPORT-ENC-CALLBACK",
                "channel_type": "third_party_callback",
                "policy_hint": "no_encrypt_candidate",
                "description": "第三方回调、通知和 webhook 入口通常按第三方签名或验签处理，不套 App 传输加解密。",
            },
            {
                "rule_id": "TRANSPORT-ENC-AUTH",
                "channel_type": "auth_or_login_entry",
                "policy_hint": "no_encrypt_candidate",
                "description": "登录或令牌入口可作为传输加解密豁免候选，但注册、验证码等相邻接口必须按项目策略二次确认。",
            },
            {
                "rule_id": "TRANSPORT-ENC-APP-PUBLIC",
                "channel_type": "app_public_api",
                "policy_hint": "requires_encryption_if_project_default_enabled",
                "description": "面向 App 的公开业务接口在项目默认开启传输加解密时，应生成请求加密和响应解密脚本能力。",
            },
        ],
        "policy_summary": summary,
        "policy_items": policy_items,
        "blocking_issues": [],
    }


def classify_api(item: dict[str, Any], classes: dict[str, Any]) -> dict[str, Any]:
    path = normalize_path(item.get("path", UNKNOWN))
    entry_type = item.get("entry_type", UNKNOWN)
    class_name = item.get("class_name", UNKNOWN)
    method_name = item.get("method_name", UNKNOWN)
    request_type = item.get("request_type", UNKNOWN)
    source_evidence = item.get("source_evidence", UNKNOWN)
    method_text = load_method_text(item, classes)

    if matches_any(path, HEALTH_PATH_PATTERNS):
        return policy_item(item, "health_check", "no_encrypt_candidate", "high", ["path_matches_health"], source_evidence)

    if is_internal_api(path, entry_type, class_name, method_name):
        return policy_item(
            item,
            "internal_service_api",
            "no_encrypt_candidate",
            "high" if entry_type in {"Feign Client", "Internal", "RPC Facade"} else "medium",
            ["entry_or_path_matches_internal"],
            source_evidence,
        )

    callback_reasons = callback_reason_codes(path, class_name, method_name, request_type, method_text)
    if callback_reasons:
        confidence = "high" if {"method_or_path_matches_callback", "request_type_or_method_body_has_third_party_signal"} <= set(callback_reasons) else "medium"
        return policy_item(item, "third_party_callback", "no_encrypt_candidate", confidence, callback_reasons, source_evidence)

    if matches_any(path, AUTH_LOGIN_PATH_PATTERNS) or method_name.lower() in {"login", "thirdlogin", "logout", "token"}:
        return policy_item(item, "auth_or_login_entry", "no_encrypt_candidate", "medium", ["path_or_method_matches_auth_login"], source_evidence)

    if APP_API_PATH_PATTERN.match(path) and not matches_any(path, INTERNAL_PATH_PATTERNS):
        return policy_item(
            item,
            "app_public_api",
            "requires_encryption_if_project_default_enabled",
            "medium",
            ["path_matches_app_public_api"],
            source_evidence,
        )

    return policy_item(
        item,
        "unknown_channel",
        "policy_required",
        "low",
        ["no_transport_encryption_channel_rule_matched"],
        source_evidence,
    )


def is_internal_api(path: str, entry_type: str, class_name: str, method_name: str) -> bool:
    if entry_type in {"Feign Client", "Internal", "RPC Facade"}:
        return True
    if matches_any(path, INTERNAL_PATH_PATTERNS):
        return True
    return bool(INTERNAL_NAME_PATTERN.search(class_name) or INTERNAL_NAME_PATTERN.search(method_name))


def callback_reason_codes(path: str, class_name: str, method_name: str, request_type: str, method_text: str) -> list[str]:
    reasons: list[str] = []
    haystack = " ".join([path, class_name, method_name])
    if not CALLBACK_NAME_PATTERN.search(haystack):
        return reasons
    reasons.append("method_or_path_matches_callback")
    third_party_text = " ".join([request_type, method_text])
    third_party_tokens = ("tencent", "nim", "netease", "alipay", "wechat", "callback", "notify", "webhook", "signature", "sign")
    if any(token.lower() in third_party_text.lower() for token in third_party_tokens):
        reasons.append("request_type_or_method_body_has_third_party_signal")
    return reasons


def policy_item(
    item: dict[str, Any],
    channel_type: str,
    policy_hint: str,
    confidence: str,
    reason_codes: list[str],
    evidence_ref: str,
) -> dict[str, Any]:
    return {
        "api_id": item.get("api_id", UNKNOWN),
        "module": item.get("module", UNKNOWN),
        "http_method": item.get("http_method", UNKNOWN),
        "path": item.get("path", UNKNOWN),
        "entry_type": item.get("entry_type", UNKNOWN),
        "class_name": item.get("class_name", UNKNOWN),
        "method_name": item.get("method_name", UNKNOWN),
        "channel_type": channel_type,
        "policy_hint": policy_hint,
        "confidence": confidence,
        "policy_status": "source_inferred",
        "requires_manual_confirmation": True,
        "reason_codes": reason_codes,
        "evidence_refs": [evidence_ref] if evidence_ref and evidence_ref != UNKNOWN else [],
    }


def load_method_text(item: dict[str, Any], classes: dict[str, Any]) -> str:
    java_class = classes.get(item.get("class_name", ""))
    if java_class is None:
        return ""
    for method in getattr(java_class, "methods", []):
        if getattr(method, "name", "") == item.get("method_name"):
            return " ".join([getattr(method, "signature", ""), getattr(method, "body", "")])
    return ""


def normalize_path(path: str) -> str:
    if not path or path == UNKNOWN:
        return UNKNOWN
    return "/" + path.strip().lstrip("/")


def matches_any(value: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.match(value) for pattern in patterns)
