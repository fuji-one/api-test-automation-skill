#!/usr/bin/env python3
"""为执行级用例阶段准备标准交接输入。"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml


ENTRY_DOCS = {
    "design": "01_接口测试用例设计文档.md",
    "contract": "02_接口结构化契约清单.md",
    "report": "03_skill执行报告.md",
}
HANDOFF_DOCS = {
    "design": "接口测试用例设计文档.md",
    "contract": "接口结构化契约清单.md",
    "case_list_yaml": "case_list.yaml",
    "case_list": "测试用例清单.md",
    "coverage_point_report": "测试覆盖点报告.md",
    "required_chain_flows": "required_chain_flows.yaml",
    "chain_flow_candidate_audit": "chain_flow_candidate_audit.yaml",
    "business_scenario_map": "business_scenario_map.yaml",
    "business_scenario_doc": "业务场景链路清单.md",
    "business_long_chain_cases": "business_long_chain_cases.yaml",
    "business_long_chain_doc": "业务长链路设计清单.md",
    "execution_report": "执行报告.md",
}
CASE_SOURCE = "04_接口测试用例清单.md"
CASE_LIST_YAML = "case_list.yaml"
COVERAGE_POINT_REPORT = "测试覆盖点报告.md"
BUSINESS_SCENARIO_MAP = "business_scenario_map.yaml"
BUSINESS_SCENARIO_DOC = "业务场景链路清单.md"
BUSINESS_LONG_CHAIN_CASES = "business_long_chain_cases.yaml"
BUSINESS_LONG_CHAIN_DOC = "业务长链路设计清单.md"
REQUIRED_CHAIN_FLOWS = "required_chain_flows.yaml"
CHAIN_FLOW_CANDIDATE_AUDIT = "chain_flow_candidate_audit.yaml"
REQUIRED_CHAIN_FLOW_REQUIRED_KEYS = (
    "schema_version",
    "stage",
    "status",
    "next_stage_allowed",
    "required_chain_flow_count",
    "flows",
    "unclassified_candidate_flows",
    "blocking_issues",
)
CHAIN_FLOW_AUDIT_REQUIRED_KEYS = (
    "schema_version",
    "stage",
    "status",
    "next_stage_allowed",
    "candidate_summary",
    "candidates",
    "unclassified_candidate_flows",
    "blocking_issues",
)
CHAIN_FLOW_ALLOWED_CANDIDATE_CLASSIFICATIONS = {
    "included",
    "design_long_chain_only",
    "design_short_chain_state_transition",
    "single_interface_mutation",
    "single_interface_readonly",
    "external_or_callback",
    "excluded_ready_by_policy",
    "excluded_missing_verification",
    "excluded_missing_change_evidence",
    "excluded_missing_link_key",
    "excluded_readonly",
}
COVERAGE_POINT_SUMMARY_TITLE = "覆盖点摘要"
COVERAGE_POINT_HEADERS = ("ID", "测试点", "业务域", "业务场景", "来源", "接口链路", "前置条件", "操作步骤", "预期结果", "优先级", "用例类型")
COVERAGE_POINT_CHINESE_FIELDS = ("测试点", "业务域", "业务场景", "前置条件", "操作步骤", "预期结果", "用例类型")
COVERAGE_POINT_PRIORITY_VALUES = {"p0", "p1", "p2"}
LONG_CHAIN_INTERFACE_THRESHOLD = 3
LONG_CHAIN_STEP_THRESHOLD = 5
COVERAGE_POINT_PLACEHOLDERS = {
    "",
    "-",
    "无",
    "暂无",
    "待确认",
    "待补充",
    "未知",
    "不详",
    "TBD",
    "tbd",
    "UNKNOWN",
    "unknown",
    "N/A",
    "n/a",
    "NA",
    "null",
    "None",
    "none",
}
QUALITY_MARKER_GROUPS = {
    "质量结论": ("## 质检结论", "## 质量结论"),
    "覆盖结论": ("## 覆盖矩阵", "## 覆盖结论", "## 覆盖率准出摘要"),
    "阻塞项": ("## 阻塞项",),
    "修正建议": ("## 修正建议",),
    "准出结论": ("## 准出结论", "## 交付结论", "## 放行结论", "## 发布结论"),
}
CASE_MARKERS = ("## 接口测试用例", "## 接口测试用例清单", "用例名称", "追溯接口")
SECTION_HEADING_RE = re.compile(r"^##+\s+(.+?)\s*$", re.MULTILINE)
COVERAGE_BLOCKING_TERMS = ("覆盖不足", "未覆盖", "待补充", "阻塞")
CONCLUSION_BLOCKING_TERMS = ("覆盖不足", "阻塞", "不通过")
NONE_MARKERS = ("无", "暂无", "不涉及", "无阻塞", "无未关闭", "已关闭")
DENY_PATTERNS = (
    re.compile(r"是否允许[^：:\n]*(?:100%|覆盖|进入下一阶段)[^：:\n]*[：:]\s*否"),
    re.compile(r"是否进入生成阶段[^：:\n]*[：:]\s*否"),
    re.compile(r"不允许声明"),
    re.compile(r"不允许进入"),
)
ALLOW_100_PATTERN = re.compile(r"是否允许[^：:\n]*(?:100%|覆盖)[^：:\n]*[：:]\s*是")
RATIO_PATTERN = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)(?![\d.])")
PERCENT_PATTERN = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*%")
YAML_SCALAR_RE = re.compile(r"^\s*(?:-\s*)?([A-Za-z0-9_]+)\s*:\s*(.*?)\s*$")
YAML_TOP_LEVEL_KEY_RE = re.compile(r"^([A-Za-z0-9_]+)\s*:", re.MULTILINE)
SIDECAR_STATUS_VALUES = {"passed", "blocked", "failed", "coverage_insufficient"}
SOURCE_FAILED_STATUS_VALUES = {"failed", "fail", "error", "不通过", "失败"}
SOURCE_ARTIFACT_REQUIRED_NAMES = (
    "source_api_design_doc",
    "source_api_contract_list",
    "source_api_stage_report",
    "source_api_business_scenario_map",
    "source_api_business_scenario_doc",
    "source_api_stage_status",
    "source_api_coverage_matrix",
    "source_api_fact_json",
    "source_api_fact_artifact_manifest",
)
PRE_DOC_COVERAGE_PAIRS = (
    ("object_total", "object_covered"),
    ("test_point_total", "test_point_mapped"),
    ("rule_total", "rule_covered"),
)
PRE_DOC_MISSING_LISTS = ("missing_object_ids", "missing_test_point_ids", "missing_rule_ids")
SOURCE_COVERAGE_PAIRS = (
    ("source_interface_total", "source_interface_covered"),
    ("source_contract_rule_total", "source_contract_rule_covered"),
    ("source_business_rule_total", "source_business_rule_covered"),
    ("source_error_code_total", "source_error_code_covered"),
    ("source_db_side_effect_total", "source_db_side_effect_covered"),
    ("source_scenario_total", "source_scenario_covered"),
)
SOURCE_MISSING_LISTS = (
    "missing_source_interface_ids",
    "missing_source_contract_rule_ids",
    "missing_source_business_rule_ids",
    "missing_source_error_code_ids",
    "missing_source_db_side_effect_ids",
    "missing_source_scenario_ids",
)
INTERFACE_COVERAGE_PAIRS = (
    ("test_point_total", "test_point_covered"),
    ("main_flow_total", "main_flow_covered"),
    ("contract_rule_total", "contract_rule_covered"),
    ("status_code_total", "status_code_covered"),
    ("p0_p1_total", "p0_p1_covered"),
)
INTERFACE_MISSING_LISTS = (
    "missing_test_point_ids",
    "missing_main_flow_ids",
    "missing_contract_rule_ids",
    "missing_status_codes",
    "missing_p0_p1_ids",
)
CHAIN_COVERAGE_PAIRS = (
    ("chain_scenario_total", "chain_scenario_covered"),
    ("chain_function_total", "chain_function_covered"),
    ("chain_process_total", "chain_process_covered"),
)
CHAIN_COVERAGE_MISSING_LISTS = (
    "missing_chain_scenario_ids",
    "missing_chain_function_ids",
    "missing_chain_process_ids",
)
BUSINESS_SCENARIO_REQUIRED_KEYS = (
    "schema_version",
    "stage",
    "status",
    "next_stage_allowed",
    "source_entry",
    "scenario_items",
    "blocking_issues",
)
BUSINESS_SCENARIO_REQUIRED_ITEM_MARKERS = (
    "scenario_id",
    "scenario_name",
    "business_domain",
    "executing_role",
    "business_description",
    "roles",
    "source_refs",
    "related_interfaces",
    "business_chain",
    "chain_type",
    "flow_generation_required",
    "related_test_point_ids",
    "related_coverage_rule_ids",
    "confidence",
    "blockers",
)
BUSINESS_LONG_CHAIN_REQUIRED_KEYS = (
    "schema_version",
    "stage",
    "status",
    "next_stage_allowed",
    "denominator_scope",
    "business_long_chain_total",
    "business_long_chain_covered",
    "script_closed_loop_ready_total",
    "missing_business_long_chain_ids",
    "chains",
    "blocking_issues",
)
BUSINESS_LONG_CHAIN_REQUIRED_ITEM_MARKERS = (
    "chain_id",
    "case_id",
    "priority",
    "business_domain",
    "scenario_name",
    "business_description",
    "executing_role",
    "chain_kind",
    "interface_count",
    "interfaces",
    "source_refs",
    "related_test_point_ids",
    "related_coverage_rule_ids",
    "design_status",
    "executable_status",
)
BUSINESS_LONG_CHAIN_DENOMINATOR_SCOPE = "business_scenario_long_chain_design"
BUSINESS_LONG_CHAIN_STAGE = "business_long_chain_design_denominator"
BUSINESS_LONG_CHAIN_EXECUTABLE_STATUSES = {
    "closed_loop_required",
    "ready",
    "not_required",
    "need_execution_input",
    "manual_confirm_required",
    "blocked_missing_execution_input",
}
BUSINESS_LONG_CHAIN_PATH_BUCKET_PATTERNS = (
    re.compile(r"\b(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b\s*/", re.IGNORECASE),
    re.compile(r"/(?:api|app|admin|internal|openapi|v\d+)(?:/|$)", re.IGNORECASE),
    re.compile(r"(?:接口|路径|URL|uri|controller|模块|包名|前缀).{0,16}(?:聚合|分组|串联|穷举)", re.IGNORECASE),
    re.compile(r"(?:调用|创建|查询|更新|删除).{0,8}接口(?:正向|反向|异常|边界)?测试", re.IGNORECASE),
    re.compile(r"(?:api/v\d+|/app|/internal).{0,20}(?:资源|接口|路径|前缀).{0,20}(?:链路|校验|测试)", re.IGNORECASE),
    re.compile(r"(?:资源|接口集合|接口组合|模块接口).{0,20}(?:业务处理到结果校验|接口链路|链路)", re.IGNORECASE),
)
HTTP_INTERFACE_RE = re.compile(r"\b(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(/[^\s，,；;]+)", re.IGNORECASE)
MUTATING_INTERFACE_RE = re.compile(r"\b(?:POST|PUT|PATCH|DELETE)\s+/", re.IGNORECASE)
READ_VERIFY_RE = re.compile(r"(?:\b(?:GET|HEAD|OPTIONS)\s+/|查询|列表|详情|状态|读取|统计|verify|check|get|list|detail|status)", re.IGNORECASE)
GENERIC_ROUTE_SEGMENTS = {
    "api",
    "app",
    "admin",
    "internal",
    "openapi",
    "v1",
    "v2",
    "v3",
}
ACTION_ROUTE_SEGMENTS = {
    "create",
    "add",
    "update",
    "delete",
    "remove",
    "get",
    "list",
    "detail",
    "query",
    "status",
    "check",
    "submit",
    "send",
    "callback",
    "verify",
    "read",
    "pay",
    "cancel",
    "confirm",
    "approve",
    "reject",
    "upload",
    "bind",
    "unbind",
    "apply",
    "publish",
    "recharge",
    "withdraw",
    "login",
    "logout",
}
CASE_LIST_REQUIRED_KEYS = (
    "schema_version",
    "stage",
    "status",
    "quality_gate",
    "cases",
    "coverage_summary",
    "case_mappings",
    "blocking_issues",
)
CASE_LIST_REQUIRED_CASE_MARKERS = (
    "case_id",
    "design_case_id",
    "test_point_ids",
    "coverage_object_ids",
    "coverage_rule_ids",
    "method",
    "path",
    "status_codes",
    "priority",
    "assertion_points",
)
CASE_LIST_REQUIRED_LIST_FIELDS = {
    "test_point_ids",
    "coverage_object_ids",
    "coverage_rule_ids",
    "status_codes",
    "assertion_points",
}


def read_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if "\ufffd" in text:
        raise ValueError(f"{path} 存在疑似中文乱码字符")
    if not text.strip():
        raise ValueError(f"{path} 内容为空")
    return text


def yaml_scalar_values(text: str, key: str) -> list[str]:
    values: list[str] = []
    for line in text.splitlines():
        match = YAML_SCALAR_RE.match(line)
        if match and match.group(1) == key:
            values.append(match.group(2).strip().strip("\"'"))
    return values


def first_yaml_scalar(text: str, key: str) -> str | None:
    values = yaml_scalar_values(text, key)
    return values[0] if values else None


def yaml_top_level_keys(text: str) -> set[str]:
    return set(YAML_TOP_LEVEL_KEY_RE.findall(text))


def require_yaml_top_level_keys(text: str, keys: tuple[str, ...], errors: list[str], label: str) -> None:
    present = yaml_top_level_keys(text)
    for key in keys:
        if key not in present:
            errors.append(f"{label} 缺少 schema 顶层字段：{key}")


def require_stage_status_schema_keys(text: str, errors: list[str], label: str, expected_stage: str) -> None:
    present = yaml_top_level_keys(text)
    base_keys = ("schema_version", "stage", "status", "next_stage_allowed", "blocking_issues")
    for key in base_keys:
        if key not in present:
            errors.append(f"{label} 缺少 schema 顶层字段：{key}")
    if {"input_paths", "output_paths", "gate_checks"} <= present:
        return
    if expected_stage == "pre_doc_analysis" and {"source_files", "stage_results", "output_files"} <= present:
        return
    for key in ("input_paths", "output_paths", "gate_checks"):
        if key not in present:
            errors.append(f"{label} 缺少 schema 顶层字段：{key}")


def require_coverage_matrix_schema_keys(text: str, errors: list[str], label: str, expected_stage: str) -> None:
    present = yaml_top_level_keys(text)
    base_keys = ("schema_version", "stage", "coverage_summary")
    for key in base_keys:
        if key not in present:
            errors.append(f"{label} 缺少 schema 顶层字段：{key}")
    if {"coverage_items", "missing_items", "upstream_downstream_mappings"} <= present:
        return
    if expected_stage == "pre_doc_analysis" and "coverage_objects" in present:
        return
    for key in ("coverage_items", "missing_items", "upstream_downstream_mappings"):
        if key not in present:
            errors.append(f"{label} 缺少 schema 顶层字段：{key}")


def yaml_int_values(text: str, key: str) -> list[int]:
    values: list[int] = []
    for value in yaml_scalar_values(text, key):
        if re.fullmatch(r"\d+", value):
            values.append(int(value))
    return values


def yaml_int_value(text: str, key: str, errors: list[str], label: str) -> int | None:
    values = yaml_int_values(text, key)
    if not values:
        errors.append(f"{label} 缺少可解析的整数字段：{key}")
        return None
    if len(set(values)) != 1:
        errors.append(f"{label} 字段 {key} 多处取值不一致：{values}")
        return None
    return values[0]


def is_yaml_true(value: str) -> bool:
    return value.strip().lower() in {"true", "yes", "是", "passed"}


def require_yaml_empty_list(text: str, key: str, errors: list[str], label: str) -> None:
    values = yaml_scalar_values(text, key)
    if not values:
        errors.append(f"{label} 缺少空缺失列表字段：{key}")
        return
    if not yaml_scalar_is_empty_list(values[0]):
        errors.append(f"{label} 缺失列表未清空：{key}={values[0]}")


def yaml_scalar_is_empty_list(value: str) -> bool:
    normalized = value.strip().strip("\"'").strip()
    return normalized == "[]"


def split_top_level_csv(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    bracket_depth = 0
    quote_char = ""
    for char in text:
        if quote_char:
            current.append(char)
            if char == quote_char:
                quote_char = ""
            continue
        if char in {"'", '"'}:
            quote_char = char
            current.append(char)
            continue
        if char == "[":
            bracket_depth += 1
        elif char == "]" and bracket_depth > 0:
            bracket_depth -= 1
        if char == "," and bracket_depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    if current:
        parts.append("".join(current).strip())
    return [part for part in parts if part]


def yaml_scalar_list_items(value: str) -> list[str]:
    normalized = value.strip()
    if not (normalized.startswith("[") and normalized.endswith("]")):
        return []
    inner = normalized[1:-1].strip()
    if not inner:
        return []
    return [item.strip().strip("\"'") for item in split_top_level_csv(inner)]


def yaml_section(text: str, key: str) -> str:
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if re.match(rf"^{re.escape(key)}\s*:\s*$", line):
            start = index + 1
            break
    if start is None:
        return ""
    end = len(lines)
    for index in range(start, len(lines)):
        if re.match(r"^[A-Za-z0-9_]+\s*:", lines[index]):
            end = index
            break
    return "\n".join(lines[start:end])


def yaml_key_block(text: str, key: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = re.match(rf"^(\s*){re.escape(key)}\s*:\s*(.*?)\s*$", line)
        if not match:
            continue
        base_indent = len(match.group(1))
        block = [match.group(2).strip()]
        for nested in lines[index + 1 :]:
            if nested.strip() and len(nested) - len(nested.lstrip(" ")) <= base_indent:
                break
            block.append(nested)
        return "\n".join(block)
    return ""


def parse_inline_mapping(text: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for part in split_top_level_csv(text):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        mapping[key.strip()] = value.strip().strip("\"'")
    return mapping


def scalar_from_block(block: str, key: str) -> str | None:
    first_line = block.splitlines()[0].strip() if block.splitlines() else ""
    if first_line.startswith("{") and first_line.endswith("}"):
        inline = parse_inline_mapping(first_line.strip("{}"))
        if key in inline:
            return inline[key]
    return first_yaml_scalar(block, key)


def gate_pass_status_from_block(block: str) -> str | None:
    return scalar_from_block(block, "status") or scalar_from_block(block, "result")


def parse_yaml_rate(value: str | None) -> float | None:
    if value is None:
        return None
    normalized = value.strip().strip("\"'").rstrip("%").strip()
    if re.fullmatch(r"\d+(?:\.\d+)?", normalized):
        return float(normalized)
    return None


def yaml_section_has_sequence_items(text: str, key: str) -> bool:
    values = yaml_scalar_values(text, key)
    if values and values[0].strip():
        return not yaml_scalar_is_empty_list(values[0])
    section = yaml_section(text, key)
    return any(re.match(r"^\s*-\s+", line) for line in section.splitlines())


def validate_status_section_passed(text: str, section_key: str, errors: list[str], label: str) -> None:
    values = yaml_scalar_values(text, section_key)
    if values and yaml_scalar_is_empty_list(values[0]):
        errors.append(f"{label} {section_key} 不能为空")
        return
    section = yaml_section(text, section_key)
    status_values = yaml_scalar_values(section, "status")
    if not status_values:
        errors.append(f"{label} {section_key} 缺少 status 明细")
        return
    for status in status_values:
        if status.strip().strip("\"'") not in {"passed", "通过"}:
            errors.append(f"{label} {section_key}.status 不是 passed：{status}")


def normalize_yaml_value(value: str | None) -> str:
    return (value or "").strip().strip("\"'").strip()


def yaml_value_is_missing(value: str | None, list_value: bool = False) -> bool:
    normalized = normalize_yaml_value(value)
    if not normalized:
        return True
    if normalized in {"[]", "{}"}:
        return True
    if normalized in COVERAGE_POINT_PLACEHOLDERS:
        return True
    if list_value and normalized.startswith("[") and normalized.endswith("]"):
        return not yaml_scalar_list_items(normalized)
    return False


def extract_yaml_sequence_blocks(text: str, section_key: str) -> list[dict[str, str]]:
    section = yaml_section(text, section_key)
    blocks: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    pending_list_key: str | None = None
    for raw_line in section.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        inline_match = re.match(r"^-\s*\{(.+)\}\s*$", stripped)
        if inline_match:
            if current is not None:
                blocks.append(current)
                current = None
            mapping = parse_inline_mapping(inline_match.group(1))
            if mapping:
                blocks.append(mapping)
            pending_list_key = None
            continue
        item_match = re.match(r"^-\s+([A-Za-z0-9_]+)\s*:\s*(.*?)\s*$", stripped)
        if item_match:
            if current is not None:
                blocks.append(current)
            value = item_match.group(2).strip().strip("\"'")
            current = {item_match.group(1): value}
            pending_list_key = item_match.group(1) if not value else None
            continue
        if current is None:
            continue
        scalar_match = re.match(r"^([A-Za-z0-9_]+)\s*:\s*(.*?)\s*$", stripped)
        if scalar_match:
            value = scalar_match.group(2).strip().strip("\"'")
            current[scalar_match.group(1)] = value
            pending_list_key = scalar_match.group(1) if not value else None
            continue
        list_item_match = re.match(r"^-\s+(.+?)\s*$", stripped)
        if list_item_match and pending_list_key:
            value = list_item_match.group(1).strip().strip("\"'")
            previous = current.get(pending_list_key, "")
            current[pending_list_key] = ",".join(item for item in (previous, value) if item)
    if current is not None:
        blocks.append(current)
    return blocks


def yaml_sequence_raw_blocks(text: str, section_key: str, first_key: str) -> list[str]:
    section = yaml_section(text, section_key)
    starts = list(re.finditer(rf"(?m)^\s*-\s+{re.escape(first_key)}\s*:", section))
    blocks: list[str] = []
    for index, start in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(section)
        blocks.append(section[start.start():end])
    return blocks


def validate_required_chain_flows_file(path: Path) -> tuple[set[str], list[str]]:
    errors: list[str] = []
    if not path.is_file():
        return set(), [f"缺少长链路必测分母：{path}"]
    try:
        text = read_text(path)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return set(), [str(exc)]

    require_yaml_top_level_keys(text, REQUIRED_CHAIN_FLOW_REQUIRED_KEYS, errors, path.name)
    stage = first_yaml_scalar(text, "stage")
    if stage != "required_chain_flow_denominator":
        errors.append(f"{path.name} stage 不匹配：{stage} != required_chain_flow_denominator")
    status = first_yaml_scalar(text, "status")
    if status != "passed":
        errors.append(f"{path.name} status 不是 passed：{status}")
    next_stage_allowed = first_yaml_scalar(text, "next_stage_allowed")
    if next_stage_allowed is None or not is_yaml_true(next_stage_allowed):
        errors.append(f"{path.name} next_stage_allowed 不是 true：{next_stage_allowed}")
    require_yaml_empty_list(text, "unclassified_candidate_flows", errors, path.name)
    require_yaml_empty_list(text, "blocking_issues", errors, path.name)

    flow_ids: list[str] = []
    for block in yaml_sequence_raw_blocks(text, "flows", "flow_id"):
        flow_id = first_yaml_scalar(block, "flow_id") or ""
        flow_status = first_yaml_scalar(block, "status")
        if flow_status != "required":
            continue
        if yaml_value_is_missing(flow_id):
            errors.append(f"{path.name} 存在缺少 flow_id 的 required flow")
            continue
        flow_ids.append(flow_id)
        business_domain = first_yaml_scalar(block, "business_domain") or ""
        scenario_name = first_yaml_scalar(block, "scenario_name") or ""
        if not has_chinese(business_domain):
            errors.append(f"{path.name} {flow_id} business_domain 必须为中文业务域")
        if not has_chinese(scenario_name):
            errors.append(f"{path.name} {flow_id} scenario_name 必须为中文业务场景名称")
        if looks_like_path_bucket_long_chain(business_domain, scenario_name):
            errors.append(f"{path.name} {flow_id} 疑似按路径/接口前缀拼接必测长链路，必须先拆成真实业务场景")
        for list_key in ("link_keys", "steps", "evidence_refs"):
            if not block_list_values(block, list_key):
                errors.append(f"{path.name} {flow_id} 缺少非空列表：{list_key}")
    if len(flow_ids) != len(set(flow_ids)):
        errors.append(f"{path.name} required flow_id 存在重复：{flow_ids}")
    required_count = yaml_int_value(text, "required_chain_flow_count", errors, path.name)
    if required_count is not None and required_count != len(set(flow_ids)):
        errors.append(f"{path.name} required_chain_flow_count 与 required flow 数不一致：{required_count} != {len(set(flow_ids))}")
    return set(flow_ids), errors


def validate_chain_flow_candidate_audit_file(path: Path, required_flow_ids: set[str]) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"缺少长链路候选审计：{path}"]
    try:
        text = read_text(path)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return [str(exc)]

    require_yaml_top_level_keys(text, CHAIN_FLOW_AUDIT_REQUIRED_KEYS, errors, path.name)
    stage = first_yaml_scalar(text, "stage")
    if stage != "chain_flow_candidate_audit":
        errors.append(f"{path.name} stage 不匹配：{stage} != chain_flow_candidate_audit")
    status = first_yaml_scalar(text, "status")
    if status != "passed":
        errors.append(f"{path.name} status 不是 passed：{status}")
    next_stage_allowed = first_yaml_scalar(text, "next_stage_allowed")
    if next_stage_allowed is None or not is_yaml_true(next_stage_allowed):
        errors.append(f"{path.name} next_stage_allowed 不是 true：{next_stage_allowed}")
    require_yaml_empty_list(text, "unclassified_candidate_flows", errors, path.name)
    require_yaml_empty_list(text, "blocking_issues", errors, path.name)

    included_ids: set[str] = set()
    observed_counts = {classification: 0 for classification in CHAIN_FLOW_ALLOWED_CANDIDATE_CLASSIFICATIONS}
    observed_unclassified = 0
    for block in yaml_sequence_raw_blocks(text, "candidates", "candidate_id"):
        candidate_id = first_yaml_scalar(block, "candidate_id") or "UNKNOWN"
        classification = first_yaml_scalar(block, "classification")
        if classification not in CHAIN_FLOW_ALLOWED_CANDIDATE_CLASSIFICATIONS:
            errors.append(f"{path.name} {candidate_id} classification 非法或未分类：{classification}")
            observed_unclassified += 1
            continue
        observed_counts[classification] += 1
        downstream_target = first_yaml_scalar(block, "downstream_target")
        if classification != "included" and yaml_value_is_missing(downstream_target):
            errors.append(f"{path.name} {candidate_id} 非 included 候选缺少 downstream_target")
        if classification == "included":
            flow_id = first_yaml_scalar(block, "flow_id")
            if yaml_value_is_missing(flow_id):
                errors.append(f"{path.name} {candidate_id} included 候选缺少 flow_id")
            else:
                included_ids.add(flow_id or "")
    summary_section = yaml_section(text, "candidate_summary")
    for classification in sorted(CHAIN_FLOW_ALLOWED_CANDIDATE_CLASSIFICATIONS):
        values = yaml_scalar_values(summary_section, classification)
        if not values:
            if observed_counts[classification] > 0:
                errors.append(f"{path.name} candidate_summary 缺少分类计数：{classification}")
            continue
        try:
            actual_count = int(values[0])
        except ValueError:
            errors.append(f"{path.name} candidate_summary.{classification} 不是整数：{values[0]}")
            continue
        if actual_count != observed_counts[classification]:
            errors.append(
                f"{path.name} candidate_summary.{classification} 与候选明细不一致："
                f"{actual_count} != {observed_counts[classification]}"
            )
    unclassified_values = yaml_scalar_values(summary_section, "unclassified")
    if unclassified_values:
        try:
            actual_unclassified = int(unclassified_values[0])
        except ValueError:
            errors.append(f"{path.name} candidate_summary.unclassified 不是整数：{unclassified_values[0]}")
        else:
            if actual_unclassified != observed_unclassified:
                errors.append(
                    f"{path.name} candidate_summary.unclassified 与候选明细不一致："
                    f"{actual_unclassified} != {observed_unclassified}"
                )
    if included_ids != required_flow_ids:
        errors.append(f"{path.name} included flow 与必测分母不一致：audit={sorted(included_ids)}，required={sorted(required_flow_ids)}")
    return errors


def coverage_type_for_total_key(total_key: str) -> str | None:
    mapping = {
        "object_total": "object",
        "test_point_total": "test_point",
        "rule_total": "rule",
        "main_flow_total": "main_flow",
        "contract_rule_total": "contract_rule",
        "status_code_total": "status_code",
        "p0_p1_total": "p0_p1",
        "design_case_total": "design_case",
        "executable_case_total": "executable_case",
        "coverage_rule_total": "coverage_rule",
        "source_interface_total": "source_interface",
        "source_contract_rule_total": "source_contract_rule",
        "source_business_rule_total": "source_business_rule",
        "source_error_code_total": "source_error_code",
        "source_db_side_effect_total": "source_db_side_effect",
        "source_scenario_total": "source_scenario",
        "chain_scenario_total": "chain_scenario",
        "chain_function_total": "chain_function",
        "chain_process_total": "chain_process",
    }
    return mapping.get(total_key)


def extract_mapping_blocks(text: str) -> list[dict[str, str]]:
    return extract_yaml_sequence_blocks(text, "upstream_downstream_mappings")


def validate_coverage_item_alignment(
    text: str,
    errors: list[str],
    label: str,
    count_pairs: tuple[tuple[str, str], ...],
) -> None:
    items = extract_coverage_item_blocks(text)
    mappings = extract_mapping_blocks(text)
    mapped_upstream_ids = {
        normalize_yaml_value(mapping.get("upstream_id"))
        for mapping in mappings
        if normalize_yaml_value(mapping.get("mapping_status")) == "mapped"
    }
    for total_key, _ in count_pairs:
        expected_values = yaml_int_values(text, total_key)
        if not expected_values:
            continue
        expected_total = expected_values[0]
        coverage_type = coverage_type_for_total_key(total_key)
        if not coverage_type:
            continue
        typed_items = [item for item in items if normalize_yaml_value(item.get("coverage_type")) == coverage_type]
        coverage_ids = [normalize_yaml_value(item.get("coverage_id")) for item in typed_items]
        coverage_ids = [coverage_id for coverage_id in coverage_ids if coverage_id]
        if len(coverage_ids) != len(set(coverage_ids)):
            errors.append(f"{label} coverage_items 存在重复 coverage_id：{coverage_type}")
        if len(set(coverage_ids)) != expected_total:
            errors.append(
                f"{label} {coverage_type} 覆盖明细数量与 {total_key} 不一致："
                f"{len(set(coverage_ids))} != {expected_total}"
            )
        for item in typed_items:
            coverage_id = normalize_yaml_value(item.get("coverage_id")) or "UNKNOWN"
            if yaml_value_is_missing(item.get("coverage_id")):
                errors.append(f"{label} {coverage_type} 覆盖项缺少 coverage_id")
            if normalize_yaml_value(item.get("status")) != "covered":
                errors.append(f"{label} 覆盖项 {coverage_id} status 不是 covered：{item.get('status')}")
            if yaml_value_is_missing(item.get("evidence_refs"), list_value=True):
                errors.append(f"{label} 覆盖项 {coverage_id} 缺少 evidence_refs")
        missing_mapping_ids = sorted(set(coverage_ids) - mapped_upstream_ids)
        if missing_mapping_ids:
            errors.append(f"{label} upstream_downstream_mappings 缺少覆盖项映射：{missing_mapping_ids}")


def validate_coverage_release_details(
    text: str,
    errors: list[str],
    label: str,
    expected_stage: str,
    count_pairs: tuple[tuple[str, str], ...],
) -> None:
    top_level_keys = yaml_top_level_keys(text)
    legacy_pre_doc = (
        expected_stage == "pre_doc_analysis"
        and "coverage_objects" in top_level_keys
        and "coverage_items" not in top_level_keys
    )
    summary_block = yaml_key_block(text, "coverage_summary")
    coverage_rate = parse_yaml_rate(scalar_from_block(summary_block, "coverage_rate"))
    if coverage_rate is None:
        errors.append(f"{label} coverage_summary.coverage_rate 缺失或不可解析")
    elif coverage_rate != 100:
        errors.append(f"{label} coverage_summary.coverage_rate 不是 100：{coverage_rate:g}")

    total_sum = 0
    for total_key, _ in count_pairs:
        values = yaml_int_values(text, total_key)
        if values:
            total_sum += values[0]

    coverage_items_values = yaml_scalar_values(text, "coverage_items")
    coverage_items_empty = bool(coverage_items_values and yaml_scalar_is_empty_list(coverage_items_values[0]))
    coverage_statuses = yaml_scalar_values(yaml_section(text, "coverage_items"), "status")
    if total_sum > 0 and not legacy_pre_doc and (coverage_items_empty or not coverage_statuses):
        errors.append(f"{label} coverage_items 为空，不能证明非零分母的覆盖明细")
    for status in coverage_statuses:
        if status.strip().strip("\"'") != "covered":
            errors.append(f"{label} coverage_items.status 不是 covered：{status}")

    if not legacy_pre_doc:
        require_yaml_empty_list(text, "missing_items", errors, label)

    mapping_values = yaml_scalar_values(text, "upstream_downstream_mappings")
    mapping_empty = bool(mapping_values and yaml_scalar_is_empty_list(mapping_values[0]))
    mapping_statuses = yaml_scalar_values(yaml_section(text, "upstream_downstream_mappings"), "mapping_status")
    if total_sum > 0 and not legacy_pre_doc and (mapping_empty or not mapping_statuses):
        errors.append(f"{label} upstream_downstream_mappings 为空，不能证明非零分母的上下游映射")
    for status in mapping_statuses:
        if status.strip().strip("\"'") != "mapped":
            errors.append(f"{label} upstream_downstream_mappings.mapping_status 不是 mapped：{status}")
    if not legacy_pre_doc:
        validate_coverage_item_alignment(text, errors, label, count_pairs)


def validate_required_chain_independent_coverage(
    text: str,
    errors: list[str],
    label: str,
    required_flow_ids: set[str],
    generated_count_key: str | None = None,
) -> None:
    if not required_flow_ids:
        return

    denominator_values = [
        value.strip().strip("\"'")
        for key in ("denominator_scope", "coverage_denominator", "coverage_scope")
        for value in yaml_scalar_values(text, key)
    ]
    if "long_chain_only" not in denominator_values:
        errors.append(f"{label} 必须声明长链路覆盖率独立计算：denominator_scope/coverage_denominator=long_chain_only")

    parsed_totals: dict[str, int] = {}
    for total_key, covered_key in CHAIN_COVERAGE_PAIRS:
        total = yaml_int_value(text, total_key, errors, label)
        covered = yaml_int_value(text, covered_key, errors, label)
        if total is None or covered is None:
            continue
        parsed_totals[total_key] = total
        if total <= 0:
            errors.append(f"{label} {total_key} 必须大于 0，不能把长链路覆盖率混入单接口覆盖率")
        if total != covered:
            errors.append(f"{label} 长链路覆盖计数不是 100%：{covered_key}/{total_key} = {covered}/{total}")
    scenario_total = parsed_totals.get("chain_scenario_total")
    if scenario_total is not None and scenario_total < len(required_flow_ids):
        errors.append(
            f"{label} chain_scenario_total 小于上游必需 flow 数："
            f"{scenario_total} < {len(required_flow_ids)}"
        )
    for key in CHAIN_COVERAGE_MISSING_LISTS:
        require_yaml_empty_list(text, key, errors, label)
    require_yaml_empty_list(text, "missing_required_flow_ids", errors, label)
    required_count = yaml_int_value(text, "required_chain_flow_count", errors, label)
    if required_count is not None and required_count != len(required_flow_ids):
        errors.append(f"{label} required_chain_flow_count 与必测 flow 数不一致：{required_count} != {len(required_flow_ids)}")
    if generated_count_key:
        generated_count = yaml_int_value(text, generated_count_key, errors, label)
        if generated_count is not None and generated_count != len(required_flow_ids):
            errors.append(f"{label} {generated_count_key} 与必测 flow 数不一致：{generated_count} != {len(required_flow_ids)}")
    validate_chain_coverage_items(text, errors, label, required_flow_ids)


def extract_coverage_item_blocks(text: str) -> list[dict[str, str]]:
    return extract_yaml_sequence_blocks(text, "coverage_items")


def validate_chain_coverage_items(
    text: str,
    errors: list[str],
    label: str,
    required_flow_ids: set[str],
) -> None:
    if not required_flow_ids:
        return
    items = extract_coverage_item_blocks(text)
    chain_items = [item for item in items if item.get("coverage_type") in {"chain_scenario", "chain_function", "chain_process"}]
    if not chain_items:
        errors.append(f"{label} coverage_items 缺少长链路覆盖明细：chain_scenario/chain_function/chain_process")
        return
    for item in chain_items:
        coverage_id = item.get("coverage_id", "UNKNOWN")
        if item.get("status") != "covered":
            errors.append(f"{label} 长链路覆盖项 {coverage_id} status 不是 covered：{item.get('status')}")
        if not item.get("evidence_refs"):
            errors.append(f"{label} 长链路覆盖项 {coverage_id} 缺少 evidence_refs")
    scenario_items = [item for item in chain_items if item.get("coverage_type") == "chain_scenario"]
    scenario_ids = {item.get("flow_id") or item.get("coverage_id") for item in scenario_items}
    missing_flow_ids = sorted(flow_id for flow_id in required_flow_ids if flow_id not in scenario_ids)
    if missing_flow_ids:
        errors.append(f"{label} chain_scenario 覆盖明细缺少上游必需 flow_id：{missing_flow_ids}")
    for coverage_type, total_key in (
        ("chain_scenario", "chain_scenario_total"),
        ("chain_function", "chain_function_total"),
        ("chain_process", "chain_process_total"),
    ):
        expected_values = yaml_int_values(text, total_key)
        if not expected_values:
            continue
        actual_ids = {
            item.get("coverage_id", "")
            for item in chain_items
            if item.get("coverage_type") == coverage_type and item.get("coverage_id")
        }
        if len(actual_ids) != expected_values[0]:
            errors.append(
                f"{label} {coverage_type} 覆盖明细数量与 {total_key} 不一致："
                f"{len(actual_ids)} != {expected_values[0]}"
            )


def read_sidecar(path: Path, errors: list[str], label: str) -> str:
    if not path.is_file():
        errors.append(f"{label} 缺少结构化 sidecar：{path.name}")
        return ""
    try:
        return read_text(path)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        errors.append(str(exc))
        return ""


def validate_stage_sidecars(
    base: Path,
    errors: list[str],
    label: str,
    expected_stage: str,
    count_pairs: tuple[tuple[str, str], ...],
    missing_lists: tuple[str, ...],
) -> None:
    stage_status_text = read_sidecar(base / "stage_status.yaml", errors, label)
    coverage_matrix_text = read_sidecar(base / "coverage_matrix.yaml", errors, label)

    if stage_status_text:
        require_stage_status_schema_keys(stage_status_text, errors, f"{label}/stage_status.yaml", expected_stage)
        schema_version = yaml_int_value(stage_status_text, "schema_version", errors, f"{label}/stage_status.yaml")
        if schema_version is not None and schema_version != 1:
            errors.append(f"{label}/stage_status.yaml schema_version 不是 1：{schema_version}")
        stage = first_yaml_scalar(stage_status_text, "stage")
        if stage != expected_stage:
            errors.append(f"{label}/stage_status.yaml stage 不匹配：{stage} != {expected_stage}")
        status = first_yaml_scalar(stage_status_text, "status")
        if status not in SIDECAR_STATUS_VALUES:
            errors.append(f"{label}/stage_status.yaml status 非法或缺失：{status}")
        elif status != "passed":
            errors.append(f"{label}/stage_status.yaml status 不是 passed：{status}")
        next_stage_allowed = first_yaml_scalar(stage_status_text, "next_stage_allowed")
        if next_stage_allowed is None or not is_yaml_true(next_stage_allowed):
            errors.append(f"{label}/stage_status.yaml next_stage_allowed 不是 true：{next_stage_allowed}")
        require_yaml_empty_list(stage_status_text, "blocking_issues", errors, f"{label}/stage_status.yaml")
        if "gate_checks" in yaml_top_level_keys(stage_status_text):
            validate_status_section_passed(stage_status_text, "gate_checks", errors, f"{label}/stage_status.yaml")

    if coverage_matrix_text:
        require_coverage_matrix_schema_keys(coverage_matrix_text, errors, f"{label}/coverage_matrix.yaml", expected_stage)
        schema_version = yaml_int_value(coverage_matrix_text, "schema_version", errors, f"{label}/coverage_matrix.yaml")
        if schema_version is not None and schema_version != 1:
            errors.append(f"{label}/coverage_matrix.yaml schema_version 不是 1：{schema_version}")
        stage = first_yaml_scalar(coverage_matrix_text, "stage")
        if stage != expected_stage:
            errors.append(f"{label}/coverage_matrix.yaml stage 不匹配：{stage} != {expected_stage}")
        for total_key, covered_key in count_pairs:
            total = yaml_int_value(coverage_matrix_text, total_key, errors, f"{label}/coverage_matrix.yaml")
            covered = yaml_int_value(coverage_matrix_text, covered_key, errors, f"{label}/coverage_matrix.yaml")
            if total is None or covered is None:
                continue
            if total <= 0:
                errors.append(f"{label}/coverage_matrix.yaml {total_key} 必须大于 0，不能用 0/0 声明 100% 覆盖")
            if total != covered:
                errors.append(f"{label}/coverage_matrix.yaml 覆盖计数不是 100%：{covered_key}/{total_key} = {covered}/{total}")
        for key in missing_lists:
            require_yaml_empty_list(coverage_matrix_text, key, errors, f"{label}/coverage_matrix.yaml")
        validate_coverage_release_details(
            coverage_matrix_text,
            errors,
            f"{label}/coverage_matrix.yaml",
            expected_stage,
            count_pairs,
        )


def resolve_entry(output_root: Path, entry: str) -> Path:
    doc_entry = output_root / "01-pre-doc-analysis"
    source_entry = output_root / "02-source-api-facts" / "docs" / "source-facts"
    if entry == "doc":
        return doc_entry
    if entry == "source":
        return source_entry
    if doc_entry.exists():
        return doc_entry
    return source_entry


def validate_entry(entry_dir: Path) -> list[str]:
    errors: list[str] = []
    if not entry_dir.is_dir():
        return [f"入口目录不存在或不是目录：{entry_dir}"]
    for filename in ENTRY_DOCS.values():
        path = entry_dir / filename
        if not path.is_file():
            errors.append(f"入口缺少文件：{path}")
            continue
        try:
            read_text(path)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            errors.append(str(exc))
    return errors


def collect_json_status_values(value: object) -> list[str]:
    values: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in {"status", "result", "quality_status", "conclusion"}:
                values.append(str(item).strip())
            values.extend(collect_json_status_values(item))
    elif isinstance(value, list):
        for item in value:
            values.extend(collect_json_status_values(item))
    return values


def validate_source_quality_report(entry_dir: Path, errors: list[str]) -> None:
    path = entry_dir / "source-api-quality-report.json"
    if not path.is_file():
        errors.append(f"源码入口缺少 source-api-quality-report.json：{path}")
        return
    try:
        quality_data = json.loads(read_text(path))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"源码入口 source-api-quality-report.json 无法解析：{exc}")
        return
    status_values = collect_json_status_values(quality_data)
    if not status_values:
        errors.append("源码入口 source-api-quality-report.json 缺少 status/result 质检结论")
        return
    for value in status_values:
        if value.lower() in SOURCE_FAILED_STATUS_VALUES:
            errors.append(f"源码入口质检结论未通过：{value}")


def validate_source_artifact_manifest(entry_dir: Path, errors: list[str]) -> None:
    path = entry_dir / "source_api_fact_artifacts.yaml"
    if not path.is_file():
        errors.append(f"源码入口缺少 source_api_fact_artifacts.yaml：{path}")
        return
    try:
        text = read_text(path)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        errors.append(str(exc))
        return
    for artifact_name in SOURCE_ARTIFACT_REQUIRED_NAMES:
        if artifact_name not in text:
            errors.append(f"源码入口 source_api_fact_artifacts.yaml 缺少必需 artifact：{artifact_name}")


def validate_source_entry_release(entry_dir: Path, errors: list[str]) -> None:
    for filename in ("source-api-facts.json",):
        path = entry_dir / filename
        if not path.is_file():
            errors.append(f"源码入口缺少 {filename}：{path}")
            continue
        try:
            read_text(path)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            errors.append(str(exc))
    validate_source_quality_report(entry_dir, errors)
    validate_source_artifact_manifest(entry_dir, errors)
    validate_stage_sidecars(
        entry_dir,
        errors,
        "源码入口",
        "source_api_facts",
        SOURCE_COVERAGE_PAIRS,
        SOURCE_MISSING_LISTS,
    )


def normalize_heading(heading: str) -> str:
    return re.sub(r"^[\d.、\s]+", "", heading.strip())


def collect_sections(text: str, title_keywords: tuple[str, ...]) -> str:
    matches = list(SECTION_HEADING_RE.finditer(text))
    parts: list[str] = []
    for index, match in enumerate(matches):
        title = normalize_heading(match.group(1))
        if not any(keyword in title for keyword in title_keywords):
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        parts.append(text[start:end].strip())
    return "\n".join(parts)


def is_none_marker_line(line: str) -> bool:
    normalized = line.strip().strip("|").strip()
    normalized = re.sub(r"^[-*]\s*", "", normalized).strip()
    normalized = normalized.strip("。；;，,：:")
    return normalized in NONE_MARKERS


def has_meaningful_blocker(section_text: str) -> bool:
    for raw_line in section_text.splitlines():
        line = raw_line.strip().strip("|").strip()
        if not line or set(line) <= {"-", ":", "|", " "}:
            continue
        if any(header in line for header in ("编号", "问题", "影响", "修正建议")):
            continue
        if is_none_marker_line(line):
            continue
        return True
    return False


def split_markdown_row(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|"):
        return []
    cells = [cell.strip() for cell in stripped.strip("|").split("|")]
    if cells and all(set(cell) <= {"-", ":", " "} for cell in cells):
        return []
    return cells


def has_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def invalid_coverage_point_value(value: str | None) -> bool:
    if value is None:
        return True
    normalized = value.strip().strip("|").strip()
    normalized = re.sub(r"<br\s*/?>", "", normalized, flags=re.IGNORECASE).strip()
    return normalized in COVERAGE_POINT_PLACEHOLDERS


def extract_coverage_point_records(text: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    header: list[str] | None = None
    header_indexes: dict[str, int] = {}
    for raw_line in text.splitlines():
        cells = split_markdown_row(raw_line)
        if not cells:
            continue
        if all(field in cells for field in COVERAGE_POINT_HEADERS):
            header = cells
            header_indexes = {field: cells.index(field) for field in COVERAGE_POINT_HEADERS}
            continue
        if header is None or len(cells) < len(header):
            continue
        records.append({field: cells[header_indexes[field]].strip() for field in COVERAGE_POINT_HEADERS})
    return records


def coverage_point_summary_text(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        cells = split_markdown_row(raw_line)
        if cells and all(field in cells for field in COVERAGE_POINT_HEADERS):
            break
        lines.append(raw_line)
    return "\n".join(lines).strip()


def coverage_point_interface_count(link: str) -> int:
    parts = [part.strip() for part in re.split(r"\s*(?:—>|->|→)\s*", link) if part.strip()]
    return len(parts) if parts else 0


def coverage_point_step_count(steps: str) -> int:
    numbered_steps = re.findall(r"(?:^|[；;。>\n])\s*\d+\s*[.、]", steps)
    if numbered_steps:
        return len(numbered_steps)
    split_steps = [part.strip() for part in re.split(r"(?:<br\s*/?>|；|;)", steps, flags=re.IGNORECASE) if part.strip()]
    return len(split_steps)


def long_chain_record_ids(records: list[dict[str, str]]) -> list[str]:
    ids: list[str] = []
    for record in records:
        if is_long_chain_coverage_point(record):
            row_id = record.get("ID", "").strip()
            if row_id:
                ids.append(row_id)
    return ids


def is_long_chain_coverage_point(record: dict[str, str]) -> bool:
    interface_count = coverage_point_interface_count(record.get("接口链路", ""))
    step_count = coverage_point_step_count(record.get("操作步骤", ""))
    return interface_count >= LONG_CHAIN_INTERFACE_THRESHOLD or step_count >= LONG_CHAIN_STEP_THRESHOLD


def is_single_interface_coverage_point(record: dict[str, str]) -> bool:
    return coverage_point_interface_count(record.get("接口链路", "")) == 1 and not is_long_chain_coverage_point(record)


def summary_has_coverage_line(summary: str, label: str, has_records: bool) -> bool:
    for line in summary.splitlines():
        if label not in line:
            continue
        if PERCENT_PATTERN.search(line):
            return True
        if not has_records and any(marker in line for marker in ("不涉及", "无", "0 个", "0个")):
            return True
    return False


def validate_coverage_point_order(records: list[dict[str, str]], errors: list[str]) -> None:
    seen_single_interface = False
    for record in records:
        row_id = record.get("ID", "UNKNOWN")
        if is_single_interface_coverage_point(record):
            seen_single_interface = True
            continue
        if is_long_chain_coverage_point(record) and seen_single_interface:
            errors.append(f"{COVERAGE_POINT_REPORT} 明细表必须先列长链路用例，再列单接口用例：{row_id}")


def validate_coverage_point_summary(text: str, records: list[dict[str, str]], errors: list[str]) -> None:
    summary = coverage_point_summary_text(text)
    if not summary:
        errors.append(f"{COVERAGE_POINT_REPORT} 明细表前缺少覆盖点摘要")
        return
    if COVERAGE_POINT_SUMMARY_TITLE not in summary:
        errors.append(f"{COVERAGE_POINT_REPORT} 开头缺少 {COVERAGE_POINT_SUMMARY_TITLE} 章节")
    if "覆盖率" not in summary:
        errors.append(f"{COVERAGE_POINT_REPORT} 覆盖点摘要缺少覆盖率")
    if not PERCENT_PATTERN.search(summary):
        errors.append(f"{COVERAGE_POINT_REPORT} 覆盖点摘要缺少覆盖率百分比")
    if not any(marker in summary for marker in ("计算口径", "计算公式", "计算方式")):
        errors.append(f"{COVERAGE_POINT_REPORT} 覆盖点摘要缺少覆盖率计算口径")
    if not ("× 100%" in summary or "* 100%" in summary or "x 100%" in summary.lower()):
        errors.append(f"{COVERAGE_POINT_REPORT} 覆盖点摘要缺少覆盖率乘以 100% 的计算说明")
    long_ids = long_chain_record_ids(records)
    single_records = [record for record in records if is_single_interface_coverage_point(record)]
    if not summary_has_coverage_line(summary, "长链路覆盖率", bool(long_ids)):
        errors.append(f"{COVERAGE_POINT_REPORT} 覆盖点摘要缺少独立长链路覆盖率或不涉及说明")
    if not summary_has_coverage_line(summary, "单接口覆盖率", bool(single_records)):
        errors.append(f"{COVERAGE_POINT_REPORT} 覆盖点摘要缺少独立单接口覆盖率或不涉及说明")
    if "长链路" in summary and "单接口" in summary and not any(marker in summary for marker in ("分别", "分项", "不得混合", "单独计算")):
        errors.append(f"{COVERAGE_POINT_REPORT} 覆盖点摘要需要说明长链路和单接口覆盖率分开计算")
    if "长链路" not in summary:
        errors.append(f"{COVERAGE_POINT_REPORT} 覆盖点摘要缺少长链路重点关注说明")

    if long_ids:
        for row_id in long_ids:
            if row_id not in summary:
                errors.append(f"{COVERAGE_POINT_REPORT} 覆盖点摘要缺少长链路重点关注 ID：{row_id}")
    elif not any(marker in summary for marker in ("长链路重点关注：无", "长链路重点关注: 无", "长链路重点关注：0", "长链路重点关注: 0")):
        errors.append(f"{COVERAGE_POINT_REPORT} 无长链路测试点时需要在摘要中明确写明无或 0 个")


def validate_coverage_point_report_file(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"缺少人工测试覆盖点报告：{path}"]
    try:
        text = read_text(path)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return [str(exc)]

    records = extract_coverage_point_records(text)
    if not records:
        errors.append(f"{COVERAGE_POINT_REPORT} 缺少包含十一个必需字段的 Markdown 表格")
        return errors
    validate_coverage_point_summary(text, records, errors)
    validate_coverage_point_order(records, errors)

    for index, record in enumerate(records, start=1):
        row_id = record.get("ID") or f"第 {index} 行"
        for field in COVERAGE_POINT_HEADERS:
            if invalid_coverage_point_value(record.get(field)):
                errors.append(f"{COVERAGE_POINT_REPORT} {row_id} 字段为空或为占位内容：{field}")
        for field in COVERAGE_POINT_CHINESE_FIELDS:
            value = record.get(field, "")
            if not invalid_coverage_point_value(value) and not has_chinese(value):
                errors.append(f"{COVERAGE_POINT_REPORT} {row_id} 字段必须使用中文描述：{field}")
        priority = record.get("优先级", "").strip().lower()
        if priority not in COVERAGE_POINT_PRIORITY_VALUES:
            errors.append(f"{COVERAGE_POINT_REPORT} {row_id} 优先级必须为 p0/p1/p2：{record.get('优先级')}")
        link = record.get("接口链路", "")
        if "->" in link or "→" in link:
            errors.append(f"{COVERAGE_POINT_REPORT} {row_id} 接口链路请使用 接口1—>接口2 格式")
        test_point = record.get("测试点", "")
        if re.search(r"\b(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b\s*/", test_point, re.IGNORECASE):
            errors.append(f"{COVERAGE_POINT_REPORT} {row_id} 测试点不能只写 method/path")
        if looks_like_path_bucket_long_chain(
            record.get("业务域", ""),
            record.get("业务场景", ""),
            test_point,
            record.get("用例类型", ""),
        ):
            errors.append(f"{COVERAGE_POINT_REPORT} {row_id} 疑似接口标签或路径前缀用例，必须改为真实业务场景描述")
        source = record.get("来源")
        if invalid_coverage_point_value(source):
            errors.append(f"{COVERAGE_POINT_REPORT} {row_id} 来源必须引用需求、测试点、覆盖对象或设计级用例证据")
    return errors


def extract_case_identity_groups(case_yaml_text: str) -> list[set[str]]:
    groups: list[set[str]] = []
    section = yaml_section(case_yaml_text, "cases")
    current: set[str] | None = None
    for raw_line in section.splitlines():
        stripped = raw_line.strip()
        inline_match = re.match(r"^-\s*\{(.+)\}\s*$", stripped)
        if inline_match:
            if current is not None:
                groups.append(current)
                current = None
            mapping = parse_inline_mapping(inline_match.group(1))
            identity = {mapping.get("case_id", ""), mapping.get("design_case_id", "")}
            groups.append({item for item in identity if item and not invalid_coverage_point_value(item)})
            continue
        item_match = re.match(r"^-\s+([A-Za-z0-9_]+)\s*:\s*(.*?)\s*$", stripped)
        if item_match:
            if current is not None:
                groups.append(current)
            current = set()
            key, value = item_match.group(1), item_match.group(2).strip().strip("\"'")
            if key in {"case_id", "design_case_id"} and not invalid_coverage_point_value(value):
                current.add(value)
            continue
        if current is None:
            continue
        scalar_match = re.match(r"^([A-Za-z0-9_]+)\s*:\s*(.*?)\s*$", stripped)
        if scalar_match:
            key, value = scalar_match.group(1), scalar_match.group(2).strip().strip("\"'")
            if key in {"case_id", "design_case_id"} and not invalid_coverage_point_value(value):
                current.add(value)
    if current is not None:
        groups.append(current)
    return [group for group in groups if group]


def validate_coverage_point_case_mapping(case_yaml_text: str, report_path: Path) -> list[str]:
    errors: list[str] = []
    try:
        report_text = read_text(report_path)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return [str(exc)]
    groups = extract_case_identity_groups(case_yaml_text)
    mapped_count = 0
    for index, group in enumerate(groups, start=1):
        if not any(identity in report_text for identity in group):
            errors.append(
                f"{COVERAGE_POINT_REPORT} 缺少 case_list.yaml 第 {index} 条设计级用例的来源映射："
                f"{sorted(group)}"
            )
        else:
            mapped_count += 1
    summary = coverage_point_summary_text(report_text)
    if groups and summary:
        expected_rate = mapped_count / len(groups) * 100
        summary_rates = [float(value) for value in PERCENT_PATTERN.findall(summary)]
        if not summary_rates:
            errors.append(f"{COVERAGE_POINT_REPORT} 覆盖点摘要缺少可解析的覆盖率百分比")
        elif not any(abs(rate - expected_rate) < 0.01 for rate in summary_rates):
            errors.append(
                f"{COVERAGE_POINT_REPORT} 覆盖点摘要覆盖率与映射结果不一致："
                f"摘要={summary_rates}，实际={expected_rate:g}%"
            )
    return errors


def business_scenario_descriptions(text: str) -> set[str]:
    return {
        value.strip()
        for value in yaml_scalar_values(text, "business_description")
        if value.strip() and not invalid_coverage_point_value(value)
    }


def business_scenario_item_blocks(text: str) -> list[str]:
    starts = list(re.finditer(r"(?m)^\s*-\s+scenario_id\s*:", text))
    blocks: list[str] = []
    for index, start in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        blocks.append(text[start.start():end])
    return blocks


def business_scenario_items_from_yaml(text: str) -> list[dict[str, Any]]:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return []
    if not isinstance(data, dict):
        return []
    items = data.get("scenario_items")
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, dict):
                result.extend(text_list(item.get("interface") or item.get("source_ref")))
            else:
                result.extend(text_list(item))
        return result
    text = str(value).strip().strip("\"'")
    if not text or invalid_coverage_point_value(text) or yaml_scalar_is_empty_list(text):
        return []
    return [text]


def scenario_item_interfaces(item: dict[str, Any]) -> list[str]:
    interfaces = text_list(item.get("related_interfaces"))
    interfaces.extend(text_list(item.get("ordered_steps")))
    return interfaces


def resource_key_from_interface(interface: str) -> str:
    match = HTTP_INTERFACE_RE.search(interface)
    if not match:
        return ""
    path = re.sub(r"\{[^}]+\}", "", match.group(1))
    parts = [part for part in re.sub(r"/+", "/", path).strip("/").split("/") if part]
    semantic_parts: list[str] = []
    for part in parts:
        lowered = part.lower()
        if lowered in GENERIC_ROUTE_SEGMENTS or re.fullmatch(r"v\d+", lowered):
            continue
        if lowered in ACTION_ROUTE_SEGMENTS:
            continue
        semantic_parts.append(lowered)
    return "/".join(semantic_parts[:2]) if semantic_parts else ""


def item_has_mutation(item: dict[str, Any]) -> bool:
    text = " ".join(
        scenario_item_interfaces(item)
        + text_list(item.get("business_chain"))
        + text_list(item.get("scenario_name"))
    )
    return bool(MUTATING_INTERFACE_RE.search(text)) or bool(
        re.search(r"创建|提交|更新|删除|发布|发送|认证|上传|支付|充值|提现|绑定|解除|申请|审核", text)
    )


def item_has_read_or_verify(item: dict[str, Any]) -> bool:
    text = " ".join(
        scenario_item_interfaces(item)
        + text_list(item.get("business_chain"))
        + text_list(item.get("scenario_name"))
    )
    return bool(READ_VERIFY_RE.search(text))


def splittable_single_interface_clusters(items: list[dict[str, Any]]) -> list[str]:
    if any(
        is_yaml_true(str(item.get("flow_generation_required", "")))
        or str(item.get("chain_type", "")).strip().strip("\"'") == "e2e_flow_candidate"
        for item in items
    ):
        return []
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        if str(item.get("chain_type", "")).strip().strip("\"'") != "single_interface":
            continue
        keys = {resource_key_from_interface(interface) for interface in scenario_item_interfaces(item)}
        for key in keys:
            if key:
                groups.setdefault(key, []).append(item)
    splittable: list[str] = []
    for key, group in sorted(groups.items()):
        if len(group) < LONG_CHAIN_INTERFACE_THRESHOLD:
            continue
        if any(item_has_mutation(item) for item in group) and any(item_has_read_or_verify(item) for item in group):
            splittable.append(key)
    return splittable


def block_first_scalar(block: str, key: str) -> str | None:
    values = yaml_scalar_values(block, key)
    return values[0] if values else None


def parse_inline_yaml_list(value: str) -> list[str]:
    normalized = value.strip().strip("\"'")
    if not (normalized.startswith("[") and normalized.endswith("]")):
        return []
    inner = normalized[1:-1].strip()
    if not inner:
        return []
    return [
        item.strip().strip("\"'")
        for item in re.split(r"\s*,\s*", inner)
        if item.strip().strip("\"'")
    ]


def block_list_values(block: str, key: str) -> list[str]:
    values: list[str] = []
    lines = block.splitlines()
    for index, line in enumerate(lines):
        match = re.match(rf"^(\s*)(?:-\s*)?{re.escape(key)}\s*:\s*(.*?)\s*$", line)
        if not match:
            continue
        indent = len(match.group(1))
        inline_value = match.group(2).strip()
        inline_items = parse_inline_yaml_list(inline_value)
        if inline_items:
            values.extend(inline_items)
            continue
        if inline_value and not yaml_scalar_is_empty_list(inline_value):
            values.append(inline_value.strip().strip("\"'"))
            continue
        for next_line in lines[index + 1:]:
            next_indent = len(next_line) - len(next_line.lstrip(" "))
            if next_line.strip() and next_indent <= indent:
                break
            item_match = re.match(r"^\s*-\s*(.*?)\s*$", next_line)
            if item_match and item_match.group(1).strip():
                values.append(item_match.group(1).strip().strip("\"'"))
    return [value for value in values if not invalid_coverage_point_value(value)]


def scenario_requires_chain(block: str) -> bool:
    chain_type = block_first_scalar(block, "chain_type")
    flow_required = is_yaml_true(block_first_scalar(block, "flow_generation_required") or "")
    return flow_required or chain_type == "e2e_flow_candidate"


def validate_required_chain_scenarios(text: str, errors: list[str], label: str) -> None:
    flow_ids: list[str] = []
    for block in business_scenario_item_blocks(text):
        scenario_id = block_first_scalar(block, "scenario_id") or "UNKNOWN"
        chain_type = block_first_scalar(block, "chain_type")
        flow_required = is_yaml_true(block_first_scalar(block, "flow_generation_required") or "")
        if chain_type == "e2e_flow_candidate" and not flow_required:
            errors.append(f"{label} {scenario_id} 是 e2e_flow_candidate 时 flow_generation_required 必须为 true")
        if not scenario_requires_chain(block):
            continue
        flow_id = block_first_scalar(block, "flow_id")
        if not flow_id or invalid_coverage_point_value(flow_id):
            errors.append(f"{label} {scenario_id} 必须生成链路脚本但缺少有效 flow_id")
        else:
            flow_ids.append(flow_id)
        step_counts = yaml_int_values(block, "ordered_step_count")
        if not step_counts:
            errors.append(f"{label} {scenario_id} 必须生成链路脚本但缺少 ordered_step_count")
        elif step_counts[0] < 2:
            errors.append(f"{label} {scenario_id} 必须生成链路脚本但 ordered_step_count 小于 2：{step_counts[0]}")
        if "ordered_steps" not in block:
            errors.append(f"{label} {scenario_id} 必须生成链路脚本但缺少 ordered_steps")
        for marker in ("step_order", "interface", "source_ref"):
            if marker not in block:
                errors.append(f"{label} {scenario_id} ordered_steps 缺少字段：{marker}")
    if len(flow_ids) != len(set(flow_ids)):
        errors.append(f"{label} 必须生成链路脚本的 flow_id 存在重复：{flow_ids}")


def validate_business_scenario_map_file(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"缺少业务场景映射 sidecar：{path}"]
    try:
        text = read_text(path)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return [str(exc)]

    require_yaml_top_level_keys(text, BUSINESS_SCENARIO_REQUIRED_KEYS, errors, path.name)
    schema_version = yaml_int_value(text, "schema_version", errors, path.name)
    if schema_version is not None and schema_version != 1:
        errors.append(f"{path.name} schema_version 不是 1：{schema_version}")
    stage = first_yaml_scalar(text, "stage")
    if stage != "business_scenario_mapping":
        errors.append(f"{path.name} stage 不匹配：{stage} != business_scenario_mapping")
    status = first_yaml_scalar(text, "status")
    if status != "passed":
        errors.append(f"{path.name} status 不是 passed：{status}")
    next_stage_allowed = first_yaml_scalar(text, "next_stage_allowed")
    if next_stage_allowed is None or not is_yaml_true(next_stage_allowed):
        errors.append(f"{path.name} next_stage_allowed 不是 true：{next_stage_allowed}")
    if not yaml_section_has_sequence_items(text, "scenario_items"):
        errors.append(f"{path.name} passed 状态下 scenario_items 不能为空")
    require_yaml_empty_list(text, "blocking_issues", errors, path.name)
    for marker in BUSINESS_SCENARIO_REQUIRED_ITEM_MARKERS:
        if marker not in text:
            errors.append(f"{path.name} 缺少业务场景字段：{marker}")
    validate_required_chain_scenarios(text, errors, path.name)
    descriptions = business_scenario_descriptions(text)
    if not descriptions:
        errors.append(f"{path.name} 缺少有效 business_description")
    for description in descriptions:
        if not has_chinese(description):
            errors.append(f"{path.name} business_description 必须使用中文：{description}")
    for block in business_scenario_item_blocks(text):
        scenario_id = block_first_scalar(block, "scenario_id") or "UNKNOWN"
        description = block_first_scalar(block, "business_description") or ""
        business_domain = block_first_scalar(block, "business_domain") or ""
        executing_role = block_first_scalar(block, "executing_role") or ""
        if invalid_coverage_point_value(business_domain) or not has_chinese(business_domain):
            errors.append(f"{path.name} {scenario_id} business_domain 必须为中文业务域")
        if invalid_coverage_point_value(executing_role) or not has_chinese(executing_role):
            errors.append(f"{path.name} {scenario_id} executing_role 必须为中文执行角色")
        elif description and executing_role not in description:
            errors.append(f"{path.name} {scenario_id} business_description 必须包含执行角色：{executing_role}")
        if scenario_requires_chain(block) and looks_like_path_bucket_long_chain(
            business_domain,
            block_first_scalar(block, "scenario_name") or "",
            description,
        ):
            errors.append(f"{path.name} {scenario_id} 疑似按路径/接口前缀拼接链路候选，必须拆成真实业务场景")
    splittable_clusters = splittable_single_interface_clusters(business_scenario_items_from_yaml(text))
    if splittable_clusters:
        errors.append(
            f"{path.name} 存在可拆分多接口业务簇但仍全部按 single_interface 输出，"
            f"必须先按执行角色、业务动作、前置状态和预期业务结果拆成真实业务链路：{', '.join(splittable_clusters[:10])}"
        )
    for list_key in ("source_refs", "related_interfaces", "business_chain", "related_test_point_ids", "related_coverage_rule_ids"):
        values = yaml_scalar_values(text, list_key)
        if not values:
            errors.append(f"{path.name} 缺少业务场景列表字段：{list_key}")
        for value in values:
            if yaml_scalar_is_empty_list(value):
                errors.append(f"{path.name} 业务场景列表字段不能为空：{list_key}")
    for confidence in yaml_scalar_values(text, "confidence"):
        if confidence not in {"high", "medium"}:
            errors.append(f"{path.name} confidence 必须为 high/medium 才能放行：{confidence}")
    for blocker in yaml_scalar_values(text, "blockers"):
        if not yaml_scalar_is_empty_list(blocker):
            errors.append(f"{path.name} blockers 未清空：{blocker}")
    return errors


def validate_business_scenario_doc_file(path: Path) -> list[str]:
    if not path.is_file():
        return [f"缺少业务场景链路清单：{path}"]
    try:
        text = read_text(path)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return [str(exc)]
    errors: list[str] = []
    for header in (
        "业务场景ID",
        "业务场景名称",
        "业务场景描述",
        "链路类型",
        "是否必须生成链路脚本",
        "flow_id",
        "步骤数",
        "来源",
        "业务链路",
        "接口链路",
        "关联测试点ID",
        "关联覆盖规则ID",
    ):
        if header not in text:
            errors.append(f"{path.name} 缺少字段：{header}")
    return errors


def looks_like_path_bucket_long_chain(*values: str) -> bool:
    normalized_values = [normalize_yaml_value(value) for value in values if value]
    text = " ".join(normalized_values)
    if not normalized_values:
        return False
    generic_names = {
        "接口链路",
        "接口集合",
        "接口组合",
        "模块接口",
        "模块链路",
        "API集合",
        "API链路",
        "平台接口",
        "资源链路",
        "资源从业务处理到结果校验",
    }
    compact = re.sub(r"\s+", "", text)
    if compact in generic_names:
        return True
    label_text = " ".join(normalized_values[:2])
    if any(pattern.search(label_text) for pattern in BUSINESS_LONG_CHAIN_PATH_BUCKET_PATTERNS):
        return True
    description_text = " ".join(normalized_values[2:])
    return any(pattern.search(description_text) for pattern in BUSINESS_LONG_CHAIN_PATH_BUCKET_PATTERNS[2:])


def validate_business_long_chain_doc_file(path: Path) -> list[str]:
    if not path.is_file():
        return [f"缺少业务长链路设计清单：{path}"]
    try:
        text = read_text(path)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return [str(exc)]
    errors: list[str] = []
    for header in (
        "长链路ID",
        "设计级用例ID",
        "业务域",
        "业务场景",
        "执行角色",
        "接口链路",
        "来源",
        "覆盖状态",
        "可执行状态",
    ):
        if header not in text:
            errors.append(f"{path.name} 缺少字段：{header}")
    return errors


def validate_business_long_chain_cases_file(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"缺少业务长链路设计分母 sidecar：{path}"]
    try:
        text = read_text(path)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return [str(exc)]

    require_yaml_top_level_keys(text, BUSINESS_LONG_CHAIN_REQUIRED_KEYS, errors, path.name)
    schema_version = yaml_int_value(text, "schema_version", errors, path.name)
    if schema_version is not None and schema_version != 1:
        errors.append(f"{path.name} schema_version 不是 1：{schema_version}")
    stage = first_yaml_scalar(text, "stage")
    if stage != BUSINESS_LONG_CHAIN_STAGE:
        errors.append(f"{path.name} stage 不匹配：{stage} != {BUSINESS_LONG_CHAIN_STAGE}")
    status = first_yaml_scalar(text, "status")
    if status != "passed":
        errors.append(f"{path.name} status 不是 passed：{status}")
    next_stage_allowed = first_yaml_scalar(text, "next_stage_allowed")
    if next_stage_allowed is None or not is_yaml_true(next_stage_allowed):
        errors.append(f"{path.name} next_stage_allowed 不是 true：{next_stage_allowed}")
    denominator_scope = first_yaml_scalar(text, "denominator_scope")
    if denominator_scope != BUSINESS_LONG_CHAIN_DENOMINATOR_SCOPE:
        errors.append(
            f"{path.name} denominator_scope 不匹配："
            f"{denominator_scope} != {BUSINESS_LONG_CHAIN_DENOMINATOR_SCOPE}"
        )
    require_yaml_empty_list(text, "missing_business_long_chain_ids", errors, path.name)
    require_yaml_empty_list(text, "blocking_issues", errors, path.name)

    total = yaml_int_value(text, "business_long_chain_total", errors, path.name)
    covered = yaml_int_value(text, "business_long_chain_covered", errors, path.name)
    script_ready_total = yaml_int_value(text, "script_closed_loop_ready_total", errors, path.name)
    if total is not None and covered is not None and total != covered:
        errors.append(f"{path.name} 业务长链路覆盖计数不是 100%：{covered}/{total}")
    if total is not None and total < 0:
        errors.append(f"{path.name} business_long_chain_total 不能小于 0：{total}")
    if script_ready_total is not None and script_ready_total < 0:
        errors.append(f"{path.name} script_closed_loop_ready_total 不能小于 0：{script_ready_total}")

    chain_blocks = yaml_sequence_raw_blocks(text, "chains", "chain_id")
    if total is not None and total != len(chain_blocks):
        errors.append(f"{path.name} chains 明细数量与 business_long_chain_total 不一致：{len(chain_blocks)} != {total}")
    chain_ids: list[str] = []
    for block in chain_blocks:
        chain_id = block_first_scalar(block, "chain_id") or "UNKNOWN"
        chain_ids.append(chain_id)
        for marker in BUSINESS_LONG_CHAIN_REQUIRED_ITEM_MARKERS:
            if marker not in block:
                errors.append(f"{path.name} {chain_id} 缺少业务长链路字段：{marker}")
        case_id = block_first_scalar(block, "case_id")
        priority = normalize_yaml_value(block_first_scalar(block, "priority")).lower()
        business_domain = block_first_scalar(block, "business_domain") or ""
        scenario_name = block_first_scalar(block, "scenario_name") or ""
        description = block_first_scalar(block, "business_description") or ""
        executing_role = block_first_scalar(block, "executing_role") or ""
        design_status = normalize_yaml_value(block_first_scalar(block, "design_status"))
        executable_status = normalize_yaml_value(block_first_scalar(block, "executable_status"))
        interfaces = block_list_values(block, "interfaces")
        source_refs = block_list_values(block, "source_refs")
        test_point_ids = block_list_values(block, "related_test_point_ids")
        coverage_rule_ids = block_list_values(block, "related_coverage_rule_ids")
        interface_counts = yaml_int_values(block, "interface_count")
        step_counts = yaml_int_values(block, "step_count")
        interface_count = interface_counts[0] if interface_counts else len(interfaces)
        step_count = step_counts[0] if step_counts else 0

        if invalid_coverage_point_value(chain_id) or invalid_coverage_point_value(case_id):
            errors.append(f"{path.name} {chain_id} chain_id/case_id 不能为空或占位")
        if priority != "p0":
            errors.append(f"{path.name} {chain_id} 业务长链路设计用例必须为 p0：{priority}")
        if invalid_coverage_point_value(business_domain) or not has_chinese(business_domain):
            errors.append(f"{path.name} {chain_id} business_domain 必须为中文业务域")
        if invalid_coverage_point_value(scenario_name) or not has_chinese(scenario_name):
            errors.append(f"{path.name} {chain_id} scenario_name 必须为中文业务场景名称")
        if invalid_coverage_point_value(description) or not has_chinese(description):
            errors.append(f"{path.name} {chain_id} business_description 必须为中文真实业务场景")
        if invalid_coverage_point_value(executing_role) or not has_chinese(executing_role):
            errors.append(f"{path.name} {chain_id} executing_role 必须为中文执行角色")
        elif description and executing_role not in description:
            errors.append(f"{path.name} {chain_id} business_description 必须包含执行角色：{executing_role}")
        if looks_like_path_bucket_long_chain(business_domain, scenario_name, description):
            errors.append(f"{path.name} {chain_id} 疑似按路径/接口前缀拼接长链路，必须改为真实业务场景")
        if interface_count < LONG_CHAIN_INTERFACE_THRESHOLD and step_count < LONG_CHAIN_STEP_THRESHOLD:
            errors.append(
                f"{path.name} {chain_id} 不满足业务长链路阈值："
                f"interface_count={interface_count}，step_count={step_count}"
            )
        if len(interfaces) < LONG_CHAIN_INTERFACE_THRESHOLD and step_count < LONG_CHAIN_STEP_THRESHOLD:
            errors.append(f"{path.name} {chain_id} interfaces 少于 3 且未提供 5 步以上业务步骤")
        for list_key, values in (
            ("interfaces", interfaces),
            ("source_refs", source_refs),
            ("related_test_point_ids", test_point_ids),
            ("related_coverage_rule_ids", coverage_rule_ids),
        ):
            if not values:
                errors.append(f"{path.name} {chain_id} {list_key} 不能为空")
        if design_status != "covered":
            errors.append(f"{path.name} {chain_id} design_status 必须为 covered：{design_status}")
        if executable_status not in BUSINESS_LONG_CHAIN_EXECUTABLE_STATUSES:
            errors.append(f"{path.name} {chain_id} executable_status 非法：{executable_status}")
    if len(chain_ids) != len(set(chain_ids)):
        errors.append(f"{path.name} chain_id 存在重复：{chain_ids}")
    return errors


def parse_number(text: str) -> float | None:
    normalized = text.strip().replace(",", "")
    if re.fullmatch(r"\d+(?:\.\d+)?", normalized):
        return float(normalized)
    return None


def validate_coverage_numbers(coverage_text: str, errors: list[str]) -> None:
    for numerator_text, denominator_text in RATIO_PATTERN.findall(coverage_text):
        numerator = float(numerator_text)
        denominator = float(denominator_text)
        if denominator <= 0 or numerator != denominator:
            errors.append(f"{CASE_SOURCE} 覆盖分子/分母不是 100%：{numerator_text}/{denominator_text}")

    for raw_line in coverage_text.splitlines():
        cells = split_markdown_row(raw_line)
        if len(cells) < 4:
            continue
        if any(header in cell for cell in cells for header in ("分子", "分母", "结果", "是否达标")):
            continue
        numerator = parse_number(cells[1])
        denominator = parse_number(cells[2])
        if numerator is not None and denominator is not None:
            if denominator <= 0 or numerator != denominator:
                errors.append(f"{CASE_SOURCE} 覆盖表分子/分母不是 100%：{' | '.join(cells)}")
        if any(cell == "否" for cell in cells):
            errors.append(f"{CASE_SOURCE} 覆盖表存在未达标结论：{' | '.join(cells)}")


def validate_coverage_response_gate(case_text: str) -> list[str]:
    errors: list[str] = []
    quality_text = collect_sections(case_text, ("质检结论", "质量结论"))
    coverage_text = collect_sections(case_text, ("覆盖矩阵", "覆盖结论", "覆盖率准出摘要"))
    blocker_text = collect_sections(case_text, ("阻塞项",))
    conclusion_text = collect_sections(case_text, ("准出结论", "交付结论", "放行结论", "发布结论"))

    if "不通过" in quality_text:
        errors.append(f"{CASE_SOURCE} 质检结论为不通过，不能交接到执行级阶段")

    if not ("100" in coverage_text or "已覆盖" in coverage_text):
        errors.append(f"{CASE_SOURCE} 覆盖结论缺少 100% 或已覆盖证据")
    if any(term in coverage_text for term in COVERAGE_BLOCKING_TERMS):
        errors.append(f"{CASE_SOURCE} 覆盖矩阵存在未达标状态：覆盖不足/未覆盖/待补充/阻塞")
    validate_coverage_numbers(coverage_text, errors)
    for percent_text in PERCENT_PATTERN.findall(coverage_text):
        if float(percent_text) != 100:
            errors.append(f"{CASE_SOURCE} 覆盖率不是 100%：{percent_text}%")

    if has_meaningful_blocker(blocker_text):
        errors.append(f"{CASE_SOURCE} 阻塞项未清空，不能交接到执行级阶段")

    if any(term in conclusion_text for term in CONCLUSION_BLOCKING_TERMS):
        errors.append(f"{CASE_SOURCE} 准出结论未通过或存在覆盖不足/阻塞")
    if any(pattern.search(conclusion_text) for pattern in DENY_PATTERNS):
        errors.append(f"{CASE_SOURCE} 准出结论不允许声明 100% 覆盖或不允许进入下一阶段")
    if "是否允许" in conclusion_text and not ALLOW_100_PATTERN.search(conclusion_text):
        errors.append(f"{CASE_SOURCE} 准出结论缺少允许声明 100% 覆盖的明确结论")
    if not any(marker in conclusion_text for marker in ("结论：通过", "结果：通过", "允许进入下一阶段", "允许声明")):
        errors.append(f"{CASE_SOURCE} 准出结论缺少明确通过结论")

    return errors


def validate_case_list_case_blocks(case_yaml_text: str, errors: list[str], label: str) -> None:
    case_blocks = extract_yaml_sequence_blocks(case_yaml_text, "cases")
    if not case_blocks:
        errors.append(f"{label} passed 状态下 cases 缺少可解析用例明细")
        return
    seen_case_ids: set[str] = set()
    for index, case in enumerate(case_blocks, start=1):
        case_label = normalize_yaml_value(case.get("case_id")) or f"第 {index} 条用例"
        for field in CASE_LIST_REQUIRED_CASE_MARKERS:
            value = case.get(field)
            if yaml_value_is_missing(value, list_value=field in CASE_LIST_REQUIRED_LIST_FIELDS):
                errors.append(f"{label} {case_label} 缺少有效设计级用例字段：{field}")
        case_id = normalize_yaml_value(case.get("case_id"))
        if case_id:
            if case_id in seen_case_ids:
                errors.append(f"{label} case_id 重复：{case_id}")
            seen_case_ids.add(case_id)
        method = normalize_yaml_value(case.get("method")).upper()
        if method and method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
            errors.append(f"{label} {case_label} method 非法：{case.get('method')}")
        path = normalize_yaml_value(case.get("path"))
        if path and not path.startswith("/"):
            errors.append(f"{label} {case_label} path 必须以 / 开头：{path}")
        priority = normalize_yaml_value(case.get("priority")).lower()
        if priority and priority not in COVERAGE_POINT_PRIORITY_VALUES:
            errors.append(f"{label} {case_label} priority 必须为 p0/p1/p2：{case.get('priority')}")


def validate_case_list_yaml(case_yaml_text: str) -> list[str]:
    errors: list[str] = []
    require_yaml_top_level_keys(case_yaml_text, CASE_LIST_REQUIRED_KEYS, errors, CASE_LIST_YAML)
    schema_version = yaml_int_value(case_yaml_text, "schema_version", errors, CASE_LIST_YAML)
    if schema_version is not None and schema_version != 1:
        errors.append(f"{CASE_LIST_YAML} schema_version 不是 1：{schema_version}")
    stage = first_yaml_scalar(case_yaml_text, "stage")
    if stage != "interface_testcase_generation":
        errors.append(f"{CASE_LIST_YAML} stage 不匹配：{stage} != interface_testcase_generation")
    status = first_yaml_scalar(case_yaml_text, "status")
    if status != "passed":
        errors.append(f"{CASE_LIST_YAML} status 不是 passed：{status}")
    if re.search(r"(?m)^cases\s*:\s*\[\]\s*$", case_yaml_text) or not yaml_section_has_sequence_items(case_yaml_text, "cases"):
        errors.append(f"{CASE_LIST_YAML} passed 状态下 cases 不能为空")
    quality_gate_block = yaml_key_block(case_yaml_text, "quality_gate")
    quality_gate_status = gate_pass_status_from_block(quality_gate_block)
    if quality_gate_status != "passed":
        errors.append(f"{CASE_LIST_YAML} quality_gate.status/result 不是 passed：{quality_gate_status}")
    coverage_summary_block = yaml_key_block(case_yaml_text, "coverage_summary")
    coverage_rate = parse_yaml_rate(scalar_from_block(coverage_summary_block, "coverage_rate"))
    if coverage_rate is None:
        errors.append(f"{CASE_LIST_YAML} coverage_summary.coverage_rate 缺失或不可解析")
    elif coverage_rate != 100:
        errors.append(f"{CASE_LIST_YAML} coverage_summary.coverage_rate 不是 100：{coverage_rate:g}")
    require_yaml_empty_list(case_yaml_text, "blocking_issues", errors, CASE_LIST_YAML)
    for marker in CASE_LIST_REQUIRED_CASE_MARKERS:
        if marker not in case_yaml_text:
            errors.append(f"{CASE_LIST_YAML} 缺少设计级用例字段：{marker}")
    validate_case_list_case_blocks(case_yaml_text, errors, CASE_LIST_YAML)
    return errors


def build_case_list_markdown(case_yaml_text: str) -> str:
    return "\n".join(
        [
            "## 设计级接口测试用例清单",
            "",
            "- 来源文件：`03-interface-testcase-generation/case_list.yaml`",
            "- 交接方式：优先消费机器可读 YAML；本文件仅作展示和兼容，不新增字段。",
            "",
            "```yaml",
            case_yaml_text.rstrip(),
            "```",
            "",
        ]
    )


def quality_marker_keywords(markers: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(marker.lstrip("#").strip() for marker in markers)


def split_case_generation(case_text: str, case_yaml_text: str) -> tuple[str, str, list[str]]:
    errors: list[str] = []
    has_case = any(marker in case_text for marker in CASE_MARKERS)
    missing_quality_groups = [
        name
        for name, markers in QUALITY_MARKER_GROUPS.items()
        if not collect_sections(case_text, quality_marker_keywords(markers))
    ]
    if not has_case:
        errors.append(f"{CASE_SOURCE} 缺少可识别的接口用例内容")
    if missing_quality_groups:
        errors.append(f"{CASE_SOURCE} 缺少可识别的交接门禁内容：{'、'.join(missing_quality_groups)}")
    errors.extend(validate_coverage_response_gate(case_text))
    errors.extend(validate_case_list_yaml(case_yaml_text))
    case_list = build_case_list_markdown(case_yaml_text)
    report = "\n".join(
        [
            "## 设计级用例生成报告",
            "",
            "- 来源文件：`03-interface-testcase-generation/04_接口测试用例清单.md`",
            "- 交接方式：质量报告原文保留；设计级用例主数据来自 `case_list.yaml`",
            "",
            case_text,
        ]
    )
    return case_list, report, errors


def prepare_handoff(output_root: Path, entry: str) -> list[str]:
    errors: list[str] = []
    entry_dir = resolve_entry(output_root, entry)
    errors.extend(validate_entry(entry_dir))
    if entry_dir.name == "01-pre-doc-analysis":
        validate_stage_sidecars(
            entry_dir,
            errors,
            "文档入口",
            "pre_doc_analysis",
            PRE_DOC_COVERAGE_PAIRS,
            PRE_DOC_MISSING_LISTS,
        )
    else:
        validate_source_entry_release(entry_dir, errors)
    business_scenario_map_source = entry_dir / BUSINESS_SCENARIO_MAP
    business_scenario_doc_source = entry_dir / BUSINESS_SCENARIO_DOC
    errors.extend(validate_business_scenario_map_file(business_scenario_map_source))
    errors.extend(validate_business_scenario_doc_file(business_scenario_doc_source))
    required_chain_flow_source = output_root / REQUIRED_CHAIN_FLOWS
    chain_flow_audit_source = output_root / CHAIN_FLOW_CANDIDATE_AUDIT
    required_flow_ids, chain_flow_errors = validate_required_chain_flows_file(required_chain_flow_source)
    errors.extend(chain_flow_errors)
    errors.extend(validate_chain_flow_candidate_audit_file(chain_flow_audit_source, required_flow_ids))

    case_source = output_root / "03-interface-testcase-generation" / CASE_SOURCE
    case_yaml_source = output_root / "03-interface-testcase-generation" / CASE_LIST_YAML
    coverage_point_source = output_root / "03-interface-testcase-generation" / COVERAGE_POINT_REPORT
    business_long_chain_cases_source = output_root / "03-interface-testcase-generation" / BUSINESS_LONG_CHAIN_CASES
    business_long_chain_doc_source = output_root / "03-interface-testcase-generation" / BUSINESS_LONG_CHAIN_DOC
    stage2_coverage_matrix = output_root / "03-interface-testcase-generation" / "coverage_matrix.yaml"
    if not case_source.is_file():
        errors.append(f"缺少设计级用例生成产物：{case_source}")
    else:
        try:
            case_text = read_text(case_source)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            errors.append(str(exc))
            case_text = ""
    if not case_yaml_source.is_file():
        errors.append(f"缺少设计级用例机器可读产物：{case_yaml_source}")
    else:
        try:
            case_yaml_text = read_text(case_yaml_source)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            errors.append(str(exc))
            case_yaml_text = ""
    if coverage_point_source.is_file():
        errors.extend(validate_coverage_point_report_file(coverage_point_source))
        if case_yaml_text:
            errors.extend(validate_coverage_point_case_mapping(case_yaml_text, coverage_point_source))
    errors.extend(validate_business_long_chain_cases_file(business_long_chain_cases_source))
    errors.extend(validate_business_long_chain_doc_file(business_long_chain_doc_source))
    if errors:
        return errors

    validate_stage_sidecars(
        case_source.parent,
        errors,
        "设计级用例生成",
        "interface_testcase_generation",
        INTERFACE_COVERAGE_PAIRS,
        INTERFACE_MISSING_LISTS,
    )
    if required_flow_ids and stage2_coverage_matrix.is_file():
        try:
            validate_required_chain_independent_coverage(
                read_text(stage2_coverage_matrix),
                errors,
                "设计级用例生成/coverage_matrix.yaml",
                required_flow_ids,
                "generated_design_chain_case_count",
            )
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            errors.append(str(exc))
    if errors:
        return errors

    case_list, report, split_errors = split_case_generation(case_text, case_yaml_text)
    if split_errors:
        return split_errors

    handoff_dir = output_root / "04-design-case-handoff"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(entry_dir / ENTRY_DOCS["design"], handoff_dir / HANDOFF_DOCS["design"])
    shutil.copyfile(entry_dir / ENTRY_DOCS["contract"], handoff_dir / HANDOFF_DOCS["contract"])
    shutil.copyfile(case_yaml_source, handoff_dir / HANDOFF_DOCS["case_list_yaml"])
    if coverage_point_source.is_file():
        shutil.copyfile(coverage_point_source, handoff_dir / HANDOFF_DOCS["coverage_point_report"])
    shutil.copyfile(business_long_chain_cases_source, handoff_dir / HANDOFF_DOCS["business_long_chain_cases"])
    shutil.copyfile(business_long_chain_doc_source, handoff_dir / HANDOFF_DOCS["business_long_chain_doc"])
    shutil.copyfile(required_chain_flow_source, handoff_dir / HANDOFF_DOCS["required_chain_flows"])
    shutil.copyfile(chain_flow_audit_source, handoff_dir / HANDOFF_DOCS["chain_flow_candidate_audit"])
    shutil.copyfile(business_scenario_map_source, handoff_dir / HANDOFF_DOCS["business_scenario_map"])
    shutil.copyfile(business_scenario_doc_source, handoff_dir / HANDOFF_DOCS["business_scenario_doc"])
    (handoff_dir / HANDOFF_DOCS["case_list"]).write_text(case_list, encoding="utf-8")
    (handoff_dir / HANDOFF_DOCS["execution_report"]).write_text(report, encoding="utf-8")
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="准备接口自动化流水线设计级用例交接文件")
    parser.add_argument("--output-root", required=True, help="流水线输出根目录")
    parser.add_argument("--entry", choices=("auto", "doc", "source"), default="auto", help="选择文档入口或源码入口")
    args = parser.parse_args()

    errors = prepare_handoff(Path(args.output_root), args.entry)
    if errors:
        print("交接准备结果：不通过")
        for index, error in enumerate(errors, start=1):
            print(f"{index}. {error}")
        return 1
    print("交接准备结果：通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
