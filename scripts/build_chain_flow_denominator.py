#!/usr/bin/env python3
"""从入口结构化证据生成长链路闭环必测分母。"""

from __future__ import annotations

import argparse
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


BUSINESS_SCENARIO_MAP = "business_scenario_map.yaml"
BUSINESS_CHAIN_CANDIDATE_INVENTORY = "business_chain_candidate_inventory.yaml"
REQUIRED_CHAIN_FLOWS = "required_chain_flows.yaml"
CHAIN_FLOW_CANDIDATE_AUDIT = "chain_flow_candidate_audit.yaml"
CHAIN_FLOW_ALIGNMENT = "chain_flow_alignment.yaml"
CHAIN_EXECUTION_READINESS_RECONCILIATION = "chain_execution_readiness_reconciliation.yaml"
READINESS_CAPABILITIES = {
    "write_restore",
    "read_only_verified",
    "create_delete_zero_residue",
    "isolated_ownership",
    "sandbox_mock_callback",
    "state_observation_verified",
}
KNOWN_EXECUTION_FACT_PATHS = (
    "04-runtime-evidence/runtime_stage_status.yaml",
    "04-runtime-evidence/runtime_evidence.yaml",
    "04-runtime-evidence/runtime_value_catalog.yaml",
    "00-inputs/execution-readiness/long_chain_missing_value_fields.yaml",
    "05-executable-interface-case-set/long_chain_missing_value_fields.yaml",
    "05-executable-interface-case-set/execution_fact_sources.yaml",
)
ALLOWED_CLASSIFICATIONS = {
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
INVENTORY_TYPES = (
    "business_long_chain_ready",
    "business_long_chain_need_execution_evidence",
    "short_state_transition",
    "single_interface_mutation",
    "readonly",
    "external_or_callback",
    "missing_evidence_candidate",
)
YAML_SCALAR_RE = re.compile(r"^\s*(?:-\s*)?([A-Za-z0-9_]+)\s*:\s*(.*?)\s*$")
MUTATING_STEP_RE = re.compile(r"^\s*(?:POST|PUT|PATCH|DELETE)\b", re.IGNORECASE)
READ_STEP_RE = re.compile(r"^\s*(?:GET|HEAD|OPTIONS)\b", re.IGNORECASE)
INTERFACE_LIKE_RE = re.compile(r"(?:\b(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b\s*/|/|接口)", re.IGNORECASE)
PATH_BUCKET_PATTERNS = (
    re.compile(r"\b(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b\s*/", re.IGNORECASE),
    re.compile(r"(?:^|[\s\"'：:])/?(?:api|app|admin|internal|openapi|v\d+)(?:/|$)", re.IGNORECASE),
    re.compile(r"(?:接口|路径|URL|uri|controller|模块|包名|前缀).{0,16}(?:聚合|分组|串联|穷举|正向测试|反向测试|异常测试)", re.IGNORECASE),
    re.compile(r"(?:调用|创建|查询|更新|删除).{0,8}接口(?:正向|反向|异常|边界)?测试", re.IGNORECASE),
    re.compile(r"(?:api/v\d+|/app|/internal).{0,20}(?:资源|接口|路径|前缀).{0,20}(?:链路|校验|测试)", re.IGNORECASE),
)
GENERIC_BUSINESS_LABELS = {
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


@dataclass
class Candidate:
    candidate_id: str
    flow_id: str
    source_route: str
    scenario_id: str
    business_domain: str
    scenario_name: str
    executing_role: str
    business_description: str
    chain_type: str
    flow_generation_required: bool
    ordered_step_count: int
    pre_action_interface: str
    observable_change_type: str
    observable_change_evidence: str
    verification_interface: str
    link_keys: list[str]
    steps: list[str]
    related_interfaces: list[str]
    business_chain: list[str]
    state_chain: list[str]
    blockers: list[str]
    evidence_refs: list[str]
    inferred_fields: list[str]
    discovery_signals: list[str]
    candidate_inventory_type: str
    missing_evidence: list[str]
    classification: str
    reason: str
    downstream_target: str


def read_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if "\ufffd" in text:
        raise ValueError(f"{path} 存在疑似中文乱码字符")
    if not text.strip():
        raise ValueError(f"{path} 内容为空")
    return text


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip().strip("\"'")


def as_bool(value: Any) -> bool:
    return as_text(value).lower() in {"true", "yes", "1", "是", "需要"}


def as_int(value: Any) -> int:
    try:
        return int(as_text(value))
    except ValueError:
        return 0


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if as_text(value) in {"", "[]", "无", "未知", "待确认", "待补充", "TBD"}:
        return []
    return [value]


def text_list(value: Any) -> list[str]:
    result: list[str] = []
    for item in as_list(value):
        if isinstance(item, dict):
            text = as_text(item.get("interface") or item.get("source_ref") or item.get("value"))
        else:
            text = as_text(item)
        if text and text not in {"[]", "无", "未知", "待确认", "待补充", "TBD"}:
            result.append(text)
    return result


def nested_text(item: dict[str, Any], parent_key: str, child_key: str) -> str:
    parent = item.get(parent_key)
    if isinstance(parent, dict):
        return as_text(parent.get(child_key))
    return ""


def ordered_step_interfaces_from_item(item: dict[str, Any]) -> list[str]:
    steps = []
    for step in as_list(item.get("ordered_steps")):
        if isinstance(step, dict):
            interface = as_text(step.get("interface"))
            if interface:
                steps.append(interface)
        else:
            text = as_text(step)
            if text:
                steps.append(text)
    if steps:
        return steps
    return text_list(item.get("steps"))


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(read_text(path))
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_non_empty_text(value: Any, field: str, errors: list[str]) -> str:
    text = as_text(value)
    if not text:
        errors.append(f"执行就绪重算缺少有效字段：{field}")
    return text


def require_non_empty_text_list(value: Any, field: str, errors: list[str]) -> list[str]:
    values = text_list(value)
    if not values:
        errors.append(f"执行就绪重算缺少非空列表：{field}")
    return values


def yaml_section(text: str, key: str) -> str:
    pattern = re.compile(rf"(?m)^({re.escape(key)}\s*:\s*)$")
    match = pattern.search(text)
    if not match:
        return ""
    start = match.end()
    next_match = re.search(r"(?m)^[A-Za-z0-9_]+\s*:", text[start:])
    end = start + next_match.start() if next_match else len(text)
    return text[start:end]


def scenario_blocks(text: str) -> list[str]:
    section = yaml_section(text, "scenario_items")
    starts = list(re.finditer(r"(?m)^\s*-\s+scenario_id\s*:", section))
    blocks: list[str] = []
    for index, start in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(section)
        blocks.append(section[start.start():end])
    return blocks


def scalar_values(text: str, key: str) -> list[str]:
    values: list[str] = []
    for line in text.splitlines():
        match = YAML_SCALAR_RE.match(line)
        if match and match.group(1) == key:
            values.append(match.group(2).strip().strip("\"'"))
    return values


def first_scalar(text: str, key: str) -> str:
    values = scalar_values(text, key)
    return values[0] if values else ""


def parse_inline_list(value: str) -> list[str]:
    normalized = value.strip().strip("\"'")
    if not normalized.startswith("[") or not normalized.endswith("]"):
        return []
    inner = normalized[1:-1].strip()
    if not inner:
        return []
    return [item.strip().strip("\"'") for item in inner.split(",") if item.strip().strip("\"'")]


def list_values(block: str, key: str) -> list[str]:
    values: list[str] = []
    lines = block.splitlines()
    for index, line in enumerate(lines):
        match = re.match(rf"^(\s*)(?:-\s*)?{re.escape(key)}\s*:\s*(.*?)\s*$", line)
        if not match:
            continue
        indent = len(match.group(1))
        inline_value = match.group(2).strip()
        inline_items = parse_inline_list(inline_value)
        if inline_items:
            values.extend(inline_items)
            continue
        if inline_value and inline_value != "[]":
            values.append(inline_value.strip().strip("\"'"))
            continue
        for next_line in lines[index + 1:]:
            if next_line.strip():
                next_indent = len(next_line) - len(next_line.lstrip(" "))
                if next_indent <= indent:
                    break
            item_match = re.match(r"^\s*-\s*(.*?)\s*$", next_line)
            if item_match and item_match.group(1).strip():
                values.append(item_match.group(1).strip().strip("\"'"))
    return [value for value in values if value and value not in {"[]", "无", "未知", "待确认", "待补充", "TBD"}]


def nested_block(block: str, parent_key: str) -> str:
    lines = block.splitlines()
    for index, line in enumerate(lines):
        match = re.match(rf"^(\s*){re.escape(parent_key)}\s*:\s*(.*?)\s*$", line)
        if not match:
            continue
        parent_indent = len(match.group(1))
        nested_lines: list[str] = []
        for nested_line in lines[index + 1:]:
            if nested_line.strip():
                nested_indent = len(nested_line) - len(nested_line.lstrip(" "))
                if nested_indent <= parent_indent:
                    break
            nested_lines.append(nested_line)
        return "\n".join(nested_lines)
    return ""


def nested_scalar(block: str, parent_key: str, child_key: str) -> str:
    return first_scalar(nested_block(block, parent_key), child_key)


def ordered_step_interfaces(block: str) -> list[str]:
    ordered_steps = nested_block(block, "ordered_steps")
    interfaces = scalar_values(ordered_steps, "interface")
    if interfaces:
        return interfaces
    return list_values(block, "steps")


def bool_scalar(value: str) -> bool:
    return value.strip().strip("\"'").lower() in {"true", "yes", "1", "是", "需要"}


def int_scalar(value: str) -> int:
    try:
        return int(value.strip().strip("\"'"))
    except ValueError:
        return 0


def has_state_change(candidate: Candidate) -> bool:
    text = " ".join(
        candidate.state_chain
        + candidate.related_interfaces
        + candidate.business_chain
        + candidate.steps
        + [candidate.business_description, candidate.scenario_name]
    ).upper()
    return any(signal in text for signal in (
        "CREATE",
        "UPDATE",
        "DELETE",
        "INSERT",
        "新增",
        "创建",
        "提交",
        "领取",
        "申请",
        "认证",
        "关注",
        "点赞",
        "评论",
        "预约",
        "加入",
        "退出",
        "开通",
        "关闭",
        "购买",
        "兑换",
        "收藏",
        "绑定",
        "撤销",
        "解除",
        "删除",
        "修改",
        "变更",
        "回调",
        "审核",
        "支付",
        "提现",
        "充值",
        "发布",
        "发送",
        "上传",
        "拉黑",
    ))


def has_read_only_signal(candidate: Candidate) -> bool:
    text = " ".join(
        candidate.state_chain
        + candidate.related_interfaces
        + candidate.business_chain
        + candidate.steps
        + [candidate.business_description, candidate.scenario_name]
    ).upper()
    if not text.strip() or has_state_change(candidate):
        return False
    interfaces = " ".join(candidate.related_interfaces + candidate.steps).upper()
    if re.search(r"\b(POST|PUT|PATCH|DELETE)\b", interfaces):
        return False
    if candidate.state_chain and all(signal in {"READ", "HTTP_200"} for signal in candidate.state_chain):
        return True
    return any(signal in text for signal in ("GET ", "HEAD ", "OPTIONS ", "READ", "查询", "列表", "详情", "读取", "搜索", "统计", "配置", "状态", "浏览"))


def has_external_signal(candidate: Candidate) -> bool:
    text = " ".join(
        [
            candidate.executing_role,
            candidate.business_domain,
            candidate.scenario_name,
            candidate.business_description,
            " ".join(candidate.related_interfaces + candidate.business_chain + candidate.steps),
        ]
    ).lower()
    return any(signal.lower() in text for signal in ("第三方", "回调", "callback", "webhook", "tencent", "apple", "google", "支付验签", "沙箱", "系统任务"))


def normalize_label(value: str) -> str:
    return value.strip().strip("\"'").strip()


def looks_like_path_bucket_candidate(candidate: Candidate) -> bool:
    label_text = " ".join(
        normalize_label(value)
        for value in (
            candidate.business_domain,
            candidate.scenario_name,
        )
        if value
    )
    compact = re.sub(r"\s+", "", label_text)
    if compact in GENERIC_BUSINESS_LABELS:
        return True
    if any(pattern.search(label_text) for pattern in PATH_BUCKET_PATTERNS):
        return True
    description = normalize_label(candidate.business_description)
    return any(pattern.search(description) for pattern in PATH_BUCKET_PATTERNS[2:])


def step_is_interface_like(step: str) -> bool:
    return bool(INTERFACE_LIKE_RE.search(step))


def step_has_mutation_signal(step: str) -> bool:
    text = step.upper()
    return bool(MUTATING_STEP_RE.search(step)) or any(
        signal in text
        for signal in (
            "CREATE",
            "UPDATE",
            "DELETE",
            "INSERT",
            "新增",
            "创建",
            "提交",
            "领取",
            "申请",
            "认证",
            "关注",
            "点赞",
            "评论",
            "预约",
            "加入",
            "退出",
            "开通",
            "关闭",
            "购买",
            "兑换",
            "收藏",
            "绑定",
            "撤销",
            "解除",
            "删除",
            "修改",
            "变更",
            "回调",
            "审核",
            "支付",
            "提现",
            "充值",
            "发布",
            "发送",
            "上传",
            "拉黑",
        )
    )


def step_has_read_signal(step: str) -> bool:
    text = step.upper()
    return bool(READ_STEP_RE.search(step)) or any(
        signal in text for signal in ("READ", "查询", "列表", "详情", "读取", "搜索", "统计", "配置", "状态", "浏览")
    )


def first_mutating_step(steps: list[str]) -> str:
    for step in steps:
        if step_is_interface_like(step) and step_has_mutation_signal(step):
            return step
    return ""


def last_read_step(steps: list[str]) -> str:
    for step in reversed(steps):
        if step_is_interface_like(step) and step_has_read_signal(step):
            return step
    return ""


def infer_candidate_fields(candidate: Candidate) -> list[str]:
    inferred_fields: list[str] = []
    if not candidate.pre_action_interface:
        inferred_pre_action = first_mutating_step(candidate.steps)
        if inferred_pre_action:
            candidate.pre_action_interface = inferred_pre_action
            inferred_fields.append("pre_action_interface_from_steps")
    if not candidate.verification_interface:
        inferred_verification = last_read_step(candidate.steps)
        if inferred_verification and inferred_verification != candidate.pre_action_interface:
            candidate.verification_interface = inferred_verification
            inferred_fields.append("verification_interface_from_steps")
    return inferred_fields


def discovery_signals_for(candidate: Candidate) -> list[str]:
    signals: list[str] = []
    if candidate.business_domain:
        signals.append("business_domain_evidenced")
    if candidate.executing_role:
        signals.append("actor_evidenced")
    if candidate.business_description:
        signals.append("business_goal_evidenced")
    if candidate.steps:
        signals.append("ordered_steps_evidenced")
    if len(candidate.steps) >= 3 or candidate.ordered_step_count >= 5:
        signals.append("multi_step_business_chain")
    if candidate.chain_type == "e2e_flow_candidate" or candidate.flow_generation_required:
        signals.append("e2e_candidate_signal")
    if first_mutating_step(candidate.steps) or candidate.pre_action_interface:
        signals.append("pre_action_signal")
    if candidate.observable_change_type or candidate.observable_change_evidence:
        signals.append("observable_change_signal")
    if last_read_step(candidate.steps) or candidate.verification_interface:
        signals.append("verification_signal")
    if candidate.link_keys:
        signals.append("link_key_signal")
    if has_state_change(candidate):
        signals.append("state_change_signal")
    if has_external_signal(candidate):
        signals.append("external_or_callback_signal")
    if has_read_only_signal(candidate):
        signals.append("readonly_signal")
    return sorted(set(signals))


def missing_evidence_for(candidate: Candidate) -> list[str]:
    missing: list[str] = []
    if not candidate.pre_action_interface:
        missing.append("pre_action_interface")
    if not candidate.observable_change_type:
        missing.append("observable_change_type")
    if not candidate.observable_change_evidence:
        missing.append("observable_change_evidence")
    if not candidate.verification_interface:
        missing.append("verification_interface")
    if not candidate.link_keys:
        missing.append("link_keys")
    if not candidate.steps:
        missing.append("ordered_steps")
    if not candidate.evidence_refs:
        missing.append("evidence_refs")
    return missing


def inventory_type_for(classification: str) -> str:
    return {
        "included": "business_long_chain_ready",
        "design_long_chain_only": "business_long_chain_need_execution_evidence",
        "design_short_chain_state_transition": "short_state_transition",
        "single_interface_mutation": "single_interface_mutation",
        "single_interface_readonly": "readonly",
        "external_or_callback": "external_or_callback",
        "excluded_ready_by_policy": "business_long_chain_ready",
        "excluded_missing_verification": "missing_evidence_candidate",
        "excluded_missing_change_evidence": "missing_evidence_candidate",
        "excluded_missing_link_key": "missing_evidence_candidate",
        "excluded_readonly": "readonly",
    }.get(classification, "missing_evidence_candidate")


def downstream_target_for(classification: str) -> str:
    return {
        "included": "required_chain_flows",
        "design_long_chain_only": "business_long_chain_cases",
        "design_short_chain_state_transition": "design_short_chain_or_state_transition_case",
        "single_interface_mutation": "single_interface_design_and_executable_case",
        "single_interface_readonly": "single_interface_design_case",
        "external_or_callback": "external_dependency_or_callback_evidence",
        "excluded_ready_by_policy": "explicit_execution_ready_exclusion",
        "excluded_missing_verification": "blocked_need_verification_evidence",
        "excluded_missing_change_evidence": "blocked_need_change_evidence",
        "excluded_missing_link_key": "blocked_need_link_key_or_ordered_steps",
        "excluded_readonly": "not_required_as_closed_loop_flow",
    }.get(classification, "unclassified")


def classify_candidate(candidate: Candidate) -> tuple[str, str]:
    if looks_like_path_bucket_candidate(candidate):
        return (
            "excluded_missing_change_evidence",
            "疑似按路径前缀、接口集合、Controller 模块或接口测试标签聚合，不能证明真实业务场景变化；需先拆成真实业务链路后再评估闭环证据",
        )
    if has_external_signal(candidate) and not (
        candidate.pre_action_interface
        and candidate.observable_change_type
        and candidate.observable_change_evidence
        and candidate.verification_interface
        and candidate.link_keys
        and candidate.steps
        and candidate.evidence_refs
    ):
        return "external_or_callback", "涉及外部依赖、回调、内部任务或第三方动作；需沙箱、Mock、回调载荷或人工执行证据后才能进入执行闭环"
    if not candidate.pre_action_interface:
        if len(candidate.steps) == 2 or candidate.ordered_step_count == 2:
            return "design_short_chain_state_transition", "具备两步业务场景或状态流转语义，但不足以作为执行闭环必测长链路；保留为设计级短链路/状态流转用例"
        if candidate.chain_type == "e2e_flow_candidate" or candidate.flow_generation_required or len(candidate.steps) >= 3 or candidate.ordered_step_count >= 5:
            return "design_long_chain_only", "具备业务长链路/多步骤场景信号，但缺少显式前序变更动作证据；保留为设计级业务长链路并补充执行闭环证据"
        if has_state_change(candidate):
            return "single_interface_mutation", "单接口场景存在创建、更新、删除、状态变更或业务提交语义；进入单接口设计/执行覆盖，不标记为只读排除"
        if has_read_only_signal(candidate):
            return "single_interface_readonly", "单接口纯查询或配置读取场景；进入单接口设计覆盖，不进入执行闭环长链路分母"
        return "excluded_missing_change_evidence", "缺少前序写动作或变更动作证据，且无法证明为纯查询、短链路或单接口变更场景"
    if not candidate.observable_change_type or not candidate.observable_change_evidence:
        if len(candidate.steps) == 2 or candidate.ordered_step_count == 2:
            return "design_short_chain_state_transition", "两步业务状态流转缺少可观察变化证据；保留为设计级短链路并补充执行断言证据"
        if candidate.chain_type == "e2e_flow_candidate" or len(candidate.steps) >= 3 or candidate.ordered_step_count >= 5:
            return "design_long_chain_only", "具备业务长链路信号，但缺少可观察变化证据；保留为设计级长链路并补充 DB/状态/记录变化证据"
        return "excluded_missing_change_evidence", "缺少可观察状态/数据/金额/关系/权限/内容/任务变化证据"
    if not candidate.verification_interface:
        if len(candidate.steps) == 2 or candidate.ordered_step_count == 2:
            return "design_short_chain_state_transition", "两步业务状态流转缺少后序验证接口；保留为设计级短链路并补充验证证据"
        if candidate.chain_type == "e2e_flow_candidate" or len(candidate.steps) >= 3 or candidate.ordered_step_count >= 5:
            return "design_long_chain_only", "具备业务长链路信号，但缺少后序验证接口；保留为设计级长链路并补充验证步骤"
        return "excluded_missing_verification", "缺少后序查询或消费验证接口证据"
    if not candidate.link_keys:
        if len(candidate.steps) == 2 or candidate.ordered_step_count == 2:
            return "design_short_chain_state_transition", "两步业务状态流转缺少 link_keys；保留为设计级短链路并补充变量/状态关联证据"
        if candidate.chain_type == "e2e_flow_candidate" or len(candidate.steps) >= 3 or candidate.ordered_step_count >= 5:
            return "design_long_chain_only", "具备业务长链路信号，但缺少连接前后步骤的 link_keys；保留为设计级长链路并补充变量链路证据"
        return "excluded_missing_link_key", "缺少连接前序动作与后序验证的 link_keys"
    if not candidate.steps:
        return "excluded_missing_link_key", "缺少有序步骤证据，无法证明前序动作、状态变化和验证步骤的链路顺序"
    if not candidate.evidence_refs:
        return "excluded_missing_change_evidence", "缺少来源证据引用，无法证明闭环变化和验证事实来自源材料"
    return "included", "闭环证据完整，进入必测长链路分母"


def load_candidates(entry_dir: Path, source_route: str) -> list[Candidate]:
    map_path = entry_dir / BUSINESS_SCENARIO_MAP
    if not map_path.is_file():
        return []
    data = load_yaml_mapping(map_path)
    scenario_items = data.get("scenario_items")
    candidates: list[Candidate] = []
    if isinstance(scenario_items, list):
        iterable_items = [item for item in scenario_items if isinstance(item, dict)]
        for index, item in enumerate(iterable_items, start=1):
            scenario_id = as_text(item.get("scenario_id")) or f"SCENARIO-{source_route.upper()}-{index:03d}"
            flow_id = as_text(item.get("flow_id")) or f"FLOW-{source_route.upper()}-{index:03d}"
            steps = ordered_step_interfaces_from_item(item)
            roles = text_list(item.get("roles"))
            executing_role = as_text(item.get("executing_role")) or (roles[0] if roles else "")
            candidate = Candidate(
                candidate_id=f"CAND-{source_route.upper()}-{index:03d}",
                flow_id=flow_id,
                source_route=source_route,
                scenario_id=scenario_id,
                business_domain=as_text(item.get("business_domain")),
                scenario_name=as_text(item.get("scenario_name")) or scenario_id,
                executing_role=executing_role,
                business_description=as_text(item.get("business_description")),
                chain_type=as_text(item.get("chain_type")),
                flow_generation_required=as_bool(item.get("flow_generation_required")),
                ordered_step_count=as_int(item.get("ordered_step_count")),
                pre_action_interface=nested_text(item, "pre_action", "interface") or as_text(item.get("pre_action_interface")),
                observable_change_type=nested_text(item, "observable_change", "type") or as_text(item.get("observable_change_type")),
                observable_change_evidence=nested_text(item, "observable_change", "evidence") or as_text(item.get("observable_change_evidence")),
                verification_interface=nested_text(item, "verification", "interface") or as_text(item.get("verification_interface")),
                link_keys=text_list(item.get("link_keys")),
                steps=steps,
                related_interfaces=text_list(item.get("related_interfaces")),
                business_chain=text_list(item.get("business_chain")),
                state_chain=text_list(item.get("state_chain")),
                blockers=text_list(item.get("blockers")),
                evidence_refs=text_list(item.get("evidence_refs")) or text_list(item.get("source_refs")),
                inferred_fields=[],
                discovery_signals=[],
                candidate_inventory_type="",
                missing_evidence=[],
                classification="",
                reason="",
                downstream_target="",
            )
            candidate.inferred_fields = infer_candidate_fields(candidate)
            candidate.classification, candidate.reason = classify_candidate(candidate)
            candidate.downstream_target = downstream_target_for(candidate.classification)
            candidate.discovery_signals = discovery_signals_for(candidate)
            candidate.candidate_inventory_type = inventory_type_for(candidate.classification)
            candidate.missing_evidence = missing_evidence_for(candidate)
            candidates.append(candidate)
        return candidates

    text = read_text(map_path)
    for index, block in enumerate(scenario_blocks(text), start=1):
        scenario_id = first_scalar(block, "scenario_id") or f"SCENARIO-{source_route.upper()}-{index:03d}"
        flow_id = first_scalar(block, "flow_id") or f"FLOW-{source_route.upper()}-{index:03d}"
        roles = list_values(block, "roles")
        executing_role = first_scalar(block, "executing_role") or (roles[0] if roles else "")
        candidate = Candidate(
            candidate_id=f"CAND-{source_route.upper()}-{index:03d}",
            flow_id=flow_id,
            source_route=source_route,
            scenario_id=scenario_id,
            business_domain=first_scalar(block, "business_domain"),
            scenario_name=first_scalar(block, "scenario_name") or scenario_id,
            executing_role=executing_role,
            business_description=first_scalar(block, "business_description"),
            chain_type=first_scalar(block, "chain_type"),
            flow_generation_required=bool_scalar(first_scalar(block, "flow_generation_required")),
            ordered_step_count=int_scalar(first_scalar(block, "ordered_step_count")),
            pre_action_interface=nested_scalar(block, "pre_action", "interface") or first_scalar(block, "pre_action_interface"),
            observable_change_type=nested_scalar(block, "observable_change", "type") or first_scalar(block, "observable_change_type"),
            observable_change_evidence=nested_scalar(block, "observable_change", "evidence") or first_scalar(block, "observable_change_evidence"),
            verification_interface=nested_scalar(block, "verification", "interface") or first_scalar(block, "verification_interface"),
            link_keys=list_values(block, "link_keys"),
            steps=ordered_step_interfaces(block),
            related_interfaces=list_values(block, "related_interfaces"),
            business_chain=list_values(block, "business_chain"),
            state_chain=list_values(block, "state_chain"),
            blockers=list_values(block, "blockers"),
            evidence_refs=list_values(block, "evidence_refs") or list_values(block, "source_refs"),
            inferred_fields=[],
            discovery_signals=[],
            candidate_inventory_type="",
            missing_evidence=[],
            classification="",
            reason="",
            downstream_target="",
        )
        candidate.inferred_fields = infer_candidate_fields(candidate)
        candidate.classification, candidate.reason = classify_candidate(candidate)
        candidate.downstream_target = downstream_target_for(candidate.classification)
        candidate.discovery_signals = discovery_signals_for(candidate)
        candidate.candidate_inventory_type = inventory_type_for(candidate.classification)
        candidate.missing_evidence = missing_evidence_for(candidate)
        candidates.append(candidate)
    return candidates


def candidate_from_reconciled_flow(flow_id: str, item: dict[str, Any], flow: dict[str, Any]) -> Candidate:
    pre_action = flow.get("pre_action") if isinstance(flow.get("pre_action"), dict) else {}
    observable_change = flow.get("observable_change") if isinstance(flow.get("observable_change"), dict) else {}
    verification = flow.get("verification") if isinstance(flow.get("verification"), dict) else {}
    source_route = as_text(flow.get("source_route")) or "doc"
    candidate = Candidate(
        candidate_id=as_text(item.get("candidate_id")) or f"CAND-RECONCILED-{flow_id}",
        flow_id=flow_id,
        source_route=source_route,
        scenario_id=as_text(flow.get("scenario_id")) or as_text(item.get("design_case_id")) or flow_id,
        business_domain=as_text(flow.get("business_domain")),
        scenario_name=as_text(flow.get("scenario_name")) or flow_id,
        executing_role=as_text(flow.get("executing_role")),
        business_description=as_text(flow.get("business_description")),
        chain_type="e2e_flow_candidate",
        flow_generation_required=True,
        ordered_step_count=len(text_list(flow.get("steps"))),
        pre_action_interface=as_text(pre_action.get("interface")),
        observable_change_type=as_text(observable_change.get("type")),
        observable_change_evidence=as_text(observable_change.get("evidence")),
        verification_interface=as_text(verification.get("interface")),
        link_keys=text_list(flow.get("link_keys")),
        steps=text_list(flow.get("steps")),
        related_interfaces=[],
        business_chain=[],
        state_chain=[],
        blockers=[],
        evidence_refs=text_list(flow.get("evidence_refs")),
        inferred_fields=[],
        discovery_signals=["execution_readiness_reconciled"],
        candidate_inventory_type="business_long_chain_ready",
        missing_evidence=[],
        classification="included",
        reason="执行事实变更后重算为目标深度可物化闭环",
        downstream_target="required_chain_flows",
    )
    return candidate


def validate_reconciled_required_flow(flow_id: str, flow: dict[str, Any], errors: list[str]) -> None:
    require_non_empty_text(flow.get("source_route"), f"{flow_id}.required_flow.source_route", errors)
    require_non_empty_text(flow.get("business_domain"), f"{flow_id}.required_flow.business_domain", errors)
    require_non_empty_text(flow.get("scenario_name"), f"{flow_id}.required_flow.scenario_name", errors)
    for parent, child in (("pre_action", "interface"), ("observable_change", "type"), ("observable_change", "evidence"), ("verification", "interface")):
        nested = flow.get(parent)
        value = nested.get(child) if isinstance(nested, dict) else None
        require_non_empty_text(value, f"{flow_id}.required_flow.{parent}.{child}", errors)
    for field in ("link_keys", "steps", "evidence_refs"):
        require_non_empty_text_list(flow.get(field), f"{flow_id}.required_flow.{field}", errors)


def apply_readiness_reconciliation(
    output_root: Path,
    candidates: list[Candidate],
    reconciliation_path: Path,
) -> list[Candidate]:
    """按版本化执行事实重算候选；校验失败时不改写任何分母产物。"""
    data = load_yaml_mapping(reconciliation_path)
    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append("chain_execution_readiness_reconciliation.yaml schema_version 必须为 1")
    if as_text(data.get("stage")) != "chain_execution_readiness_reconciliation":
        errors.append("chain_execution_readiness_reconciliation.yaml stage 非法")
    if as_text(data.get("status")) not in {"ready_for_generation", "passed"}:
        errors.append("chain_execution_readiness_reconciliation.yaml status 必须为 ready_for_generation 或 passed")
    target_depth = as_text(data.get("target_depth"))
    if target_depth not in {"executable", "framework"}:
        errors.append("chain_execution_readiness_reconciliation.yaml target_depth 必须为 executable 或 framework")
    if text_list(data.get("blocking_issues")):
        errors.append("chain_execution_readiness_reconciliation.yaml blocking_issues 必须为空")

    revisions = data.get("fact_revisions")
    revision_paths: set[str] = set()
    if not isinstance(revisions, list) or not revisions:
        errors.append("chain_execution_readiness_reconciliation.yaml fact_revisions 必须为非空列表")
    else:
        for index, revision in enumerate(revisions, start=1):
            if not isinstance(revision, dict):
                errors.append(f"fact_revisions 第 {index} 项必须为对象")
                continue
            relative = require_non_empty_text(revision.get("path"), f"fact_revisions[{index}].path", errors)
            expected_hash = require_non_empty_text(revision.get("sha256"), f"fact_revisions[{index}].sha256", errors)
            if relative:
                revision_paths.add(relative)
            if expected_hash and not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
                errors.append(f"fact_revisions[{index}].sha256 必须为 64 位小写十六进制")
            if not relative:
                continue
            source_path = (output_root / relative).resolve()
            try:
                source_path.relative_to(output_root.resolve())
            except ValueError:
                errors.append(f"fact_revisions[{index}].path 越出流水线输出目录：{relative}")
                continue
            if not source_path.is_file():
                errors.append(f"fact_revisions[{index}] 引用文件不存在：{relative}")
            elif expected_hash and sha256_file(source_path) != expected_hash:
                errors.append(f"执行事实已变化，必须重新计算链路分母：{relative}")
    missing_fact_revisions = [
        relative
        for relative in KNOWN_EXECUTION_FACT_PATHS
        if (output_root / relative).is_file() and relative not in revision_paths
    ]
    if missing_fact_revisions:
        errors.append(f"执行就绪重算遗漏现有事实文件版本：{missing_fact_revisions}")

    ready_items = data.get("ready_chains")
    if not isinstance(ready_items, list):
        ready_items = []
        errors.append("chain_execution_readiness_reconciliation.yaml ready_chains 必须为列表")
    pending_items = data.get("pending_chains")
    if not isinstance(pending_items, list):
        pending_items = []
        errors.append("chain_execution_readiness_reconciliation.yaml pending_chains 必须为列表")

    ready_ids: list[str] = []
    generate_ids: set[str] = set()
    exclusion_ids: set[str] = set()
    normalized_items: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for index, item in enumerate(ready_items, start=1):
        if not isinstance(item, dict):
            errors.append(f"ready_chains 第 {index} 项必须为对象")
            continue
        flow_id = require_non_empty_text(item.get("flow_id"), f"ready_chains[{index}].flow_id", errors)
        if not flow_id:
            continue
        ready_ids.append(flow_id)
        decision = as_text(item.get("decision"))
        if decision not in {"generate", "exclude"}:
            errors.append(f"{flow_id}.decision 必须为 generate 或 exclude")
        capability = as_text(item.get("closure_capability"))
        if capability not in READINESS_CAPABILITIES:
            errors.append(f"{flow_id}.closure_capability 非法：{capability}")
        supported_depths = set(text_list(item.get("supported_target_depths")))
        if target_depth not in supported_depths:
            errors.append(f"{flow_id} 不支持目标深度 {target_depth}")
        if as_text(item.get("materialization_status")) != "ready":
            errors.append(f"{flow_id}.materialization_status 必须为 ready")
        unresolved = text_list(item.get("unresolved_materialization_items"))
        if unresolved:
            errors.append(f"{flow_id} 仍有未闭合物化项：{unresolved}")
        require_non_empty_text_list(item.get("closure_evidence_refs"), f"{flow_id}.closure_evidence_refs", errors)
        if decision == "generate":
            required_flow = item.get("required_flow")
            if not isinstance(required_flow, dict):
                errors.append(f"{flow_id}.required_flow 必须为对象")
                required_flow = {}
            validate_reconciled_required_flow(flow_id, required_flow, errors)
            generate_ids.add(flow_id)
            normalized_items.append((flow_id, item, required_flow))
        elif decision == "exclude":
            exclusion_ids.add(flow_id)
            require_non_empty_text(item.get("exclusion_reason_code"), f"{flow_id}.exclusion_reason_code", errors)
            require_non_empty_text_list(item.get("exclusion_evidence_refs"), f"{flow_id}.exclusion_evidence_refs", errors)
            if text_list(item.get("executable_case_ids")):
                errors.append(f"{flow_id} 明确排除时 executable_case_ids 必须为空")

    if len(ready_ids) != len(set(ready_ids)):
        errors.append("ready_chains.flow_id 必须唯一")
    pending_ids = [as_text(item.get("flow_id")) for item in pending_items if isinstance(item, dict)]
    pending_ids = [flow_id for flow_id in pending_ids if flow_id]
    if len(pending_ids) != len(set(pending_ids)):
        errors.append("pending_chains.flow_id 必须唯一")
    overlap = set(ready_ids) & set(pending_ids)
    if overlap:
        errors.append(f"ready_chains 与 pending_chains 不得重叠：{sorted(overlap)}")

    expected_counts = {
        "ready_chain_count": len(set(ready_ids)),
        "generate_count": len(generate_ids),
        "explicit_exclusion_count": len(exclusion_ids),
        "pending_chain_count": len(set(pending_ids)),
    }
    for field, expected in expected_counts.items():
        if data.get(field) != expected:
            errors.append(f"{field} 与明细不一致：{data.get(field)} != {expected}")
    if len(set(ready_ids)) != len(generate_ids) + len(exclusion_ids):
        errors.append("执行就绪链路守恒失败：ready != generate + explicit exclusion")

    if errors:
        raise ValueError("\n".join(errors))

    by_alias: dict[str, list[Candidate]] = {}
    for candidate in candidates:
        by_alias.setdefault(candidate.flow_id, []).append(candidate)
    for flow_id, item, required_flow in normalized_items:
        aliases = {flow_id, *text_list(item.get("aliases"))}
        matches = [candidate for alias in aliases for candidate in by_alias.get(alias, [])]
        if not matches:
            candidate = candidate_from_reconciled_flow(flow_id, item, required_flow)
            candidates.append(candidate)
            by_alias.setdefault(flow_id, []).append(candidate)
            matches = [candidate]
        for candidate in matches:
            replacement = candidate_from_reconciled_flow(flow_id, item, required_flow)
            candidate.flow_id = replacement.flow_id
            candidate.source_route = replacement.source_route
            candidate.scenario_id = replacement.scenario_id
            candidate.business_domain = replacement.business_domain
            candidate.scenario_name = replacement.scenario_name
            candidate.executing_role = replacement.executing_role or candidate.executing_role
            candidate.business_description = replacement.business_description or candidate.business_description
            candidate.chain_type = replacement.chain_type
            candidate.flow_generation_required = True
            candidate.ordered_step_count = replacement.ordered_step_count
            candidate.pre_action_interface = replacement.pre_action_interface
            candidate.observable_change_type = replacement.observable_change_type
            candidate.observable_change_evidence = replacement.observable_change_evidence
            candidate.verification_interface = replacement.verification_interface
            candidate.link_keys = replacement.link_keys
            candidate.steps = replacement.steps
            candidate.evidence_refs = sorted(set(candidate.evidence_refs + replacement.evidence_refs + text_list(item.get("closure_evidence_refs"))))
            candidate.discovery_signals = sorted(set(candidate.discovery_signals + replacement.discovery_signals))
            candidate.candidate_inventory_type = replacement.candidate_inventory_type
            candidate.missing_evidence = []
            candidate.classification = replacement.classification
            candidate.reason = replacement.reason
            candidate.downstream_target = replacement.downstream_target

    for item in ready_items:
        if not isinstance(item, dict) or as_text(item.get("decision")) != "exclude":
            continue
        flow_id = as_text(item.get("flow_id"))
        aliases = {flow_id, *text_list(item.get("aliases"))}
        matches = [candidate for alias in aliases for candidate in by_alias.get(alias, [])]
        for candidate in matches:
            candidate.flow_id = flow_id
            candidate.classification = "excluded_ready_by_policy"
            candidate.candidate_inventory_type = "business_long_chain_ready"
            candidate.downstream_target = "explicit_execution_ready_exclusion"
            candidate.missing_evidence = []
            candidate.discovery_signals = sorted(set(candidate.discovery_signals + ["execution_readiness_reconciled"]))
            candidate.evidence_refs = sorted(
                set(
                    candidate.evidence_refs
                    + text_list(item.get("closure_evidence_refs"))
                    + text_list(item.get("exclusion_evidence_refs"))
                )
            )
            candidate.reason = f"执行就绪但按明确策略排除：{as_text(item.get('exclusion_reason_code'))}"

    canonical_path = output_root / CHAIN_EXECUTION_READINESS_RECONCILIATION
    if reconciliation_path.resolve() != canonical_path.resolve():
        canonical_path.write_text(read_text(reconciliation_path), encoding="utf-8")
    return candidates


def yaml_list(values: list[str], indent: int = 6) -> list[str]:
    prefix = " " * indent
    if not values:
        return [f"{prefix}[]"]
    return [f"{prefix}- {yaml_scalar(value)}" for value in values]


def yaml_scalar(value: str) -> str:
    """输出安全的 YAML 标量，避免中文业务文本中的冒号等字符破坏结构。"""
    if value == "":
        return '""'
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def write_required_flows(output_root: Path, candidates: list[Candidate]) -> None:
    included = [candidate for candidate in candidates if candidate.classification == "included"]
    merged: dict[str, Candidate] = {}
    evidence_routes: dict[str, set[str]] = {}
    for candidate in included:
        merged.setdefault(candidate.flow_id, candidate)
        evidence_routes.setdefault(candidate.flow_id, set()).add(candidate.source_route)

    lines = [
        "schema_version: 1",
        "stage: required_chain_flow_denominator",
        "status: passed",
        "next_stage_allowed: true",
        f"required_chain_flow_count: {len(merged)}",
        "unclassified_candidate_flows: []",
        "flows:",
    ]
    if not merged:
        lines.append("  []")
    for flow_id in sorted(merged):
        candidate = merged[flow_id]
        routes = sorted(evidence_routes.get(flow_id, {candidate.source_route}))
        lines.extend(
            [
                f"  - flow_id: {yaml_scalar(flow_id)}",
                f"    source_route: {yaml_scalar(candidate.source_route)}",
                "    evidence_routes:",
                *yaml_list(routes, indent=6),
                f"    business_domain: {yaml_scalar(candidate.business_domain)}",
                f"    scenario_name: {yaml_scalar(candidate.scenario_name)}",
                "    pre_action:",
                f"      interface: {yaml_scalar(candidate.pre_action_interface)}",
                "    observable_change:",
                f"      type: {yaml_scalar(candidate.observable_change_type)}",
                f"      evidence: {yaml_scalar(candidate.observable_change_evidence)}",
                "    verification:",
                f"      interface: {yaml_scalar(candidate.verification_interface)}",
                "    link_keys:",
                *yaml_list(candidate.link_keys, indent=6),
                "    steps:",
                *yaml_list(candidate.steps, indent=6),
                "    evidence_refs:",
                *yaml_list(candidate.evidence_refs, indent=6),
                "    status: required",
            ]
        )
    lines.append("blocking_issues: []")
    (output_root / REQUIRED_CHAIN_FLOWS).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_candidate_inventory(output_root: Path, candidates: list[Candidate]) -> None:
    counts = {inventory_type: 0 for inventory_type in INVENTORY_TYPES}
    for candidate in candidates:
        counts[candidate.candidate_inventory_type] = counts.get(candidate.candidate_inventory_type, 0) + 1
    lines = [
        "schema_version: 1",
        "stage: business_chain_candidate_inventory",
        "status: passed",
        "next_stage_allowed: true",
        f"candidate_total: {len(candidates)}",
        "candidate_type_summary:",
    ]
    lines.extend(f"  {inventory_type}: {counts[inventory_type]}" for inventory_type in INVENTORY_TYPES)
    lines.append("items:")
    if not candidates:
        lines.append("  []")
    for candidate in candidates:
        lines.extend(
            [
                f"  - candidate_id: {yaml_scalar(candidate.candidate_id)}",
                f"    candidate_type: {yaml_scalar(candidate.candidate_inventory_type)}",
                f"    classification: {yaml_scalar(candidate.classification)}",
                f"    flow_id: {yaml_scalar(candidate.flow_id)}",
                f"    scenario_id: {yaml_scalar(candidate.scenario_id)}",
                f"    source_route: {yaml_scalar(candidate.source_route)}",
                f"    business_domain: {yaml_scalar(candidate.business_domain)}",
                f"    scenario_name: {yaml_scalar(candidate.scenario_name)}",
                f"    executing_role: {yaml_scalar(candidate.executing_role)}",
                f"    downstream_target: {yaml_scalar(candidate.downstream_target)}",
                "    inferred_fields:",
                *yaml_list(candidate.inferred_fields, indent=6),
                "    discovery_signals:",
                *yaml_list(candidate.discovery_signals, indent=6),
                "    missing_evidence:",
                *yaml_list(candidate.missing_evidence, indent=6),
                "    steps:",
                *yaml_list(candidate.steps, indent=6),
                "    evidence_refs:",
                *yaml_list(candidate.evidence_refs, indent=6),
                f"    reason: {yaml_scalar(candidate.reason)}",
            ]
        )
    lines.append("blocking_issues: []")
    (output_root / BUSINESS_CHAIN_CANDIDATE_INVENTORY).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_candidate_audit(output_root: Path, candidates: list[Candidate]) -> None:
    counts = {classification: 0 for classification in sorted(ALLOWED_CLASSIFICATIONS)}
    for candidate in candidates:
        counts[candidate.classification] += 1
    summary_order = (
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
    )
    lines = [
        "schema_version: 1",
        "stage: chain_flow_candidate_audit",
        "status: passed",
        "next_stage_allowed: true",
        "candidate_summary:",
    ]
    lines.extend(f"  {classification}: {counts[classification]}" for classification in summary_order)
    lines.extend(["  unclassified: 0", "candidates:"])
    if not candidates:
        lines.append("  []")
    for candidate in candidates:
        lines.extend(
            [
                f"  - candidate_id: {yaml_scalar(candidate.candidate_id)}",
                f"    classification: {yaml_scalar(candidate.classification)}",
                f"    flow_id: {yaml_scalar(candidate.flow_id)}",
                f"    source_route: {yaml_scalar(candidate.source_route)}",
                f"    scenario_id: {yaml_scalar(candidate.scenario_id)}",
                f"    downstream_target: {yaml_scalar(candidate.downstream_target)}",
                f"    candidate_inventory_type: {yaml_scalar(candidate.candidate_inventory_type)}",
                "    inferred_fields:",
                *yaml_list(candidate.inferred_fields, indent=6),
                "    discovery_signals:",
                *yaml_list(candidate.discovery_signals, indent=6),
                "    missing_evidence:",
                *yaml_list(candidate.missing_evidence, indent=6),
                "    evidence_refs:",
                *yaml_list(candidate.evidence_refs, indent=6),
                f"    reason: {yaml_scalar(candidate.reason)}",
            ]
        )
    lines.extend(["unclassified_candidate_flows: []", "blocking_issues: []"])
    (output_root / CHAIN_FLOW_CANDIDATE_AUDIT).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_alignment(output_root: Path, doc_candidates: list[Candidate], source_candidates: list[Candidate]) -> None:
    doc_included = {candidate.flow_id: candidate for candidate in doc_candidates if candidate.classification == "included"}
    source_included = {candidate.flow_id: candidate for candidate in source_candidates if candidate.classification == "included"}
    all_flow_ids = sorted(set(doc_included) | set(source_included))
    lines = [
        "schema_version: 1",
        "stage: chain_flow_alignment",
        "status: passed",
        "alignment_items:",
    ]
    if not all_flow_ids:
        lines.append("  []")
    for flow_id in all_flow_ids:
        if flow_id in doc_included and flow_id in source_included:
            status = "both_consistent" if doc_included[flow_id].steps == source_included[flow_id].steps else "both_step_diff"
        elif flow_id in doc_included:
            status = "doc_only"
        else:
            status = "source_only"
        lines.extend([f"  - flow_id: {yaml_scalar(flow_id)}", f"    alignment_status: {yaml_scalar(status)}"])
    lines.append("blocking_issues: []")
    (output_root / CHAIN_FLOW_ALIGNMENT).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="生成长链路闭环必测分母和候选审计")
    parser.add_argument("--output-root", required=True, help="流水线输出根目录")
    parser.add_argument("--doc-entry", help="文档入口产物目录，默认 output-root/01-pre-doc-analysis")
    parser.add_argument("--source-entry", help="源码入口产物目录，默认 output-root/02-source-api-facts/docs/source-facts")
    parser.add_argument(
        "--readiness-reconciliation",
        help="执行事实变化后的链路就绪重算文件；提供后会先校验事实版本和守恒关系，再重写分母",
    )
    args = parser.parse_args()

    output_root = Path(args.output_root)
    doc_entry = Path(args.doc_entry) if args.doc_entry else output_root / "01-pre-doc-analysis"
    source_entry = Path(args.source_entry) if args.source_entry else output_root / "02-source-api-facts" / "docs" / "source-facts"
    doc_candidates = load_candidates(doc_entry, "doc") if doc_entry.exists() else []
    source_candidates = load_candidates(source_entry, "source") if source_entry.exists() else []
    candidates = doc_candidates + source_candidates
    output_root.mkdir(parents=True, exist_ok=True)
    if args.readiness_reconciliation:
        try:
            candidates = apply_readiness_reconciliation(output_root, candidates, Path(args.readiness_reconciliation))
        except ValueError as exc:
            print(f"执行就绪重算失败：\n{exc}")
            return 2
    write_candidate_inventory(output_root, candidates)
    write_required_flows(output_root, candidates)
    write_candidate_audit(output_root, candidates)
    if doc_entry.exists() and source_entry.exists():
        write_alignment(output_root, doc_candidates, source_candidates)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
