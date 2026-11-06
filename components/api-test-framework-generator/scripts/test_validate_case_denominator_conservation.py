from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml


SCRIPT = Path(__file__).with_name("validate_case_denominator_conservation.py")


def load_validator():
    spec = importlib.util.spec_from_file_location("case_denominator_validator_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_framework(tmp_path: Path) -> tuple[Path, Path, Path]:
    framework = tmp_path / "api-test-framework"
    case_set = tmp_path / "执行级接口用例集.md"
    required_flows = tmp_path / "required_chain_flows.yaml"
    write(case_set, "# 执行级接口用例集\n\n- 用例ID: CASE-001\n")
    write(required_flows, "flows:\n  - flow_id: FLOW-001\n    status: required\n")
    write(
        framework / "data/cases/cases.yaml",
        yaml.safe_dump(
            {
                "cases": [
                    {"case_id": "CASE-001", "interface_id": "API-001"},
                    {
                        "case_id": "CASE-MANUAL",
                        "interface_id": "API-002",
                        "automation_decision": "manual_review_only",
                        "live_pytest_release_ready": False,
                    },
                ]
            },
            allow_unicode=True,
        ),
    )
    write(
        framework / "data/flow_cases.yaml",
        yaml.safe_dump({"flows": [{"flow_id": "FLOW-001"}]}, allow_unicode=True),
    )
    write(
        framework / "configs/generation_status.yaml",
        yaml.safe_dump(
            {
                "pytest_collection_mapping": {
                    "mappings": [
                        {"executable_case_id": "CASE-001", "pytest_nodeid": "testcases/test_cases.py::test_case[CASE-001]"},
                        {
                            "executable_case_id": "CASE-MANUAL",
                            "pytest_nodeid": "testcases/test_cases.py::test_case[CASE-MANUAL]",
                        },
                        {"flow_id": "FLOW-001", "pytest_nodeid": "testcases/test_flows.py::test_flow_001"},
                    ]
                }
            },
            allow_unicode=True,
        ),
    )
    return framework, case_set, required_flows


def test_legacy_framework_accepts_exact_collection_sets_and_non_default_case(tmp_path: Path) -> None:
    validator = load_validator()
    framework, case_set, required_flows = build_framework(tmp_path)

    errors = validator.validate_case_denominator_conservation(
        framework,
        executable_case_set=case_set,
        required_chain_flows=required_flows,
    )

    assert errors == []


def test_mutation_detects_unmapped_case_and_flow_mapping_without_flow_data(tmp_path: Path) -> None:
    validator = load_validator()
    framework, case_set, required_flows = build_framework(tmp_path)
    status_path = framework / "configs/generation_status.yaml"
    status = yaml.safe_load(status_path.read_text(encoding="utf-8"))
    status["pytest_collection_mapping"]["mappings"].append(
        {"flow_id": "FLOW-MISSING", "pytest_nodeid": "testcases/test_flows.py::test_flow_missing"}
    )
    write(status_path, yaml.safe_dump(status, allow_unicode=True))
    case_path = framework / "data/cases/cases.yaml"
    cases = yaml.safe_load(case_path.read_text(encoding="utf-8"))
    cases["cases"].append({"case_id": "CASE-UNMAPPED", "interface_id": "API-003"})
    write(case_path, yaml.safe_dump(cases, allow_unicode=True))

    errors = validator.validate_case_denominator_conservation(
        framework,
        executable_case_set=case_set,
        required_chain_flows=required_flows,
    )

    assert any("CASE-UNMAPPED" in error and "pytest 映射" in error for error in errors)
    assert any("FLOW-MISSING" in error and "分母外 ID" in error for error in errors)


def test_mutation_detects_upstream_case_omission(tmp_path: Path) -> None:
    validator = load_validator()
    framework, case_set, required_flows = build_framework(tmp_path)
    write(case_set, "# 执行级接口用例集\n\n- 用例ID: CASE-001\n- 用例ID: CASE-OMITTED\n")

    errors = validator.validate_case_denominator_conservation(
        framework,
        executable_case_set=case_set,
        required_chain_flows=required_flows,
    )

    assert any("CASE-OMITTED" in error and "未进入生成用例数据" in error for error in errors)


def test_manifest_freezes_supplemental_denominator_and_source_refs(tmp_path: Path) -> None:
    validator = load_validator()
    framework, case_set, required_flows = build_framework(tmp_path)
    status_path = framework / "configs/generation_status.yaml"
    status = yaml.safe_load(status_path.read_text(encoding="utf-8"))
    status["case_denominator_conservation"] = {
        "status": "passed",
        "manifest_path": "configs/case_denominator_manifest.yaml",
        "ordinary_source_count": 1,
        "ordinary_supplemental_count": 1,
        "ordinary_generated_count": 2,
        "flow_source_count": 1,
        "flow_supplemental_count": 0,
        "flow_generated_count": 1,
        "missing_case_ids": [],
        "extra_case_ids": [],
        "missing_flow_ids": [],
        "extra_flow_ids": [],
        "duplicate_ids": [],
    }
    write(status_path, yaml.safe_dump(status, allow_unicode=True))
    manifest = {
        "schema_version": 1,
        "status": "passed",
        "ordinary": {
            "supplemental_groups": [
                {
                    "group_id": "manual-supplement",
                    "source_refs": ["补充用例清单.md#人工复核"],
                    "case_ids": ["CASE-MANUAL"],
                }
            ],
            "non_default_case_ids": ["CASE-MANUAL"],
        },
        "flows": {"supplemental_groups": [], "non_default_flow_ids": []},
    }
    manifest_path = framework / "configs/case_denominator_manifest.yaml"
    write(manifest_path, yaml.safe_dump(manifest, allow_unicode=True))

    errors = validator.validate_case_denominator_conservation(
        framework,
        executable_case_set=case_set,
        required_chain_flows=required_flows,
    )
    assert errors == []

    status["case_denominator_conservation"]["ordinary_generated_count"] = 1
    write(status_path, yaml.safe_dump(status, allow_unicode=True))
    errors = validator.validate_case_denominator_conservation(
        framework,
        executable_case_set=case_set,
        required_chain_flows=required_flows,
    )
    assert any("ordinary_generated_count" in error and "1 != 2" in error for error in errors)
    status["case_denominator_conservation"]["ordinary_generated_count"] = 2
    write(status_path, yaml.safe_dump(status, allow_unicode=True))

    manifest["ordinary"]["supplemental_groups"][0]["case_ids"] = []
    write(manifest_path, yaml.safe_dump(manifest, allow_unicode=True))
    errors = validator.validate_case_denominator_conservation(
        framework,
        executable_case_set=case_set,
        required_chain_flows=required_flows,
    )
    assert any("CASE-MANUAL" in error and "分母外 ID" in error for error in errors)
    assert any("缺少 case_ids" in error for error in errors)


def test_declared_gate_requires_manifest(tmp_path: Path) -> None:
    validator = load_validator()
    framework, case_set, required_flows = build_framework(tmp_path)
    status_path = framework / "configs/generation_status.yaml"
    status = yaml.safe_load(status_path.read_text(encoding="utf-8"))
    status["case_denominator_conservation"] = {"status": "passed"}
    write(status_path, yaml.safe_dump(status, allow_unicode=True))

    errors = validator.validate_case_denominator_conservation(
        framework,
        executable_case_set=case_set,
        required_chain_flows=required_flows,
    )

    assert any("已声明 case_denominator_conservation" in error for error in errors)


def test_v2_manifest_rejects_generated_output_as_supplement_source(tmp_path: Path) -> None:
    validator = load_validator()
    framework, case_set, required_flows = build_framework(tmp_path)
    status_path = framework / "configs/generation_status.yaml"
    status = yaml.safe_load(status_path.read_text(encoding="utf-8"))
    status["case_denominator_conservation"] = {
        "status": "passed",
        "manifest_path": "configs/case_denominator_manifest.yaml",
        "ordinary_source_count": 1,
        "ordinary_supplemental_count": 1,
        "ordinary_generated_count": 2,
        "flow_source_count": 1,
        "flow_supplemental_count": 0,
        "flow_generated_count": 1,
        "missing_case_ids": [],
        "extra_case_ids": [],
        "missing_flow_ids": [],
        "extra_flow_ids": [],
        "duplicate_ids": [],
    }
    write(status_path, yaml.safe_dump(status, allow_unicode=True))
    manifest = {
        "schema_version": 2,
        "status": "passed",
        "source_integrity": "upstream_authoritative",
        "ordinary": {
            "supplemental_groups": [
                {
                    "group_id": "circular-supplement",
                    "source_refs": ["core/generated_runner.py#run"],
                    "case_ids": ["CASE-MANUAL"],
                }
            ],
            "non_default_case_ids": ["CASE-MANUAL"],
        },
        "flows": {"supplemental_groups": [], "non_default_flow_ids": []},
    }
    write(
        framework / "configs/case_denominator_manifest.yaml",
        yaml.safe_dump(manifest, allow_unicode=True),
    )

    errors = validator.validate_case_denominator_conservation(
        framework,
        executable_case_set=case_set,
        required_chain_flows=required_flows,
    )

    assert any("source_refs 反向引用生成物" in error for error in errors)


def test_v2_manifest_accepts_external_authoritative_supplement_source(tmp_path: Path) -> None:
    validator = load_validator()
    framework, case_set, required_flows = build_framework(tmp_path)
    status_path = framework / "configs/generation_status.yaml"
    status = yaml.safe_load(status_path.read_text(encoding="utf-8"))
    status["case_denominator_conservation"] = {
        "status": "passed",
        "manifest_path": "configs/case_denominator_manifest.yaml",
        "ordinary_source_count": 1,
        "ordinary_supplemental_count": 1,
        "ordinary_generated_count": 2,
        "flow_source_count": 1,
        "flow_supplemental_count": 0,
        "flow_generated_count": 1,
        "missing_case_ids": [],
        "extra_case_ids": [],
        "missing_flow_ids": [],
        "extra_flow_ids": [],
        "duplicate_ids": [],
    }
    write(status_path, yaml.safe_dump(status, allow_unicode=True))
    manifest = {
        "schema_version": 2,
        "status": "passed",
        "source_integrity": "upstream_authoritative",
        "ordinary": {
            "supplemental_groups": [
                {
                    "group_id": "external-supplement",
                    "source_refs": ["../04-runtime-evidence/supplement.yaml#CASE-MANUAL"],
                    "case_ids": ["CASE-MANUAL"],
                }
            ],
            "non_default_case_ids": ["CASE-MANUAL"],
        },
        "flows": {"supplemental_groups": [], "non_default_flow_ids": []},
    }
    write(
        framework / "configs/case_denominator_manifest.yaml",
        yaml.safe_dump(manifest, allow_unicode=True),
    )

    errors = validator.validate_case_denominator_conservation(
        framework,
        executable_case_set=case_set,
        required_chain_flows=required_flows,
    )

    assert errors == []
