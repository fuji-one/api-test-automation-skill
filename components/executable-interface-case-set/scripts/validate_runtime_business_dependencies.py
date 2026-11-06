#!/usr/bin/env python3
"""校验执行级产物中的可变运行时业务依赖审计。"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml


YAML_BLOCK_RE = re.compile(r"```ya?ml\s*\n(.*?)\n```", re.DOTALL | re.IGNORECASE)
DEPENDENCY_TYPES = {
    "mutable_dictionary_state",
    "mutable_configuration_state",
    "mutable_eligibility_state",
    "quota_or_limit_state",
    "external_runtime_state",
}
RUNNABLE_PRECHECK_MODES = {"api_query", "sql_query", "fixture_assertion", "isolated_state"}
AUTOMATION_DECISIONS = {"runnable", "generated_non_live", "manual_review_only"}


def _read_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if "\ufffd" in text:
        raise ValueError(f"{path.name} 存在疑似中文乱码字符")
    loaded = yaml.safe_load(text)
    if not isinstance(loaded, dict):
        raise ValueError(f"{path.name} 顶层必须是对象")
    return loaded


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _nonempty_strings(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item.strip() for item in value)


def _case_ids_from_text(text: str) -> list[str]:
    case_ids: list[str] = []
    for block in YAML_BLOCK_RE.findall(text):
        loaded = yaml.safe_load(block)
        entries = loaded if isinstance(loaded, list) else []
        for case in entries:
            if isinstance(case, dict) and isinstance(case.get("用例ID"), str):
                case_ids.append(case["用例ID"])
    return case_ids


def _all_case_ids(output_dir: Path) -> list[str]:
    texts = [(output_dir / "执行级接口用例集.md").read_text(encoding="utf-8")]
    shard_dir = output_dir / "执行级用例分片"
    if shard_dir.is_dir():
        texts.extend(path.read_text(encoding="utf-8") for path in sorted(shard_dir.glob("*.md")))
    return [case_id for text in texts for case_id in _case_ids_from_text(text)]


def _validate_dependency(item: Any, valid_case_ids: set[str], seen_ids: set[str], errors: list[str]) -> None:
    if not isinstance(item, dict):
        errors.append("runtime_business_dependency_audit.dependency_items 每项必须是对象")
        return
    dependency_id = item.get("dependency_id")
    case_id = item.get("case_id")
    if not isinstance(dependency_id, str) or not dependency_id.strip():
        errors.append("运行时业务依赖缺少 dependency_id")
    elif dependency_id in seen_ids:
        errors.append(f"运行时业务依赖 ID 重复：{dependency_id}")
    else:
        seen_ids.add(dependency_id)
    if case_id not in valid_case_ids:
        errors.append(f"运行时业务依赖引用未知用例：{case_id}")
    if item.get("dependency_type") not in DEPENDENCY_TYPES:
        errors.append(f"{dependency_id} 的 dependency_type 非法：{item.get('dependency_type')}")
    if not _nonempty_strings(item.get("request_paths")):
        errors.append(f"{dependency_id} 的 request_paths 必须是非空路径列表")
    predicates = item.get("required_predicates")
    if not isinstance(predicates, dict) or not predicates:
        errors.append(f"{dependency_id} 的 required_predicates 必须是非空对象")
    if not _nonempty_strings(item.get("source_refs")):
        errors.append(f"{dependency_id} 的 source_refs 必须是非空来源列表")
    decision = item.get("automation_decision")
    if decision not in AUTOMATION_DECISIONS:
        errors.append(f"{dependency_id} 的 automation_decision 非法：{decision}")
        return
    precheck = item.get("precheck")
    if not isinstance(precheck, dict):
        errors.append(f"{dependency_id} 缺少 precheck 对象")
        return
    mode = precheck.get("mode")
    if decision == "runnable":
        if mode not in RUNNABLE_PRECHECK_MODES:
            errors.append(f"{dependency_id} 的 runnable 预检模式非法：{mode}")
        executable_ref = precheck.get("executable_ref")
        if not isinstance(executable_ref, str) or not executable_ref.strip():
            errors.append(f"{dependency_id} 的 runnable 预检缺少 executable_ref")
        if precheck.get("changes_state") is True:
            restore_ref = precheck.get("restore_ref")
            if not isinstance(restore_ref, str) or not restore_ref.strip():
                errors.append(f"{dependency_id} 的有状态预检缺少 restore_ref")
    else:
        if mode != "non_live":
            errors.append(f"{dependency_id} 的非实时自动化决策必须使用 precheck.mode=non_live")
        reason = precheck.get("blocking_reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"{dependency_id} 的非实时自动化决策缺少 blocking_reason")


def validate_runtime_business_dependencies(output_dir: Path) -> list[str]:
    errors: list[str] = []
    stage_status_path = output_dir / "stage_status.yaml"
    fact_path = output_dir / "execution_fact_sources.yaml"
    if not stage_status_path.is_file() or not fact_path.is_file():
        return errors
    try:
        stage_status = _read_yaml(stage_status_path).get("status")
        facts = _read_yaml(fact_path)
    except (OSError, UnicodeDecodeError, ValueError, yaml.YAMLError) as exc:
        return [str(exc)]
    if stage_status != "passed":
        return errors
    audit = facts.get("runtime_business_dependency_audit")
    if not isinstance(audit, dict):
        return ["PASSED 产物缺少 execution_fact_sources.yaml.runtime_business_dependency_audit"]
    try:
        case_ids = _all_case_ids(output_dir)
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        return [f"读取执行级用例失败：{exc}"]
    if len(case_ids) != len(set(case_ids)):
        errors.append("运行时业务依赖审计发现重复用例 ID")
    scanned_case_ids = audit.get("scanned_case_ids")
    if not isinstance(scanned_case_ids, list) or set(scanned_case_ids) != set(case_ids) or len(scanned_case_ids) != len(case_ids):
        errors.append("runtime_business_dependency_audit.scanned_case_ids 必须与全部执行级用例精确一致")
    unresolved = audit.get("unresolved_candidate_case_ids")
    if unresolved != []:
        errors.append("runtime_business_dependency_audit.unresolved_candidate_case_ids 必须为空")
    status = audit.get("status")
    items = _as_list(audit.get("dependency_items"))
    if status == "not_required":
        if items:
            errors.append("runtime_business_dependency_audit.status=not_required 时 dependency_items 必须为空")
        return errors
    if status != "passed":
        errors.append(f"PASSED 阶段的 runtime_business_dependency_audit.status 必须是 passed 或 not_required：{status}")
        return errors
    if not items:
        errors.append("runtime_business_dependency_audit.status=passed 时 dependency_items 不能为空")
        return errors
    seen_ids: set[str] = set()
    for item in items:
        _validate_dependency(item, set(case_ids), seen_ids, errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="校验执行级可变运行时业务依赖")
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    errors = validate_runtime_business_dependencies(args.output_dir)
    if errors:
        print("运行时业务依赖校验：不通过")
        for index, error in enumerate(errors, start=1):
            print(f"{index}. {error}")
        return 1
    print("运行时业务依赖校验：通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
