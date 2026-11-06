from __future__ import annotations

import importlib.util
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
SELECT_ROUTE = ROOT / "scripts" / "select_entry_route.py"
BUILD_CHAIN = ROOT / "scripts" / "build_chain_flow_denominator.py"
BUILD_RUNTIME_PLAN = ROOT / "scripts" / "build_runtime_evidence_plan.py"
PREPARE_HANDOFF = ROOT / "scripts" / "prepare_handoff.py"
VALIDATE_PIPELINE = ROOT / "scripts" / "validate_pipeline_outputs.py"
RUN_LIVE_REQUEST_EVIDENCE = ROOT / "scripts" / "run_live_request_evidence.py"
VALIDATE_RUNTIME_EVIDENCE = ROOT / "scripts" / "validate_runtime_evidence.py"
VALIDATE_EXECUTABLE = ROOT / "components" / "executable-interface-case-set" / "scripts" / "validate_outputs.py"
VALIDATE_CASE_DENOMINATOR = (
    ROOT
    / "components"
    / "api-test-framework-generator"
    / "scripts"
    / "validate_case_denominator_conservation.py"
)
FRAMEWORK_TEMPLATE = (
    ROOT
    / "components"
    / "api-test-framework-generator"
    / "assets"
    / "api-test-framework-template"
)


@pytest.fixture()
def temp_root() -> Path:
    with tempfile.TemporaryDirectory(prefix="api_suite_guard_") as raw:
        yield Path(raw)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def confidence_payload(
    *,
    score: float = 0.85,
    scope: str = "framework",
    relevance: str = "reachable_business_branch",
    dimension_value: float = 0.9,
    runtime_value: float | str = 0.9,
    cap_reasons: list[str] | None = None,
    automation_decision: str | None = None,
) -> dict:
    cap_reasons = ["RUNTIME_NOT_VERIFIED"] if cap_reasons is None else cap_reasons
    reason_codes = ["SOURCE_CONTRACT_CONFIRMED", *cap_reasons]
    payload = {
        "confidence_score": score,
        "confidence_level": "low" if score < 0.7 else "medium" if score < 0.9 else "high",
        "confidence_band": (
            "insufficient"
            if score < 0.6
            else "contract_confirmed"
            if score < 0.7
            else "request_confirmed"
            if score < 0.8
            else "scenario_confirmed"
            if score < 0.9
            else "runtime_closed"
        ),
        "confidence_scope": scope,
        "scenario_relevance": relevance,
        "confidence_dimensions": {
            "contract": dimension_value,
            "request_materialization": dimension_value,
            "scenario_precondition": dimension_value,
            "business_assertion": dimension_value,
            "runtime_repeatability": runtime_value,
        },
        "confidence_reason_codes": reason_codes,
        "confidence_cap_reasons": cap_reasons,
        "confidence_evidence_refs": ["case_list.yaml#/cases/1"],
    }
    if automation_decision:
        payload["automation_decision"] = automation_decision
    return payload


def confidence_archive(*record_ids: str) -> str:
    blocks = ["# 接口案例"]
    for record_id in record_ids:
        blocks.extend(
            [
                f"### `{record_id}`",
                f"<!-- CASE_CONFIDENCE_INLINE:{record_id} START -->",
                "- 置信度分数：0.85",
                "- 置信度等级：medium",
                f"<!-- CASE_CONFIDENCE_INLINE:{record_id} END -->",
            ]
        )
    return "\n".join(blocks) + "\n"


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_case_confidence_score_uses_weights_cap_and_downward_quantization() -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_confidence_score_test")
    dimensions = {
        "contract": 0.9,
        "request_materialization": 0.9,
        "scenario_precondition": 0.9,
        "business_assertion": 0.9,
        "runtime_repeatability": 0.9,
    }

    assert validator.calculate_confidence_score(dimensions, []) == 0.9
    assert validator.calculate_confidence_score(dimensions, ["RUNTIME_NOT_VERIFIED"]) == 0.85
    assert validator.confidence_band(0.85) == "scenario_confirmed"
    assert validator.confidence_level(0.85) == "medium"


def test_case_confidence_does_not_penalize_contract_boundary_relevance() -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_confidence_relevance_test")
    item = confidence_payload(
        score=0.95,
        relevance="contract_boundary",
        dimension_value=0.95,
        runtime_value=0.95,
        cap_reasons=[],
    )
    errors: list[str] = []

    validator.validate_case_confidence(
        item,
        "TC-BOUNDARY-001",
        errors,
        require_runtime_dimension=True,
        enforce_live_boundary=True,
    )

    assert errors == []


def test_low_confidence_case_is_blocked_from_live_but_kept_non_live() -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_confidence_live_boundary_test")
    live_item = confidence_payload(
        score=0.65,
        dimension_value=0.7,
        runtime_value=0.7,
        cap_reasons=["INPUT_NOT_CONFIRMED"],
    )
    errors: list[str] = []
    validator.validate_case_confidence(
        live_item,
        "TC-LOW-LIVE",
        errors,
        require_runtime_dimension=True,
        enforce_live_boundary=True,
    )
    assert any("低置信度用例不能进入 live 分母" in error for error in errors)

    non_live_item = dict(live_item, automation_decision="generated_non_live")
    errors = []
    validator.validate_case_confidence(
        non_live_item,
        "TC-LOW-NONLIVE",
        errors,
        require_runtime_dimension=True,
        enforce_live_boundary=True,
    )
    assert errors == []


