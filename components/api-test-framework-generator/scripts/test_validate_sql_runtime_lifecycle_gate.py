#!/usr/bin/env python3
"""专项验证 SQL 运行生命周期门禁的正例、反例和泛化边界。"""

from __future__ import annotations

import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

# 允许从 Skill 根目录或 scripts 目录启动同一组专项测试。
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_sql_runtime_lifecycle_gate import CHECK_RULES, validate_audit


def build_audit(**capability_overrides: bool) -> dict:
    capabilities = {
        "sql_runtime_stages": False,
        "sql_runtime_preflight": False,
        "preflight_consumes_runtime_variables": False,
        "explicit_subset_selection": False,
        "dynamic_database_expectations": False,
    }
    capabilities.update(capability_overrides)
    checks = {}
    applicable_count = 0
    for name, applies_when in CHECK_RULES.items():
        if applies_when(capabilities):
            applicable_count += 1
            checks[name] = {"status": "passed", "evidence": [f"test:{name}"]}
        else:
            checks[name] = {"status": "not_applicable", "reason": "当前架构未启用对应能力"}
    return {
        "schema_version": 1,
        "status": "passed" if applicable_count else "not_applicable",
        "capabilities": capabilities,
        "checks": checks,
        "blocking_issues": [],
    }


class SqlRuntimeLifecycleGateTest(unittest.TestCase):
    def test_pure_api_is_not_applicable(self) -> None:
        self.assertEqual(validate_audit(build_audit()), [])

    def test_basic_setup_cleanup_is_not_over_gated(self) -> None:
        audit = build_audit(sql_runtime_preflight=True)
        self.assertEqual(validate_audit(audit), [])
        self.assertEqual(audit["status"], "not_applicable")

    def test_fixture_snapshot_architecture_keeps_unrelated_checks_optional(self) -> None:
        audit = build_audit(
            sql_runtime_stages=True,
            sql_runtime_preflight=True,
            dynamic_database_expectations=True,
        )
        self.assertEqual(validate_audit(audit), [])
        self.assertEqual(audit["checks"]["phase_isolation"]["status"], "passed")
        self.assertEqual(audit["checks"]["runtime_context_parity"]["status"], "not_applicable")
        self.assertEqual(audit["checks"]["selection_closure"]["status"], "not_applicable")
        self.assertEqual(audit["checks"]["dynamic_baseline_source"]["status"], "passed")

    def test_full_sql_lifecycle_contract_passes(self) -> None:
        self.assertEqual(
            validate_audit(build_audit(**{name: True for name in build_audit()["capabilities"]})),
            [],
        )

    def test_phase_inversion_is_rejected(self) -> None:
        audit = build_audit(sql_runtime_stages=True, sql_runtime_preflight=True)
        audit["checks"]["phase_isolation"] = {"status": "failed", "evidence": ["API 前断言 API 后结果"]}
        self.assertTrue(any("phase_isolation" in error for error in validate_audit(audit)))

    def test_unresolved_context_contract_is_rejected(self) -> None:
        audit = build_audit(
            sql_runtime_preflight=True,
            preflight_consumes_runtime_variables=True,
        )
        audit["checks"]["runtime_context_parity"] = {"status": "passed", "evidence": []}
        self.assertTrue(any("runtime_context_parity" in error for error in validate_audit(audit)))

    def test_subset_without_selection_closure_is_rejected(self) -> None:
        audit = build_audit(sql_runtime_preflight=True, explicit_subset_selection=True)
        audit["checks"]["selection_closure"]["status"] = "not_applicable"
        self.assertTrue(any("selection_closure" in error for error in validate_audit(audit)))

    def test_subset_cannot_claim_full_evidence_without_scope_test(self) -> None:
        audit = build_audit(sql_runtime_preflight=True, explicit_subset_selection=True)
        audit["checks"]["validation_evidence_scope"] = {"status": "passed", "evidence": []}
        self.assertTrue(any("validation_evidence_scope" in error for error in validate_audit(audit)))

    def test_frozen_dynamic_baseline_is_rejected(self) -> None:
        audit = build_audit(dynamic_database_expectations=True)
        audit["checks"]["dynamic_baseline_source"] = {"status": "failed", "evidence": ["固定 None"]}
        self.assertTrue(any("dynamic_baseline_source" in error for error in validate_audit(audit)))

    def test_unknown_extension_fields_are_allowed(self) -> None:
        audit = build_audit()
        audit["capabilities"]["fixture_snapshot_restore"] = True
        audit["checks"]["future_architecture_check"] = {"status": "passed", "evidence": ["future"]}
        self.assertEqual(validate_audit(audit), [])

    def test_missing_capability_is_rejected(self) -> None:
        audit = build_audit()
        del audit["capabilities"]["sql_runtime_stages"]
        self.assertTrue(any("sql_runtime_stages" in error for error in validate_audit(audit)))

    def test_cli_returns_zero_for_pass_and_one_for_failure(self) -> None:
        validator_path = Path(__file__).with_name("validate_sql_runtime_lifecycle_gate.py")
        with tempfile.TemporaryDirectory() as directory:
            audit_path = Path(directory) / "gate.yaml"
            audit = build_audit(sql_runtime_stages=True, sql_runtime_preflight=True)
            audit_path.write_text(yaml.safe_dump(audit, allow_unicode=True), encoding="utf-8")
            passed = subprocess.run(
                [sys.executable, str(validator_path), str(audit_path)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)

            audit["checks"]["phase_isolation"]["evidence"] = []
            audit_path.write_text(yaml.safe_dump(audit, allow_unicode=True), encoding="utf-8")
            failed = subprocess.run(
                [sys.executable, str(validator_path), str(audit_path)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(failed.returncode, 1, failed.stdout + failed.stderr)


if __name__ == "__main__":
    unittest.main()
