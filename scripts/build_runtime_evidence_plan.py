#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build generic runtime-evidence planning sidecars from interface case lists.

This script deliberately avoids project-specific values. It only classifies
runtime execution risk from generic signals such as HTTP method, path/name
semantics, declared case type, and source side-effect hints.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - exercised only when PyYAML is absent.
    yaml = None


READ_METHODS = {"GET", "HEAD", "OPTIONS"}
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

READ_KEYWORDS = {
    "get",
    "list",
    "query",
    "search",
    "detail",
    "details",
    "count",
    "config",
    "profile",
    "status",
    "history",
    "record",
    "page",
    "fetch",
    "读取",
    "查询",
    "列表",
    "详情",
    "分页",
    "搜索",
    "统计",
    "配置",
    "状态",
    "记录",
    "历史",
}

AUTH_KEYWORDS = {
    "login",
    "signin",
    "sign_in",
    "token",
    "auth",
    "oauth",
    "session",
    "captcha",
    "verify_code",
    "verification",
    "登录",
    "认证",
    "验证码",
    "换取令牌",
    "刷新令牌",
}

MUTATION_KEYWORDS = {
    "create",
    "add",
    "save",
    "update",
    "edit",
    "modify",
    "submit",
    "send",
    "publish",
    "bind",
    "unbind",
    "cancel",
    "confirm",
    "approve",
    "reject",
    "audit",
    "upload",
    "start",
    "stop",
    "finish",
    "complete",
    "创建",
    "新增",
    "保存",
    "修改",
    "更新",
    "提交",
    "发送",
    "发布",
    "绑定",
    "解绑",
    "取消",
    "确认",
    "审核",
    "上传",
    "开始",
    "结束",
    "完成",
}

DESTRUCTIVE_KEYWORDS = {
    "delete",
    "remove",
    "destroy",
    "deactivate",
    "disable",
    "freeze",
    "blacklist",
    "block",
    "logout",
    "withdraw",
    "refund",
    "chargeback",
    "pay",
    "payment",
    "recharge",
    "扣款",
    "支付",
    "充值",
    "提现",
    "退款",
    "删除",
    "移除",
    "注销",
    "禁用",
    "冻结",
    "拉黑",
    "封禁",
}

EXTERNAL_KEYWORDS = {
    "callback",
    "notify",
    "webhook",
    "third",
    "thirdparty",
    "third_party",
    "sdk",
    "apple",
    "wechat",
    "weixin",
    "alipay",
    "google",
    "oss",
    "cos",
    "s3",
    "push",
    "mq",
    "kafka",
    "rocketmq",
    "回调",
    "通知",
    "第三方",
    "外部",
    "苹果",
    "微信",
    "支付宝",
    "对象存储",
    "消息队列",
}

RUNTIME_RISK_LEVELS = (
    "safe_readonly",
    "auth_setup",
    "mutation_requires_cleanup",
    "destructive_state",
    "external_or_callback",
    "unknown_requires_review",
)
RUNTIME_REQUEST_DECISIONS = (
    "request_allowed",
    "request_allowed_with_user_config",
    "manual_confirmation_required",
    "blocked_until_isolated_account_and_cleanup",
)


