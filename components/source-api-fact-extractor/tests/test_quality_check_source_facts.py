from __future__ import annotations

import json
import re
import shutil
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PROJECT = SKILL_ROOT / "examples" / "sample-java-project"


def test_quality_check_writes_report_for_clean_sample(tmp_path):
    from quality_check_source_facts import run_quality_check
    from scan_source import scan

    scan(SAMPLE_PROJECT, tmp_path)
    source_facts = tmp_path / "docs" / "source-facts"

    report = run_quality_check(
        src_root=SAMPLE_PROJECT,
        facts_path=source_facts / "source-api-facts.json",
        out_dir=source_facts,
    )

    assert report["summary"]["error_count"] == 0
    assert report["coverage"]["expected_api_count"] == 3
    assert report["coverage"]["actual_api_count"] == 3
    assert (source_facts / "07-extraction-quality-report.md").exists()
    assert (source_facts / "source-api-quality-report.json").exists()
    assert (source_facts / "01_接口测试用例设计文档.md").exists()
    assert (source_facts / "coverage_matrix.yaml").exists()
    assert (source_facts / "08-security-transform-facts.md").exists()
    assert (source_facts / "source_api_fact_artifacts.yaml").exists()


def test_quality_check_detects_missing_feign_entry(tmp_path):
    from quality_check_source_facts import run_quality_check
    from scan_source import scan

    project = copy_sample_with_feign(tmp_path)
    scan(project, tmp_path)
    source_facts = tmp_path / "docs" / "source-facts"
    facts_path = source_facts / "source-api-facts.json"
    data = json.loads(facts_path.read_text(encoding="utf-8"))

    assert any(api["entry"]["class_name"] == "AccountClient" for api in data["apis"])
    data["apis"] = [api for api in data["apis"] if api["entry"]["class_name"] != "AccountClient"]
    data["summary"]["api_count"] = len(data["apis"])
    facts_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    report = run_quality_check(src_root=project, facts_path=facts_path, out_dir=source_facts)

    assert report["summary"]["error_count"] > 0
    assert any(
        issue["code"] == "MISSING_SOURCE_API" and "AccountClient.syncAccount" in issue["message"]
        for issue in report["issues"]
    )


def test_quality_check_detects_resolved_db_operation_without_table(tmp_path):
    from quality_check_source_facts import run_quality_check
    from scan_source import scan

    scan(SAMPLE_PROJECT, tmp_path)
    source_facts = tmp_path / "docs" / "source-facts"
    facts_path = source_facts / "source-api-facts.json"
    data = json.loads(facts_path.read_text(encoding="utf-8"))
    create_api = next(api for api in data["apis"] if api["entry"]["method_name"] == "create")
    create_effect = next(effect for effect in create_api["db_side_effects"] if effect["operation_type"] == "CREATE")
    create_effect["tables"] = "UNKNOWN"
    create_effect["entity_or_do"] = "UNKNOWN"
    facts_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    report = run_quality_check(src_root=SAMPLE_PROJECT, facts_path=facts_path, out_dir=source_facts)

    assert report["summary"]["error_count"] > 0
    assert any(issue["code"] == "DB_TABLE_UNRESOLVED" for issue in report["issues"])


def test_quality_check_detects_evidence_line_method_mismatch(tmp_path):
    from quality_check_source_facts import run_quality_check
    from scan_source import scan

    scan(SAMPLE_PROJECT, tmp_path)
    source_facts = tmp_path / "docs" / "source-facts"
    facts_path = source_facts / "source-api-facts.json"
    data = json.loads(facts_path.read_text(encoding="utf-8"))
    api = next(item for item in data["apis"] if item["entry"]["class_name"] == "AccountController")
    api["entry"]["source_evidence"] = re.sub(r":\d+(\s+\|)", r":1\1", api["entry"]["source_evidence"])
    facts_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    report = run_quality_check(src_root=SAMPLE_PROJECT, facts_path=facts_path, out_dir=source_facts)

    assert report["summary"]["error_count"] > 0
    assert any(issue["code"] == "EVIDENCE_METHOD_MISMATCH" for issue in report["issues"])


def test_quality_check_rejects_plaintext_secret_config_value(tmp_path):
    from quality_check_source_facts import run_quality_check
    from scan_source import scan

    scan(SAMPLE_PROJECT, tmp_path)
    source_facts = tmp_path / "docs" / "source-facts"
    facts_path = source_facts / "source-api-facts.json"
    data = json.loads(facts_path.read_text(encoding="utf-8"))
    data["secret_config_refs"] = [
        {
            "config_key": "sample.api.secret",
            "secret_ref": "config.sample.api.secret",
            "sensitivity": "HIGH",
            "value_visible": "YES",
            "config_value": "plain-secret",
            "config_value_masked": "pl********et",
            "execution_impact": "用于外部接口鉴权。",
            "script_strategy": "运行时注入。",
            "evidence": "src/main/resources/application.yml:1 | config.sample.api.secret",
        }
    ]
    data["summary"]["secret_config_ref_count"] = 1
    facts_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    report = run_quality_check(src_root=SAMPLE_PROJECT, facts_path=facts_path, out_dir=source_facts)

    assert any(issue["code"] == "SECRET_CONFIG_PLAINTEXT_FORBIDDEN" for issue in report["issues"])


