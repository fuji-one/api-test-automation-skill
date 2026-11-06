from __future__ import annotations

import json


def test_render_docs_generates_markdown_and_json(output_root):
    source_facts = output_root / "docs" / "source-facts"
    expected = [
        "01_接口测试用例设计文档.md",
        "02_接口结构化契约清单.md",
        "03_skill执行报告.md",
        "stage_status.yaml",
        "coverage_matrix.yaml",
        "01-api-inventory.md",
        "02-api-contracts.md",
        "03-call-chain.md",
        "04-business-rules.md",
        "05-source-db-side-effects.md",
        "06-unknown-and-risk.md",
        "08-security-transform-facts.md",
        "source_api_fact_artifacts.yaml",
        "source-api-facts.json",
    ]
    for name in expected:
        assert (source_facts / name).exists(), name

    data = json.loads((source_facts / "source-api-facts.json").read_text(encoding="utf-8"))
    assert data["summary"]["api_count"] == 3


def test_render_docs_generates_downstream_ready_contract(output_root):
    source_facts = output_root / "docs" / "source-facts"
    design_doc = (source_facts / "01_接口测试用例设计文档.md").read_text(encoding="utf-8")
    contract_doc = (source_facts / "02_接口结构化契约清单.md").read_text(encoding="utf-8")
    stage_status = (source_facts / "stage_status.yaml").read_text(encoding="utf-8")
    coverage_matrix = (source_facts / "coverage_matrix.yaml").read_text(encoding="utf-8")
    business_scenario_map = (source_facts / "business_scenario_map.yaml").read_text(encoding="utf-8")
    artifact_manifest = (source_facts / "source_api_fact_artifacts.yaml").read_text(encoding="utf-8")

    assert "覆盖对象ID" in design_doc
    assert "追溯测试点" in design_doc
    assert "覆盖规则ID" in design_doc
    assert "HTTP_200" in contract_doc
    assert "状态码与错误码" in contract_doc
    assert "加密签名与执行转换" in contract_doc
    assert "stage: source_api_facts" in stage_status
    assert "name: source_api_design_doc" in stage_status
    assert "name: source_api_contract_list" in stage_status
    assert "status: passed" in stage_status
    assert "coverage_rate: 100" in coverage_matrix
    assert "source_interface_total:" in coverage_matrix
    assert 'coverage_type: "source_interface"' in coverage_matrix
    assert 'coverage_type: "source_contract_rule"' in coverage_matrix
    assert "missing_source_scenario_ids: []" in coverage_matrix
    assert "business_domain:" in business_scenario_map
    assert "executing_role:" in business_scenario_map
    assert "用户通过" in business_scenario_map
    assert "artifact_name: \"source_api_design_doc\"" in artifact_manifest
    assert "artifact_name: \"source_api_security_transform_facts\"" in artifact_manifest


def test_render_docs_coverage_ids_are_rendered(output_root):
    import re

    source_facts = output_root / "docs" / "source-facts"
    coverage_matrix = (source_facts / "coverage_matrix.yaml").read_text(encoding="utf-8")
    rendered = (
        (source_facts / "01_接口测试用例设计文档.md").read_text(encoding="utf-8")
        + "\n"
        + (source_facts / "02_接口结构化契约清单.md").read_text(encoding="utf-8")
    )

    coverage_ids = set(re.findall(r'coverage_id: "([^"]+)"', coverage_matrix))
    assert coverage_ids
    assert not sorted(coverage_id for coverage_id in coverage_ids if coverage_id not in rendered)


def test_render_docs_includes_api_table_impact_summary(output_root):
    db_doc = (output_root / "docs" / "source-facts" / "05-source-db-side-effects.md").read_text(encoding="utf-8")

    assert "## 接口表影响汇总" in db_doc
    assert "| src:AccountController.create:POST:/api/accounts | 1 | 1 | 1 | account | account |" in db_doc


def test_chain_candidate_groups_use_semantic_resource_not_generic_prefix():
    from render_docs import api_resource_key, chain_candidate_groups

    facts = {
        "apis": [
            {
                "api_id": "API-LOGIN",
                "entry": {"http_method": "POST", "path": "/api/v1/user/login"},
            },
            {
                "api_id": "API-ORDER-CREATE",
                "entry": {"http_method": "POST", "path": "/api/v1/order/create"},
            },
            {
                "api_id": "API-ORDER-DETAIL",
                "entry": {"http_method": "GET", "path": "/api/v1/order/detail"},
            },
            {
                "api_id": "API-PROFILE",
                "entry": {"http_method": "GET", "path": "/api/v1/user/profile"},
            },
            {
                "api_id": "API-COMMON-PROFILE-UPDATE",
                "entry": {"http_method": "POST", "path": "/api/v1/common/profile/detail/update"},
            },
            {
                "api_id": "API-COMMON-PROFILE-DETAIL",
                "entry": {"http_method": "POST", "path": "/api/v1/common/profile/detail"},
            },
            {
                "api_id": "API-FEMALE-ONBOARD-STATUS",
                "entry": {"http_method": "POST", "path": "/api/v1/female/onboard/status"},
            },
            {
                "api_id": "API-FEMALE-ONBOARD-IDENTITY",
                "entry": {"http_method": "POST", "path": "/api/v1/female/onboard/step/identity"},
            },
        ]
    }

    keys = [api_resource_key(api) for api in facts["apis"]]
    groups = {key: [api["api_id"] for api in apis] for key, apis in chain_candidate_groups(facts)}

    assert keys == ["user", "order", "order", "user/profile", "common/profile", "common/profile", "female/onboard", "female/onboard"]
    assert "api/v1" not in groups
    assert "common" not in groups
    assert "female" not in groups
    assert groups["order"] == ["API-ORDER-CREATE", "API-ORDER-DETAIL"]
    assert "user" not in groups
    assert groups["common/profile"] == ["API-COMMON-PROFILE-DETAIL", "API-COMMON-PROFILE-UPDATE"]
    assert groups["female/onboard"] == ["API-FEMALE-ONBOARD-STATUS", "API-FEMALE-ONBOARD-IDENTITY"]


def test_render_docs_uses_explicit_empty_messages(output_root):
    from render_docs import render_business_rules

    docs_dir = output_root / "docs" / "source-facts"
    contract_doc = (docs_dir / "02-api-contracts.md").read_text(encoding="utf-8")
    db_doc = (docs_dir / "05-source-db-side-effects.md").read_text(encoding="utf-8")
    no_rule_doc = render_business_rules({"apis": [{"api_id": "sample", "business_rules": []}]})

    assert "无响应字段。" in contract_doc
    assert "未发现源码可见业务规则。" in no_rule_doc
    assert "未发现源码可见 DB 访问或副作用。" in db_doc
    assert "| UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |" not in db_doc


def test_rendered_json_keeps_unknowns_only_at_api_or_project_level(output_root):
    facts_path = output_root / "docs" / "source-facts" / "source-api-facts.json"
    data = json.loads(facts_path.read_text(encoding="utf-8"))

    assert all("unknowns" not in api["contract"] for api in data["apis"])
