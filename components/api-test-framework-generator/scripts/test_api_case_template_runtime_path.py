from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


TEMPLATE_ROOT = Path(__file__).parent.parent / "assets/api-test-framework-template"
TEST_ENTRY = TEMPLATE_ROOT / "testcases/test_api_cases.py"


def load_test_entry(monkeypatch):
    monkeypatch.syspath_prepend(str(TEMPLATE_ROOT))
    spec = importlib.util.spec_from_file_location("test_api_case_template_runtime_path", TEST_ENTRY)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    status_code = 200
    text = '{"code": 200}'

    @staticmethod
    def json():
        return {"code": 200}


class RecordingClient:
    def __init__(self) -> None:
        self.path = ""

    def set_auth_context(self, auth_context):
        return None

    def request(self, method, path, **kwargs):
        self.path = path
        return FakeResponse()


def test_execute_step_resolves_runtime_variable_in_path(monkeypatch) -> None:
    entry = load_test_entry(monkeypatch)
    client = RecordingClient()
    step = {
        "method": "GET",
        "path": "/items/${id}",
        "session_role": "default",
        "request": {},
        "expected": {"status_code": 200},
    }

    entry._execute_step(
        client,
        {},
        {"id": 7},
        {"default": {"enabled": False}},
        step,
    )

    assert client.path == "/items/7"
