from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


TEMPLATE_ROOT = Path(__file__).parent.parent / "assets/api-test-framework-template"
CASE_LOADER = TEMPLATE_ROOT / "core/case_loader.py"


def load_case_loader(monkeypatch):
    monkeypatch.syspath_prepend(str(TEMPLATE_ROOT))
    sys.modules.pop("utils", None)
    sys.modules.pop("utils.yaml_util", None)
    spec = importlib.util.spec_from_file_location("case_loader_template_contract_test", CASE_LOADER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_case_loader_preserves_runtime_materialization_fields(tmp_path: Path, monkeypatch) -> None:
    loader = load_case_loader(monkeypatch)
    raw_case = {
        "case_id": "CASE-SPECIAL",
        "interface_id": "API-SPECIAL",
        "session_role": "operator",
        "account_group_key": "operator-group",
        "required_session_roles": ["operator"],
        "preconditions": [{"type": "api", "name": "准备数据"}],
        "cleanup": [{"type": "api", "name": "清理数据"}],
        "specialized_runner_id": "stateful_runner",
        "specialized_runner_config": {"mode": "safe"},
        "specialized_runner_assertions": {"true_fields": ["success"]},
        "assertion_strength": "L5_cleanup_verified",
        "result_observation_mode": "api_followup_and_restore",
        "setup_cleanup_materialization": {"status": "api_state_restore"},
    }
    case_file = loader.ROOT_DIR / "data/cases/special.yaml"
    case = loader.build_case_parameter(
        raw_case,
        {"API-SPECIAL": {"method": "POST", "path": "/special"}},
        case_file,
        set(),
    )

    assert case["specialized_runner_id"] == "stateful_runner"
    assert case["session_role"] == "operator"
    assert case["preconditions"][0]["name"] == "准备数据"
    assert case["cleanup"][0]["name"] == "清理数据"
    assert case["assertion_strength"] == "L5_cleanup_verified"
    assert case["sql_fixture_required"] is False


def test_case_loader_attaches_api_setup_cleanup_markers_without_sql_marker(monkeypatch) -> None:
    loader = load_case_loader(monkeypatch)
    case = {
        "case_id": "CASE-API-RESTORE",
        "flow_type": "main",
        "preconditions": [{"type": "api", "name": "准备数据"}],
        "cleanup": [{"type": "api", "name": "清理数据"}],
        "sql_fixture_required": False,
        "live_pytest_release_ready": True,
        "automation_decision": "runnable",
    }
    monkeypatch.setattr(loader, "load_case_parameters", lambda: [case])

    parameter = loader.load_case_pytest_parameters()[0]
    marker_names = {mark.name for mark in parameter.marks}

    assert marker_names == {"main_flow", "preconditions", "cleanup"}


def test_api_cleanup_required_boolean_does_not_enable_sql_fixture(monkeypatch) -> None:
    loader = load_case_loader(monkeypatch)
    materialization = {
        "status": "api_cleanup_by_current_run_id",
        "closure_mode": "api_cleanup",
        "cleanup_required": True,
    }

    assert loader.materialization_requires_sql(materialization, "setup_cleanup_materialization") is False


def test_explicit_nested_sql_boolean_enables_sql_fixture(monkeypatch) -> None:
    loader = load_case_loader(monkeypatch)

    assert loader.materialization_requires_sql(
        {"status": "passed", "sql_required": True},
        "setup_cleanup_materialization",
    ) is True
