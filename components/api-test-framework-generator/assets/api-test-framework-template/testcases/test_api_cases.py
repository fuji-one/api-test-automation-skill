import copy
from typing import Any, Dict

import allure
import pytest

from core.assertor import Assertor
from core.auth_manager import AuthManager
from core.case_loader import load_case_pytest_parameters
from core.extractor import Extractor
from core.runtime_context import publish_runtime_value, resolve_runtime_value
from core.specialized_runner import resolve_specialized_runner_id, run_specialized_runner


def case_id(case_data):
    return case_data["case_id"]


@allure.feature("api")
@pytest.mark.parametrize("case_data", load_case_pytest_parameters(), ids=case_id)
def test_api_case(
    authenticated_client,
    case_account_login,
    case_data_manager,
    case_sql_manager,
    env_config,
    runtime_context,
    auth_contexts,
    case_data,
):
    """参数化执行普通接口用例，维护入口集中在 data/cases 和 data/interfaces.*。"""

    allure.dynamic.title(case_data["title"])
    allure.dynamic.feature((case_data.get("allure") or {}).get("feature", "api"))
    allure.dynamic.story((case_data.get("allure") or {}).get("story", case_data["title"]))
    allure.dynamic.severity((case_data.get("allure") or {}).get("severity", "normal"))
    _apply_confidence_labels(case_data)
    for key, value in (env_config.get("runtime_variables") or {}).items():
        runtime_context.setdefault(key, value)
    if resolve_specialized_runner_id(case_data):
        run_specialized_runner(
            case_data,
            authenticated_client,
            env_config,
            runtime_context,
            auth_contexts,
        )
        return
    steps = case_data.get("steps") or [
        {
            "title": case_data["title"],
            "method": case_data["method"],
            "path": case_data["path"],
            "module": case_data.get("module"),
            "session_role": case_data.get("session_role") or "default",
            "request": case_data.get("request") or {},
            "expected": case_data.get("expected") or {},
        }
    ]
    for step in steps:
        _execute_step(authenticated_client, env_config, runtime_context, auth_contexts, step)


def _apply_confidence_labels(case_data: Dict[str, Any]) -> None:
    """将证据置信度投影到 Allure，且不参与执行分支。"""

    allure.dynamic.label("confidence_score", str(case_data["confidence_score"]))
    allure.dynamic.label("confidence_level", str(case_data["confidence_level"]))


def _execute_step(authenticated_client, env_config: Dict[str, Any], runtime_context: Dict[str, Any], auth_contexts: Dict[str, Dict[str, Any]], step: Dict[str, Any]) -> Any:
    role = step.get("session_role") or "default"
    auth_context = _select_auth_context(auth_contexts, role)
    active_context = _build_active_runtime_context(runtime_context, env_config, role, auth_context)
    authenticated_client.set_auth_context(auth_context)
    request_data = resolve_runtime_value(copy.deepcopy(step.get("request") or {}), active_context, env_config)
    resolved_path = resolve_runtime_value(step["path"], active_context, env_config)
    if not isinstance(resolved_path, str):
        raise TypeError("步骤 path 解析结果必须是字符串")
    response = authenticated_client.request(
        step["method"],
        resolved_path,
        module=step.get("module"),
        headers=request_data.get("headers") or {},
        params=request_data.get("query") or {},
        json=request_data.get("body") or None,
    )
    expected = step.get("expected") or {}
    Assertor.status_code(response, expected.get("status_code", 200))
    payload = response.json() if response.text else {}
    business_path = expected.get("business_code_path")
    if business_path and expected.get("business_code") is not None:
        Assertor.json_path_equal(payload, _normalize_json_path(business_path), expected.get("business_code"))
    for rule in Assertor.normalize_assertion_rules(expected.get("json_equals"), "value"):
        Assertor.json_path_equal(payload, _normalize_json_path(rule["path"]), rule["value"])
    for rule in Assertor.normalize_assertion_rules(expected.get("array_length_equals"), "length"):
        Assertor.array_length_equal(payload, _normalize_json_path(rule["path"]), rule["length"])
    for rule in Assertor.normalize_assertion_rules(expected.get("string_min_lengths"), "min_length"):
        Assertor.string_min_length(payload, _normalize_json_path(rule["path"]), rule["min_length"])
    Assertor.required_fields(payload, [_normalize_json_path(field) for field in expected.get("required_fields") or []])
    _extract_step_values(authenticated_client, runtime_context, auth_contexts, step, payload)
    return payload


def _select_auth_context(auth_contexts: Dict[str, Dict[str, Any]], role: str) -> Dict[str, Any]:
    if role == "none":
        return {"enabled": False}
    if role not in auth_contexts:
        raise ValueError(f"用例声明了未配置的 session_role：{role}")
    return auth_contexts[role]


def _build_active_runtime_context(runtime_context: Dict[str, Any], env_config: Dict[str, Any], role: str, auth_context: Dict[str, Any]) -> Dict[str, Any]:
    active_context: Dict[str, Any] = {}
    active_context.update(env_config.get("runtime_variables") or {})
    active_context.update(runtime_context)
    active_context.update(runtime_context.get(f"{role}_context") or {})
    if auth_context.get("enabled"):
        active_context["auth_token"] = auth_context.get("token_value")
        if auth_context.get("session_secret"):
            active_context["session_secret"] = auth_context.get("session_secret")
        if auth_context.get("hash_user_id"):
            active_context["hash_user_id"] = auth_context.get("hash_user_id")
        if auth_context.get("user_id") is not None:
            active_context["login_user_id"] = auth_context.get("user_id")
            active_context["appUserId"] = auth_context.get("user_id")
            active_context["userId"] = auth_context.get("user_id")
    return active_context


def _extract_step_values(
    authenticated_client,
    runtime_context: Dict[str, Any],
    auth_contexts: Dict[str, Dict[str, Any]],
    step: Dict[str, Any],
    payload: Dict[str, Any],
) -> None:
    extract = step.get("extract") or {}
    if not extract:
        return
    if not isinstance(extract, dict):
        raise TypeError("步骤 extract 必须是变量名到 JSONPath 的对象")

    values: Dict[str, Any] = {}
    for name, path in extract.items():
        if not isinstance(path, str) or not path.strip():
            raise ValueError(f"步骤抽取路径不能为空：{name}")
        values[name] = Extractor.extract_json_value(payload, _normalize_json_path(path))
        publish_runtime_value(runtime_context, name, values[name])

    if step.get("step_type") in {"auth", "login"}:
        target_role = (step.get("account_context") or {}).get("role") or step.get("session_role")
        AuthManager.apply_login_step_context(
            str(target_role or ""),
            values,
            authenticated_client,
            runtime_context,
            auth_contexts,
        )


def _normalize_json_path(path: str) -> str:
    if path == "$":
        return path
    if path.startswith("$."):
        return path[2:]
    return path
