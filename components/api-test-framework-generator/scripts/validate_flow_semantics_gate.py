#!/usr/bin/env python3
"""按能力校验长链路的响应断言绑定与写后有界观测。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


BUSINESS_ASSERTION_KEYS = (
    "required_fields",
    "json_equals",
    "json_not_equals",
    "json_contains",
    "json_not_contains",
    "array_length_equals",
    "array_length_min",
    "array_length_max",
)
ENVELOPE_PATHS = {"$", "$.code", "$.success", "$.message", "$.msg", "$.data"}
PAGINATION_KEYS = {
    "page",
    "pageno",
    "pageindex",
    "pagesize",
    "current",
    "currentpage",
    "size",
    "limit",
    "offset",
    "sort",
    "orderby",
    "order",
}
OBSERVATION_MODES = {
    "unique_filter",
    "detail_by_id",
    "bounded_pagination",
    "scoped_database_assertion",
}
ASSERTION_BINDING_MODES = {"same_request_variant_evidence", "response_contract_rebound"}
PLACEHOLDER_RE = re.compile(r"\$\{([^}]+)\}")


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path} 不是 UTF-8 编码: {exc}") from exc
    if "\ufffd" in content:
        raise ValueError(f"{path} 存在疑似中文乱码字符")
    loaded = yaml.safe_load(content)
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} 顶层必须是对象")
    return loaded


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _is_identity_key(key: str) -> bool:
    normalized = _normalized_key(key)
    return (
        normalized in {"id", "key", "role", "tenant", "account"}
        or normalized.endswith(("id", "key"))
        or "tenant" in normalized
        or "role" in normalized
    )


def _is_ownership_key(key: str) -> bool:
    normalized = _normalized_key(key)
    return (
        _is_identity_key(key)
        or normalized.endswith(("name", "code", "value", "number", "no", "uuid", "marker"))
    )


def _walk_leaves(value: Any, prefix: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], Any]]:
    if isinstance(value, dict):
        leaves: list[tuple[tuple[str, ...], Any]] = []
        for key, item in value.items():
            leaves.extend(_walk_leaves(item, (*prefix, str(key))))
        return leaves
    if isinstance(value, list):
        leaves = []
        for index, item in enumerate(value):
            leaves.extend(_walk_leaves(item, (*prefix, str(index))))
        return leaves
    return [(prefix, value)]


def _deep_merge(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        merged = deepcopy(base)
        for key, value in override.items():
            merged[key] = _deep_merge(merged[key], value) if key in merged else deepcopy(value)
        return merged
    return deepcopy(override)


def _assertion_path(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        path = item.get("path")
        return path if isinstance(path, str) else ""
    return ""


def _business_assertion_categories(expected: dict[str, Any]) -> set[str]:
    categories: set[str] = set()
    for key in BUSINESS_ASSERTION_KEYS:
        value = expected.get(key)
        items = _as_list(value)
        if any(_assertion_path(item) not in ENVELOPE_PATHS for item in items):
            categories.add(key)
    return categories


def _identity_variant_changed(step: dict[str, Any]) -> tuple[bool, list[str]]:
    if step.get("request_variant_changed") is True:
        return True, ["request_variant_changed"]
    paths: list[str] = []
    for field in ("request_overrides", "request_body_replace"):
        value = step.get(field)
        if not isinstance(value, dict):
            continue
        for path, _ in _walk_leaves(value):
            if path and _is_identity_key(path[-1]):
                paths.append(".".join((field, *path)))
    if "session_role" in step:
        paths.append("role_context")
    return bool(paths), paths


def _binding_is_complete(binding: Any, allowed_modes: set[str]) -> bool:
    if not isinstance(binding, dict):
        return False
    evidence_refs = binding.get("evidence_refs")
    return (
        binding.get("status") == "passed"
        and binding.get("mode") in allowed_modes
        and isinstance(evidence_refs, list)
        and bool(evidence_refs)
        and all(isinstance(item, str) and item.strip() for item in evidence_refs)
    )


def _load_cases(project_root: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    cases: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    cases_dir = project_root / "data" / "cases"
    if not cases_dir.is_dir():
        return cases, errors
    for path in sorted(cases_dir.glob("*.yaml")):
        data = _read_yaml(path)
        for case in _as_list(data.get("cases")):
            if not isinstance(case, dict):
                continue
            case_id = case.get("case_id")
            if not isinstance(case_id, str) or not case_id:
                errors.append(f"{path.name} 存在缺少 case_id 的用例")
                continue
            if case_id in cases:
                errors.append(f"用例 ID 重复：{case_id}")
                continue
            cases[case_id] = case
    return cases, errors


def _source_step(case: dict[str, Any]) -> dict[str, Any]:
    steps = _as_list(case.get("steps"))
    return steps[0] if steps and isinstance(steps[0], dict) else {}


def _validate_response_binding(
    flow_id: str,
    step: dict[str, Any],
    cases: dict[str, dict[str, Any]],
) -> tuple[bool, dict[str, Any] | None]:
    changed, changed_paths = _identity_variant_changed(step)
    if not changed:
        return False, None
    source_case_id = step.get("source_executable_case_id")
    source_case = cases.get(source_case_id)
    if source_case is None:
        return True, {
            "check_id": "response_assertion_binding",
            "flow_id": flow_id,
            "step_id": step.get("step_id"),
            "case_id": source_case_id,
            "message": "请求身份变体已改变，但找不到来源用例，无法校验响应断言绑定",
        }
    source_expected = _source_step(source_case).get("expected")
    if not isinstance(source_expected, dict):
        return True, {
            "check_id": "response_assertion_binding",
            "flow_id": flow_id,
            "step_id": step.get("step_id"),
            "case_id": source_case_id,
            "message": "请求身份变体已改变，但来源用例缺少 expected 对象",
        }
    source_categories = _business_assertion_categories(source_expected)
    if not source_categories:
        return True, None
    if _binding_is_complete(step.get("assertion_binding"), ASSERTION_BINDING_MODES):
        return True, None
    overrides = step.get("expected_overrides")
    rebound_categories = set(overrides) if isinstance(overrides, dict) else set()
    inherited_categories = sorted(source_categories - rebound_categories)
    if not inherited_categories:
        return True, None
    return True, {
        "check_id": "response_assertion_binding",
        "flow_id": flow_id,
        "step_id": step.get("step_id"),
        "case_id": source_case_id,
        "changed_identity_paths": changed_paths,
        "inherited_business_assertion_categories": inherited_categories,
        "message": "请求身份/角色变体已改变，仍继承未重新绑定的业务字段断言",
    }


def _assertion_match_items(step: dict[str, Any]) -> list[dict[str, Any]]:
    expected = step.get("expected_overrides")
    if not isinstance(expected, dict):
        return []
    items: list[dict[str, Any]] = []
    for key in ("json_contains", "json_not_contains"):
        for item in _as_list(expected.get(key)):
            if isinstance(item, dict) and isinstance(item.get("match"), dict):
                items.append(item["match"])
    return items


def _runtime_names(value: Any) -> set[str]:
    names: set[str] = set()
    for _, leaf in _walk_leaves(value):
        if isinstance(leaf, str):
            names.update(match.group(1).split(".")[-1] for match in PLACEHOLDER_RE.finditer(leaf))
    return names


def _bounded_by_request(
    request: dict[str, Any],
    matches: list[dict[str, Any]],
    producer_fields: set[str],
) -> bool:
    match_values: dict[str, set[str]] = {}
    for match in matches:
        for path, value in _walk_leaves(match):
            if path and not isinstance(value, (dict, list)):
                match_values.setdefault(_normalized_key(path[-1]), set()).add(str(value))
    for location in ("path", "query", "body", "form"):
        location_value = request.get(location)
        if not isinstance(location_value, dict):
            continue
        for path, value in _walk_leaves(location_value):
            if not path:
                continue
            key = path[-1]
            normalized = _normalized_key(key)
            if normalized in PAGINATION_KEYS or not _is_ownership_key(key):
                continue
            names = _runtime_names(value)
            if names & producer_fields:
                return True
            if str(value) in match_values.get(normalized, set()):
                return True
    return False


def _validate_write_followup(
    flow_id: str,
    steps: list[dict[str, Any]],
    cases: dict[str, dict[str, Any]],
) -> tuple[int, list[dict[str, Any]]]:
    applicable = 0
    errors: list[dict[str, Any]] = []
    produced: set[str] = set()
    for step in steps:
        matches = _assertion_match_items(step)
        consumer_fields = {item for item in _as_list(step.get("consumer_fields")) if isinstance(item, str)}
        asserted_runtime_names = _runtime_names(matches)
        linked_fields = produced & (consumer_fields | asserted_runtime_names)
        if produced and matches and linked_fields:
            applicable += 1
            binding = step.get("observation_binding")
            if _binding_is_complete(binding, OBSERVATION_MODES):
                ownership_fields = binding.get("ownership_fields")
                if isinstance(ownership_fields, list) and ownership_fields:
                    pass
                else:
                    errors.append({
                        "check_id": "bounded_write_followup_observation",
                        "flow_id": flow_id,
                        "step_id": step.get("step_id"),
                        "producer_fields": sorted(linked_fields),
                        "message": "显式观测绑定缺少 ownership_fields",
                    })
            else:
                source_case = cases.get(step.get("source_executable_case_id"), {})
                source_request = _source_step(source_case).get("request")
                request = source_request if isinstance(source_request, dict) else {}
                overrides = step.get("request_overrides")
                if isinstance(overrides, dict):
                    request = _deep_merge(request, overrides)
                if not _bounded_by_request(request, matches, linked_fields):
                    errors.append({
                        "check_id": "bounded_write_followup_observation",
                        "flow_id": flow_id,
                        "step_id": step.get("step_id"),
                        "producer_fields": sorted(linked_fields),
                        "message": "写后集合断言未通过本次运行 ID/唯一标识过滤，也未声明有证据的有界观测",
                    })
        producer_fields = {item for item in _as_list(step.get("producer_fields")) if isinstance(item, str)}
        if step.get("sql_runtime_extract") is True or producer_fields:
            produced.update(producer_fields)
    return applicable, errors


def validate_project(project_root: Path) -> dict[str, Any]:
    cases, structural_errors = _load_cases(project_root)
    flow_file = project_root / "data" / "flow_cases.yaml"
    if not flow_file.exists():
        return {
            "schema_version": 1,
            "gate": "flow_runtime_semantics",
            "status": "failed" if structural_errors else "not_required",
            "checks": {
                "response_assertion_binding": {"status": "not_required", "applicable_step_count": 0},
                "bounded_write_followup_observation": {"status": "not_required", "applicable_step_count": 0},
            },
            "errors": structural_errors,
        }
    flow_data = _read_yaml(flow_file)
    flows = [item for item in _as_list(flow_data.get("flows")) if isinstance(item, dict)]
    binding_applicable = 0
    observation_applicable = 0
    errors: list[Any] = list(structural_errors)
    for flow in flows:
        flow_id = str(flow.get("flow_id", ""))
        steps = [item for item in _as_list(flow.get("steps")) if isinstance(item, dict)]
        for step in steps:
            applicable, error = _validate_response_binding(flow_id, step, cases)
            binding_applicable += int(applicable)
            if error:
                errors.append(error)
        count, observation_errors = _validate_write_followup(flow_id, steps, cases)
        observation_applicable += count
        errors.extend(observation_errors)
    binding_errors = [item for item in errors if isinstance(item, dict) and item.get("check_id") == "response_assertion_binding"]
    observation_errors = [item for item in errors if isinstance(item, dict) and item.get("check_id") == "bounded_write_followup_observation"]
    return {
        "schema_version": 1,
        "gate": "flow_runtime_semantics",
        "status": "failed" if errors else ("passed" if binding_applicable or observation_applicable else "not_required"),
        "checks": {
            "response_assertion_binding": {
                "status": "failed" if binding_errors else ("passed" if binding_applicable else "not_required"),
                "applicable_step_count": binding_applicable,
                "error_count": len(binding_errors),
            },
            "bounded_write_followup_observation": {
                "status": "failed" if observation_errors else ("passed" if observation_applicable else "not_required"),
                "applicable_step_count": observation_applicable,
                "error_count": len(observation_errors),
            },
        },
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="校验长链路响应绑定与写后有界观测")
    parser.add_argument("project_root", type=Path, help="生成的 api-test-framework 根目录")
    parser.add_argument("--output", type=Path, help="可选的 JSON 审计输出路径")
    args = parser.parse_args()
    try:
        report = validate_project(args.project_root.resolve())
    except (OSError, ValueError, yaml.YAMLError) as exc:
        report = {
            "schema_version": 1,
            "gate": "flow_runtime_semantics",
            "status": "failed",
            "checks": {},
            "errors": [str(exc)],
        }
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0 if report["status"] in {"passed", "not_required"} else 1


if __name__ == "__main__":
    sys.exit(main())
