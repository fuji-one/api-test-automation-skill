#!/usr/bin/env python3
"""校验可变运行时业务依赖从执行级审计到生成脚本的物化。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


AUDIT_FILE = "configs/runtime_business_dependency_audit.yaml"
DEPENDENCY_TYPES = {
    "mutable_dictionary_state",
    "mutable_configuration_state",
    "mutable_eligibility_state",
    "quota_or_limit_state",
    "external_runtime_state",
}
RUNNABLE_MODES = {"api_query", "sql_query", "fixture_assertion", "isolated_state"}


def _read_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if "\ufffd" in text:
        raise ValueError(f"{path} 存在疑似中文乱码字符")
    loaded = yaml.safe_load(text)
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} 顶层必须是对象")
    return loaded


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _load_cases(project_root: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    cases: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for path in sorted((project_root / "data" / "cases").glob("*.yaml")):
        for case in _as_list(_read_yaml(path).get("cases")):
            if not isinstance(case, dict):
                continue
            case_id = case.get("case_id")
            if not isinstance(case_id, str) or not case_id:
                errors.append(f"{path.name} 存在缺少 case_id 的用例")
            elif case_id in cases:
                errors.append(f"用例 ID 重复：{case_id}")
            else:
                cases[case_id] = case
    return cases, errors


def _sql_case_ids(project_root: Path) -> set[str]:
    path = project_root / "data" / "case_sql_commands.yaml"
    if not path.is_file():
        return set()
    cases = _read_yaml(path).get("cases")
    return set(cases) if isinstance(cases, dict) else set()


def _nonempty_strings(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item.strip() for item in value)


def _materialized_precheck(case_id: str, case: dict[str, Any], precheck: dict[str, Any], sql_case_ids: set[str]) -> bool:
    mode = precheck.get("mode")
    if mode == "api_query":
        return bool(_as_list(case.get("preconditions")))
    if mode == "sql_query":
        return case_id in sql_case_ids
    if mode == "fixture_assertion":
        return bool(_as_list(case.get("preconditions"))) or isinstance(case.get("setup_cleanup_materialization"), dict)
    if mode == "isolated_state":
        return isinstance(case.get("business_state_isolation"), dict) or isinstance(case.get("setup_cleanup_materialization"), dict)
    return False


def _dependency_by_id(case: dict[str, Any], dependency_id: str) -> dict[str, Any] | None:
    for item in _as_list(case.get("runtime_business_dependencies")):
        if isinstance(item, dict) and item.get("dependency_id") == dependency_id:
            return item
    return None


def validate_project(project_root: Path) -> dict[str, Any]:
    audit_path = project_root / AUDIT_FILE
    if not audit_path.is_file():
        return {
            "schema_version": 1,
            "gate": "runtime_business_dependency_materialization",
            "status": "failed",
            "audit_path": AUDIT_FILE,
            "errors": [f"缺少运行时业务依赖审计：{AUDIT_FILE}"],
        }
    audit = _read_yaml(audit_path)
    cases, errors = _load_cases(project_root)
    sql_case_ids = _sql_case_ids(project_root)
    scanned = audit.get("scanned_case_ids")
    if not isinstance(scanned, list) or set(scanned) != set(cases) or len(scanned) != len(cases):
        errors.append("scanned_case_ids 必须与 data/cases 全部用例精确一致")
    if audit.get("unresolved_candidate_case_ids") != []:
        errors.append("unresolved_candidate_case_ids 必须为空")
    status = audit.get("status")
    dependency_items = _as_list(audit.get("dependency_items"))
    materialized_count = 0
    if status == "not_required":
        if dependency_items:
            errors.append("status=not_required 时 dependency_items 必须为空")
        cases_with_dependencies = sorted(
            case_id for case_id, case in cases.items() if _as_list(case.get("runtime_business_dependencies"))
        )
        if cases_with_dependencies:
            errors.append(f"审计为 not_required，但生成用例仍声明运行时业务依赖：{cases_with_dependencies}")
    elif status == "passed":
        if not dependency_items:
            errors.append("status=passed 时 dependency_items 不能为空")
        seen: set[str] = set()
        for item in dependency_items:
            if not isinstance(item, dict):
                errors.append("dependency_items 每项必须是对象")
                continue
            dependency_id = item.get("dependency_id")
            case_id = item.get("case_id")
            if not isinstance(dependency_id, str) or not dependency_id:
                errors.append("运行时业务依赖缺少 dependency_id")
                continue
            if dependency_id in seen:
                errors.append(f"运行时业务依赖 ID 重复：{dependency_id}")
                continue
            seen.add(dependency_id)
            case = cases.get(case_id)
            if case is None:
                errors.append(f"{dependency_id} 引用未知用例：{case_id}")
                continue
            if item.get("dependency_type") not in DEPENDENCY_TYPES:
                errors.append(f"{dependency_id} 的 dependency_type 非法")
            if not _nonempty_strings(item.get("request_paths")):
                errors.append(f"{dependency_id} 的 request_paths 必须是非空列表")
            if not isinstance(item.get("required_predicates"), dict) or not item["required_predicates"]:
                errors.append(f"{dependency_id} 的 required_predicates 必须是非空对象")
            generated = _dependency_by_id(case, dependency_id)
            if generated is None:
                errors.append(f"{dependency_id} 未物化到生成用例 {case_id}")
                continue
            for field in ("dependency_type", "request_paths", "required_predicates", "automation_decision"):
                if generated.get(field) != item.get(field):
                    errors.append(f"{dependency_id} 的 {field} 在审计与生成用例间不一致")
            precheck = item.get("precheck")
            generated_precheck = generated.get("precheck")
            if not isinstance(precheck, dict) or not isinstance(generated_precheck, dict):
                errors.append(f"{dependency_id} 缺少可比对的 precheck")
                continue
            if generated_precheck != precheck:
                errors.append(f"{dependency_id} 的 precheck 在审计与生成用例间不一致")
            decision = item.get("automation_decision")
            if decision == "runnable":
                if precheck.get("mode") not in RUNNABLE_MODES:
                    errors.append(f"{dependency_id} 的 runnable 预检模式非法")
                elif not _materialized_precheck(str(case_id), case, precheck, sql_case_ids):
                    errors.append(f"{dependency_id} 的预检未物化为可执行 API/SQL/fixture/隔离状态")
                else:
                    materialized_count += 1
                if precheck.get("changes_state") is True:
                    if not isinstance(precheck.get("restore_ref"), str) or not precheck["restore_ref"].strip():
                        errors.append(f"{dependency_id} 的有状态预检缺少 restore_ref")
                    if not _as_list(case.get("cleanup")) and str(case_id) not in sql_case_ids:
                        errors.append(f"{dependency_id} 的有状态预检未物化清理/恢复动作")
            elif decision in {"generated_non_live", "manual_review_only"}:
                if precheck.get("mode") != "non_live":
                    errors.append(f"{dependency_id} 的非实时决策必须使用 precheck.mode=non_live")
                if case.get("live_pytest_release_ready") is not False:
                    errors.append(f"{dependency_id} 的非实时用例不得标记 live_pytest_release_ready=true")
            else:
                errors.append(f"{dependency_id} 的 automation_decision 非法：{decision}")
    else:
        errors.append(f"审计 status 必须是 passed 或 not_required：{status}")
    return {
        "schema_version": 1,
        "gate": "runtime_business_dependency_materialization",
        "status": "failed" if errors else status,
        "audit_path": AUDIT_FILE,
        "scanned_case_count": len(cases),
        "dependency_count": len(dependency_items),
        "materialized_runnable_dependency_count": materialized_count,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="校验可变运行时业务依赖的脚本物化")
    parser.add_argument("project_root", type=Path)
    args = parser.parse_args()
    try:
        report = validate_project(args.project_root.resolve())
    except (OSError, UnicodeDecodeError, ValueError, yaml.YAMLError) as exc:
        report = {
            "schema_version": 1,
            "gate": "runtime_business_dependency_materialization",
            "status": "failed",
            "errors": [str(exc)],
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"passed", "not_required"} else 1


if __name__ == "__main__":
    sys.exit(main())
