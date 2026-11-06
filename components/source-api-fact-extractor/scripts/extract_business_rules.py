from __future__ import annotations

import re
from typing import Any

from extract_call_chain import find_method
from extract_java_api import UNKNOWN, JavaClass, evidence


ERROR_CODE_RE = re.compile(r"\b([A-Z][A-Z0-9_]*)(?:\)|,|;)")


def build_business_rules(
    apis: list[dict[str, Any]],
    classes: dict[str, JavaClass],
    contracts: dict[str, dict[str, Any]],
    call_chains: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    class_by_name = {c.name: c for c in {id(v): v for v in classes.values()}.values()}
    rules: dict[str, list[dict[str, Any]]] = {}
    for api in apis:
        api_rules: list[dict[str, Any]] = []
        api_rules.extend(validation_rules(api, contracts.get(api["api_id"], {})))
        for call in call_chains.get(api["api_id"], []):
            java_class = class_by_name.get(call["class_name"])
            if not java_class:
                continue
            method = find_method(java_class, call["method_name"])
            if not method:
                continue
            api_rules.extend(scan_method_rules(api, java_class, method))
        rules[api["api_id"]] = dedupe_rules(api_rules)
    return rules


def validation_rules(api: dict[str, Any], contract: dict[str, Any]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for field in contract.get("request_fields", []):
        annotations = field.get("validation_annotation", UNKNOWN)
        if annotations == UNKNOWN:
            continue
        rule_id = f"{api['api_id']}:validation:{field['field_name']}"
        rules.append(
            {
                "rule_id": rule_id,
                "api_id": api["api_id"],
                "rule_type": "PARAM_VALIDATION",
                "condition": annotations,
                "success_behavior": "框架参数校验通过",
                "failure_behavior": "框架参数校验失败，业务方法无法正常完成",
                "error_code": UNKNOWN,
                "exception_type": "BeanValidation",
                "server_judgable": "YES",
                "evidence": field.get("evidence", api["source_evidence"]),
            }
        )
    return rules


def scan_method_rules(api: dict[str, Any], java_class: JavaClass, method: Any) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    last_condition = UNKNOWN
    for offset, raw_line in enumerate(method.body.splitlines(), start=method.line):
        line = raw_line.strip()
        if not line or line.startswith("//"):
            continue
        if_match = re.search(r"\bif\s*\((?P<condition>.*)\)", line)
        if if_match:
            last_condition = if_match.group("condition").strip()
            if "throw" not in line and "return" not in line:
                continue
        if "switch" in line:
            rules.append(rule(api, java_class, method, offset, "STATE_MACHINE", line, UNKNOWN, UNKNOWN))
            continue
        if any(token in line for token in ("throw new", "BusinessException", "IllegalArgumentException", "Assert.", "Preconditions.")):
            error_code = extract_error_code(line)
            exception_type = extract_exception_type(line)
            rule_type = infer_rule_type(last_condition, line, error_code)
            rules.append(rule(api, java_class, method, offset, rule_type, last_condition, error_code, exception_type))
            last_condition = UNKNOWN
        elif "return" in line and any(token in line.lower() for token in ("fail", "error", "false")):
            rules.append(rule(api, java_class, method, offset, "BUSINESS_VALIDATION", last_condition, UNKNOWN, UNKNOWN))
            last_condition = UNKNOWN
    return rules


def extract_error_code(line: str) -> str:
    if "ErrorCode" not in line and "ErrorCodeEnum" not in line:
        return UNKNOWN
    dotted = re.search(r"(?:ErrorCode|ErrorCodeEnum|CommonErrorCode)\.([A-Z][A-Z0-9_]*)", line)
    if dotted:
        return dotted.group(1)
    match = ERROR_CODE_RE.search(line)
    return match.group(1) if match else UNKNOWN


def extract_exception_type(line: str) -> str:
    match = re.search(r"new\s+(\w+Exception|\w+Error)\s*\(", line)
    if match:
        return match.group(1)
    if "Assert." in line:
        return "Assert"
    if "Preconditions." in line:
        return "Preconditions"
    return UNKNOWN


def infer_rule_type(condition: str, line: str, error_code: str) -> str:
    source = f"{condition} {line} {error_code}".lower()
    if any(token in source for token in ("status", "state", "lifecycle")):
        return "STATE_MACHINE"
    if any(token in source for token in ("idempot", "requestid", "request_id", "order_no", "biz_no")):
        return "IDEMPOTENCY"
    if any(token in source for token in ("exists", "duplicate", "unique", "already")):
        return "UNIQUE_CONSTRAINT"
    if any(token in source for token in ("permission", "role", "auth", "login")):
        return "PERMISSION"
    if error_code != UNKNOWN:
        return "ERROR_CODE"
    return "BUSINESS_VALIDATION"


def rule(
    api: dict[str, Any],
    java_class: JavaClass,
    method: Any,
    line: int,
    rule_type: str,
    condition: str,
    error_code: str,
    exception_type: str,
) -> dict[str, Any]:
    return {
        "rule_id": f"{api['api_id']}:{java_class.name}.{method.name}:{line}",
        "api_id": api["api_id"],
        "rule_type": rule_type,
        "condition": condition or UNKNOWN,
        "success_behavior": "继续执行当前方法" if condition != UNKNOWN else UNKNOWN,
        "failure_behavior": "抛出异常或返回失败结果",
        "error_code": error_code,
        "exception_type": exception_type,
        "server_judgable": "YES" if condition != UNKNOWN or exception_type != UNKNOWN else UNKNOWN,
        "evidence": evidence(java_class.path, java_class.name, method.name, line),
    }


def dedupe_rules(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict[str, Any]] = []
    for item in rules:
        key = (item["rule_type"], item["condition"], item["evidence"])
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