def load_structured(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text) or {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return fallback_case_list(text)


def fallback_case_list(text: str) -> Dict[str, Any]:
    """Best-effort parser for simple YAML case lists when PyYAML is absent."""
    cases: List[Dict[str, Any]] = []
    chunks = re.split(r"(?m)^\s*-\s+case_id\s*:\s*", text)
    for chunk in chunks[1:]:
        first, _, rest = chunk.partition("\n")
        case: Dict[str, Any] = {"case_id": strip_scalar(first)}
        for key in ("name", "case_name", "case_type", "priority", "method", "path", "module"):
            match = re.search(rf"(?m)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", rest)
            if match:
                case[key] = strip_scalar(match.group(1))
        cases.append(case)
    return {"cases": cases}


def strip_scalar(value: Any) -> str:
    text = str(value).strip()
    if (text.startswith("'") and text.endswith("'")) or (
        text.startswith('"') and text.endswith('"')
    ):
        return text[1:-1]
    return text


def dump_structured(data: Dict[str, Any], path: Path) -> None:
    if yaml is not None:
        path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_cases(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        raw_cases = data
    elif isinstance(data, dict):
        raw_cases = []
        for key in ("cases", "case_list", "items", "test_cases", "interface_cases"):
            value = data.get(key)
            if isinstance(value, list):
                raw_cases = value
                break
        if not raw_cases and all(k in data for k in ("case_id", "name")):
            raw_cases = [data]
    else:
        raw_cases = []

    cases: List[Dict[str, Any]] = []
    for index, raw in enumerate(raw_cases, start=1):
        if not isinstance(raw, dict):
            continue
        case = dict(raw)
        case.setdefault("case_id", f"CASE-{index:04d}")
        case.setdefault("name", case.get("case_name") or case.get("title") or case["case_id"])
        case["method"] = str(case.get("method") or case.get("http_method") or "").upper()
        case["path"] = str(case.get("path") or case.get("url") or case.get("endpoint") or "")
        case["_source_index"] = index - 1
        cases.append(case)
    return cases


def flatten_text(value: Any) -> Iterable[str]:
    if value is None:
        return []
    if isinstance(value, (str, int, float, bool)):
        return [str(value)]
    if isinstance(value, dict):
        out: List[str] = []
        for key, item in value.items():
            out.extend(flatten_text(key))
            out.extend(flatten_text(item))
        return out
    if isinstance(value, list):
        out = []
        for item in value:
            out.extend(flatten_text(item))
        return out
    return [str(value)]


def has_keyword(text: str, keywords: Iterable[str]) -> bool:
    normalized = text.lower()
    return any(keyword.lower() in normalized for keyword in keywords)


def classify_case(case: Dict[str, Any]) -> Dict[str, Any]:
    method = str(case.get("method") or "").upper()
    text = " ".join(flatten_text(case))

    is_external = has_keyword(text, EXTERNAL_KEYWORDS)
    is_destructive = method == "DELETE" or has_keyword(text, DESTRUCTIVE_KEYWORDS)
    is_auth = has_keyword(text, AUTH_KEYWORDS)
    is_read_semantic = has_keyword(text, READ_KEYWORDS)
    is_mutation_semantic = has_keyword(text, MUTATION_KEYWORDS)
    is_read_method = method in READ_METHODS
    is_write_method = method in WRITE_METHODS

    if is_external:
        return {
            "risk_level": "external_or_callback",
            "request_decision": "manual_confirmation_required",
            "reason_codes": ["external_dependency_or_callback_channel"],
            "cleanup_required": False,
            "db_probe_required": False,
        }
    if is_destructive:
        return {
            "risk_level": "destructive_state",
            "request_decision": "blocked_until_isolated_account_and_cleanup",
            "reason_codes": ["destructive_or_financial_state_change"],
            "cleanup_required": True,
            "db_probe_required": True,
        }
    if is_auth:
        return {
            "risk_level": "auth_setup",
            "request_decision": "request_allowed_with_user_config",
            "reason_codes": ["authentication_or_session_setup"],
            "cleanup_required": False,
            "db_probe_required": False,
        }
    if is_read_method or (is_read_semantic and not is_mutation_semantic):
        return {
            "risk_level": "safe_readonly",
            "request_decision": "request_allowed",
            "reason_codes": ["readonly_semantics_detected"],
            "cleanup_required": False,
            "db_probe_required": False,
        }
    if is_write_method or is_mutation_semantic:
        return {
            "risk_level": "mutation_requires_cleanup",
            "request_decision": "manual_confirmation_required",
            "reason_codes": ["state_mutation_requires_db_before_after_and_cleanup"],
            "cleanup_required": True,
            "db_probe_required": True,
        }
    return {
        "risk_level": "unknown_requires_review",
        "request_decision": "manual_confirmation_required",
        "reason_codes": ["insufficient_method_or_semantic_signal"],
        "cleanup_required": False,
        "db_probe_required": False,
    }


def compact_case_ref(case: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "case_id": str(case.get("case_id", "")),
        "name": str(case.get("name", "")),
        "priority": str(case.get("priority", "")),
        "case_type": str(case.get("case_type", "")),
        "module": str(case.get("module", "")),
        "method": str(case.get("method", "")),
        "path": str(case.get("path", "")),
    }


def is_long_chain_case(case: Dict[str, Any]) -> bool:
    text = " ".join(flatten_text(case)).lower()
    explicit_flags = (
        case.get("flow_id"),
        case.get("required_flow_id"),
        case.get("required_chain_flow_id"),
    )
    if any(value not in (None, "", [], {}) for value in explicit_flags):
        return True
    if str(case.get("flow_generation_required", "")).lower() in {"true", "yes", "1", "是"}:
        return True
    return any(keyword in text for keyword in ("long_chain", "chain", "e2e", "flow", "长链路", "链路", "流程"))


def priority_bucket_for(case: Dict[str, Any]) -> str:
    if is_long_chain_case(case):
        return "long_chain"
    priority = str(case.get("priority") or "").strip().lower()
    if priority in {"p0", "p1", "p2", "p3"}:
        return priority
    return "other"


def runtime_priority_sort_key(case: Dict[str, Any]) -> tuple[int, int]:
    bucket_rank = {"long_chain": 0, "p0": 1, "p1": 2, "p2": 3, "p3": 4, "other": 5}
    return (bucket_rank[priority_bucket_for(case)], int(case.get("_source_index", 0)))


def order_runtime_cases(cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(cases, key=runtime_priority_sort_key)


def build_outputs(cases: List[Dict[str, Any]], env_name: str) -> Dict[str, Dict[str, Any]]:
    audit_items: List[Dict[str, Any]] = []
    request_steps: List[Dict[str, Any]] = []
    db_probes: List[Dict[str, Any]] = []
    blockers: List[Dict[str, Any]] = []

    ordered_cases = order_runtime_cases(cases)
    for index, case in enumerate(ordered_cases, start=1):
        source_index = int(case.get("_source_index", index - 1))
        risk = classify_case(case)
        priority_bucket = priority_bucket_for(case)
        item_id = f"RISK-{index:04d}"
        item = {
            "item_id": item_id,
            **compact_case_ref(case),
            "priority_bucket": priority_bucket,
            **risk,
            "source_case_ref": f"case_list.yaml#/cases/{source_index}",
        }
        audit_items.append(item)

        if risk["request_decision"] in {"request_allowed", "request_allowed_with_user_config"}:
            request_steps.append(
                {
                    "step_id": f"STEP-{index:04d}",
                    "case_id": item["case_id"],
                    "name": item["name"],
                    "priority_bucket": priority_bucket,
                    "module": item["module"] or "${MODULE_ALIAS}",
                    "method": item["method"] or "${HTTP_METHOD}",
                    "path": item["path"] or "${REQUEST_PATH}",
                    "risk_level": risk["risk_level"],
                    "request_decision": risk["request_decision"],
                    "cleanup_required": risk["cleanup_required"],
                    "expected_status": case.get("expected_status", "${EXPECTED_HTTP_STATUS}"),
                    "headers": "${RUNTIME_HEADERS}",
                    "query": "${RUNTIME_QUERY}",
                    "body": "${RUNTIME_BODY}",
                    "assertions_ref": f"case_list.yaml#/cases/{source_index}",
                    "extract": {},
                    "execution_status": "needs_runtime_values",
                    "risk_audit_ref": f"runtime_risk_audit.yaml#/items/{index - 1}",
                }
            )

        if risk["db_probe_required"]:
            db_probes.append(
                {
                    "probe_id": f"DBP-{index:04d}",
                    "case_id": item["case_id"],
                    "name": item["name"],
                    "probe_strategy": "before_after_snapshot_required",
                    "ownership_key_required": True,
                    "expected_delta_source_ref": f"case_list.yaml#/cases/{source_index}",
                    "cleanup_strategy_required": True,
                    "risk_audit_ref": f"runtime_risk_audit.yaml#/items/{index - 1}",
                }
            )

        if risk["request_decision"].startswith("manual") or risk["request_decision"].startswith("blocked"):
            blockers.append(
                {
                    "blocker_id": f"RTB-{index:04d}",
                    "case_id": item["case_id"],
                    "name": item["name"],
                    "risk_level": risk["risk_level"],
                    "reason_codes": risk["reason_codes"],
                    "needed_input": needed_input_for(risk),
                    "risk_audit_ref": f"runtime_risk_audit.yaml#/items/{index - 1}",
                }
            )

    summary_counts = Counter(item["risk_level"] for item in audit_items)
    decision_counts = Counter(item["request_decision"] for item in audit_items)
    summary = {risk_level: summary_counts.get(risk_level, 0) for risk_level in RUNTIME_RISK_LEVELS}
    decision_summary = {
        decision: decision_counts.get(decision, 0)
        for decision in RUNTIME_REQUEST_DECISIONS
    }
    request_plan_status = "ready_for_manual_completion" if request_steps else "blocked_no_allowed_request"

    return {
        "runtime_risk_audit.yaml": {
            "schema_version": 1,
            "stage": "runtime_evidence_planning",
            "status": "passed",
            "next_stage_allowed": True,
            "risk_summary": summary,
            "request_decision_summary": decision_summary,
            "execution_authorization": {
                "case_scope_default_authorized": False,
                "environment_default": "test",
                "env_name": env_name,
                "is_test_environment": True,
                "scope": "selected_case_denominator",
                "source_type": "none",
                "source_ref": "",
            },
            "db_authorization": {
                "allow_source_bound_before_after_query": False,
                "allow_current_run_cleanup": False,
                "non_test_reauthorization_required": False,
                "non_test_reauthorization_status": "not_required",
                "source_ref": "",
            },
            "classification_policy": {
                "source_signals": [
                    "http_method",
                    "path_semantics",
                    "case_name_semantics",
                    "case_type",
                    "source_side_effect_hints",
                ],
                "project_specific_values_allowed": False,
                "blind_all_interface_execution_allowed": False,
            },
            "items": audit_items,
        },
        "runtime_request_plan.skeleton.yaml": {
            "schema_version": 1,
            "stage": "runtime_request_plan_skeleton",
            "status": request_plan_status,
            "next_stage_allowed": False,
            "env": {
                "env_name": env_name,
                "base_urls": {},
                "secrets_ref": "${RUNTIME_SECRETS_JSON}",
            },
            "request_scope": {
                "mutating_requests_allowed": False,
                "execute_only_request_allowed_items": True,
                "cleanup_required_before_mutation": True,
            },
            "steps": request_steps,
        },
        "db_before_after_probe_plan.yaml": {
            "schema_version": 1,
            "stage": "db_before_after_probe_planning",
            "status": "ready" if db_probes else "not_required",
            "next_stage_allowed": True,
            "probe_policy": {
                "db_mcp_only_for_evidence_collection": True,
                "scripts_must_consume_normalized_sidecars": True,
                "ownership_keys_required_for_mutation": True,
                "cleanup_graph_required_for_mutation": True,
            },
            "probes": db_probes,
        },
        "runtime_blocker_candidates.yaml": {
            "schema_version": 1,
            "stage": "runtime_blocker_candidate_collection",
            "status": "has_blockers" if blockers else "passed",
            "next_stage_allowed": True,
            "blocking_items": blockers,
        },
    }


def needed_input_for(risk: Dict[str, Any]) -> List[str]:
    risk_level = risk["risk_level"]
    if risk_level == "destructive_state":
        return [
            "isolated_test_account_or_resource_scope",
            "db_before_after_snapshot",
            "cleanup_strategy",
            "manual_execution_confirmation",
        ]
    if risk_level == "mutation_requires_cleanup":
        return [
            "db_before_after_snapshot",
            "ownership_key",
            "cleanup_strategy",
            "manual_execution_confirmation",
        ]
    if risk_level == "external_or_callback":
        return [
            "safe_external_dependency_strategy",
            "callback_or_mock_confirmation",
            "manual_execution_confirmation",
        ]
    return ["manual_execution_confirmation"]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build generic runtime evidence planning sidecars."
    )
    parser.add_argument("--case-list", required=True, help="Path to case_list.yaml/json.")
    parser.add_argument("--output-dir", required=True, help="Output directory for planning sidecars.")
    parser.add_argument("--env-name", default="${ENV_NAME}", help="Logical runtime environment name.")
    args = parser.parse_args(argv)

    case_list_path = Path(args.case_list)
    output_dir = Path(args.output_dir)
    data = load_structured(case_list_path)
    cases = normalize_cases(data)
    if not cases:
        raise SystemExit(f"No cases found in {case_list_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = build_outputs(cases, args.env_name)
    for filename, payload in outputs.items():
        dump_structured(payload, output_dir / filename)

    print(
        json.dumps(
            {
                "status": "ok",
                "case_count": len(cases),
                "output_dir": str(output_dir),
                "files": sorted(outputs.keys()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
