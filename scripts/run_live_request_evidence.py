#!/usr/bin/env python3
"""按配置直接请求接口并生成运行时取证 sidecar。"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import urllib.error
import urllib.request
from copy import deepcopy
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - 运行环境缺少 PyYAML 时给出清晰错误
    yaml = None


_redaction_path = Path(__file__).resolve().parents[1] / "components/api-test-framework-generator/assets/api-test-framework-template/core/security_redaction.py"
_redaction_spec = importlib.util.spec_from_file_location("_pipeline_security_redaction", _redaction_path)
assert _redaction_spec and _redaction_spec.loader
_redaction_module = importlib.util.module_from_spec(_redaction_spec)
_redaction_spec.loader.exec_module(_redaction_module)
_runtime_redactor = _redaction_module.SecretRedactor(marker="<redacted>")


def strip_yaml_comment(line: str) -> str:
    in_single = False
    in_double = False
    for index, char in enumerate(line):
        if char == "'" and not in_double:
            in_single = not in_single
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            continue
        if char == "#" and not in_single and not in_double:
            return line[:index]
    return line


def fallback_yaml_lines(text: str) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    for raw_line in text.splitlines():
        without_comment = strip_yaml_comment(raw_line).rstrip()
        if not without_comment.strip():
            continue
        indent = len(without_comment) - len(without_comment.lstrip(" "))
        lines.append((indent, without_comment.strip()))
    return lines


def split_inline_csv(value: str) -> list[str]:
    items: list[str] = []
    current: list[str] = []
    depth = 0
    in_single = False
    in_double = False
    for char in value:
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double:
            if char in "[{":
                depth += 1
            elif char in "]}":
                depth -= 1
            elif char == "," and depth == 0:
                items.append("".join(current).strip())
                current = []
                continue
        current.append(char)
    if current or value.strip():
        items.append("".join(current).strip())
    return items


def split_yaml_key_value(text: str) -> tuple[str, str | None]:
    in_single = False
    in_double = False
    for index, char in enumerate(text):
        if char == "'" and not in_double:
            in_single = not in_single
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            continue
        if char == ":" and not in_single and not in_double:
            if index + 1 == len(text) or text[index + 1].isspace():
                return text[:index].strip(), text[index + 1 :].strip()
    return text.strip(), None


def parse_yaml_scalar(value: str) -> Any:
    normalized = value.strip()
    lowered = normalized.lower()
    if normalized == "":
        return ""
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none", "~"}:
        return None
    if normalized == "[]":
        return []
    if normalized == "{}":
        return {}
    if normalized.startswith("[") and normalized.endswith("]"):
        inner = normalized[1:-1].strip()
        if not inner:
            return []
        return [parse_yaml_scalar(item) for item in split_inline_csv(inner)]
    if normalized.startswith("{") and normalized.endswith("}"):
        try:
            parsed = json.loads(normalized)
        except json.JSONDecodeError:
            parsed = {}
            inner = normalized[1:-1].strip()
            for item in split_inline_csv(inner):
                key, raw_value = split_yaml_key_value(item)
                if raw_value is None:
                    raise ValueError(f"无法解析内联 YAML 对象：{normalized}")
                parsed[key.strip("\"'")] = parse_yaml_scalar(raw_value)
            return parsed
        return parsed
    if (normalized.startswith('"') and normalized.endswith('"')) or (
        normalized.startswith("'") and normalized.endswith("'")
    ):
        if normalized.startswith('"'):
            try:
                return json.loads(normalized)
            except json.JSONDecodeError:
                pass
        return normalized[1:-1]
    if re.fullmatch(r"-?\d+", normalized):
        return int(normalized)
    if re.fullmatch(r"-?\d+\.\d+", normalized):
        return float(normalized)
    return normalized


def parse_fallback_yaml_block(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[Any, int]:
    if index >= len(lines):
        return {}, index
    current_indent, current_text = lines[index]
    if current_indent < indent:
        return {}, index
    if current_text.startswith("- "):
        return parse_fallback_yaml_list(lines, index, current_indent)
    return parse_fallback_yaml_dict(lines, index, current_indent)


def parse_fallback_yaml_dict(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while index < len(lines):
        current_indent, text = lines[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ValueError(f"YAML 缩进不合法：{text}")
        if text.startswith("- "):
            break
        key, raw_value = split_yaml_key_value(text)
        if not key or raw_value is None:
            raise ValueError(f"无法解析 YAML 键值行：{text}")
        index += 1
        if raw_value == "":
            if index < len(lines) and lines[index][0] > current_indent:
                result[key], index = parse_fallback_yaml_block(lines, index, lines[index][0])
            else:
                result[key] = None
            continue
        result[key] = parse_yaml_scalar(raw_value)
    return result, index


def parse_fallback_yaml_list(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[list[Any], int]:
    result: list[Any] = []
    while index < len(lines):
        current_indent, text = lines[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ValueError(f"YAML 缩进不合法：{text}")
        if not text.startswith("- "):
            break
        item_text = text[2:].strip()
        index += 1
        if item_text == "":
            if index < len(lines) and lines[index][0] > current_indent:
                item, index = parse_fallback_yaml_block(lines, index, lines[index][0])
                result.append(item)
            else:
                result.append(None)
            continue
        key, raw_value = split_yaml_key_value(item_text)
        if raw_value is None:
            result.append(parse_yaml_scalar(item_text))
            continue
        item: dict[str, Any] = {}
        if raw_value == "":
            if index < len(lines) and lines[index][0] > current_indent:
                value, index = parse_fallback_yaml_block(lines, index, lines[index][0])
            else:
                value = None
            item[key] = value
        else:
            item[key] = parse_yaml_scalar(raw_value)
        if index < len(lines) and lines[index][0] > current_indent:
            extra, index = parse_fallback_yaml_dict(lines, index, lines[index][0])
            item.update(extra)
        result.append(item)
    return result, index


def fallback_load_yaml(text: str) -> Any:
    stripped = text.strip()
    if not stripped:
        return {}
    if stripped.startswith("{") or stripped.startswith("["):
        return json.loads(stripped)
    lines = fallback_yaml_lines(text)
    if not lines:
        return {}
    data, index = parse_fallback_yaml_block(lines, 0, lines[0][0])
    if index != len(lines):
        raise ValueError(f"YAML 存在无法解析的剩余内容：{lines[index][1]}")
    return data


def load_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text) if yaml is not None else fallback_load_yaml(text)
    data = data or {}
    if not isinstance(data, dict):
        raise ValueError("请求计划必须是 YAML 对象")
    return data


def load_secrets(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("secrets 文件必须是 JSON 对象")
    return data


def expand_env(value: Any) -> Any:
    if isinstance(value, str):
        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            return os.environ.get(name, match.group(0))

        return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", replace, value)
    if isinstance(value, dict):
        return {key: expand_env(item) for key, item in value.items()}
    if isinstance(value, list):
        return [expand_env(item) for item in value]
    return value


def json_path_get(data: Any, path: str) -> Any:
    if not path.startswith("$."):
        raise ValueError(f"仅支持以 $. 开头的 JSONPath：{path}")
    current = data
    for part in path[2:].split("."):
        if isinstance(current, dict):
            current = current[part]
            continue
        if isinstance(current, list) and part.isdigit():
            current = current[int(part)]
            continue
        raise KeyError(path)
    return current


def apply_context(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str):
        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in context:
                raise KeyError(f"上下文变量未提取：{name}")
            return str(context[name])

        return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", replace, value)
    if isinstance(value, dict):
        return {key: apply_context(item, context) for key, item in value.items()}
    if isinstance(value, list):
        return [apply_context(item, context) for item in value]
    return value


def redact(value: Any, key_hint: str = "") -> Any:
    return _runtime_redactor.redact(value, key_hint)


def resolve_body(step: dict[str, Any], secrets: dict[str, Any]) -> Any:
    if "body" in step:
        return deepcopy(step["body"])
    body_ref = step.get("body_ref")
    if not body_ref:
        return None
    prefix = "runtime_secrets."
    if not str(body_ref).startswith(prefix):
        raise ValueError(f"body_ref 只允许引用 runtime_secrets.*：{body_ref}")
    secret_key = str(body_ref)[len(prefix):]
    if secret_key not in secrets:
        raise KeyError(f"缺少运行时 secret：{secret_key}")
    return deepcopy(secrets[secret_key])


def decode_json_response(status: int, raw: bytes) -> tuple[int, Any]:
    if not raw:
        return status, None
    return status, json.loads(raw.decode("utf-8"))


def request_json(method: str, url: str, headers: dict[str, str], body: Any, timeout: float) -> tuple[int, Any]:
    payload = None
    request_headers = dict(headers)
    if body is not None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=payload, headers=request_headers, method=method.upper())
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return decode_json_response(response.status, response.read())
    except urllib.error.HTTPError as error:
        return decode_json_response(error.code, error.read())


def expected_status_for(step: dict[str, Any], step_id: str) -> int:
    expected_status = step.get("expected_status")
    if expected_status is None:
        raise ValueError(f"步骤 {step_id} 缺少 expected_status")
    try:
        return int(expected_status)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"步骤 {step_id} expected_status 必须是整数：{expected_status}") from exc


def value_type_for(name: str) -> str:
    lowered = name.lower()
    if "token" in lowered:
        return "token"
    if lowered.endswith("_id") or lowered == "id":
        return "id"
    if "status" in lowered:
        return "status_code"
    if "code" in lowered:
        return "business_code"
    return "field_value"


READ_METHODS = {"GET", "HEAD", "OPTIONS"}
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
REQUEST_ALLOWED_DECISIONS = {"request_allowed", "request_allowed_with_user_config"}
REQUEST_BLOCKING_DECISIONS = {"manual_confirmation_required", "blocked_until_isolated_account_and_cleanup"}
AUTH_STEP_KEYWORDS = ("login", "signin", "sign_in", "auth", "token", "captcha", "verify", "登录", "鉴权", "认证", "验证码")
HIGH_RISK_KEYWORDS = (
    "pay", "payment", "withdraw", "subscribe", "subscription", "settle", "order", "message",
    "relation", "review", "audit", "callback", "webhook", "支付", "提现", "订阅", "结算",
    "订单", "消息", "关系", "评价", "审核", "回调",
)


def step_text_for_authorization(step: dict[str, Any], step_id: str) -> str:
    return " ".join(
        str(value)
        for value in (
            step_id,
            step.get("name", ""),
            step.get("case_name", ""),
            step.get("case_type", ""),
            step.get("step_type", ""),
            step.get("path", ""),
            step.get("source_contract_ref", ""),
        )
    ).lower()


def is_auth_or_login_step(step: dict[str, Any], step_id: str) -> bool:
    # Preserve existing /login plans; unrelated names/refs never grant permission.
    path = str(step.get("path", "")).split("?", 1)[0].rstrip("/")
    return path.lower() in {"/login", "/auth/login", "/api/login", "/api/auth/login", "/signin", "/auth/signin", "/sign_in"}


def ensure_step_request_allowed(step: dict[str, Any], step_id: str, method: str, request_scope: dict[str, Any]) -> None:
    decision = str(step.get("request_decision") or step.get("runtime_request_decision") or "")
    risk_level = str(step.get("risk_level") or "")
    if decision in REQUEST_BLOCKING_DECISIONS:
        raise ValueError(f"步骤 {step_id} 未获准直接请求：request_decision={decision}")
    if decision and decision not in REQUEST_ALLOWED_DECISIONS:
        raise ValueError(f"步骤 {step_id} 未获准直接请求：未知 request_decision={decision}")
    if risk_level in {"destructive_state", "external_or_callback"} and decision not in REQUEST_ALLOWED_DECISIONS:
        raise ValueError(f"步骤 {step_id} 风险等级 {risk_level} 缺少可请求决策")
    if method in READ_METHODS:
        return
    if method not in MUTATING_METHODS:
        raise ValueError(f"步骤 {step_id} 请求方法不在允许集合：{method}")
    if is_auth_or_login_step(step, step_id):
        return
    if decision in REQUEST_ALLOWED_DECISIONS:
        return
    if request_scope.get("mutating_requests_allowed") is True:
        return
    raise ValueError(f"步骤 {step_id} 是变更类请求，缺少 mutating_requests_allowed 或 request_allowed 决策")


def optional_step_evidence_fields(step: dict[str, Any]) -> dict[str, Any]:
    db_evidence = step.get("db_evidence") or {}
    fields = {
        "assertions_ref": step.get("assertions_ref"),
        "assertion_status": "passed" if step.get("assertions_ref") else None,
        "db_before_ref": step.get("db_before_ref") or db_evidence.get("before_ref"),
        "db_after_ref": step.get("db_after_ref") or db_evidence.get("after_ref"),
        "db_delta_assertion": step.get("db_delta_assertion") or db_evidence.get("delta_assertion"),
        "db_probe_source_ref": step.get("db_probe_source_ref") or db_evidence.get("probe_source_ref"),
    }
    return {
        key: value
        for key, value in fields.items()
        if value not in (None, "", [], {})
    }


def validate_cleanup_plan(step: dict[str, Any], steps: list[Any], step_index: int, cleanup: dict[str, Any]) -> None:
    """Require executable, later cleanup/verification steps before a write occurs.

    Steps remain in the original ordered plan so multi-step flows are preserved.
    A request-known ownership value must also survive missing response IDs.
    """
    later = {str(item.get("step_id")): item for item in steps[step_index:] if isinstance(item, dict)}
    cleanup_ids = cleanup.get("step_ids") or step.get("cleanup_step_ids") or []
    verify_ids = cleanup.get("verification_step_ids") or step.get("cleanup_verification_step_ids") or []
    if not isinstance(cleanup_ids, list) or not cleanup_ids or not isinstance(verify_ids, list) or not verify_ids:
        raise ValueError("未获准直接请求：cleanup 必须引用计划中后续清理及最终验证 step_ids")
    ownership = cleanup.get("ownership_key") or cleanup.get("cleanup_identity")
    if not ownership or not cleanup.get("failure_path_ownership"):
        raise ValueError("未获准直接请求：cleanup 缺少归属键或请求已知的 failure_path_ownership")
    for cleanup_id in cleanup_ids + verify_ids:
        action = later.get(str(cleanup_id))
        if action is None or not action.get("module") or not action.get("path"):
            raise ValueError(f"未获准直接请求：cleanup 引用不存在或不可执行：{cleanup_id}")
        expected_status_for(action, str(cleanup_id))
        ensure_step_request_allowed(action, str(cleanup_id), str(action.get("method", "GET")).upper(), {})
    for verify_id in verify_ids:
        action = later[str(verify_id)]
        if str(action.get("method", "GET")).upper() not in READ_METHODS or not action.get("assertions_ref"):
            raise ValueError("未获准直接请求：cleanup 最终验证必须是带 assertions_ref 的只读步骤")
        if not action.get("response_assertions"):
            raise ValueError("未获准直接请求：cleanup 最终验证必须有可执行 response_assertions")
        validate_response_assertions(action)


def validate_response_assertions(step: dict[str, Any]) -> None:
    assertions = step.get("response_assertions", {})
    if not isinstance(assertions, dict) or any(not isinstance(path, str) or not path.startswith("$.") for path in assertions):
        raise ValueError("response_assertions 必须是 $.JSONPath 到明确期望值的映射")


def data_shape(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: data_shape(item) for key, item in value.items()}
    if isinstance(value, list):
        first_shape = data_shape(value[0]) if value else None
        return {"type": "array", "length": len(value), "item_shape": first_shape}
    if value is None:
        return "null"
    return type(value).__name__


def shallow_key_fields(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    fields: dict[str, Any] = {}
    for key, item in value.items():
        lowered = str(key).lower()
        if key in {"code", "message", "msg", "status"} or lowered.endswith("id") or lowered.endswith("_id"):
            fields[str(key)] = item
    data = value.get("data")
    if isinstance(data, dict):
        for key, item in data.items():
            lowered = str(key).lower()
            if lowered.endswith("id") or lowered.endswith("_id") or lowered in {"status", "state", "code"}:
                fields[f"data.{key}"] = item
    return fields


def has_business_payload_field(value: Any) -> bool:
    if not isinstance(value, dict):
        return value not in (None, "", [], {})
    for key, item in value.items():
        lowered = str(key).lower()
        if lowered in {"code", "business_code", "bizcode", "status", "message", "msg", "errormessage"}:
            continue
        if item not in (None, "", [], {}):
            return True
        if str(key) == "data" and item in ([], {}):
            return True
    return False


def response_business_code(response_json: Any) -> Any:
    if isinstance(response_json, dict):
        for key in ("code", "business_code", "bizCode", "status"):
            if key in response_json:
                return response_json[key]
    return None


def response_message(response_json: Any) -> Any:
    if isinstance(response_json, dict):
        for key in ("message", "msg", "errorMessage"):
            if key in response_json:
                return response_json[key]
    return None


def assertion_candidates_for(
    step: dict[str, Any],
    response_status: int,
    response_json: Any,
    extract_rules: dict[str, Any],
) -> dict[str, Any]:
    candidates: dict[str, Any] = {
        "http_status": response_status,
        "business_code": response_business_code(response_json),
        "message": response_message(response_json),
        "field_exists": list(extract_rules.values()),
        "key_fields": shallow_key_fields(response_json),
    }
    if step.get("assertion_candidates"):
        candidates["source_assertion_candidates"] = step.get("assertion_candidates")
    if step.get("assertions_ref"):
        candidates["assertions_ref"] = step.get("assertions_ref")
    return {key: value for key, value in candidates.items() if value not in (None, "", [], {})}


def setup_evidence_for(step: dict[str, Any]) -> Any:
    if step.get("setup_data") not in (None, "", [], {}):
        return step.get("setup_data")
    if step.get("preconditions") not in (None, "", [], {}):
        return step.get("preconditions")
    return {"required": False, "reason": "not_required_or_not_declared"}


def cleanup_evidence_for(step: dict[str, Any], step_id: str, method: str) -> dict[str, Any]:
    cleanup = step.get("cleanup") or step.get("cleanup_strategy")
    if isinstance(cleanup, dict) and cleanup:
        if cleanup.get("required") is False and method in MUTATING_METHODS and not is_auth_or_login_step(step, step_id) and not (cleanup.get("reason") or cleanup.get("exemption_reason")):
            return {"required": False, "status": "missing", "missing_items": ["cleanup_exemption_reason"]}
        return cleanup
    if cleanup not in (None, "", [], {}):
        return {"required": True, "source": cleanup}
    if step.get("cleanup_required") is False:
        reason = step.get("cleanup_exemption_reason")
        if method in MUTATING_METHODS and not is_auth_or_login_step(step, step_id) and not reason:
            return {
                "required": False,
                "status": "missing",
                "missing_items": ["cleanup_exemption_reason"],
                "reason": "mutating_request_without_cleanup_needs_exemption_reason",
            }
        return {
            "required": False,
            "reason": reason or "source_or_runtime_exemption_declared",
        }
    if method in MUTATING_METHODS and not is_auth_or_login_step(step, step_id):
        return {
            "required": True,
            "status": "missing",
            "missing_items": ["cleanup_rule", "cleanup_identity", "cleanup_verification"],
            "reason": "mutating_request_requires_cleanup_or_exemption",
        }
    return {"required": False, "reason": "read_only_or_auth_setup_no_persistent_effect"}


def has_db_observation(step: dict[str, Any], optional_fields: dict[str, Any]) -> bool:
    return bool(
        step.get("db_assertions")
        or step.get("db_before_after")
        or optional_fields.get("db_before_ref")
        or optional_fields.get("db_after_ref")
        or optional_fields.get("db_delta_assertion")
    )


def has_followup_observation(step: dict[str, Any]) -> bool:
    return bool(step.get("followup_api_assertions") or step.get("verification_api") or step.get("state_verification_ref"))


def observation_mode_for(step: dict[str, Any], db_observed: bool) -> str:
    if step.get("result_observation_mode"):
        return str(step.get("result_observation_mode"))
    if step.get("cleanup_verification"):
        return "cleanup_verification"
    if db_observed:
        return "db_assertion"
    if has_followup_observation(step):
        return "followup_api"
    return "response_field"


def assertion_strength_for(
    step: dict[str, Any],
    method: str,
    response_json: Any,
    extract_rules: dict[str, Any],
    db_observed: bool,
    cleanup_evidence: dict[str, Any],
) -> str:
    if step.get("assertion_strength"):
        return str(step.get("assertion_strength"))
    cleanup_verified = bool(step.get("cleanup_verification") or cleanup_evidence.get("verification"))
    if cleanup_verified:
        return "L5_cleanup_verified"
    if db_observed:
        return "L4_persistence_verified"
    if has_followup_observation(step):
        return "L3_business_observable"
    if extract_rules or has_business_payload_field(response_json):
        return "L2_response_field"
    return "L1_basic"


def materialization_missing_items(
    step: dict[str, Any],
    step_id: str,
    method: str,
    cleanup_evidence: dict[str, Any],
    assertion_strength: str,
) -> list[str]:
    missing: list[str] = []
    if not (step.get("case_id") or step.get("flow_id")):
        missing.append("case_id_or_flow_id")
    for key in ("module", "path"):
        if not step.get(key):
            missing.append(key)
    if cleanup_evidence.get("status") == "missing":
        missing.extend(cleanup_evidence.get("missing_items") or ["cleanup_rule"])
    is_write = method in MUTATING_METHODS and not is_auth_or_login_step(step, step_id)
    text = step_text_for_authorization(step, step_id)
    high_risk = any(keyword.lower() in text for keyword in HIGH_RISK_KEYWORDS)
    if is_write and assertion_strength in {"L1_basic", "L2_response_field"}:
        missing.append("business_result_observability")
    if is_write and high_risk and assertion_strength not in {"L4_persistence_verified", "L5_cleanup_verified"}:
        missing.append("high_risk_persistence_or_cleanup_verification")
    return sorted(set(missing))


def build_evidence_item(
    evidence_id: str,
    step_id: str,
    step: dict[str, Any],
    method: str,
    response_status: int,
    headers: dict[str, Any],
    body: Any,
    response_json: Any,
    extract_rules: dict[str, Any],
    value_type: str,
    field_path: Any,
    field_value: Any,
    usable_for_execution_case: bool,
    redacted: bool = False,
) -> dict[str, Any]:
    optional_fields = optional_step_evidence_fields(step)
    db_observed = has_db_observation(step, optional_fields)
    cleanup_evidence = cleanup_evidence_for(step, step_id, method)
    assertion_strength = assertion_strength_for(step, method, response_json, extract_rules, db_observed, cleanup_evidence)
    result_observation_mode = observation_mode_for(step, db_observed)
    missing_items = materialization_missing_items(step, step_id, method, cleanup_evidence, assertion_strength)
    script_ready = not missing_items
    auth_config = step.get("auth") if isinstance(step.get("auth"), dict) else {}
    item = {
        "evidence_id": evidence_id,
        "flow_id": step.get("flow_id", ""),
        "case_id": step.get("case_id", ""),
        "step_id": step_id,
        "step_order": step.get("step_order", ""),
        "module": step.get("module", ""),
        "method": method,
        "path": step.get("path"),
        "base_url_alias": step.get("base_url_alias") or step.get("module", ""),
        "session_role": step.get("session_role") or step.get("role") or "default",
        "auth_policy": step.get("auth_policy") or auth_config.get("policy") or "unspecified",
        "token_injection_location": step.get("token_injection_location") or auth_config.get("placement") or "header",
        "source_contract_ref": step.get("source_contract_ref", ""),
        "request_source_ref": f"runtime_request_plan.yaml#{step_id}",
        "request_plaintext": {
            "path": step.get("path_params") or {},
            "query": step.get("query") or step.get("params") or {},
            "header": redact(headers),
            "body": redact(body),
        },
        "response_status": response_status,
        "response_plaintext": {
            "http_status": response_status,
            "business_code": response_business_code(response_json),
            "message": response_message(response_json),
            "data_shape": redact(data_shape(response_json.get("data") if isinstance(response_json, dict) else response_json)),
            "key_fields": redact(shallow_key_fields(response_json)),
            "body": redact(response_json),
        },
        "assertion_candidates": assertion_candidates_for(step, response_status, response_json, extract_rules),
        "setup_data": setup_evidence_for(step),
        "cleanup": cleanup_evidence,
        "db_before_after": {
            "db_before_ref": optional_fields.get("db_before_ref"),
            "db_after_ref": optional_fields.get("db_after_ref"),
            "db_delta_assertion": optional_fields.get("db_delta_assertion"),
            "db_probe_source_ref": optional_fields.get("db_probe_source_ref"),
        },
        "assertion_strength": assertion_strength,
        "result_observation_mode": result_observation_mode,
        "script_materialization_ready": script_ready,
        "missing_materialization_items": missing_items,
        "value_type": value_type,
        "field_path": field_path,
        "field_value": field_value,
        "source_status": "confirmed",
        "usable_for_execution_case": usable_for_execution_case,
        "redacted": redacted,
    }
    item.update(optional_fields)
    return item


def format_yaml_scalar(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "":
        return '""'
    if text == "[]" or text == "{}":
        return json.dumps(text, ensure_ascii=False)
    if any(char in text for char in (":", "#", "[", "]", "{", "}", "\n")) or text.strip() != text:
        return json.dumps(text, ensure_ascii=False)
    lowered = text.lower()
    if lowered in {"true", "false", "null", "none", "~"}:
        return json.dumps(text, ensure_ascii=False)
    return text


def append_yaml_lines(lines: list[str], value: Any, indent: int = 0) -> None:
    prefix = " " * indent
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)) and item:
                lines.append(f"{prefix}{key}:")
                append_yaml_lines(lines, item, indent + 2)
            elif isinstance(item, list) and not item:
                lines.append(f"{prefix}{key}: []")
            elif isinstance(item, dict) and not item:
                lines.append(f"{prefix}{key}: {{}}")
            else:
                lines.append(f"{prefix}{key}: {format_yaml_scalar(item)}")
        return
    if isinstance(value, list):
        if not value:
            lines.append(f"{prefix}[]")
            return
        for item in value:
            if isinstance(item, dict):
                if not item:
                    lines.append(f"{prefix}- {{}}")
                    continue
                first_key, first_value = next(iter(item.items()))
                rest = dict(list(item.items())[1:])
                if isinstance(first_value, (dict, list)) and first_value:
                    lines.append(f"{prefix}- {first_key}:")
                    append_yaml_lines(lines, first_value, indent + 4)
                elif isinstance(first_value, list) and not first_value:
                    lines.append(f"{prefix}- {first_key}: []")
                elif isinstance(first_value, dict) and not first_value:
                    lines.append(f"{prefix}- {first_key}: {{}}")
                else:
                    lines.append(f"{prefix}- {first_key}: {format_yaml_scalar(first_value)}")
                append_yaml_lines(lines, rest, indent + 2)
                continue
            if isinstance(item, list):
                lines.append(f"{prefix}-")
                append_yaml_lines(lines, item, indent + 2)
                continue
            lines.append(f"{prefix}- {format_yaml_scalar(item)}")
        return
    lines.append(f"{prefix}{format_yaml_scalar(value)}")


def fallback_dump_yaml(data: dict[str, Any]) -> str:
    lines: list[str] = []
    append_yaml_lines(lines, data)
    return "\n".join(lines) + "\n"


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    data = redact(data)
    if yaml is not None:
        content = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=1000)
    else:
        content = fallback_dump_yaml(data)
    path.write_text(content, encoding="utf-8")


def request_scope_from_plan(expanded_plan: dict[str, Any], base_urls: dict[str, Any]) -> dict[str, Any]:
    return {
        "env_name": expanded_plan.get("env", {}).get("env_name", ""),
        "allowed_modules": sorted(base_urls.keys()),
        "mutating_requests_allowed": expanded_plan.get("request_scope", {}).get("mutating_requests_allowed", False),
        "cleanup_required": expanded_plan.get("cleanup", {}).get("required", False),
    }


def classify_step_failure(exc: BaseException) -> tuple[str, str, str]:
    message = str(exc)
    if "缺少模块 base_url" in message:
        return "blocked_final", "missing_module_base_url", "complete_runtime_execution_config"
    if "未获准直接请求" in message or "缺少可请求决策" in message or "缺少 mutating_requests_allowed" in message:
        return "blocked_final", "request_not_authorized_for_selected_scope", "complete_execution_authorization_or_mock"
    if "expected_status" in message:
        return "blocked_final", "missing_or_invalid_expected_status", "repair_runtime_request_plan"
    if "上下文变量未提取" in message:
        return "skipped_recoverable", "missing_upstream_runtime_context", "retry_after_upstream_step_evidence"
    if "响应状态码不匹配" in message:
        return "retryable", "response_status_mismatch_needs_triage", "triage_request_materialization_or_product_defect"
    if "JSONPath" in message or isinstance(exc, KeyError):
        return "retryable", "extraction_path_unresolved", "repair_extraction_rule_or_response_inference"
    if isinstance(exc, (urllib.error.URLError, TimeoutError, json.JSONDecodeError)):
        return "retryable", "request_or_response_temporarily_unusable", "retry_or_repair_runtime_endpoint"
    return "retryable", "runtime_step_failed_but_queue_can_continue", "review_and_retry_item"


def build_queue_item(
    step: dict[str, Any],
    step_id: str,
    queue_state: str,
    last_attempt: str,
    next_action: str,
    reason_code: str,
    evidence_refs: list[str] | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "case_id": step.get("case_id", ""),
        "flow_id": step.get("flow_id", ""),
        "step_order": step.get("step_order", ""),
        "step_id": step_id,
        "priority_bucket": step.get("priority_bucket") or step.get("priority") or "other",
        "queue_state": queue_state,
        "last_attempt": last_attempt,
        "next_action": next_action,
        "reason_code": reason_code,
        "evidence_refs": evidence_refs or [],
    }
    return item


def build_continuation_queue(queue_items: list[dict[str, Any]]) -> dict[str, Any]:
    states = ("pending", "requested", "evidenced", "retryable", "skipped_recoverable", "blocked_final", "excluded")
    summary = {state: 0 for state in states}
    for item in queue_items:
        state = str(item.get("queue_state") or "")
        if state in summary:
            summary[state] += 1
    return {
        "schema_version": 1,
        "queue_policy": "long_chain_then_p0_p1_p2_p3_skip_recoverable_and_continue",
        "summary": summary,
        "items": queue_items,
    }


def write_queue_file(output_dir: Path, continuation_queue: dict[str, Any], stage_status: str) -> None:
    write_yaml(output_dir / "runtime_evidence_queue.yaml", {
        "schema_version": 1,
        "stage": "runtime_evidence_continuation_queue",
        "status": stage_status,
        "queue_state_field": "queue_state",
        **continuation_queue,
    })


def build_blocked_outputs(output_dir: Path, plan: dict[str, Any], issue: str) -> None:
    issue = str(redact(issue))
    output_dir.mkdir(parents=True, exist_ok=True)
    common_scope = plan.get("request_scope") or {}
    first_step = (plan.get("steps") or [{}])[0]
    queue_items = [
        build_queue_item(
            first_step if isinstance(first_step, dict) else {},
            str((first_step or {}).get("step_id") or "runtime_plan") if isinstance(first_step, dict) else "runtime_plan",
            "blocked_final",
            "runtime_setup_failed",
            "repair_runtime_request_plan_or_config",
            "runtime_requester_setup_blocked",
            [],
        )
    ]
    continuation_queue = build_continuation_queue(queue_items)
    write_yaml(output_dir / "runtime_stage_status.yaml", {
        "schema_version": 1,
        "stage": "runtime_live_evidence",
        "status": "blocked",
        "next_stage_allowed": False,
        "request_scope": common_scope,
        "input_paths": [],
        "output_paths": [],
        "gate_checks": [],
        "continuation_queue": continuation_queue,
        "blocking_issues": [issue],
    })
    write_yaml(output_dir / "runtime_evidence.yaml", {
        "schema_version": 1,
        "stage": "runtime_live_evidence",
        "status": "blocked",
        "next_stage_allowed": False,
        "request_scope": common_scope,
        "auth_evidence": {"status": "blocked", "token_source": "none", "secret_redaction": "enabled"},
        "evidence_items": [],
        "conflict_items": [],
        "blocking_issues": [issue],
    })
    write_yaml(output_dir / "runtime_value_catalog.yaml", {
        "schema_version": 1,
        "stage": "runtime_value_catalog",
        "status": "blocked",
        "values": [],
        "usable_fact_types": [],
        "missing_values": [issue],
        "conflict_values": [],
        "blocking_issues": [issue],
    })
    write_queue_file(output_dir, continuation_queue, "blocked")
    (output_dir / "runtime_conflict_report.md").write_text(f"## 运行时取证冲突报告\n\n- 阻塞项：{issue}\n", encoding="utf-8")


def run(plan_path: Path, output_dir: Path, secrets_path: Path | None) -> int:
    global _runtime_redactor
    _runtime_redactor = _redaction_module.SecretRedactor(marker="<redacted>")
    output_dir.mkdir(parents=True, exist_ok=True)
    plan: dict[str, Any] = {}
    try:
        plan = load_yaml(plan_path)
        secrets = load_secrets(secrets_path)
        _runtime_redactor.register(expand_env(plan))
        _runtime_redactor.register(secrets)
        sanitized_plan = redact(expand_env(deepcopy(plan)))
        write_yaml(output_dir / "runtime_request_plan.yaml", sanitized_plan)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        build_blocked_outputs(output_dir, plan, str(exc))
        return 1

    try:
        expanded_plan = expand_env(plan)
        base_urls = expanded_plan.get("env", {}).get("base_urls") or {}
        timeout = float(expanded_plan.get("env", {}).get("timeout_seconds", 15))
        steps = expanded_plan.get("steps") or []
        if not steps:
            raise ValueError("请求计划 steps 不能为空")
        if not isinstance(steps, list) or any(not isinstance(item, dict) for item in steps):
            raise ValueError("请求计划 steps 必须是对象列表")
        explicit_ids = [str(item["step_id"]) for item in steps if item.get("step_id")]
        if len(explicit_ids) != len(set(explicit_ids)):
            raise ValueError("请求计划 step_id 不得重复")
    except (KeyError, ValueError, OSError, json.JSONDecodeError) as exc:
        build_blocked_outputs(output_dir, plan, str(exc))
        return 1

    context: dict[str, Any] = {}
    evidence_items: list[dict[str, Any]] = []
    catalog_values: list[dict[str, Any]] = []
    queue_items: list[dict[str, Any]] = []
    auth_status = "missing"
    token_extract_path = expanded_plan.get("auth", {}).get("token_extract_path")
    request_scope_config = expanded_plan.get("request_scope") or {}

    for step_index, raw_step in enumerate(steps, start=1):
        step = raw_step if isinstance(raw_step, dict) else {}
        step_id = str(step.get("step_id") or f"step_{step_index}")
        evidence_refs: list[str] = []
        try:
            module = step.get("module")
            if module not in base_urls:
                raise KeyError(f"步骤 {step_id} 缺少模块 base_url：{module}")
            method = str(step.get("method", "GET")).upper()
            ensure_step_request_allowed(step, step_id, method, request_scope_config)
            url = str(base_urls[module]).rstrip("/") + "/" + str(step.get("path", "")).lstrip("/")
            headers = apply_context(step.get("headers") or {}, context)
            body = apply_context(resolve_body(step, secrets), context)
            expected_status = expected_status_for(step, step_id)
            validate_response_assertions(step)
            cleanup = cleanup_evidence_for(step, step_id, method)
            if cleanup.get("status") == "missing":
                raise ValueError(f"步骤 {step_id} 未获准直接请求：缺少 cleanup 清理规则或豁免证据")
            if method in MUTATING_METHODS and not is_auth_or_login_step(step, step_id):
                if cleanup.get("required") is not False:
                    validate_cleanup_plan(step, steps, step_index, cleanup)
            _runtime_redactor.register(headers)
            _runtime_redactor.register(body)
            response_status, response_json = request_json(method, url, headers, body, timeout)
            _runtime_redactor.register(response_json)
            if response_status != expected_status:
                raise ValueError(f"步骤 {step_id} 响应状态码不匹配：实际 {response_status}，期望 {expected_status}")
            for assertion_path, expected_value in (step.get("response_assertions") or {}).items():
                if json_path_get(response_json, assertion_path) != expected_value:
                    raise ValueError(f"步骤 {step_id} 响应断言未通过：{assertion_path}")
            extract_rules = step.get("extract") or {}
            if not extract_rules:
                evidence_id = f"RT-{step_id.upper().replace('-', '_')}-{len(evidence_items) + 1:03d}"
                evidence_items.append(build_evidence_item(
                    evidence_id=evidence_id,
                    step_id=step_id,
                    step=step,
                    method=method,
                    response_status=response_status,
                    headers=headers,
                    body=body,
                    response_json=response_json,
                    extract_rules=extract_rules,
                    value_type="assertion_value",
                    field_path="$.http_status",
                    field_value=response_status,
                    usable_for_execution_case=bool(step.get("assertions_ref")),
                    redacted=False,
                ))
                evidence_refs.append(f"runtime_evidence.yaml#{evidence_id}")
            for name, path in extract_rules.items():
                value = json_path_get(response_json, str(path))
                context[str(name)] = value
                value_type = value_type_for(str(name))
                safe_value = redact(value, str(name))
                if _redaction_module.sensitive_key(str(path).rsplit(".", 1)[-1]) or value_type == "token":
                    safe_value = "<redacted>"
                redacted = safe_value != value
                evidence_id = f"RT-{step_id.upper().replace('-', '_')}-{len(evidence_items) + 1:03d}"
                evidence_items.append(build_evidence_item(
                    evidence_id=evidence_id,
                    step_id=step_id,
                    step=step,
                    method=method,
                    response_status=response_status,
                    headers=headers,
                    body=body,
                    response_json=response_json,
                    extract_rules=extract_rules,
                    value_type=value_type,
                    field_path=path,
                    field_value=safe_value,
                    usable_for_execution_case=True,
                    redacted=redacted,
                ))
                evidence_refs.append(f"runtime_evidence.yaml#{evidence_id}")
                catalog_values.append({
                    "value_id": f"VAL-{step_id.upper().replace('-', '_')}-{str(name).upper()}",
                    "value_type": value_type,
                    "field": str(name),
                    "value": safe_value,
                    "source_type": "live_request_evidence",
                    "source_ref": f"runtime_evidence.yaml#{evidence_id}",
                    "cross_checked_by": step.get("cross_checked_by", []),
                    "source_status": "confirmed",
                })
                if value_type == "token":
                    auth_status = "confirmed"
            queue_items.append(build_queue_item(
                step,
                step_id,
                "evidenced",
                "request_ok",
                "consume_confirmed_evidence",
                "runtime_evidence_confirmed",
                evidence_refs,
            ))
        except (KeyError, ValueError, OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            queue_state, reason_code, next_action = classify_step_failure(exc)
            queue_items.append(build_queue_item(
                step,
                step_id,
                queue_state,
                str(redact(str(exc))),
                next_action,
                reason_code,
                evidence_refs,
            ))
            continue

    request_scope = request_scope_from_plan(expanded_plan, base_urls)
    non_evidenced = [item for item in queue_items if item.get("queue_state") != "evidenced"]
    blocked_final = [item for item in queue_items if item.get("queue_state") == "blocked_final"]
    evidenced_steps = {str(item.get("step_id")) for item in queue_items if item.get("queue_state") == "evidenced"}
    failed_cleanup_refs = set()
    for planned in steps:
        cleanup = planned.get("cleanup") or planned.get("cleanup_strategy") or {}
        if not isinstance(cleanup, dict):
            continue
        cleanup_ids = cleanup.get("step_ids") or []
        verify_ids = cleanup.get("verification_step_ids") or []
        cleanup_refs = (cleanup_ids if isinstance(cleanup_ids, list) else []) + (verify_ids if isinstance(verify_ids, list) else [])
        if str(planned.get("step_id")) in evidenced_steps or cleanup_refs:
            failed_cleanup_refs.update(str(ref) for ref in cleanup_refs if str(ref) not in evidenced_steps)
    for item in evidence_items:
        if failed_cleanup_refs:
            item["script_materialization_ready"] = False
            item["usable_for_execution_case"] = False
            item["missing_materialization_items"] = sorted(set(item.get("missing_materialization_items") or []) | {"cleanup_or_final_verification_failed"})
    if failed_cleanup_refs:
        stage_status = "blocked"
    elif evidence_items and not non_evidenced:
        stage_status = "passed"
    elif evidence_items:
        stage_status = "partial"
    else:
        stage_status = "blocked"
    next_stage_allowed = stage_status in {"passed", "partial"}
    script_ready_count = sum(1 for item in evidence_items if item.get("script_materialization_ready") is True)
    script_not_ready_count = len(evidence_items) - script_ready_count
    continuation_queue = build_continuation_queue(queue_items)
    missing_values = [
        f"{item.get('step_id')}: {item.get('reason_code')}"
        for item in non_evidenced
    ]
    blocking_issues = [
        f"{item.get('step_id')}: {item.get('last_attempt') or item.get('reason_code')}"
        for item in blocked_final
    ]
    if failed_cleanup_refs:
        blocking_issues.append("cleanup_or_final_verification_failed: " + ", ".join(sorted(failed_cleanup_refs)))

    write_yaml(output_dir / "runtime_stage_status.yaml", {
        "schema_version": 1,
        "stage": "runtime_live_evidence",
        "status": stage_status,
        "next_stage_allowed": next_stage_allowed,
        "request_scope": request_scope,
        "input_paths": [{"path": str(plan_path), "role": "runtime_request_plan"}],
        "output_paths": [
            {"path": "runtime_evidence.yaml", "role": "runtime_evidence"},
            {"path": "runtime_evidence_queue.yaml", "role": "runtime_evidence_queue"},
        ],
        "gate_checks": [{
            "check_id": "direct_request_execution",
            "status": "passed" if stage_status == "passed" else "blocked",
            "evidence_refs": ["runtime_evidence.yaml", "runtime_evidence_queue.yaml"],
        }, {
            "check_id": "runtime_requester_evidence_contract_gate",
            "status": "passed" if script_not_ready_count == 0 else "partial",
            "script_materialization_ready_count": script_ready_count,
            "script_materialization_not_ready_count": script_not_ready_count,
        }],
        "continuation_queue": continuation_queue,
        "blocking_issues": [] if next_stage_allowed else blocking_issues,
    })
    write_yaml(output_dir / "runtime_evidence.yaml", {
        "schema_version": 1,
        "stage": "runtime_live_evidence",
        "status": stage_status,
        "next_stage_allowed": next_stage_allowed,
        "request_scope": request_scope,
        "script_materialization_ready_count": script_ready_count,
        "script_materialization_not_ready_count": script_not_ready_count,
        "auth_evidence": {
            "status": auth_status if next_stage_allowed else "blocked",
            "token_source": "login_response" if auth_status == "confirmed" else "none",
            "token_extract_path": token_extract_path,
            "secret_redaction": "enabled",
        },
        "evidence_items": evidence_items,
        "conflict_items": [],
        "blocking_issues": [] if stage_status == "passed" else missing_values,
    })
    write_yaml(output_dir / "runtime_value_catalog.yaml", {
        "schema_version": 1,
        "stage": "runtime_value_catalog",
        "status": "passed" if stage_status == "passed" and catalog_values else ("partial" if next_stage_allowed else "blocked"),
        "values": catalog_values,
        "usable_fact_types": ["token_rule", "test_data_rule", "variable_link", "assertion_rule"] if next_stage_allowed else [],
        "missing_values": missing_values if missing_values else ([] if catalog_values else ["no_runtime_values_extracted"]),
        "conflict_values": [],
        "blocking_issues": [] if next_stage_allowed else blocking_issues,
    })
    write_queue_file(output_dir, continuation_queue, stage_status)
    if non_evidenced:
        lines = ["## 运行时取证冲突报告", "", "- 冲突项：无", "", "## 未闭合队列项"]
        for item in non_evidenced:
            lines.append(f"- {item.get('step_id')}：{item.get('queue_state')}，{item.get('reason_code')}")
        content = "\n".join(lines) + "\n"
    else:
        content = "## 运行时取证冲突报告\n\n- 冲突项：无\n"
    (output_dir / "runtime_conflict_report.md").write_text(content, encoding="utf-8")
    return 0 if next_stage_allowed else 1

def main() -> int:
    parser = argparse.ArgumentParser(description="配置驱动的运行时接口取证请求器")
    parser.add_argument("--plan", required=True, help="runtime_request_plan.yaml 路径")
    parser.add_argument("--output-dir", required=True, help="输出 04-runtime-evidence 目录")
    parser.add_argument("--secrets-file", help="运行时 secret JSON 文件，仅用于本次请求，不写入输出")
    args = parser.parse_args()
    return run(
        Path(args.plan),
        Path(args.output_dir),
        Path(args.secrets_file) if args.secrets_file else None,
    )


if __name__ == "__main__":
    sys.exit(main())
