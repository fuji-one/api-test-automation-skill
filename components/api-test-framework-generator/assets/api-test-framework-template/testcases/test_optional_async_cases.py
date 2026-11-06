import time
from typing import Any, Dict, List

import allure
import pytest

from core.case_loader import INTERFACE_FILES, ROOT_DIR, build_case_parameter, load_case_records, load_interface_index
from testcases.test_api_cases import _apply_confidence_labels, _execute_step


OPTIONAL_ASYNC_CASE_FILE = ROOT_DIR / "data" / "optional_async_cases.yaml"


def load_optional_async_pytest_parameters() -> List[Any]:
    interface_index = load_interface_index(INTERFACE_FILES)
    raw_cases = load_case_records(OPTIONAL_ASYNC_CASE_FILE)
    if not isinstance(raw_cases, list):
        raise ValueError(f"可选慢异步用例文件必须包含 cases 列表：{OPTIONAL_ASYNC_CASE_FILE}")

    params: List[Any] = []
    for raw_case in raw_cases:
        case_data = build_case_parameter(raw_case, interface_index, OPTIONAL_ASYNC_CASE_FILE)
        case_data["optional_async"] = raw_case.get("optional_async")
        case_data["async_observation"] = raw_case.get("async_observation") or {}
        case_data["assertion_strength"] = raw_case.get("assertion_strength")
        case_data["result_observation_mode"] = raw_case.get("result_observation_mode")
        case_data["setup_cleanup_materialization"] = raw_case.get("setup_cleanup_materialization")
        case_data["db_assertion_materialization"] = raw_case.get("db_assertion_materialization")
        case_data["sql_fixture_required"] = bool(
            raw_case.get("sql_fixture_required")
            or raw_case.get("setup_cleanup_materialization")
            or raw_case.get("db_assertion_materialization")
        )
        marks = [
            pytest.mark.optional_async,
            pytest.mark.main_flow,
        ]
        if case_data.get("sql_fixture_required"):
            marks.append(pytest.mark.case_id(case_data["case_id"]))
        params.append(pytest.param(case_data, marks=tuple(marks), id=case_data["case_id"]))
    return params


@allure.feature("optional_async")
@pytest.mark.parametrize("case_data", load_optional_async_pytest_parameters())
def test_optional_async_case(
    authenticated_client,
    case_data_manager,
    case_sql_manager,
    env_config,
    runtime_context,
    auth_contexts,
    pytestconfig,
    case_data,
):
    """执行默认不收集的慢异步用例，用于验证延迟队列窗口后的业务结果。"""
    allure.dynamic.title(case_data["title"])
    allure.dynamic.feature((case_data.get("allure") or {}).get("feature", "optional_async"))
    allure.dynamic.story((case_data.get("allure") or {}).get("story", case_data["title"]))
    allure.dynamic.severity((case_data.get("allure") or {}).get("severity", "normal"))
    _apply_confidence_labels(case_data)
    for key, value in (env_config.get("runtime_variables") or {}).items():
        runtime_context.setdefault(key, value)
    for step in case_data.get("steps") or []:
        _execute_step(authenticated_client, env_config, runtime_context, auth_contexts, step)

    wait_seconds = _resolve_optional_async_wait_seconds(pytestconfig, case_data)
    if wait_seconds > 0:
        with allure.step(f"等待慢异步消费窗口：{wait_seconds} 秒"):
            time.sleep(wait_seconds)


def _resolve_optional_async_wait_seconds(pytestconfig: pytest.Config, case_data: Dict[str, Any]) -> int:
    override_value = pytestconfig.getoption("--slow-async-wait-seconds")
    if override_value not in (None, ""):
        wait_seconds = int(override_value)
    else:
        wait_seconds = int((case_data.get("async_observation") or {}).get("wait_seconds", 0))
    if wait_seconds < 0:
        raise ValueError("慢异步等待秒数不能小于 0")
    return wait_seconds
