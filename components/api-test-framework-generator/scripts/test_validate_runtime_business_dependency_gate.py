#!/usr/bin/env python3
"""专项测试运行时业务依赖脚本物化门禁。"""

from __future__ import annotations

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT_PATH = Path(__file__).with_name("validate_runtime_business_dependency_gate.py")
SPEC = importlib.util.spec_from_file_location("validate_runtime_business_dependency_gate", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def _dependency(mode: str = "api_query", decision: str = "runnable") -> dict:
    precheck = {"mode": mode, "executable_ref": "PRE-RBD-001", "changes_state": False}
    if mode == "non_live":
        precheck = {"mode": "non_live", "blocking_reason": "环境无法安全构造"}
    return {
        "dependency_id": "RBD-001",
        "case_id": "CASE-001",
        "dependency_type": "mutable_eligibility_state",
        "request_paths": ["$.body.creatorUserId"],
        "required_predicates": {"eligible": True},
        "source_refs": ["contract#eligibility"],
        "automation_decision": decision,
        "precheck": precheck,
    }


class RuntimeBusinessDependencyGateTest(unittest.TestCase):
    def _project(self, audit: dict | None, case: dict | None = None, sql_case: bool = False) -> Path:
        root = Path(tempfile.mkdtemp(prefix="runtime-business-materialization-"))
        self.addCleanup(lambda: shutil.rmtree(root))
        (root / "configs").mkdir(parents=True)
        (root / "data" / "cases").mkdir(parents=True)
        if audit is not None:
            (root / MODULE.AUDIT_FILE).write_text(
                yaml.safe_dump(audit, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )
        case_value = case or {"case_id": "CASE-001", "steps": []}
        (root / "data" / "cases" / "cases.yaml").write_text(
            yaml.safe_dump({"schema_version": 1, "cases": [case_value]}, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        if sql_case:
            (root / "data" / "case_sql_commands.yaml").write_text(
                yaml.safe_dump({"cases": {"CASE-001": {"precheck": []}}}, sort_keys=False), encoding="utf-8"
            )
        return root

    def _audit(self, item: dict | None) -> dict:
        return {
            "status": "passed" if item else "not_required",
            "scanned_case_ids": ["CASE-001"],
            "dependency_items": [item] if item else [],
            "unresolved_candidate_case_ids": [],
        }

    def test_audit_file_is_required(self) -> None:
        report = MODULE.validate_project(self._project(None))
        self.assertEqual("failed", report["status"])

    def test_not_required_passes_for_pure_api_case(self) -> None:
        report = MODULE.validate_project(self._project(self._audit(None)))
        self.assertEqual("not_required", report["status"])

    def test_scan_scope_must_cover_all_generated_cases(self) -> None:
        audit = self._audit(None)
        audit["scanned_case_ids"] = []
        report = MODULE.validate_project(self._project(audit))
        self.assertEqual("failed", report["status"])

    def test_dependency_must_be_copied_to_case(self) -> None:
        item = _dependency()
        report = MODULE.validate_project(self._project(self._audit(item)))
        self.assertTrue(any("未物化" in error for error in report["errors"]))

    def test_api_precheck_materialization_passes(self) -> None:
        item = _dependency()
        case = {"case_id": "CASE-001", "preconditions": [{"name": "资格查询"}], "runtime_business_dependencies": [item]}
        report = MODULE.validate_project(self._project(self._audit(item), case))
        self.assertEqual("passed", report["status"])

    def test_sql_precheck_materialization_passes(self) -> None:
        item = _dependency(mode="sql_query")
        case = {"case_id": "CASE-001", "runtime_business_dependencies": [item]}
        report = MODULE.validate_project(self._project(self._audit(item), case, sql_case=True))
        self.assertEqual("passed", report["status"])

    def test_fixture_precheck_without_fixture_fails(self) -> None:
        item = _dependency(mode="fixture_assertion")
        case = {"case_id": "CASE-001", "runtime_business_dependencies": [item]}
        report = MODULE.validate_project(self._project(self._audit(item), case))
        self.assertTrue(any("未物化" in error for error in report["errors"]))

    def test_state_change_requires_restore_and_cleanup(self) -> None:
        item = _dependency()
        item["precheck"]["changes_state"] = True
        case = {"case_id": "CASE-001", "preconditions": [{"name": "构造资格"}], "runtime_business_dependencies": [item]}
        report = MODULE.validate_project(self._project(self._audit(item), case))
        self.assertTrue(any("restore_ref" in error for error in report["errors"]))
        self.assertTrue(any("清理/恢复" in error for error in report["errors"]))

    def test_non_live_dependency_is_not_forced_into_live_denominator(self) -> None:
        item = _dependency(mode="non_live", decision="generated_non_live")
        case = {
            "case_id": "CASE-001",
            "live_pytest_release_ready": False,
            "automation_decision": "generated_non_live",
            "runtime_business_dependencies": [item],
        }
        report = MODULE.validate_project(self._project(self._audit(item), case))
        self.assertEqual("passed", report["status"])

    def test_audit_and_case_predicates_must_match(self) -> None:
        item = _dependency()
        generated = _dependency()
        generated["required_predicates"] = {"eligible": False}
        case = {"case_id": "CASE-001", "preconditions": [{"name": "资格查询"}], "runtime_business_dependencies": [generated]}
        report = MODULE.validate_project(self._project(self._audit(item), case))
        self.assertTrue(any("required_predicates" in error for error in report["errors"]))

    def test_unknown_extension_fields_are_allowed(self) -> None:
        item = _dependency()
        item["extension"] = {"owner": "qa"}
        case = {"case_id": "CASE-001", "preconditions": [{"name": "资格查询"}], "runtime_business_dependencies": [item], "extension": True}
        audit = self._audit(item)
        audit["extension"] = True
        report = MODULE.validate_project(self._project(audit, case))
        self.assertEqual("passed", report["status"])


if __name__ == "__main__":
    unittest.main()
