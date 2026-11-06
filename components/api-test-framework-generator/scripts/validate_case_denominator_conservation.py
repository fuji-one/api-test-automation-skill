#!/usr/bin/env python3
"""校验执行级用例、生成数据与 pytest 映射之间的逐 ID 守恒。"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml


NON_DEFAULT_DECISIONS = {
    "generated_non_live",
    "manual_review_only",
    "optional_async",
    "excluded",
}
MANIFEST_NAME = "case_denominator_manifest.yaml"
GENERATED_SOURCE_PREFIXES = {
    "api",
    "configs",
    "core",
    "data",
    "reports",
    "scripts",
    "testcases",
}
GENERATED_SOURCE_DOCUMENTS = {"接口案例.md", "自动化运行配置.md", "缺陷列表.md"}


def read_yaml(path: Path, errors: list[str], label: str) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        errors.append(f"{label} 读取或 YAML 解析失败：{exc}")
        return None


def python_records(path: Path, export_name: str, errors: list[str]) -> list[dict[str, Any]]:
    """只读取常量赋值，避免为分母校验执行生成脚本。"""

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        errors.append(f"{path.name} 读取或 Python 解析失败：{exc}")
        return []
    value: Any = None
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == export_name for target in targets):
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, TypeError) as exc:
            errors.append(f"{path.name} 的 {export_name} 不是可静态读取的常量：{exc}")
            return []
    if value is None:
        return []
    if not isinstance(value, list):
        errors.append(f"{path.name} 的 {export_name} 必须是列表")
        return []
    return [item for item in value if isinstance(item, dict)]


def structured_records(
    paths: list[Path],
    yaml_key: str,
    python_export: str,
    errors: list[str],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        if path.suffix == ".py":
            records.extend(python_records(path, python_export, errors))
            continue
        payload = read_yaml(path, errors, str(path))
        items = payload.get(yaml_key) if isinstance(payload, dict) else None
        if items is None:
            continue
        if not isinstance(items, list):
            errors.append(f"{path.name} 的 {yaml_key} 必须是列表")
            continue
        records.extend(item for item in items if isinstance(item, dict))
    return records


def is_default_record(item: dict[str, Any]) -> bool:
    decision = str(item.get("automation_decision") or "").strip().lower()
    if decision in NON_DEFAULT_DECISIONS:
        return False
    if item.get("optional_async") is True:
        return False
    if item.get("live_pytest_release_ready") is False:
        return False
    return True


def record_ids(
    records: list[dict[str, Any]],
    id_key: str,
    label: str,
    errors: list[str],
) -> tuple[set[str], set[str]]:
    all_ids: list[str] = []
    default_ids: set[str] = set()
    for index, item in enumerate(records, start=1):
        record_id = str(item.get(id_key) or "").strip()
        if not record_id:
            errors.append(f"{label} 第 {index} 条缺少 {id_key}")
            continue
        all_ids.append(record_id)
        if is_default_record(item):
            default_ids.add(record_id)
    duplicates = sorted(record_id for record_id, count in Counter(all_ids).items() if count > 1)
    if duplicates:
        errors.append(f"{label} 存在重复 ID：{duplicates}")
    return set(all_ids), default_ids


def mapping_ids(status: dict[str, Any], errors: list[str]) -> tuple[set[str], set[str]]:
    section = status.get("pytest_collection_mapping")
    mappings = section.get("mappings") if isinstance(section, dict) else None
    if not isinstance(mappings, list):
        errors.append("generation_status.yaml pytest_collection_mapping.mappings 必须是列表")
        return set(), set()
    ordinary: list[str] = []
    flows: list[str] = []
    for index, item in enumerate(mappings, start=1):
        if not isinstance(item, dict):
            errors.append(f"pytest_collection_mapping.mappings 第 {index} 条必须是对象")
            continue
        case_id = str(item.get("executable_case_id") or "").strip()
        flow_id = str(item.get("flow_id") or "").strip()
        if bool(case_id) == bool(flow_id):
            errors.append(f"pytest_collection_mapping.mappings 第 {index} 条必须且只能声明一种 ID")
            continue
        (ordinary if case_id else flows).append(case_id or flow_id)
    for label, values in (("普通用例 pytest 映射", ordinary), ("E2E Flow pytest 映射", flows)):
        duplicates = sorted(item_id for item_id, count in Counter(values).items() if count > 1)
        if duplicates:
            errors.append(f"{label} 存在重复 ID：{duplicates}")
    return set(ordinary), set(flows)


def executable_case_ids(path: Path, errors: list[str]) -> set[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        errors.append(f"执行级接口用例集读取失败：{exc}")
        return set()
    ids = {
        match.group(1).strip("`\"'")
        for match in re.finditer(r"(?m)^\s*(?:[-*]\s*)?用例ID\s*[：:]\s*([^\s|]+)", text)
    }
    case_id_column: int | None = None
    for raw_line in text.splitlines():
        if not raw_line.strip().startswith("|"):
            case_id_column = None
            continue
        cells = [cell.strip() for cell in raw_line.strip().strip("|").split("|")]
        if "用例ID" in cells:
            case_id_column = cells.index("用例ID")
            continue
        if case_id_column is None or case_id_column >= len(cells):
            continue
        value = cells[case_id_column].strip("`\"'")
        if value and not re.fullmatch(r"[-: ]+", value):
            ids.add(value)
    if not ids:
        errors.append("执行级接口用例集缺少可机器识别的用例ID")
    return ids


def required_flow_ids(path: Path, errors: list[str]) -> set[str]:
    payload = read_yaml(path, errors, "required_chain_flows.yaml")
    items = payload.get("flows") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        errors.append("required_chain_flows.yaml flows 必须是列表")
        return set()
    values: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("status") or "required").strip().lower() != "required":
            continue
        flow_id = str(item.get("flow_id") or "").strip()
        if flow_id:
            values.append(flow_id)
    duplicates = sorted(flow_id for flow_id, count in Counter(values).items() if count > 1)
    if duplicates:
        errors.append(f"required_chain_flows.yaml 存在重复 flow_id：{duplicates}")
    return set(values)


def supplemental_ids(
    section: Any,
    id_key: str,
    label: str,
    errors: list[str],
) -> set[str]:
    if not isinstance(section, dict):
        errors.append(f"{MANIFEST_NAME} 缺少 {label} 对象")
        return set()
    groups = section.get("supplemental_groups", [])
    if not isinstance(groups, list):
        errors.append(f"{MANIFEST_NAME} {label}.supplemental_groups 必须是列表")
        return set()
    values: list[str] = []
    for index, group in enumerate(groups, start=1):
        if not isinstance(group, dict):
            errors.append(f"{MANIFEST_NAME} {label}.supplemental_groups 第 {index} 组必须是对象")
            continue
        group_id = str(group.get("group_id") or "").strip()
        source_refs = group.get("source_refs")
        group_ids = group.get(id_key)
        if not group_id:
            errors.append(f"{MANIFEST_NAME} {label} 补充分组第 {index} 组缺少 group_id")
        if not isinstance(source_refs, list) or not any(str(ref).strip() for ref in source_refs):
            errors.append(f"{MANIFEST_NAME} {label} 补充分组 {group_id or index} 缺少 source_refs")
        if not isinstance(group_ids, list) or not group_ids:
            errors.append(f"{MANIFEST_NAME} {label} 补充分组 {group_id or index} 缺少 {id_key}")
            continue
        values.extend(str(item).strip() for item in group_ids if str(item).strip())
    duplicates = sorted(item_id for item_id, count in Counter(values).items() if count > 1)
    if duplicates:
        errors.append(f"{MANIFEST_NAME} {label} 补充 ID 重复：{duplicates}")
    return set(values)


def is_generated_source_ref(framework: Path, source_ref: str) -> bool:
    """识别把框架生成物反向声明为上游权威来源的循环证据。"""

    value = source_ref.split("#", 1)[0].strip().replace("\\", "/")
    if not value or "://" in value or "@" in value.split("/", 1)[0]:
        return False
    if value.startswith("../"):
        return False
    if value.startswith("/"):
        try:
            Path(value).resolve().relative_to(framework.resolve())
            return True
        except ValueError:
            return False
    normalized = value.removeprefix("./")
    first = normalized.split("/", 1)[0]
    return first in GENERATED_SOURCE_PREFIXES or normalized in GENERATED_SOURCE_DOCUMENTS


def validate_v2_source_integrity(
    framework: Path,
    manifest: dict[str, Any],
    errors: list[str],
) -> None:
    if str(manifest.get("source_integrity") or "").strip() != "upstream_authoritative":
        errors.append(f"{MANIFEST_NAME} schema_version=2 时 source_integrity 必须为 upstream_authoritative")
    for section_name in ("ordinary", "flows"):
        section = manifest.get(section_name)
        groups = section.get("supplemental_groups", []) if isinstance(section, dict) else []
        if not isinstance(groups, list):
            continue
        for index, group in enumerate(groups, start=1):
            if not isinstance(group, dict):
                continue
            group_id = str(group.get("group_id") or index)
            refs = group.get("source_refs")
            if not isinstance(refs, list):
                continue
            circular = [str(ref) for ref in refs if is_generated_source_ref(framework, str(ref))]
            if circular:
                errors.append(
                    f"{MANIFEST_NAME} {section_name} 补充分组 {group_id} 的 source_refs 反向引用生成物：{circular}"
                )


def declared_id_list(section: Any, key: str, label: str, errors: list[str]) -> set[str]:
    if not isinstance(section, dict):
        return set()
    values = section.get(key, [])
    if not isinstance(values, list):
        errors.append(f"{MANIFEST_NAME} {label}.{key} 必须是列表")
        return set()
    normalized = [str(item).strip() for item in values if str(item).strip()]
    duplicates = sorted(item_id for item_id, count in Counter(normalized).items() if count > 1)
    if duplicates:
        errors.append(f"{MANIFEST_NAME} {label}.{key} 存在重复 ID：{duplicates}")
    return set(normalized)


def compare_sets(expected: set[str], actual: set[str], label: str, errors: list[str]) -> None:
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        errors.append(f"{label} 缺少 ID：{missing}")
    if extra:
        errors.append(f"{label} 存在分母外 ID：{extra}")


def validate_case_denominator_conservation(
    framework: Path,
    *,
    executable_case_set: Path | None = None,
    required_chain_flows: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    status_path = framework / "configs" / "generation_status.yaml"
    if not status_path.is_file():
        return ["缺少 configs/generation_status.yaml，无法校验用例分母守恒"]
    status = read_yaml(status_path, errors, "generation_status.yaml")
    if not isinstance(status, dict):
        return errors or ["generation_status.yaml 顶层必须是对象"]

    case_dir = framework / "data" / "cases"
    case_paths = sorted([*case_dir.glob("*.yaml"), *case_dir.glob("*.yml"), *case_dir.glob("*.py")])
    flow_paths = [
        path
        for path in (framework / "data" / "flow_cases.yaml", framework / "data" / "flow_cases.yml", framework / "data" / "flow_cases.py")
        if path.is_file()
    ]
    case_records = structured_records(case_paths, "cases", "CASES", errors)
    flow_records = structured_records(flow_paths, "flows", "FLOWS", errors)
    all_case_ids, default_case_ids = record_ids(case_records, "case_id", "data/cases", errors)
    all_flow_ids, default_flow_ids = record_ids(flow_records, "flow_id", "data/flow_cases", errors)
    mapped_case_ids, mapped_flow_ids = mapping_ids(status, errors)

    # collection 映射覆盖全部生成条目；live/non-live 由既有运行分母门禁另行判定。
    compare_sets(all_case_ids, mapped_case_ids, "普通用例数据与 pytest 映射", errors)
    compare_sets(all_flow_ids, mapped_flow_ids, "E2E Flow 数据与 pytest 映射", errors)

    source_case_ids: set[str] = set()
    source_flow_ids: set[str] = set()
    if executable_case_set is not None and executable_case_set.is_file():
        source_case_ids = executable_case_ids(executable_case_set, errors)
        missing = sorted(source_case_ids - all_case_ids)
        if missing:
            errors.append(f"执行级接口用例未进入生成用例数据：{missing}")
    if required_chain_flows is not None and required_chain_flows.is_file():
        source_flow_ids = required_flow_ids(required_chain_flows, errors)
        missing = sorted(source_flow_ids - all_flow_ids)
        if missing:
            errors.append(f"上游必需 Flow 未进入生成 Flow 数据：{missing}")

    manifest_path = framework / "configs" / MANIFEST_NAME
    status_gate = status.get("case_denominator_conservation")
    if not manifest_path.is_file():
        if status_gate is not None:
            errors.append(f"generation_status.yaml 已声明 case_denominator_conservation，但缺少 configs/{MANIFEST_NAME}")
        return errors

    manifest = read_yaml(manifest_path, errors, MANIFEST_NAME)
    if not isinstance(manifest, dict):
        return errors
    schema_version = manifest.get("schema_version")
    if schema_version not in {1, 2}:
        errors.append(f"{MANIFEST_NAME} schema_version 必须为 1 或 2")
    if schema_version == 2:
        validate_v2_source_integrity(framework, manifest, errors)
    if str(manifest.get("status") or "").strip() != "passed":
        errors.append(f"{MANIFEST_NAME} status 必须为 passed")
    if not isinstance(status_gate, dict) or str(status_gate.get("status") or "").strip() != "passed":
        errors.append("generation_status.yaml case_denominator_conservation.status 必须为 passed")
    if executable_case_set is None or not executable_case_set.is_file():
        errors.append(f"存在 {MANIFEST_NAME} 时必须提供执行级接口用例集")
    ordinary_section = manifest.get("ordinary")
    flow_section = manifest.get("flows")
    required_flow_source = (
        str(flow_section.get("required_source") or "required_chain_flows").strip()
        if isinstance(flow_section, dict)
        else "required_chain_flows"
    )
    if required_flow_source not in {"required_chain_flows", "not_available"}:
        errors.append(f"{MANIFEST_NAME} flows.required_source 非法：{required_flow_source}")
    elif required_flow_source == "required_chain_flows" and (
        required_chain_flows is None or not required_chain_flows.is_file()
    ):
        errors.append(f"存在 {MANIFEST_NAME} 且 flows.required_source=required_chain_flows 时必须提供该文件")
    supplemental_case_ids = supplemental_ids(ordinary_section, "case_ids", "ordinary", errors)
    supplemental_flow_ids = supplemental_ids(flow_section, "flow_ids", "flows", errors)
    non_default_case_ids = declared_id_list(
        ordinary_section, "non_default_case_ids", "ordinary", errors
    )
    non_default_flow_ids = declared_id_list(flow_section, "non_default_flow_ids", "flows", errors)
    expected_case_ids = source_case_ids | supplemental_case_ids
    expected_flow_ids = source_flow_ids | supplemental_flow_ids
    compare_sets(expected_case_ids, all_case_ids, "普通用例冻结分母与生成数据", errors)
    compare_sets(expected_flow_ids, all_flow_ids, "E2E Flow 冻结分母与生成数据", errors)
    compare_sets(expected_case_ids, mapped_case_ids, "普通用例冻结分母与 pytest 映射", errors)
    compare_sets(expected_flow_ids, mapped_flow_ids, "E2E Flow 冻结分母与 pytest 映射", errors)
    compare_sets(non_default_case_ids, all_case_ids - default_case_ids, "普通用例非默认分母声明与数据分类", errors)
    compare_sets(non_default_flow_ids, all_flow_ids - default_flow_ids, "E2E Flow 非默认分母声明与数据分类", errors)
    if isinstance(status_gate, dict):
        expected_summary = {
            "ordinary_source_count": len(source_case_ids),
            "ordinary_supplemental_count": len(supplemental_case_ids),
            "ordinary_generated_count": len(all_case_ids),
            "flow_source_count": len(source_flow_ids),
            "flow_supplemental_count": len(supplemental_flow_ids),
            "flow_generated_count": len(all_flow_ids),
        }
        if str(status_gate.get("manifest_path") or "").strip() != f"configs/{MANIFEST_NAME}":
            errors.append("generation_status.yaml case_denominator_conservation.manifest_path 非法或缺失")
        for field, expected in expected_summary.items():
            actual = status_gate.get(field)
            if isinstance(actual, bool) or not isinstance(actual, int) or actual != expected:
                errors.append(
                    f"generation_status.yaml case_denominator_conservation.{field} 不一致：{actual} != {expected}"
                )
        for field in (
            "missing_case_ids",
            "extra_case_ids",
            "missing_flow_ids",
            "extra_flow_ids",
            "duplicate_ids",
        ):
            if status_gate.get(field) != []:
                errors.append(
                    f"generation_status.yaml case_denominator_conservation.{field} 必须是空列表"
                )
    return errors


def default_upstream_paths(framework: Path) -> tuple[Path, Path]:
    pipeline_root = framework.parent
    return (
        pipeline_root / "05-executable-interface-case-set" / "执行级接口用例集.md",
        pipeline_root / "required_chain_flows.yaml",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 API 自动化脚本的用例分母逐 ID 守恒")
    parser.add_argument("framework", type=Path, help="api-test-framework 目录")
    parser.add_argument("--executable-case-set", type=Path, help="执行级接口用例集.md")
    parser.add_argument("--required-chain-flows", type=Path, help="required_chain_flows.yaml")
    args = parser.parse_args()
    default_case_set, default_flows = default_upstream_paths(args.framework)
    errors = validate_case_denominator_conservation(
        args.framework,
        executable_case_set=args.executable_case_set or default_case_set,
        required_chain_flows=args.required_chain_flows or default_flows,
    )
    if errors:
        print("用例分母守恒校验失败：")
        for error in errors:
            print(f"- {error}")
        return 1
    print("用例分母守恒校验通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
