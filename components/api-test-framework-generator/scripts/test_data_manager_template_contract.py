from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


TEMPLATE_ROOT = Path(__file__).parent.parent / "assets/api-test-framework-template"
DATA_MANAGER = TEMPLATE_ROOT / "core/data_manager.py"


def load_data_manager(monkeypatch):
    monkeypatch.syspath_prepend(str(TEMPLATE_ROOT))
    sys.modules.pop("core", None)
    spec = importlib.util.spec_from_file_location("data_manager_template_contract_test", DATA_MANAGER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class NoRequestClient:
    auth_context = {"enabled": False}

    def request(self, **kwargs):
        raise AssertionError(f"变量缺失时不应执行清理请求：{kwargs}")


def test_cleanup_skips_only_when_declared_runtime_variable_is_missing(monkeypatch) -> None:
    module = load_data_manager(monkeypatch)
    executor = module.DataRuleExecutor(NoRequestClient(), {})
    rule = {
        "type": "api",
        "name": "按本轮 id 清理",
        "method": "DELETE",
        "path": "/items/${id}",
        "expected_status": 204,
        "skip_if_missing_runtime_vars": ["id"],
        "cleanup_identity": {"field": "id", "value_ref": "path.id"},
    }

    assert executor.cleanup([rule]) == []


def test_cleanup_skip_variables_must_be_valid_names(monkeypatch) -> None:
    module = load_data_manager(monkeypatch)
    executor = module.DataRuleExecutor(NoRequestClient(), {})

    try:
        executor.cleanup([{"skip_if_missing_runtime_vars": ["invalid-name"]}])
    except ValueError as exc:
        assert "Python 标识符" in str(exc)
    else:
        raise AssertionError("非法变量名必须被拒绝")
