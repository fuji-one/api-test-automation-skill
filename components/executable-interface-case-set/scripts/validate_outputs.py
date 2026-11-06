#!/usr/bin/env python3
"""校验 executable-interface-case-set 阶段产物。"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# 允许总回归从任意工作目录按文件路径加载本校验器，同时保持原有同目录导入逻辑。
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from validate_runtime_business_dependencies import validate_runtime_business_dependencies


REQUIRED_FILES = ("执行级接口用例集.md", "前置数据构造规则.md")
REQUIRED_SIDECARS = ("stage_status.yaml", "coverage_matrix.yaml", "execution_fact_sources.yaml")
OPTIONAL_APIFOX_SIDECAR = "apifox_evidence_index.yaml"
SHARD_INDEX_FILE = "执行级用例分片索引.md"
SHARD_DIR = "执行级用例分片"
BASE_OUTPUT_ENTRIES = (*REQUIRED_FILES, *REQUIRED_SIDECARS)
SHARDED_OUTPUT_ENTRIES = (*BASE_OUTPUT_ENTRIES, SHARD_INDEX_FILE, SHARD_DIR)
STAGE_STATUSES = (
    "PASSED",
    "FAILED_DESIGN_GATE",
    "FAILED_CONTRACT_GATE",
    "BLOCKED_NEED_EXECUTION_INPUT",
    "BLOCKED_NEED_CHAIN_FLOW_EVIDENCE",
    "FAILED_EXECUTION_READINESS",
)
CASE_FIELDS = (
    "用例ID",
    "用例名称",
    "用例类型",
    "用例优先级",
    "请求方式",
    "追溯接口",
    "追溯测试点",
    "allure 标记",
    "前置条件",
    "执行步骤",
    "完整入参",
    "出参契约",
    "预期响应",
    "断言规则",
    "变量提取",
    "变量注入",
    "链路flow_id",
    "链路步骤序号",
    "链路生产者/消费者",
    "清理引用",
    "可转 pytest 标记",
    "来源依据",
    "置信度分数",
    "置信度等级",
    "置信度区间",
    "置信度范围",
    "场景相关性",
    "置信度维度",
    "置信度原因码",
    "置信度硬上限原因",
    "置信度证据引用",
)
RULE_SECTIONS = (
    "阶段结论",
    "输入前置校验",
    "输入完整性检查",
    "数据模型索引",
    "环境与鉴权配置需求",
    "前置数据构造规则",
    "变量提取与注入规则",
    "链路脚本生成证据",
    "清理策略",
    "可重复执行校验",
    "脚本生成准出门禁",
    "缺失数据与待确认项",
    "pytest+allure 转换准出结论",
)
REQUEST_METHODS = ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS")
PRIORITIES = ("P0", "P1", "P2")
PASSED_PRECHECK_ITEMS = (
    "前置校验总结果",
    "文档完整性",
    "设计级准出",
    "用例基础字段完整性",
    "主要流程字段完整性",
    "异常流程字段完整性",
    "契约完整性",
    "数据模型完整性",
    "表关系知识图谱完整性",
    "链路场景完整性",
    "铺数与清理顺序完整性",
    "MCP 连接状态",
    "鉴权账号与清理输入",
)
SCRIPT_GATE_ITEMS = (
    "脚本生成准出总结果",
    "真实入参完整性",
    "正向展示字段真实合法性",
    "预期出参与码值完整性",
    "断言规则完整性",
    "鉴权账号与 token 规则完整性",
    "前置数据构造完整性",
    "表结构与关系图完整性",
    "变量提取与注入完整性",
    "清理策略完整性",
    "多接口链路完整性",
    "来源追溯完整性",
    "脚本生成字段完整性",
)
YAML_BLOCK_RE = re.compile(r"```ya?ml\s*\n(.*?)\n```", re.DOTALL | re.IGNORECASE)
CASE_START_RE = re.compile(r"(?m)^\s*-\s+用例ID\s*:")
CASE_FIELD_RE = re.compile(r"(?m)^\s*(?:-\s+)?{field}\s*:")
EMPTY_SCALAR_VALUES = ("", '""', "''", "{}", "[]", "null", "None", "~")
UNRESOLVED_EXACT_VALUES = (
    "...",
    "通过/不通过",
    "通过/部分通过/不通过",
    "是/否",
    "PASSED/BLOCKED_NEED_EXECUTION_INPUT/BLOCKED_NEED_CHAIN_FLOW_EVIDENCE/FAILED_DESIGN_GATE/FAILED_CONTRACT_GATE/FAILED_EXECUTION_READINESS",
    "status/jsonpath/schema/db/event/callback/relation",
)
UNRESOLVED_TEXT_MARKERS = (
    "待补充",
    "待确认",
    "TBD",
    "TODO",
)
TEMPLATE_PLACEHOLDER_TEXT_MARKERS = (
    "待补充",
    "TBD",
    "TODO",
)
NON_EMPTY_SCALAR_CASE_FIELDS = (
    "用例ID",
    "用例名称",
    "用例类型",
    "用例优先级",
    "请求方式",
    "追溯接口",
    "追溯测试点",
    "置信度分数",
    "置信度等级",
    "置信度区间",
    "置信度范围",
    "场景相关性",
)
CONFIDENCE_DIMENSION_WEIGHTS = {
    "contract": 0.25,
    "request_materialization": 0.20,
    "scenario_precondition": 0.20,
    "business_assertion": 0.20,
    "runtime_repeatability": 0.15,
}
CONFIDENCE_CAPS = {
    "SOURCE_CONFLICT_UNRESOLVED": 0.49,
    "CONTRACT_NOT_CONFIRMED": 0.59,
    "INPUT_NOT_CONFIRMED": 0.69,
    "SCENARIO_STATE_NOT_CLOSED": 0.79,
    "ASSERTION_BUSINESS_RESULT_NOT_CLOSED": 0.79,
    "WRITE_CLEANUP_NOT_MATERIALIZED": 0.59,
    "EXTERNAL_DEPENDENCY_SANDBOX_MISSING": 0.69,
    "RUNTIME_NOT_VERIFIED": 0.89,
}
CONFIDENCE_RELEVANCE = {
    "core_real_journey",
    "reachable_business_branch",
    "contract_boundary",
    "synthetic_resilience",
    "source_inferred_only",
}
NON_PASSED_CASE_LINES = (
    "## 执行级接口用例集",
    "- 阶段状态：{stage_status}",
    "- 生成状态：未生成",
    "- 原因：执行级门禁未通过，详见 `前置数据构造规则.md`",
)
PASSED_REQUIRED_TABLE_SECTIONS = (
    "输入完整性检查",
    "数据模型索引",
    "环境与鉴权配置需求",
    "前置数据构造规则",
    "变量提取与注入规则",
    "链路脚本生成证据",
    "清理策略",
    "可重复执行校验",
)
YAML_SCALAR_RE = re.compile(r"^\s*([A-Za-z0-9_]+)\s*:\s*(.*?)\s*$")
YAML_TOP_LEVEL_KEY_RE = re.compile(r"^([A-Za-z0-9_]+)\s*:", re.MULTILINE)
STAGE_STATUS_REQUIRED_KEYS = ("schema_version", "stage", "status", "next_stage_allowed", "input_paths", "output_paths", "gate_checks", "blocking_issues")
COVERAGE_MATRIX_REQUIRED_KEYS = ("schema_version", "stage", "coverage_summary", "coverage_items", "missing_items", "upstream_downstream_mappings")
EXECUTION_FACT_SOURCE_REQUIRED_KEYS = ("schema_version", "stage", "status", "required_human_inputs", "fact_sources", "missing_required_facts", "conflict_facts", "blocking_issues")
APIFOX_EVIDENCE_REQUIRED_KEYS = ("schema_version", "stage", "status", "evidence_items", "conflict_items", "conflict_priority", "resolution_policy")
EXECUTABLE_COVERAGE_PAIRS = (("design_case_total", "design_case_mapped"), ("executable_case_total", "executable_case_traced"), ("coverage_rule_total", "coverage_rule_mapped"))
EXECUTABLE_MISSING_LISTS = ("missing_design_case_ids", "missing_executable_trace_ids", "missing_coverage_rule_ids")
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
CHAIN_COVERAGE_TYPES = ("chain_scenario", "chain_function", "chain_process")
APIFOX_EVIDENCE_LEVELS = ("project_structure", "interface_contract", "saved_case_example", "response_example")
RUNTIME_EVIDENCE_DIR = "04-runtime-evidence"
RUNTIME_EVIDENCE_FILES = ("runtime_stage_status.yaml", "runtime_evidence.yaml", "runtime_value_catalog.yaml")
RUNTIME_STATUS_VALUES = {"passed", "partial", "blocked", "failed"}
ACCOUNT_NOT_REQUIRED_VALUES = {
    "",
    "false",
    "no",
    "none",
    "null",
    "not_required",
    "not_required_or_none",
    "不需要",
    "无",
    "否",
}
ACCOUNT_SPECIFIC_CHAIN_FACT_TYPE = "account_specific_chain"
LOGIN_ENTRY_FACT_TYPE = "login_entry_rule"
ACCOUNT_SPECIFIC_MARKER_KEYS = (
    "specific_account_required",
    "requires_specific_account",
    "account_specific",
    "required_account_role",
    "required_account_business_state",
    "required_tenant",
    "required_permission",
)
REQUIRED_CHAIN_FLOWS = "required_chain_flows.yaml"


def read_text(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path.name} 不是 UTF-8 编码: {exc}") from exc
    if chr(0xFFFD) in text:
        raise ValueError(f"{path.name} 存在疑似中文乱码字符")
    if not text.strip():
        raise ValueError(f"{path.name} 内容为空")
    return text


def require(condition: bool, errors: list[str], message: str) -> None:
    if not condition:
        errors.append(message)



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


def is_yaml_true(value: str | None) -> bool:
    return (value or "").strip().lower() in {"true", "yes", "是", "passed"}


def require_yaml_empty_list(text: str, key: str, errors: list[str], label: str) -> None:
    values = yaml_scalar_values(text, key)
    if not values:
        errors.append(f"{label} 缺少空列表字段：{key}")
        return
    if values[0] != "[]":
        errors.append(f"{label} 列表未清空：{key}={values[0]}")


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


def parse_inline_mapping(text: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for part in text.split(","):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        mapping[key.strip()] = value.strip().strip("\"'")
    return mapping


def extract_yaml_sequence_blocks(text: str, section_key: str) -> list[dict[str, str]]:
    section = yaml_section(text, section_key)
    blocks: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw_line in section.splitlines():
        stripped = raw_line.strip()
        inline_match = re.match(r"^-\s*\{(.+)\}\s*$", stripped)
        if inline_match:
            if current is not None:
                blocks.append(current)
                current = None
            blocks.append(parse_inline_mapping(inline_match.group(1)))
            continue
        item_match = re.match(r"^-\s+([A-Za-z0-9_]+)\s*:\s*(.*?)\s*$", stripped)
        if item_match:
            if current is not None:
                blocks.append(current)
            current = {item_match.group(1): item_match.group(2).strip().strip("\"'")}
            continue
        if current is None:
            continue
        scalar_match = re.match(r"^([A-Za-z0-9_]+)\s*:\s*(.*?)\s*$", stripped)
        if scalar_match:
            current[scalar_match.group(1)] = scalar_match.group(2).strip().strip("\"'")
    if current is not None:
        blocks.append(current)
    return blocks


def extract_fact_source_items(text: str) -> list[dict[str, str]]:
    return extract_yaml_sequence_blocks(text, "fact_sources")


def required_chain_flow_ids_from_text(text: str) -> set[str]:
    flow_ids: set[str] = set()
    for item in extract_yaml_sequence_blocks(text, "flows"):
        if item.get("status") != "required":
            continue
        flow_id = normalized_scalar(item.get("flow_id"))
        if flow_id:
            flow_ids.add(flow_id)
    return flow_ids


def required_chain_flow_ids_from_context(output_dir: Path, fact_text: str) -> set[str]:
    flow_ids: set[str] = set()
    candidate_paths = (
        output_dir / REQUIRED_CHAIN_FLOWS,
        output_dir.parent / REQUIRED_CHAIN_FLOWS,
        output_dir.parent / "04-design-case-handoff" / REQUIRED_CHAIN_FLOWS,
    )
    seen_paths: set[Path] = set()
    for path in candidate_paths:
        normalized_path = path.resolve()
        if normalized_path in seen_paths:
            continue
        seen_paths.add(normalized_path)
        if not path.is_file():
            continue
        flow_ids.update(required_chain_flow_ids_from_text(read_text(path)))
    flow_ids.update(
        match.group(1).strip().strip("\"'")
        for match in re.finditer(r"required_chain_flows\.ya?ml#([A-Za-z0-9_.:-]+)", fact_text)
    )
    return {flow_id for flow_id in flow_ids if flow_id}


def account_marker_value_requires_login(value: str | None) -> bool:
    normalized = normalized_scalar(value).lower()
    return normalized not in ACCOUNT_NOT_REQUIRED_VALUES


def item_marks_account_specific(item: dict[str, str]) -> bool:
    if item.get("fact_type") == ACCOUNT_SPECIFIC_CHAIN_FACT_TYPE:
        return True
    for key in ACCOUNT_SPECIFIC_MARKER_KEYS:
        if key not in item:
            continue
        if key in {"specific_account_required", "requires_specific_account", "account_specific"}:
            if is_yaml_true(item.get(key) or ""):
                return True
            continue
        if account_marker_value_requires_login(item.get(key)):
            return True
    return False


def fact_sources_need_login_entry_rule(fact_items: list[dict[str, str]]) -> bool:
    return any(item_marks_account_specific(item) for item in fact_items)


def has_confirmed_login_entry_rule(fact_items: list[dict[str, str]]) -> bool:
    for item in fact_items:
        if item.get("fact_type") != LOGIN_ENTRY_FACT_TYPE:
            continue
        if item.get("source_status") == "confirmed" and normalized_scalar(item.get("source_ref")):
            return True
    return False


def runtime_ref_id(source_ref: str | None) -> str | None:
    normalized = normalized_scalar(source_ref)
    if "#" not in normalized:
        return None
    return normalized.rsplit("#", 1)[1].strip()


def runtime_confirmed_ids(path: Path, id_key: str, section_key: str, require_usable: bool = False) -> set[str]:
    text = read_text(path)
    ids: set[str] = set()
    for block in extract_yaml_sequence_blocks(text, section_key):
        item_id = normalized_scalar(block.get(id_key))
        if not item_id:
            continue
        source_status = normalized_scalar(block.get("source_status"))
        usable = is_yaml_true(block.get("usable_for_execution_case") or "")
        if source_status == "confirmed" and (not require_usable or usable):
            ids.add(item_id)
    return ids


def validate_runtime_evidence_sidecars(output_dir: Path, fact_text: str, errors: list[str]) -> None:
    if "live_request_evidence" not in fact_text:
        return
    runtime_dir = output_dir.parent / RUNTIME_EVIDENCE_DIR
    require(runtime_dir.is_dir(), errors, f"执行事实引用 live_request_evidence 时缺少运行时取证目录：{runtime_dir}")
    if not runtime_dir.is_dir():
        return
    for filename in RUNTIME_EVIDENCE_FILES:
        require((runtime_dir / filename).is_file(), errors, f"运行时取证目录缺少文件：{filename}")
    if not all((runtime_dir / filename).is_file() for filename in RUNTIME_EVIDENCE_FILES):
        return

    try:
        stage_status_text = read_text(runtime_dir / "runtime_stage_status.yaml")
        evidence_text = read_text(runtime_dir / "runtime_evidence.yaml")
        catalog_text = read_text(runtime_dir / "runtime_value_catalog.yaml")
    except ValueError as exc:
        errors.append(str(exc))
        return
    for filename, text in (
        ("runtime_stage_status.yaml", stage_status_text),
        ("runtime_evidence.yaml", evidence_text),
        ("runtime_value_catalog.yaml", catalog_text),
    ):
        schema_version = yaml_int_value(text, "schema_version", errors, filename)
        if schema_version is not None and schema_version != 1:
            errors.append(f"{filename} schema_version 不是 1：{schema_version}")
        status = first_yaml_scalar(text, "status")
        require(status in RUNTIME_STATUS_VALUES, errors, f"{filename} status 非法：{status}")
    require(first_yaml_scalar(stage_status_text, "stage") == "runtime_live_evidence", errors, "runtime_stage_status.yaml stage 必须为 runtime_live_evidence")
    require(first_yaml_scalar(evidence_text, "stage") == "runtime_live_evidence", errors, "runtime_evidence.yaml stage 必须为 runtime_live_evidence")
    require(first_yaml_scalar(catalog_text, "stage") == "runtime_value_catalog", errors, "runtime_value_catalog.yaml stage 必须为 runtime_value_catalog")
    require(first_yaml_scalar(evidence_text, "status") in {"passed", "partial"}, errors, "runtime_evidence.yaml 被引用时 status 必须为 passed 或 partial")
    require(first_yaml_scalar(catalog_text, "status") in {"passed", "partial"}, errors, "runtime_value_catalog.yaml 被引用时 status 必须为 passed 或 partial")
    require_yaml_empty_list(evidence_text, "conflict_items", errors, "runtime_evidence.yaml")
    require_yaml_empty_list(catalog_text, "conflict_values", errors, "runtime_value_catalog.yaml")

    try:
        valid_ids = runtime_confirmed_ids(runtime_dir / "runtime_evidence.yaml", "evidence_id", "evidence_items", require_usable=True)
        valid_ids.update(runtime_confirmed_ids(runtime_dir / "runtime_value_catalog.yaml", "value_id", "values"))
    except ValueError as exc:
        errors.append(str(exc))
        return
    for item in extract_fact_source_items(fact_text):
        if item.get("source_type") != "live_request_evidence":
            continue
        fact_id = item.get("fact_id") or item.get("fact_type") or "UNKNOWN"
        require(item.get("source_status") == "confirmed", errors, f"execution_fact_sources.yaml {fact_id} live_request_evidence 必须为 confirmed")
        ref_id = runtime_ref_id(item.get("source_ref"))
        require(bool(ref_id), errors, f"execution_fact_sources.yaml {fact_id} live_request_evidence 必须引用证据 ID")
        if ref_id:
            require(ref_id in valid_ids, errors, f"execution_fact_sources.yaml {fact_id} 引用的运行时证据不存在或不可用：{ref_id}")


def require_sections(text: str, sections: tuple[str, ...], filename: str, errors: list[str]) -> None:
    for section in sections:
        pattern = re.compile(r"(?m)^##\s+{section}\s*$".format(section=re.escape(section)))
        require(pattern.search(text) is not None, errors, f"{filename} 缺少章节：## {section}")


def line_value(text: str, label: str) -> str | None:
    for line in text.splitlines():
        normalized = line.strip().lstrip("-").strip()
        if normalized.startswith(f"{label}："):
            return normalized.split("：", 1)[1].strip()
    return None


def require_line_value(text: str, label: str, expected: str, errors: list[str], message: str) -> None:
    value = line_value(text, label)
    require(value == expected, errors, message)


def detect_stage_status(text: str) -> str | None:
    for line in text.splitlines():
        normalized = line.strip().lstrip("-").strip()
        if normalized.startswith("阶段状态："):
            return normalized.split("：", 1)[1].strip()
    return None


def detect_all_stage_statuses(text: str) -> list[str]:
    statuses = []
    for line in text.splitlines():
        normalized = line.strip().lstrip("-").strip()
        if normalized.startswith("阶段状态："):
            statuses.append(normalized.split("：", 1)[1].strip())
    return statuses


def extract_yaml_case_blocks(case_text: str) -> list[str]:
    blocks = []
    for yaml_block in YAML_BLOCK_RE.findall(case_text):
        starts = list(CASE_START_RE.finditer(yaml_block))
        for index, start in enumerate(starts):
            end = starts[index + 1].start() if index + 1 < len(starts) else len(yaml_block)
            blocks.append(yaml_block[start.start():end])
    return blocks


def normalized_scalar(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip().strip("\"'")


def is_unresolved_scalar(value: str | None) -> bool:
    normalized = normalized_scalar(value)
    if normalized in UNRESOLVED_EXACT_VALUES:
        return True
    return any(marker in normalized for marker in UNRESOLVED_TEXT_MARKERS)


def is_template_placeholder_scalar(value: str | None) -> bool:
    normalized = normalized_scalar(value)
    if normalized in UNRESOLVED_EXACT_VALUES:
        return True
    return any(marker in normalized for marker in TEMPLATE_PLACEHOLDER_TEXT_MARKERS)


def is_meaningful_scalar(value: str | None) -> bool:
    normalized = normalized_scalar(value)
    return normalized not in EMPTY_SCALAR_VALUES and not is_unresolved_scalar(normalized)


def is_closed_scalar(value: str | None) -> bool:
    normalized = normalized_scalar(value)
    return normalized not in EMPTY_SCALAR_VALUES and not is_template_placeholder_scalar(normalized)


def section_body(text: str, section: str) -> str:
    pattern = re.compile(
        r"(?ms)^##\s+{section}\s*$\n?(.*?)(?=^##\s+|\Z)".format(section=re.escape(section))
    )
    match = pattern.search(text)
    return match.group(1) if match else ""


def table_data_rows(section_text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    table_lines = [line.strip() for line in section_text.splitlines() if line.strip().startswith("|")]
    separator_index = None
    for index, line in enumerate(table_lines):
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            separator_index = index
            break
    if separator_index is None:
        return rows

    for line in table_lines[separator_index + 1 :]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells and any(is_meaningful_scalar(cell) for cell in cells):
            rows.append(cells)
    return rows


def read_shard_index(index_text: str, errors: list[str]) -> list[tuple[str, str, str]]:
    require(index_text.lstrip().startswith("## 执行级用例分片索引"), errors, f"{SHARD_INDEX_FILE} 必须以 ## 执行级用例分片索引 开头")
    rows = table_data_rows(index_text)
    require(bool(rows), errors, f"{SHARD_INDEX_FILE} 必须包含分片顺序表")
    validate_table_values(SHARD_INDEX_FILE, rows, errors)

    shards = []
    seen_orders: set[str] = set()
    seen_files: set[str] = set()
    for row_index, row in enumerate(rows, start=1):
        require(len(row) >= 3, errors, f"{SHARD_INDEX_FILE} 第 {row_index} 条数据至少需要 顺序、分片ID、文件 三列")
        if len(row) < 3:
            continue
        order, shard_id, file_ref = row[0], row[1], row[2]
        file_name = Path(file_ref).name
        require(re.fullmatch(r"\d{3}", order) is not None, errors, f"{SHARD_INDEX_FILE} 第 {row_index} 条顺序必须是 001 格式：{order}")
        require(is_meaningful_scalar(shard_id), errors, f"{SHARD_INDEX_FILE} 第 {row_index} 条分片ID不能为空")
        require(file_ref.startswith(f"{SHARD_DIR}/"), errors, f"{SHARD_INDEX_FILE} 第 {row_index} 条文件必须位于 {SHARD_DIR}/ 下：{file_ref}")
        require(re.fullmatch(rf"{re.escape(SHARD_DIR)}/\d{{3}}_[^/]+\.md", file_ref) is not None, errors, f"{SHARD_INDEX_FILE} 第 {row_index} 条文件名必须使用 001_名称.md 格式：{file_ref}")
        require(file_name.startswith(f"{order}_"), errors, f"{SHARD_INDEX_FILE} 第 {row_index} 条文件名前缀必须与顺序一致：{file_ref}")
        require(order not in seen_orders, errors, f"{SHARD_INDEX_FILE} 存在重复顺序：{order}")
        require(file_ref not in seen_files, errors, f"{SHARD_INDEX_FILE} 存在重复文件引用：{file_ref}")
        seen_orders.add(order)
        seen_files.add(file_ref)
        shards.append((order, shard_id, file_ref))

    expected_orders = [f"{index:03d}" for index in range(1, len(shards) + 1)]
    actual_orders = [order for order, _, _ in sorted(shards)]
    require(actual_orders == expected_orders, errors, f"{SHARD_INDEX_FILE} 顺序必须从 001 连续递增")
    return sorted(shards)


def read_sharded_case_text(output_dir: Path, index_text: str, errors: list[str], shards: list[tuple[str, str, str]] | None = None) -> str:
    if shards is None:
        shards = read_shard_index(index_text, errors)
    shard_dir = output_dir / SHARD_DIR
    require(shard_dir.is_dir(), errors, f"分片目录不存在或不是目录：{SHARD_DIR}")
    if not shard_dir.is_dir():
        return ""

    actual_shards = sorted(path.name for path in shard_dir.iterdir() if path.is_file())
    non_file_entries = sorted(path.name for path in shard_dir.iterdir() if not path.is_file())
    require(not non_file_entries, errors, f"{SHARD_DIR} 目录不得包含子目录或非文件条目：{', '.join(non_file_entries)}")
    expected_shards = sorted(Path(file_ref).name for _, _, file_ref in shards)
    require(actual_shards == expected_shards, errors, f"{SHARD_DIR} 目录中的分片文件必须与 {SHARD_INDEX_FILE} 完全一致")

    shard_texts = []
    for order, shard_id, file_ref in shards:
        shard_path = output_dir / file_ref
        try:
            shard_text = read_text(shard_path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        require(shard_text.lstrip().startswith("## 执行级接口用例分片"), errors, f"{file_ref} 必须以 ## 执行级接口用例分片 开头")
        require_line_value(shard_text, "顺序", order, errors, f"{file_ref} 必须声明顺序：{order}")
        require_line_value(shard_text, "分片ID", shard_id, errors, f"{file_ref} 必须声明分片ID：{shard_id}")
        shard_texts.append(shard_text)
    return "\n\n".join(shard_texts)


def validate_sharded_entry(case_text: str, shard_count: int, errors: list[str]) -> None:
    require_line_value(case_text, "阶段状态", "PASSED", errors, "分片输出的执行级接口用例集.md 必须声明阶段状态：PASSED")
    require_line_value(case_text, "分片模式", "启用", errors, "分片输出的执行级接口用例集.md 必须声明分片模式：启用")
    require_line_value(case_text, "分片索引", SHARD_INDEX_FILE, errors, f"分片输出的执行级接口用例集.md 必须声明分片索引：{SHARD_INDEX_FILE}")
    count_value = line_value(case_text, "分片数量")
    require(count_value == str(shard_count), errors, f"分片输出的执行级接口用例集.md 必须声明正确分片数量：{shard_count}")
    require(line_value(case_text, "读取顺序") is not None, errors, "分片输出的执行级接口用例集.md 必须声明读取顺序")
    require_line_value(case_text, "规则文件", "前置数据构造规则.md", errors, "分片输出的执行级接口用例集.md 必须声明规则文件：前置数据构造规则.md")
    require(not extract_yaml_case_blocks(case_text), errors, "分片输出的执行级接口用例集.md 不得直接包含执行级用例 yaml 块")


def validate_table_values(section: str, rows: list[list[str]], errors: list[str]) -> None:
    for row_index, row in enumerate(rows, start=1):
        for cell in row:
            require(not is_unresolved_scalar(cell), errors, f"{section} 第 {row_index} 条数据存在未闭合占位值：{cell}")


def validate_table_placeholders(section: str, rows: list[list[str]], errors: list[str]) -> None:
    for row_index, row in enumerate(rows, start=1):
        for cell in row:
            require(not is_template_placeholder_scalar(cell), errors, f"{section} 第 {row_index} 条数据存在未闭合模板占位值：{cell}")


def validate_rules_line_values_closed(rules_text: str, errors: list[str]) -> None:
    in_code_block = False
    for line_no, line in enumerate(rules_text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block or not stripped or stripped.startswith("#") or stripped.startswith("|"):
            continue
        normalized = stripped.lstrip("-").strip()
        if "：" not in normalized:
            continue
        _, value = normalized.split("：", 1)
        require(
            not is_template_placeholder_scalar(value),
            errors,
            f"前置数据构造规则.md 第 {line_no} 行存在未闭合模板占位值：{value.strip()}",
        )


def require_balanced_inline_yaml(line: str, errors: list[str], case_label: str, line_no: int) -> None:
    stack: list[str] = []
    quote: str | None = None
    escaped = False
    pairs = {"]": "[", "}": "{"}
    for char in line:
        if quote:
            if quote == '"' and char == "\\" and not escaped:
                escaped = True
                continue
            if char == quote and not escaped:
                quote = None
            escaped = False
            continue
        if char in ("'", '"'):
            quote = char
        elif char in ("[", "{"):
            stack.append(char)
        elif char in pairs:
            if not stack or stack[-1] != pairs[char]:
                errors.append(f"{case_label} 第 {line_no} 行存在未匹配的 YAML 括号")
                return
            stack.pop()
    require(quote is None, errors, f"{case_label} 第 {line_no} 行存在未闭合的 YAML 引号")
    require(not stack, errors, f"{case_label} 第 {line_no} 行存在未闭合的 YAML 括号")


def validate_yaml_like_syntax(case_block: str, errors: list[str], case_label: str) -> None:
    for line_no, line in enumerate(case_block.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        require("\t" not in line[: len(line) - len(line.lstrip())], errors, f"{case_label} 第 {line_no} 行缩进不得使用制表符")
        require((len(line) - len(line.lstrip(" "))) % 2 == 0, errors, f"{case_label} 第 {line_no} 行缩进必须是 2 的倍数")
        require_balanced_inline_yaml(line, errors, case_label, line_no)
        if stripped.startswith("- "):
            item = stripped[2:].strip()
            require(bool(item), errors, f"{case_label} 第 {line_no} 行列表项不能为空")
            continue
        require(":" in stripped, errors, f"{case_label} 第 {line_no} 行不是有效的 YAML 字段行")


def validate_case_values_closed(case_block: str, errors: list[str], case_label: str) -> None:
    for line_no, line in enumerate(case_block.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            item = stripped[2:].strip()
            if ":" in item:
                _, value = item.split(":", 1)
                value = value.strip()
            else:
                value = item
        elif ":" in stripped:
            _, value = stripped.split(":", 1)
            value = value.strip()
        else:
            continue
        require(not is_unresolved_scalar(value), errors, f"{case_label} 第 {line_no} 行存在未闭合占位值：{value}")


def top_level_indent(case_block: str) -> str | None:
    match = re.search(r"(?m)^(\s*)-\s+用例ID\s*:", case_block)
    if not match:
        return None
    return match.group(1) + "  "


def top_level_scalar(case_block: str, field: str) -> str | None:
    if field == "用例ID":
        pattern = re.compile(r"(?m)^\s*-\s+用例ID\s*:\s*[\"']?(.*?)[\"']?\s*$")
        match = pattern.search(case_block)
        if not match:
            return None
        return match.group(1).strip().strip("\"'")

    indent = top_level_indent(case_block)
    if indent is None:
        return None
    pattern = re.compile(r"(?m)^{indent}{field}\s*:\s*[\"']?(.*?)[\"']?\s*$".format(indent=re.escape(indent), field=re.escape(field)))
    match = pattern.search(case_block)
    if not match:
        return None
    return match.group(1).strip().strip("\"'")


def top_level_field_block(case_block: str, field: str) -> str | None:
    indent = top_level_indent(case_block)
    if indent is None:
        return None
    if field == "用例ID":
        pattern = re.compile(r"(?m)^(\s*-\s+用例ID\s*:.*(?:\n(?!{indent}\S[^:\n]*:).*)*)".format(indent=re.escape(indent)))
    else:
        pattern = re.compile(r"(?m)^({indent}{field}\s*:.*(?:\n(?!{indent}\S[^:\n]*:).*)*)".format(indent=re.escape(indent), field=re.escape(field)))
    match = pattern.search(case_block)
    if not match:
        return None
    return match.group(1)


def top_level_field_count(case_block: str, field: str) -> int:
    indent = top_level_indent(case_block)
    if field == "用例ID":
        return len(re.findall(r"(?m)^\s*-\s+用例ID\s*:", case_block))
    if indent is None:
        return 0
    pattern = re.compile(r"(?m)^{indent}{field}\s*:".format(indent=re.escape(indent), field=re.escape(field)))
    return len(pattern.findall(case_block))


def list_scalar_values(case_block: str, field: str) -> list[str]:
    field_block = top_level_field_block(case_block, field)
    if not field_block:
        return []
    values = []
    for line in field_block.splitlines()[1:]:
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        item = stripped[2:].strip()
        if ":" in item:
            continue
        value = normalized_scalar(item)
        if value:
            values.append(value)
    return values


def nested_scalar_values(case_block: str, field: str, nested_field: str) -> list[str]:
    field_block = top_level_field_block(case_block, field)
    if not field_block:
        return []
    pattern = re.compile(r"(?m)^\s*(?:-\s+)?{nested_field}\s*:\s*(.*?)\s*$".format(nested_field=re.escape(nested_field)))
    return [normalized_scalar(match.group(1).strip()) for match in pattern.finditer(field_block)]


def block_has_meaningful_leaf_values(field_block: str | None, ignored_keys: tuple[str, ...] = ()) -> bool:
    if field_block is None:
        return False
    for line in field_block.splitlines()[1:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            item = stripped[2:].strip()
            if ":" in item:
                key, value = item.split(":", 1)
                if key.strip() in ignored_keys:
                    continue
                if is_meaningful_scalar(value):
                    return True
            elif is_meaningful_scalar(item):
                return True
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        if key.strip() in ignored_keys:
            continue
        if is_meaningful_scalar(value):
            return True
    return False


def require_named_scalar(case_block: str, field: str, nested_field: str, errors: list[str], case_label: str) -> None:
    field_block = top_level_field_block(case_block, field)
    pattern = re.compile(r"(?m)^\s*(?:-\s+)?{nested_field}\s*:\s*(.*?)\s*$".format(nested_field=re.escape(nested_field)))
    match = pattern.search(field_block or "")
    value = match.group(1).strip() if match else None
    require(is_meaningful_scalar(value), errors, f"{case_label} 的 {field}.{nested_field} 不能为空")


def named_scalar(case_block: str, field: str, nested_field: str) -> str:
    field_block = top_level_field_block(case_block, field)
    pattern = re.compile(r"(?m)^\s*(?:-\s+)?{nested_field}\s*:\s*(.*?)\s*$".format(nested_field=re.escape(nested_field)))
    match = pattern.search(field_block or "")
    return normalized_scalar(match.group(1)) if match else ""


def confidence_band(score: float) -> str:
    if score < 0.60:
        return "insufficient"
    if score < 0.70:
        return "contract_confirmed"
    if score < 0.80:
        return "request_confirmed"
    if score < 0.90:
        return "scenario_confirmed"
    return "runtime_closed"


def confidence_level(score: float) -> str:
    if score < 0.70:
        return "low"
    if score < 0.90:
        return "medium"
    return "high"


def validate_executable_confidence(case_block: str, errors: list[str], case_label: str) -> None:
    score_text = normalized_scalar(top_level_scalar(case_block, "置信度分数"))
    try:
        score = float(score_text)
    except (TypeError, ValueError):
        errors.append(f"{case_label} 的 置信度分数 必须是 0 到 1 的数字")
        return
    if not 0.0 <= score <= 1.0:
        errors.append(f"{case_label} 的 置信度分数 超出 0 到 1：{score_text}")
        return
    if abs(score * 20 - round(score * 20)) > 1e-8:
        errors.append(f"{case_label} 的 置信度分数 必须按 0.05 量化：{score_text}")

    level = normalized_scalar(top_level_scalar(case_block, "置信度等级"))
    band = normalized_scalar(top_level_scalar(case_block, "置信度区间"))
    scope = normalized_scalar(top_level_scalar(case_block, "置信度范围"))
    relevance = normalized_scalar(top_level_scalar(case_block, "场景相关性"))
    require(level == confidence_level(score), errors, f"{case_label} 的 置信度等级 与分数不一致")
    require(band == confidence_band(score), errors, f"{case_label} 的 置信度区间 与分数不一致")
    require(scope in {"executable", "design_and_execution"}, errors, f"{case_label} 的 置信度范围 必须是 executable/design_and_execution")
    require(relevance in CONFIDENCE_RELEVANCE, errors, f"{case_label} 的 场景相关性 非法：{relevance}")

    weighted_total = 0.0
    for dimension, weight in CONFIDENCE_DIMENSION_WEIGHTS.items():
        value_text = named_scalar(case_block, "置信度维度", dimension)
        try:
            value = float(value_text)
        except (TypeError, ValueError):
            errors.append(f"{case_label} 的 置信度维度.{dimension} 必须是 0 到 1 的数字")
            return
        if not 0.0 <= value <= 1.0:
            errors.append(f"{case_label} 的 置信度维度.{dimension} 超出 0 到 1")
            return
        weighted_total += value * weight

    cap_block = top_level_field_block(case_block, "置信度硬上限原因") or ""
    declared_cap_tokens = set(re.findall(r"\b[A-Z][A-Z0-9_]+\b", cap_block))
    unknown_cap_tokens = declared_cap_tokens - set(CONFIDENCE_CAPS)
    require(not unknown_cap_tokens, errors, f"{case_label} 的 置信度硬上限原因 包含未知原因：{sorted(unknown_cap_tokens)}")
    cap_reasons = [reason for reason in CONFIDENCE_CAPS if reason in cap_block]
    reason_block = top_level_field_block(case_block, "置信度原因码") or ""
    for reason in cap_reasons:
        require(reason in reason_block, errors, f"{case_label} 的硬上限原因未同步到 置信度原因码：{reason}")
    active_caps = [CONFIDENCE_CAPS[reason] for reason in cap_reasons]
    capped_score = min([weighted_total, *active_caps]) if active_caps else weighted_total
    expected_score = int((capped_score + 1e-9) * 20) / 20
    require(abs(score - expected_score) <= 1e-8, errors, f"{case_label} 的 置信度分数不可重算：期望 {expected_score:g}")
    if score >= 0.90:
        require("RUNTIME_NOT_VERIFIED" not in cap_reasons, errors, f"{case_label} 的 runtime_closed 仍声明 RUNTIME_NOT_VERIFIED")


def require_block_meaningful(case_block: str, field: str, errors: list[str], case_label: str, ignored_keys: tuple[str, ...] = ()) -> None:
    field_block = top_level_field_block(case_block, field)
    require(block_has_meaningful_leaf_values(field_block, ignored_keys), errors, f"{case_label} 的 {field} 必须包含非空执行值或来源依据")


def validate_passed_case_content(case_block: str, errors: list[str], case_label: str) -> None:
    for field in NON_EMPTY_SCALAR_CASE_FIELDS:
        require(is_meaningful_scalar(top_level_scalar(case_block, field)), errors, f"{case_label} 的 {field} 不能为空")

    for field in CASE_FIELDS:
        count = top_level_field_count(case_block, field)
        require(count == 1, errors, f"{case_label} 的顶层字段 {field} 必须出现且只能出现一次")

    for nested_field in ("feature", "story", "severity"):
        require_named_scalar(case_block, "allure 标记", nested_field, errors, case_label)
    for nested_field in ("环境", "鉴权", "数据状态"):
        require_named_scalar(case_block, "前置条件", nested_field, errors, case_label)
    for nested_field in ("步骤ID", "步骤名称", "请求方式", "接口路径"):
        require_named_scalar(case_block, "执行步骤", nested_field, errors, case_label)
    for nested_field in ("http_status",):
        require_named_scalar(case_block, "预期响应", nested_field, errors, case_label)
    for nested_field in ("断言ID", "类型", "表达式", "期望", "来源依据"):
        require_named_scalar(case_block, "断言规则", nested_field, errors, case_label)
    for nested_field in ("变量名", "来源", "表达式"):
        require_named_scalar(case_block, "变量提取", nested_field, errors, case_label)
    for nested_field in ("变量名", "目标步骤", "目标位置"):
        require_named_scalar(case_block, "变量注入", nested_field, errors, case_label)
    flow_id = top_level_scalar(case_block, "链路flow_id")
    flow_step_no = top_level_scalar(case_block, "链路步骤序号")
    if is_meaningful_scalar(flow_id) or is_meaningful_scalar(flow_step_no):
        require(is_meaningful_scalar(flow_id), errors, f"{case_label} 声明链路步骤时 链路flow_id 不能为空")
        require(re.fullmatch(r"\d+", normalized_scalar(flow_step_no)) is not None, errors, f"{case_label} 的 链路步骤序号 必须是从 1 开始的数字")
        require_block_meaningful(case_block, "链路生产者/消费者", errors, case_label)
    for nested_field in ("client",):
        require_named_scalar(case_block, "可转 pytest 标记", nested_field, errors, case_label)
    for nested_field in ("设计级用例", "契约清单", "数据模型", "Apifox"):
        require_named_scalar(case_block, "来源依据", nested_field, errors, case_label)

    require_block_meaningful(case_block, "完整入参", errors, case_label)
    require_block_meaningful(case_block, "出参契约", errors, case_label, ignored_keys=("type",))
    require_block_meaningful(case_block, "预期响应", errors, case_label, ignored_keys=("http_status",))
    require_block_meaningful(case_block, "清理引用", errors, case_label)
    for nested_field in CONFIDENCE_DIMENSION_WEIGHTS:
        require_named_scalar(case_block, "置信度维度", nested_field, errors, case_label)
    require_block_meaningful(case_block, "置信度原因码", errors, case_label)
    require_block_meaningful(case_block, "置信度证据引用", errors, case_label)
    validate_executable_confidence(case_block, errors, case_label)


def require_yaml_field(case_block: str, field: str, errors: list[str], case_label: str) -> None:
    if field == "用例ID":
        pattern = CASE_FIELD_RE.pattern.format(field=re.escape(field))
        require(re.search(pattern, case_block) is not None, errors, f"{case_label} 缺少字段：{field}")
        return

    indent = top_level_indent(case_block)
    require(indent is not None, errors, f"{case_label} 缺少字段：用例ID")
    if indent is None:
        return
    pattern = re.compile(r"(?m)^{indent}{field}\s*:".format(indent=re.escape(indent), field=re.escape(field)))
    require(pattern.search(case_block) is not None, errors, f"{case_label} 缺少字段：{field}")


def validate_passed_cases(case_text: str, errors: list[str]) -> list[str]:
    case_blocks = extract_yaml_case_blocks(case_text)
    require(bool(case_blocks), errors, "PASSED 分支必须包含 yaml 代码块形式的执行级用例")
    require("生成状态：未生成" not in case_text, errors, "PASSED 分支不能包含未生成说明")

    for case_index, case_block in enumerate(case_blocks, start=1):
        case_label = f"第 {case_index} 个执行级用例"
        validate_yaml_like_syntax(case_block, errors, case_label)
        validate_case_values_closed(case_block, errors, case_label)
        for field in CASE_FIELDS:
            require_yaml_field(case_block, field, errors, case_label)
        request_method = top_level_scalar(case_block, "请求方式")
        priority = top_level_scalar(case_block, "用例优先级")
        require(request_method in REQUEST_METHODS, errors, f"{case_label} 的请求方式必须是 {'、'.join(REQUEST_METHODS)}")
        require(priority in PRIORITIES, errors, f"{case_label} 的用例优先级必须是 {'、'.join(PRIORITIES)}")
        validate_passed_case_content(case_block, errors, case_label)
    return case_blocks


def validate_non_passed_cases(case_text: str, stage_status: str, errors: list[str]) -> None:
    require("- 生成状态：未生成" in case_text, errors, "非 PASSED 分支必须声明生成状态：未生成")
    require(f"- 阶段状态：{stage_status}" in case_text, errors, "执行级接口用例集.md 的阶段状态必须与前置数据构造规则.md 一致")
    require(not extract_yaml_case_blocks(case_text), errors, "非 PASSED 分支不得包含执行级用例 yaml 块")
    expected_lines = [line.format(stage_status=stage_status) for line in NON_PASSED_CASE_LINES]
    actual_lines = [line.strip() for line in case_text.splitlines() if line.strip()]
    require(actual_lines == expected_lines, errors, "非 PASSED 分支必须只包含标题、阶段状态、生成状态和原因")


def validate_passed_precheck(rules_text: str, errors: list[str]) -> None:
    for item in PASSED_PRECHECK_ITEMS:
        require_line_value(rules_text, item, "通过", errors, f"PASSED 分支必须声明前置校验通过：{item}")


def validate_passed_script_gate(rules_text: str, errors: list[str]) -> None:
    for item in SCRIPT_GATE_ITEMS:
        require_line_value(rules_text, item, "通过", errors, f"PASSED 分支必须声明脚本生成准出门禁通过：{item}")
    require_line_value(
        rules_text,
        "允许外部补充项",
        "环境配置、pytest 工程规范、allure 标注规范",
        errors,
        "PASSED 分支必须声明唯一允许外部补充项：环境配置、pytest 工程规范、allure 标注规范",
    )
    require_line_value(rules_text, "是否可依据产物生成完整测试脚本", "是", errors, "PASSED 分支必须声明是否可依据产物生成完整测试脚本：是")


def validate_passed_rule_tables(rules_text: str, errors: list[str]) -> None:
    for section in PASSED_REQUIRED_TABLE_SECTIONS:
        rows = table_data_rows(section_body(rules_text, section))
        require(bool(rows), errors, f"PASSED 分支的 {section} 必须至少包含一条有效数据")
        validate_table_values(section, rows, errors)
    validate_table_values("缺失数据与待确认项", table_data_rows(section_body(rules_text, "缺失数据与待确认项")), errors)
    validate_table_values("脚本生成准出门禁", table_data_rows(section_body(rules_text, "脚本生成准出门禁")), errors)


def validate_passed_cross_references(case_blocks: list[str], rules_text: str, errors: list[str]) -> None:
    precondition_body = section_body(rules_text, "前置数据构造规则")
    variable_body = section_body(rules_text, "变量提取与注入规则")
    cleanup_body = section_body(rules_text, "清理策略")

    for case_index, case_block in enumerate(case_blocks, start=1):
        case_label = f"第 {case_index} 个执行级用例"
        case_id = top_level_scalar(case_block, "用例ID")
        if case_id:
            require(case_id in precondition_body, errors, f"{case_label} 的用例ID 未在前置数据构造规则中闭合：{case_id}")
            require(case_id in cleanup_body, errors, f"{case_label} 的用例ID 未在清理策略中闭合：{case_id}")

        for cleanup_id in list_scalar_values(case_block, "清理引用"):
            require(cleanup_id in cleanup_body, errors, f"{case_label} 的清理引用未在清理策略中闭合：{cleanup_id}")

        variable_names = set(nested_scalar_values(case_block, "变量提取", "变量名")) | set(nested_scalar_values(case_block, "变量注入", "变量名"))
        for variable_name in sorted(variable_names):
            require(variable_name in variable_body, errors, f"{case_label} 的变量未在变量提取与注入规则中闭合：{variable_name}")


def validate_non_passed_blockers(rules_text: str, errors: list[str]) -> None:
    for section in RULE_SECTIONS:
        validate_table_placeholders(section, table_data_rows(section_body(rules_text, section)), errors)

    missing_rows = table_data_rows(section_body(rules_text, "缺失数据与待确认项"))
    require(bool(missing_rows), errors, "非 PASSED 分支必须在缺失数据与待确认项列出至少一个阻塞项")
    for row_index, row in enumerate(missing_rows, start=1):
        require(len(row) >= 6, errors, f"缺失数据与待确认项 第 {row_index} 条数据必须包含编号、缺失/待确认内容、涉及用例/接口、阻塞级别、需要提供的数据、建议来源")
        for cell in row[:6]:
            require(is_closed_scalar(cell), errors, f"缺失数据与待确认项 第 {row_index} 条数据存在空值或未闭合模板占位值：{cell}")



def sidecar_stage_status_for(stage_status: str) -> str:
    if stage_status == "PASSED":
        return "passed"
    if stage_status in {"BLOCKED_NEED_EXECUTION_INPUT", "BLOCKED_NEED_CHAIN_FLOW_EVIDENCE"}:
        return "blocked"
    return "failed"


def validate_stage_status_sidecar(text: str, stage_status: str, errors: list[str]) -> None:
    label = "stage_status.yaml"
    require_yaml_top_level_keys(text, STAGE_STATUS_REQUIRED_KEYS, errors, label)
    schema_version = yaml_int_value(text, "schema_version", errors, label)
    if schema_version is not None and schema_version != 1:
        errors.append(f"{label} schema_version 不是 1：{schema_version}")
    stage = first_yaml_scalar(text, "stage")
    require(stage == "executable_interface_case_set", errors, f"{label} stage 不匹配：{stage}")
    status = first_yaml_scalar(text, "status")
    expected_status = sidecar_stage_status_for(stage_status)
    require(status == expected_status, errors, f"{label} status 与阶段状态不一致：{status} != {expected_status}")
    next_stage_allowed = first_yaml_scalar(text, "next_stage_allowed")
    if stage_status == "PASSED":
        require(is_yaml_true(next_stage_allowed), errors, f"{label} next_stage_allowed 不是 true：{next_stage_allowed}")
        require_yaml_empty_list(text, "blocking_issues", errors, label)
    else:
        require(not is_yaml_true(next_stage_allowed), errors, f"{label} 非 PASSED 时 next_stage_allowed 必须为 false：{next_stage_allowed}")


def validate_long_chain_coverage_matrix(
    text: str,
    stage_status: str,
    errors: list[str],
    required_flow_ids: set[str] | None = None,
) -> None:
    if stage_status != "PASSED":
        return
    label = "coverage_matrix.yaml"
    required_flow_ids = required_flow_ids or set()
    required_count_values = yaml_int_values(text, "required_chain_flow_count")
    required_count = required_count_values[0] if required_count_values else 0
    long_chain_declared = "long_chain_coverage_summary" in text or any(
        key in text
        for key, _ in CHAIN_COVERAGE_PAIRS
    )
    expected_count = len(required_flow_ids) if required_flow_ids else required_count
    if expected_count <= 0 and not long_chain_declared:
        return

    denominator_values = [
        value.strip().strip("\"'")
        for key in ("denominator_scope", "coverage_denominator", "coverage_scope")
        for value in yaml_scalar_values(text, key)
    ]
    if "long_chain_only" not in denominator_values:
        errors.append(f"{label} 必须声明长链路覆盖率独立计算：denominator_scope/coverage_denominator=long_chain_only")

    for total_key, covered_key in CHAIN_COVERAGE_PAIRS:
        total = yaml_int_value(text, total_key, errors, label)
        covered = yaml_int_value(text, covered_key, errors, label)
        if total is None or covered is None:
            continue
        if total <= 0:
            errors.append(f"{label} {total_key} 必须大于 0，不能把长链路覆盖率混入单接口覆盖率")
        if total != covered:
            errors.append(f"{label} 长链路覆盖计数不是 100%：{covered_key}/{total_key} = {covered}/{total}")
    for key in CHAIN_COVERAGE_MISSING_LISTS:
        require_yaml_empty_list(text, key, errors, label)
    require_yaml_empty_list(text, "missing_required_flow_ids", errors, label)

    required_count = yaml_int_value(text, "required_chain_flow_count", errors, label)
    if required_count is not None and expected_count > 0 and required_count != expected_count:
        errors.append(f"{label} required_chain_flow_count 与必测 flow 数不一致：{required_count} != {expected_count}")
    generated_count = yaml_int_value(text, "generated_executable_chain_case_count", errors, label)
    if generated_count is not None and expected_count > 0 and generated_count != expected_count:
        errors.append(
            f"{label} generated_executable_chain_case_count 与必测 flow 数不一致："
            f"{generated_count} != {expected_count}"
        )

    coverage_section = yaml_section(text, "coverage_items")
    coverage_types = set(yaml_scalar_values(coverage_section, "coverage_type"))
    for coverage_type in CHAIN_COVERAGE_TYPES:
        if coverage_type not in coverage_types:
            errors.append(f"{label} coverage_items 缺少长链路覆盖类型：{coverage_type}")
    for flow_id in sorted(required_flow_ids):
        if flow_id not in coverage_section:
            errors.append(f"{label} coverage_items 未列出上游必需 flow_id：{flow_id}")


def validate_coverage_matrix_sidecar(
    text: str,
    stage_status: str,
    errors: list[str],
    required_flow_ids: set[str] | None = None,
) -> None:
    label = "coverage_matrix.yaml"
    require_yaml_top_level_keys(text, COVERAGE_MATRIX_REQUIRED_KEYS, errors, label)
    schema_version = yaml_int_value(text, "schema_version", errors, label)
    if schema_version is not None and schema_version != 1:
        errors.append(f"{label} schema_version 不是 1：{schema_version}")
    stage = first_yaml_scalar(text, "stage")
    require(stage == "executable_interface_case_set", errors, f"{label} stage 不匹配：{stage}")
    if stage_status == "PASSED":
        for total_key, mapped_key in EXECUTABLE_COVERAGE_PAIRS:
            total = yaml_int_value(text, total_key, errors, label)
            mapped = yaml_int_value(text, mapped_key, errors, label)
            if total is not None and mapped is not None:
                require(total == mapped, errors, f"{label} 覆盖计数不是 100%：{mapped_key}/{total_key} = {mapped}/{total}")
        for key in EXECUTABLE_MISSING_LISTS:
            require_yaml_empty_list(text, key, errors, label)
        validate_long_chain_coverage_matrix(text, stage_status, errors, required_flow_ids)


def validate_execution_fact_sources_sidecar(text: str, stage_status: str, errors: list[str]) -> None:
    label = "execution_fact_sources.yaml"
    require_yaml_top_level_keys(text, EXECUTION_FACT_SOURCE_REQUIRED_KEYS, errors, label)
    schema_version = yaml_int_value(text, "schema_version", errors, label)
    if schema_version is not None and schema_version != 1:
        errors.append(f"{label} schema_version 不是 1：{schema_version}")
    stage = first_yaml_scalar(text, "stage")
    require(stage == "executable_interface_case_set", errors, f"{label} stage 不匹配：{stage}")
    status = first_yaml_scalar(text, "status")
    expected_status = sidecar_stage_status_for(stage_status)
    require(status == expected_status, errors, f"{label} status 与阶段状态不一致：{status} != {expected_status}")
    for required_marker in ("environment_reference", "authentication_account"):
        require(required_marker in text, errors, f"{label} 缺少必填人工输入状态：{required_marker}")
    for fact_type in ("token_rule", "test_data_rule", "variable_link", "chain_flow", "assertion_rule", "cleanup_strategy"):
        require(fact_type in text, errors, f"{label} 缺少执行事实类型索引：{fact_type}")
    fact_items = extract_fact_source_items(text)
    if stage_status == "PASSED" and fact_sources_need_login_entry_rule(fact_items):
        require(
            has_confirmed_login_entry_rule(fact_items),
            errors,
            f"{label} 账号型长链路缺少 confirmed 且 source_ref 有效的 login_entry_rule",
        )
    database_backed_setup_or_cleanup = any(
        marker in text for marker in ("source_type: data_model", "source_type: \"data_model\"", "数据模型", "database", "SQL", "sql")
    )
    precondition_seeded_values = any(
        marker in text
        for marker in (
            "fact_type: seed_value",
            "source_type: precondition_api_response",
            "source_type: db_seed_evidence",
        )
    )
    if stage_status == "PASSED" and database_backed_setup_or_cleanup:
        for fact_type in ("relationship_graph", "ownership_key", "seed_scope_guard"):
            require(fact_type in text, errors, f"{label} 数据库铺数/清理缺少执行事实类型索引：{fact_type}")
    if stage_status == "PASSED" and precondition_seeded_values:
        require("seed_scope_guard" in text, errors, f"{label} 前置造数缺少执行事实类型索引：seed_scope_guard")
    if stage_status == "PASSED":
        for key in ("missing_required_facts", "conflict_facts", "blocking_issues"):
            require_yaml_empty_list(text, key, errors, label)


def validate_apifox_evidence_sidecar(text: str, stage_status: str, errors: list[str]) -> None:
    label = "apifox_evidence_index.yaml"
    require_yaml_top_level_keys(text, APIFOX_EVIDENCE_REQUIRED_KEYS, errors, label)
    schema_version = yaml_int_value(text, "schema_version", errors, label)
    if schema_version is not None and schema_version != 1:
        errors.append(f"{label} schema_version 不是 1：{schema_version}")
    stage = first_yaml_scalar(text, "stage")
    require(stage == "executable_interface_case_set", errors, f"{label} stage 不匹配：{stage}")
    status = first_yaml_scalar(text, "status")
    require(status in {"passed", "partial", "blocked", "failed"}, errors, f"{label} status 非法：{status}")
    for level in APIFOX_EVIDENCE_LEVELS:
        require(level in text, errors, f"{label} 缺少 Apifox 证据等级或处理策略：{level}")
    require("结构化契约" in text or "structured contract" in text, errors, f"{label} 缺少结构化契约冲突优先级")
    if stage_status == "PASSED":
        require(status == "passed", errors, f"{label} PASSED 分支 status 必须为 passed：{status}")
        require_yaml_empty_list(text, "conflict_items", errors, label)


def validate_sidecars(output_dir: Path, stage_status: str, errors: list[str]) -> str:
    sidecar_texts: dict[str, str] = {}
    for filename in REQUIRED_SIDECARS:
        path = output_dir / filename
        require(path.is_file(), errors, f"缺少结构化 sidecar：{filename}")
        if path.is_file():
            try:
                sidecar_texts[filename] = read_text(path)
            except ValueError as exc:
                errors.append(str(exc))
    if not all(filename in sidecar_texts for filename in REQUIRED_SIDECARS):
        return ""
    fact_text = sidecar_texts["execution_fact_sources.yaml"]
    required_flow_ids = required_chain_flow_ids_from_context(output_dir, fact_text)
    validate_stage_status_sidecar(sidecar_texts["stage_status.yaml"], stage_status, errors)
    validate_coverage_matrix_sidecar(sidecar_texts["coverage_matrix.yaml"], stage_status, errors, required_flow_ids)
    validate_execution_fact_sources_sidecar(fact_text, stage_status, errors)
    validate_runtime_evidence_sidecars(output_dir, fact_text, errors)
    apifox_path = output_dir / OPTIONAL_APIFOX_SIDECAR
    apifox_required = "apifox_mcp" in fact_text or apifox_path.is_file()
    if apifox_required:
        require(apifox_path.is_file(), errors, f"执行事实来源包含 apifox_mcp 时缺少结构化 sidecar：{OPTIONAL_APIFOX_SIDECAR}")
        if apifox_path.is_file():
            try:
                validate_apifox_evidence_sidecar(read_text(apifox_path), stage_status, errors)
            except ValueError as exc:
                errors.append(str(exc))
    return fact_text


def validate_output_dir(output_dir: Path) -> list[str]:
    errors: list[str] = []
    require(output_dir.exists(), errors, f"输出目录不存在：{output_dir}")
    require(output_dir.is_dir(), errors, f"输出路径不是目录：{output_dir}")
    if errors:
        return errors

    output_entries = sorted(path.name for path in output_dir.iterdir())
    is_sharded_output = SHARD_INDEX_FILE in output_entries or SHARD_DIR in output_entries
    allowed_entries = set(SHARDED_OUTPUT_ENTRIES if is_sharded_output else BASE_OUTPUT_ENTRIES)
    if OPTIONAL_APIFOX_SIDECAR in output_entries:
        allowed_entries.add(OPTIONAL_APIFOX_SIDECAR)
    if is_sharded_output:
        require(set(output_entries) == allowed_entries, errors, f"分片输出目录必须只包含根产物、sidecar 和分片产物：{', '.join(sorted(allowed_entries))}")
        require((output_dir / SHARD_INDEX_FILE).is_file(), errors, f"分片输出缺少分片索引：{SHARD_INDEX_FILE}")
        require((output_dir / SHARD_DIR).is_dir(), errors, f"分片输出缺少分片目录：{SHARD_DIR}")
    else:
        require(set(output_entries) == allowed_entries, errors, f"输出目录必须只包含阶段产物和 sidecar：{', '.join(sorted(allowed_entries))}")
    for filename in REQUIRED_FILES:
        require((output_dir / filename).is_file(), errors, f"缺少阶段产物：{filename}")
    if errors:
        return errors

    try:
        case_text = read_text(output_dir / "执行级接口用例集.md")
        rules_text = read_text(output_dir / "前置数据构造规则.md")
        shard_index_text = read_text(output_dir / SHARD_INDEX_FILE) if is_sharded_output else ""
    except ValueError as exc:
        errors.append(str(exc))
        return errors

    require(case_text.lstrip().startswith("## 执行级接口用例集"), errors, "执行级接口用例集.md 必须以 ## 执行级接口用例集 开头")
    require_sections(rules_text, RULE_SECTIONS, "前置数据构造规则.md", errors)

    stage_status = detect_stage_status(rules_text)
    require(stage_status is not None, errors, "前置数据构造规则.md 必须声明阶段状态")
    require(stage_status in STAGE_STATUSES, errors, f"前置数据构造规则.md 阶段状态非法：{stage_status}")
    stage_statuses = detect_all_stage_statuses(rules_text)
    require(all(status == stage_status for status in stage_statuses), errors, "前置数据构造规则.md 内所有阶段状态必须一致")
    validate_rules_line_values_closed(rules_text, errors)
    if errors:
        return errors

    validate_sidecars(output_dir, stage_status, errors)
    if errors:
        return errors

    if stage_status == "PASSED":
        require_line_value(rules_text, "是否允许进入 pytest+allure 代码生成", "是", errors, "PASSED 分支必须允许进入 pytest+allure 代码生成")
        require_line_value(rules_text, "是否准出", "是", errors, "PASSED 分支必须声明是否准出：是")
        validate_passed_precheck(rules_text, errors)
        validate_passed_script_gate(rules_text, errors)
        validate_passed_rule_tables(rules_text, errors)
        if is_sharded_output:
            shards = read_shard_index(shard_index_text, errors)
            shard_count = len(shards)
            validate_sharded_entry(case_text, shard_count, errors)
            sharded_case_text = read_sharded_case_text(output_dir, shard_index_text, errors, shards)
            case_blocks = validate_passed_cases(sharded_case_text, errors)
        else:
            case_blocks = validate_passed_cases(case_text, errors)
        validate_passed_cross_references(case_blocks, rules_text, errors)
    else:
        require(not is_sharded_output, errors, "非 PASSED 分支不得生成分片索引或分片目录")
        require_line_value(rules_text, "是否允许进入 pytest+allure 代码生成", "否", errors, "非 PASSED 分支必须禁止进入 pytest+allure 代码生成")
        require_line_value(rules_text, "是否准出", "否", errors, "非 PASSED 分支必须声明是否准出：否")
        validate_non_passed_cases(case_text, stage_status, errors)
        validate_non_passed_blockers(rules_text, errors)

    errors.extend(validate_runtime_business_dependencies(output_dir))

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 executable-interface-case-set 阶段产物")
    parser.add_argument("output_dir", help="包含执行级 Markdown 产物和结构化 sidecar 的输出目录")
    args = parser.parse_args()

    errors = validate_output_dir(Path(args.output_dir))
    if errors:
        print("校验结果：不通过")
        for index, error in enumerate(errors, start=1):
            print(f"{index}. {error}")
        return 1

    print("校验结果：通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
