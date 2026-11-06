#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


UNKNOWN = "UNKNOWN"
PATH_BUCKET_PATTERNS = (
    re.compile(r"(?:接口|路径|URL|uri|controller|模块|包名|前缀).{0,16}(?:聚合|分组|串联|穷举|正向测试|反向测试|异常测试)", re.IGNORECASE),
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

REQUIRED_DOCS = [
    "01_接口测试用例设计文档.md",
    "02_接口结构化契约清单.md",
    "03_skill执行报告.md",
    "stage_status.yaml",
    "coverage_matrix.yaml",
    "business_scenario_map.yaml",
    "业务场景链路清单.md",
    "01-api-inventory.md",
    "02-api-contracts.md",
    "03-call-chain.md",
    "04-business-rules.md",
    "05-source-db-side-effects.md",
    "06-unknown-and-risk.md",
    "08-security-transform-facts.md",
    "09-interface-encryption-policy.md",
    "source_api_fact_artifacts.yaml",
    "source-api-facts.json",
]

REQUIRED_ARTIFACT_NAMES = {
    "source_api_design_doc",
    "source_api_contract_list",
    "source_api_stage_report",
    "source_api_security_transform_facts",
    "source_api_interface_encryption_policy",
    "source_api_business_scenario_map",
    "source_api_business_scenario_doc",
    "source_api_stage_status",
    "source_api_coverage_matrix",
    "source_api_fact_json",
    "source_api_fact_artifact_manifest",
}

REQUIRED_API_KEYS = {
    "api_id",
    "module",
    "entry",
    "contract",
    "call_chain",
    "business_rules",
    "db_side_effects",
    "security_transforms",
    "transport_encryption_policy",
    "unknowns",
}

REQUIRED_TRANSPORT_ENCRYPTION_POLICY_KEYS = {
    "api_id",
    "module",
    "http_method",
    "path",
    "entry_type",
    "class_name",
    "method_name",
    "channel_type",
    "policy_hint",
    "confidence",
    "policy_status",
    "requires_manual_confirmation",
    "reason_codes",
    "evidence_refs",
}

REQUIRED_SECURITY_TRANSFORM_KEYS = {
    "transform_id",
    "api_id",
    "scope",
    "class_name",
    "method_name",
    "transform_type",
    "algorithm",
    "input_role",
    "output_role",
    "deterministic",
    "reversible",
    "requires_secret",
    "config_key",
    "execution_impact",
    "script_assertion_strategy",
    "evidence",
}


def business_scenario_blocks(content: str) -> list[str]:
    starts = list(re.finditer(r"(?m)^\s*-\s+scenario_id\s*:", content))
    blocks: list[str] = []
    for index, start in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(content)
        blocks.append(content[start.start():end])
    return blocks


def yaml_scalar(block: str, key: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*:\s*\"?(.+?)\"?\s*$", block)
    return match.group(1).strip().strip("\"'") if match else ""


def is_yaml_true(value: str) -> bool:
    return value.strip().strip("\"'").lower() in {"true", "yes", "1", "是", "需要"}


def looks_like_path_bucket_text(*values: str) -> bool:
    text = " ".join(value.strip().strip("\"'") for value in values if value)
    compact = re.sub(r"\s+", "", text)
    if compact in {"接口链路", "接口集合", "接口组合", "模块链路", "API链路", "资源从业务处理到结果校验"}:
        return True
    return any(pattern.search(text) for pattern in PATH_BUCKET_PATTERNS)


def scenario_items_from_content(content: str) -> list[dict[str, Any]]:
    try:
        data = yaml.safe_load(content)
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
    if not text or text in {"[]", "无", "未知", "待确认", "待补充", "TBD"}:
        return []
    return [text]


def scenario_interfaces(item: dict[str, Any]) -> list[str]:
    interfaces = text_list(item.get("related_interfaces"))
    for step in item.get("ordered_steps") or []:
        if isinstance(step, dict):
            interfaces.extend(text_list(step.get("interface")))
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
    if not semantic_parts:
        return ""
    return "/".join(semantic_parts[:2])


def item_has_mutation(item: dict[str, Any]) -> bool:
    text = " ".join(scenario_interfaces(item) + text_list(item.get("business_chain")) + text_list(item.get("scenario_name")))
    return bool(MUTATING_INTERFACE_RE.search(text)) or bool(re.search(r"创建|提交|更新|删除|发布|发送|认证|上传|支付|充值|提现|绑定|解除|申请|审核", text))


def item_has_read_or_verify(item: dict[str, Any]) -> bool:
    text = " ".join(scenario_interfaces(item) + text_list(item.get("business_chain")) + text_list(item.get("scenario_name")))
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
        keys = {resource_key_from_interface(interface) for interface in scenario_interfaces(item)}
        for key in keys:
            if key:
                groups.setdefault(key, []).append(item)
    splittable: list[str] = []
    for key, group in sorted(groups.items()):
        if len(group) < 3:
            continue
        if any(item_has_mutation(item) for item in group) and any(item_has_read_or_verify(item) for item in group):
            splittable.append(key)
    return splittable

REQUIRED_ENTRY_KEYS = {
    "entry_type",
    "class_name",
    "method_name",
    "http_method",
    "path",
    "rpc_interface",
    "request_type",
    "response_type",
    "auth_hint",
    "source_evidence",
}

HTTP_MAPPING_METHODS = {
    "GetMapping": "GET",
    "PostMapping": "POST",
    "PutMapping": "PUT",
    "DeleteMapping": "DELETE",
    "PatchMapping": "PATCH",
}

MAPPING_ANNOTATIONS = set(HTTP_MAPPING_METHODS) | {"RequestMapping"}
ENTRY_CLASS_ANNOTATIONS = {"RestController", "Controller", "FeignClient"}
EVIDENCE_RE = re.compile(
    r"(?P<path>[^|\n]+?\.(?:java|xml|yml|yaml|properties))"
    r"(?::(?P<line>\d+))?"
    r"(?:\s*\|\s*(?P<class>\w+)\.(?P<method>\w+|UNKNOWN))?"
)


@dataclass(frozen=True)
class ExpectedApi:
    rel_path: str
    class_name: str
    method_name: str
    entry_type: str
    http_method: str
    path: str
    line: int

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.rel_path, self.class_name, self.method_name)