def test_optional_transfer_release_rejects_unknown_live_decision(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_optional_transfer_release_bad_decision_test")
    framework = temp_root / "api-test-framework"
    write(
        framework / "configs/final_release_audit.yaml",
        """status: passed
scope:
  generated_candidate_case_count: 1
  selected_case_count: 1
  runnable_case_count: 1
  non_live_case_count: 0
  e2e_flow_count: 0
  runnable_node_count: 1
  collected_node_count: 1
release_decision:
  script_generation_ready: true
""",
    )
    write(
        framework / "data/cases/cases.yaml",
        """cases:
- case_id: CASE-001
  live_pytest_release_ready: true
  automation_decision: live_pytest
""",
    )
    errors: list[str] = []
    validator.validate_optional_transfer_release(
        framework,
        {"selected_case_count": 1, "e2e_flow_case_count": 0, "collected_test_count": 1},
        errors,
    )
    assert any("automation_decision 非法" in error for error in errors)


def test_optional_transfer_release_accepts_dynamic_runnable_denominator(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_optional_transfer_release_dynamic_denominator_test")
    framework = temp_root / "api-test-framework"
    write(
        framework / "configs/final_release_audit.yaml",
        """status: passed
scope:
  generated_candidate_case_count: 2
  selected_case_count: 2
  runnable_case_count: 1
  non_live_case_count: 1
  e2e_flow_count: 1
  runnable_node_count: 2
  collected_node_count: 3
checks:
  pytest_collect_only:
    collected_node_count: 3
release_decision:
  script_generation_ready: true
""",
    )
    write(
        framework / "data/cases/cases.yaml",
        """cases:
- case_id: CASE-RUNNABLE
  live_pytest_release_ready: true
  automation_decision: runnable
- case_id: CASE-NON-LIVE
  live_pytest_release_ready: false
  automation_decision: generated_non_live
""",
    )
    write(
        framework / "data/flow_cases.yaml",
        """flows:
- flow_id: FLOW-001
  live_pytest_release_ready: true
  automation_decision: runnable
""",
    )
    errors: list[str] = []
    validator.validate_optional_transfer_release(
        framework,
        {"selected_case_count": 2, "e2e_flow_case_count": 1, "collected_test_count": 3},
        errors,
    )
    assert errors == []


def test_design_confidence_not_applicable_runtime_requires_cap() -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_design_confidence_cap_test")
    item = confidence_payload(
        score=0.9,
        scope="design",
        runtime_value="not_applicable",
        cap_reasons=[],
    )
    errors: list[str] = []

    validator.validate_case_confidence(
        item,
        "DC-001",
        errors,
        require_runtime_dimension=False,
        enforce_live_boundary=False,
    )

    assert any("必须声明 RUNTIME_NOT_VERIFIED" in error for error in errors)


def test_framework_confidence_gate_rejects_flow_above_weakest_step(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_flow_confidence_test")
    framework = temp_root / "api-test-framework"
    case_item = {
        "case_id": "TC-STEP-001",
        "interface_id": "API-001",
        **confidence_payload(),
    }
    flow_item = {
        "flow_id": "FLOW-001",
        "source_executable_case_ids": "TC-STEP-001",
        "steps": [{"case_id": "TC-STEP-001"}],
        **confidence_payload(
            score=0.95,
            relevance="core_real_journey",
            dimension_value=0.95,
            runtime_value=0.95,
            cap_reasons=[],
        ),
    }
    write(framework / "data" / "cases" / "cases.yaml", yaml.safe_dump({"cases": [case_item]}, allow_unicode=True))
    write(framework / "data" / "flow_cases.yaml", yaml.safe_dump({"flows": [flow_item]}, allow_unicode=True))
    write(framework / "接口案例.md", confidence_archive("TC-STEP-001", "FLOW-001"))
    status = {
        "case_confidence_gate": {
            "status": "passed",
            "candidate_case_count": 2,
            "declared_confidence_case_count": 2,
            "high_count": 1,
            "medium_count": 1,
            "low_count": 0,
            "missing_confidence_case_ids": [],
            "invalid_confidence_case_ids": [],
            "low_confidence_live_case_ids": [],
            "archive_missing_confidence_case_ids": [],
        }
    }
    errors: list[str] = []

    validator.validate_framework_case_confidence(framework, status, errors)

    assert any("长链路置信度高于最弱必需步骤" in error for error in errors)


def test_framework_confidence_gate_accepts_matching_counts_and_weakest_flow_score(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_valid_confidence_gate_test")
    framework = temp_root / "api-test-framework"
    case_item = {"case_id": "TC-STEP-001", "interface_id": "API-001", **confidence_payload()}
    flow_item = {
        "flow_id": "FLOW-001",
        "source_executable_case_ids": ["TC-STEP-001"],
        "steps": [{"case_id": "TC-STEP-001"}],
        **confidence_payload(relevance="core_real_journey"),
    }
    write(framework / "data" / "cases" / "cases.yaml", yaml.safe_dump({"cases": [case_item]}, allow_unicode=True))
    write(framework / "data" / "flow_cases.yaml", yaml.safe_dump({"flows": [flow_item]}, allow_unicode=True))
    write(framework / "接口案例.md", confidence_archive("TC-STEP-001", "FLOW-001"))
    status = {
        "case_confidence_gate": {
            "status": "passed",
            "candidate_case_count": 2,
            "declared_confidence_case_count": 2,
            "high_count": 0,
            "medium_count": 2,
            "low_count": 0,
            "missing_confidence_case_ids": [],
            "invalid_confidence_case_ids": [],
            "low_confidence_live_case_ids": [],
            "archive_missing_confidence_case_ids": [],
        }
    }
    errors: list[str] = []

    validator.validate_framework_case_confidence(framework, status, errors)

    assert errors == []


def test_flow_confidence_accepts_consolidated_case_for_unmaterialized_source_steps(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_consolidated_flow_confidence_test")
    framework = temp_root / "api-test-framework"
    case_item = {"case_id": "TC-LC-001", "interface_id": "API-001", **confidence_payload()}
    flow_item = {
        "flow_id": "FLOW-001",
        "case_id": "TC-LC-001",
        "source_executable_case_ids": ["TC-SOURCE-NOT-SEPARATELY-GENERATED"],
        "steps": [],
        **confidence_payload(relevance="core_real_journey"),
    }
    write(framework / "data" / "cases" / "cases.yaml", yaml.safe_dump({"cases": [case_item]}, allow_unicode=True))
    write(framework / "data" / "flow_cases.yaml", yaml.safe_dump({"flows": [flow_item]}, allow_unicode=True))
    write(framework / "接口案例.md", confidence_archive("TC-LC-001", "FLOW-001"))
    status = {
        "case_confidence_gate": {
            "status": "passed",
            "candidate_case_count": 2,
            "declared_confidence_case_count": 2,
            "high_count": 0,
            "medium_count": 2,
            "low_count": 0,
            "missing_confidence_case_ids": [],
            "invalid_confidence_case_ids": [],
            "low_confidence_live_case_ids": [],
            "archive_missing_confidence_case_ids": [],
        }
    }
    errors: list[str] = []

    validator.validate_framework_case_confidence(framework, status, errors)

    assert not any("缺少必需步骤置信度" in error for error in errors)
    assert errors == []


def test_confidence_increase_requires_new_evidence_and_changed_basis(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_confidence_progression_test")
    root = temp_root / "pipeline"
    framework = root / "api-test-framework"
    design_item = {
        "case_id": "DC-001",
        "design_case_id": "DC-001",
        **confidence_payload(scope="design", runtime_value=0.9),
    }
    framework_item = {
        "case_id": "EC-001",
        "design_case_id": "DC-001",
        "interface_id": "API-001",
        **confidence_payload(
            score=0.95,
            dimension_value=0.95,
            runtime_value=0.95,
            cap_reasons=[],
        ),
    }
    framework_item["confidence_evidence_refs"] = list(design_item["confidence_evidence_refs"])
    write(
        root / "04-design-case-handoff" / "case_list.yaml",
        yaml.safe_dump({"cases": [design_item]}, allow_unicode=True),
    )
    write(
        framework / "data" / "cases" / "cases.yaml",
        yaml.safe_dump({"cases": [framework_item]}, allow_unicode=True),
    )
    errors: list[str] = []

    validator.validate_confidence_stage_progression(root, framework, errors)

    assert any("没有新增证据引用" in error for error in errors)

    framework_item["confidence_evidence_refs"].append("runtime_evidence.yaml#EV-001")
    write(
        framework / "data" / "cases" / "cases.yaml",
        yaml.safe_dump({"cases": [framework_item]}, allow_unicode=True),
    )
    errors = []
    validator.validate_confidence_stage_progression(root, framework, errors)
    assert errors == []


def test_confidence_decrease_requires_new_evidence_changed_basis_and_reason(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_confidence_decrease_test")
    root = temp_root / "pipeline"
    framework = root / "api-test-framework"
    design_item = {
        "case_id": "DC-001",
        "design_case_id": "DC-001",
        **confidence_payload(
            score=0.95,
            scope="design",
            dimension_value=0.95,
            runtime_value=0.95,
            cap_reasons=[],
        ),
    }
    framework_item = {
        "case_id": "EC-001",
        "design_case_id": "DC-001",
        "interface_id": "API-001",
        **confidence_payload(
            score=0.80,
            dimension_value=0.95,
            runtime_value=0.95,
            cap_reasons=[],
        ),
    }
    write(
        root / "04-design-case-handoff" / "case_list.yaml",
        yaml.safe_dump({"cases": [design_item]}, allow_unicode=True),
    )
    write(
        framework / "data" / "cases" / "cases.yaml",
        yaml.safe_dump({"cases": [framework_item]}, allow_unicode=True),
    )
    errors: list[str] = []

    validator.validate_confidence_stage_progression(root, framework, errors)

    assert any("降至" in error and "没有新增证据引用" in error for error in errors)
    assert any("维度和硬上限条件均未变化" in error for error in errors)
    assert any("原因码和硬上限原因均未变化" in error for error in errors)

    framework_item.update(
        confidence_payload(
            score=0.80,
            dimension_value=0.95,
            runtime_value=0.20,
            cap_reasons=["RUNTIME_NOT_VERIFIED"],
        )
    )
    framework_item["confidence_evidence_refs"].append("runtime_evidence.yaml#UNRESOLVED-RUNTIME-001")
    write(
        framework / "data" / "cases" / "cases.yaml",
        yaml.safe_dump({"cases": [framework_item]}, allow_unicode=True),
    )
    errors = []
    validator.validate_confidence_stage_progression(root, framework, errors)
    assert errors == []


@pytest.mark.parametrize(
    ("mapping_field", "mapping_value"),
    (
        ("source_case_id", "TC-SRC-001"),
        ("supplemental_design_case_ref", "DC-001"),
    ),
)
def test_confidence_progression_resolves_existing_traceability_aliases(
    temp_root: Path,
    mapping_field: str,
    mapping_value: str,
) -> None:
    validator = load_module(VALIDATE_PIPELINE, f"validate_pipeline_confidence_alias_{mapping_field}_test")
    root = temp_root / "pipeline"
    framework = root / "api-test-framework"
    design_item = {
        "case_id": "TC-SRC-001",
        "design_case_id": "DC-001",
        **confidence_payload(scope="design"),
    }
    framework_item = {
        "case_id": "TC-RUNTIME-001",
        "interface_id": "API-001",
        "traceability": {mapping_field: mapping_value},
        **confidence_payload(
            score=0.95,
            dimension_value=0.95,
            runtime_value=0.95,
            cap_reasons=[],
        ),
    }
    framework_item["confidence_evidence_refs"] = list(design_item["confidence_evidence_refs"])
    write(
        root / "04-design-case-handoff" / "case_list.yaml",
        yaml.safe_dump({"cases": [design_item]}, allow_unicode=True),
    )
    write(
        framework / "data" / "cases" / "cases.yaml",
        yaml.safe_dump({"cases": [framework_item]}, allow_unicode=True),
    )
    errors: list[str] = []

    validator.validate_confidence_stage_progression(root, framework, errors)

    assert any("没有新增证据引用" in error for error in errors)


def test_executable_confidence_participates_in_vertical_progression(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_executable_confidence_progression_test")
    root = temp_root / "pipeline"
    framework = root / "api-test-framework"
    design_item = {
        "case_id": "TC-SRC-001",
        "design_case_id": "DC-001",
        **confidence_payload(
            score=0.95,
            scope="design",
            dimension_value=0.95,
            runtime_value=0.95,
            cap_reasons=[],
        ),
    }
    executable_case = """```yaml
- 用例ID: TC-EXEC-001
  设计级用例ID: DC-001
  置信度分数: 0.85
  置信度等级: medium
  置信度区间: scenario_confirmed
  置信度范围: executable
  场景相关性: core_real_journey
  置信度维度:
    contract: 0.9
    request_materialization: 0.9
    scenario_precondition: 0.9
    business_assertion: 0.9
    runtime_repeatability: 0.9
  置信度原因码:
    - SOURCE_CONTRACT_CONFIRMED
    - RUNTIME_NOT_VERIFIED
  置信度硬上限原因:
    - RUNTIME_NOT_VERIFIED
  置信度证据引用:
    - case_list.yaml#/cases/1
```
"""
    write(
        root / "04-design-case-handoff" / "case_list.yaml",
        yaml.safe_dump({"cases": [design_item]}, allow_unicode=True),
    )
    executable_path = root / "05-executable-interface-case-set" / "执行级接口用例集.md"
    write(executable_path, executable_case)
    errors: list[str] = []

    validator.validate_confidence_stage_progression(root, framework, errors)

    assert any("降至" in error and "没有新增证据引用" in error for error in errors)

    write(
        executable_path,
        executable_case.replace(
            "    - case_list.yaml#/cases/1\n",
            "    - case_list.yaml#/cases/1\n    - execution_fact_sources.yaml#FACT-001\n",
        ),
    )
    errors = []
    validator.validate_confidence_stage_progression(root, framework, errors)
    assert errors == []


def test_sharded_executable_confidence_is_loaded_in_index_order(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_sharded_confidence_test")
    root = temp_root / "pipeline"
    executable_dir = root / "05-executable-interface-case-set"
    write(
        executable_dir / "执行级接口用例集.md",
        "## 执行级接口用例集\n\n- 分片模式：启用\n- 分片索引：执行级用例分片索引.md\n",
    )
    write(
        executable_dir / "执行级用例分片索引.md",
        """## 执行级用例分片索引

| 顺序 | 分片ID | 文件 |
|---|---|---|
| 001 | SHARD-001 | 执行级用例分片/001_demo.md |
""",
    )
    write(
        executable_dir / "执行级用例分片" / "001_demo.md",
        """## 执行级接口用例分片

```yaml
- 用例ID: TC-EXEC-001
  设计级用例ID: DC-001
  置信度分数: 0.85
  置信度等级: medium
  置信度区间: scenario_confirmed
  置信度范围: executable
  场景相关性: core_real_journey
  置信度维度:
    contract: 0.9
    request_materialization: 0.9
    scenario_precondition: 0.9
    business_assertion: 0.9
    runtime_repeatability: 0.9
  置信度原因码:
    - SOURCE_CONTRACT_CONFIRMED
    - RUNTIME_NOT_VERIFIED
  置信度硬上限原因:
    - RUNTIME_NOT_VERIFIED
  置信度证据引用:
    - case_list.yaml#/cases/1
```
""",
    )
    errors: list[str] = []

    records = validator.executable_confidence_records(root, errors)

    assert errors == []
    assert [record[1]["case_id"] for record in records] == ["TC-EXEC-001"]


def test_sharded_executable_confidence_rejects_missing_shard(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_missing_sharded_confidence_test")
    root = temp_root / "pipeline"
    executable_dir = root / "05-executable-interface-case-set"
    write(
        executable_dir / "执行级接口用例集.md",
        "## 执行级接口用例集\n\n- 分片模式：启用\n- 分片索引：执行级用例分片索引.md\n",
    )
    write(
        executable_dir / "执行级用例分片索引.md",
        """## 执行级用例分片索引

| 顺序 | 分片ID | 文件 |
|---|---|---|
| 001 | SHARD-001 | 执行级用例分片/001_missing.md |
""",
    )
    errors: list[str] = []

    records = validator.executable_confidence_records(root, errors)

    assert records == []
    assert any("分片文件不存在" in error for error in errors)


@pytest.mark.parametrize(
    ("rows", "existing_files", "expected_error"),
    [
        (
            "| 001 | SHARD-001 | ../escape.md |",
            [],
            "分片文件路径非法",
        ),
        (
            "| 002 | SHARD-002 | 执行级用例分片/002_demo.md |",
            ["执行级用例分片/002_demo.md"],
            "顺序必须从 001 连续递增",
        ),
        (
            "\n".join(
                [
                    "| 001 | SHARD-001 | 执行级用例分片/001_demo.md |",
                    "| 001 | SHARD-001-DUP | 执行级用例分片/001_demo.md |",
                ]
            ),
            ["执行级用例分片/001_demo.md"],
            "存在重复顺序或文件",
        ),
    ],
)
def test_sharded_executable_confidence_rejects_unsafe_or_ambiguous_index(
    temp_root: Path,
    rows: str,
    existing_files: list[str],
    expected_error: str,
) -> None:
    validator = load_module(VALIDATE_PIPELINE, f"validate_pipeline_sharded_index_{len(rows)}_test")
    executable_dir = temp_root / "pipeline" / "05-executable-interface-case-set"
    write(
        executable_dir / "执行级接口用例集.md",
        "## 执行级接口用例集\n\n- 分片模式：启用\n- 分片索引：执行级用例分片索引.md\n",
    )
    write(
        executable_dir / "执行级用例分片索引.md",
        "## 执行级用例分片索引\n\n| 顺序 | 分片ID | 文件 |\n|---|---|---|\n" + rows + "\n",
    )
    for relative_path in existing_files:
        write(executable_dir / relative_path, "## 执行级接口用例分片\n")
    errors: list[str] = []

    validator.executable_confidence_case_paths(executable_dir, errors)

    assert any(expected_error in error for error in errors)


def test_executable_confidence_missing_object_is_rejected_by_pipeline(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_executable_confidence_missing_test")
    root = temp_root / "pipeline"
    framework = root / "api-test-framework"
    design_item = {
        "case_id": "TC-SRC-001",
        "design_case_id": "DC-001",
        **confidence_payload(scope="design"),
    }
    write(
        root / "04-design-case-handoff" / "case_list.yaml",
        yaml.safe_dump({"cases": [design_item]}, allow_unicode=True),
    )
    write(
        root / "05-executable-interface-case-set" / "执行级接口用例集.md",
        """```yaml
- 用例ID: TC-EXEC-001
  设计级用例ID: DC-001
```
""",
    )
    errors: list[str] = []

    validator.validate_confidence_stage_progression(root, framework, errors)

    assert any("缺少置信度字段" in error for error in errors)


def test_executable_confidence_validator_recalculates_score() -> None:
    validator = load_module(VALIDATE_EXECUTABLE, "validate_executable_confidence_test")
    case_block = """- 用例ID: EC-001
  置信度分数: 0.85
  置信度等级: medium
  置信度区间: scenario_confirmed
  置信度范围: executable
  场景相关性: core_real_journey
  置信度维度:
    contract: 0.9
    request_materialization: 0.9
    scenario_precondition: 0.9
    business_assertion: 0.9
    runtime_repeatability: 0.9
  置信度原因码:
    - SOURCE_CONTRACT_CONFIRMED
    - RUNTIME_NOT_VERIFIED
  置信度硬上限原因:
    - RUNTIME_NOT_VERIFIED
  置信度证据引用:
    - execution_fact_sources.yaml#FACT-001
"""
    errors: list[str] = []
    validator.validate_executable_confidence(case_block, errors, "EC-001")
    assert errors == []

    errors = []
    validator.validate_executable_confidence(case_block.replace("置信度分数: 0.85", "置信度分数: 0.90"), errors, "EC-001")
    assert any("不可重算" in error or "runtime_closed" in error for error in errors)


def test_framework_template_projects_confidence_without_execution_branching() -> None:
    loader = (FRAMEWORK_TEMPLATE / "core" / "case_loader.py").read_text(encoding="utf-8")
    test_api = (FRAMEWORK_TEMPLATE / "testcases" / "test_api_cases.py").read_text(encoding="utf-8")
    optional_async = (FRAMEWORK_TEMPLATE / "testcases" / "test_optional_async_cases.py").read_text(encoding="utf-8")

    for field in ("confidence_score", "confidence_level"):
        assert f'"{field}"' in loader
        assert f'allure.dynamic.label("{field}"' in test_api
    assert 'allure.dynamic.label("confidence_band"' not in test_api
    assert 'allure.dynamic.label("scenario_relevance"' not in test_api
    assert "_apply_confidence_labels(case_data)" in optional_async
    confidence_function = test_api[test_api.index("def _apply_confidence_labels") : test_api.index("def _execute_step")]
    assert "authenticated_client" not in confidence_function
    assert "Assertor" not in confidence_function


def test_confidence_contract_is_loaded_without_replacing_existing_quality_gates() -> None:
    root_skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    loading_matrix = (ROOT / "references" / "loading-matrix.md").read_text(encoding="utf-8")
    contract = (ROOT / "references" / "case-confidence-contract.md").read_text(encoding="utf-8")
    framework_skill = (ROOT / "components" / "api-test-framework-generator" / "SKILL.md").read_text(encoding="utf-8")

    assert "references/case-confidence-contract.md" in root_skill
    assert "references/case-confidence-contract.md" in loading_matrix
    assert "Never use confidence to replace assertion" in contract
    assert "downstream stage may lower a score only when it adds at least one new evidence reference" in contract
    assert "must not erase design or executable coverage" in contract
    assert "case_confidence_gate" in framework_skill
    for existing_gate in ("assertion_strength_gate", "setup_cleanup_materialization", "business_result_observability"):
        assert existing_gate in (ROOT / "scripts" / "validate_pipeline_outputs.py").read_text(encoding="utf-8")


def test_real_world_profile_value_rule_remains_source_bound() -> None:
    runtime_inputs = (ROOT / "references" / "source-derived-runtime-inputs.md").read_text(encoding="utf-8")
    executable_skill = (ROOT / "components" / "executable-interface-case-set" / "SKILL.md").read_text(encoding="utf-8")

    assert "广东省/深圳市" in runtime_inputs
    assert "自动化省" in runtime_inputs
    assert "generic real-world legal sample only for ordinary user-entered/profile/display fields" in executable_skill
    assert "Do not use generic samples for IDs" in executable_skill


def test_case_sql_manager_loads_database_only_after_sql_stage_detection() -> None:
    source = (FRAMEWORK_TEMPLATE / "conftest.py").read_text(encoding="utf-8")
    function_source = source[source.index("def case_sql_manager(") : source.index("\n\n@pytest.fixture", source.index("def case_sql_manager("))]

    stage_guard = 'sql_stages = ("setup", "runtime_extract", "cleanup", "final_verify")'
    empty_lifecycle_return = "if not any(case_commands.get(stage) for stage in sql_stages):"
    database_load = 'request.getfixturevalue("database_engines")'
    assert stage_guard in function_source
    assert empty_lifecycle_return in function_source
    assert function_source.index(empty_lifecycle_return) < function_source.index(database_load)


def test_database_engine_template_protects_long_wait_sql_lifecycle() -> None:
    source = (FRAMEWORK_TEMPLATE / "conftest.py").read_text(encoding="utf-8")
    database_config = yaml.safe_load(
        (FRAMEWORK_TEMPLATE / "configs" / "database.yaml").read_text(encoding="utf-8")
    )

    assert "def _database_engine_options(" in source
    assert '"pool_pre_ping": bool(engine_options.get("pool_pre_ping", True))' in source
    assert '"pool_recycle": pool_recycle_seconds' in source
    assert "**engine_options" in source
    for environment in ("dev", "test", "prod"):
        assert database_config[environment]["engine_options"] == {
            "pool_pre_ping": True,
            "pool_recycle_seconds": 300,
        }


def test_runtime_usability_gate_requires_database_pool_liveness() -> None:
    gate = (
        ROOT
        / "components"
        / "api-test-framework-generator"
        / "references"
        / "runtime-usability-gate.md"
    ).read_text(encoding="utf-8")

    assert "Database pooled-connection liveness gate" in gate
    assert "pool_pre_ping" in gate
    assert "pool_recycle" in gate


def test_sql_executor_template_supports_assertion_driven_bounded_polling() -> None:
    source = (FRAMEWORK_TEMPLATE / "core" / "sql_executor.py").read_text(encoding="utf-8")
    gate = (
        ROOT
        / "components"
        / "api-test-framework-generator"
        / "references"
        / "runtime-usability-gate.md"
    ).read_text(encoding="utf-8")

    assert 'command.get("poll_until_expected")' in source
    assert "_poll_runtime_queries_until_expected" in source
    assert "_collect_runtime_query_values" in source
    assert "except AssertionError as error" in source
    assert "不能同时配置固定等待和有界轮询" in source
    assert "SQL bounded polling gate" in gate
    assert "poll_until_expected.timeout_seconds" in gate
    assert "database, transport, SQL syntax, and configuration errors must fail immediately" in (ROOT / "SKILL.md").read_text(encoding="utf-8")


def test_transport_redaction_masks_cloud_credentials_and_identity_fields() -> None:
    module = load_module(FRAMEWORK_TEMPLATE / "core" / "transport_crypto.py", "template_transport_crypto")
    payload = {
        "accessId": "cloud-access-id",
        "accessKey": "cloud-access-key",
        "secretId": "cloud-secret-id",
        "secretKey": "cloud-secret-key",
        "Authorization": "Bearer secret-token",
        "Set-Cookie": "session=secret-cookie",
        "X-API-Key": "secret-api-key",
        "nested": {"realName": "test-user", "idNumber": "test-id-number"},
        "error": "Authorization: Bearer secret-bearer token=secret-token password:secret-password",
        "endpoint": "https://example.invalid",
    }

    redacted = module.redact(payload)

    assert redacted["accessId"] == "__redacted__"
    assert redacted["accessKey"] == "__redacted__"
    assert redacted["secretId"] == "__redacted__"
    assert redacted["secretKey"] == "__redacted__"
    assert redacted["Authorization"] == "__redacted__"
    assert redacted["Set-Cookie"] == "__redacted__"
    assert redacted["X-API-Key"] == "__redacted__"
    assert redacted["nested"]["realName"] == "__redacted__"
    assert redacted["nested"]["idNumber"] == "__redacted__"
    assert "secret-bearer" not in redacted["error"]
    assert redacted["error"] == "Authorization=__redacted__ token=__redacted__ password=__redacted__"
    assert redacted["endpoint"] == "https://example.invalid"


def test_runtime_scope_isolates_business_values_and_preserves_account_context() -> None:
    module = load_module(FRAMEWORK_TEMPLATE / "core" / "runtime_context.py", "template_runtime_scope")
    account_context = {"auth_token": "runtime-only-token", "userId": 42}
    runtime_context = {
        "auth_role_configs": {"provider": {}},
        "auth_roles": {"provider": {"enabled": True}},
        "case_account_logged_roles": {"provider": {"first_case_id": "CASE-000"}},
        "provider_context": account_context,
        "provider_user_id": 42,
        "prior_business_id": 999,
    }
    env_config = {
        "auth_roles": {"provider": {}},
        "runtime_variables": {"tenant": "test-tenant"},
    }

    module.prepare_case_runtime_context(runtime_context, env_config, "CASE-001")

    assert "prior_business_id" not in runtime_context
    assert runtime_context["provider_context"] is account_context
    assert runtime_context["provider_user_id"] == 42
    assert runtime_context["caseId"] == "CASE-001"
    assert runtime_context["tenant"] == "test-tenant"

    runtime_context["flow_step_id"] = 1001
    module.prepare_case_runtime_context(runtime_context, env_config, "CASE-001")
    assert runtime_context["flow_step_id"] == 1001

    module.prepare_case_runtime_context(runtime_context, env_config, "CASE-002")
    assert "flow_step_id" not in runtime_context
    assert runtime_context["provider_context"] is account_context


def test_runtime_resilience_template_keeps_rules_and_implementation_aligned() -> None:
    suite_skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    generator_skill = (ROOT / "components" / "api-test-framework-generator" / "SKILL.md").read_text(encoding="utf-8")
    usability_gate = (
        ROOT
        / "components"
        / "api-test-framework-generator"
        / "references"
        / "runtime-usability-gate.md"
    ).read_text(encoding="utf-8")
    conftest = (FRAMEWORK_TEMPLATE / "conftest.py").read_text(encoding="utf-8")
    runtime_context = (FRAMEWORK_TEMPLATE / "core" / "runtime_context.py").read_text(encoding="utf-8")
    data_manager = (FRAMEWORK_TEMPLATE / "core" / "data_manager.py").read_text(encoding="utf-8")
    auth_manager = (FRAMEWORK_TEMPLATE / "core" / "auth_manager.py").read_text(encoding="utf-8")
    test_api = (FRAMEWORK_TEMPLATE / "testcases" / "test_api_cases.py").read_text(encoding="utf-8")
    client = (FRAMEWORK_TEMPLATE / "core" / "client.py").read_text(encoding="utf-8")

    assert "business runtime variables" in suite_skill
    assert "one business-variable runtime scope per ordinary case" in generator_skill
    assert "Runtime scope materialization gate" in usability_gate
    assert "API teardown resilience gate" in usability_gate
    assert "Transport diagnostic evidence gate" in usability_gate
    assert "def prepare_case_runtime_context" in runtime_context
    assert "def case_runtime_scope" in conftest
    assert "case_runtime_scope" in conftest[conftest.index("def case_account_login(") : conftest.index(") -> list", conftest.index("def case_account_login("))]
    assert "preconditions" in conftest[conftest.index("def _collect_case_session_roles(") : conftest.index("def _resolve_auth_role_name(")]
    assert "finally:" in conftest[conftest.index("def case_data_manager(") : conftest.index("def sql_commands(")]
    assert "cleanup_errors" in data_manager
    assert "def apply_login_step_context" in auth_manager
    assert 'set_auth_context({"enabled": False})' in auth_manager
    assert "def _extract_step_values" in test_api
    assert "AuthManager.apply_login_step_context" in test_api
    assert "case_account_login" in test_api[test_api.index("def test_api_case(") : test_api.index("):", test_api.index("def test_api_case("))]
    assert "case_sql_manager" in test_api[test_api.index("def test_api_case(") : test_api.index("):", test_api.index("def test_api_case("))]
    assert "def _attach_transport_raw_response" in client
    assert "def _attach_transport_decode_failure" in client
    assert "request_envelope_field" in client
    assert "max_attachment_text_chars" in client


def test_runtime_resilience_validator_accepts_template_and_rejects_partial_materialization(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_runtime_resilience_test")
    template_errors: list[str] = []
    validator.validate_framework_runtime_resilience(FRAMEWORK_TEMPLATE, template_errors)
    assert template_errors == []

    framework = temp_root / "framework"
    write(framework / "conftest.py", "def case_runtime_scope():\n    pass\n")
    write(framework / "core" / "runtime_context.py", "")
    write(framework / "core" / "data_manager.py", "")
    write(framework / "core" / "auth_manager.py", "")
    write(framework / "core" / "client.py", "")
    write(framework / "core" / "transport_crypto.py", "")
    write(framework / "testcases" / "test_api_cases.py", "")
    partial_errors: list[str] = []

    validator.validate_framework_runtime_resilience(framework, partial_errors)

    assert any("缺少用例/长链路业务变量作用域初始化" in error for error in partial_errors)
    assert any("API cleanup" in error for error in partial_errors)
    assert any("显式登录" in error for error in partial_errors)
    assert any("解密前响应证据" in error for error in partial_errors)


def test_explicit_login_updates_alias_account_context_without_fallback() -> None:
    script = """
from core.auth_manager import AuthManager

class Codec:
    def hash_user_id(self, value):
        return f"hash-{value}"

class Client:
    crypto_codec = Codec()

runtime_context = {
    "auth_role_configs": {
        "provider": {"expected_user_id": 42, "token_prefix": "Bearer"},
        "provider_alias": "provider",
    }
}
auth_contexts = {
    "provider": {"enabled": False},
    "provider_alias": {"enabled": False},
}
context = AuthManager.apply_login_step_context(
    "provider_alias",
    {"token": "runtime-token", "sessionSecret": "runtime-secret", "user_id": 42, "deviceId": "device"},
    Client(),
    runtime_context,
    auth_contexts,
)
assert context["token_text"] == "Bearer runtime-token"
assert auth_contexts["provider"] is auth_contexts["provider_alias"]
assert runtime_context["provider_alias_context"]["userId"] == 42
runtime_context["auth_role_configs"]["no_prefix"] = {"token_prefix": ""}
auth_contexts["no_prefix"] = {"enabled": False}
no_prefix_context = AuthManager.apply_login_step_context(
    "no_prefix",
    {"token": "plain-token"},
    Client(),
    runtime_context,
    auth_contexts,
)
assert no_prefix_context["token_text"] == "plain-token"
try:
    AuthManager.apply_login_step_context("provider", {}, Client(), runtime_context, auth_contexts)
except ValueError:
    pass
else:
    raise AssertionError("missing token must fail")
"""

    result = run([sys.executable, "-B", "-c", script], cwd=FRAMEWORK_TEMPLATE)

    assert result.returncode == 0, result.stdout + result.stderr


def test_api_cleanup_continues_independent_rules_and_reports_failures() -> None:
    script = """
from core.data_manager import DataRuleExecutor

executor = DataRuleExecutor(object(), {})
calls = []

def execute(rule, stage):
    calls.append(rule["name"])
    if rule["name"] == "first":
        raise RuntimeError("first failed")
    return rule["name"]

executor._execute_rule = execute
try:
    executor.cleanup([{"name": "first"}, {"name": "second"}])
except AssertionError as error:
    assert "1 个失败规则" in str(error)
else:
    raise AssertionError("cleanup must report failure")
assert calls == ["first", "second"]
"""

    result = run([sys.executable, "-B", "-c", script], cwd=FRAMEWORK_TEMPLATE)

    assert result.returncode == 0, result.stdout + result.stderr


def test_flow_runner_must_share_runtime_scope_and_login_context_helpers(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_flow_runtime_resilience_test")
    framework = temp_root / "framework"
    shutil.copytree(FRAMEWORK_TEMPLATE, framework)
    flow_runner = framework / "core" / "flow_runner.py"
    write(flow_runner, "def run_flow():\n    pass\n")
    errors: list[str] = []

    validator.validate_framework_runtime_resilience(framework, errors)

    assert any("flow 开始前初始化共享作用域" in error for error in errors)
    assert any("flow_runner.py 未复用统一显式登录" in error for error in errors)

    write(
        flow_runner,
        "from core.auth_manager import AuthManager\n"
        "from core.runtime_context import prepare_case_runtime_context\n\n"
        "def run_flow(flow_id, env_config, runtime_context):\n"
        "    prepare_case_runtime_context\n"
        "    AuthManager.apply_login_step_context\n",
    )
    errors = []
    validator.validate_framework_runtime_resilience(framework, errors)
    assert any("flow 开始前初始化共享作用域" in error for error in errors)
    assert any("flow_runner.py 未复用统一显式登录" in error for error in errors)

    write(
        flow_runner,
        "from core.auth_manager import AuthManager\n"
        "from core.runtime_context import prepare_case_runtime_context\n\n"
        "def run_flow(flow_id, env_config, runtime_context):\n"
        "    prepare_case_runtime_context(runtime_context, env_config, flow_id)\n\n"
        "def _extract_step_values(client, runtime_context, auth_contexts):\n"
        "    AuthManager.apply_login_step_context('role', {}, client, runtime_context, auth_contexts)\n",
    )
    errors = []
    validator.validate_framework_runtime_resilience(framework, errors)
    assert errors == []


def test_runtime_resilience_gate_rejects_missing_capabilities_but_skips_case_free(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_runtime_resilience_scope_test")
    framework = temp_root / "framework"
    for relative_path in (
        "conftest.py",
        "core/runtime_context.py",
        "core/data_manager.py",
        "core/auth_manager.py",
        "core/client.py",
        "core/transport_crypto.py",
        "testcases/test_api_cases.py",
    ):
        write(framework / relative_path, "# legacy generated file\n")
    errors: list[str] = []

    validator.validate_framework_runtime_resilience(
        framework,
        errors,
        ordinary_case_required=True,
        flow_required=False,
    )

    assert any("case_runtime_scope" in error for error in errors)
    assert any("缺少解密前响应证据" in error for error in errors)

    errors = []
    validator.validate_framework_runtime_resilience(
        framework,
        errors,
        ordinary_case_required=False,
        flow_required=False,
    )
    assert errors == []


def test_anonymous_flow_does_not_require_login_context_helper(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_anonymous_flow_resilience_test")
    framework = temp_root / "framework"
    shutil.copytree(FRAMEWORK_TEMPLATE, framework)
    write(
        framework / "core" / "flow_runner.py",
        "from core.runtime_context import prepare_case_runtime_context\n\n"
        "def run_flow(flow_id, env_config, runtime_context):\n"
        "    prepare_case_runtime_context(runtime_context, env_config, flow_id)\n",
    )
    errors: list[str] = []

    validator.validate_framework_runtime_resilience(
        framework,
        errors,
        ordinary_case_required=False,
        flow_required=True,
        flow_login_required=False,
    )

    assert errors == []


def test_runtime_resilience_ordinary_only_does_not_require_flow_runner(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_ordinary_only_resilience_test")
    framework = temp_root / "framework"
    shutil.copytree(FRAMEWORK_TEMPLATE, framework)
    errors: list[str] = []

    validator.validate_framework_runtime_resilience(
        framework,
        errors,
        ordinary_case_required=True,
        flow_required=False,
    )

    assert errors == []


def test_framework_flow_login_detection_uses_declared_flow_steps(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_flow_login_detection_test")
    framework = temp_root / "framework"
    flow_path = framework / "data" / "flow_cases.yaml"
    write(
        flow_path,
        yaml.safe_dump(
            {
                "flows": [
                    {
                        "flow_id": "FLOW-PUBLIC",
                        "steps": [{"step_id": "STEP-QUERY", "step_type": "request"}],
                    }
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
    )
    errors: list[str] = []

    assert validator.framework_flow_has_login_step(framework, errors) is False
    assert errors == []

    write(
        flow_path,
        yaml.safe_dump(
            {
                "flows": [
                    {
                        "flow_id": "FLOW-AUTH",
                        "steps": [{"step_id": "STEP-LOGIN", "step_type": "login"}],
                    }
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
    )
    errors = []

    assert validator.framework_flow_has_login_step(framework, errors) is True
    assert errors == []


def test_transport_diagnostic_attachment_limit_is_configurable_and_bounded() -> None:
    script = """
from core.client import HttpClient, MAX_ATTACHMENT_TEXT_CHARS, _bounded_attachment_limit, _truncate_text

client = HttpClient(
    "https://example.invalid",
    5,
    transport_config={"diagnostics": {"max_attachment_text_chars": 7}},
)
assert client.max_attachment_text_chars == 7
assert _bounded_attachment_limit(MAX_ATTACHMENT_TEXT_CHARS + 1) == MAX_ATTACHMENT_TEXT_CHARS
assert _truncate_text("123456789", 7).startswith("1234567")
try:
    _bounded_attachment_limit(0)
except ValueError:
    pass
else:
    raise AssertionError("zero attachment limit must fail")
"""

    result = run([sys.executable, "-B", "-c", script], cwd=FRAMEWORK_TEMPLATE)

    assert result.returncode == 0, result.stdout + result.stderr


def test_runtime_resilience_template_collects_a_materialized_case(temp_root: Path) -> None:
    framework = temp_root / "framework"
    shutil.copytree(FRAMEWORK_TEMPLATE, framework)
    write(
        framework / "data" / "interfaces.yaml",
        yaml.safe_dump(
            {
                "schema_version": 1,
                "interfaces": [
                    {
                        "interface_id": "API-SMOKE",
                        "method": "GET",
                        "path": "/smoke",
                    }
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
    )
    write(
        framework / "data" / "cases" / "smoke.yaml",
        yaml.safe_dump(
            {
                "cases": [
                    {
                        "case_id": "TC-SMOKE",
                        "interface_id": "API-SMOKE",
                        "title": "模板收集验证",
                        "flow_type": "main",
                        "request": {},
                        "expected": {"status_code": 200},
                        "setup_cleanup_materialization": "not_required",
                        **confidence_payload(scope="framework"),
                    }
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
    )

    result = run(
        [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "-p",
            "no:allure_pytest",
            "-o",
            "addopts=",
            "--env=dev",
        ],
        cwd=framework,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 test collected" in result.stdout


def scenario_item(
    flow_id: str,
    scenario_name: str,
    *,
    verification: bool = True,
    link_keys: bool = True,
    steps: list[str] | None = None,
) -> str:
    steps = steps or ["POST /orders", "GET /orders/{id}"]
    verification_block = (
        "  verification:\n"
        "    interface: GET /orders/{id}\n"
        if verification
        else ""
    )
    link_block = "  link_keys:\n    - order_id\n" if link_keys else "  link_keys: []\n"
    step_lines = "\n".join(f"    - interface: {step}" for step in steps)
    return f"""- scenario_id: SCN-{flow_id.replace(':', '_')}
  flow_id: {flow_id}
  business_domain: 订单
  scenario_name: {scenario_name}
  pre_action:
    interface: POST /orders
  observable_change:
    type: 订单状态: 已创建
    evidence: 订单状态: 已创建且金额冻结
{verification_block}{link_block}  ordered_steps:
{step_lines}
  evidence_refs:
    - 业务规则: 下单后可查询订单
"""


def business_map(*items: str) -> str:
    return (
        "schema_version: 1\n"
        "stage: business_scenario_mapping\n"
        "status: passed\n"
        "next_stage_allowed: true\n"
        "source_entry: fixture\n"
        "scenario_items:\n"
        + "".join(items)
        + "blocking_issues: []\n"
    )


def single_interface_cluster_business_map() -> str:
    return """schema_version: 1
stage: business_scenario_mapping
status: passed
next_stage_allowed: true
source_entry: source
scenario_items:
  - scenario_id: SCN-ORDER-CREATE
    scenario_name: 用户创建订单
    business_domain: 订单
    executing_role: 用户
    business_description: 用户创建订单后系统生成订单记录
    roles:
      - 用户
    source_refs:
      - OrderController.java#create
    related_interfaces:
      - POST /api/v1/order/create
    business_chain:
      - 用户提交创建订单请求
      - 系统生成订单记录
    chain_type: single_interface
    flow_generation_required: false
    related_test_point_ids:
      - TP-ORDER-CREATE
    related_coverage_rule_ids:
      - RULE-ORDER-CREATE
    confidence: high
    blockers: []
  - scenario_id: SCN-ORDER-PAY
    scenario_name: 用户支付订单
    business_domain: 订单
    executing_role: 用户
    business_description: 用户支付订单后系统更新订单支付状态
    roles:
      - 用户
    source_refs:
      - OrderController.java#pay
    related_interfaces:
      - POST /api/v1/order/pay
    business_chain:
      - 用户提交订单支付请求
      - 系统更新订单支付状态
    chain_type: single_interface
    flow_generation_required: false
    related_test_point_ids:
      - TP-ORDER-PAY
    related_coverage_rule_ids:
      - RULE-ORDER-PAY
    confidence: high
    blockers: []
  - scenario_id: SCN-ORDER-DETAIL
    scenario_name: 用户查询订单详情
    business_domain: 订单
    executing_role: 用户
    business_description: 用户查询订单详情确认订单状态和金额
    roles:
      - 用户
    source_refs:
      - OrderController.java#detail
    related_interfaces:
      - GET /api/v1/order/detail
    business_chain:
      - 用户查询订单详情
      - 系统返回订单状态和金额
    chain_type: single_interface
    flow_generation_required: false
    related_test_point_ids:
      - TP-ORDER-DETAIL
    related_coverage_rule_ids:
      - RULE-ORDER-DETAIL
    confidence: high
    blockers: []
blocking_issues: []
"""


def business_long_chain_cases(*, path_bucket: bool = False) -> str:
    domain = "接口集合" if path_bucket else "订阅服务"
    name = "api/v1 资源从业务处理到结果校验" if path_bucket else "用户订阅后生成服务任务并查看今日进度"
    description = (
        "用户作为订阅用户在订阅权益生效后生成服务任务并查看今日服务进度，确认服务承诺进入可履约状态"
        if not path_bucket
        else "用户作为调用方按 /api/v1 路径前缀串联接口，资源从业务处理到结果校验"
    )
    return f"""schema_version: 1
stage: business_long_chain_design_denominator
status: passed
next_stage_allowed: true
denominator_scope: business_scenario_long_chain_design
business_long_chain_total: 1
business_long_chain_covered: 1
script_closed_loop_ready_total: 0
missing_business_long_chain_ids: []
chains:
  - chain_id: BLC-001
    case_id: DC-LC-001
    priority: p0
    business_domain: {domain}
    scenario_name: {name}
    business_description: {description}
    executing_role: 用户
    chain_kind: lifecycle
    interface_count: 3
    step_count: 3
    interfaces:
      - POST /subscriptions
      - POST /tasks/generate
      - GET /tasks/today
    source_refs:
      - source-api-facts.json#API-001
    related_test_point_ids:
      - TP-001
    related_coverage_rule_ids:
      - RULE-001
    required_flow_id: ""
    design_status: covered
    executable_status: need_execution_input
blocking_issues: []
"""


def create_executable_non_passed(out: Path) -> None:
    write(
        out / "执行级接口用例集.md",
        """## 执行级接口用例集

- 阶段状态：BLOCKED_NEED_EXECUTION_INPUT
- 生成状态：未生成
- 原因：执行级门禁未通过，详见 `前置数据构造规则.md`
""",
    )
    sections = (
        "阶段结论",
        "输入前置校验",
        "输入完整性检查",
        "数据模型索引",
        "环境与鉴权配置需求",
        "前置数据构造规则",
        "变量提取与注入规则",
        "链路脚本生成证据",
        "清理策略",
        "可重复执行校验",
        "脚本生成准出门禁",
        "缺失数据与待确认项",
        "pytest+allure 转换准出结论",
    )
    blocks: list[str] = []
    for section in sections:
        if section == "阶段结论":
            body = (
                "- 阶段状态：BLOCKED_NEED_EXECUTION_INPUT\n"
                "- 是否允许进入 pytest+allure 代码生成：否\n"
                "- 是否准出：否\n"
            )
        elif section == "缺失数据与待确认项":
            body = (
                "| 编号 | 缺失/待确认内容 | 涉及用例/接口 | 阻塞级别 | 需要提供的数据 | 建议来源 |\n"
                "|---|---|---|---|---|---|\n"
                "| B001 | 测试环境 base_url | 全部接口 | P0 | dev.base_url | 用户执行配置 |\n"
            )
        elif section == "pytest+allure 转换准出结论":
            body = (
                "- 阶段状态：BLOCKED_NEED_EXECUTION_INPUT\n"
                "- 是否允许进入 pytest+allure 代码生成：否\n"
                "- 是否准出：否\n"
            )
        else:
            body = "- 结论：阻塞，缺少执行输入\n"
        blocks.append(f"## {section}\n{body}")
    write(out / "前置数据构造规则.md", "\n".join(blocks))
    write(
        out / "stage_status.yaml",
        """schema_version: 1
stage: executable_interface_case_set
status: blocked
next_stage_allowed: false
input_paths: []
output_paths: []
gate_checks: []
blocking_issues:
  - 缺少执行配置
""",
    )
    write(
        out / "coverage_matrix.yaml",
        """schema_version: 1
stage: executable_interface_case_set
coverage_summary: {}
coverage_items: []
missing_items: []
upstream_downstream_mappings: []
""",
    )
    write(
        out / "execution_fact_sources.yaml",
        """schema_version: 1
stage: executable_interface_case_set
status: blocked
required_human_inputs:
  - type: environment_reference
    status: missing
  - type: authentication_account
    status: missing
fact_sources:
  - fact_type: token_rule
    status: missing
  - fact_type: test_data_rule
    status: missing
  - fact_type: variable_link
    status: missing
  - fact_type: chain_flow
    status: missing
  - fact_type: assertion_rule
    status: missing
  - fact_type: cleanup_strategy
    status: missing
missing_required_facts:
  - environment_reference
conflict_facts: []
blocking_issues:
  - 缺少执行输入
""",
    )


def create_runtime_evidence(root: Path, *, token_plaintext: bool = False) -> None:
    runtime_dir = root / "04-runtime-evidence"
    field_value = "secret-token-value" if token_plaintext else "<redacted>"
    redacted = "false" if token_plaintext else "true"
    write(
        runtime_dir / "runtime_stage_status.yaml",
        """schema_version: 1
stage: runtime_live_evidence
status: passed
next_stage_allowed: true
request_scope:
  env_name: test
  allowed_modules: [user]
  mutating_requests_allowed: false
  cleanup_required: false
input_paths:
  - path: runtime_request_plan.yaml
    role: runtime_request_plan
output_paths:
  - path: runtime_evidence.yaml
    role: runtime_evidence
gate_checks:
  - check_id: direct_request_execution
    status: passed
    evidence_refs: [runtime_evidence.yaml]
blocking_issues: []
""",
    )
    write(
        runtime_dir / "runtime_evidence.yaml",
        f"""schema_version: 1
stage: runtime_live_evidence
status: passed
next_stage_allowed: true
request_scope:
  env_name: test
  allowed_modules: [user]
  mutating_requests_allowed: false
  cleanup_required: false
auth_evidence:
  status: confirmed
  token_source: login_response
  token_extract_path: "$.data.token"
  secret_redaction: enabled
evidence_items:
  - evidence_id: RT-LOGIN-001
    flow_id: FLOW-LOGIN
    case_id: DC-001
    method: POST
    path: /api/v1/auth/login
    source_contract_ref: 接口结构化契约清单.md#login
    request_source_ref: runtime_request_plan.yaml#login
    response_status: 200
    value_type: token
    field_path: "$.data.token"
    field_value: "{field_value}"
    source_status: confirmed
    usable_for_execution_case: true
    redacted: {redacted}
  - evidence_id: RT-USER-001
    flow_id: FLOW-LOGIN
    case_id: DC-002
    method: GET
    path: /api/v1/user/profile
    source_contract_ref: 接口结构化契约清单.md#profile
    request_source_ref: runtime_request_plan.yaml#profile
    response_status: 200
    value_type: enum_code
    field_path: "$.data.status"
    field_value: ACTIVE
    source_status: confirmed
    usable_for_execution_case: true
    redacted: false
conflict_items: []
blocking_issues: []
""",
    )
    write(
        runtime_dir / "runtime_value_catalog.yaml",
        """schema_version: 1
stage: runtime_value_catalog
status: passed
values:
  - value_id: VAL-USER-STATUS-ACTIVE
    value_type: enum_code
    field: userStatus
    value: ACTIVE
    source_type: live_request_evidence
    source_ref: runtime_evidence.yaml#RT-USER-001
    cross_checked_by:
      - 数据模型.md#user_status
      - 接口结构化契约清单.md#UserStatus
    source_status: confirmed
usable_fact_types:
  - token_rule
  - test_data_rule
  - variable_link
  - assertion_rule
missing_values: []
conflict_values: []
blocking_issues: []
""",
    )


def test_entry_route_exposes_downstream_missing_inputs(temp_root: Path) -> None:
    select_mod = load_module(SELECT_ROUTE, "select_entry_route_test")
    prd = temp_root / "PRD.md"
    api = temp_root / "API.md"
    system_analysis = temp_root / "系统分析.md"
    data_model = temp_root / "数据模型.md"
    for path in (prd, api, system_analysis):
        write(path, f"# {path.stem}\n有效内容\n")
    write(data_model, "# 数据模型\n## 表结构\n| 表名 | 字段 |\n|---|---|\n| user_account | id |\n")

    route = select_mod.decide_route(
        str(prd),
        str(api),
        str(system_analysis),
        None,
        str(data_model),
        None,
        "framework",
    )
    bad_config = temp_root / "bad_exec.txt"
    write(bad_config, "无环境引用\n鉴权账号：example-account\n")

    assert route["route"] == "pre-doc-analysis-pipeline"
    assert route["downstream_missing_inputs"]
    assert set(select_mod.execution_config_missing_items(str(bad_config))) == {"环境引用", "鉴权账号"}


def test_chain_denominator_filters_incomplete_candidates_and_outputs_valid_yaml(temp_root: Path) -> None:
    output_root = temp_root / "pipeline"
    write(
        output_root / "01-pre-doc-analysis" / "business_scenario_map.yaml",
        business_map(scenario_item("flow:order_create", "订单: 创建后查询")),
    )
    write(
        output_root / "02-source-api-facts" / "docs" / "source-facts" / "business_scenario_map.yaml",
        business_map(scenario_item("source_only", "源码链路", verification=False, steps=["POST /orders", "POST /orders/confirm"])),
    )

    completed = run([sys.executable, str(BUILD_CHAIN), "--output-root", str(output_root)])

    required = yaml.safe_load((output_root / "required_chain_flows.yaml").read_text(encoding="utf-8"))
    audit = yaml.safe_load((output_root / "chain_flow_candidate_audit.yaml").read_text(encoding="utf-8"))
    assert completed.returncode == 0, completed.stderr
    assert required["required_chain_flow_count"] == 1
    assert required["flows"][0]["flow_id"] == "flow:order_create"
    assert audit["candidate_summary"]["design_short_chain_state_transition"] == 1
    assert audit["candidate_summary"]["excluded_missing_verification"] == 0


def test_chain_denominator_writes_candidate_inventory_and_infers_from_ordered_steps(temp_root: Path) -> None:
    output_root = temp_root / "pipeline_inventory_infer"
    write(
        output_root / "01-pre-doc-analysis" / "business_scenario_map.yaml",
        """schema_version: 1
stage: business_scenario_mapping
status: passed
next_stage_allowed: true
source_entry: fixture
scenario_items:
  - scenario_id: SCN-INFER-FLOW
    flow_id: FLOW-INFER-FLOW
    business_domain: 订单
    scenario_name: 订单支付后查询订单状态
    executing_role: 用户
    business_description: 用户提交订单并完成支付后查询订单状态确认订单进入已支付状态
    observable_change:
      type: 订单状态变更
      evidence: 订单状态从待支付变为已支付
    link_keys:
      - order_id
    ordered_steps:
      - interface: POST /orders
      - interface: POST /payments
      - interface: GET /orders/{id}
    evidence_refs:
      - 业务规则#订单支付后可查询状态
blocking_issues: []
""",
    )

    completed = run([sys.executable, str(BUILD_CHAIN), "--output-root", str(output_root)])

    required = yaml.safe_load((output_root / "required_chain_flows.yaml").read_text(encoding="utf-8"))
    inventory = yaml.safe_load((output_root / "business_chain_candidate_inventory.yaml").read_text(encoding="utf-8"))
    item = inventory["items"][0]
    assert completed.returncode == 0, completed.stderr
    assert required["required_chain_flow_count"] == 1
    assert required["flows"][0]["pre_action"]["interface"] == "POST /orders"
    assert required["flows"][0]["verification"]["interface"] == "GET /orders/{id}"
    assert item["candidate_type"] == "business_long_chain_ready"
    assert item["inferred_fields"] == ["pre_action_interface_from_steps", "verification_interface_from_steps"]
    assert item["missing_evidence"] == []


def test_chain_denominator_reads_source_style_yaml_steps_and_source_refs(temp_root: Path) -> None:
    output_root = temp_root / "pipeline_source_style_yaml"
    write(
        output_root / "02-source-api-facts" / "docs" / "source-facts" / "business_scenario_map.yaml",
        """schema_version: 1
stage: business_scenario_mapping
status: passed
next_stage_allowed: true
source_entry: source
scenario_items:
- scenario_id: SCN-SOURCE-STYLE
  flow_id: FLOW-SOURCE-STYLE
  business_domain: 订单
  scenario_name: 用户创建订单后查询订单状态
  executing_role: 用户
  business_description: 用户创建订单后查询订单状态，确认订单记录已经进入可查看状态
  chain_type: e2e_flow_candidate
  flow_generation_required: true
  observable_change:
    type: 订单记录创建
    evidence: 订单记录由不存在变为已创建
  link_keys:
  - order_id
  source_refs:
  - OrderController.java:10 | OrderController.create
  - OrderController.java:20 | OrderController.detail
  ordered_step_count: 3
  ordered_steps:
  - step_order: 1
    interface: POST /orders
    source_ref: OrderController.java:10 | OrderController.create
  - step_order: 2
    interface: POST /orders/pay
    source_ref: PaymentController.java:15 | PaymentController.pay
  - step_order: 3
    interface: GET /orders/{id}
    source_ref: OrderController.java:20 | OrderController.detail
blocking_issues: []
""",
    )

    completed = run([sys.executable, str(BUILD_CHAIN), "--output-root", str(output_root)])

    required = yaml.safe_load((output_root / "required_chain_flows.yaml").read_text(encoding="utf-8"))
    inventory = yaml.safe_load((output_root / "business_chain_candidate_inventory.yaml").read_text(encoding="utf-8"))
    item = inventory["items"][0]
    assert completed.returncode == 0, completed.stderr
    assert required["required_chain_flow_count"] == 1
    assert required["flows"][0]["steps"] == ["POST /orders", "POST /orders/pay", "GET /orders/{id}"]
    assert item["evidence_refs"] == [
        "OrderController.java:10 | OrderController.create",
        "OrderController.java:20 | OrderController.detail",
    ]
    assert item["missing_evidence"] == []


def test_chain_denominator_keeps_missing_link_key_in_candidate_inventory(temp_root: Path) -> None:
    output_root = temp_root / "pipeline_inventory_missing_link_key"
    write(
        output_root / "01-pre-doc-analysis" / "business_scenario_map.yaml",
        """schema_version: 1
stage: business_scenario_mapping
status: passed
next_stage_allowed: true
source_entry: fixture
scenario_items:
  - scenario_id: SCN-MISSING-LINK-KEY
    flow_id: FLOW-MISSING-LINK-KEY
    business_domain: 订单
    scenario_name: 订单支付后查询订单状态
    executing_role: 用户
    business_description: 用户提交订单并完成支付后查询订单状态确认订单进入已支付状态
    chain_type: e2e_flow_candidate
    pre_action:
      interface: POST /orders
    observable_change:
      type: 订单状态变更
      evidence: 订单状态从待支付变为已支付
    verification:
      interface: GET /orders/{id}
    link_keys: []
    ordered_steps:
      - interface: POST /orders
      - interface: POST /payments
      - interface: GET /orders/{id}
    evidence_refs:
      - 业务规则#订单支付后可查询状态
blocking_issues: []
""",
    )

    completed = run([sys.executable, str(BUILD_CHAIN), "--output-root", str(output_root)])

    required = yaml.safe_load((output_root / "required_chain_flows.yaml").read_text(encoding="utf-8"))
    audit = yaml.safe_load((output_root / "chain_flow_candidate_audit.yaml").read_text(encoding="utf-8"))
    inventory = yaml.safe_load((output_root / "business_chain_candidate_inventory.yaml").read_text(encoding="utf-8"))
    item = inventory["items"][0]
    assert completed.returncode == 0, completed.stderr
    assert required["required_chain_flow_count"] == 0
    assert required["flows"] == []
    assert audit["candidates"][0]["classification"] == "design_long_chain_only"
    assert item["candidate_type"] == "business_long_chain_need_execution_evidence"
    assert item["missing_evidence"] == ["link_keys"]


def test_chain_denominator_rejects_path_bucket_even_with_closed_loop_evidence(temp_root: Path) -> None:
    output_root = temp_root / "pipeline_path_bucket"
    write(
        output_root / "01-pre-doc-analysis" / "business_scenario_map.yaml",
        """schema_version: 1
stage: business_scenario_mapping
status: passed
next_stage_allowed: true
source_entry: fixture
scenario_items:
  - scenario_id: SCN-PATH-BUCKET
    flow_id: FLOW-PATH-BUCKET
    business_domain: 接口集合
    scenario_name: /api/v1/app 接口链路
    executing_role: 用户
    business_description: 用户在 /api/v1/app 路径前缀下依次调用多个接口完成接口链路处理
    pre_action:
      interface: POST /api/v1/app/foo/create
    observable_change:
      type: 接口返回记录创建
      evidence: 接口返回中出现 id
    verification:
      interface: GET /api/v1/app/foo/detail
    link_keys:
      - id
    ordered_steps:
      - interface: POST /api/v1/app/foo/create
      - interface: GET /api/v1/app/foo/detail
      - interface: GET /api/v1/app/foo/list
    evidence_refs:
      - source-api-facts.json#PATH-BUCKET
blocking_issues: []
""",
    )

    completed = run([sys.executable, str(BUILD_CHAIN), "--output-root", str(output_root)])

    required = yaml.safe_load((output_root / "required_chain_flows.yaml").read_text(encoding="utf-8"))
    audit = yaml.safe_load((output_root / "chain_flow_candidate_audit.yaml").read_text(encoding="utf-8"))
    assert completed.returncode == 0, completed.stderr
    assert required["required_chain_flow_count"] == 0
    assert required["flows"] == []
    assert audit["candidates"][0]["classification"] == "excluded_missing_change_evidence"
    assert "真实业务场景" in audit["candidates"][0]["reason"]


def test_chain_denominator_classifies_mutation_before_readonly(temp_root: Path) -> None:
    output_root = temp_root / "pipeline_single_mutation"
    write(
        output_root / "01-pre-doc-analysis" / "business_scenario_map.yaml",
        """schema_version: 1
stage: business_scenario_mapping
status: passed
next_stage_allowed: true
source_entry: fixture
scenario_items:
  - scenario_id: SCN-REWARD-CLAIM
    flow_id: FLOW-REWARD-CLAIM
    business_domain: 活动奖励
    scenario_name: 领取奖励
    executing_role: 用户
    business_description: 用户在完成任务后领取奖励
    related_interfaces:
      - POST /reward/claim
    evidence_refs:
      - source-api-facts.json#API-REWARD-CLAIM
blocking_issues: []
""",
    )

    completed = run([sys.executable, str(BUILD_CHAIN), "--output-root", str(output_root)])

    audit = yaml.safe_load((output_root / "chain_flow_candidate_audit.yaml").read_text(encoding="utf-8"))
    candidate = audit["candidates"][0]
    assert completed.returncode == 0, completed.stderr
    assert candidate["classification"] == "single_interface_mutation"
    assert audit["candidate_summary"]["single_interface_mutation"] == 1
    assert audit["candidate_summary"]["single_interface_readonly"] == 0


def test_chain_denominator_does_not_include_candidates_without_steps_or_evidence(temp_root: Path) -> None:
    output_root = temp_root / "pipeline_missing_steps"
    write(
        output_root / "01-pre-doc-analysis" / "business_scenario_map.yaml",
        """schema_version: 1
stage: business_scenario_mapping
status: passed
next_stage_allowed: true
source_entry: fixture
scenario_items:
  - scenario_id: SCN-MISSING-STEPS
    flow_id: FLOW-MISSING-STEPS
    business_domain: 订单
    scenario_name: 订单创建后查询
    pre_action:
      interface: POST /orders
    observable_change:
      type: 订单状态变更
      evidence: 订单从未创建变为已创建
    verification:
      interface: GET /orders/{id}
    link_keys:
      - order_id
    ordered_steps: []
    evidence_refs: []
blocking_issues: []
""",
    )

    completed = run([sys.executable, str(BUILD_CHAIN), "--output-root", str(output_root)])

    required = yaml.safe_load((output_root / "required_chain_flows.yaml").read_text(encoding="utf-8"))
    audit = yaml.safe_load((output_root / "chain_flow_candidate_audit.yaml").read_text(encoding="utf-8"))
    assert completed.returncode == 0, completed.stderr
    assert required["required_chain_flow_count"] == 0
    assert required["flows"] == []
    assert audit["candidate_summary"]["excluded_missing_link_key"] == 1


def test_chain_readiness_reconciliation_promotes_capability_ready_flow(temp_root: Path) -> None:
    output_root = temp_root / "pipeline_reconciliation"
    write(
        output_root / "01-pre-doc-analysis" / "business_scenario_map.yaml",
        """schema_version: 1
stage: business_scenario_mapping
status: passed
next_stage_allowed: true
source_entry: fixture
scenario_items:
  - scenario_id: SCN-RECONCILE
    flow_id: FLOW-RECONCILE
    business_domain: 订单
    scenario_name: 订单创建后查询
    chain_type: e2e_flow_candidate
    flow_generation_required: true
    ordered_steps:
      - interface: POST /orders
      - interface: GET /orders/{id}
blocking_issues: []
""",
    )
    completed = run([sys.executable, str(BUILD_CHAIN), "--output-root", str(output_root)])
    assert completed.returncode == 0, completed.stderr
    before = yaml.safe_load((output_root / "required_chain_flows.yaml").read_text(encoding="utf-8"))
    assert before["required_chain_flow_count"] == 0

    fact_path = output_root / "04-runtime-evidence" / "runtime_evidence.yaml"
    write(fact_path, "schema_version: 1\nevidence_items: []\n")
    reconciliation = {
        "schema_version": 1,
        "stage": "chain_execution_readiness_reconciliation",
        "status": "ready_for_generation",
        "target_depth": "executable",
        "fact_revisions": [
            {"path": "04-runtime-evidence/runtime_evidence.yaml", "sha256": file_sha256(fact_path)}
        ],
        "ready_chain_count": 1,
        "generate_count": 1,
        "explicit_exclusion_count": 0,
        "pending_chain_count": 0,
        "ready_chains": [
            {
                "flow_id": "FLOW-RECONCILE",
                "decision": "generate",
                "closure_capability": "write_restore",
                "supported_target_depths": ["executable", "framework"],
                "materialization_status": "ready",
                "unresolved_materialization_items": [],
                "closure_evidence_refs": ["04-runtime-evidence/runtime_evidence.yaml#RT-001"],
                "required_flow": {
                    "source_route": "doc",
                    "scenario_id": "SCN-RECONCILE",
                    "business_domain": "订单",
                    "scenario_name": "订单创建后查询",
                    "pre_action": {"interface": "POST /orders"},
                    "observable_change": {"type": "订单创建", "evidence": "订单由不存在变为可查询"},
                    "verification": {"interface": "GET /orders/{id}"},
                    "link_keys": ["order_id"],
                    "steps": ["POST /orders", "GET /orders/{id}"],
                    "evidence_refs": ["04-runtime-evidence/runtime_evidence.yaml#RT-001"],
                },
            }
        ],
        "pending_chains": [],
        "blocking_issues": [],
    }
    reconciliation_path = temp_root / "reconciliation.yaml"
    write(reconciliation_path, yaml.safe_dump(reconciliation, allow_unicode=True, sort_keys=False))

    completed = run(
        [
            sys.executable,
            str(BUILD_CHAIN),
            "--output-root",
            str(output_root),
            "--readiness-reconciliation",
            str(reconciliation_path),
        ]
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    required = yaml.safe_load((output_root / "required_chain_flows.yaml").read_text(encoding="utf-8"))
    inventory = yaml.safe_load((output_root / "business_chain_candidate_inventory.yaml").read_text(encoding="utf-8"))
    assert required["required_chain_flow_count"] == 1
    assert required["flows"][0]["flow_id"] == "FLOW-RECONCILE"
    assert inventory["items"][0]["candidate_type"] == "business_long_chain_ready"
    assert inventory["items"][0]["missing_evidence"] == []


def test_chain_readiness_reconciliation_rejects_stale_fact_revision_without_rewrite(temp_root: Path) -> None:
    output_root = temp_root / "pipeline_stale_reconciliation"
    write(
        output_root / "01-pre-doc-analysis" / "business_scenario_map.yaml",
        business_map(scenario_item("FLOW-STALE", "订单创建后查询")),
    )
    completed = run([sys.executable, str(BUILD_CHAIN), "--output-root", str(output_root)])
    assert completed.returncode == 0
    required_path = output_root / "required_chain_flows.yaml"
    before = required_path.read_text(encoding="utf-8")
    fact_path = output_root / "04-runtime-evidence" / "runtime_evidence.yaml"
    write(fact_path, "schema_version: 1\nevidence_items: []\n")
    reconciliation = {
        "schema_version": 1,
        "stage": "chain_execution_readiness_reconciliation",
        "status": "ready_for_generation",
        "target_depth": "executable",
        "fact_revisions": [{"path": "04-runtime-evidence/runtime_evidence.yaml", "sha256": "0" * 64}],
        "ready_chain_count": 0,
        "generate_count": 0,
        "explicit_exclusion_count": 0,
        "pending_chain_count": 0,
        "ready_chains": [],
        "pending_chains": [],
        "blocking_issues": [],
    }
    reconciliation_path = temp_root / "stale.yaml"
    write(reconciliation_path, yaml.safe_dump(reconciliation, allow_unicode=True, sort_keys=False))

    completed = run(
        [
            sys.executable,
            str(BUILD_CHAIN),
            "--output-root",
            str(output_root),
            "--readiness-reconciliation",
            str(reconciliation_path),
        ]
    )

    assert completed.returncode == 2
    assert "必须重新计算链路分母" in completed.stdout
    assert required_path.read_text(encoding="utf-8") == before


def test_chain_readiness_reconciliation_removes_explicitly_excluded_ready_flow(temp_root: Path) -> None:
    output_root = temp_root / "pipeline_reconciliation_exclusion"
    write(
        output_root / "01-pre-doc-analysis" / "business_scenario_map.yaml",
        business_map(scenario_item("FLOW-EXCLUDE", "订单创建后查询")),
    )
    fact_path = output_root / "04-runtime-evidence" / "runtime_evidence.yaml"
    write(fact_path, "schema_version: 1\nevidence_items: []\n")
    reconciliation = {
        "schema_version": 1,
        "stage": "chain_execution_readiness_reconciliation",
        "status": "ready_for_generation",
        "target_depth": "executable",
        "fact_revisions": [
            {"path": "04-runtime-evidence/runtime_evidence.yaml", "sha256": file_sha256(fact_path)}
        ],
        "ready_chain_count": 1,
        "generate_count": 0,
        "explicit_exclusion_count": 1,
        "pending_chain_count": 0,
        "ready_chains": [
            {
                "flow_id": "FLOW-EXCLUDE",
                "decision": "exclude",
                "closure_capability": "read_only_verified",
                "supported_target_depths": ["executable"],
                "materialization_status": "ready",
                "unresolved_materialization_items": [],
                "closure_evidence_refs": ["04-runtime-evidence/runtime_evidence.yaml#RT-EXCLUDE"],
                "exclusion_reason_code": "OUT_OF_SELECTED_RUN_SCOPE",
                "exclusion_evidence_refs": ["04-design-case-handoff/business_long_chain_cases.yaml#FLOW-EXCLUDE"],
                "executable_case_ids": [],
            }
        ],
        "pending_chains": [],
        "blocking_issues": [],
    }
    path = output_root / "chain_execution_readiness_reconciliation.yaml"
    write(path, yaml.safe_dump(reconciliation, allow_unicode=True, sort_keys=False))

    completed = run(
        [
            sys.executable,
            str(BUILD_CHAIN),
            "--output-root",
            str(output_root),
            "--readiness-reconciliation",
            str(path),
        ]
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    required = yaml.safe_load((output_root / "required_chain_flows.yaml").read_text(encoding="utf-8"))
    audit = yaml.safe_load((output_root / "chain_flow_candidate_audit.yaml").read_text(encoding="utf-8"))
    inventory = yaml.safe_load((output_root / "business_chain_candidate_inventory.yaml").read_text(encoding="utf-8"))
    assert required["required_chain_flow_count"] == 0
    assert audit["candidates"][0]["classification"] == "excluded_ready_by_policy"
    assert inventory["items"][0]["candidate_type"] == "business_long_chain_ready"


def test_filled_long_chain_facts_cannot_pass_zero_denominator_without_reconciliation(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_filled_chain_reconciliation_test")
    root = temp_root / "pipeline_filled_without_reconciliation"
    checklist_path = root / "05-executable-interface-case-set" / "long_chain_missing_value_fields.yaml"
    write(
        checklist_path,
        "schema_version: 1\nfilled_count: 1\nopen_required_count: 0\n",
    )
    errors: list[str] = []
    validator.validate_chain_execution_readiness_reconciliation(root, "executable", set(), errors)
    assert any("缺少 chain_execution_readiness_reconciliation.yaml" in error for error in errors), errors
    assert any("filled_count > 0" in error for error in errors), errors


def test_chain_readiness_conservation_accepts_explicit_exclusion_and_capability_variants(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_chain_conservation_test")
    root = temp_root / "pipeline_chain_conservation"
    fact_path = root / "04-runtime-evidence" / "runtime_evidence.yaml"
    write(fact_path, "schema_version: 1\nevidence_items: []\n")
    checklist_path = root / "05-executable-interface-case-set" / "long_chain_missing_value_fields.yaml"
    write(
        checklist_path,
        "schema_version: 1\nfilled_count: 1\nopen_required_count: 0\n",
    )
    reconciliation = {
        "schema_version": 1,
        "stage": "chain_execution_readiness_reconciliation",
        "status": "passed",
        "target_depth": "executable",
        "fact_revisions": [
            {"path": "04-runtime-evidence/runtime_evidence.yaml", "sha256": file_sha256(fact_path)},
            {
                "path": "05-executable-interface-case-set/long_chain_missing_value_fields.yaml",
                "sha256": file_sha256(checklist_path),
            },
        ],
        "ready_chain_count": 1,
        "generate_count": 0,
        "explicit_exclusion_count": 1,
        "pending_chain_count": 0,
        "ready_chains": [
            {
                "flow_id": "FLOW-EXCLUDED",
                "decision": "exclude",
                "closure_capability": "sandbox_mock_callback",
                "supported_target_depths": ["executable"],
                "materialization_status": "ready",
                "unresolved_materialization_items": [],
                "closure_evidence_refs": ["04-runtime-evidence/runtime_evidence.yaml#RT-EXCLUDED"],
                "exclusion_reason_code": "BUSINESS_SCOPE_EXCLUDED",
                "exclusion_evidence_refs": ["04-design-case-handoff/business_long_chain_cases.yaml#FLOW-EXCLUDED"],
                "executable_case_ids": [],
            }
        ],
        "pending_chains": [],
        "blocking_issues": [],
    }
    write(
        root / "chain_execution_readiness_reconciliation.yaml",
        yaml.safe_dump(reconciliation, allow_unicode=True, sort_keys=False),
    )

    errors: list[str] = []
    validator.validate_chain_execution_readiness_reconciliation(root, "executable", set(), errors)
    assert errors == []


def test_chain_readiness_conservation_requires_generated_mapping_exactly_once(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_chain_exact_mapping_test")
    root = temp_root / "pipeline_chain_exact_mapping"
    fact_path = root / "04-runtime-evidence" / "runtime_evidence.yaml"
    write(fact_path, "schema_version: 1\nevidence_items: []\n")
    write(root / "05-executable-interface-case-set" / "执行级接口用例集.md", "# 用例\n\nEXE-FLOW-001\n")
    reconciliation = {
        "schema_version": 1,
        "stage": "chain_execution_readiness_reconciliation",
        "status": "passed",
        "target_depth": "executable",
        "fact_revisions": [
            {"path": "04-runtime-evidence/runtime_evidence.yaml", "sha256": file_sha256(fact_path)}
        ],
        "ready_chain_count": 1,
        "generate_count": 1,
        "explicit_exclusion_count": 0,
        "pending_chain_count": 0,
        "ready_chains": [
            {
                "flow_id": "FLOW-001",
                "decision": "generate",
                "closure_capability": "read_only_verified",
                "supported_target_depths": ["executable", "framework"],
                "materialization_status": "ready",
                "unresolved_materialization_items": [],
                "closure_evidence_refs": ["04-runtime-evidence/runtime_evidence.yaml#RT-001"],
                "executable_case_ids": ["EXE-FLOW-001"],
            }
        ],
        "pending_chains": [],
        "blocking_issues": [],
    }
    path = root / "chain_execution_readiness_reconciliation.yaml"
    write(path, yaml.safe_dump(reconciliation, allow_unicode=True, sort_keys=False))
    errors: list[str] = []
    validator.validate_chain_execution_readiness_reconciliation(root, "executable", {"FLOW-001"}, errors)
    assert errors == []

    reconciliation["ready_chains"].append(dict(reconciliation["ready_chains"][0]))
    reconciliation["ready_chain_count"] = 2
    reconciliation["generate_count"] = 1
    write(path, yaml.safe_dump(reconciliation, allow_unicode=True, sort_keys=False))
    errors = []
    validator.validate_chain_execution_readiness_reconciliation(root, "executable", {"FLOW-001"}, errors)
    assert any("必须且只能出现一次" in error for error in errors), errors


def test_chain_alignment_marks_step_diff_and_single_sided_flows(temp_root: Path) -> None:
    output_root = temp_root / "alignment"
    write(
        output_root / "01-pre-doc-analysis" / "business_scenario_map.yaml",
        business_map(
            scenario_item("shared_flow", "文档同源", steps=["POST /a", "GET /a"]),
            scenario_item("doc_only_flow", "仅文档", steps=["POST /b", "GET /b"]),
        ),
    )
    write(
        output_root / "02-source-api-facts" / "docs" / "source-facts" / "business_scenario_map.yaml",
        business_map(
            scenario_item("shared_flow", "源码同源", steps=["POST /a", "GET /a/detail"]),
            scenario_item("source_only_flow", "仅源码", steps=["POST /c", "GET /c"]),
        ),
    )

    completed = run([sys.executable, str(BUILD_CHAIN), "--output-root", str(output_root)])

    alignment = yaml.safe_load((output_root / "chain_flow_alignment.yaml").read_text(encoding="utf-8"))
    statuses = {item["flow_id"]: item["alignment_status"] for item in alignment["alignment_items"]}
    assert completed.returncode == 0, completed.stderr
    assert statuses == {
        "doc_only_flow": "doc_only",
        "shared_flow": "both_step_diff",
        "source_only_flow": "source_only",
    }


def test_chain_candidate_audit_summary_and_candidate_completeness_are_validated(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_outputs_chain_audit_test")
    root = temp_root / "pipeline"
    write(
        root / "business_chain_candidate_inventory.yaml",
        """schema_version: 1
stage: business_chain_candidate_inventory
status: passed
next_stage_allowed: true
candidate_total: 1
candidate_type_summary:
  business_long_chain_ready: 1
  business_long_chain_need_execution_evidence: 0
  short_state_transition: 0
  single_interface_mutation: 0
  readonly: 0
  external_or_callback: 0
  missing_evidence_candidate: 0
items:
  - candidate_id: CAND-001
    candidate_type: business_long_chain_ready
    classification: included
    flow_id: FLOW-001
    scenario_id: SCN-001
    source_route: doc
    downstream_target: required_chain_flows
    inferred_fields: []
    discovery_signals:
      - ordered_steps_evidenced
    missing_evidence: []
    steps:
      - POST /orders
      - GET /orders/{id}
    evidence_refs:
      - 业务规则#订单创建后可查询
    reason: 闭环证据完整
blocking_issues: []
""",
    )
    write(
        root / "required_chain_flows.yaml",
        """schema_version: 1
stage: required_chain_flow_denominator
status: passed
next_stage_allowed: true
required_chain_flow_count: 1
unclassified_candidate_flows: []
flows:
  - flow_id: FLOW-001
    source_route: doc
    evidence_routes:
      - doc
    business_domain: 订单
    scenario_name: 订单创建后查询
    pre_action:
      interface: POST /orders
    observable_change:
      type: 订单状态变更
      evidence: 订单从未创建变为已创建
    verification:
      interface: GET /orders/{id}
    link_keys:
      - order_id
    steps:
      - POST /orders
      - GET /orders/{id}
    evidence_refs:
      - 业务规则#订单创建后可查询
    status: required
blocking_issues: []
""",
    )
    write(
        root / "chain_flow_candidate_audit.yaml",
        """schema_version: 1
stage: chain_flow_candidate_audit
status: passed
next_stage_allowed: true
candidate_summary:
  included: 0
  excluded_missing_verification: 99
  excluded_missing_change_evidence: 0
  excluded_missing_link_key: 0
  excluded_readonly: 0
  unclassified: 0
candidates:
  - candidate_id: CAND-001
    classification: included
    flow_id: FLOW-001
    source_route: doc
    evidence_refs:
      - 业务规则#订单创建后可查询
    reason: 闭环证据完整
unclassified_candidate_flows: []
blocking_issues: []
""",
    )

    errors: list[str] = []
    validator.validate_chain_flow_denominator(root, errors, True, False, {"FLOW-001"})
    assert any("candidate_summary.included" in error for error in errors), errors
    assert any("excluded_missing_verification" in error for error in errors), errors

    write(
        root / "chain_flow_candidate_audit.yaml",
        """schema_version: 1
stage: chain_flow_candidate_audit
status: passed
next_stage_allowed: true
candidate_summary:
  included: 0
  excluded_missing_verification: 0
  excluded_missing_change_evidence: 0
  excluded_missing_link_key: 0
  excluded_readonly: 0
  unclassified: 0
candidates: []
unclassified_candidate_flows: []
blocking_issues: []
""",
    )
    errors = []
    validator.validate_chain_flow_denominator(root, errors, True, False, {"FLOW-001"})
    assert any("未覆盖选定入口" in error for error in errors), errors


def test_chain_candidate_inventory_summary_and_type_consistency_are_validated(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_outputs_inventory_test")
    root = temp_root / "pipeline_inventory_validator"
    write(
        root / "business_chain_candidate_inventory.yaml",
        """schema_version: 1
stage: business_chain_candidate_inventory
status: passed
next_stage_allowed: true
candidate_total: 2
candidate_type_summary:
  business_long_chain_ready: 1
  business_long_chain_need_execution_evidence: 0
  short_state_transition: 0
  single_interface_mutation: 0
  readonly: 0
  external_or_callback: 0
  missing_evidence_candidate: 0
items:
  - candidate_id: CAND-001
    candidate_type: readonly
    classification: included
    flow_id: FLOW-001
    scenario_id: SCN-001
    source_route: doc
    downstream_target: required_chain_flows
blocking_issues: []
""",
    )

    errors: list[str] = []
    validator.validate_business_chain_candidate_inventory_file(root / "business_chain_candidate_inventory.yaml", errors, True)
    assert any("candidate_total" in error for error in errors), errors
    assert any("candidate_type 与 classification 不一致" in error for error in errors), errors
    assert any("candidate_type_summary.business_long_chain_ready" in error for error in errors), errors


def test_prepare_handoff_accepts_reclassified_chain_candidates(temp_root: Path) -> None:
    handoff = load_module(PREPARE_HANDOFF, "prepare_handoff_reclassified_candidates_test")
    audit = temp_root / "chain_flow_candidate_audit.yaml"
    write(
        audit,
        """schema_version: 1
stage: chain_flow_candidate_audit
status: passed
next_stage_allowed: true
candidate_summary:
  included: 0
  design_long_chain_only: 0
  design_short_chain_state_transition: 1
  single_interface_mutation: 1
  single_interface_readonly: 1
  external_or_callback: 1
  excluded_missing_verification: 0
  excluded_missing_change_evidence: 0
  excluded_missing_link_key: 0
  excluded_readonly: 0
  unclassified: 0
candidates:
  - candidate_id: CAND-SHORT
    classification: design_short_chain_state_transition
    flow_id: FLOW-SHORT
    downstream_target: design_short_chain_or_state_transition_case
  - candidate_id: CAND-MUTATION
    classification: single_interface_mutation
    flow_id: FLOW-MUTATION
    downstream_target: single_interface_design_and_executable_case
  - candidate_id: CAND-READ
    classification: single_interface_readonly
    flow_id: FLOW-READ
    downstream_target: single_interface_design_case
  - candidate_id: CAND-EXTERNAL
    classification: external_or_callback
    flow_id: FLOW-EXTERNAL
    downstream_target: external_dependency_or_callback_evidence
unclassified_candidate_flows: []
blocking_issues: []
""",
    )

    assert handoff.validate_chain_flow_candidate_audit_file(audit, set()) == []


def test_coverage_point_report_requires_long_chain_first_and_separate_summary(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_outputs_report_test")
    report = temp_root / "测试覆盖点报告.md"
    write(
        report,
        """## 覆盖点摘要

- 覆盖率：100%（已映射设计级用例数 2 / 设计级用例总数 2）
- 计算口径：覆盖率 = 已映射设计级用例数 / passed 设计级用例总数 × 100%。
- 长链路覆盖率：100%（已映射长链路设计级用例数 1 / 长链路设计级用例总数 1）
- 单接口覆盖率：100%（已映射单接口设计级用例数 1 / 单接口设计级用例总数 1）
- 分项计算口径：长链路和单接口分别计算，不得混合计算。
- 长链路重点关注：TCP-001。

| ID | 测试点 | 接口链路 | 关注原因 |
|---|---|---|---|
| TCP-001 | 用户下单后完成支付并查询订单状态 | 创建订单接口—>支付订单接口—>查询订单接口 | 涉及 3 个接口，需重点检查变量传递 |

| ID | 测试点 | 业务域 | 业务场景 | 来源 | 接口链路 | 前置条件 | 操作步骤 | 预期结果 | 优先级 | 用例类型 |
|---|---|---|---|---|---|---|---|---|---|---|
| TCP-001 | 用户下单后完成支付并查询订单状态 | 订单支付 | 用户在存在可用账号且订单待支付时发起支付，并查询订单状态确认支付完成 | 需求 R-001；测试点 TP-001；设计级用例 DC-001 | 创建订单接口—>支付订单接口—>查询订单接口 | 已存在可登录用户，订单处于待支付状态 | 1. 创建待支付订单；2. 调用支付接口；3. 查询订单状态 | 订单支付成功，订单状态为支付完成 | p0 | 正向流程 |
| TCP-002 | 用户查询自己的订单详情 | 订单查询 | 用户在已有订单时查询订单详情，确认订单基础信息可见 | 需求 R-002；测试点 TP-002；设计级用例 DC-002 | 查询订单接口 | 已存在可登录用户和一笔订单 | 1. 调用查询订单接口 | 返回当前用户订单详情 | p1 | 正向流程 |
""",
    )
    errors: list[str] = []
    validator.validate_coverage_point_report_file(report, errors, require_records=True)
    assert errors == []

    bad_report = temp_root / "测试覆盖点报告_bad.md"
    write(
        bad_report,
        """## 覆盖点摘要

- 覆盖率：100%（已映射设计级用例数 2 / 设计级用例总数 2）
- 计算口径：覆盖率 = 已映射设计级用例数 / passed 设计级用例总数 × 100%。
- 长链路覆盖率：100%（已映射长链路设计级用例数 1 / 长链路设计级用例总数 1）
- 单接口覆盖率：100%（已映射单接口设计级用例数 1 / 单接口设计级用例总数 1）
- 分项计算口径：长链路和单接口分别计算，不得混合计算。
- 长链路重点关注：TCP-001。

| ID | 测试点 | 接口链路 | 关注原因 |
|---|---|---|---|
| TCP-001 | 用户下单后完成支付并查询订单状态 | 创建订单接口—>支付订单接口—>查询订单接口 | 涉及 3 个接口，需重点检查变量传递 |

| ID | 测试点 | 业务域 | 业务场景 | 来源 | 接口链路 | 前置条件 | 操作步骤 | 预期结果 | 优先级 | 用例类型 |
|---|---|---|---|---|---|---|---|---|---|---|
| TCP-002 | 用户查询自己的订单详情 | 订单查询 | 用户在已有订单时查询订单详情，确认订单基础信息可见 | 需求 R-002；测试点 TP-002；设计级用例 DC-002 | 查询订单接口 | 已存在可登录用户和一笔订单 | 1. 调用查询订单接口 | 返回当前用户订单详情 | p1 | 正向流程 |
| TCP-001 | 用户下单后完成支付并查询订单状态 | 订单支付 | 用户在存在可用账号且订单待支付时发起支付，并查询订单状态确认支付完成 | 需求 R-001；测试点 TP-001；设计级用例 DC-001 | 创建订单接口—>支付订单接口—>查询订单接口 | 已存在可登录用户，订单处于待支付状态 | 1. 创建待支付订单；2. 调用支付接口；3. 查询订单状态 | 订单支付成功，订单状态为支付完成 | p0 | 正向流程 |
""",
    )
    errors = []
    validator.validate_coverage_point_report_file(bad_report, errors, require_records=True)
    assert any("明细表必须先列长链路用例" in error for error in errors), errors


def test_business_long_chain_design_denominator_rejects_path_bucket_candidates(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_outputs_business_long_chain_test")
    handoff = load_module(PREPARE_HANDOFF, "prepare_handoff_business_long_chain_test")
    valid = temp_root / "business_long_chain_cases.yaml"
    write(valid, business_long_chain_cases())

    errors: list[str] = []
    validator.validate_business_long_chain_cases_file(valid, errors, require_passed=True)
    assert errors == []
    assert handoff.validate_business_long_chain_cases_file(valid) == []

    bad = temp_root / "business_long_chain_cases_bad.yaml"
    write(bad, business_long_chain_cases(path_bucket=True))
    errors = []
    validator.validate_business_long_chain_cases_file(bad, errors, require_passed=True)
    assert any("路径/接口前缀" in error for error in errors), errors
    assert any("路径/接口前缀" in error for error in handoff.validate_business_long_chain_cases_file(bad))


def test_path_bucket_required_flow_map_and_report_are_rejected(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_outputs_path_bucket_test")
    handoff = load_module(PREPARE_HANDOFF, "prepare_handoff_path_bucket_test")
    required_flow = temp_root / "required_chain_flows.yaml"
    write(
        required_flow,
        """schema_version: 1
stage: required_chain_flow_denominator
status: passed
next_stage_allowed: true
required_chain_flow_count: 1
unclassified_candidate_flows: []
flows:
  - flow_id: FLOW-PATH-BUCKET
    source_route: source
    evidence_routes:
      - source
    business_domain: 接口集合
    scenario_name: /api/v1/app 接口链路
    pre_action:
      interface: POST /api/v1/app/foo/create
    observable_change:
      type: 接口返回记录创建
      evidence: 接口返回中出现 id
    verification:
      interface: GET /api/v1/app/foo/detail
    link_keys:
      - id
    steps:
      - POST /api/v1/app/foo/create
      - GET /api/v1/app/foo/detail
      - GET /api/v1/app/foo/list
    evidence_refs:
      - source-api-facts.json#PATH-BUCKET
    status: required
blocking_issues: []
""",
    )
    errors: list[str] = []
    validator.validate_required_chain_flows_file(required_flow, errors, require_passed=True)
    assert any("路径/接口前缀" in error for error in errors), errors
    _, handoff_errors = handoff.validate_required_chain_flows_file(required_flow)
    assert any("路径/接口前缀" in error for error in handoff_errors), handoff_errors

    business_map_path = temp_root / "business_scenario_map.yaml"
    write(
        business_map_path,
        """schema_version: 1
stage: business_scenario_mapping
status: passed
next_stage_allowed: true
source_entry: source
scenario_items:
  - scenario_id: SCN-PATH-BUCKET
    scenario_name: api/v1 资源从业务处理到结果校验的接口链路
    business_domain: 接口集合
    executing_role: 用户
    business_description: 用户围绕 api/v1 业务资源依次调用多个接口，通过前序业务处理结果驱动后续查询或状态校验
    roles:
      - 用户
    source_refs:
      - source-api-facts.json#PATH-BUCKET
    related_interfaces:
      - POST /api/v1/order/create
      - POST /api/v1/user/login
      - GET /api/v1/user/profile
    business_chain:
      - 执行创建接口
      - 执行登录接口
      - 执行查询接口
    chain_type: e2e_flow_candidate
    flow_generation_required: true
    flow_id: FLOW-PATH-BUCKET
    ordered_step_count: 3
    ordered_steps:
      - step_order: 1
        interface: POST /api/v1/order/create
        source_ref: OrderController.java#create
      - step_order: 2
        interface: POST /api/v1/user/login
        source_ref: LoginController.java#login
      - step_order: 3
        interface: GET /api/v1/user/profile
        source_ref: ProfileController.java#detail
    related_test_point_ids:
      - TP-PATH-BUCKET
    related_coverage_rule_ids:
      - RULE-PATH-BUCKET
    confidence: high
    blockers: []
blocking_issues: []
""",
    )
    errors = []
    validator.validate_business_scenario_map_file(business_map_path, errors, require_passed=True)
    assert any("路径/接口前缀" in error for error in errors), errors
    assert any("路径/接口前缀" in error for error in handoff.validate_business_scenario_map_file(business_map_path))

    report = temp_root / "测试覆盖点报告.md"
    write(
        report,
        """## 覆盖点摘要

- 覆盖率：100%（已映射设计级用例数 1 / 设计级用例总数 1）
- 计算口径：覆盖率 = 已映射设计级用例数 / passed 设计级用例总数 × 100%。
- 长链路覆盖率：不涉及，长链路重点关注：无。
- 单接口覆盖率：100%（已映射单接口设计级用例数 1 / 单接口设计级用例总数 1）
- 分项计算口径：长链路和单接口分别计算，不得混合计算。

| ID | 测试点 | 业务域 | 业务场景 | 来源 | 接口链路 | 前置条件 | 操作步骤 | 预期结果 | 优先级 | 用例类型 |
|---|---|---|---|---|---|---|---|---|---|---|
| TCP-PATH | 创建接口正向测试 | 接口集合 | 用户调用创建接口正向测试 | 设计级用例 DC-PATH | POST /api/v1/app/foo/create | 用户已登录 | 1. 调用创建接口 | 返回成功 | p1 | 单接口正向用例 |
""",
    )
    errors = []
    validator.validate_coverage_point_report_file(report, errors, require_records=True)
    assert any("路径前缀" in error or "接口标签" in error for error in errors), errors
    assert any("路径前缀" in error or "接口标签" in error for error in handoff.validate_coverage_point_report_file(report))


def test_single_interface_cluster_must_be_split_before_handoff_and_pipeline_validation(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_outputs_single_interface_split_test")
    handoff = load_module(PREPARE_HANDOFF, "prepare_handoff_single_interface_split_test")
    business_map_path = temp_root / "business_scenario_map.yaml"
    write(business_map_path, single_interface_cluster_business_map())

    errors: list[str] = []
    validator.validate_business_scenario_map_file(business_map_path, errors, require_passed=True)

    assert any("可拆分多接口业务簇" in error for error in errors), errors
    assert any("可拆分多接口业务簇" in error for error in handoff.validate_business_scenario_map_file(business_map_path))


def test_runtime_evidence_validator_requires_confirmed_redacted_values(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_outputs_runtime_test")
    create_runtime_evidence(temp_root)
    errors: list[str] = []
    index = validator.validate_runtime_evidence(temp_root, errors, required=True, require_usable=True)
    assert errors == []
    assert "RT-LOGIN-001" in index["evidence_ids"]
    assert "VAL-USER-STATUS-ACTIVE" in index["value_ids"]

    bad_root = temp_root / "bad_runtime"
    create_runtime_evidence(bad_root, token_plaintext=True)
    errors = []
    validator.validate_runtime_evidence(bad_root, errors, required=True, require_usable=True)
    assert any("token" in error.lower() or "敏感" in error for error in errors), errors


def test_live_request_runner_writes_blocked_sidecars_for_preflight_failure(temp_root: Path) -> None:
    plan = temp_root / "runtime_request_plan.yaml"
    output_dir = temp_root / "04-runtime-evidence"
    write(
        plan,
        """schema_version: 1
request_scope:
  mutating_requests_allowed: false
env:
  env_name: dev
  timeout_seconds: 1
  base_urls:
    user: http://127.0.0.1:1
steps: []
cleanup:
  required: false
""",
    )

    completed = run([sys.executable, str(RUN_LIVE_REQUEST_EVIDENCE), "--plan", str(plan), "--output-dir", str(output_dir)])

    assert completed.returncode != 0
    for filename in ("runtime_stage_status.yaml", "runtime_evidence.yaml", "runtime_value_catalog.yaml"):
        assert (output_dir / filename).is_file(), completed.stderr
    status_text = (output_dir / "runtime_stage_status.yaml").read_text(encoding="utf-8")
    assert "status: blocked" in status_text
    assert "请求计划 steps 不能为空" in status_text

    validation = run([sys.executable, str(VALIDATE_RUNTIME_EVIDENCE), str(output_dir)])
    assert validation.returncode == 0, validation.stdout + validation.stderr


def test_live_request_runner_extracts_redacted_values_from_request_plan(
    temp_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = load_module(RUN_LIVE_REQUEST_EVIDENCE, "run_live_request_evidence_success_test")

    def fake_request_json(method: str, url: str, headers: dict, body: dict | None, timeout: float) -> tuple[int, dict]:
        if url.endswith("/login"):
            assert method == "POST"
            assert body == {"username": "demo", "password": "secret-password"}
            return 200, {"data": {"token": "token-secret-value"}}
        if url.endswith("/profile"):
            assert headers["Authorization"] == "Bearer token-secret-value"
            return 200, {"data": {"status": "ACTIVE"}}
        if url.endswith("/expected-error"):
            return 400, {"code": "INVALID_STATE"}
        return 404, {"code": "NOT_FOUND"}

    monkeypatch.setattr(runner, "request_json", fake_request_json)
    plan_text = """schema_version: 1
request_scope:
  mutating_requests_allowed: false
env:
  env_name: local
  timeout_seconds: 3
  base_urls:
    user: http://runtime.test
steps:
  - case_id: TC-RUNTIME-LOGIN
    step_id: login
    module: user
    method: POST
    path: /login
    expected_status: 200
    body:
      username: demo
      password: secret-password
    extract:
      auth_token: $.data.token
  - case_id: TC-RUNTIME-PROFILE
    step_id: profile
    module: user
    method: GET
    path: /profile
    expected_status: 200
    headers:
      Authorization: Bearer ${auth_token}
    extract:
      user_status: $.data.status
  - case_id: TC-RUNTIME-EXPECTED-ERROR
    step_id: expected-error
    module: user
    method: GET
    path: /expected-error
    expected_status: 400
    extract:
      error_code: $.code
cleanup:
  required: false
"""
    plan = temp_root / "runtime_request_plan.yaml"
    output_dir = temp_root / "04-runtime-evidence"
    write(plan, plan_text)

    completed = runner.run(plan, output_dir, None)

    assert completed == 0
    validation = run([sys.executable, str(VALIDATE_RUNTIME_EVIDENCE), str(output_dir), "--require-usable"])
    assert validation.returncode == 0, validation.stdout + validation.stderr
    evidence_text = (output_dir / "runtime_evidence.yaml").read_text(encoding="utf-8")
    request_plan_text = (output_dir / "runtime_request_plan.yaml").read_text(encoding="utf-8")
    assert "token-secret-value" not in evidence_text
    assert "secret-password" not in request_plan_text
    assert "field_value: ACTIVE" in evidence_text
    assert "field_value: INVALID_STATE" in evidence_text

    bad_plan = temp_root / "runtime_request_plan_bad_status.yaml"
    bad_output_dir = temp_root / "04-runtime-evidence-bad"
    write(bad_plan, plan_text.replace("expected_status: 200", "expected_status: 201", 1))
    bad_completed = runner.run(bad_plan, bad_output_dir, None)
    assert bad_completed == 0
    bad_status = yaml.safe_load((bad_output_dir / "runtime_stage_status.yaml").read_text(encoding="utf-8"))
    assert bad_status["status"] == "partial"
    assert [item["queue_state"] for item in bad_status["continuation_queue"]["items"]] == [
        "retryable",
        "skipped_recoverable",
        "evidenced",
    ]
    bad_status_text = (bad_output_dir / "runtime_stage_status.yaml").read_text(encoding="utf-8")
    assert "响应状态码不匹配" in bad_status_text


def test_live_request_runner_blocks_unapproved_mutating_step_before_request(
    temp_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = load_module(RUN_LIVE_REQUEST_EVIDENCE, "run_live_request_evidence_scope_guard_test")
    calls: list[str] = []

    def fake_request_json(method: str, url: str, headers: dict, body: dict | None, timeout: float) -> tuple[int, dict]:
        calls.append(url)
        return 200, {"ok": True}

    monkeypatch.setattr(runner, "request_json", fake_request_json)
    plan = temp_root / "runtime_request_plan.yaml"
    output_dir = temp_root / "04-runtime-evidence"
    write(
        plan,
        """schema_version: 1
request_scope:
  mutating_requests_allowed: false
env:
  env_name: local
  timeout_seconds: 3
  base_urls:
    reward: http://runtime.test
steps:
  - step_id: claim_reward
    module: reward
    method: POST
    path: /reward/claim
    expected_status: 200
cleanup:
  required: false
""",
    )

    completed = runner.run(plan, output_dir, None)

    assert completed != 0
    assert calls == []
    status_text = (output_dir / "runtime_stage_status.yaml").read_text(encoding="utf-8")
    assert "缺少 mutating_requests_allowed 或 request_allowed 决策" in status_text


def test_execution_fact_sources_live_request_refs_must_match_runtime_evidence(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_outputs_live_fact_test")
    create_runtime_evidence(temp_root)
    fact_text = """schema_version: 1
stage: executable_interface_case_set
status: passed
required_human_inputs:
  environment_reference:
    status: provided
    source_ref: 执行配置.md#env
  authentication_account:
    status: provided
    source_ref: 执行配置.md#auth
fact_sources:
  - fact_id: FACT-RUNTIME-001
    fact_type: assertion_rule
    source_type: live_request_evidence
    source_ref: runtime_value_catalog.yaml#VAL-USER-STATUS-ACTIVE
    source_status: confirmed
missing_required_facts: []
conflict_facts: []
blocking_issues: []
"""
    errors: list[str] = []
    index = validator.validate_runtime_evidence(temp_root, errors, required=True, require_usable=True)
    validator.validate_live_request_fact_source_refs(fact_text, index, errors)
    assert errors == []

    bad_text = fact_text.replace("VAL-USER-STATUS-ACTIVE", "VAL-MISSING")
    errors = []
    index = validator.validate_runtime_evidence(temp_root, errors, required=True, require_usable=True)
    validator.validate_live_request_fact_source_refs(bad_text, index, errors)
    assert any("不存在或不可用" in error for error in errors), errors


def test_account_specific_chain_requires_login_entry_fact() -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_outputs_account_login_fact_test")
    base_text = """schema_version: 1
stage: executable_interface_case_set
status: passed
required_human_inputs:
  environment_reference:
    status: provided
    source_ref: runtime_execution_config.yaml#env
  authentication_account:
    status: provided
    source_ref: runtime_execution_config.yaml#accounts
fact_sources:
  - fact_id: FACT-TOKEN
    fact_type: token_rule
    source_type: user_config
    source_ref: runtime_execution_config.yaml#auth.token
    source_status: confirmed
  - fact_id: FACT-DATA
    fact_type: test_data_rule
    source_type: interface_contract
    source_ref: 接口结构化契约清单.md#data-rule
    source_status: confirmed
  - fact_id: FACT-VAR
    fact_type: variable_link
    source_type: interface_contract
    source_ref: 接口结构化契约清单.md#var
    source_status: confirmed
  - fact_id: FACT-CHAIN
    fact_type: chain_flow
    source_type: design_case
    source_ref: required_chain_flows.yaml#FLOW-ACCOUNT
    source_status: confirmed
  - fact_id: FACT-ACCOUNT-CHAIN
    fact_type: account_specific_chain
    source_type: design_case
    source_ref: required_chain_flows.yaml#FLOW-ACCOUNT
    source_status: confirmed
    specific_account_required: true
    required_account_role: buyer
  - fact_id: FACT-ASSERT
    fact_type: assertion_rule
    source_type: interface_contract
    source_ref: 接口结构化契约清单.md#assert
    source_status: confirmed
  - fact_id: FACT-CLEAN
    fact_type: cleanup_strategy
    source_type: user_config
    source_ref: runtime_execution_config.yaml#cleanup
    source_status: confirmed
missing_required_facts: []
conflict_facts: []
blocking_issues: []
"""

    errors: list[str] = []
    validator.validate_execution_fact_sources_passed(base_text, errors)
    assert any("login_entry_rule" in error for error in errors), errors

    fixed_text = base_text.replace(
        "  - fact_id: FACT-ASSERT\n",
        (
            "  - fact_id: FACT-LOGIN\n"
            "    fact_type: login_entry_rule\n"
            "    source_type: user_config\n"
            "    source_ref: runtime_execution_config.yaml#auth.login\n"
            "    source_status: confirmed\n"
            "  - fact_id: FACT-ASSERT\n"
        ),
    )
    errors = []
    validator.validate_execution_fact_sources_passed(fixed_text, errors)
    assert errors == []


def test_long_chain_coverage_matrix_must_use_authoritative_denominator() -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_outputs_chain_matrix_test")
    valid_matrix = """coverage_summary:
  denominator_scope: design_case
  coverage_rate: 100
long_chain_coverage_summary:
  denominator_scope: long_chain_only
chain_scenario_total: 1
chain_scenario_covered: 1
chain_function_total: 2
chain_function_covered: 2
chain_process_total: 1
chain_process_covered: 1
required_chain_flow_count: 1
generated_design_chain_case_count: 1
missing_chain_scenario_ids: []
missing_chain_function_ids: []
missing_chain_process_ids: []
missing_required_flow_ids: []
coverage_items:
  - coverage_id: FLOW-001
    coverage_type: chain_scenario
    flow_id: FLOW-001
    status: covered
    evidence_refs:
      - required_chain_flows.yaml#FLOW-001
  - coverage_id: CHAIN-FUNC-001
    coverage_type: chain_function
    flow_id: FLOW-001
    status: covered
    evidence_refs:
      - 接口结构化契约清单.md#API-001
  - coverage_id: CHAIN-FUNC-002
    coverage_type: chain_function
    flow_id: FLOW-001
    status: covered
    evidence_refs:
      - 接口结构化契约清单.md#API-002
  - coverage_id: CHAIN-PROC-001
    coverage_type: chain_process
    flow_id: FLOW-001
    status: covered
    evidence_refs:
      - 业务场景链路清单.md#FLOW-001
upstream_downstream_mappings:
  - upstream_id: FLOW-001
    downstream_ids:
      - DC-001
    mapping_status: mapped
  - upstream_id: CHAIN-FUNC-001
    downstream_ids:
      - DC-001
    mapping_status: mapped
  - upstream_id: CHAIN-FUNC-002
    downstream_ids:
      - DC-001
    mapping_status: mapped
  - upstream_id: CHAIN-PROC-001
    downstream_ids:
      - DC-001
    mapping_status: mapped
"""
    errors: list[str] = []
    validator.validate_required_chain_independent_coverage(
        valid_matrix,
        errors,
        "阶段2/coverage_matrix.yaml",
        {"FLOW-001"},
        "generated_design_chain_case_count",
        require_item_mappings=True,
    )
    assert errors == []

    missing_mapping_matrix = valid_matrix.replace(
        "  - upstream_id: CHAIN-FUNC-001\n    downstream_ids:\n      - DC-001\n    mapping_status: mapped\n",
        "",
    )
    errors = []
    validator.validate_required_chain_independent_coverage(
        missing_mapping_matrix,
        errors,
        "阶段2/coverage_matrix.yaml",
        {"FLOW-001"},
        "generated_design_chain_case_count",
        require_item_mappings=True,
    )
    assert any("缺少长链路覆盖项映射" in error for error in errors), errors

    mixed_unit_matrix = valid_matrix.replace("denominator_scope: long_chain_only", "denominator_scope: all_cases")
    mixed_unit_matrix = mixed_unit_matrix.replace("chain_scenario_total: 1", "chain_scenario_total: 0")
    mixed_unit_matrix = mixed_unit_matrix.replace("generated_design_chain_case_count: 1", "generated_design_chain_case_count: 0")
    errors = []
    validator.validate_required_chain_independent_coverage(
        mixed_unit_matrix,
        errors,
        "阶段2/coverage_matrix.yaml",
        {"FLOW-001"},
        "generated_design_chain_case_count",
        require_item_mappings=True,
    )
    assert any("long_chain_only" in error for error in errors), errors
    assert any("必须大于 0" in error for error in errors), errors
    assert any("generated_design_chain_case_count" in error for error in errors), errors


def test_blocked_execution_input_requires_runtime_config_fillable_package(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_outputs_runtime_config_package_test")
    report = temp_root / "00_流水线执行报告.md"
    write(
        report,
        """## 阶段结论

- 目标阶段：framework
- 流水线状态：BLOCKED_NEED_EXECUTION_INPUT
- 是否允许进入下一阶段：否
- 判断依据：缺少执行配置、环境信息、鉴权账号，需要填写 runtime_execution_config。
""",
    )

    errors = validator.validate_output_root(temp_root)
    assert any("执行配置待填写模板" in error for error in errors), errors
    assert any("前置执行配置待填写说明" in error for error in errors), errors
    assert any("执行配置缺失字段清单" in error for error in errors), errors

    write(temp_root / "00-inputs" / "runtime_execution_config.template.yaml", "schema_version: 1\n")
    write(
        temp_root / "00-inputs" / "前置执行配置待填写.md",
        """## 环境信息
## 模块 base URL 与网关前缀
## 账号与角色及业务状态
## 鉴权与 token 提取/注入
## 加解密策略
## 执行授权范围
## DB before/after 与清理授权
## 外部依赖或沙箱/Mock
## 必填缺失字段清单
## 填写后继续条件
""",
    )
    write(
        temp_root / "00-inputs" / "runtime_execution_config.missing_fields.yaml",
        """schema_version: 1
missing_fields:
  - field: environment.env_name
    reason: 缺少环境名称
""",
    )

    errors = validator.validate_output_root(temp_root)
    assert errors == []


def test_runtime_evidence_plan_summary_is_complete_and_consistent() -> None:
    planner = load_module(BUILD_RUNTIME_PLAN, "build_runtime_evidence_plan_summary_test")
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_outputs_runtime_plan_summary_test")
    outputs = planner.build_outputs(
        [
            {"case_id": "DC-READ", "name": "查询用户资料", "method": "GET", "path": "/profile"},
            {"case_id": "DC-AUTH", "name": "短信登录", "method": "POST", "path": "/login"},
            {"case_id": "DC-DELETE", "name": "注销账号", "method": "DELETE", "path": "/account"},
        ],
        "test",
    )

    audit = outputs["runtime_risk_audit.yaml"]
    assert set(audit["risk_summary"]) == set(planner.RUNTIME_RISK_LEVELS)
    assert set(audit["request_decision_summary"]) == set(planner.RUNTIME_REQUEST_DECISIONS)
    assert audit["risk_summary"]["safe_readonly"] == 1
    assert audit["risk_summary"]["auth_setup"] == 1
    assert audit["risk_summary"]["destructive_state"] == 1
    assert audit["risk_summary"]["mutation_requires_cleanup"] == 0
    assert audit["request_decision_summary"]["request_allowed"] == 1
    assert audit["request_decision_summary"]["request_allowed_with_user_config"] == 1
    assert audit["request_decision_summary"]["blocked_until_isolated_account_and_cleanup"] == 1
    assert "execution_authorization" in audit
    assert "db_authorization" in audit

    errors: list[str] = []
    allowed_case_ids = validator.validate_runtime_risk_audit_file(
        yaml.safe_dump(audit, allow_unicode=True, sort_keys=False),
        errors,
    )
    assert errors == []
    assert allowed_case_ids == {"DC-READ", "DC-AUTH"}


def test_source_entry_missing_data_model_requires_db_mcp_attempt(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_outputs_source_db_mcp_attempt_test")
    source_entry = temp_root / "02-source-api-facts" / "docs" / "source-facts"
    doc_entry = temp_root / "01-pre-doc-analysis"
    source_entry.mkdir(parents=True)
    report_text = "目标阶段 framework，流水线状态 BLOCKED_NEED_EXECUTION_INPUT，缺少数据模型。"

    errors: list[str] = []
    validator.validate_source_data_model_mcp_attempt(
        temp_root,
        report_text,
        "BLOCKED_NEED_EXECUTION_INPUT",
        "framework",
        source_entry,
        doc_entry,
        errors,
    )
    assert any("数据库 MCP" in error for error in errors), errors

    errors = []
    validator.validate_source_data_model_mcp_attempt(
        temp_root,
        report_text + " 已尝试数据库 MCP，但连接未授权且不可读。",
        "BLOCKED_NEED_EXECUTION_INPUT",
        "framework",
        source_entry,
        doc_entry,
        errors,
    )
    assert errors == []


def test_executable_component_validator_requires_independent_long_chain_coverage() -> None:
    validator = load_module(VALIDATE_EXECUTABLE, "validate_executable_long_chain_matrix_test")
    matrix_without_chain = """schema_version: 1
stage: executable_interface_case_set
coverage_summary:
  denominator_scope: executable_case
  coverage_rate: 100
design_case_total: 1
design_case_mapped: 1
executable_case_total: 1
executable_case_traced: 1
coverage_rule_total: 1
coverage_rule_mapped: 1
missing_design_case_ids: []
missing_executable_trace_ids: []
missing_coverage_rule_ids: []
coverage_items:
  - coverage_id: EC-001
    coverage_type: executable_case
    status: covered
    evidence_refs:
      - 执行级接口用例集.md#EC-001
missing_items: []
upstream_downstream_mappings:
  - upstream_id: EC-001
    downstream_ids:
      - TC-001
    mapping_status: mapped
"""
    errors: list[str] = []
    validator.validate_coverage_matrix_sidecar(matrix_without_chain, "PASSED", errors, {"FLOW-001"})
    assert any("long_chain_only" in error for error in errors), errors
    assert any("chain_scenario_total" in error for error in errors), errors
    assert any("generated_executable_chain_case_count" in error for error in errors), errors


def test_generation_status_requires_independent_e2e_flow_mapping() -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_outputs_generation_status_test")
    valid_status = """stage: api_test_framework_generator
status: validated
next_stage_allowed: true
executable_case_count: 1
e2e_flow_case_count: 1
collected_test_count: 2
coverage_traceability:
  status: passed
  executable_case_count: 1
  missing_executable_mappings: []
  missing_pytest_mappings: []
pytest_collection_mapping:
  status: passed
  collected_test_count: 2
  mappings:
    - executable_case_id: EXE-TC-001
      design_case_id: DC-001
      coverage_object_ids: [OBJ-001]
      coverage_rule_ids: [RULE-001]
      test_point_id: TP-001
      pytest_nodeid: testcases/test_order.py::test_order_detail
    - flow_id: FLOW-001
      source_executable_case_ids: [EXE-TC-001, EXE-TC-002]
      pytest_nodeid: testcases/test_flows.py::test_flow_001
chain_script_coverage:
  status: passed
  coverage_denominator: long_chain_only
  required_flow_count: 1
  generated_flow_count: 1
  required_chain_flow_count: 1
  generated_pytest_flow_count: 1
  chain_scenario_total: 1
  chain_scenario_covered: 1
  chain_function_total: 2
  chain_function_covered: 2
  chain_process_total: 1
  chain_process_covered: 1
  missing_chain_scenario_ids: []
  missing_chain_function_ids: []
  missing_chain_process_ids: []
  missing_required_flow_ids: []
  single_interface_only_flow_ids: []
  required_flow_ids:
    - FLOW-001
  coverage_items:
    - coverage_id: FLOW-001
      coverage_type: chain_scenario
      flow_id: FLOW-001
      status: covered
      evidence_refs:
        - required_chain_flows.yaml#FLOW-001
    - coverage_id: CHAIN-FUNC-001
      coverage_type: chain_function
      flow_id: FLOW-001
      status: covered
      evidence_refs:
        - data/flow_cases.yaml#FLOW-001
    - coverage_id: CHAIN-FUNC-002
      coverage_type: chain_function
      flow_id: FLOW-001
      status: covered
      evidence_refs:
        - data/flow_cases.yaml#FLOW-001
    - coverage_id: CHAIN-PROC-001
      coverage_type: chain_process
      flow_id: FLOW-001
      status: covered
      evidence_refs:
        - testcases/test_flows.py::test_flow_001
"""
    errors: list[str] = []
    validator.validate_generation_status(valid_status, errors, {"FLOW-001"}, False)
    assert errors == []

    single_interface_only_status = valid_status.replace("e2e_flow_case_count: 1", "e2e_flow_case_count: 0")
    single_interface_only_status = single_interface_only_status.replace("collected_test_count: 2", "collected_test_count: 1")
    single_interface_only_status = single_interface_only_status.replace("generated_flow_count: 1", "generated_flow_count: 0")
    single_interface_only_status = single_interface_only_status.replace("generated_pytest_flow_count: 1", "generated_pytest_flow_count: 0")
    single_interface_only_status = single_interface_only_status.replace(
        "    - flow_id: FLOW-001\n      source_executable_case_ids: [EXE-TC-001, EXE-TC-002]\n      pytest_nodeid: testcases/test_flows.py::test_flow_001\n",
        "",
    )
    errors = []
    validator.validate_generation_status(single_interface_only_status, errors, {"FLOW-001"}, False)
    assert any("E2E flow 数不足" in error for error in errors), errors
    assert any("generated_pytest_flow_count" in error for error in errors), errors
    assert any("E2E flow 映射缺少" in error for error in errors), errors


def test_pytest_flow_mapping_must_call_run_flow_with_mapped_flow_id(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_outputs_flow_ast_test")
    framework = temp_root / "api-test-framework"
    for dirname in ("core", "testcases"):
        (framework / dirname).mkdir(parents=True, exist_ok=True)
    write(framework / "core" / "flow_runner.py", "def run_flow(flow_id, authenticated_client, env_config, runtime_context):\n    return None\n")
    write(framework / "conftest.py", "import pytest\n\n@pytest.fixture\ndef authenticated_client():\n    return object()\n\n@pytest.fixture\ndef env_config():\n    return {}\n\n@pytest.fixture\ndef runtime_context():\n    return {}\n")
    generation_status = """pytest_collection_mapping:
  status: passed
  mappings:
    - flow_id: FLOW-001
      source_executable_case_ids: [EXE-TC-001]
      pytest_nodeid: testcases/test_flows.py::test_flow_001
"""

    write(framework / "testcases" / "test_flows.py", "def test_flow_001(authenticated_client, env_config, runtime_context):\n    pass\n")
    errors: list[str] = []
    validator.validate_pytest_nodeid_targets(framework, generation_status, errors, {"FLOW-001"})
    assert any("run_flow" in error for error in errors), errors

    write(
        framework / "testcases" / "test_flows.py",
        (
            "from core.flow_runner import run_flow\n\n"
            "def test_flow_001(authenticated_client, env_config, runtime_context):\n"
            "    run_flow(\"FLOW-001\", authenticated_client, env_config, runtime_context)\n"
        ),
    )
    errors = []
    validator.validate_pytest_nodeid_targets(framework, generation_status, errors, {"FLOW-001"})
    assert errors == []


def test_pytest_collection_uses_current_python_module_when_env_missing(
    temp_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_outputs_pytest_command_default_test")
    framework = temp_root / "api-test-framework"
    framework.mkdir(parents=True)
    monkeypatch.delenv("API_AUTOMATION_PYTEST", raising=False)
    calls: list[dict[str, object]] = []

    class Result:
        returncode = 0
        stdout = "testcases/test_demo.py::test_demo\n"
        stderr = ""

    def fake_run(cmd, cwd, text, capture_output, timeout):
        calls.append({
            "cmd": cmd,
            "cwd": cwd,
            "text": text,
            "capture_output": capture_output,
            "timeout": timeout,
        })
        return Result()

    monkeypatch.setattr(validator.subprocess, "run", fake_run)
    errors: list[str] = []
    validator.validate_pytest_collection(framework, ["testcases/test_demo.py::test_demo"], errors)

    assert errors == []
    assert calls
    assert calls[0]["cmd"] == [validator.sys.executable, "-m", "pytest", "--collect-only", "-q"]
    assert calls[0]["cwd"] == framework


def test_pytest_collection_rejects_missing_explicit_env_path(
    temp_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_outputs_pytest_command_env_test")
    framework = temp_root / "api-test-framework"
    framework.mkdir(parents=True)
    missing_pytest = temp_root / "missing-pytest"
    monkeypatch.setenv("API_AUTOMATION_PYTEST", str(missing_pytest))

    errors: list[str] = []
    validator.validate_pytest_collection(framework, ["testcases/test_demo.py::test_demo"], errors)

    assert any("API_AUTOMATION_PYTEST" in error and "不存在" in error for error in errors), errors


def test_framework_requires_data_driven_parametrize_layout(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_outputs_data_driven_test")
    framework = temp_root / "api-test-framework"
    for dirname in ("data/cases", "testcases"):
        (framework / dirname).mkdir(parents=True, exist_ok=True)
    generation_status = """executable_case_count: 1
pytest_collection_mapping:
  status: passed
  mappings:
    - executable_case_id: EXE-TC-001
      design_case_id: DC-001
      coverage_object_ids: [OBJ-001]
      coverage_rule_ids: [RULE-001]
      test_point_id: TP-001
      pytest_nodeid: testcases/test_api_cases.py::test_api_case[EXE-TC-001]
"""

    errors: list[str] = []
    validator.validate_data_driven_framework_files(framework, generation_status, errors)
    assert any("interfaces.yaml" in error for error in errors), errors
    assert any("flow_cases.yaml" in error for error in errors), errors
    assert any("用例 YAML" in error for error in errors), errors

    write(
        framework / "data" / "interfaces.yaml",
        """schema_version: 1
interfaces:
  - interface_id: IF-001
    method: GET
    path: /orders/{id}
""",
    )
    write(framework / "data" / "flow_cases.yaml", "schema_version: 1\nflows: []\n")
    write(
        framework / "data" / "cases" / "order_cases.yaml",
        """schema_version: 1
cases:
  - case_id: EXE-TC-001
    interface_id: IF-001
    title: 用户查询订单详情
    request:
      query: {}
    expected:
      status_code: 200
""",
    )
    write(framework / "testcases" / "test_api_cases.py", "def test_api_case(case_data):\n    pass\n")
    errors = []
    validator.validate_data_driven_framework_files(framework, generation_status, errors)
    assert any("pytest.mark.parametrize" in error for error in errors), errors

    write(
        framework / "testcases" / "test_api_cases.py",
        (
            "import pytest\n\n"
            "@pytest.mark.parametrize(\"case_data\", [{\"case_id\": \"EXE-TC-001\"}])\n"
            "def test_api_case(case_data):\n"
            "    assert case_data[\"case_id\"] == \"EXE-TC-001\"\n"
        ),
    )
    errors = []
    validator.validate_data_driven_framework_files(framework, generation_status, errors)
    assert errors == []


def test_framework_accepts_python_data_driven_layout(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_outputs_python_data_driven_test")
    framework = temp_root / "api-test-framework"
    for dirname in ("data/cases", "testcases"):
        (framework / dirname).mkdir(parents=True, exist_ok=True)
    generation_status = """executable_case_count: 1
pytest_collection_mapping:
  status: passed
  mappings:
    - executable_case_id: EXE-TC-001
      design_case_id: DC-001
      coverage_object_ids: [OBJ-001]
      coverage_rule_ids: [RULE-001]
      test_point_id: TP-001
      pytest_nodeid: testcases/test_api_cases.py::test_api_case[EXE-TC-001]
"""
    write(
        framework / "data" / "interfaces.py",
        """SCHEMA_VERSION = 1
INTERFACES = [
    {"interface_id": "IF-001", "method": "GET", "path": "/orders/{id}"}
]
""",
    )
    write(framework / "data" / "flow_cases.py", "SCHEMA_VERSION = 1\nFLOWS = []\n")
    write(
        framework / "data" / "cases" / "order_cases.py",
        """SCHEMA_VERSION = 1
CASES = [
    {
        "case_id": "EXE-TC-001",
        "interface_id": "IF-001",
        "title": "用户查询订单详情",
        "request": {"query": {}},
        "expected": {"status_code": 200},
    }
]
""",
    )
    write(
        framework / "testcases" / "test_api_cases.py",
        (
            "import pytest\n\n"
            "@pytest.mark.parametrize(\"case_data\", [{\"case_id\": \"EXE-TC-001\"}])\n"
            "def test_api_case(case_data):\n"
            "    assert case_data[\"case_id\"] == \"EXE-TC-001\"\n"
        ),
    )

    errors: list[str] = []
    validator.validate_data_driven_framework_files(framework, generation_status, errors)
    assert errors == []

    write(
        framework / "data" / "cases" / "bad_cases.py",
        "import os\n\nCASES = []\n",
    )
    errors = []
    validator.validate_data_driven_framework_files(framework, generation_status, errors)
    assert any("只能包含常量赋值" in error for error in errors), errors


def test_root_validator_integrates_case_denominator_conservation(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_outputs_case_denominator_test")
    root = temp_root / "pipeline"
    framework = root / "api-test-framework"
    write(
        root / "05-executable-interface-case-set/执行级接口用例集.md",
        "# 执行级接口用例集\n\n- 用例ID: CASE-001\n",
    )
    write(root / "required_chain_flows.yaml", "flows:\n  - flow_id: FLOW-001\n    status: required\n")
    write(
        framework / "data/cases/cases.yaml",
        "cases:\n  - case_id: CASE-001\n    interface_id: API-001\n",
    )
    write(framework / "data/flow_cases.yaml", "flows:\n  - flow_id: FLOW-001\n")
    write(
        framework / "configs/generation_status.yaml",
        """pytest_collection_mapping:
  mappings:
    - executable_case_id: CASE-001
      pytest_nodeid: testcases/test_cases.py::test_case[CASE-001]
    - flow_id: FLOW-001
      pytest_nodeid: testcases/test_flows.py::test_flow_001
    - flow_id: FLOW-MISSING
      pytest_nodeid: testcases/test_flows.py::test_flow_missing
""",
    )

    errors: list[str] = []
    validator.validate_framework_case_denominator_conservation(root, framework, errors)

    assert any("FLOW-MISSING" in error and "用例分母守恒" in error for error in errors), errors


def test_case_denominator_gate_is_bundled_and_referenced() -> None:
    component = ROOT / "components" / "api-test-framework-generator"
    assert (component / "scripts/validate_case_denominator_conservation.py").is_file()
    assert (component / "references/case-denominator-conservation.md").is_file()
    text = (component / "SKILL.md").read_text(encoding="utf-8")
    assert "references/case-denominator-conservation.md" in text
    assert "validate_case_denominator_conservation.py" in text
    assert "case_denominator_conservation.status" in text


def test_case_denominator_gate_stays_out_of_unrelated_runtime_gates() -> None:
    text = VALIDATE_CASE_DENOMINATOR.read_text(encoding="utf-8")

    for forbidden in ("requests.", "sqlalchemy", "Authorization", "cleanup_required", "assertion_strength"):
        assert forbidden not in text


def test_required_flow_framework_files_accept_python_flow_cases(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_outputs_required_flow_python_test")
    framework = temp_root / "api-test-framework"
    for dirname in ("data", "core", "testcases"):
        (framework / dirname).mkdir(parents=True, exist_ok=True)
    write(
        framework / "data" / "flow_cases.py",
        """SCHEMA_VERSION = 1
FLOWS = [
    {
        "flow_id": "FLOW-001",
        "title": "查询订单链路",
        "steps": [
            {"case_id": "EXE-TC-001", "method": "GET", "path": "/orders/{id}"}
        ],
    }
]
""",
    )
    write(framework / "core" / "flow_runner.py", "def run_flow(flow_id, authenticated_client, env_config, runtime_context):\n    return None\n")
    write(
        framework / "testcases" / "test_flows.py",
        (
            "from core.flow_runner import run_flow\n\n"
            "def test_flow_001(authenticated_client, env_config, runtime_context):\n"
            "    run_flow(\"FLOW-001\", authenticated_client, env_config, runtime_context)\n"
        ),
    )

    errors: list[str] = []
    validator.validate_required_flow_framework_files(framework, {"FLOW-001"}, False, errors)
    assert errors == []


def test_template_case_loader_reads_python_data_files(temp_root: Path) -> None:
    framework = temp_root / "api-test-framework"
    shutil.copytree(FRAMEWORK_TEMPLATE, framework)
    write(
        framework / "data" / "interfaces.py",
        """SCHEMA_VERSION = 1
INTERFACES = [
    {"interface_id": "IF-001", "method": "POST", "path": "/orders"}
]
""",
    )
    write(
        framework / "data" / "cases" / "order_cases.py",
        """SCHEMA_VERSION = 1
CASES = [
    {
        "case_id": "EXE-TC-001",
        "interface_id": "IF-001",
        "title": "创建订单",
        "request": {"body": {"amount": 100}},
        "expected": {"status_code": 200},
    }
]
""",
    )
    script = (
        "import sys\n"
        f"sys.path.insert(0, {str(framework)!r})\n"
        "from core.case_loader import load_case_parameters\n"
        "cases = load_case_parameters()\n"
        "assert len(cases) == 1\n"
        "assert cases[0]['case_id'] == 'EXE-TC-001'\n"
        "assert cases[0]['method'] == 'POST'\n"
        "assert cases[0]['path'] == '/orders'\n"
    )
    result = run([sys.executable, "-c", script])
    assert result.returncode == 0, result.stderr


def test_template_case_loader_marks_materialized_sql_cases(temp_root: Path) -> None:
    framework = temp_root / "api-test-framework"
    shutil.copytree(FRAMEWORK_TEMPLATE, framework)
    (framework / "data" / "interfaces.py").unlink(missing_ok=True)
    write(
        framework / "data" / "interfaces.yaml",
        """interfaces:
  - interface_id: IF-001
    method: POST
    path: /orders
""",
    )
    write(
        framework / "data" / "cases" / "materialized_sql_cases.yaml",
        """cases:
  - case_id: TC-SETUP-001
    interface_id: IF-001
    title: SQL前置清理后创建订单
    setup_cleanup_materialization: sql_setup_runtime_context_cleanup_final_verify
    request:
      body:
        amount: 100
    expected:
      status_code: 200
  - case_id: TC-DB-ASSERT-001
    interface_id: IF-001
    title: DB断言验证订单状态
    db_assertion_materialization: case_sql_runtime_extract_stage
    request:
      body:
        amount: 200
    expected:
      status_code: 200
  - case_id: TC-NONLIVE-001
    interface_id: IF-001
    title: 需要人工确认的写接口
    live_pytest_release_ready: false
    non_live_reason: 外部依赖未隔离
    request:
      body:
        amount: 300
    expected:
      status_code: 200
""",
    )
    script = (
        "import sys\n"
        f"sys.path.insert(0, {str(framework)!r})\n"
        "from core.case_loader import load_case_parameters, load_case_pytest_parameters\n"
        "cases = {item['case_id']: item for item in load_case_parameters()}\n"
        "assert cases['TC-SETUP-001']['sql_fixture_required'] is True\n"
        "assert cases['TC-DB-ASSERT-001']['sql_fixture_required'] is True\n"
        "assert cases['TC-NONLIVE-001']['sql_fixture_required'] is False\n"
        "params = {item.id: item for item in load_case_pytest_parameters()}\n"
        "assert 'case_id' in {mark.name for mark in params['TC-SETUP-001'].marks}\n"
        "assert 'case_id' in {mark.name for mark in params['TC-DB-ASSERT-001'].marks}\n"
        "assert 'skip' in {mark.name for mark in params['TC-NONLIVE-001'].marks}\n"
    )
    result = run([sys.executable, "-B", "-c", script])
    assert result.returncode == 0, result.stderr


def test_template_optional_async_and_sql_lifecycle_rules_are_wired() -> None:
    optional_async_text = (
        FRAMEWORK_TEMPLATE / "testcases" / "test_optional_async_cases.py"
    ).read_text(encoding="utf-8")
    conftest_text = (FRAMEWORK_TEMPLATE / "conftest.py").read_text(encoding="utf-8")
    sql_executor_text = (FRAMEWORK_TEMPLATE / "core" / "sql_executor.py").read_text(encoding="utf-8")
    dependency_text = (FRAMEWORK_TEMPLATE / "core" / "dependency_check.py").read_text(encoding="utf-8")
    runtime_context_text = (FRAMEWORK_TEMPLATE / "core" / "runtime_context.py").read_text(encoding="utf-8")

    assert "db_assertion_materialization" in optional_async_text
    assert "setup_cleanup_materialization" in optional_async_text
    assert "pytest.mark.case_id" in optional_async_text
    assert "extract_runtime" in conftest_text
    assert "final_verify" in conftest_text
    assert "SQLAlchemyOperationalError" in conftest_text
    assert "database_aliases" in sql_executor_text
    assert "check_database_runtime_required" in dependency_text
    assert "publish_runtime_variables" in runtime_context_text


def test_template_runtime_extract_failure_is_not_retried_in_teardown(temp_root: Path) -> None:
    framework = temp_root / "api-test-framework"
    shutil.copytree(FRAMEWORK_TEMPLATE, framework)
    script = (
        "import sys\n"
        f"sys.path.insert(0, {str(framework)!r})\n"
        "from core.sql_executor import SqlExecutor\n"
        "executor = SqlExecutor({}, {})\n"
        "calls = []\n"
        "def fail_once(*args):\n"
        "    calls.append(args)\n"
        "    raise AssertionError('runtime extract failed')\n"
        "executor._execute_commands = fail_once\n"
        "try:\n"
        "    executor.extract_runtime('TC-ASYNC-001', {})\n"
        "except AssertionError:\n"
        "    pass\n"
        "executor.extract_runtime('TC-ASYNC-001', {})\n"
        "assert len(calls) == 1\n"
    )
    result = run([sys.executable, "-B", "-c", script])
    assert result.returncode == 0, result.stderr


def test_template_sql_executor_compares_temporal_db_values_with_text_expectations(temp_root: Path) -> None:
    framework = temp_root / "api-test-framework"
    shutil.copytree(FRAMEWORK_TEMPLATE, framework)
    script = (
        "import sys\n"
        "from datetime import date, datetime, time\n"
        f"sys.path.insert(0, {str(framework)!r})\n"
        "from core.sql_executor import SqlExecutor\n"
        "executor = SqlExecutor({}, {})\n"
        "executor._assert_expected_fields('TC-DT', [{'updated_at': datetime(2026, 7, 8, 9, 10, 11)}], {'expected_updated_at': '2026-07-08 09:10:11'})\n"
        "executor._assert_expected_fields('TC-DT-ISO', [{'latest_time': datetime(2026, 7, 8, 9, 10, 11)}], {'expected_latest_time': '2026-07-08T09:10:11'})\n"
        "executor._assert_expected_fields('TC-DATE', [{'biz_date': date(2026, 7, 8)}], {'expected_biz_date': '2026-07-08'})\n"
        "executor._assert_expected_fields('TC-TIME', [{'biz_time': time(9, 10, 11)}], {'expected_biz_time': '09:10:11'})\n"
        "assert executor._values_equal(datetime(2026, 7, 8, 9, 10, 11), '2026-07-08 09:10:11')\n"
        "assert not executor._values_equal('2026-07-08T09:10:11', '2026-07-08 09:10:11')\n"
        "failed = False\n"
        "try:\n"
        "    executor._assert_expected_fields('TC-DT-MISMATCH', [{'updated_at': datetime(2026, 7, 8, 9, 10, 11)}], {'expected_updated_at': '2026-07-08 09:10:12'})\n"
        "except AssertionError:\n"
        "    failed = True\n"
        "assert failed\n"
    )
    result = run([sys.executable, "-B", "-c", script])
    assert result.returncode == 0, result.stderr


def test_sql_fixture_and_existing_state_rules_are_documented_consistently() -> None:
    paths = [
        ROOT / "SKILL.md",
        ROOT / "components" / "api-test-framework-generator" / "SKILL.md",
        ROOT / "components" / "api-test-framework-generator" / "references" / "runtime-usability-gate.md",
        ROOT / "components" / "api-test-framework-generator" / "references" / "setup-cleanup-defect-gate.md",
        ROOT / "components" / "api-test-framework-generator" / "references" / "conversion-contract.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    assert "setup_cleanup_materialization" in combined
    assert "db_assertion_materialization" in combined
    assert "case_sql_commands.yaml" in combined
    assert "existing_state_closure" in combined
    assert "FAILED_SQL_FIXTURE_MATERIALIZATION" in combined
    assert "BLOCKED_EXISTING_STATE_CLOSURE" in combined
    assert "long-chain-only checks" in combined or "long-chain extraction checks" in combined


def test_required_flow_framework_files_are_mandatory(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_outputs_required_flow_files_test")
    framework = temp_root / "api-test-framework"
    for dirname in ("data", "core", "testcases"):
        (framework / dirname).mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    validator.validate_required_flow_framework_files(framework, {"FLOW-001"}, False, errors)
    assert any("data/flow_cases.yaml" in error for error in errors), errors
    assert any("core/flow_runner.py" in error for error in errors), errors
    assert any("testcases/test_flows.py" in error for error in errors), errors

    write(framework / "data" / "flow_cases.yaml", "flows:\n  - flow_id: FLOW-001\n")
    write(framework / "core" / "flow_runner.py", "def run_flow(flow_id, authenticated_client, env_config, runtime_context):\n    return None\n")
    write(framework / "testcases" / "test_flows.py", "def test_flow_001():\n    pass\n")
    errors = []
    validator.validate_required_flow_framework_files(framework, {"FLOW-001"}, False, errors)
    assert any("run_flow" in error for error in errors), errors

    write(
        framework / "testcases" / "test_flows.py",
        (
            "from core.flow_runner import run_flow\n\n"
            "def test_flow_001(authenticated_client, env_config, runtime_context):\n"
            "    run_flow(\"FLOW-001\", authenticated_client, env_config, runtime_context)\n"
        ),
    )
    errors = []
    validator.validate_required_flow_framework_files(framework, {"FLOW-001"}, False, errors)
    assert errors == []


def test_account_specific_flow_cases_must_start_with_login(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_outputs_account_flow_login_test")
    framework = temp_root / "api-test-framework"
    for dirname in ("data", "core", "testcases"):
        (framework / dirname).mkdir(parents=True, exist_ok=True)
    write(framework / "core" / "flow_runner.py", "def run_flow(flow_id, authenticated_client, env_config, runtime_context):\n    return None\n")
    write(
        framework / "testcases" / "test_flows.py",
        (
            "from core.flow_runner import run_flow\n\n"
            "def test_flow_account(authenticated_client, env_config, runtime_context):\n"
            "    run_flow(\"FLOW-ACCOUNT\", authenticated_client, env_config, runtime_context)\n"
        ),
    )

    bad_flow = """flows:
  - flow_id: FLOW-ACCOUNT
    specific_account_required: true
    required_account_role: buyer
    steps:
      - step_id: create_order
        step_type: business
        path: /orders
        extract:
          order_id: $.data.id
      - step_id: query_order
        step_type: business
        path: /orders/${order_id}
"""
    write(framework / "data" / "flow_cases.yaml", bad_flow)
    errors: list[str] = []
    validator.validate_required_flow_framework_files(framework, {"FLOW-ACCOUNT"}, False, errors)
    assert any("首步不是登录/授权接口" in error for error in errors), errors

    good_flow = """flows:
  - flow_id: FLOW-ACCOUNT
    specific_account_required: true
    required_account_role: buyer
    steps:
      - step_id: login
        step_type: login
        path: /auth/login
        extract:
          auth_token: $.data.token
          userId: $.data.userId
      - step_id: create_order
        step_type: business
        path: /orders
        headers:
          Authorization: Bearer ${auth_token}
        request_overrides:
          body:
            userId: ${userId}
"""
    write(framework / "data" / "flow_cases.yaml", good_flow)
    errors = []
    validator.validate_required_flow_framework_files(framework, {"FLOW-ACCOUNT"}, False, errors)
    assert errors == []


def test_pipeline_and_handoff_validators_reject_false_passed(temp_root: Path) -> None:
    blocked_root = temp_root / "blocked_pipeline"
    write(
        blocked_root / "00_流水线执行报告.md",
        "## 流水线执行报告\n- 目标阶段：framework\n- 流水线状态：BLOCKED_MISSING_ENTRY_INPUT\n",
    )
    assert run([sys.executable, str(VALIDATE_PIPELINE), str(blocked_root)]).returncode == 0

    false_passed_root = temp_root / "false_passed"
    write(
        false_passed_root / "00_流水线执行报告.md",
        "## 流水线执行报告\n- 目标阶段：framework\n- 流水线状态：PASSED\n",
    )
    false_passed = run([sys.executable, str(VALIDATE_PIPELINE), str(false_passed_root)])
    assert false_passed.returncode != 0
    assert "必须存在" in false_passed.stdout

    handoff = run(
        [
            sys.executable,
            str(PREPARE_HANDOFF),
            "--source-dir",
            str(temp_root / "missing-stage2"),
            "--output-dir",
            str(temp_root / "handoff"),
        ]
    )
    assert handoff.returncode != 0


def test_executable_validator_keeps_blocked_branch_case_free(temp_root: Path) -> None:
    output_dir = temp_root / "exe_blocked"
    create_executable_non_passed(output_dir)

    blocked = run([sys.executable, str(VALIDATE_EXECUTABLE), str(output_dir)])
    assert blocked.returncode == 0, blocked.stdout + blocked.stderr

    rules_text = (output_dir / "前置数据构造规则.md").read_text(encoding="utf-8")
    rules_text = rules_text.replace("BLOCKED_NEED_EXECUTION_INPUT", "PASSED")
    rules_text = rules_text.replace("是否允许进入 pytest+allure 代码生成：否", "是否允许进入 pytest+allure 代码生成：是")
    rules_text = rules_text.replace("是否准出：否", "是否准出：是")
    write(output_dir / "前置数据构造规则.md", rules_text)
    write(
        output_dir / "stage_status.yaml",
        """schema_version: 1
stage: executable_interface_case_set
status: passed
next_stage_allowed: true
input_paths: []
output_paths: []
gate_checks: []
blocking_issues: []
""",
    )

    false_passed = run([sys.executable, str(VALIDATE_EXECUTABLE), str(output_dir)])
    assert false_passed.returncode != 0


def test_executable_script_gate_requires_business_readable_input_quality() -> None:
    validator = load_module(VALIDATE_EXECUTABLE, "validate_executable_business_readable_gate_test")
    gate_lines = [
        f"- {item}：通过"
        for item in validator.SCRIPT_GATE_ITEMS
    ]
    gate_lines.extend([
        "- 允许外部补充项：环境配置、pytest 工程规范、allure 标注规范",
        "- 是否可依据产物生成完整测试脚本：是",
    ])
    good_rules = "\n".join(gate_lines)
    errors: list[str] = []
    validator.validate_passed_script_gate(good_rules, errors)
    assert errors == []

    bad_rules = good_rules.replace("- 正向展示字段真实合法性：通过\n", "")
    errors = []
    validator.validate_passed_script_gate(bad_rules, errors)
    assert any("正向展示字段真实合法性" in error for error in errors)


def test_executable_validator_rejects_missing_live_request_evidence(temp_root: Path) -> None:
    output_dir = temp_root / "pipeline" / "05-executable-interface-case-set"
    create_executable_non_passed(output_dir)
    fact_text = (output_dir / "execution_fact_sources.yaml").read_text(encoding="utf-8")
    fact_text = fact_text.replace(
        "  - fact_type: assertion_rule\n    status: missing",
        (
            "  - fact_id: FACT-RUNTIME-001\n"
            "    fact_type: assertion_rule\n"
            "    source_type: live_request_evidence\n"
            "    source_ref: runtime_value_catalog.yaml#VAL-USER-STATUS-ACTIVE\n"
            "    source_status: confirmed"
        ),
    )
    write(output_dir / "execution_fact_sources.yaml", fact_text)

    missing_runtime = run([sys.executable, str(VALIDATE_EXECUTABLE), str(output_dir)])
    assert missing_runtime.returncode != 0
    assert "live_request_evidence" in (missing_runtime.stdout + missing_runtime.stderr)

    create_runtime_evidence(output_dir.parent)
    with_runtime = run([sys.executable, str(VALIDATE_EXECUTABLE), str(output_dir)])
    assert with_runtime.returncode == 0, with_runtime.stdout + with_runtime.stderr


def test_framework_quality_gate_requires_business_readable_input_quality(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_business_readable_gate_test")
    framework = temp_root / "api-test-framework"
    framework.mkdir()
    generation_status = """execution_fact_closure:
  status: passed
  unresolved_main_flow_business_fields: 0
  stateful_cases_without_setup_cleanup: 0
  pre_login_steps_with_token_injection: 0
  unresolved_auth_placeholders: 0
  cross_role_identity_mismatches: 0
assertion_strength_gate:
  status: passed
business_result_observability:
  status: passed
setup_cleanup_materialization:
  status: passed
final_case_archive:
  status: passed
"""
    errors: list[str] = []
    validator.validate_framework_quality_gates(framework, generation_status, errors)
    assert any("business_readable_input_quality" in error for error in errors)
    assert not any("failure_path_cleanup_resilience" in error for error in errors)


def test_sql_setup_runtime_refs_follow_command_order(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_sql_setup_runtime_order_test")
    framework = temp_root / "api-test-framework"
    commands = {
        "cases": {
            "TC-SEQUENTIAL": {
                "setup": [
                    {
                        "command_id": "SQL-EXTRACT-BEFORE-001",
                        "sql": "SELECT status AS original_status FROM identity_user WHERE id = :user_id",
                        "params": {"user_id": 150},
                        "extract_to_runtime_context": ["original_status"],
                    },
                    {
                        "command_id": "SQL-SETUP-001",
                        "sql": "UPDATE identity_user SET status = :original_status WHERE id = :user_id",
                        "params": {
                            "user_id": 150,
                            "original_status": "${runtime_context.original_status}",
                            "window_start": "${runtime_context.task_window_start}",
                        },
                    },
                ]
            },
            "TC-FORWARD-REF": {
                "setup": [
                    {
                        "command_id": "SQL-SETUP-BEFORE-EXTRACT",
                        "sql": "UPDATE identity_user SET status = :future_status WHERE id = :user_id",
                        "params": {
                            "user_id": 150,
                            "future_status": "${runtime_context.future_status}",
                        },
                    },
                    {
                        "command_id": "SQL-EXTRACT-AFTER-001",
                        "sql": "SELECT status AS future_status FROM identity_user WHERE id = :user_id",
                        "params": {"user_id": 150},
                        "extract_to_runtime_context": ["future_status"],
                    },
                ]
            },
        }
    }
    write(
        framework / "data" / "case_sql_commands.yaml",
        yaml.safe_dump(commands, allow_unicode=True, sort_keys=False),
    )

    errors: list[str] = []
    validator.validate_sql_fixture_deep_static_gate(framework, errors)

    assert not any("TC-SEQUENTIAL" in error and "runtime_context" in error for error in errors)
    assert any("TC-FORWARD-REF/SQL-SETUP-BEFORE-EXTRACT" in error and "future_status" in error for error in errors)


def test_failure_path_cleanup_gate_accepts_request_marker_fallback(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_failure_path_cleanup_pass_test")
    framework = temp_root / "api-test-framework"
    write(
        framework / "configs" / "test.yaml",
        yaml.safe_dump({"runtime_variables": {"run_marker": "${nowIso}"}}, sort_keys=False),
    )
    commands = {
        "cases": {
            "TC-WRITE-AMBIGUOUS": {
                "runtime_extract": [
                    {
                        "command_id": "SQL-EXTRACT-CREATED-ID-BY-MARKER",
                        "queries": {
                            "created_id": "SELECT id AS created_id FROM business_object WHERE marker = :run_marker LIMIT 1"
                        },
                        "params_source": {"run_marker": "${runtime_context.run_marker}"},
                        "optional_query_names": ["created_id"],
                    }
                ],
                "cleanup": [
                    {
                        "command_id": "SQL-CLEAN-PRIMARY",
                        "side_effect_class": "primary",
                        "skip_if_missing_runtime_vars": ["created_id"],
                        "sql": "DELETE FROM business_object WHERE id = :created_id AND marker = :run_marker",
                        "params": {
                            "created_id": "${runtime_context.created_id}",
                            "run_marker": "${runtime_context.run_marker}",
                        },
                    },
                    {
                        "command_id": "SQL-RESTORE-PRESTATE",
                        "side_effect_class": "prestate_restore",
                        "sql": "UPDATE known_target SET status = :before_status WHERE id = :target_id",
                        "params": {"before_status": 0, "target_id": 7},
                    },
                ],
                "final_verify": [
                    {
                        "query_id": "SQL-VERIFY-RUN-MARKER-NO-RESIDUE",
                        "sql": "SELECT COUNT(*) AS marker_count FROM business_object WHERE marker = :run_marker",
                        "params": {"run_marker": "${runtime_context.run_marker}"},
                        "expected_count": 0,
                    }
                ],
                "failure_path_cleanup": {
                    "transport_outcome": "ambiguous",
                    "request_ownership_vars": ["run_marker"],
                    "fallback_runtime_extract_command_ids": ["SQL-EXTRACT-CREATED-ID-BY-MARKER"],
                    "always_run_restore_command_ids": ["SQL-RESTORE-PRESTATE"],
                    "final_verify_command_ids": ["SQL-VERIFY-RUN-MARKER-NO-RESIDUE"],
                },
            }
        }
    }
    write(
        framework / "data" / "case_sql_commands.yaml",
        yaml.safe_dump(commands, allow_unicode=True, sort_keys=False),
    )

    errors: list[str] = []
    validator.validate_sql_fixture_deep_static_gate(framework, errors)

    assert errors == []


def test_failure_path_cleanup_gate_rejects_response_id_only_cleanup(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_failure_path_cleanup_block_test")
    framework = temp_root / "api-test-framework"
    commands = {
        "cases": {
            "TC-RESPONSE-ID-ONLY": {
                "cleanup": [
                    {
                        "command_id": "SQL-CLEAN-PRIMARY",
                        "side_effect_class": "primary",
                        "sql": "DELETE FROM business_object WHERE id = :created_id",
                        "params": {"created_id": "${runtime_context.created_id}"},
                    },
                    {
                        "command_id": "SQL-RESTORE-PRESTATE",
                        "side_effect_class": "prestate_restore",
                        "sql": "UPDATE known_target SET status = :before_status WHERE id = :target_id",
                        "params": {
                            "before_status": 0,
                            "target_id": 7,
                            "created_id": "${runtime_context.created_id}",
                        },
                    },
                ]
            }
        }
    }
    write(
        framework / "data" / "case_sql_commands.yaml",
        yaml.safe_dump(commands, allow_unicode=True, sort_keys=False),
    )

    errors: list[str] = []
    validator.validate_sql_fixture_deep_static_gate(framework, errors)

    assert any("未声明缺失策略" in error and "created_id" in error for error in errors)
    assert any("SQL 未使用的运行变量" in error and "created_id" in error for error in errors)
    assert any("ambiguous failure_path_cleanup" in error for error in errors)


def test_failure_path_cleanup_gate_skips_explicit_non_live_cases(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_failure_path_non_live_test")
    framework = temp_root / "api-test-framework"
    write(
        framework / "data" / "flow_cases.yaml",
        """schema_version: 1
flows:
  - case_id: TC-NON-LIVE-WRITE
    automation_decision: generated_non_live
""",
    )
    write(
        framework / "data" / "case_sql_commands.yaml",
        """schema_version: 1
cases:
  TC-NON-LIVE-WRITE:
    setup: []
    runtime_extract: []
    cleanup:
      - command_id: SQL-CLEAN-NON-LIVE
        sql: DELETE FROM business_object WHERE id = :created_id
        params:
          created_id: ${runtime_context.created_id}
    final_verify: []
""",
    )

    errors: list[str] = []
    validator.validate_sql_fixture_deep_static_gate(framework, errors)

    assert errors == []
    assert validator.framework_has_post_request_cleanup_dependencies(framework) is False


def test_sql_executor_template_skips_only_missing_optional_command_and_continues_cleanup() -> None:
    sys.path.insert(0, str(FRAMEWORK_TEMPLATE))
    try:
        module = load_module(
            FRAMEWORK_TEMPLATE / "core" / "sql_executor.py",
            "template_sql_executor_failure_path",
        )
    finally:
        sys.path.remove(str(FRAMEWORK_TEMPLATE))
    executor = module.SqlExecutor({}, {})
    executed: list[str] = []

    def fake_execute(case_id: str, stage_name: str, command: dict, case_context: dict) -> None:
        executed.append(command["command_id"])
        if command["command_id"] == "CLEAN-FAILS":
            raise AssertionError("cleanup failed")

    executor._execute_command = fake_execute
    commands = {
        "cleanup": [
            {
                "command_id": "CLEAN-OPTIONAL",
                "side_effect_class": "conditional",
                "skip_if_missing_runtime_vars": ["optional_id"],
            },
            {"command_id": "CLEAN-FAILS", "side_effect_class": "primary"},
            {"command_id": "RESTORE-ALWAYS", "side_effect_class": "prestate_restore"},
        ]
    }

    with pytest.raises(AssertionError, match="1 个失败命令"):
        executor.cleanup("TC-CLEANUP", commands)

    assert executed == ["CLEAN-FAILS", "RESTORE-ALWAYS"]


def test_sql_validator_template_enforces_primary_fallback_and_unused_runtime_params() -> None:
    sys.path.insert(0, str(FRAMEWORK_TEMPLATE))
    try:
        module = load_module(
            FRAMEWORK_TEMPLATE / "core" / "sql_validator.py",
            "template_sql_validator_failure_path",
        )
    finally:
        sys.path.remove(str(FRAMEWORK_TEMPLATE))

    primary_cleanup = {
        "command_id": "SQL-CLEAN-PRIMARY",
        "side_effect_class": "primary",
        "skip_if_missing_runtime_vars": ["created_id"],
        "sql": "DELETE FROM business_object WHERE id = :created_id AND marker = :run_marker",
        "params": {
            "created_id": "${runtime_context.created_id}",
            "run_marker": "${runtime_context.run_marker}",
        },
    }
    incomplete_commands = {
        "runtime_extract": [],
        "cleanup": [primary_cleanup],
        "final_verify": [],
        "failure_path_cleanup": {},
    }

    with pytest.raises(ValueError, match="ambiguous transport contract"):
        module.SqlCommandValidator._validate_failure_path_cleanup_contract(
            "TC-INCOMPLETE",
            incomplete_commands,
        )

    with pytest.raises(ValueError, match="未被 SQL 使用的运行变量"):
        module.SqlCommandValidator._validate_bind_params(
            "TC-UNUSED",
            {
                "sql": "UPDATE known_target SET status = :before_status WHERE id = :target_id"
            },
            {
                "before_status": 0,
                "target_id": 7,
                "created_id": "${runtime_context.created_id}",
            },
            {
                "before_status": 0,
                "target_id": 7,
                "created_id": "${runtime_context.created_id}",
            },
            True,
        )


def test_sql_validator_template_keeps_legacy_missing_variable_policy_compatible() -> None:
    sys.path.insert(0, str(FRAMEWORK_TEMPLATE))
    try:
        module = load_module(
            FRAMEWORK_TEMPLATE / "core" / "sql_validator.py",
            "template_sql_validator_legacy_compatibility",
        )
    finally:
        sys.path.remove(str(FRAMEWORK_TEMPLATE))

    legacy_command = {
        "command_id": "SQL-CLEAN-LEGACY",
        "skip_if_missing_runtime_vars": ["created_id"],
        "sql": "DELETE FROM business_object WHERE id = :created_id",
        "params": {"created_id": "${runtime_context.created_id}"},
    }
    module.SqlCommandValidator._validate_command_missing_variable_policy(
        "TC-LEGACY",
        "SQL 后置清理",
        legacy_command,
        enforce_failure_path_policy=False,
    )

    with pytest.raises(ValueError, match="side_effect_class"):
        module.SqlCommandValidator._validate_command_missing_variable_policy(
            "TC-MIGRATED",
            "SQL 后置清理",
            legacy_command,
            enforce_failure_path_policy=True,
        )


def test_sql_finalizer_template_attempts_all_post_request_stages() -> None:
    source = (FRAMEWORK_TEMPLATE / "conftest.py").read_text(encoding="utf-8")
    function_start = source.index("def case_sql_manager(")
    function_end = source.index("\n\n@pytest.fixture", function_start)
    function_source = source[function_start:function_end]

    assert '"runtime_extract", executor.extract_runtime' in function_source
    assert '"cleanup", executor.cleanup' in function_source
    assert '"final_verify", executor.final_verify' in function_source
    assert "lifecycle_errors.append((stage_name, error))" in function_source


def test_failure_path_cleanup_rules_are_wired_into_skill_and_generator() -> None:
    root_skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    cleanup_gate = (
        ROOT
        / "components"
        / "api-test-framework-generator"
        / "references"
        / "setup-cleanup-defect-gate.md"
    ).read_text(encoding="utf-8")
    conversion_contract = (
        ROOT
        / "components"
        / "api-test-framework-generator"
        / "references"
        / "conversion-contract.md"
    ).read_text(encoding="utf-8")

    assert "ambiguous write outcome" in root_skill
    assert "post_request_variable_dependency_gate" in cleanup_gate
    assert "ambiguous_write_outcome_cleanup_gate" in cleanup_gate
    assert "failure_path_cleanup" in conversion_contract
    assert "Do not generate a blanket missing-variable rule" in conversion_contract


def test_framework_quality_gate_requires_failure_path_status_for_late_cleanup_vars(temp_root: Path) -> None:
    validator = load_module(VALIDATE_PIPELINE, "validate_pipeline_failure_path_status_test")
    framework = temp_root / "api-test-framework"
    write(
        framework / "data" / "case_sql_commands.yaml",
        yaml.safe_dump(
            {
                "cases": {
                    "TC-LATE-CLEANUP": {
                        "cleanup": [
                            {
                                "command_id": "SQL-CLEAN-LATE",
                                "side_effect_class": "primary",
                                "skip_if_missing_runtime_vars": ["created_id"],
                                "sql": "DELETE FROM business_object WHERE id = :created_id",
                                "params": {"created_id": "${runtime_context.created_id}"},
                            }
                        ]
                    }
                }
            },
            allow_unicode=True,
            sort_keys=False,
        ),
    )
    write(framework / "接口案例.md", "# 接口案例\n")
    generation_status = """execution_fact_closure:
  status: passed
  unresolved_main_flow_business_fields: 0
  stateful_cases_without_setup_cleanup: 0
  pre_login_steps_with_token_injection: 0
  unresolved_auth_placeholders: 0
  cross_role_identity_mismatches: 0
assertion_strength_gate:
  status: passed
business_readable_input_quality:
  status: passed
business_result_observability:
  status: passed
setup_cleanup_materialization:
  status: passed
final_case_archive:
  status: passed
"""

    errors: list[str] = []
    validator.validate_framework_quality_gates(framework, generation_status, errors)

    assert any("缺少 failure_path_cleanup_resilience 明细" in error for error in errors)

    with_status = generation_status + """failure_path_cleanup_resilience:
  status: passed
  checked_write_case_count: 1
  response_id_dependent_case_count: 1
  fallback_cleanup_case_count: 1
  missing_fallback_case_ids: []
  unsafe_skip_primary_cleanup_case_ids: []
  restore_with_late_variable_case_ids: []
"""
    errors = []
    validator.validate_framework_quality_gates(framework, with_status, errors)

    assert not any("failure_path_cleanup_resilience" in error for error in errors)


def sql_generation_gate() -> dict:
    return {
        "status": "passed",
        "passed": True,
        "reason": "SQL 生成准出门禁通过",
        "source_files": ["执行级接口用例集.md", "前置数据构造规则.md", "数据模型.md"],
        "quality_checks": {
            "table_structure_verified": True,
            "knowledge_graph_verified": True,
            "ownership_boundary_verified": True,
            "cleanup_scope_verified": True,
            "id_cleanup_verified": True,
            "insert_exit_gate_verified": True,
            "delete_exit_gate_verified": True,
            "api_insufficiency_verified": True,
            "seed_scope_guard_verified": True,
            "dangerous_sql_rejected": True,
            "sql_syntax_verified": True,
            "sql_logic_verified": True,
            "historical_shape_reference_verified": True,
            "runtime_validation_verified": False,
        },
        "allowed_tables": ["user_account"],
        "validation_report": "data/case_sql_validation.yaml",
    }


def insert_command() -> dict:
    return {
        "name": "准备测试账户",
        "source_evidence": "前置数据构造规则.md#TC001",
        "api_unavailable_reason": "接口无法构造目标状态",
        "api_unavailable_source_evidence": "接口测试用例设计文档.md#TC001",
        "seed_scope_reason": "仅准备目标业务状态，普通请求字段由用例参数或运行变量提供",
        "allowed_seed_fields": ["id", "status"],
        "forbidden_seed_fields": ["token", "smsCode", "pageNum", "pageSize", "deviceId", "thirdPartyOrderId"],
        "runtime_value_fields": ["request.body", "auth.token", "runtime_context"],
        "distortion_risk": "low",
        "historical_shape_reference": {
            "status": "passed",
            "source_ref": "database_mcp_evidence_index.yaml#user_account-active-shape",
            "sampled_table": "user_account",
            "sample_scope": "same_business_state_recent_non_deleted",
            "sample_count": 3,
            "verified_fields": ["id", "status"],
            "privacy_status": "sampled_shape_only_redacted",
        },
        "target_tables": ["user_account"],
        "cleanup_identity": {"field": "id", "value_ref": "params.id"},
        "ownership": {"keys": ["id"]},
        "sql_exit_gate": {
            "status": "passed",
            "passed": True,
            "checks": {
                "target_table_verified": True,
                "ownership_boundary_verified": True,
                "expected_effect_verified": True,
                "insert_identity_verified": True,
                "insert_columns_verified": True,
            },
        },
        "sql": "INSERT INTO user_account (id, status) VALUES (:id, :status)",
        "params": {"id": "test-user-001", "status": "ACTIVE"},
        "expected_effect": {"affected_rows": 1},
    }


def delete_command(sql: str = "DELETE FROM user_account WHERE id = :id") -> dict:
    return {
        "name": "清理测试账户",
        "source_evidence": "前置数据构造规则.md#TC001",
        "api_unavailable_reason": "接口无法保证清理状态",
        "api_unavailable_source_evidence": "接口测试用例设计文档.md#TC001",
        "target_tables": ["user_account"],
        "cleanup_identity": {"field": "id", "value_ref": "params.id"},
        "ownership": {"keys": ["id"]},
        "sql_exit_gate": {
            "status": "passed",
            "passed": True,
            "checks": {
                "target_table_verified": True,
                "ownership_boundary_verified": True,
                "expected_effect_verified": True,
                "delete_identity_verified": True,
                "delete_scope_verified": True,
            },
        },
        "sql": sql,
        "params": {"id": "test-user-001"},
        "expected_effect": {"affected_rows": 1},
    }


def test_sql_template_static_gate_blocks_default_and_dangerous_sql(temp_root: Path) -> None:
    framework = temp_root / "api-test-framework"
    shutil.copytree(FRAMEWORK_TEMPLATE, framework)

    blocked = run([sys.executable, str(framework / "check_sql_commands.py"), "--env=dev"], cwd=framework)
    assert blocked.returncode != 0
    assert "SQL 生成准出门禁未通过" in (blocked.stdout + blocked.stderr)

    commands = {
        "sql_generation_gate": sql_generation_gate(),
        "cases": {
            "TC001": {
                "setup": [insert_command()],
                "cleanup": [delete_command()],
            }
        },
    }
    write(framework / "data" / "case_sql_commands.yaml", yaml.safe_dump(commands, allow_unicode=True, sort_keys=False))

    safe = run([sys.executable, str(framework / "check_sql_commands.py"), "--env=dev"], cwd=framework)
    validation = yaml.safe_load((framework / "data" / "case_sql_validation.yaml").read_text(encoding="utf-8"))
    assert safe.returncode == 0, safe.stdout + safe.stderr
    assert validation["sql_validation"]["status"] == "static_passed"

    missing_seed_gate = json.loads(json.dumps(commands))
    del missing_seed_gate["sql_generation_gate"]["quality_checks"]["seed_scope_guard_verified"]
    write(framework / "data" / "case_sql_commands.yaml", yaml.safe_dump(missing_seed_gate, allow_unicode=True, sort_keys=False))
    missing_seed_guard = run([sys.executable, str(framework / "check_sql_commands.py"), "--env=dev"], cwd=framework)
    assert missing_seed_guard.returncode != 0
    assert "seed_scope_guard_verified" in (missing_seed_guard.stdout + missing_seed_guard.stderr)

    missing_historical_shape_gate = json.loads(json.dumps(commands))
    del missing_historical_shape_gate["sql_generation_gate"]["quality_checks"]["historical_shape_reference_verified"]
    write(
        framework / "data" / "case_sql_commands.yaml",
        yaml.safe_dump(missing_historical_shape_gate, allow_unicode=True, sort_keys=False),
    )
    missing_shape_gate = run([sys.executable, str(framework / "check_sql_commands.py"), "--env=dev"], cwd=framework)
    assert missing_shape_gate.returncode != 0
    assert "historical_shape_reference_verified" in (missing_shape_gate.stdout + missing_shape_gate.stderr)

    missing_historical_shape = json.loads(json.dumps(commands))
    del missing_historical_shape["cases"]["TC001"]["setup"][0]["historical_shape_reference"]
    write(framework / "data" / "case_sql_commands.yaml", yaml.safe_dump(missing_historical_shape, allow_unicode=True, sort_keys=False))
    missing_shape = run([sys.executable, str(framework / "check_sql_commands.py"), "--env=dev"], cwd=framework)
    assert missing_shape.returncode != 0
    assert "历史形态引用证据" in (missing_shape.stdout + missing_shape.stderr)

    invalid_privacy = json.loads(json.dumps(commands))
    invalid_privacy["cases"]["TC001"]["setup"][0]["historical_shape_reference"]["privacy_status"] = "raw_sample"
    write(framework / "data" / "case_sql_commands.yaml", yaml.safe_dump(invalid_privacy, allow_unicode=True, sort_keys=False))
    invalid_privacy_result = run([sys.executable, str(framework / "check_sql_commands.py"), "--env=dev"], cwd=framework)
    assert invalid_privacy_result.returncode != 0
    assert "历史形态引用证据未脱敏" in (invalid_privacy_result.stdout + invalid_privacy_result.stderr)

    invalid_sample_count = json.loads(json.dumps(commands))
    invalid_sample_count["cases"]["TC001"]["setup"][0]["historical_shape_reference"]["sample_count"] = 0
    write(framework / "data" / "case_sql_commands.yaml", yaml.safe_dump(invalid_sample_count, allow_unicode=True, sort_keys=False))
    invalid_sample_count_result = run([sys.executable, str(framework / "check_sql_commands.py"), "--env=dev"], cwd=framework)
    assert invalid_sample_count_result.returncode != 0
    assert "sample_count 必须为正整数" in (invalid_sample_count_result.stdout + invalid_sample_count_result.stderr)

    cleanup_only_commands = json.loads(json.dumps(commands))
    cleanup_only_commands["cases"]["TC001"]["setup"] = []
    del cleanup_only_commands["sql_generation_gate"]["quality_checks"]["historical_shape_reference_verified"]
    write(framework / "data" / "case_sql_commands.yaml", yaml.safe_dump(cleanup_only_commands, allow_unicode=True, sort_keys=False))
    cleanup_only = run([sys.executable, str(framework / "check_sql_commands.py"), "--env=dev"], cwd=framework)
    assert cleanup_only.returncode == 0, cleanup_only.stdout + cleanup_only.stderr

    commands["cases"]["TC001"]["cleanup"][0] = delete_command("DELETE FROM user_account WHERE 1=1")
    write(framework / "data" / "case_sql_commands.yaml", yaml.safe_dump(commands, allow_unicode=True, sort_keys=False))
    dangerous = run([sys.executable, str(framework / "check_sql_commands.py"), "--env=dev"], cwd=framework)
    assert dangerous.returncode != 0
    assert "无边界" in (dangerous.stdout + dangerous.stderr)


def test_runtime_evidence_script_materialization_gate_is_wired() -> None:
    reference = (
        ROOT
        / "components"
        / "api-test-framework-generator"
        / "references"
        / "runtime-evidence-script-materialization.md"
    )
    generator_skill = ROOT / "components" / "api-test-framework-generator" / "SKILL.md"
    suite_skill = ROOT / "SKILL.md"
    runtime_usability = (
        ROOT
        / "components"
        / "api-test-framework-generator"
        / "references"
        / "runtime-usability-gate.md"
    )
    runtime_failure = (
        ROOT
        / "components"
        / "api-test-framework-generator"
        / "references"
        / "runtime-failure-diagnosis.md"
    )

    assert reference.exists()
    reference_text = reference.read_text(encoding="utf-8")
    generator_text = generator_skill.read_text(encoding="utf-8")
    suite_text = suite_skill.read_text(encoding="utf-8")
    usability_text = runtime_usability.read_text(encoding="utf-8")
    failure_text = runtime_failure.read_text(encoding="utf-8")

    assert "expected_response.business_code_value" in reference_text
    assert "session_role" in reference_text
    assert "runtime_evidence_script_mapping" in reference_text
    assert "runtime_evidence_script_mapping_audit.yaml" in reference_text
    assert "FAILED_RUNTIME_EVIDENCE_SCRIPT_MATERIALIZATION" in reference_text
    assert "references/runtime-evidence-script-materialization.md" in generator_text
    assert "runtime_evidence_script_mapping_audit.yaml" in generator_text
    assert "generation_status.yaml.runtime_evidence_script_materialization.status" in suite_text
    assert "FAILED_RUNTIME_EVIDENCE_SCRIPT_MATERIALIZATION" in usability_text
    assert "runtime-evidence script materialization audit" in generator_text
    assert "runtime-evidence script materialization defect" in failure_text


def test_script_materialization_fidelity_rules_are_documented_consistently() -> None:
    suite_skill = ROOT / "SKILL.md"
    generator_skill = ROOT / "components" / "api-test-framework-generator" / "SKILL.md"
    references = ROOT / "components" / "api-test-framework-generator" / "references"
    runtime_evidence = references / "runtime-evidence-script-materialization.md"
    runtime_usability = references / "runtime-usability-gate.md"
    setup_cleanup = references / "setup-cleanup-defect-gate.md"
    conversion = references / "conversion-contract.md"
    final_archive = references / "final-case-archive.md"

    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            suite_skill,
            generator_skill,
            runtime_evidence,
            runtime_usability,
            setup_cleanup,
            conversion,
            final_archive,
        )
    )

    assert "request_shape_fidelity" in combined
    assert "scalar/list/object/map" in combined
    assert "generated collection artifacts" in combined
    assert "persisted representation" in combined
    assert "source formulas" in combined
    assert "current-run extraction" in combined
    assert "SQL lifecycle idempotence" in combined
    assert "completed-stage guard" in combined
    assert "status-code-only" in combined
    assert "fixed historical constants" in combined or "historical aggregate constants" in combined

    forbidden_project_terms = [
        "TC-LC-RT-008",
        "TC-SRC-071",
        "feedback/tags",
        "taskType",
        "productId",
        "unilink",
        "provider_good_rate",
    ]
    for term in forbidden_project_terms:
        assert term not in combined



def test_runtime_plan_orders_long_chain_before_priority_buckets(temp_root: Path) -> None:
    case_list = temp_root / "case_list.yaml"
    write(
        case_list,
        """schema_version: 1
stage: interface_testcase_generation
status: passed
cases:
  - case_id: DC-P2-001
    name: 普通查询P2
    priority: p2
    case_type: single
    module: demo
    method: GET
    path: /demo/list
  - case_id: DC-P0-CHAIN
    name: 真实业务长链路
    priority: p0
    case_type: chain
    flow_id: FLOW-001
    module: demo
    method: GET
    path: /demo/flow/verify
  - case_id: DC-P1-001
    name: 普通查询P1
    priority: p1
    case_type: single
    module: demo
    method: GET
    path: /demo/detail
  - case_id: DC-P0-001
    name: 普通查询P0
    priority: p0
    case_type: single
    module: demo
    method: GET
    path: /demo/profile
""",
    )
    out = temp_root / "04-runtime-evidence-plan"

    result = run([sys.executable, str(BUILD_RUNTIME_PLAN), "--case-list", str(case_list), "--output-dir", str(out), "--env-name", "test"])

    assert result.returncode == 0, result.stderr
    plan = yaml.safe_load((out / "runtime_request_plan.skeleton.yaml").read_text(encoding="utf-8"))
    assert [step["case_id"] for step in plan["steps"]] == ["DC-P0-CHAIN", "DC-P0-001", "DC-P1-001", "DC-P2-001"]
    assert [step["priority_bucket"] for step in plan["steps"]] == ["long_chain", "p0", "p1", "p2"]


def test_live_request_evidence_continues_after_recoverable_step_failure(temp_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_module(RUN_LIVE_REQUEST_EVIDENCE, "run_live_request_evidence_under_test")
    plan_path = temp_root / "runtime_request_plan.yaml"
    out = temp_root / "04-runtime-evidence"
    write(
        plan_path,
        """schema_version: 1
env:
  env_name: test
  base_urls:
    demo: http://example.test
request_scope:
  mutating_requests_allowed: false
cleanup:
  required: false
steps:
  - step_id: STEP-001
    case_id: DC-LC-001
    flow_id: FLOW-001
    priority_bucket: long_chain
    module: demo
    method: GET
    path: /ok
    expected_status: 200
    request_decision: request_allowed
    extract:
      item_id: $.data.id
  - step_id: STEP-002
    case_id: DC-P0-001
    priority_bucket: p0
    module: demo
    method: GET
    path: /bad
    expected_status: 200
    request_decision: request_allowed
    extract:
      missing_id: $.data.id
  - step_id: STEP-003
    case_id: DC-P1-001
    priority_bucket: p1
    module: demo
    method: GET
    path: /also-ok
    expected_status: 200
    request_decision: request_allowed
    assertions_ref: case_list.yaml#/cases/2
    extract: {}
""",
    )

    def fake_request_json(method: str, url: str, headers: dict[str, str], body: object, timeout: float) -> tuple[int, object]:
        if url.endswith("/bad"):
            return 500, {"error": "boom"}
        return 200, {"data": {"id": 159}}

    monkeypatch.setattr(module, "request_json", fake_request_json)

    exit_code = module.run(plan_path, out, None)

    assert exit_code == 0
    stage_status = yaml.safe_load((out / "runtime_stage_status.yaml").read_text(encoding="utf-8"))
    assert stage_status["status"] == "partial"
    items = stage_status["continuation_queue"]["items"]
    assert [item["queue_state"] for item in items] == ["evidenced", "retryable", "evidenced"]
    assert all("status" not in item for item in items)
    assert (out / "runtime_evidence_queue.yaml").is_file()

    validation = run([sys.executable, str(VALIDATE_RUNTIME_EVIDENCE), str(out), "--require-usable"])
    assert validation.returncode == 0, validation.stdout + validation.stderr


def test_runtime_validator_rejects_nested_queue_status_field(temp_root: Path) -> None:
    evidence_dir = temp_root / "04-runtime-evidence"
    evidence_dir.mkdir(parents=True)
    write(
        evidence_dir / "runtime_stage_status.yaml",
        """schema_version: 1
stage: runtime_live_evidence
status: partial
next_stage_allowed: true
request_scope:
  env_name: test
  allowed_modules:
    - demo
  mutating_requests_allowed: false
  cleanup_required: false
input_paths:
  - path: runtime_request_plan.yaml
    role: runtime_request_plan
output_paths:
  - path: runtime_evidence.yaml
    role: runtime_evidence
gate_checks:
  - check_id: direct_request_execution
    status: blocked
    evidence_refs:
      - runtime_evidence.yaml
continuation_queue:
  items:
    - case_id: DC-P0-001
      priority_bucket: p0
      status: retryable
      reason_code: should_use_queue_state
blocking_issues: []
""",
    )
    write(
        evidence_dir / "runtime_evidence.yaml",
        """schema_version: 1
stage: runtime_live_evidence
status: partial
next_stage_allowed: true
request_scope:
  env_name: test
  allowed_modules:
    - demo
  mutating_requests_allowed: false
  cleanup_required: false
auth_evidence:
  status: missing
  token_source: none
  token_extract_path: ""
  secret_redaction: enabled
evidence_items:
  - evidence_id: RT-001
    case_id: DC-001
    method: GET
    path: /demo
    response_status: 200
    value_type: field_value
    field_path: $.data.id
    field_value: 159
    source_status: confirmed
    usable_for_execution_case: true
    redacted: false
conflict_items: []
blocking_issues: []
""",
    )
    write(
        evidence_dir / "runtime_value_catalog.yaml",
        """schema_version: 1
stage: runtime_value_catalog
status: partial
values:
  - value_id: VAL-001
    value_type: id
    field: id
    value: 159
    source_type: live_request_evidence
    source_ref: runtime_evidence.yaml#RT-001
    source_status: confirmed
usable_fact_types:
  - variable_link
missing_values: []
conflict_values: []
blocking_issues: []
""",
    )

    validation = run([sys.executable, str(VALIDATE_RUNTIME_EVIDENCE), str(evidence_dir), "--require-usable"])

    assert validation.returncode == 1
    assert "禁止使用 status 字段" in validation.stdout
    assert "status 非法或缺失：retryable" not in validation.stdout


def test_template_runtime_identifier_limit_is_configurable() -> None:
    template_path = FRAMEWORK_TEMPLATE / "core" / "runtime_context.py"
    spec = importlib.util.spec_from_file_location("template_runtime_context_limits", template_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    runtime_context = {
        "nowIso": "20260715104500",
        "caseId": "TC-LC-RT-013-conversation-read-visible-with-a-very-long-case-id",
    }
    env_config = {
        "runtime_variables": {"traceId": "rt-framework-${nowIso}-${caseId}"},
        "runtime_identifier_limits": {"traceId": 64},
    }

    module.publish_runtime_variables(runtime_context, env_config)

    assert len(runtime_context["traceId"]) == 64
    assert runtime_context["traceId"] == runtime_context["trace_id"]


def test_template_sql_fixture_predicate_distinguishes_non_sql_status_and_ledger_membership() -> None:
    sys.path.insert(0, str(FRAMEWORK_TEMPLATE))
    try:
        module = load_module(FRAMEWORK_TEMPLATE / "core" / "case_loader.py", "template_case_loader_sql_predicate")
    finally:
        sys.path.pop(0)
    interfaces = {
        "interface-001": {
            "method": "GET",
            "path": "/api/v1/example",
            "module": "example",
        }
    }
    source = FRAMEWORK_TEMPLATE / "data" / "cases" / "example.yaml"
    raw_case = {
        "case_id": "TC-NON-SQL-001",
        "interface_id": "interface-001",
        "sql_fixture_required": False,
        "setup_cleanup_materialization": "no_cleanup_required_after_db_probe",
        "db_assertion_materialization": "not_required_observable_api_response",
    }

    pure_api = module.build_case_parameter(raw_case, interfaces, source)
    ledger_bound = module.build_case_parameter(raw_case, interfaces, source, {"TC-NON-SQL-001"})

    assert pure_api["sql_fixture_required"] is False
    assert ledger_bound["sql_fixture_required"] is True
