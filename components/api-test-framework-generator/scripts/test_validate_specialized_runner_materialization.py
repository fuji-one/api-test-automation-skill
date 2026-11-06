from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml


SCRIPT = Path(__file__).with_name("validate_specialized_runner_materialization.py")


def load_validator():
    spec = importlib.util.spec_from_file_location("specialized_runner_validator_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def contract(source_ref: str = "../04-runtime-evidence/runner.yaml#RUNNER-001") -> dict:
    return {
        "runner_id": "stateful_runner",
        "consumer_case_ids": ["CASE-001"],
        "consumer_flow_ids": [],
        "reason_generic_runner_insufficient": "需要统一处理异步观测和失败路径精确恢复",
        "authoritative_source_refs": [source_ref],
        "adapter": {"module": "core.stateful_runner", "callable": "run_specialized"},
        "generation_contract": {
            "inputs": [
                "definition",
                "client",
                "env_config",
                "runtime_context",
                "auth_contexts",
            ],
            "ordered_actions": ["准备当前轮状态", "执行请求并观测"],
            "result_fields": ["success", "restore"],
            "assertion_obligations": ["当前轮业务结果可观测"],
            "cleanup_guarantees": ["按当前轮归属键精确恢复"],
            "failure_path_guarantees": ["主流程失败后继续执行独立清理"],
        },
        "generated_files": ["core/stateful_runner.py"],
    }


def build_framework(tmp_path: Path, *, source_ref: str = "../04-runtime-evidence/runner.yaml#RUNNER-001") -> Path:
    framework = tmp_path / "api-test-framework"
    write(
        framework / "data/cases/cases.yaml",
        yaml.safe_dump(
            {
                "cases": [
                    {
                        "case_id": "CASE-001",
                        "interface_id": "API-001",
                        "specialized_runner_id": "stateful_runner",
                    }
                ]
            },
            allow_unicode=True,
        ),
    )
    write(framework / "data/flow_cases.yaml", "flows: []\n")
    write(
        framework / "core/stateful_runner.py",
        """def run_specialized(*, definition, client, env_config, runtime_context, auth_contexts):
    return {"success": True, "restore": {"record": True}}
""",
    )
    write(
        framework / "configs/specialized_runner_materialization.yaml",
        yaml.safe_dump(
            {"schema_version": 1, "status": "passed", "runners": [contract(source_ref)]},
            allow_unicode=True,
            sort_keys=False,
        ),
    )
    write(
        framework / "configs/generation_status.yaml",
        yaml.safe_dump(
            {
                "specialized_runner_materialization": {
                    "status": "passed",
                    "manifest_path": "configs/specialized_runner_materialization.yaml",
                    "runner_count": 1,
                    "consumer_case_count": 1,
                    "consumer_flow_count": 0,
                    "errors": [],
                }
            },
            allow_unicode=True,
        ),
    )
    return framework


def test_no_specialized_runner_is_not_required(tmp_path: Path) -> None:
    validator = load_validator()
    framework = tmp_path / "api-test-framework"
    write(
        framework / "data/cases/cases.yaml",
        "cases:\n  - case_id: CASE-PLAIN\n    interface_id: API-PLAIN\n",
    )
    write(framework / "data/flow_cases.yaml", "flows: []\n")

    result = validator.validate_framework(framework)

    assert result["status"] == "not_required"
    assert result["errors"] == []


def test_valid_contract_passes_and_legacy_alias_is_discovered(tmp_path: Path) -> None:
    validator = load_validator()
    framework = build_framework(tmp_path)
    case_path = framework / "data/cases/cases.yaml"
    payload = yaml.safe_load(case_path.read_text(encoding="utf-8"))
    payload["cases"][0]["custom_runner"] = payload["cases"][0].pop("specialized_runner_id")
    write(case_path, yaml.safe_dump(payload, allow_unicode=True))

    result = validator.validate_framework(framework)

    assert result["status"] == "passed"
    assert result["runner_ids"] == ["stateful_runner"]
    assert result["errors"] == []


def test_missing_manifest_blocks_discovered_runner(tmp_path: Path) -> None:
    validator = load_validator()
    framework = build_framework(tmp_path)
    (framework / "configs/specialized_runner_materialization.yaml").unlink()

    result = validator.validate_framework(framework)

    assert result["status"] == "failed"
    assert any("缺少 configs/specialized_runner_materialization.yaml" in error for error in result["errors"])


def test_generated_output_cannot_be_authoritative_source(tmp_path: Path) -> None:
    validator = load_validator()
    framework = build_framework(tmp_path, source_ref="core/stateful_runner.py#run_specialized")

    result = validator.validate_framework(framework)

    assert result["status"] == "failed"
    assert any("反向引用生成物" in error for error in result["errors"])


def test_consumer_and_adapter_contract_drift_are_detected(tmp_path: Path) -> None:
    validator = load_validator()
    framework = build_framework(tmp_path)
    manifest_path = framework / "configs/specialized_runner_materialization.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["runners"][0]["consumer_case_ids"] = ["CASE-OTHER"]
    write(manifest_path, yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False))
    runner_path = framework / "core/stateful_runner.py"
    write(runner_path, "def run_specialized(*, definition, client):\n    return {}\n")

    result = validator.validate_framework(framework)

    assert result["status"] == "failed"
    assert any("普通用例消费者不一致" in error for error in result["errors"])
    assert any("适配函数参数不一致" in error for error in result["errors"])


def test_dedicated_flow_requires_canonical_runner_id(tmp_path: Path) -> None:
    validator = load_validator()
    framework = tmp_path / "api-test-framework"
    write(framework / "data/cases/cases.yaml", "cases: []\n")
    write(
        framework / "data/flow_cases.yaml",
        """flows:
  - flow_id: FLOW-001
    execution_mode: dedicated_closed_loop_runner
    runner_ref: core/stateful_runner.py#Runner
""",
    )

    result = validator.validate_framework(framework)

    assert result["status"] == "failed"
    assert any("必须声明 specialized_runner_id" in error for error in result["errors"])


def test_cold_start_comparison_is_semantic_not_byte_exact(tmp_path: Path) -> None:
    validator = load_validator()
    baseline = build_framework(tmp_path / "baseline")
    rebuilt = build_framework(tmp_path / "rebuilt")
    write(
        rebuilt / "core/stateful_runner.py",
        """def run_specialized(
    *, definition, client, env_config, runtime_context, auth_contexts
):
    # 冷启动实现允许采用不同格式，但适配合同必须一致。
    return {"restore": {"record": True}, "success": True}
""",
    )

    baseline_result = validator.validate_framework(baseline)
    rebuilt_result = validator.validate_framework(rebuilt)
    errors = validator.compare_rebuild(baseline_result, rebuilt_result)

    assert baseline_result["status"] == "passed"
    assert rebuilt_result["status"] == "passed"
    assert errors == []


def test_cold_start_comparison_detects_semantic_contract_drift(tmp_path: Path) -> None:
    validator = load_validator()
    baseline = build_framework(tmp_path / "baseline")
    rebuilt = build_framework(tmp_path / "rebuilt")
    manifest_path = rebuilt / "configs/specialized_runner_materialization.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["runners"][0]["generation_contract"]["cleanup_guarantees"] = ["仅记录清理意图"]
    write(manifest_path, yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False))

    errors = validator.compare_rebuild(
        validator.validate_framework(baseline),
        validator.validate_framework(rebuilt),
    )

    assert any("语义合同不一致" in error for error in errors)