def run_quality_check(
    src_root: str | Path,
    facts_path: str | Path,
    out_dir: str | Path | None = None,
    fail_on: str = "ERROR",
) -> dict[str, Any]:
    src = Path(src_root).resolve()
    facts_file = Path(facts_path).resolve()
    output_dir = Path(out_dir).resolve() if out_dir else facts_file.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    issues: list[dict[str, str]] = []
    facts = load_facts(facts_file, issues)
    apis = facts.get("apis", []) if isinstance(facts, dict) else []
    summary = facts.get("summary", {}) if isinstance(facts, dict) else {}

    check_required_docs(output_dir, issues)
    check_artifact_manifest(output_dir, issues)
    check_business_scenario_map(output_dir, issues)
    check_rendered_coverage_id_consistency(output_dir, issues)
    check_json_shape(facts, issues)
    check_api_structure(apis, issues)
    check_unique_api_ids(apis, issues)
    check_unknown_structure(apis, facts.get("project_unknowns", []), issues)
    check_security_transform_structure(apis, facts.get("project_security_transforms", []), facts.get("secret_config_refs", []), issues)
    check_transport_encryption_policy_structure(apis, facts.get("project_encryption_policy", {}), issues)
    check_summary(summary, apis, facts.get("project_unknowns", []), facts.get("secret_config_refs", []), issues)
    check_evidence_paths(src, facts, issues)
    check_entry_evidence_targets(src, apis, issues)

    expected_entries = independently_scan_source_entries(src, facts, issues)
    actual_entries = actual_source_entries(apis)
    check_source_coverage(expected_entries, actual_entries, apis, issues)
    check_contract_field_presence(src, facts, apis, issues)
    check_db_side_effect_consistency(apis, issues)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_root": str(src),
        "facts_path": str(facts_file),
        "summary": {
            "status": "FAILED" if any(i["level"] == "ERROR" for i in issues) else "PASSED",
            "error_count": sum(1 for i in issues if i["level"] == "ERROR"),
            "warn_count": sum(1 for i in issues if i["level"] == "WARN"),
            "info_count": sum(1 for i in issues if i["level"] == "INFO"),
        },
        "coverage": {
            "expected_api_count": len(expected_entries),
            "actual_api_count": len(apis),
            "actual_source_entry_count": len(actual_entries),
            "expected_feign_count": sum(1 for item in expected_entries if item.entry_type == "Feign Client"),
            "actual_feign_count": sum(1 for api in apis if api.get("entry", {}).get("entry_type") == "Feign Client"),
            "missing_source_api_count": count_missing_source_entries(expected_entries, actual_entries),
        },
        "issues": issues,
    }

    (output_dir / "source-api-quality-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "07-extraction-quality-report.md").write_text(render_markdown(report), encoding="utf-8")
    return report


def load_facts(facts_file: Path, issues: list[dict[str, str]]) -> dict[str, Any]:
    if not facts_file.exists():
        add_issue(issues, "ERROR", "FACTS_JSON_MISSING", f"事实 JSON 不存在：{facts_file}", str(facts_file))
        return {}
    try:
        data = json.loads(facts_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        add_issue(issues, "ERROR", "FACTS_JSON_INVALID", f"事实 JSON 无法解析：{exc}", str(facts_file))
        return {}
    if not isinstance(data, dict):
        add_issue(issues, "ERROR", "FACTS_JSON_INVALID", "事实 JSON 根节点必须是对象。", str(facts_file))
        return {}
    return data


def check_required_docs(output_dir: Path, issues: list[dict[str, str]]) -> None:
    for name in REQUIRED_DOCS:
        path = output_dir / name
        if not path.exists():
            add_issue(issues, "ERROR", "OUTPUT_FILE_MISSING", f"缺少输出文件：{name}", str(path))


def check_artifact_manifest(output_dir: Path, issues: list[dict[str, str]]) -> None:
    path = output_dir / "source_api_fact_artifacts.yaml"
    if not path.exists():
        return
    content = path.read_text(encoding="utf-8", errors="ignore")
    names = set(re.findall(r"artifact_name:\s*\"?([A-Za-z0-9_-]+)\"?", content))
    missing = sorted(REQUIRED_ARTIFACT_NAMES - names)
    if missing:
        add_issue(
            issues,
            "ERROR",
            "ARTIFACT_MANIFEST_NAME_MISSING",
            f"产物清单缺少明确 artifact_name：{', '.join(missing)}",
            str(path),
        )


def check_business_scenario_map(output_dir: Path, issues: list[dict[str, str]]) -> None:
    path = output_dir / "business_scenario_map.yaml"
    if not path.exists():
        return
    content = path.read_text(encoding="utf-8", errors="ignore")
    required_markers = (
        "schema_version: 1",
        "stage: business_scenario_mapping",
        "source_entry: source",
        "scenario_source_status: source_inferred",
        "scenario_items:",
        "scenario_id:",
        "business_description:",
        "related_test_point_ids:",
        "related_coverage_rule_ids:",
        "chain_type:",
        "flow_generation_required:",
    )
    for marker in required_markers:
        if marker not in content:
            add_issue(
                issues,
                "ERROR",
                "BUSINESS_SCENARIO_MAP_FIELD_MISSING",
                f"业务场景映射缺少字段或标记：{marker}",
                str(path),
            )
    if "status: passed" not in content:
        add_issue(
            issues,
            "ERROR",
            "BUSINESS_SCENARIO_MAP_NOT_PASSED",
            "业务场景映射未通过，不能作为下游覆盖点报告的业务场景来源",
            str(path),
        )
    descriptions = re.findall(r"business_description:\s*\"?(.+?)\"?\s*$", content, flags=re.MULTILINE)
    if not descriptions:
        add_issue(
            issues,
            "ERROR",
            "BUSINESS_SCENARIO_DESCRIPTION_MISSING",
            "业务场景映射缺少可解析的 business_description",
            str(path),
        )
    for description in descriptions:
        if not re.search(r"[\u4e00-\u9fff]", description):
            add_issue(
                issues,
                "ERROR",
                "BUSINESS_SCENARIO_DESCRIPTION_NOT_CHINESE",
                f"业务场景描述必须使用中文：{description}",
                str(path),
            )
    for block in business_scenario_blocks(content):
        if not is_yaml_true(yaml_scalar(block, "flow_generation_required")):
            continue
        if looks_like_path_bucket_text(yaml_scalar(block, "scenario_name"), yaml_scalar(block, "business_description")):
            add_issue(
                issues,
                "ERROR",
                "BUSINESS_SCENARIO_PATH_BUCKET",
                "业务场景链路疑似按路径前缀、接口集合或接口测试标签聚合，必须拆成真实业务场景",
                str(path),
            )
    scenario_items = scenario_items_from_content(content)
    splittable_clusters = splittable_single_interface_clusters(scenario_items)
    if splittable_clusters:
        add_issue(
            issues,
            "ERROR",
            "BUSINESS_SCENARIO_SPLIT_REQUIRED",
            "业务场景映射存在可拆分多接口业务簇但仍全部按单接口输出，必须先按执行角色、业务动作、前置状态和预期业务结果拆成真实业务链路："
            + ", ".join(splittable_clusters[:10]),
            str(path),
        )
    required_flow_count = len(re.findall(r"flow_generation_required:\s*true", content))
    if required_flow_count:
        for marker in ("flow_id:", "ordered_steps:", "ordered_step_count:"):
            if marker not in content:
                add_issue(
                    issues,
                    "ERROR",
                    "BUSINESS_SCENARIO_FLOW_FIELD_MISSING",
                    f"链路业务场景缺少字段：{marker}",
                    str(path),
                )
        step_counts = [int(value) for value in re.findall(r"ordered_step_count:\s*(\d+)", content)]
        if not step_counts or max(step_counts) < 2:
            add_issue(
                issues,
                "ERROR",
                "BUSINESS_SCENARIO_FLOW_STEP_INSUFFICIENT",
                "链路业务场景至少需要两个有序接口步骤",
                str(path),
            )


def check_rendered_coverage_id_consistency(output_dir: Path, issues: list[dict[str, str]]) -> None:
    coverage_path = output_dir / "coverage_matrix.yaml"
    design_path = output_dir / "01_接口测试用例设计文档.md"
    contract_path = output_dir / "02_接口结构化契约清单.md"
    if not coverage_path.exists() or not design_path.exists() or not contract_path.exists():
        return
    coverage_text = coverage_path.read_text(encoding="utf-8", errors="ignore")
    rendered_text = (
        design_path.read_text(encoding="utf-8", errors="ignore")
        + "\n"
        + contract_path.read_text(encoding="utf-8", errors="ignore")
    )
    coverage_ids = set(re.findall(r'coverage_id:\s*"([^"]+)"', coverage_text))
    missing = sorted(coverage_id for coverage_id in coverage_ids if coverage_id not in rendered_text)
    if missing:
        add_issue(
            issues,
            "ERROR",
            "COVERAGE_ID_NOT_RENDERED",
            f"coverage_matrix 中存在未渲染到设计/契约文档的覆盖 ID，数量：{len(missing)}，示例：{', '.join(missing[:10])}",
            str(coverage_path),
        )


def check_json_shape(facts: dict[str, Any], issues: list[dict[str, str]]) -> None:
    for key in ("project", "apis", "summary", "project_encryption_policy"):
        if key not in facts:
            add_issue(issues, "ERROR", "FACTS_FIELD_MISSING", f"事实 JSON 缺少顶层字段：{key}", key)
    if "apis" in facts and not isinstance(facts["apis"], list):
        add_issue(issues, "ERROR", "FACTS_FIELD_INVALID", "apis 必须是数组。", "apis")
    if "summary" in facts and not isinstance(facts["summary"], dict):
        add_issue(issues, "ERROR", "FACTS_FIELD_INVALID", "summary 必须是对象。", "summary")
    if "project_encryption_policy" in facts and not isinstance(facts["project_encryption_policy"], dict):
        add_issue(issues, "ERROR", "FACTS_FIELD_INVALID", "project_encryption_policy 必须是对象。", "project_encryption_policy")


def check_api_structure(apis: Any, issues: list[dict[str, str]]) -> None:
    if not isinstance(apis, list):
        return
    for idx, api in enumerate(apis):
        if not isinstance(api, dict):
            add_issue(issues, "ERROR", "API_ITEM_INVALID", f"apis[{idx}] 必须是对象。", f"apis[{idx}]")
            continue
        missing = sorted(REQUIRED_API_KEYS - set(api))
        if missing:
            add_issue(issues, "ERROR", "API_FIELD_MISSING", f"{api.get('api_id', idx)} 缺少字段：{', '.join(missing)}", api.get("api_id", str(idx)))
        entry = api.get("entry", {})
        if not isinstance(entry, dict):
            add_issue(issues, "ERROR", "API_ENTRY_INVALID", f"{api.get('api_id', idx)} 的 entry 必须是对象。", api.get("api_id", str(idx)))
            continue
        entry_missing = sorted(REQUIRED_ENTRY_KEYS - set(entry))
        if entry_missing:
            add_issue(issues, "ERROR", "API_ENTRY_FIELD_MISSING", f"{api.get('api_id', idx)} 的 entry 缺少字段：{', '.join(entry_missing)}", api.get("api_id", str(idx)))


def check_unique_api_ids(apis: Any, issues: list[dict[str, str]]) -> None:
    if not isinstance(apis, list):
        return
    seen: dict[str, int] = {}
    for idx, api in enumerate(apis):
        api_id = str(api.get("api_id", ""))
        if not api_id:
            add_issue(issues, "ERROR", "API_ID_MISSING", f"apis[{idx}] 缺少 api_id。", f"apis[{idx}]")
            continue
        if api_id in seen:
            add_issue(issues, "ERROR", "API_ID_DUPLICATED", f"api_id 重复：{api_id}", f"apis[{seen[api_id]}], apis[{idx}]")
        seen[api_id] = idx


def check_unknown_structure(apis: Any, project_unknowns: Any, issues: list[dict[str, str]]) -> None:
    unknown_ids: dict[str, str] = {}
    required = {
        "unknown_id",
        "api_id",
        "scope",
        "unknown_type",
        "severity",
        "action_required",
        "description",
        "why_unknown",
        "evidence_or_location",
        "suggested_manual_check",
    }
    api_items = apis if isinstance(apis, list) else []
    for api in api_items:
        if not isinstance(api, dict):
            continue
        api_id = str(api.get("api_id", UNKNOWN))
        contract = api.get("contract", {})
        if isinstance(contract, dict) and "unknowns" in contract:
            add_issue(
                issues,
                "ERROR",
                "CONTRACT_UNKNOWNS_DUPLICATED",
                f"{api_id} 的 contract 内仍包含 unknowns，风险项应统一收敛到 api.unknowns。",
                api_id,
            )
        check_unknown_items(api.get("unknowns", []), required, unknown_ids, issues, api_id)
    check_unknown_items(project_unknowns, required, unknown_ids, issues, "project_unknowns")


def check_unknown_items(
    items: Any,
    required: set[str],
    unknown_ids: dict[str, str],
    issues: list[dict[str, str]],
    location: str,
) -> None:
    if not isinstance(items, list):
        add_issue(issues, "ERROR", "UNKNOWNS_FIELD_INVALID", f"{location} 的 unknowns 必须是数组。", location)
        return
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            add_issue(issues, "ERROR", "UNKNOWN_ITEM_INVALID", f"{location}[{idx}] 必须是对象。", f"{location}[{idx}]")
            continue
        missing = sorted(required - set(item))
        if missing:
            add_issue(
                issues,
                "ERROR",
                "UNKNOWN_FIELD_MISSING",
                f"{location}[{idx}] 缺少字段：{', '.join(missing)}。",
                f"{location}[{idx}]",
            )
        unknown_id = str(item.get("unknown_id", ""))
        if not unknown_id:
            continue
        if unknown_id in unknown_ids:
            add_issue(
                issues,
                "ERROR",
                "UNKNOWN_ID_DUPLICATED",
                f"unknown_id 重复：{unknown_id}",
                f"{unknown_ids[unknown_id]}, {location}[{idx}]",
            )
        unknown_ids[unknown_id] = f"{location}[{idx}]"


def check_security_transform_structure(
    apis: Any,
    project_security_transforms: Any,
    secret_config_refs: Any,
    issues: list[dict[str, str]],
) -> None:
    transform_ids: dict[str, str] = {}
    groups = []
    if isinstance(apis, list):
        for api_idx, api in enumerate(apis):
            groups.append((f"apis[{api_idx}].security_transforms", api.get("security_transforms", []), api.get("api_id", "UNKNOWN")))
    groups.append(("project_security_transforms", project_security_transforms, "PROJECT"))
    for location, transforms, owner_api_id in groups:
        if not isinstance(transforms, list):
            add_issue(issues, "ERROR", "SECURITY_TRANSFORMS_INVALID", f"{location} 必须是数组。", location)
            continue
        for idx, transform in enumerate(transforms):
            item_location = f"{location}[{idx}]"
            if not isinstance(transform, dict):
                add_issue(issues, "ERROR", "SECURITY_TRANSFORM_INVALID", f"{item_location} 必须是对象。", item_location)
                continue
            missing = sorted(REQUIRED_SECURITY_TRANSFORM_KEYS - set(transform))
            if missing:
                add_issue(issues, "ERROR", "SECURITY_TRANSFORM_FIELD_MISSING", f"{item_location} 缺少字段：{', '.join(missing)}。", item_location)
            if transform.get("api_id") not in {owner_api_id, "PROJECT"}:
                add_issue(
                    issues,
                    "ERROR",
                    "SECURITY_TRANSFORM_API_MISMATCH",
                    f"{item_location} 的 api_id 与所属 API 不一致。",
                    item_location,
                )
            transform_id = str(transform.get("transform_id", ""))
            if not transform_id:
                add_issue(issues, "ERROR", "SECURITY_TRANSFORM_ID_MISSING", f"{item_location} 缺少 transform_id。", item_location)
                continue
            if transform_id in transform_ids:
                add_issue(
                    issues,
                    "ERROR",
                    "SECURITY_TRANSFORM_ID_DUPLICATED",
                    f"transform_id 重复：{transform_id}",
                    f"{transform_ids[transform_id]}, {item_location}",
                )
            transform_ids[transform_id] = item_location

    if not isinstance(secret_config_refs, list):
        add_issue(issues, "ERROR", "SECRET_CONFIG_REFS_INVALID", "secret_config_refs 必须是数组。", "secret_config_refs")
        return
    for idx, ref in enumerate(secret_config_refs):
        location = f"secret_config_refs[{idx}]"
        if not isinstance(ref, dict):
            add_issue(issues, "ERROR", "SECRET_CONFIG_REF_INVALID", f"{location} 必须是对象。", location)
            continue
        for key in (
            "config_key",
            "secret_ref",
            "sensitivity",
            "value_visible",
            "config_value_masked",
            "execution_impact",
            "script_strategy",
            "evidence",
        ):
            if key not in ref:
                add_issue(issues, "ERROR", "SECRET_CONFIG_REF_FIELD_MISSING", f"{location} 缺少字段：{key}。", location)
        if "config_value" in ref:
            add_issue(
                issues,
                "ERROR",
                "SECRET_CONFIG_PLAINTEXT_FORBIDDEN",
                f"{location} 不得保留明文 config_value；请使用 secret_ref 运行时注入。",
                location,
            )


def check_transport_encryption_policy_structure(
    apis: Any,
    project_encryption_policy: Any,
    issues: list[dict[str, str]],
) -> None:
    if not isinstance(project_encryption_policy, dict):
        add_issue(issues, "ERROR", "ENCRYPTION_POLICY_INVALID", "project_encryption_policy 必须是对象。", "project_encryption_policy")
        return
    policy_items = project_encryption_policy.get("policy_items")
    if not isinstance(policy_items, list):
        add_issue(issues, "ERROR", "ENCRYPTION_POLICY_ITEMS_INVALID", "project_encryption_policy.policy_items 必须是数组。", "project_encryption_policy.policy_items")
        policy_items = []
    item_by_api = {item.get("api_id"): item for item in policy_items if isinstance(item, dict)}
    if isinstance(apis, list) and len(policy_items) != len(apis):
        add_issue(
            issues,
            "ERROR",
            "ENCRYPTION_POLICY_COUNT_MISMATCH",
            f"传输加解密策略数量与 API 数量不一致：policy_items={len(policy_items)}，apis={len(apis)}。",
            "project_encryption_policy.policy_items",
        )
    for idx, api in enumerate(apis if isinstance(apis, list) else []):
        if not isinstance(api, dict):
            continue
        api_id = api.get("api_id", UNKNOWN)
        item = api.get("transport_encryption_policy")
        location = f"apis[{idx}].transport_encryption_policy"
        if not isinstance(item, dict):
            add_issue(issues, "ERROR", "ENCRYPTION_POLICY_ITEM_INVALID", f"{location} 必须是对象。", location)
            continue
        missing = sorted(REQUIRED_TRANSPORT_ENCRYPTION_POLICY_KEYS - set(item))
        if missing:
            add_issue(issues, "ERROR", "ENCRYPTION_POLICY_FIELD_MISSING", f"{api_id} 的传输加解密策略缺少字段：{', '.join(missing)}。", location)
        if item.get("api_id") != api_id:
            add_issue(issues, "ERROR", "ENCRYPTION_POLICY_API_MISMATCH", f"{api_id} 的传输加解密策略 api_id 不匹配。", location)
        if item_by_api.get(api_id) != item:
            add_issue(issues, "ERROR", "ENCRYPTION_POLICY_INDEX_MISMATCH", f"{api_id} 的 API 级策略与 project_encryption_policy.policy_items 不一致。", location)
        if item.get("policy_hint") not in {"no_encrypt_candidate", "requires_encryption_if_project_default_enabled", "policy_required"}:
            add_issue(issues, "ERROR", "ENCRYPTION_POLICY_HINT_INVALID", f"{api_id} 的 policy_hint 非法：{item.get('policy_hint')}", location)
        if item.get("confidence") not in {"high", "medium", "low"}:
            add_issue(issues, "ERROR", "ENCRYPTION_POLICY_CONFIDENCE_INVALID", f"{api_id} 的 confidence 非法：{item.get('confidence')}", location)
        if not isinstance(item.get("reason_codes"), list) or not item.get("reason_codes"):
            add_issue(issues, "ERROR", "ENCRYPTION_POLICY_REASON_MISSING", f"{api_id} 缺少传输加解密策略原因码。", location)


def check_summary(
    summary: dict[str, Any],
    apis: Any,
    project_unknowns: Any,
    secret_config_refs: Any,
    issues: list[dict[str, str]],
) -> None:
    if not isinstance(summary, dict) or not isinstance(apis, list):
        return
    project_unknown_count = len(project_unknowns) if isinstance(project_unknowns, list) else 0
    secret_config_ref_count = len(secret_config_refs) if isinstance(secret_config_refs, list) else 0
    computed = {
        "api_count": len(apis),
        "http_api_count": sum(1 for api in apis if api.get("entry", {}).get("http_method") != UNKNOWN),
        "rpc_api_count": sum(1 for api in apis if api.get("entry", {}).get("rpc_interface") != UNKNOWN),
        "unknown_path_count": sum(1 for api in apis if api.get("entry", {}).get("path") == UNKNOWN),
        "write_api_count": sum(
            1
            for api in apis
            if any(
                effect.get("operation_type") in {"CREATE", "UPDATE", "DELETE", "UPSERT"}
                for effect in api.get("db_side_effects", [])
            )
        ),
        "read_api_count": sum(
            1
            for api in apis
            if any(effect.get("operation_type") == "READ" for effect in api.get("db_side_effects", []))
        ),
        "business_rule_count": sum(len(api.get("business_rules", [])) for api in apis),
        "security_transform_count": sum(len(api.get("security_transforms", [])) for api in apis),
        "secret_config_ref_count": secret_config_ref_count,
        "error_code_count": sum(
            1
            for api in apis
            for rule in api.get("business_rules", [])
            if rule.get("error_code", UNKNOWN) != UNKNOWN
        ),
        "unknown_count": sum(len(api.get("unknowns", [])) for api in apis) + project_unknown_count,
    }
    for key, actual in computed.items():
        recorded = summary.get(key)
        if recorded != actual:
            add_issue(
                issues,
                "ERROR",
                "SUMMARY_MISMATCH",
                f"summary.{key} 与明细不一致：记录值 {recorded}，实际值 {actual}。",
                f"summary.{key}",
            )


def check_evidence_paths(src: Path, facts: dict[str, Any], issues: list[dict[str, str]]) -> None:
    for evidence in sorted(collect_evidence_values(facts)):
        parsed = parse_evidence(evidence)
        if not parsed:
            continue
        path_text = parsed["path"]
        source_path = resolve_source_path(src, path_text)
        if not source_path:
            add_issue(issues, "ERROR", "EVIDENCE_PATH_MISSING", f"源码证据路径不存在：{path_text}", evidence)
            continue
        line = parsed.get("line")
        if line:
            line_no = int(line)
            if line_no < 1:
                add_issue(issues, "ERROR", "EVIDENCE_LINE_INVALID", f"源码证据行号非法：{evidence}", evidence)
                continue
            try:
                line_count = len(source_path.read_text(encoding="utf-8", errors="ignore").splitlines())
            except OSError as exc:
                add_issue(issues, "ERROR", "EVIDENCE_FILE_UNREADABLE", f"源码证据文件无法读取：{source_path}，{exc}", evidence)
                continue
            if line_no > line_count:
                add_issue(issues, "ERROR", "EVIDENCE_LINE_OUT_OF_RANGE", f"源码证据行号超出文件范围：{evidence}", evidence)


def check_entry_evidence_targets(src: Path, apis: Any, issues: list[dict[str, str]]) -> None:
    if not isinstance(apis, list):
        return
    for api in apis:
        if not isinstance(api, dict):
            continue
        entry = api.get("entry", {})
        evidence = str(entry.get("source_evidence", ""))
        parsed = parse_evidence(evidence)
        if not parsed or not parsed.get("line"):
            continue
        method_name = str(entry.get("method_name", ""))
        source_path = resolve_source_path(src, parsed["path"])
        if not source_path or source_path.suffix != ".java":
            continue
        lines = source_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        line_no = int(parsed["line"])
        start = max(0, line_no - 4)
        end = min(len(lines), line_no + 3)
        window = "\n".join(lines[start:end])
        if not re.search(rf"\b{re.escape(method_name)}\s*\(", window):
            add_issue(
                issues,
                "ERROR",
                "EVIDENCE_METHOD_MISMATCH",
                f"入口源码证据行号未指向方法 {entry.get('class_name')}.{method_name}。",
                evidence,
                "重新生成证据行号，并确保块注释、注解和多行签名不会造成行号漂移。",
            )


def independently_scan_source_entries(
    src: Path,
    facts: dict[str, Any],
    issues: list[dict[str, str]],
) -> list[ExpectedApi]:
    roots = source_roots_from_scope(src, facts, issues)
    entries: list[ExpectedApi] = []
    seen: set[tuple[str, str, str]] = set()
    for root in roots:
        for java_file in sorted(root.rglob("*.java")):
            rel_to_scan_root = safe_relative(java_file, root)
            if should_skip_relative_path(rel_to_scan_root):
                continue
            rel_path = safe_relative(java_file, src).as_posix()
            text = java_file.read_text(encoding="utf-8", errors="ignore")
            for entry in scan_java_file_for_entries(rel_path, text):
                if entry.key in seen:
                    continue
                seen.add(entry.key)
                entries.append(entry)
    return sorted(entries, key=lambda item: item.key)


def source_roots_from_scope(src: Path, facts: dict[str, Any], issues: list[dict[str, str]]) -> list[Path]:
    scope = facts.get("project", {}).get("scan_scope") if isinstance(facts, dict) else None
    if isinstance(scope, list) and scope:
        roots: list[Path] = []
        for item in scope:
            candidate = (src / str(item)).resolve()
            if candidate.exists() and candidate.is_dir():
                roots.append(candidate)
            else:
                add_issue(issues, "WARN", "SCAN_SCOPE_MISSING", f"scan_scope 路径不存在：{item}", str(candidate))
        if roots:
            return roots
    return [src]


def should_skip_relative_path(rel_path: Path) -> bool:
    ignored_parts = {
        ".git",
        ".idea",
        ".gradle",
        ".mvn",
        ".agents",
        ".understand-anything",
        ".windsurf",
        "__pycache__",
        "target",
        "build",
        "node_modules",
        "docs",
        "doc",
        "prd",
        "tests",
    }
    return any(part in ignored_parts for part in rel_path.parts)


def scan_java_file_for_entries(rel_path: str, text: str) -> list[ExpectedApi]:
    text = strip_block_comments(text)
    lines = text.splitlines()
    class_name, class_annotations = parse_top_level_class(lines)
    if not class_name:
        return []
    annotation_names = {annotation_name(item) for item in class_annotations}
    if not (annotation_names & ENTRY_CLASS_ANNOTATIONS):
        return []
    class_is_feign = "FeignClient" in annotation_names
    entry_type = "Feign Client" if class_is_feign else "HTTP Controller"
    base_path = class_base_path(class_annotations)

    entries: list[ExpectedApi] = []
    pending_annotations: list[str] = []
    idx = 0
    while idx < len(lines):
        stripped = lines[idx].strip()
        if stripped.startswith("@"):
            annotation, end_idx = collect_annotation(lines, idx)
            pending_annotations.append(annotation)
            idx = end_idx + 1
            continue
        if not stripped or stripped.startswith("}"):
            idx += 1
            continue

        signature = stripped
        sig_start_idx = idx
        while signature and not re.search(r"[{;]\s*$", signature) and idx + 1 < len(lines):
            idx += 1
            signature += " " + lines[idx].strip()
            if len(signature) > 2000:
                break

        method_name = parse_method_name(signature)
        if method_name:
            http_method, method_path = method_mapping(pending_annotations)
            if pending_annotations and any(annotation_name(item) in MAPPING_ANNOTATIONS for item in pending_annotations):
                entries.append(
                    ExpectedApi(
                        rel_path=rel_path,
                        class_name=class_name,
                        method_name=method_name,
                        entry_type=entry_type,
                        http_method=http_method,
                        path=normalize_path(base_path, method_path),
                        line=sig_start_idx + 1,
                    )
                )
            pending_annotations = []
        elif stripped and not stripped.startswith("//"):
            pending_annotations = []
        idx += 1
    return entries


def parse_top_level_class(lines: list[str]) -> tuple[str, list[str]]:
    pending_annotations: list[str] = []
    class_re = re.compile(r"\b(?:public\s+)?(?:abstract\s+)?(?:class|interface|enum)\s+(\w+)")
    idx = 0
    while idx < len(lines):
        stripped = lines[idx].strip()
        if stripped.startswith("@"):
            annotation, end_idx = collect_annotation(lines, idx)
            pending_annotations.append(annotation)
            idx = end_idx + 1
            continue
        match = class_re.search(stripped)
        if match:
            return match.group(1), pending_annotations[:]
        if stripped and not stripped.startswith("import") and not stripped.startswith("package") and not stripped.startswith("//"):
            pending_annotations = []
        idx += 1
    return "", []


def parse_method_name(signature: str) -> str:
    cleaned = re.sub(r"@\w+(?:\([^)]*\))?\s*", "", signature)
    match = re.search(
        r"\b(?:(?:public|protected|private|default|static|final|abstract|synchronized)\s+)*"
        r"(?:<[\w,\s? extends super]+>\s+)?"
        r"[\w.<>, ?\[\]]+?\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w.,\s]+)?\s*[{;]",
        cleaned,
    )
    if not match:
        return ""
    method_name = match.group(1)
    return "" if method_name in {"if", "for", "while", "switch", "catch"} else method_name


def actual_source_entries(apis: Any) -> dict[tuple[str, str, str], dict[str, Any]]:
    result: dict[tuple[str, str, str], dict[str, Any]] = {}
    if not isinstance(apis, list):
        return result
    for api in apis:
        entry = api.get("entry", {}) if isinstance(api, dict) else {}
        parsed = parse_evidence(str(entry.get("source_evidence", "")))
        if not parsed or not parsed.get("class") or not parsed.get("method"):
            continue
        key = (parsed["path"], parsed["class"], parsed["method"])
        result[key] = api
    return result


def check_source_coverage(
    expected_entries: list[ExpectedApi],
    actual_entries: dict[tuple[str, str, str], dict[str, Any]],
    apis: Any,
    issues: list[dict[str, str]],
) -> None:
    expected_keys = {item.key for item in expected_entries}
    actual_keys = set(actual_entries)
    for missing in sorted(expected_keys - actual_keys):
        expected = next(item for item in expected_entries if item.key == missing)
        add_issue(
            issues,
            "ERROR",
            "MISSING_SOURCE_API",
            f"事实文件缺少源码映射入口：{expected.class_name}.{expected.method_name} {expected.http_method} {expected.path}",
            f"{expected.rel_path}:{expected.line}",
        )

    actual_api_count = len(apis) if isinstance(apis, list) else 0
    if expected_entries and len(expected_entries) > actual_api_count:
        add_issue(
            issues,
            "ERROR",
            "API_COUNT_UNDER_SOURCE",
            f"事实 API 数量小于独立源码映射数量：事实 {actual_api_count}，源码映射 {len(expected_entries)}。",
            "summary.api_count",
        )

    unmatched_actual = actual_keys - expected_keys
    for key in sorted(unmatched_actual):
        api = actual_entries[key]
        entry = api.get("entry", {})
        if entry.get("http_method") == UNKNOWN:
            continue
        add_issue(
            issues,
            "WARN",
            "UNMATCHED_FACT_API",
            f"事实入口未被独立源码映射复扫命中：{entry.get('class_name')}.{entry.get('method_name')} {entry.get('http_method')} {entry.get('path')}",
            entry.get("source_evidence", UNKNOWN),
            "人工复核该接口是否来自动态注解、组合注解、生成源码或质检扫描规则缺口。",
        )

    expected_feign_count = sum(1 for item in expected_entries if item.entry_type == "Feign Client")
    actual_feign_count = sum(
        1 for api in apis if isinstance(api, dict) and api.get("entry", {}).get("entry_type") == "Feign Client"
    )
    if expected_feign_count != actual_feign_count:
        add_issue(
            issues,
            "ERROR",
            "FEIGN_COUNT_MISMATCH",
            f"Feign 接口数量不一致：事实 {actual_feign_count}，源码复扫 {expected_feign_count}。",
            "entry.entry_type",
        )


def check_contract_field_presence(
    src: Path,
    facts: dict[str, Any],
    apis: Any,
    issues: list[dict[str, str]],
) -> None:
    project_types = java_type_names(src, facts, issues)
    if not isinstance(apis, list):
        return
    for api in apis:
        if not isinstance(api, dict):
            continue
        entry = api.get("entry", {})
        contract = api.get("contract", {})
        request_types = split_type_names(str(entry.get("request_type", UNKNOWN)))
        if any(item in project_types for item in request_types) and not contract.get("request_fields"):
            add_issue(
                issues,
                "WARN",
                "REQUEST_FIELDS_EMPTY",
                f"{entry.get('class_name')}.{entry.get('method_name')} 的请求类型在源码中存在，但 request_fields 为空。",
                entry.get("source_evidence", UNKNOWN),
                "人工复核 DTO 字段是否来自父类、泛型、生成代码或扫描规则缺口。",
            )
        response_body = split_type_names(str(contract.get("response_body_type", UNKNOWN)))
        if any(item in project_types for item in response_body) and not contract.get("response_fields"):
            add_issue(
                issues,
                "WARN",
                "RESPONSE_FIELDS_EMPTY",
                f"{entry.get('class_name')}.{entry.get('method_name')} 的响应体类型在源码中存在，但 response_fields 为空。",
                entry.get("source_evidence", UNKNOWN),
                "人工复核 VO 字段是否来自父类、泛型、生成代码或扫描规则缺口。",
            )


def check_db_side_effect_consistency(apis: Any, issues: list[dict[str, str]]) -> None:
    if not isinstance(apis, list):
        return
    resolved_ops = {"CREATE", "UPDATE", "DELETE", "UPSERT", "READ"}
    write_ops = {"CREATE", "UPDATE", "DELETE", "UPSERT"}
    for api in apis:
        if not isinstance(api, dict):
            continue
        entry = api.get("entry", {})
        for effect in api.get("db_side_effects", []):
            operation_type = effect.get("operation_type", UNKNOWN)
            if operation_type not in resolved_ops:
                continue
            context = f"{entry.get('class_name')}.{entry.get('method_name')} {operation_type}"
            if effect.get("tables", UNKNOWN) == UNKNOWN:
                add_issue(
                    issues,
                    "ERROR",
                    "DB_TABLE_UNRESOLVED",
                    f"{context} 已识别 DB 操作，但表名仍为 UNKNOWN。",
                    effect.get("evidence", entry.get("source_evidence", UNKNOWN)),
                    "检查 RepositoryImpl、Mapper BaseMapper<DO>、DO @TableName 或 Mapper XML 表名解析。",
                )
            if effect.get("evidence", UNKNOWN) == UNKNOWN:
                add_issue(
                    issues,
                    "ERROR",
                    "DB_EVIDENCE_MISSING",
                    f"{context} 已识别 DB 操作，但缺少源码证据。",
                    entry.get("source_evidence", UNKNOWN),
                    "检查 DB 副作用是否记录到 RepositoryImpl、Mapper XML 或 SQL 注解位置。",
                )
            if operation_type in write_ops and effect.get("tables", UNKNOWN) != UNKNOWN and effect.get("side_effect_level") != "CONFIRMED":
                add_issue(
                    issues,
                    "ERROR",
                    "DB_WRITE_LEVEL_MISMATCH",
                    f"{context} 已识别写操作和表名，但副作用级别不是 CONFIRMED。",
                    effect.get("evidence", entry.get("source_evidence", UNKNOWN)),
                    "写操作表名明确时应标记为 CONFIRMED，供 DB 后置断言使用。",
                )


def java_type_names(src: Path, facts: dict[str, Any], issues: list[dict[str, str]]) -> set[str]:
    names: set[str] = set()
    class_re = re.compile(r"\b(?:class|interface|enum)\s+(\w+)")
    for root in source_roots_from_scope(src, facts, issues):
        for path in root.rglob("*.java"):
            rel_to_scan_root = safe_relative(path, root)
            if should_skip_relative_path(rel_to_scan_root):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            names.update(class_re.findall(strip_block_comments(text)))
    return names


def count_missing_source_entries(
    expected_entries: list[ExpectedApi],
    actual_entries: dict[tuple[str, str, str], dict[str, Any]],
) -> int:
    return len({item.key for item in expected_entries} - set(actual_entries))


def collect_evidence_values(value: Any) -> set[str]:
    values: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, str) and ("evidence" in key.lower() or "location" in key.lower() or key == "source_path"):
                values.add(item)
            values.update(collect_evidence_values(item))
    elif isinstance(value, list):
        for item in value:
            values.update(collect_evidence_values(item))
    elif isinstance(value, str) and EVIDENCE_RE.search(value):
        values.add(value)
    return values


def parse_evidence(value: str) -> dict[str, str] | None:
    match = EVIDENCE_RE.search(value.strip())
    if not match:
        return None
    result = {key: val for key, val in match.groupdict().items() if val}
    result["path"] = result["path"].strip().replace("\\", "/")
    return result


def resolve_source_path(src: Path, path_text: str) -> Path | None:
    candidate = Path(path_text)
    if candidate.is_absolute() and candidate.exists():
        return candidate
    relative_candidate = (src / path_text).resolve()
    if relative_candidate.exists():
        return relative_candidate
    return None


def safe_relative(path: Path, root: Path) -> Path:
    try:
        return path.resolve().relative_to(root.resolve())
    except ValueError:
        return Path(path.name)


def strip_block_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", preserve_comment_lines, text, flags=re.DOTALL)


def preserve_comment_lines(match: re.Match[str]) -> str:
    return "\n" * match.group(0).count("\n")


def collect_annotation(lines: list[str], start_idx: int) -> tuple[str, int]:
    annotation = lines[start_idx].strip()
    balance = annotation.count("(") - annotation.count(")")
    idx = start_idx
    while balance > 0 and idx + 1 < len(lines):
        idx += 1
        part = lines[idx].strip()
        annotation += " " + part
        balance += part.count("(") - part.count(")")
    return annotation, idx


def annotation_name(annotation: str) -> str:
    match = re.match(r"@([\w.]+)", annotation.strip())
    return match.group(1).split(".")[-1] if match else UNKNOWN


def extract_annotation_value(annotation: str) -> str:
    match = re.search(r"['\"]([^'\"]*)['\"]", annotation)
    return match.group(1) if match else UNKNOWN


def extract_annotation_attr(annotation: str, attr: str) -> str:
    match = re.search(rf"\b{re.escape(attr)}\s*=\s*['\"]([^'\"]*)['\"]", annotation)
    return match.group(1) if match else UNKNOWN


def class_base_path(annotations: list[str]) -> str:
    for annotation in annotations:
        name = annotation_name(annotation)
        if name == "RequestMapping":
            value = extract_annotation_value(annotation)
            return "" if value == UNKNOWN else value
        if name == "FeignClient":
            path = extract_annotation_attr(annotation, "path")
            return "" if path == UNKNOWN else path
    return ""


def method_mapping(annotations: list[str]) -> tuple[str, str]:
    for annotation in annotations:
        name = annotation_name(annotation)
        if name in HTTP_MAPPING_METHODS:
            return HTTP_MAPPING_METHODS[name], extract_annotation_value(annotation)
        if name == "RequestMapping":
            return extract_request_mapping_method(annotation), extract_annotation_value(annotation)
    return UNKNOWN, UNKNOWN


def extract_request_mapping_method(annotation: str) -> str:
    for method in ("GET", "POST", "PUT", "DELETE", "PATCH"):
        if f"RequestMethod.{method}" in annotation or f"method = {method}" in annotation:
            return method
    return UNKNOWN


def normalize_path(*parts: str) -> str:
    clean: list[str] = []
    for part in parts:
        if not part or part == UNKNOWN:
            continue
        clean.append(part.strip("/"))
    if not clean:
        return UNKNOWN
    return "/" + "/".join(part for part in clean if part)


def split_type_names(type_text: str) -> set[str]:
    if not type_text or type_text == UNKNOWN:
        return set()
    candidates = re.findall(r"\b[A-Z]\w+\b", type_text)
    primitives = {
        "String",
        "Integer",
        "Long",
        "Boolean",
        "Double",
        "Float",
        "BigDecimal",
        "List",
        "Set",
        "Map",
        "Collection",
        "Optional",
        "Void",
    }
    return {item for item in candidates if item not in primitives}


def add_issue(
    issues: list[dict[str, str]],
    level: str,
    code: str,
    message: str,
    evidence: str = UNKNOWN,
    suggestion: str = "",
) -> None:
    issues.append(
        {
            "level": level,
            "code": code,
            "message": message,
            "evidence": evidence or UNKNOWN,
            "suggestion": suggestion or "",
        }
    )


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    coverage = report["coverage"]
    lines = [
        "# 抽取后质检报告",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 源码根目录：`{report['source_root']}`",
        f"- 事实文件：`{report['facts_path']}`",
        f"- 结论：{summary['status']}",
        f"- ERROR：{summary['error_count']}",
        f"- WARN：{summary['warn_count']}",
        "",
        "## 覆盖对账",
        "",
        "| 指标 | 数量 |",
        "| --- | ---: |",
        f"| 独立源码映射数量 | {coverage['expected_api_count']} |",
        f"| 事实 API 数量 | {coverage['actual_api_count']} |",
        f"| 可定位源码入口数量 | {coverage['actual_source_entry_count']} |",
        f"| 独立源码 Feign 数量 | {coverage['expected_feign_count']} |",
        f"| 事实 Feign 数量 | {coverage['actual_feign_count']} |",
        f"| 缺失源码入口数量 | {coverage['missing_source_api_count']} |",
        "",
        "## 问题清单",
        "",
    ]
    if not report["issues"]:
        lines.append("未发现 ERROR 或 WARN。")
    else:
        lines.extend(["| 等级 | 编码 | 说明 | 证据 | 建议 |", "| --- | --- | --- | --- | --- |"])
        for issue in report["issues"]:
            lines.append(
                "| {level} | {code} | {message} | `{evidence}` | {suggestion} |".format(
                    level=escape_table(issue["level"]),
                    code=escape_table(issue["code"]),
                    message=escape_table(issue["message"]),
                    evidence=escape_table(issue["evidence"]),
                    suggestion=escape_table(issue["suggestion"]),
                )
            )
    lines.append("")
    return "\n".join(lines)


def escape_table(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def main() -> int:
    parser = argparse.ArgumentParser(description="对源码接口事实抽取结果做抽取后质检。")
    parser.add_argument("--src", required=True, help="源码根目录；如 JSON 中含 scan_scope，会按该范围复扫")
    parser.add_argument("--facts", required=True, help="source-api-facts.json 路径")
    parser.add_argument("--out", help="质检报告输出目录，默认与 facts 同目录")
    parser.add_argument("--fail-on", choices=["ERROR", "WARN", "NEVER"], default="ERROR", help="达到指定等级时返回非 0")
    args = parser.parse_args()
    report = run_quality_check(args.src, args.facts, args.out, args.fail_on)
    print(
        "抽取后质检完成："
        f"{report['summary']['status']}，"
        f"ERROR={report['summary']['error_count']}，"
        f"WARN={report['summary']['warn_count']}，"
        f"报告={Path(args.out).resolve() if args.out else Path(args.facts).resolve().parent}"
    )
    if args.fail_on == "NEVER":
        return 0
    if args.fail_on == "WARN" and (report["summary"]["error_count"] or report["summary"]["warn_count"]):
        return 1
    if args.fail_on == "ERROR" and report["summary"]["error_count"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
