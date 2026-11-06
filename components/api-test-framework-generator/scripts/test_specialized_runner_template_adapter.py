from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml


ADAPTER = (
    Path(__file__).parent.parent
    / "assets/api-test-framework-template/core/specialized_runner.py"
)


def load_adapter():
    spec = importlib.util.spec_from_file_location("specialized_runner_template_test", ADAPTER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def prepare_runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    core_dir = tmp_path / "core"
    core_dir.mkdir()
    (core_dir / "__init__.py").write_text("", encoding="utf-8")
    (core_dir / "fake_runner.py").write_text(
        """def run_specialized(*, definition, client, env_config, runtime_context, auth_contexts):
    runtime_context["called"] = True
    return {"success": True, "restore": {"record": True}, "business_code": 200}
""",
        encoding="utf-8",
    )
    manifest = tmp_path / "configs/specialized_runner_materialization.yaml"
    manifest.parent.mkdir()
    manifest.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "status": "passed",
                "runners": [
                    {
                        "runner_id": "fake_runner",
                        "adapter": {"module": "core.fake_runner", "callable": "run_specialized"},
                    }
                ],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    sys.modules.pop("core", None)
    sys.modules.pop("core.fake_runner", None)
    adapter = load_adapter()
    monkeypatch.setattr(adapter, "MANIFEST_PATH", manifest)
    adapter._runner_index.cache_clear()
    return adapter


def test_shared_adapter_dispatches_and_asserts_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = prepare_runner(tmp_path, monkeypatch)
    runtime_context = {}
    definition = {
        "specialized_runner_id": "fake_runner",
        "specialized_runner_assertions": {
            "equals": {"business_code": 200},
            "true_fields": ["success"],
            "required_fields": ["restore.record"],
            "all_true_fields": ["restore"],
        },
    }

    result = adapter.run_specialized_runner(definition, object(), {}, runtime_context, {})

    assert result["business_code"] == 200
    assert runtime_context["called"] is True


def test_shared_adapter_fails_fast_for_undeclared_runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = prepare_runner(tmp_path, monkeypatch)

    with pytest.raises(ValueError, match="未在物化清单中声明"):
        adapter.run_specialized_runner(
            {"specialized_runner_id": "missing"},
            object(),
            {},
            {},
            {},
        )


def test_ordinary_case_has_no_specialized_runner_marker() -> None:
    adapter = load_adapter()

    assert adapter.resolve_specialized_runner_id({"case_id": "CASE-PLAIN"}) == ""
