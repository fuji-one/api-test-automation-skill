#!/usr/bin/env python3
"""专项测试长链路运行语义门禁。"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT_PATH = Path(__file__).with_name("validate_flow_semantics_gate.py")
SPEC = importlib.util.spec_from_file_location("validate_flow_semantics_gate", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def _base_case(case_id: str = "CASE-QUERY") -> dict:
    return {
        "case_id": case_id,
        "steps": [{
            "request": {"body": {"id": 1, "pageIndex": 1, "pageSize": 20}},
            "expected": {
                "status_code": 200,
                "business_code": 200,
                "required_fields": ["$.code", "$.data.appName"],
                "json_type_equals": [{"path": "$.data", "type": "object"}],
            },
        }],
    }


class FlowSemanticsGateTest(unittest.TestCase):
    def _project(self, cases: list[dict], flows: list[dict] | None) -> Path:
        root = Path(tempfile.mkdtemp(prefix="flow-semantics-"))
        cases_dir = root / "data" / "cases"
        cases_dir.mkdir(parents=True)
        (cases_dir / "cases.yaml").write_text(
            yaml.safe_dump({"schema_version": 1, "cases": cases}, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        if flows is not None:
            (root / "data" / "flow_cases.yaml").write_text(
                yaml.safe_dump({"schema_version": 1, "flows": flows}, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
        self.addCleanup(lambda: __import__("shutil").rmtree(root))
        return root

    def test_no_flow_file_is_not_required(self) -> None:
        report = MODULE.validate_project(self._project([_base_case()], None))
        self.assertEqual("not_required", report["status"])

    def test_identity_override_cannot_inherit_business_assertions(self) -> None:
        flow = {"flow_id": "FLOW-1", "steps": [{
            "step_id": "detail",
            "source_executable_case_id": "CASE-QUERY",
            "request_overrides": {"body": {"id": 18}},
        }]}
        report = MODULE.validate_project(self._project([_base_case()], [flow]))
        self.assertEqual("failed", report["status"])
        self.assertIn("required_fields", report["errors"][0]["inherited_business_assertion_categories"])

    def test_all_business_assertion_categories_can_be_rebound(self) -> None:
        flow = {"flow_id": "FLOW-1", "steps": [{
            "step_id": "detail",
            "source_executable_case_id": "CASE-QUERY",
            "request_overrides": {"body": {"id": 18}},
            "expected_overrides": {"required_fields": ["$.code"], "json_type_equals": []},
        }]}
        report = MODULE.validate_project(self._project([_base_case()], [flow]))
        self.assertEqual("passed", report["status"])

    def test_source_bound_assertion_binding_can_pass(self) -> None:
        flow = {"flow_id": "FLOW-1", "steps": [{
            "step_id": "detail",
            "source_executable_case_id": "CASE-QUERY",
            "request_overrides": {"body": {"id": 18}},
            "assertion_binding": {
                "status": "passed",
                "mode": "same_request_variant_evidence",
                "evidence_refs": ["runtime_evidence.yaml#RT-1"],
            },
        }]}
        report = MODULE.validate_project(self._project([_base_case()], [flow]))
        self.assertEqual("passed", report["status"])

    def test_pagination_override_does_not_trigger_binding_gate(self) -> None:
        flow = {"flow_id": "FLOW-1", "steps": [{
            "step_id": "page",
            "source_executable_case_id": "CASE-QUERY",
            "request_overrides": {"body": {"pageIndex": 2}},
        }]}
        report = MODULE.validate_project(self._project([_base_case()], [flow]))
        self.assertEqual("not_required", report["status"])

    def test_unfiltered_write_followup_fails(self) -> None:
        producer = {"case_id": "CASE-WRITE", "steps": [{"request": {"body": {}}, "expected": {"required_fields": ["$.code"]}}]}
        flow = {"flow_id": "FLOW-1", "steps": [
            {"step_id": "create", "source_executable_case_id": "CASE-WRITE", "sql_runtime_extract": True, "producer_fields": ["record_id"]},
            {"step_id": "verify", "source_executable_case_id": "CASE-QUERY", "consumer_fields": ["record_id"], "expected_overrides": {
                "json_contains": [{"path": "$.data.records", "match": {"id": "${record_id}", "tagValue": "activeUser2026"}}],
            }},
        ]}
        report = MODULE.validate_project(self._project([_base_case(), producer], [flow]))
        self.assertEqual("failed", report["status"])
        self.assertEqual("bounded_write_followup_observation", report["errors"][0]["check_id"])

    def test_runtime_id_filter_passes(self) -> None:
        case = _base_case()
        case["steps"][0]["request"] = {"body": {"id": "${record_id}"}}
        producer = {"case_id": "CASE-WRITE", "steps": [{"request": {"body": {}}, "expected": {"required_fields": ["$.code"]}}]}
        flow = {"flow_id": "FLOW-1", "steps": [
            {"step_id": "create", "source_executable_case_id": "CASE-WRITE", "producer_fields": ["record_id"]},
            {"step_id": "verify", "source_executable_case_id": "CASE-QUERY", "consumer_fields": ["record_id"], "expected_overrides": {
                "json_contains": [{"path": "$.data.records", "match": {"id": "${record_id}"}}],
            }},
        ]}
        report = MODULE.validate_project(self._project([case, producer], [flow]))
        self.assertEqual("passed", report["status"])

    def test_literal_unique_filter_passes(self) -> None:
        case = _base_case()
        case["steps"][0]["request"] = {"body": {"strategyName": "current-run-name", "pageIndex": 1}}
        producer = {"case_id": "CASE-WRITE", "steps": [{"request": {"body": {}}, "expected": {"required_fields": ["$.code"]}}]}
        flow = {"flow_id": "FLOW-1", "steps": [
            {"step_id": "create", "source_executable_case_id": "CASE-WRITE", "producer_fields": ["record_id"]},
            {"step_id": "verify", "source_executable_case_id": "CASE-QUERY", "consumer_fields": ["record_id"], "expected_overrides": {
                "json_contains": [{"path": "$.data.records", "match": {"id": "${record_id}", "strategyName": "current-run-name"}}],
            }},
        ]}
        report = MODULE.validate_project(self._project([case, producer], [flow]))
        self.assertEqual("passed", report["status"])

    def test_status_filter_alone_is_not_ownership_scope(self) -> None:
        case = _base_case()
        case["steps"][0]["request"] = {"body": {"status": 1, "pageSize": 20}}
        producer = {"case_id": "CASE-WRITE", "steps": [{"request": {"body": {}}, "expected": {"required_fields": ["$.code"]}}]}
        flow = {"flow_id": "FLOW-1", "steps": [
            {"step_id": "create", "source_executable_case_id": "CASE-WRITE", "producer_fields": ["record_id"]},
            {"step_id": "verify", "source_executable_case_id": "CASE-QUERY", "consumer_fields": ["record_id"], "expected_overrides": {
                "json_contains": [{"path": "$.data.records", "match": {"id": "${record_id}", "status": 1}}],
            }},
        ]}
        report = MODULE.validate_project(self._project([case, producer], [flow]))
        self.assertEqual("failed", report["status"])

    def test_explicit_bounded_pagination_requires_ownership_fields(self) -> None:
        producer = {"case_id": "CASE-WRITE", "steps": [{"request": {"body": {}}, "expected": {"required_fields": ["$.code"]}}]}
        flow = {"flow_id": "FLOW-1", "steps": [
            {"step_id": "create", "source_executable_case_id": "CASE-WRITE", "producer_fields": ["record_id"]},
            {"step_id": "verify", "source_executable_case_id": "CASE-QUERY", "consumer_fields": ["record_id"], "observation_binding": {
                "status": "passed", "mode": "bounded_pagination", "evidence_refs": ["contract#page"], "ownership_fields": ["record_id"],
            }, "expected_overrides": {"json_contains": [{"path": "$.data.records", "match": {"id": "${record_id}"}}]}},
        ]}
        report = MODULE.validate_project(self._project([_base_case(), producer], [flow]))
        self.assertEqual("passed", report["status"])

    def test_cli_writes_audit(self) -> None:
        root = self._project([_base_case()], [])
        output = root / "configs" / "flow_runtime_semantics_gate.json"
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(root), "--output", str(output)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(output.exists())
        self.assertIn('"status": "not_required"', output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