def test_security_transform_gate_requires_runtime_secret_reference():
    from quality_check_source_facts import check_security_transform_structure

    issues: list[dict[str, str]] = []
    check_security_transform_structure(
        [],
        [],
        [
            {
                "config_key": "sample.api.secret",
                "sensitivity": "HIGH",
                "value_visible": "YES",
                "config_value_masked": "sa********et",
                "execution_impact": "用于接口鉴权。",
                "script_strategy": "运行时注入。",
                "evidence": "application.yml:1 | config.sample.api.secret",
            }
        ],
        issues,
    )

    assert any(
        issue["code"] == "SECRET_CONFIG_REF_FIELD_MISSING" and "secret_ref" in issue["message"]
        for issue in issues
    )


def test_quality_check_rejects_path_bucket_business_scenario_map(tmp_path):
    from quality_check_source_facts import check_business_scenario_map

    out_dir = tmp_path / "docs" / "source-facts"
    out_dir.mkdir(parents=True)
    (out_dir / "business_scenario_map.yaml").write_text(
        """schema_version: 1
stage: business_scenario_mapping
status: passed
next_stage_allowed: true
source_entry: source
scenario_source_status: source_inferred
scenario_items:
  - scenario_id: BS-SRC-CHAIN-001
    scenario_name: api/v1 资源从业务处理到结果校验的接口链路
    business_description: 用户围绕 api/v1 业务资源依次调用多个接口，通过前序业务处理结果驱动后续查询或状态校验
    related_test_point_ids: [TP-001]
    related_coverage_rule_ids: [RULE-001]
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
blocking_issues: []
""",
        encoding="utf-8",
    )
    issues: list[dict[str, str]] = []

    check_business_scenario_map(out_dir, issues)

    assert any(issue["code"] == "BUSINESS_SCENARIO_PATH_BUCKET" for issue in issues)


def test_quality_check_rejects_single_interface_only_when_cluster_can_split(tmp_path):
    from quality_check_source_facts import check_business_scenario_map

    out_dir = tmp_path / "docs" / "source-facts"
    out_dir.mkdir(parents=True)
    (out_dir / "business_scenario_map.yaml").write_text(
        """schema_version: 1
stage: business_scenario_mapping
status: passed
next_stage_allowed: true
source_entry: source
scenario_source_status: source_inferred
scenario_items:
  - scenario_id: BS-ORDER-001
    scenario_name: 用户创建订单
    business_description: 用户创建订单，系统生成订单记录
    related_interfaces:
      - POST /api/v1/order/create
    related_test_point_ids: [TP-ORDER-001]
    related_coverage_rule_ids: [RULE-ORDER-001]
    chain_type: single_interface
    flow_generation_required: false
  - scenario_id: BS-ORDER-002
    scenario_name: 用户支付订单
    business_description: 用户支付订单，系统更新订单支付状态
    related_interfaces:
      - POST /api/v1/order/pay
    related_test_point_ids: [TP-ORDER-002]
    related_coverage_rule_ids: [RULE-ORDER-002]
    chain_type: single_interface
    flow_generation_required: false
  - scenario_id: BS-ORDER-003
    scenario_name: 用户查询订单详情
    business_description: 用户查询订单详情，确认订单状态和金额
    related_interfaces:
      - GET /api/v1/order/detail
    related_test_point_ids: [TP-ORDER-003]
    related_coverage_rule_ids: [RULE-ORDER-003]
    chain_type: single_interface
    flow_generation_required: false
blocking_issues: []
""",
        encoding="utf-8",
    )
    issues: list[dict[str, str]] = []

    check_business_scenario_map(out_dir, issues)

    assert any(issue["code"] == "BUSINESS_SCENARIO_SPLIT_REQUIRED" for issue in issues)


def test_quality_check_parses_multiline_signature_with_parameter_annotation():
    from quality_check_source_facts import parse_method_name

    signature = (
        'public ResponseEntity<String> nimCallBack(@RequestBody String body, '
        '@RequestHeader(value = "type", required = false) String type) {'
    )

    assert parse_method_name(signature) == "nimCallBack"


def copy_sample_with_feign(tmp_path: Path) -> Path:
    project = tmp_path / "sample-with-feign"
    shutil.copytree(SAMPLE_PROJECT, project)
    client_dir = project / "src" / "main" / "java" / "com" / "example" / "client"
    client_dir.mkdir(parents=True)
    (client_dir / "AccountClient.java").write_text(
        """
package com.example.client;

import com.example.dto.CreateAccountRequest;
import com.example.vo.AccountResponse;
import com.example.vo.BaseResult;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;

@FeignClient(name = "account", path = "/internal/accounts")
public interface AccountClient {
    @PostMapping("/sync")
    BaseResult<AccountResponse> syncAccount(@RequestBody CreateAccountRequest request);
}
""".lstrip(),
        encoding="utf-8",
    )
    return project
