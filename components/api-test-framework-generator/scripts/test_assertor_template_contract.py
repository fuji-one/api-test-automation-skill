from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ASSERTOR = Path(__file__).parent.parent / "assets/api-test-framework-template/core/assertor.py"


def load_assertor():
    spec = importlib.util.spec_from_file_location("assertor_template_contract_test", ASSERTOR)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.Assertor


def test_normalize_assertion_rules_accepts_list_and_mapping() -> None:
    assertor = load_assertor()

    assert assertor.normalize_assertion_rules([{"path": "$.code", "value": 200}], "value") == [
        {"path": "$.code", "value": 200}
    ]
    assert assertor.normalize_assertion_rules({"$.code": 200}, "value") == [
        {"path": "$.code", "value": 200}
    ]


def test_normalize_assertion_rules_rejects_incomplete_rule() -> None:
    assertor = load_assertor()

    with pytest.raises(ValueError, match="缺少 value"):
        assertor.normalize_assertion_rules([{"path": "$.code"}], "value")
