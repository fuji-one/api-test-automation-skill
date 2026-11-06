#!/usr/bin/env python3
"""校验 SQL 运行生命周期门禁的条件适用性和证据完整性。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

import yaml


CAPABILITY_NAMES = (
    "sql_runtime_stages",
    "sql_runtime_preflight",
    "preflight_consumes_runtime_variables",
    "explicit_subset_selection",
    "dynamic_database_expectations",
)

CHECK_RULES: dict[str, Callable[[dict[str, bool]], bool]] = {
    "phase_isolation": lambda value: value["sql_runtime_stages"] and value["sql_runtime_preflight"],
    "runtime_context_parity": lambda value: value["sql_runtime_preflight"]
    and value["preflight_consumes_runtime_variables"],
    "selection_closure": lambda value: value["sql_runtime_preflight"]
    and value["explicit_subset_selection"],
    "dynamic_baseline_source": lambda value: value["dynamic_database_expectations"],
    "validation_evidence_scope": lambda value: value["sql_runtime_preflight"]
    and value["explicit_subset_selection"],
}


def load_audit(path: Path) -> dict[str, Any]:
    """读取 UTF-8 YAML 门禁产物。"""

    with path.open("r", encoding="utf-8") as file:
        value = yaml.safe_load(file)
    if not isinstance(value, dict):
        raise ValueError("SQL 运行生命周期门禁必须是 YAML 对象")
    return value


def validate_audit(audit: dict[str, Any]) -> list[str]:
    """返回门禁错误；未知扩展字段不参与阻塞，保留架构扩展能力。"""

    errors: list[str] = []
    if audit.get("schema_version") != 1:
        errors.append("schema_version 必须为 1")

    raw_capabilities = audit.get("capabilities")
    if not isinstance(raw_capabilities, dict):
        return [*errors, "capabilities 必须是对象"]
    capabilities: dict[str, bool] = {}
    for name in CAPABILITY_NAMES:
        value = raw_capabilities.get(name)
        if type(value) is not bool:
            errors.append(f"capabilities.{name} 必须是布尔值")
            continue
        capabilities[name] = value
    if len(capabilities) != len(CAPABILITY_NAMES):
        return errors

    raw_checks = audit.get("checks")
    if not isinstance(raw_checks, dict):
        return [*errors, "checks 必须是对象"]

    applicable_count = 0
    for name, applies_when in CHECK_RULES.items():
        applies = applies_when(capabilities)
        applicable_count += int(applies)
        check = raw_checks.get(name)
        if not isinstance(check, dict):
            errors.append(f"checks.{name} 必须是对象")
            continue
        status = check.get("status")
        if applies:
            if status != "passed":
                errors.append(f"checks.{name} 适用时必须为 passed")
            evidence = check.get("evidence")
            if not isinstance(evidence, list) or not evidence or any(
                not isinstance(item, str) or not item.strip() for item in evidence
            ):
                errors.append(f"checks.{name}.evidence 必须包含非空证据")
            continue
        if status != "not_applicable":
            errors.append(f"checks.{name} 不适用时必须为 not_applicable")
        reason = check.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"checks.{name}.reason 在不适用时不能为空")

    expected_status = "passed" if applicable_count else "not_applicable"
    if audit.get("status") != expected_status:
        errors.append(f"status 应为 {expected_status}")
    blocking_issues = audit.get("blocking_issues")
    if not isinstance(blocking_issues, list):
        errors.append("blocking_issues 必须是列表")
    elif blocking_issues:
        errors.append("通过或不适用的门禁不能包含 blocking_issues")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 SQL 运行生命周期门禁产物")
    parser.add_argument("audit_file", type=Path, help="configs/sql_runtime_lifecycle_gate.yaml 路径")
    args = parser.parse_args()

    errors = validate_audit(load_audit(args.audit_file))
    if errors:
        print(json.dumps({"status": "failed", "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"status": "passed", "audit_file": str(args.audit_file)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
