#!/usr/bin/env python3
"""专项测试执行级可变运行时业务依赖门禁。"""

from __future__ import annotations

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT_PATH = Path(__file__).with_name("validate_runtime_business_dependencies.py")
SPEC = importlib.util.spec_from_file_location("validate_runtime_business_dependencies", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def _valid_dependency() -> dict:
    return {
        "dependency_id": "RBD-001",
        "case_id": "CASE-001",
        "dependency_type": "mutable_eligibility_state",
        "request_paths": ["$.body.creatorUserId"],
        "required_predicates": {"eligible": True, "status": 1},
        "source_refs": ["接口契约.md#creatorPriority"],
        "automation_decision": "runnable",
        "precheck": {
            "mode": "api_query",
            "executable_ref": "前置数据构造规则.md#PRE-RBD-001",
            "changes_state": False,
        },
    }


class RuntimeBusinessDependencyTest(unittest.TestCase):
    def _output(self, audit: dict | None, status: str = "passed", case_ids: tuple[str, ...] = ("CASE-001",)) -> Path:
        root = Path(tempfile.mkdtemp(prefix="runtime-business-dependency-"))
        self.addCleanup(lambda: shutil.rmtree(root))
        (root / "stage_status.yaml").write_text(
            yaml.safe_dump({"status": status}, allow_unicode=True), encoding="utf-8"
        )
        facts = {"schema_version": 1, "fact_sources": []}
        if audit is not None:
            facts["runtime_business_dependency_audit"] = audit
        (root / "execution_fact_sources.yaml").write_text(
            yaml.safe_dump(facts, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        cases = [{"用例ID": case_id} for case_id in case_ids]
        (root / "执行级接口用例集.md").write_text(
            "## 执行级接口用例集\n\n```yaml\n"
            + yaml.safe_dump(cases, allow_unicode=True, sort_keys=False).rstrip()
            + "\n```\n",
            encoding="utf-8",
        )
        return root

    def test_non_passed_stage_does_not_require_audit(self) -> None:
        self.assertEqual([], MODULE.validate_runtime_business_dependencies(self._output(None, status="blocked")))

    def test_passed_stage_requires_audit(self) -> None:
        errors = MODULE.validate_runtime_business_dependencies(self._output(None))
        self.assertIn("缺少", errors[0])

    def test_not_required_audit_passes_after_full_scan(self) -> None:
        audit = {"status": "not_required", "scanned_case_ids": ["CASE-001"], "dependency_items": [], "unresolved_candidate_case_ids": []}
        self.assertEqual([], MODULE.validate_runtime_business_dependencies(self._output(audit)))

    def test_scan_scope_must_match_all_cases(self) -> None:
        audit = {"status": "not_required", "scanned_case_ids": [], "dependency_items": [], "unresolved_candidate_case_ids": []}
        errors = MODULE.validate_runtime_business_dependencies(self._output(audit))
        self.assertTrue(any("精确一致" in error for error in errors))

    def test_valid_runnable_dependency_passes(self) -> None:
        audit = {"status": "passed", "scanned_case_ids": ["CASE-001"], "dependency_items": [_valid_dependency()], "unresolved_candidate_case_ids": []}
        self.assertEqual([], MODULE.validate_runtime_business_dependencies(self._output(audit)))

    def test_required_predicates_are_mandatory(self) -> None:
        dependency = _valid_dependency()
        dependency["required_predicates"] = {}
        audit = {"status": "passed", "scanned_case_ids": ["CASE-001"], "dependency_items": [dependency], "unresolved_candidate_case_ids": []}
        errors = MODULE.validate_runtime_business_dependencies(self._output(audit))
        self.assertTrue(any("required_predicates" in error for error in errors))

    def test_runnable_dependency_requires_executable_ref(self) -> None:
        dependency = _valid_dependency()
        dependency["precheck"].pop("executable_ref")
        audit = {"status": "passed", "scanned_case_ids": ["CASE-001"], "dependency_items": [dependency], "unresolved_candidate_case_ids": []}
        errors = MODULE.validate_runtime_business_dependencies(self._output(audit))
        self.assertTrue(any("executable_ref" in error for error in errors))

    def test_state_changing_precheck_requires_restore(self) -> None:
        dependency = _valid_dependency()
        dependency["precheck"]["changes_state"] = True
        audit = {"status": "passed", "scanned_case_ids": ["CASE-001"], "dependency_items": [dependency], "unresolved_candidate_case_ids": []}
        errors = MODULE.validate_runtime_business_dependencies(self._output(audit))
        self.assertTrue(any("restore_ref" in error for error in errors))

    def test_non_live_dependency_can_remain_traceable(self) -> None:
        dependency = _valid_dependency()
        dependency["automation_decision"] = "generated_non_live"
        dependency["precheck"] = {"mode": "non_live", "blocking_reason": "测试环境无法构造资格状态"}
        audit = {"status": "passed", "scanned_case_ids": ["CASE-001"], "dependency_items": [dependency], "unresolved_candidate_case_ids": []}
        self.assertEqual([], MODULE.validate_runtime_business_dependencies(self._output(audit)))

    def test_unresolved_candidates_block_passed_stage(self) -> None:
        audit = {"status": "not_required", "scanned_case_ids": ["CASE-001"], "dependency_items": [], "unresolved_candidate_case_ids": ["CASE-001"]}
        errors = MODULE.validate_runtime_business_dependencies(self._output(audit))
        self.assertTrue(any("必须为空" in error for error in errors))

    def test_unknown_extension_fields_are_allowed(self) -> None:
        dependency = _valid_dependency()
        dependency["extension"] = {"team": "qa"}
        audit = {"status": "passed", "scanned_case_ids": ["CASE-001"], "dependency_items": [dependency], "unresolved_candidate_case_ids": [], "extension": True}
        self.assertEqual([], MODULE.validate_runtime_business_dependencies(self._output(audit)))


if __name__ == "__main__":
    unittest.main()
