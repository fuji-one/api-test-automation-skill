#!/usr/bin/env python3
"""校验接口自动化流水线总控阶段产物。"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


ENTRY_DOCS = (
    "01_接口测试用例设计文档.md",
    "02_接口结构化契约清单.md",
    "03_skill执行报告.md",
)
STAGE_STATUSES = (
    "PASSED",
    "BLOCKED_MISSING_ENTRY_INPUT",
    "FAILED_ENTRY_QUALITY_GATE",
    "FAILED_ENTRY_ALIGNMENT_GATE",
    "BLOCKED_NEED_BUSINESS_SCENARIO_MAPPING",
    "BLOCKED_NEED_CHAIN_FLOW_DENOMINATOR",
    "FAILED_DESIGN_CASE_GATE",
    "BLOCKED_NEED_HANDOFF_REPAIR",
    "BLOCKED_NEED_EXECUTION_INPUT",
    "BLOCKED_NEED_CHAIN_FLOW_EVIDENCE",
    "FAILED_EXECUTION_READINESS",
    "FAILED_SCRIPT_GENERATION_GATE",
    "BLOCKED_RETRY_EXHAUSTED",
)
TARGET_DEPTHS = ("design", "executable", "framework")
FRAMEWORK_REQUIRED = (
    "configs",
    "data",
    "testcases",
    "api",
    "core",
    "utils",
    "conftest.py",
    "pytest.ini",
    "requirements.txt",
)
HANDOFF_REQUIRED = (
    "接口测试用例设计文档.md",
    "接口结构化契约清单.md",
    "case_list.yaml",
    "测试用例清单.md",
    "required_chain_flows.yaml",
    "chain_flow_candidate_audit.yaml",
    "business_scenario_map.yaml",
    "业务场景链路清单.md",
    "business_long_chain_cases.yaml",
    "业务长链路设计清单.md",
    "执行报告.md",
)
QUALITY_MARKER_GROUPS = {
    "质量结论": ("质检结论", "质量结论"),
    "覆盖结论": ("覆盖矩阵", "覆盖结论", "覆盖率准出摘要"),
    "阻塞项": ("阻塞项",),
    "修正建议": ("修正建议",),
    "准出结论": ("准出结论", "交付结论", "放行结论", "发布结论"),
}
DOC_ENTRY_REQUIRED_REPORT_SECTIONS = (
    "输入文档清单",
    "阶段执行结果",
    "二阶段测试点分析报告",
    "覆盖率准出摘要",
    "交付结论",
)
DOC_ENTRY_TEST_POINT_SECTIONS = (
    "需求-接口-状态三向追踪矩阵",
    "字段-规则-断言映射表",
    "错误码-异常场景映射表",
    "状态迁移-触发入口映射表",
    "依赖失败-补偿场景映射表",
    "覆盖率矩阵",
)
DOC_ENTRY_TRACE_MARKERS = ("覆盖对象ID", "覆盖规则ID", "追溯测试点")
SOURCE_FAILED_STATUS_VALUES = {"failed", "fail", "error", "不通过", "失败"}
SIDECAR_STATUS_VALUES = {"passed", "blocked", "failed", "coverage_insufficient"}
HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")
STATUS_DETAIL_KEYS = {"status", "status_code", "status_codes", "http_status", "http_status_code", "状态码", "响应状态码"}
ERROR_DETAIL_KEYS = {"error_code", "error_codes", "business_code", "business_codes", "错误码", "业务码"}
FIELD_DETAIL_KEYS = {
    "field",
    "fields",
    "request_field",
    "request_fields",
    "response_field",
    "response_fields",
    "字段",
    "请求字段",
    "响应字段",
}
REQUIRED_EXECUTION_FACT_TYPES = (
    "token_rule",
    "test_data_rule",
    "variable_link",
    "chain_flow",
    "assertion_rule",
    "cleanup_strategy",
)
DATABASE_EXECUTION_FACT_TYPES = ("relationship_graph", "ownership_key", "seed_scope_guard")
ACCOUNT_SPECIFIC_CHAIN_FACT_TYPE = "account_specific_chain"
LOGIN_ENTRY_FACT_TYPE = "login_entry_rule"
ACCOUNT_SPECIFIC_MARKER_KEYS = (
    "specific_account_required",
    "requires_specific_account",
    "account_specific",
    "required_account_role",
    "required_account_business_state",
    "required_tenant",
    "required_permission",
)
ACCOUNT_NOT_REQUIRED_VALUES = {
    "",
    "false",
    "no",
    "none",
    "null",
    "not_required",
    "not_required_or_none",
    "不需要",
    "无",
    "否",
}
LOGIN_STEP_TYPE_VALUES = {"login", "auth", "authentication", "authorization"}
REQUIRED_HUMAN_INPUTS = ("environment_reference", "authentication_account")
CONFIRMED_FACT_STATUS = "confirmed"
PRE_DOC_COVERAGE_PAIRS = (
    ("object_total", "object_covered"),
    ("test_point_total", "test_point_mapped"),
    ("rule_total", "rule_covered"),
)
PRE_DOC_MISSING_LISTS = ("missing_object_ids", "missing_test_point_ids", "missing_rule_ids")
SOURCE_COVERAGE_PAIRS = (
    ("source_interface_total", "source_interface_covered"),
    ("source_contract_rule_total", "source_contract_rule_covered"),
    ("source_business_rule_total", "source_business_rule_covered"),
    ("source_error_code_total", "source_error_code_covered"),
    ("source_db_side_effect_total", "source_db_side_effect_covered"),
    ("source_scenario_total", "source_scenario_covered"),
)
SOURCE_MISSING_LISTS = (
    "missing_source_interface_ids",
    "missing_source_contract_rule_ids",
    "missing_source_business_rule_ids",
    "missing_source_error_code_ids",
    "missing_source_db_side_effect_ids",
    "missing_source_scenario_ids",
)
INTERFACE_COVERAGE_PAIRS = (
    ("test_point_total", "test_point_covered"),
    ("main_flow_total", "main_flow_covered"),
    ("contract_rule_total", "contract_rule_covered"),
    ("status_code_total", "status_code_covered"),
    ("p0_p1_total", "p0_p1_covered"),
)
INTERFACE_MISSING_LISTS = (
    "missing_test_point_ids",
    "missing_main_flow_ids",
    "missing_contract_rule_ids",
    "missing_status_codes",
    "missing_p0_p1_ids",
)
EXECUTABLE_COVERAGE_PAIRS = (
    ("design_case_total", "design_case_mapped"),
    ("executable_case_total", "executable_case_traced"),
    ("coverage_rule_total", "coverage_rule_mapped"),
)
EXECUTABLE_MISSING_LISTS = (
    "missing_design_case_ids",
    "missing_executable_trace_ids",
    "missing_coverage_rule_ids",
)
CHAIN_COVERAGE_PAIRS = (
    ("chain_scenario_total", "chain_scenario_covered"),
    ("chain_function_total", "chain_function_covered"),
    ("chain_process_total", "chain_process_covered"),
)
CHAIN_COVERAGE_MISSING_LISTS = (
    "missing_chain_scenario_ids",
    "missing_chain_function_ids",
    "missing_chain_process_ids",
)
EXECUTION_FACT_SOURCE_REQUIRED_KEYS = (
    "schema_version",
    "stage",
    "status",
    "required_human_inputs",
    "fact_sources",
    "missing_required_facts",
    "conflict_facts",
    "blocking_issues",
)
APIFOX_EVIDENCE_REQUIRED_KEYS = (
    "schema_version",
    "stage",
    "status",
    "evidence_items",
    "conflict_items",
    "conflict_priority",
    "resolution_policy",
)
RUNTIME_EVIDENCE_REQUIRED_FILES = (
    "runtime_stage_status.yaml",
    "runtime_evidence.yaml",
    "runtime_value_catalog.yaml",
)
RUNTIME_EVIDENCE_QUEUE = "runtime_evidence_queue.yaml"
RUNTIME_QUEUE_STATE_VALUES = {"pending", "requested", "evidenced", "retryable", "skipped_recoverable", "blocked_final", "excluded"}
DATABASE_MCP_EVIDENCE_REQUIRED_KEYS = (
    "schema_version",
    "stage",
    "status",
    "mcp_connection",
    "evidence_items",
    "conflict_items",
    "blocking_issues",
)
DATABASE_MCP_REQUIRED_EVIDENCE_LEVELS = (
    "table_schema",
    "column_schema",
    "index_constraint",
    "relationship_graph",
    "cleanup_key",
    "ownership_boundary",
)
SOURCE_DB_ALIGNMENT_REQUIRED_CHECKS = (
    "datasource_identity",
    "table_mapping",
    "column_mapping",
    "key_constraint_mapping",
    "relationship_graph_mapping",
    "seed_cleanup_strategy",
    "side_effect_mapping",
)
RETRY_HISTORY_REQUIRED_KEYS = (
    "schema_version",
    "status",
    "max_attempts",
    "next_stage_allowed",
    "retry_key",
    "gate_id",
    "consumer_stage",
    "producer_stage",
    "final_blocker",
    "attempts",
)
RETRY_HISTORY_STATUSES = {"retrying", "resolved", "blocked"}
APIFOX_EVIDENCE_LEVELS = ("project_structure", "interface_contract", "saved_case_example", "response_example")
RUNTIME_EVIDENCE_DIR = "04-runtime-evidence"
RUNTIME_EVIDENCE_PLAN_DIR = "04-runtime-evidence-plan"
RUNTIME_RISK_AUDIT = "runtime_risk_audit.yaml"
RUNTIME_REQUEST_PLAN_SKELETON = "runtime_request_plan.skeleton.yaml"
DB_BEFORE_AFTER_PROBE_PLAN = "db_before_after_probe_plan.yaml"
RUNTIME_BLOCKER_CANDIDATES = "runtime_blocker_candidates.yaml"
RUNTIME_EVIDENCE_PLAN_REQUIRED_FILES = (
    RUNTIME_RISK_AUDIT,
    RUNTIME_REQUEST_PLAN_SKELETON,
    DB_BEFORE_AFTER_PROBE_PLAN,
    RUNTIME_BLOCKER_CANDIDATES,
)
RUNTIME_STAGE_STATUS = "runtime_stage_status.yaml"
RUNTIME_EVIDENCE = "runtime_evidence.yaml"
RUNTIME_VALUE_CATALOG = "runtime_value_catalog.yaml"
RUNTIME_STATUS_VALUES = {"passed", "partial", "blocked", "failed"}
RUNTIME_RISK_LEVELS = {
    "safe_readonly",
    "auth_setup",
    "mutation_requires_cleanup",
    "destructive_state",
    "external_or_callback",
    "unknown_requires_review",
}
RUNTIME_REQUEST_DECISIONS = {
    "request_allowed",
    "request_allowed_with_user_config",
    "manual_confirmation_required",
    "blocked_until_isolated_account_and_cleanup",
}
RUNTIME_PLAN_STATUS_VALUES = {
    "passed",
    "blocked",
    "failed",
    "ready",
    "not_required",
    "has_blockers",
    "ready_for_manual_completion",
    "blocked_no_allowed_request",
}
RUNTIME_RISK_AUDIT_REQUIRED_KEYS = (
    "schema_version",
    "stage",
    "status",
    "next_stage_allowed",
    "risk_summary",
    "request_decision_summary",
    "execution_authorization",
    "db_authorization",
    "classification_policy",
    "items",
)
RUNTIME_REQUEST_PLAN_SKELETON_REQUIRED_KEYS = (
    "schema_version",
    "stage",
    "status",
    "next_stage_allowed",
    "env",
    "request_scope",
    "steps",
)
DB_BEFORE_AFTER_PROBE_PLAN_REQUIRED_KEYS = (
    "schema_version",
    "stage",
    "status",
    "next_stage_allowed",
    "probe_policy",
    "probes",
)
RUNTIME_BLOCKER_CANDIDATES_REQUIRED_KEYS = (
    "schema_version",
    "stage",
    "status",
    "next_stage_allowed",
    "blocking_items",
)
RUNTIME_STAGE_STATUS_REQUIRED_KEYS = (
    "schema_version",
    "stage",
    "status",
    "next_stage_allowed",
    "request_scope",
    "input_paths",
    "output_paths",
    "gate_checks",
    "blocking_issues",
)
RUNTIME_EVIDENCE_REQUIRED_KEYS = (
    "schema_version",
    "stage",
    "status",
    "next_stage_allowed",
    "request_scope",
    "auth_evidence",
    "evidence_items",
    "conflict_items",
    "blocking_issues",
)
RUNTIME_VALUE_CATALOG_REQUIRED_KEYS = (
    "schema_version",
    "stage",
    "status",
    "values",
    "usable_fact_types",
    "missing_values",
    "conflict_values",
    "blocking_issues",
)
RUNTIME_ALLOWED_SOURCE_STATUS = {"confirmed", "missing", "conflict", "blocked"}
CASE_LIST_YAML_REQUIRED_KEYS = ("schema_version", "stage", "status", "quality_gate", "cases", "coverage_summary", "case_mappings", "blocking_issues")
CASE_LIST_YAML_REQUIRED_CASE_MARKERS = (
    "case_id",
    "design_case_id",
    "test_point_ids",
    "coverage_object_ids",
    "coverage_rule_ids",
    "method",
    "path",
    "status_codes",
    "priority",
    "assertion_points",
    "confidence_score",
    "confidence_level",
    "confidence_band",
    "confidence_scope",
    "scenario_relevance",
    "confidence_reason_codes",
    "confidence_cap_reasons",
    "confidence_evidence_refs",
)
CASE_LIST_YAML_REQUIRED_LIST_FIELDS = {
    "test_point_ids",
    "coverage_object_ids",
    "coverage_rule_ids",
    "status_codes",
    "assertion_points",
    "confidence_reason_codes",
    "confidence_evidence_refs",
}
CONFIDENCE_DIMENSION_WEIGHTS = {
    "contract": 0.25,
    "request_materialization": 0.20,
    "scenario_precondition": 0.20,
    "business_assertion": 0.20,
    "runtime_repeatability": 0.15,
}
CONFIDENCE_CAPS = {
    "SOURCE_CONFLICT_UNRESOLVED": 0.49,
    "CONTRACT_NOT_CONFIRMED": 0.59,
    "INPUT_NOT_CONFIRMED": 0.69,
    "SCENARIO_STATE_NOT_CLOSED": 0.79,
    "ASSERTION_BUSINESS_RESULT_NOT_CLOSED": 0.79,
    "WRITE_CLEANUP_NOT_MATERIALIZED": 0.59,
    "EXTERNAL_DEPENDENCY_SANDBOX_MISSING": 0.69,
    "RUNTIME_NOT_VERIFIED": 0.89,
}
CONFIDENCE_SCOPES = {"design", "executable", "framework", "design_and_execution"}
CONFIDENCE_SCENARIO_RELEVANCE = {
    "core_real_journey",
    "reachable_business_branch",
    "contract_boundary",
    "synthetic_resilience",
    "source_inferred_only",
}
CONFIDENCE_NON_LIVE_DECISIONS = {
    "generated_non_live",
    "manual_review_only",
    "blocked_live_execution",
    "non_live",
}
EXECUTABLE_CONFIDENCE_FIELD_MAP = {
    "confidence_score": "置信度分数",
    "confidence_level": "置信度等级",
    "confidence_band": "置信度区间",
    "confidence_scope": "置信度范围",
    "scenario_relevance": "场景相关性",
    "confidence_dimensions": "置信度维度",
    "confidence_reason_codes": "置信度原因码",
    "confidence_cap_reasons": "置信度硬上限原因",
    "confidence_evidence_refs": "置信度证据引用",
}
COVERAGE_POINT_REPORT = "测试覆盖点报告.md"
BUSINESS_SCENARIO_MAP = "business_scenario_map.yaml"
BUSINESS_SCENARIO_DOC = "业务场景链路清单.md"
BUSINESS_LONG_CHAIN_CASES = "business_long_chain_cases.yaml"
BUSINESS_LONG_CHAIN_DOC = "业务长链路设计清单.md"
BUSINESS_CHAIN_CANDIDATE_INVENTORY = "business_chain_candidate_inventory.yaml"
REQUIRED_CHAIN_FLOWS = "required_chain_flows.yaml"
CHAIN_FLOW_CANDIDATE_AUDIT = "chain_flow_candidate_audit.yaml"
CHAIN_FLOW_ALIGNMENT = "chain_flow_alignment.yaml"
CHAIN_EXECUTION_READINESS_RECONCILIATION = "chain_execution_readiness_reconciliation.yaml"
CHAIN_READINESS_CAPABILITIES = {
    "write_restore",
    "read_only_verified",
    "create_delete_zero_residue",
    "isolated_ownership",
    "sandbox_mock_callback",
    "state_observation_verified",
}
KNOWN_CHAIN_EXECUTION_FACT_PATHS = (
    "04-runtime-evidence/runtime_stage_status.yaml",
    "04-runtime-evidence/runtime_evidence.yaml",
    "04-runtime-evidence/runtime_value_catalog.yaml",
    "00-inputs/execution-readiness/long_chain_missing_value_fields.yaml",
    "05-executable-interface-case-set/long_chain_missing_value_fields.yaml",
    "05-executable-interface-case-set/execution_fact_sources.yaml",
)
CHAIN_FLOW_ALLOWED_CANDIDATE_CLASSIFICATIONS = {
    "included",
    "design_long_chain_only",
    "design_short_chain_state_transition",
    "single_interface_mutation",
    "single_interface_readonly",
    "external_or_callback",
    "excluded_ready_by_policy",
    "excluded_missing_verification",
    "excluded_missing_change_evidence",
    "excluded_missing_link_key",
    "excluded_readonly",
}
BUSINESS_CHAIN_CANDIDATE_INVENTORY_TYPES = (
    "business_long_chain_ready",
    "business_long_chain_need_execution_evidence",
    "short_state_transition",
    "single_interface_mutation",
    "readonly",
    "external_or_callback",
    "missing_evidence_candidate",
)
BUSINESS_CHAIN_INVENTORY_TYPE_BY_CLASSIFICATION = {
    "included": "business_long_chain_ready",
    "design_long_chain_only": "business_long_chain_need_execution_evidence",
    "design_short_chain_state_transition": "short_state_transition",
    "single_interface_mutation": "single_interface_mutation",
    "single_interface_readonly": "readonly",
    "external_or_callback": "external_or_callback",
    "excluded_ready_by_policy": "business_long_chain_ready",
    "excluded_missing_verification": "missing_evidence_candidate",
    "excluded_missing_change_evidence": "missing_evidence_candidate",
    "excluded_missing_link_key": "missing_evidence_candidate",
    "excluded_readonly": "readonly",
}
COVERAGE_POINT_SUMMARY_TITLE = "覆盖点摘要"
COVERAGE_POINT_HEADERS = ("ID", "测试点", "业务域", "业务场景", "来源", "接口链路", "前置条件", "操作步骤", "预期结果", "优先级", "用例类型")
COVERAGE_POINT_CHINESE_FIELDS = ("测试点", "业务域", "业务场景", "前置条件", "操作步骤", "预期结果", "用例类型")
COVERAGE_POINT_PRIORITY_VALUES = {"p0", "p1", "p2"}
LONG_CHAIN_INTERFACE_THRESHOLD = 3
LONG_CHAIN_STEP_THRESHOLD = 5
COVERAGE_POINT_PLACEHOLDERS = {
    "",
    "-",
    "无",
    "暂无",
    "待确认",
    "待补充",
    "未知",
    "不详",
    "TBD",
    "tbd",
    "UNKNOWN",
    "unknown",
    "N/A",
    "n/a",
    "NA",
    "null",
    "None",
    "none",
}
BUSINESS_SCENARIO_REQUIRED_KEYS = (
    "schema_version",
    "stage",
    "status",
    "next_stage_allowed",
    "source_entry",
    "scenario_items",
    "blocking_issues",
)
BUSINESS_SCENARIO_REQUIRED_ITEM_MARKERS = (
    "scenario_id",
    "scenario_name",
    "business_domain",
    "executing_role",
    "business_description",
    "roles",
    "source_refs",
    "related_interfaces",
    "business_chain",
    "chain_type",
    "flow_generation_required",
    "related_test_point_ids",
    "related_coverage_rule_ids",
    "confidence",
    "blockers",
)
BUSINESS_LONG_CHAIN_REQUIRED_KEYS = (
    "schema_version",
    "stage",
    "status",
    "next_stage_allowed",
    "denominator_scope",
    "business_long_chain_total",
    "business_long_chain_covered",
    "script_closed_loop_ready_total",
    "missing_business_long_chain_ids",
    "chains",
    "blocking_issues",
)
BUSINESS_LONG_CHAIN_REQUIRED_ITEM_MARKERS = (
    "chain_id",
    "case_id",
    "priority",
    "business_domain",
    "scenario_name",
    "business_description",
    "executing_role",
    "chain_kind",
    "interface_count",
    "interfaces",
    "source_refs",
    "related_test_point_ids",
    "related_coverage_rule_ids",
    "design_status",
    "executable_status",
)
BUSINESS_LONG_CHAIN_DENOMINATOR_SCOPE = "business_scenario_long_chain_design"
BUSINESS_LONG_CHAIN_STAGE = "business_long_chain_design_denominator"
BUSINESS_LONG_CHAIN_EXECUTABLE_STATUSES = {
    "closed_loop_required",
    "ready",
    "not_required",
    "need_execution_input",
    "manual_confirm_required",
    "blocked_missing_execution_input",
}
BUSINESS_LONG_CHAIN_PATH_BUCKET_PATTERNS = (
    re.compile(r"\b(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b\s*/", re.IGNORECASE),
    re.compile(r"/(?:api|app|admin|internal|openapi|v\d+)(?:/|$)", re.IGNORECASE),
    re.compile(r"(?:接口|路径|URL|uri|controller|模块|包名|前缀).{0,16}(?:聚合|分组|串联|穷举)", re.IGNORECASE),
    re.compile(r"(?:调用|创建|查询|更新|删除).{0,8}接口(?:正向|反向|异常|边界)?测试", re.IGNORECASE),
    re.compile(r"(?:api/v\d+|/app|/internal).{0,20}(?:资源|接口|路径|前缀).{0,20}(?:链路|校验|测试)", re.IGNORECASE),
    re.compile(r"(?:资源|接口集合|接口组合|模块接口).{0,20}(?:业务处理到结果校验|接口链路|链路)", re.IGNORECASE),
)
HTTP_INTERFACE_RE = re.compile(r"\b(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(/[^\s，,；;]+)", re.IGNORECASE)
MUTATING_INTERFACE_RE = re.compile(r"\b(?:POST|PUT|PATCH|DELETE)\s+/", re.IGNORECASE)
READ_VERIFY_RE = re.compile(r"(?:\b(?:GET|HEAD|OPTIONS)\s+/|查询|列表|详情|状态|读取|统计|verify|check|get|list|detail|status)", re.IGNORECASE)
GENERIC_ROUTE_SEGMENTS = {
    "api",
    "app",
    "admin",
    "internal",
    "openapi",
    "v1",
    "v2",
    "v3",
}
ACTION_ROUTE_SEGMENTS = {
    "create",
    "add",
    "update",
    "delete",
    "remove",
    "get",
    "list",
    "detail",
    "query",
    "status",
    "check",
    "submit",
    "send",
    "callback",
    "verify",
    "read",
    "pay",
    "cancel",
    "confirm",
    "approve",
    "reject",
    "upload",
    "bind",
    "unbind",
    "apply",
    "publish",
    "recharge",
    "withdraw",
    "login",
    "logout",
}
BUSINESS_CHAIN_CANDIDATE_INVENTORY_REQUIRED_KEYS = (
    "schema_version",
    "stage",
    "status",
    "next_stage_allowed",
    "candidate_total",
    "candidate_type_summary",
    "items",
    "blocking_issues",
)
REQUIRED_CHAIN_FLOW_REQUIRED_KEYS = (
    "schema_version",
    "stage",
    "status",
    "next_stage_allowed",
    "required_chain_flow_count",
    "flows",
    "unclassified_candidate_flows",
    "blocking_issues",
)
CHAIN_FLOW_AUDIT_REQUIRED_KEYS = (
    "schema_version",
    "stage",
    "status",
    "next_stage_allowed",
    "candidate_summary",
    "candidates",
    "unclassified_candidate_flows",
    "blocking_issues",
)
CHAIN_FLOW_ALIGNMENT_REQUIRED_KEYS = (
    "schema_version",
    "stage",
    "status",
    "alignment_items",
    "blocking_issues",
)
DATA_MODEL_REQUIRED = ("00-inputs", "数据模型.md")
DATABASE_MCP_EVIDENCE_REQUIRED = ("00-inputs", "database_mcp_evidence_index.yaml")
SOURCE_DB_ALIGNMENT_REQUIRED = ("00-inputs", "source_db_alignment.yaml")
SOURCE_DB_ALIGNMENT_REPORT_REQUIRED = ("00-inputs", "source_db_alignment_report.md")
RUNTIME_EXECUTION_CONFIG_TEMPLATE_REQUIRED = ("00-inputs", "runtime_execution_config.template.yaml")
RUNTIME_EXECUTION_CONFIG_GUIDE_REQUIRED = ("00-inputs", "前置执行配置待填写.md")
RUNTIME_EXECUTION_CONFIG_MISSING_FIELDS = ("00-inputs", "runtime_execution_config.missing_fields.yaml")
FRAMEWORK_CONFIG_REQUIRED = ("input_precheck_report.yaml", "generation_status.yaml")
CASE_DENOMINATOR_VALIDATOR = (
    Path(__file__).resolve().parents[1]
    / "components"
    / "api-test-framework-generator"
    / "scripts"
    / "validate_case_denominator_conservation.py"
)
DATA_DRIVEN_INTERFACE_FILES = (
    Path("data") / "interfaces.yaml",
    Path("data") / "interfaces.py",
)
DATA_DRIVEN_CASE_DIR = Path("data") / "cases"
DATA_DRIVEN_FLOW_FILES = (
    Path("data") / "flow_cases.yaml",
    Path("data") / "flow_cases.py",
)
EXECUTABLE_SHARD_INDEX_FILE = "执行级用例分片索引.md"
EXECUTABLE_SHARD_DIR = "执行级用例分片"
PY_DATA_COMMON_EXPORTS = {"SCHEMA_VERSION", "schema_version"}
PY_DATA_EXPORTS_BY_KIND = {
    "interfaces": {"INTERFACES", "interfaces"},
    "cases": {"CASES", "cases"},
    "flows": {"FLOWS", "flows"},
}
SECTION_HEADING_RE = re.compile(r"^##+\s+(.+?)\s*$", re.MULTILINE)
COVERAGE_BLOCKING_TERMS = ("覆盖不足", "未覆盖", "待补充", "阻塞")
CONCLUSION_BLOCKING_TERMS = ("覆盖不足", "阻塞", "不通过")
NONE_MARKERS = ("无", "暂无", "不涉及", "无阻塞", "无未关闭", "已关闭")
DATA_MODEL_EXECUTION_MARKER_GROUPS = {
    "表结构": ("表结构", "表名", "字段", "columns", "column"),
    "关系图": ("关系图", "表关系", "父子关系", "relationship", "graph"),
    "铺数顺序": ("铺数顺序", "构造顺序", "setup order", "setup_order"),
    "清理逆序": ("清理逆序", "清理顺序", "cleanup order", "cleanup_order"),
    "归属键": ("归属键", "ownership key", "ownership_key"),
    "清理边界": ("清理边界", "cleanup boundary", "cleanup_boundary"),
}
DATA_MODEL_MISSING_CONTENT_MARKERS = (
    "缺失",
    "未提供",
    "没有",
    "待提供",
    "待补充",
    "待确认",
    "未知",
    "不详",
    "暂无",
    "todo",
    "tbd",
    "unknown",
    "n/a",
    "none",
    "null",
)
SOURCE_ARTIFACT_REQUIRED_NAMES = (
    "source_api_design_doc",
    "source_api_contract_list",
    "source_api_stage_report",
    "source_api_business_scenario_map",
    "source_api_business_scenario_doc",
    "source_api_stage_status",
    "source_api_coverage_matrix",
    "source_api_fact_json",
    "source_api_fact_artifact_manifest",
)
DENY_PATTERNS = (
    re.compile(r"是否允许[^：:\n]*(?:100%|覆盖|进入下一阶段)[^：:\n]*[：:]\s*否"),
    re.compile(r"是否进入生成阶段[^：:\n]*[：:]\s*否"),
    re.compile(r"不允许声明"),
    re.compile(r"不允许进入"),
)
ALLOW_100_PATTERN = re.compile(r"是否允许[^：:\n]*(?:100%|覆盖)[^：:\n]*[：:]\s*是")
EXECUTABLE_TRACE_FIELDS = ("用例ID", "设计级用例ID", "覆盖对象ID", "覆盖规则ID", "追溯测试点")
GENERATION_STATUS_FIELDS = (
    "coverage_traceability",
    "pytest_collection_mapping",
    "chain_script_coverage",
    "pytest_nodeid",
    "executable_case_count",
    "collected_test_count",
)
RATIO_PATTERN = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)(?![\d.])")
PERCENT_PATTERN = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*%")
YAML_SCALAR_RE = re.compile(r"^\s*(?:-\s*)?([A-Za-z0-9_]+)\s*:\s*(.*?)\s*$")
YAML_TOP_LEVEL_SCALAR_RE = re.compile(r"^([A-Za-z0-9_]+)\s*:\s*(.*?)\s*$")
YAML_TOP_LEVEL_KEY_RE = re.compile(r"^([A-Za-z0-9_]+)\s*:", re.MULTILINE)
PYTEST_EXECUTABLE_ENV = "API_AUTOMATION_PYTEST"
RUNTIME_CONFIG_BLOCKER_TERMS = (
    "执行配置",
    "运行配置",
    "环境信息",
    "环境引用",
    "鉴权",
    "账号",
    "token",
    "runtime_execution_config",
    "environment_reference",
    "authentication_account",
)
RUNTIME_CONFIG_KNOWN_MISSING_TERMS = (
    "缺少执行配置",
    "缺少运行配置",
    "缺少环境",
    "缺少鉴权",
    "缺少账号",
    "缺失字段",
    "missing_fields",
    "environment_reference",
    "authentication_account",
)
RUNTIME_CONFIG_GUIDE_REQUIRED_SECTIONS = (
    "环境信息",
    "模块 base URL 与网关前缀",
    "账号与角色及业务状态",
    "鉴权与 token 提取/注入",
    "加解密策略",
    "执行授权范围",
    "DB before/after 与清理授权",
    "外部依赖或沙箱/Mock",
    "必填缺失字段清单",
    "填写后继续条件",
)
DB_MCP_ATTEMPT_TERMS = ("数据库 MCP", "DB MCP", "database MCP", "database_mcp")
DB_MCP_BLOCKER_TERMS = (
    "不可用",
    "不可读",
    "未授权",
    "未配置",
    "无法连接",
    "无法确认",
    "身份无法确认",
    "图谱",
    "清理证据",
    "unavailable",
    "unreadable",
    "not authorized",
)


def read_text(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path} 不是 UTF-8 编码：{exc}") from exc
    if "\ufffd" in text:
        raise ValueError(f"{path} 存在疑似中文乱码字符")
    if not text.strip():
        raise ValueError(f"{path} 内容为空")
    return text


def read_yaml_file(path: Path, errors: list[str], label: str) -> Any:
    """读取 YAML 文件，并沿用 UTF-8 与乱码检查。"""

    try:
        text = read_text(path)
    except ValueError as exc:
        errors.append(str(exc))
        return None
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        errors.append(f"{label} YAML 解析失败：{exc}")
        return None


def read_optional_text(path: Path, errors: list[str]) -> str:
    """读取可选文本文件；读取失败时记录错误并返回空文本。"""

    if not path.is_file():
        return ""
    try:
        return read_text(path)
    except ValueError as exc:
        errors.append(str(exc))
        return ""


def line_value(text: str, label: str) -> str | None:
    for line in text.splitlines():
        normalized = line.strip().lstrip("-").strip()
        if normalized.startswith(f"{label}："):
            return normalized.split("：", 1)[1].strip()
    return None


def require(condition: bool, errors: list[str], message: str) -> None:
    if not condition:
        errors.append(message)


def require_files(base: Path, names: tuple[str, ...], errors: list[str], label: str) -> None:
    for name in names:
        path = base / name
        require(path.is_file(), errors, f"{label} 缺少文件：{path}")
        if path.is_file():
            try:
                read_text(path)
            except ValueError as exc:
                errors.append(str(exc))


def normalize_heading(heading: str) -> str:
    return re.sub(r"^[\d.、\s]+", "", heading.strip())


def collect_sections(text: str, title_keywords: tuple[str, ...]) -> str:
    matches = list(SECTION_HEADING_RE.finditer(text))
    parts: list[str] = []
    for index, match in enumerate(matches):
        title = normalize_heading(match.group(1))
        if not any(keyword in title for keyword in title_keywords):
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        parts.append(text[start:end].strip())
    return "\n".join(parts)


def is_none_marker_line(line: str) -> bool:
    normalized = line.strip().strip("|").strip()
    normalized = re.sub(r"^[-*]\s*", "", normalized).strip()
    normalized = normalized.strip("。；;，,：:")
    return normalized in NONE_MARKERS


def data_model_section_blocks(text: str, markers: tuple[str, ...]) -> list[str]:
    lines = text.splitlines()
    blocks: list[str] = []
    for index, raw_line in enumerate(lines):
        lowered = raw_line.lower()
        if not any(marker.lower() in lowered for marker in markers):
            continue
        block_lines = [raw_line]
        for nested in lines[index + 1 :]:
            if nested.lstrip().startswith("#"):
                break
            block_lines.append(nested)
        blocks.append("\n".join(block_lines))
    return blocks


def data_model_line_has_confirmed_content(line: str, markers: tuple[str, ...]) -> bool:
    normalized = line.strip().strip("|").strip()
    if not normalized or set(normalized) <= {"-", ":", "|", " "}:
        return False
    for marker in markers:
        normalized = re.sub(re.escape(marker), "", normalized, flags=re.IGNORECASE).strip()
    normalized = normalized.strip("#：:。；;，, ")
    if not normalized:
        return False
    return not any(marker in normalized.lower() for marker in DATA_MODEL_MISSING_CONTENT_MARKERS)


def data_model_group_has_confirmed_content(text: str, markers: tuple[str, ...]) -> bool:
    for block in data_model_section_blocks(text, markers):
        if any(data_model_line_has_confirmed_content(line, markers) for line in block.splitlines()):
            return True
    return False


def has_meaningful_blocker(section_text: str) -> bool:
    for raw_line in section_text.splitlines():
        line = raw_line.strip().strip("|").strip()
        if not line or set(line) <= {"-", ":", "|", " "}:
            continue
        if any(header in line for header in ("编号", "问题", "影响", "修正建议")):
            continue
        if is_none_marker_line(line):
            continue
        return True
    return False


def split_markdown_row(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|"):
        return []
    cells = [cell.strip() for cell in stripped.strip("|").split("|")]
    if cells and all(set(cell) <= {"-", ":", " "} for cell in cells):
        return []
    return cells


def has_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def invalid_coverage_point_value(value: str | None) -> bool:
    if value is None:
        return True
    normalized = value.strip().strip("|").strip()
    normalized = re.sub(r"<br\s*/?>", "", normalized, flags=re.IGNORECASE).strip()
    return normalized in COVERAGE_POINT_PLACEHOLDERS


def extract_coverage_point_records(text: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    header: list[str] | None = None
    header_indexes: dict[str, int] = {}
    for raw_line in text.splitlines():
        cells = split_markdown_row(raw_line)
        if not cells:
            continue
        if all(field in cells for field in COVERAGE_POINT_HEADERS):
            header = cells
            header_indexes = {field: cells.index(field) for field in COVERAGE_POINT_HEADERS}
            continue
        if header is None or len(cells) < len(header):
            continue
        records.append({field: cells[header_indexes[field]].strip() for field in COVERAGE_POINT_HEADERS})
    return records


def coverage_point_summary_text(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        cells = split_markdown_row(raw_line)
        if cells and all(field in cells for field in COVERAGE_POINT_HEADERS):
            break
        lines.append(raw_line)
    return "\n".join(lines).strip()


def coverage_point_interface_count(link: str) -> int:
    parts = [part.strip() for part in re.split(r"\s*(?:—>|->|→)\s*", link) if part.strip()]
    return len(parts) if parts else 0


def coverage_point_step_count(steps: str) -> int:
    numbered_steps = re.findall(r"(?:^|[；;。>\n])\s*\d+\s*[.、]", steps)
    if numbered_steps:
        return len(numbered_steps)
    split_steps = [part.strip() for part in re.split(r"(?:<br\s*/?>|；|;)", steps, flags=re.IGNORECASE) if part.strip()]
    return len(split_steps)


def long_chain_record_ids(records: list[dict[str, str]]) -> list[str]:
    ids: list[str] = []
    for record in records:
        if is_long_chain_coverage_point(record):
            row_id = record.get("ID", "").strip()
            if row_id:
                ids.append(row_id)
    return ids


def is_long_chain_coverage_point(record: dict[str, str]) -> bool:
    interface_count = coverage_point_interface_count(record.get("接口链路", ""))
    step_count = coverage_point_step_count(record.get("操作步骤", ""))
    return interface_count >= LONG_CHAIN_INTERFACE_THRESHOLD or step_count >= LONG_CHAIN_STEP_THRESHOLD


def is_single_interface_coverage_point(record: dict[str, str]) -> bool:
    return coverage_point_interface_count(record.get("接口链路", "")) == 1 and not is_long_chain_coverage_point(record)


def summary_has_coverage_line(summary: str, label: str, has_records: bool) -> bool:
    for line in summary.splitlines():
        if label not in line:
            continue
        if PERCENT_PATTERN.search(line):
            return True
        if not has_records and any(marker in line for marker in ("不涉及", "无", "0 个", "0个")):
            return True
    return False


def validate_coverage_point_order(records: list[dict[str, str]], errors: list[str], label: str) -> None:
    seen_single_interface = False
    for record in records:
        row_id = record.get("ID", "UNKNOWN")
        if is_single_interface_coverage_point(record):
            seen_single_interface = True
            continue
        if is_long_chain_coverage_point(record) and seen_single_interface:
            errors.append(f"{label} 明细表必须先列长链路用例，再列单接口用例：{row_id}")


def validate_coverage_point_summary(text: str, records: list[dict[str, str]], errors: list[str], label: str) -> None:
    summary = coverage_point_summary_text(text)
    if not summary:
        errors.append(f"{label} 明细表前缺少覆盖点摘要")
        return
    if COVERAGE_POINT_SUMMARY_TITLE not in summary:
        errors.append(f"{label} 开头缺少 {COVERAGE_POINT_SUMMARY_TITLE} 章节")
    if "覆盖率" not in summary:
        errors.append(f"{label} 覆盖点摘要缺少覆盖率")
    if not PERCENT_PATTERN.search(summary):
        errors.append(f"{label} 覆盖点摘要缺少覆盖率百分比")
    if not any(marker in summary for marker in ("计算口径", "计算公式", "计算方式")):
        errors.append(f"{label} 覆盖点摘要缺少覆盖率计算口径")
    if not ("× 100%" in summary or "* 100%" in summary or "x 100%" in summary.lower()):
        errors.append(f"{label} 覆盖点摘要缺少覆盖率乘以 100% 的计算说明")
    long_ids = long_chain_record_ids(records)
    single_records = [record for record in records if is_single_interface_coverage_point(record)]
    if not summary_has_coverage_line(summary, "长链路覆盖率", bool(long_ids)):
        errors.append(f"{label} 覆盖点摘要缺少独立长链路覆盖率或不涉及说明")
    if not summary_has_coverage_line(summary, "单接口覆盖率", bool(single_records)):
        errors.append(f"{label} 覆盖点摘要缺少独立单接口覆盖率或不涉及说明")
    if "长链路" in summary and "单接口" in summary and not any(marker in summary for marker in ("分别", "分项", "不得混合", "单独计算")):
        errors.append(f"{label} 覆盖点摘要需要说明长链路和单接口覆盖率分开计算")
    if "长链路" not in summary:
        errors.append(f"{label} 覆盖点摘要缺少长链路重点关注说明")

    if long_ids:
        for row_id in long_ids:
            if row_id not in summary:
                errors.append(f"{label} 覆盖点摘要缺少长链路重点关注 ID：{row_id}")
    elif not any(marker in summary for marker in ("长链路重点关注：无", "长链路重点关注: 无", "长链路重点关注：0", "长链路重点关注: 0")):
        errors.append(f"{label} 无长链路测试点时需要在摘要中明确写明无或 0 个")


def validate_coverage_point_report_file(path: Path, errors: list[str], require_records: bool) -> None:
    if not path.is_file():
        if require_records:
            errors.append(f"缺少人工测试覆盖点报告：{path}")
        return
    try:
        text = read_text(path)
    except ValueError as exc:
        errors.append(str(exc))
        return

    records = extract_coverage_point_records(text)
    if require_records and not records:
        errors.append(f"{path.name} 缺少包含十一个必需字段的 Markdown 表格")
        return
    if records:
        validate_coverage_point_summary(text, records, errors, path.name)
        validate_coverage_point_order(records, errors, path.name)

    for index, record in enumerate(records, start=1):
        row_id = record.get("ID") or f"第 {index} 行"
        for field in COVERAGE_POINT_HEADERS:
            if invalid_coverage_point_value(record.get(field)):
                errors.append(f"{path.name} {row_id} 字段为空或为占位内容：{field}")
        for field in COVERAGE_POINT_CHINESE_FIELDS:
            value = record.get(field, "")
            if not invalid_coverage_point_value(value) and not has_chinese(value):
                errors.append(f"{path.name} {row_id} 字段必须使用中文描述：{field}")
        priority = record.get("优先级", "").strip().lower()
        if priority not in COVERAGE_POINT_PRIORITY_VALUES:
            errors.append(f"{path.name} {row_id} 优先级必须为 p0/p1/p2：{record.get('优先级')}")
        link = record.get("接口链路", "")
        if "->" in link or "→" in link:
            errors.append(f"{path.name} {row_id} 接口链路请使用 接口1—>接口2 格式")
        test_point = record.get("测试点", "")
        if re.search(r"\b(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b\s*/", test_point, re.IGNORECASE):
            errors.append(f"{path.name} {row_id} 测试点不能只写 method/path")
        if looks_like_path_bucket_long_chain(
            record.get("业务域", ""),
            record.get("业务场景", ""),
            test_point,
            record.get("用例类型", ""),
        ):
            errors.append(f"{path.name} {row_id} 疑似接口标签或路径前缀用例，必须改为真实业务场景描述")
        if invalid_coverage_point_value(record.get("来源")):
            errors.append(f"{path.name} {row_id} 来源必须引用需求、测试点、覆盖对象或设计级用例证据")


def extract_case_identity_groups(case_yaml_text: str) -> list[set[str]]:
    groups: list[set[str]] = []
    section = yaml_section(case_yaml_text, "cases")
    current: set[str] | None = None
    for raw_line in section.splitlines():
        stripped = raw_line.strip()
        inline_match = re.match(r"^-\s*\{(.+)\}\s*$", stripped)
        if inline_match:
            if current is not None:
                groups.append(current)
                current = None
            mapping = parse_inline_mapping(inline_match.group(1))
            identity = {mapping.get("case_id", ""), mapping.get("design_case_id", "")}
            groups.append({item for item in identity if item and not invalid_coverage_point_value(item)})
            continue
        item_match = re.match(r"^-\s+([A-Za-z0-9_]+)\s*:\s*(.*?)\s*$", stripped)
        if item_match:
            if current is not None:
                groups.append(current)
            current = set()
            key, value = item_match.group(1), item_match.group(2).strip().strip("\"'")
            if key in {"case_id", "design_case_id"} and not invalid_coverage_point_value(value):
                current.add(value)
            continue
        if current is None:
            continue
        scalar_match = re.match(r"^([A-Za-z0-9_]+)\s*:\s*(.*?)\s*$", stripped)
        if scalar_match:
            key, value = scalar_match.group(1), scalar_match.group(2).strip().strip("\"'")
            if key in {"case_id", "design_case_id"} and not invalid_coverage_point_value(value):
                current.add(value)
    if current is not None:
        groups.append(current)
    return [group for group in groups if group]


def validate_coverage_point_case_mapping(case_yaml_path: Path, report_path: Path, errors: list[str], require_passed: bool) -> None:
    if not require_passed or not case_yaml_path.is_file() or not report_path.is_file():
        return
    try:
        case_yaml_text = read_text(case_yaml_path)
        report_text = read_text(report_path)
    except ValueError as exc:
        errors.append(str(exc))
        return
    groups = extract_case_identity_groups(case_yaml_text)
    mapped_count = 0
    if not groups:
        return
    for index, group in enumerate(groups, start=1):
        if not any(identity in report_text for identity in group):
            errors.append(
                f"{report_path.name} 缺少 case_list.yaml 第 {index} 条设计级用例的来源映射："
                f"{sorted(group)}"
            )
        else:
            mapped_count += 1
    summary = coverage_point_summary_text(report_text)
    if summary:
        expected_rate = mapped_count / len(groups) * 100
        summary_rates = [float(value) for value in PERCENT_PATTERN.findall(summary)]
        if not summary_rates:
            errors.append(f"{report_path.name} 覆盖点摘要缺少可解析的覆盖率百分比")
        elif not any(abs(rate - expected_rate) < 0.01 for rate in summary_rates):
            errors.append(
                f"{report_path.name} 覆盖点摘要覆盖率与映射结果不一致："
                f"摘要={summary_rates}，实际={expected_rate:g}%"
            )


def business_scenario_descriptions(text: str) -> set[str]:
    return {
        value.strip()
        for value in yaml_scalar_values(text, "business_description")
        if value.strip() and not invalid_coverage_point_value(value)
    }


def business_scenario_item_blocks(text: str) -> list[str]:
    starts = list(re.finditer(r"(?m)^\s*-\s+scenario_id\s*:", text))
    blocks: list[str] = []
    for index, start in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        blocks.append(text[start.start():end])
    return blocks


def business_scenario_items_from_yaml(text: str) -> list[dict[str, Any]]:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return []
    if not isinstance(data, dict):
        return []
    items = data.get("scenario_items")
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, dict):
                result.extend(text_list(item.get("interface") or item.get("source_ref")))
            else:
                result.extend(text_list(item))
        return result
    text = str(value).strip().strip("\"'")
    if not text or invalid_coverage_point_value(text) or yaml_scalar_is_empty_list(text):
        return []
    return [text]


def scenario_item_interfaces(item: dict[str, Any]) -> list[str]:
    interfaces = text_list(item.get("related_interfaces"))
    interfaces.extend(text_list(item.get("ordered_steps")))
    return interfaces


def resource_key_from_interface(interface: str) -> str:
    match = HTTP_INTERFACE_RE.search(interface)
    if not match:
        return ""
    path = re.sub(r"\{[^}]+\}", "", match.group(1))
    parts = [part for part in re.sub(r"/+", "/", path).strip("/").split("/") if part]
    semantic_parts: list[str] = []
    for part in parts:
        lowered = part.lower()
        if lowered in GENERIC_ROUTE_SEGMENTS or re.fullmatch(r"v\d+", lowered):
            continue
        if lowered in ACTION_ROUTE_SEGMENTS:
            continue
        semantic_parts.append(lowered)
    return "/".join(semantic_parts[:2]) if semantic_parts else ""


def item_has_mutation(item: dict[str, Any]) -> bool:
    text = " ".join(
        scenario_item_interfaces(item)
        + text_list(item.get("business_chain"))
        + text_list(item.get("scenario_name"))
    )
    return bool(MUTATING_INTERFACE_RE.search(text)) or bool(
        re.search(r"创建|提交|更新|删除|发布|发送|认证|上传|支付|充值|提现|绑定|解除|申请|审核", text)
    )


def item_has_read_or_verify(item: dict[str, Any]) -> bool:
    text = " ".join(
        scenario_item_interfaces(item)
        + text_list(item.get("business_chain"))
        + text_list(item.get("scenario_name"))
    )
    return bool(READ_VERIFY_RE.search(text))


def splittable_single_interface_clusters(items: list[dict[str, Any]]) -> list[str]:
    if any(
        is_yaml_true(str(item.get("flow_generation_required", "")))
        or str(item.get("chain_type", "")).strip().strip("\"'") == "e2e_flow_candidate"
        for item in items
    ):
        return []
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        if str(item.get("chain_type", "")).strip().strip("\"'") != "single_interface":
            continue
        keys = {resource_key_from_interface(interface) for interface in scenario_item_interfaces(item)}
        for key in keys:
            if key:
                groups.setdefault(key, []).append(item)
    splittable: list[str] = []
    for key, group in sorted(groups.items()):
        if len(group) < LONG_CHAIN_INTERFACE_THRESHOLD:
            continue
        if any(item_has_mutation(item) for item in group) and any(item_has_read_or_verify(item) for item in group):
            splittable.append(key)
    return splittable


def block_first_scalar(block: str, key: str) -> str | None:
    values = yaml_scalar_values(block, key)
    return values[0] if values else None


def block_has_key(block: str, key: str) -> bool:
    return re.search(rf"(?m)^\s*(?:-\s*)?{re.escape(key)}\s*:", block) is not None


def block_has_any_key(block: str, keys: tuple[str, ...]) -> bool:
    return any(block_has_key(block, key) for key in keys)


def block_scalar_present(block: str, key: str) -> bool:
    value = block_first_scalar(block, key)
    if value is None:
        return False
    normalized = value.strip().strip("\"'").lower()
    return normalized not in {"", "null", "none", "~"}


def block_has_any_scalar(block: str, keys: tuple[str, ...]) -> bool:
    return any(block_scalar_present(block, key) for key in keys)


def parse_inline_yaml_list(value: str) -> list[str]:
    normalized = value.strip().strip("\"'")
    if not (normalized.startswith("[") and normalized.endswith("]")):
        return []
    inner = normalized[1:-1].strip()
    if not inner:
        return []
    return [
        item.strip().strip("\"'")
        for item in re.split(r"\s*,\s*", inner)
        if item.strip().strip("\"'")
    ]


def block_list_values(block: str, key: str) -> list[str]:
    values: list[str] = []
    lines = block.splitlines()
    for index, line in enumerate(lines):
        match = re.match(rf"^(\s*)(?:-\s*)?{re.escape(key)}\s*:\s*(.*?)\s*$", line)
        if not match:
            continue
        indent = len(match.group(1))
        inline_value = match.group(2).strip()
        inline_items = parse_inline_yaml_list(inline_value)
        if inline_items:
            values.extend(inline_items)
            continue
        if inline_value and not yaml_scalar_is_empty_list(inline_value):
            values.append(inline_value.strip().strip("\"'"))
            continue
        for next_line in lines[index + 1:]:
            next_indent = len(next_line) - len(next_line.lstrip(" "))
            item_match = re.match(r"^\s*-\s*(.*?)\s*$", next_line)
            if item_match and item_match.group(1).strip():
                values.append(item_match.group(1).strip().strip("\"'"))
                continue
            if next_line.strip() and next_indent <= indent:
                break
    return [value for value in values if not invalid_coverage_point_value(value)]


def yaml_sequence_raw_blocks(text: str, section_key: str, first_key: str) -> list[str]:
    section = yaml_section(text, section_key)
    starts = list(re.finditer(rf"(?m)^\s*-\s+{re.escape(first_key)}\s*:", section))
    blocks: list[str] = []
    for index, start in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(section)
        blocks.append(section[start.start():end])
    return blocks


def nested_yaml_block(block: str, parent_key: str) -> str:
    lines = block.splitlines()
    for index, line in enumerate(lines):
        match = re.match(rf"^(\s*){re.escape(parent_key)}\s*:\s*(.*?)\s*$", line)
        if not match:
            continue
        parent_indent = len(match.group(1))
        nested_lines: list[str] = []
        for nested_line in lines[index + 1:]:
            if nested_line.strip():
                nested_indent = len(nested_line) - len(nested_line.lstrip(" "))
                if nested_indent <= parent_indent:
                    break
            nested_lines.append(nested_line)
        return "\n".join(nested_lines)
    return ""


def nested_first_scalar(block: str, parent_key: str, child_key: str) -> str | None:
    nested = nested_yaml_block(block, parent_key)
    values = yaml_scalar_values(nested, child_key)
    return values[0] if values else None


def validate_required_chain_flows_file(path: Path, errors: list[str], require_passed: bool) -> set[str]:
    if not path.is_file():
        if require_passed:
            errors.append(f"缺少长链路必测分母：{path}")
        return set()
    try:
        text = read_text(path)
    except ValueError as exc:
        errors.append(str(exc))
        return set()

    label = path.name
    require_yaml_top_level_keys(text, REQUIRED_CHAIN_FLOW_REQUIRED_KEYS, errors, label)
    schema_version = yaml_int_value(text, "schema_version", errors, label)
    if schema_version is not None and schema_version != 1:
        errors.append(f"{label} schema_version 不是 1：{schema_version}")
    stage = first_yaml_scalar(text, "stage")
    if stage != "required_chain_flow_denominator":
        errors.append(f"{label} stage 不匹配：{stage} != required_chain_flow_denominator")
    status = first_yaml_scalar(text, "status")
    if status not in {"passed", "blocked"}:
        errors.append(f"{label} status 非法或缺失：{status}")
    if require_passed:
        if status != "passed":
            errors.append(f"{label} status 不是 passed：{status}")
        next_stage_allowed = first_yaml_scalar(text, "next_stage_allowed")
        if next_stage_allowed is None or not is_yaml_true(next_stage_allowed):
            errors.append(f"{label} next_stage_allowed 不是 true：{next_stage_allowed}")
        require_yaml_empty_list(text, "unclassified_candidate_flows", errors, label)
        require_yaml_empty_list(text, "blocking_issues", errors, label)

    required_ids: list[str] = []
    flow_blocks = yaml_sequence_raw_blocks(text, "flows", "flow_id")
    for block in flow_blocks:
        flow_id = block_first_scalar(block, "flow_id") or "UNKNOWN"
        flow_status = block_first_scalar(block, "status")
        if flow_status != "required":
            continue
        if invalid_coverage_point_value(flow_id):
            errors.append(f"{label} 存在缺少有效 flow_id 的 required flow")
            continue
        required_ids.append(flow_id)
        source_route = block_first_scalar(block, "source_route")
        if source_route not in {"doc", "source"}:
            errors.append(f"{label} {flow_id} source_route 必须为 doc/source：{source_route}")
        for scalar_key in ("business_domain", "scenario_name"):
            value = block_first_scalar(block, scalar_key)
            if invalid_coverage_point_value(value):
                errors.append(f"{label} {flow_id} 缺少有效字段：{scalar_key}")
        if not has_chinese(block_first_scalar(block, "business_domain") or ""):
            errors.append(f"{label} {flow_id} business_domain 必须为中文业务域")
        if not has_chinese(block_first_scalar(block, "scenario_name") or ""):
            errors.append(f"{label} {flow_id} scenario_name 必须为中文业务场景名称")
        if looks_like_path_bucket_long_chain(
            block_first_scalar(block, "business_domain") or "",
            block_first_scalar(block, "scenario_name") or "",
        ):
            errors.append(f"{label} {flow_id} 疑似按路径/接口前缀拼接必测长链路，必须先拆成真实业务场景")
        pre_interface = nested_first_scalar(block, "pre_action", "interface")
        if invalid_coverage_point_value(pre_interface):
            errors.append(f"{label} {flow_id} 缺少前序业务动作接口：pre_action.interface")
        change_type = nested_first_scalar(block, "observable_change", "type")
        change_evidence = nested_first_scalar(block, "observable_change", "evidence")
        if invalid_coverage_point_value(change_type) or invalid_coverage_point_value(change_evidence):
            errors.append(f"{label} {flow_id} 缺少可观察变化证据：observable_change.type/evidence")
        verification_interface = nested_first_scalar(block, "verification", "interface")
        if invalid_coverage_point_value(verification_interface):
            errors.append(f"{label} {flow_id} 缺少后序查询或消费验证接口：verification.interface")
        for list_key in ("link_keys", "steps", "evidence_refs"):
            values = block_list_values(block, list_key)
            if not values:
                errors.append(f"{label} {flow_id} 缺少非空列表：{list_key}")

    if len(required_ids) != len(set(required_ids)):
        errors.append(f"{label} required flow_id 存在重复：{required_ids}")
    required_count = yaml_int_value(text, "required_chain_flow_count", errors, label)
    if required_count is not None and required_count != len(set(required_ids)):
        errors.append(
            f"{label} required_chain_flow_count 与 required flow 数不一致："
            f"{required_count} != {len(set(required_ids))}"
        )
    return set(required_ids)


def validate_business_chain_candidate_inventory_file(path: Path, errors: list[str], require_passed: bool) -> None:
    if not path.is_file():
        if require_passed:
            errors.append(f"缺少业务链路候选库存：{path}")
        return
    try:
        text = read_text(path)
    except ValueError as exc:
        errors.append(str(exc))
        return

    label = path.name
    require_yaml_top_level_keys(text, BUSINESS_CHAIN_CANDIDATE_INVENTORY_REQUIRED_KEYS, errors, label)
    schema_version = yaml_int_value(text, "schema_version", errors, label)
    if schema_version is not None and schema_version != 1:
        errors.append(f"{label} schema_version 不是 1：{schema_version}")
    stage = first_yaml_scalar(text, "stage")
    if stage != "business_chain_candidate_inventory":
        errors.append(f"{label} stage 不匹配：{stage} != business_chain_candidate_inventory")
    status = first_yaml_scalar(text, "status")
    if status not in {"passed", "blocked"}:
        errors.append(f"{label} status 非法或缺失：{status}")
    if require_passed:
        if status != "passed":
            errors.append(f"{label} status 不是 passed：{status}")
        next_stage_allowed = first_yaml_scalar(text, "next_stage_allowed")
        if next_stage_allowed is None or not is_yaml_true(next_stage_allowed):
            errors.append(f"{label} next_stage_allowed 不是 true：{next_stage_allowed}")
        require_yaml_empty_list(text, "blocking_issues", errors, label)

    observed_counts = {inventory_type: 0 for inventory_type in BUSINESS_CHAIN_CANDIDATE_INVENTORY_TYPES}
    item_count = 0
    for block in yaml_sequence_raw_blocks(text, "items", "candidate_id"):
        item_count += 1
        candidate_id = block_first_scalar(block, "candidate_id") or "UNKNOWN"
        candidate_type = block_first_scalar(block, "candidate_type")
        classification = block_first_scalar(block, "classification")
        if candidate_type not in BUSINESS_CHAIN_CANDIDATE_INVENTORY_TYPES:
            errors.append(f"{label} {candidate_id} candidate_type 非法或缺失：{candidate_type}")
        else:
            observed_counts[candidate_type] += 1
        if classification not in CHAIN_FLOW_ALLOWED_CANDIDATE_CLASSIFICATIONS:
            errors.append(f"{label} {candidate_id} classification 非法或缺失：{classification}")
            continue
        expected_type = BUSINESS_CHAIN_INVENTORY_TYPE_BY_CLASSIFICATION[classification]
        if candidate_type in BUSINESS_CHAIN_CANDIDATE_INVENTORY_TYPES and candidate_type != expected_type:
            errors.append(
                f"{label} {candidate_id} candidate_type 与 classification 不一致："
                f"{candidate_type} != {expected_type}"
            )
        for required_field in ("flow_id", "scenario_id", "source_route", "downstream_target"):
            if invalid_coverage_point_value(block_first_scalar(block, required_field)):
                errors.append(f"{label} {candidate_id} 缺少 {required_field}")

    candidate_total = yaml_int_value(text, "candidate_total", errors, label)
    if candidate_total is not None and candidate_total != item_count:
        errors.append(f"{label} candidate_total 与候选明细不一致：{candidate_total} != {item_count}")
    summary_section = yaml_section(text, "candidate_type_summary")
    for inventory_type in BUSINESS_CHAIN_CANDIDATE_INVENTORY_TYPES:
        actual_count = yaml_int_value(summary_section, inventory_type, errors, f"{label}.candidate_type_summary")
        if actual_count is not None and actual_count != observed_counts[inventory_type]:
            errors.append(
                f"{label} candidate_type_summary.{inventory_type} 与候选明细不一致："
                f"{actual_count} != {observed_counts[inventory_type]}"
            )


def validate_chain_flow_candidate_audit_file(
    path: Path,
    errors: list[str],
    require_passed: bool,
    audited_flow_ids: set[str] | None = None,
) -> set[str]:
    if not path.is_file():
        if require_passed:
            errors.append(f"缺少长链路候选审计：{path}")
        return set()
    try:
        text = read_text(path)
    except ValueError as exc:
        errors.append(str(exc))
        return set()

    label = path.name
    require_yaml_top_level_keys(text, CHAIN_FLOW_AUDIT_REQUIRED_KEYS, errors, label)
    schema_version = yaml_int_value(text, "schema_version", errors, label)
    if schema_version is not None and schema_version != 1:
        errors.append(f"{label} schema_version 不是 1：{schema_version}")
    stage = first_yaml_scalar(text, "stage")
    if stage != "chain_flow_candidate_audit":
        errors.append(f"{label} stage 不匹配：{stage} != chain_flow_candidate_audit")
    status = first_yaml_scalar(text, "status")
    if status not in {"passed", "blocked"}:
        errors.append(f"{label} status 非法或缺失：{status}")
    if require_passed:
        if status != "passed":
            errors.append(f"{label} status 不是 passed：{status}")
        next_stage_allowed = first_yaml_scalar(text, "next_stage_allowed")
        if next_stage_allowed is None or not is_yaml_true(next_stage_allowed):
            errors.append(f"{label} next_stage_allowed 不是 true：{next_stage_allowed}")
        require_yaml_empty_list(text, "unclassified_candidate_flows", errors, label)
        require_yaml_empty_list(text, "blocking_issues", errors, label)

    included_ids: set[str] = set()
    observed_counts = {classification: 0 for classification in CHAIN_FLOW_ALLOWED_CANDIDATE_CLASSIFICATIONS}
    observed_unclassified = 0
    for block in yaml_sequence_raw_blocks(text, "candidates", "candidate_id"):
        candidate_id = block_first_scalar(block, "candidate_id") or "UNKNOWN"
        classification = block_first_scalar(block, "classification")
        if classification not in CHAIN_FLOW_ALLOWED_CANDIDATE_CLASSIFICATIONS:
            errors.append(f"{label} {candidate_id} classification 非法或未分类：{classification}")
            observed_unclassified += 1
            continue
        observed_counts[classification] += 1
        downstream_target = block_first_scalar(block, "downstream_target")
        if classification != "included" and invalid_coverage_point_value(downstream_target):
            errors.append(f"{label} {candidate_id} 非 included 候选缺少 downstream_target，无法证明已正确分流")
        reason = block_first_scalar(block, "reason") or ""
        if classification == "excluded_readonly":
            if "已纳入设计级覆盖" in reason:
                errors.append(f"{label} {candidate_id} excluded_readonly 使用了泛化排除理由，必须说明真实只读证据")
            readonly_reason = any(marker in reason for marker in ("只读", "纯查询", "读取", "READ", "read"))
            mutation_reason = any(marker in reason.upper() for marker in ("CREATE", "UPDATE", "DELETE", "INSERT", "新增", "创建", "提交", "绑定", "撤销", "解除", "删除", "修改", "变更", "回调", "审核", "支付", "提现", "充值", "发布", "发送", "拉黑"))
            if not readonly_reason or mutation_reason:
                errors.append(f"{label} {candidate_id} excluded_readonly 理由不能证明纯只读：{reason}")
        flow_id = block_first_scalar(block, "flow_id")
        if flow_id and not invalid_coverage_point_value(flow_id) and audited_flow_ids is not None:
            audited_flow_ids.add(flow_id)
        if classification == "included":
            if invalid_coverage_point_value(flow_id):
                errors.append(f"{label} {candidate_id} included 候选缺少 flow_id")
            else:
                included_ids.add(flow_id or "")
    summary_section = yaml_section(text, "candidate_summary")
    for classification in sorted(CHAIN_FLOW_ALLOWED_CANDIDATE_CLASSIFICATIONS):
        expected_count = observed_counts[classification]
        if classification == "excluded_ready_by_policy" and not yaml_scalar_values(summary_section, classification):
            # 兼容事实重算规则引入前生成的候选审计；新产物由 builder 显式写出该计数。
            continue
        actual_count = yaml_int_value(summary_section, classification, errors, f"{label}.candidate_summary")
        if actual_count is not None and actual_count != expected_count:
            errors.append(
                f"{label} candidate_summary.{classification} 与候选明细不一致："
                f"{actual_count} != {expected_count}"
            )
    unclassified_count = yaml_int_value(summary_section, "unclassified", errors, f"{label}.candidate_summary")
    if unclassified_count is not None and unclassified_count != observed_unclassified:
        errors.append(
            f"{label} candidate_summary.unclassified 与候选明细不一致："
            f"{unclassified_count} != {observed_unclassified}"
        )
    return included_ids


def validate_chain_flow_alignment_file(path: Path, errors: list[str], required: bool) -> None:
    if not path.is_file():
        if required:
            errors.append(f"文档入口和源码入口同时存在时缺少链路差异对齐产物：{path}")
        return
    try:
        text = read_text(path)
    except ValueError as exc:
        errors.append(str(exc))
        return
    label = path.name
    require_yaml_top_level_keys(text, CHAIN_FLOW_ALIGNMENT_REQUIRED_KEYS, errors, label)
    status = first_yaml_scalar(text, "status")
    if status not in {"passed", "blocked"}:
        errors.append(f"{label} status 非法或缺失：{status}")
    for value in yaml_scalar_values(text, "alignment_status"):
        normalized = value.strip().strip("\"'")
        if normalized not in {"doc_only", "source_only", "both_step_diff", "both_consistent"}:
            errors.append(f"{label} alignment_status 非法：{value}")


def validate_chain_flow_denominator(
    root: Path,
    errors: list[str],
    require_passed: bool,
    require_alignment: bool,
    expected_candidate_flow_ids: set[str] | None = None,
) -> set[str]:
    validate_business_chain_candidate_inventory_file(root / BUSINESS_CHAIN_CANDIDATE_INVENTORY, errors, require_passed)
    required_ids = validate_required_chain_flows_file(root / REQUIRED_CHAIN_FLOWS, errors, require_passed)
    audited_flow_ids: set[str] = set()
    included_ids = validate_chain_flow_candidate_audit_file(
        root / CHAIN_FLOW_CANDIDATE_AUDIT,
        errors,
        require_passed,
        audited_flow_ids,
    )
    if require_passed and included_ids != required_ids:
        errors.append(
            "长链路候选审计 included flow 与必测分母不一致："
            f"audit={sorted(included_ids)}，required={sorted(required_ids)}"
        )
    if require_passed and expected_candidate_flow_ids:
        missing_audited = sorted(expected_candidate_flow_ids - audited_flow_ids)
        if missing_audited:
            errors.append(
                "长链路候选审计未覆盖选定入口 business_scenario_map.yaml 中必须生成链路脚本的候选 flow："
                f"{missing_audited}"
            )
    validate_chain_flow_alignment_file(root / CHAIN_FLOW_ALIGNMENT, errors, require_alignment and require_passed)
    return required_ids


def load_yaml_mapping_for_gate(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(read_text(path))
    except (ValueError, yaml.YAMLError) as exc:
        errors.append(f"无法读取结构化门禁文件 {path}：{exc}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"结构化门禁文件顶层必须为对象：{path}")
        return {}
    return data


def text_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [] if not text else [text]


def collect_chain_aliases(value: Any) -> set[str]:
    aliases: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"flow_id", "chain_id", "case_id", "design_case_id", "required_flow_id"}:
                aliases.update(text_values(item))
            aliases.update(collect_chain_aliases(item))
    elif isinstance(value, list):
        for item in value:
            aliases.update(collect_chain_aliases(item))
    return {alias for alias in aliases if alias and not invalid_coverage_point_value(alias)}


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def runtime_ready_chain_aliases(root: Path, design_aliases: set[str], errors: list[str]) -> set[str]:
    evidence_path = root / RUNTIME_EVIDENCE_DIR / RUNTIME_EVIDENCE
    data = load_yaml_mapping_for_gate(evidence_path, errors)
    evidence_items = data.get("evidence_items")
    if not isinstance(evidence_items, list):
        return set()
    ready_aliases: set[str] = set()
    for item in evidence_items:
        if not isinstance(item, dict):
            continue
        if item.get("source_status") != "confirmed" or item.get("usable_for_execution_case") is not True:
            continue
        if item.get("script_materialization_ready") is not True:
            continue
        unresolved = text_values(item.get("missing_materialization_items") or item.get("unresolved_materialization_items"))
        if unresolved:
            continue
        aliases = collect_chain_aliases(item)
        ready_aliases.update(aliases & design_aliases)
    return ready_aliases


def filled_long_chain_fact_count(root: Path, errors: list[str]) -> int:
    counts: list[int] = []
    for relative in (
        "00-inputs/execution-readiness/long_chain_missing_value_fields.yaml",
        "05-executable-interface-case-set/long_chain_missing_value_fields.yaml",
    ):
        path = root / relative
        data = load_yaml_mapping_for_gate(path, errors)
        value = data.get("filled_count", 0)
        try:
            counts.append(int(value))
        except (TypeError, ValueError):
            if data:
                errors.append(f"{relative} filled_count 不是整数：{value}")
    return max(counts, default=0)


def validate_chain_execution_readiness_reconciliation(
    root: Path,
    target_depth: str | None,
    required_flow_ids: set[str],
    errors: list[str],
) -> None:
    if target_depth not in {"executable", "framework"}:
        return
    design_path = root / "04-design-case-handoff" / BUSINESS_LONG_CHAIN_CASES
    if not design_path.is_file():
        design_path = root / "03-interface-testcase-generation" / BUSINESS_LONG_CHAIN_CASES
    design_data = load_yaml_mapping_for_gate(design_path, errors)
    design_aliases = collect_chain_aliases(design_data)
    runtime_ready_aliases = runtime_ready_chain_aliases(root, design_aliases, errors)
    filled_count = filled_long_chain_fact_count(root, errors)
    reconciliation_path = root / CHAIN_EXECUTION_READINESS_RECONCILIATION
    reconciliation_required = bool(runtime_ready_aliases or filled_count > 0)
    if not reconciliation_path.is_file():
        if reconciliation_required:
            errors.append(
                "执行就绪事实已补充但缺少 chain_execution_readiness_reconciliation.yaml；"
                "必须作废旧链路分母并重算，不能继续沿用初始 required_chain_flow_count"
            )
        if filled_count > 0 and not required_flow_ids:
            errors.append(
                "long_chain_missing_value_fields.yaml filled_count > 0，但 required_chain_flow_count=0 且无明确排除清单，守恒门禁不通过"
            )
        return

    data = load_yaml_mapping_for_gate(reconciliation_path, errors)
    if not data:
        return
    label = reconciliation_path.name
    if data.get("schema_version") != 1:
        errors.append(f"{label} schema_version 必须为 1")
    if data.get("stage") != "chain_execution_readiness_reconciliation":
        errors.append(f"{label} stage 必须为 chain_execution_readiness_reconciliation")
    status = data.get("status")
    if status not in {"ready_for_generation", "passed"}:
        errors.append(f"{label} status 非法：{status}")
    if data.get("target_depth") != target_depth:
        errors.append(f"{label} target_depth 与流水线目标深度不一致：{data.get('target_depth')} != {target_depth}")
    if text_values(data.get("blocking_issues")):
        errors.append(f"{label} blocking_issues 必须为空")

    revisions = data.get("fact_revisions")
    revision_paths: set[str] = set()
    if not isinstance(revisions, list) or not revisions:
        errors.append(f"{label} fact_revisions 必须为非空列表")
    else:
        for index, revision in enumerate(revisions, start=1):
            if not isinstance(revision, dict):
                errors.append(f"{label} fact_revisions 第 {index} 项必须为对象")
                continue
            relative = str(revision.get("path") or "").strip()
            expected_hash = str(revision.get("sha256") or "").strip()
            if not relative or not expected_hash:
                errors.append(f"{label} fact_revisions 第 {index} 项缺少 path/sha256")
                continue
            revision_paths.add(relative)
            if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
                errors.append(f"{label} fact_revisions 第 {index} 项 sha256 必须为 64 位小写十六进制")
            fact_path = (root / relative).resolve()
            try:
                fact_path.relative_to(root.resolve())
            except ValueError:
                errors.append(f"{label} fact_revisions 路径越出输出目录：{relative}")
                continue
            if not fact_path.is_file():
                errors.append(f"{label} fact_revisions 引用文件不存在：{relative}")
            elif sha256_path(fact_path) != expected_hash:
                errors.append(f"执行事实 {relative} 已变化，旧链路分母和重算结果必须作废后重新计算")
    missing_fact_revisions = [
        relative
        for relative in KNOWN_CHAIN_EXECUTION_FACT_PATHS
        if (root / relative).is_file() and relative not in revision_paths
    ]
    if missing_fact_revisions:
        errors.append(f"{label} 遗漏现有执行就绪事实文件版本：{missing_fact_revisions}")

    ready_items = data.get("ready_chains")
    if not isinstance(ready_items, list):
        errors.append(f"{label} ready_chains 必须为列表")
        ready_items = []
    pending_items = data.get("pending_chains")
    if not isinstance(pending_items, list):
        errors.append(f"{label} pending_chains 必须为列表")
        pending_items = []

    ready_ids: list[str] = []
    generate_ids: set[str] = set()
    exclusion_ids: set[str] = set()
    executable_text = ""
    executable_paths = (
        root / "05-executable-interface-case-set" / "执行级接口用例集.md",
        root / "05-executable-interface-case-set" / "coverage_matrix.yaml",
    )
    for path in executable_paths:
        if path.is_file():
            try:
                executable_text += "\n" + read_text(path)
            except ValueError as exc:
                errors.append(str(exc))
    framework_text = ""
    generation_status_path = root / "api-test-framework" / "configs" / "generation_status.yaml"
    if generation_status_path.is_file():
        try:
            framework_text = read_text(generation_status_path)
        except ValueError as exc:
            errors.append(str(exc))

    for index, item in enumerate(ready_items, start=1):
        if not isinstance(item, dict):
            errors.append(f"{label} ready_chains 第 {index} 项必须为对象")
            continue
        flow_id = str(item.get("flow_id") or "").strip()
        if not flow_id:
            errors.append(f"{label} ready_chains 第 {index} 项缺少 flow_id")
            continue
        ready_ids.append(flow_id)
        decision = item.get("decision")
        capability = item.get("closure_capability")
        if capability not in CHAIN_READINESS_CAPABILITIES:
            errors.append(f"{label} {flow_id} closure_capability 非法：{capability}")
        if target_depth not in set(text_values(item.get("supported_target_depths"))):
            errors.append(f"{label} {flow_id} 未证明支持目标深度 {target_depth}")
        if item.get("materialization_status") != "ready":
            errors.append(f"{label} {flow_id} materialization_status 必须为 ready")
        if text_values(item.get("unresolved_materialization_items")):
            errors.append(f"{label} {flow_id} 仍有未闭合物化项")
        if not text_values(item.get("closure_evidence_refs")):
            errors.append(f"{label} {flow_id} 缺少 closure_evidence_refs")
        if decision == "generate":
            generate_ids.add(flow_id)
            case_ids = text_values(item.get("executable_case_ids"))
            if status == "passed" and not case_ids:
                errors.append(f"{label} {flow_id} decision=generate 但缺少 executable_case_ids")
            for case_id in case_ids:
                if executable_text and case_id not in executable_text:
                    errors.append(f"{label} {flow_id} 的 executable_case_id 未出现在执行级产物：{case_id}")
            if target_depth == "framework" and status == "passed":
                nodeids = text_values(item.get("pytest_nodeids"))
                if not nodeids:
                    errors.append(f"{label} {flow_id} 目标为 framework 时缺少 pytest_nodeids")
                for nodeid in nodeids:
                    if framework_text and nodeid not in framework_text:
                        errors.append(f"{label} {flow_id} 的 pytest_nodeid 未出现在 generation_status.yaml：{nodeid}")
        elif decision == "exclude":
            exclusion_ids.add(flow_id)
            if not str(item.get("exclusion_reason_code") or "").strip():
                errors.append(f"{label} {flow_id} 明确排除时缺少 exclusion_reason_code")
            if not text_values(item.get("exclusion_evidence_refs")):
                errors.append(f"{label} {flow_id} 明确排除时缺少 exclusion_evidence_refs")
            if text_values(item.get("executable_case_ids")) or text_values(item.get("pytest_nodeids")):
                errors.append(f"{label} {flow_id} 明确排除时不得填写生成映射")
        else:
            errors.append(f"{label} {flow_id} decision 必须为 generate 或 exclude")

    if len(ready_ids) != len(set(ready_ids)):
        errors.append(f"{label} 每条 execution-ready chain 必须且只能出现一次")
    pending_ids = [str(item.get("flow_id") or "").strip() for item in pending_items if isinstance(item, dict)]
    pending_ids = [flow_id for flow_id in pending_ids if flow_id]
    if len(pending_ids) != len(set(pending_ids)):
        errors.append(f"{label} pending_chains.flow_id 必须唯一")
    overlap = set(ready_ids) & set(pending_ids)
    if overlap:
        errors.append(f"{label} ready_chains 与 pending_chains 重叠：{sorted(overlap)}")

    observed_counts = {
        "ready_chain_count": len(set(ready_ids)),
        "generate_count": len(generate_ids),
        "explicit_exclusion_count": len(exclusion_ids),
        "pending_chain_count": len(set(pending_ids)),
    }
    for key, expected in observed_counts.items():
        if data.get(key) != expected:
            errors.append(f"{label} {key} 与明细不一致：{data.get(key)} != {expected}")
    if len(set(ready_ids)) != len(generate_ids) + len(exclusion_ids):
        errors.append(f"{label} 守恒失败：execution-ready != generated + explicitly-excluded")
    if generate_ids != required_flow_ids:
        errors.append(
            f"{label} 重算后的生成集合必须等于 required_chain_flows 分母："
            f"generate={sorted(generate_ids)}，required={sorted(required_flow_ids)}"
        )
    if filled_count > 0 and not generate_ids and not exclusion_ids:
        errors.append(f"{label} filled_count > 0 时不能以零生成、零明确排除通过")
    if (root / "05-executable-interface-case-set").exists() and status != "passed":
        errors.append(f"{label} 已进入执行级阶段时 status 必须为 passed，不能停留在 ready_for_generation")


def scenario_requires_chain(block: str) -> bool:
    chain_type = block_first_scalar(block, "chain_type")
    flow_required = is_yaml_true(block_first_scalar(block, "flow_generation_required") or "")
    return flow_required or chain_type == "e2e_flow_candidate"


def validate_required_chain_scenarios(text: str, errors: list[str], display: str) -> set[str]:
    flow_ids: list[str] = []
    for block in business_scenario_item_blocks(text):
        scenario_id = block_first_scalar(block, "scenario_id") or "UNKNOWN"
        chain_type = block_first_scalar(block, "chain_type")
        flow_required = is_yaml_true(block_first_scalar(block, "flow_generation_required") or "")
        if chain_type == "e2e_flow_candidate" and not flow_required:
            errors.append(f"{display} {scenario_id} 是 e2e_flow_candidate 时 flow_generation_required 必须为 true")
        if not scenario_requires_chain(block):
            continue
        flow_id = block_first_scalar(block, "flow_id")
        if not flow_id or invalid_coverage_point_value(flow_id):
            errors.append(f"{display} {scenario_id} 必须生成链路脚本但缺少有效 flow_id")
        else:
            flow_ids.append(flow_id)
        step_counts = yaml_int_values(block, "ordered_step_count")
        if not step_counts:
            errors.append(f"{display} {scenario_id} 必须生成链路脚本但缺少 ordered_step_count")
        elif step_counts[0] < 2:
            errors.append(f"{display} {scenario_id} 必须生成链路脚本但 ordered_step_count 小于 2：{step_counts[0]}")
        if "ordered_steps" not in block:
            errors.append(f"{display} {scenario_id} 必须生成链路脚本但缺少 ordered_steps")
        for marker in ("step_order", "interface", "source_ref"):
            if marker not in block:
                errors.append(f"{display} {scenario_id} ordered_steps 缺少字段：{marker}")
    if len(flow_ids) != len(set(flow_ids)):
        errors.append(f"{display} 必须生成链路脚本的 flow_id 存在重复：{flow_ids}")
    return set(flow_ids)


def validate_business_scenario_map_file(path: Path, errors: list[str], require_passed: bool, label: str | None = None) -> set[str]:
    display = label or path.name
    if not path.is_file():
        if require_passed:
            errors.append(f"缺少业务场景映射 sidecar：{path}")
        return set()
    try:
        text = read_text(path)
    except ValueError as exc:
        errors.append(str(exc))
        return set()

    require_yaml_top_level_keys(text, BUSINESS_SCENARIO_REQUIRED_KEYS, errors, display)
    schema_version = yaml_int_value(text, "schema_version", errors, display)
    if schema_version is not None and schema_version != 1:
        errors.append(f"{display} schema_version 不是 1：{schema_version}")
    stage = first_yaml_scalar(text, "stage")
    if stage != "business_scenario_mapping":
        errors.append(f"{display} stage 不匹配：{stage} != business_scenario_mapping")
    status = first_yaml_scalar(text, "status")
    if status not in {"passed", "blocked", "partial"}:
        errors.append(f"{display} status 非法或缺失：{status}")
    if require_passed:
        if status != "passed":
            errors.append(f"{display} status 不是 passed：{status}")
        next_stage_allowed = first_yaml_scalar(text, "next_stage_allowed")
        if next_stage_allowed is None or not is_yaml_true(next_stage_allowed):
            errors.append(f"{display} next_stage_allowed 不是 true：{next_stage_allowed}")
        if not yaml_section_has_sequence_items(text, "scenario_items"):
            errors.append(f"{display} passed 状态下 scenario_items 不能为空")
        require_yaml_empty_list(text, "blocking_issues", errors, display)
        for marker in BUSINESS_SCENARIO_REQUIRED_ITEM_MARKERS:
            if marker not in text:
                errors.append(f"{display} 缺少业务场景字段：{marker}")
        scenario_ids = yaml_scalar_values(text, "scenario_id")
        if len(scenario_ids) != len(set(scenario_ids)):
            errors.append(f"{display} scenario_id 存在重复：{scenario_ids}")
        required_flow_ids = validate_required_chain_scenarios(text, errors, display)
        descriptions = business_scenario_descriptions(text)
        if not descriptions:
            errors.append(f"{display} 缺少有效 business_description")
        for description in descriptions:
            if not has_chinese(description):
                errors.append(f"{display} business_description 必须使用中文：{description}")
            if re.search(r"\b(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b\s*/", description, re.IGNORECASE) and len(description) < 20:
                errors.append(f"{display} business_description 不能只写 method/path：{description}")
        for block in business_scenario_item_blocks(text):
            scenario_id = block_first_scalar(block, "scenario_id") or "UNKNOWN"
            description = block_first_scalar(block, "business_description") or ""
            business_domain = block_first_scalar(block, "business_domain") or ""
            executing_role = block_first_scalar(block, "executing_role") or ""
            if invalid_coverage_point_value(business_domain) or not has_chinese(business_domain):
                errors.append(f"{display} {scenario_id} business_domain 必须为中文业务域")
            if invalid_coverage_point_value(executing_role) or not has_chinese(executing_role):
                errors.append(f"{display} {scenario_id} executing_role 必须为中文执行角色")
            elif description and executing_role not in description:
                errors.append(f"{display} {scenario_id} business_description 必须包含执行角色：{executing_role}")
            if scenario_requires_chain(block) and looks_like_path_bucket_long_chain(
                business_domain,
                block_first_scalar(block, "scenario_name") or "",
                description,
            ):
                errors.append(f"{display} {scenario_id} 疑似按路径/接口前缀拼接链路候选，必须拆成真实业务场景")
        splittable_clusters = splittable_single_interface_clusters(business_scenario_items_from_yaml(text))
        if splittable_clusters:
            errors.append(
                f"{display} 存在可拆分多接口业务簇但仍全部按 single_interface 输出，"
                f"必须先按执行角色、业务动作、前置状态和预期业务结果拆成真实业务链路：{', '.join(splittable_clusters[:10])}"
            )
        for list_key in ("source_refs", "related_interfaces", "business_chain", "related_test_point_ids", "related_coverage_rule_ids"):
            values = yaml_scalar_values(text, list_key)
            if not values:
                errors.append(f"{display} 缺少业务场景列表字段：{list_key}")
            for value in values:
                if yaml_scalar_is_empty_list(value):
                    errors.append(f"{display} 业务场景列表字段不能为空：{list_key}")
        confidence_values = yaml_scalar_values(text, "confidence")
        if not confidence_values:
            errors.append(f"{display} 缺少 confidence")
        for value in confidence_values:
            if value not in {"high", "medium"}:
                errors.append(f"{display} confidence 必须为 high/medium 才能放行：{value}")
        blocker_values = yaml_scalar_values(text, "blockers")
        for value in blocker_values:
            if not yaml_scalar_is_empty_list(value):
                errors.append(f"{display} blockers 未清空：{value}")
    return required_flow_ids if require_passed else set()


def validate_business_scenario_doc_file(path: Path, errors: list[str], require_records: bool) -> None:
    if not path.is_file():
        if require_records:
            errors.append(f"缺少业务场景链路清单：{path}")
        return
    try:
        text = read_text(path)
    except ValueError as exc:
        errors.append(str(exc))
        return
    if require_records:
        for header in (
            "业务场景ID",
            "业务场景名称",
            "业务场景描述",
            "链路类型",
            "是否必须生成链路脚本",
            "flow_id",
            "步骤数",
            "来源",
            "业务链路",
            "接口链路",
            "关联测试点ID",
            "关联覆盖规则ID",
        ):
            if header not in text:
                errors.append(f"{path.name} 缺少字段：{header}")


def looks_like_path_bucket_long_chain(*values: str) -> bool:
    normalized_values = [normalize_yaml_value(value) for value in values if value]
    text = " ".join(normalized_values)
    if not normalized_values:
        return False
    generic_names = {
        "接口链路",
        "接口集合",
        "接口组合",
        "模块接口",
        "模块链路",
        "API集合",
        "API链路",
        "平台接口",
        "资源链路",
        "资源从业务处理到结果校验",
    }
    compact = re.sub(r"\s+", "", text)
    if compact in generic_names:
        return True
    label_text = " ".join(normalized_values[:2])
    if any(pattern.search(label_text) for pattern in BUSINESS_LONG_CHAIN_PATH_BUCKET_PATTERNS):
        return True
    description_text = " ".join(normalized_values[2:])
    return any(pattern.search(description_text) for pattern in BUSINESS_LONG_CHAIN_PATH_BUCKET_PATTERNS[2:])


def validate_business_long_chain_doc_file(path: Path, errors: list[str], require_records: bool) -> None:
    if not path.is_file():
        if require_records:
            errors.append(f"缺少业务长链路设计清单：{path}")
        return
    try:
        text = read_text(path)
    except ValueError as exc:
        errors.append(str(exc))
        return
    if require_records:
        for header in (
            "长链路ID",
            "设计级用例ID",
            "业务域",
            "业务场景",
            "执行角色",
            "接口链路",
            "来源",
            "覆盖状态",
            "可执行状态",
        ):
            if header not in text:
                errors.append(f"{path.name} 缺少字段：{header}")


def validate_business_long_chain_cases_file(path: Path, errors: list[str], require_passed: bool) -> None:
    if not path.is_file():
        if require_passed:
            errors.append(f"缺少业务长链路设计分母 sidecar：{path}")
        return
    try:
        text = read_text(path)
    except ValueError as exc:
        errors.append(str(exc))
        return

    require_yaml_top_level_keys(text, BUSINESS_LONG_CHAIN_REQUIRED_KEYS, errors, path.name)
    schema_version = yaml_int_value(text, "schema_version", errors, path.name)
    if schema_version is not None and schema_version != 1:
        errors.append(f"{path.name} schema_version 不是 1：{schema_version}")
    stage = first_yaml_scalar(text, "stage")
    if stage != BUSINESS_LONG_CHAIN_STAGE:
        errors.append(f"{path.name} stage 不匹配：{stage} != {BUSINESS_LONG_CHAIN_STAGE}")
    status = first_yaml_scalar(text, "status")
    if status not in {"passed", "blocked", "partial", "failed"}:
        errors.append(f"{path.name} status 非法或缺失：{status}")
    if require_passed:
        if status != "passed":
            errors.append(f"{path.name} status 不是 passed：{status}")
        next_stage_allowed = first_yaml_scalar(text, "next_stage_allowed")
        if next_stage_allowed is None or not is_yaml_true(next_stage_allowed):
            errors.append(f"{path.name} next_stage_allowed 不是 true：{next_stage_allowed}")
        require_yaml_empty_list(text, "missing_business_long_chain_ids", errors, path.name)
        require_yaml_empty_list(text, "blocking_issues", errors, path.name)
    denominator_scope = first_yaml_scalar(text, "denominator_scope")
    if denominator_scope != BUSINESS_LONG_CHAIN_DENOMINATOR_SCOPE:
        errors.append(
            f"{path.name} denominator_scope 不匹配："
            f"{denominator_scope} != {BUSINESS_LONG_CHAIN_DENOMINATOR_SCOPE}"
        )

    total = yaml_int_value(text, "business_long_chain_total", errors, path.name)
    covered = yaml_int_value(text, "business_long_chain_covered", errors, path.name)
    script_ready_total = yaml_int_value(text, "script_closed_loop_ready_total", errors, path.name)
    if total is not None and total < 0:
        errors.append(f"{path.name} business_long_chain_total 不能小于 0：{total}")
    if script_ready_total is not None and script_ready_total < 0:
        errors.append(f"{path.name} script_closed_loop_ready_total 不能小于 0：{script_ready_total}")
    if require_passed and total is not None and covered is not None and total != covered:
        errors.append(f"{path.name} 业务长链路覆盖计数不是 100%：{covered}/{total}")

    chain_blocks = yaml_sequence_raw_blocks(text, "chains", "chain_id")
    if total is not None and total != len(chain_blocks):
        errors.append(f"{path.name} chains 明细数量与 business_long_chain_total 不一致：{len(chain_blocks)} != {total}")
    chain_ids: list[str] = []
    for block in chain_blocks:
        chain_id = block_first_scalar(block, "chain_id") or "UNKNOWN"
        chain_ids.append(chain_id)
        for marker in BUSINESS_LONG_CHAIN_REQUIRED_ITEM_MARKERS:
            if marker not in block:
                errors.append(f"{path.name} {chain_id} 缺少业务长链路字段：{marker}")
        case_id = block_first_scalar(block, "case_id")
        priority = normalize_yaml_value(block_first_scalar(block, "priority")).lower()
        business_domain = block_first_scalar(block, "business_domain") or ""
        scenario_name = block_first_scalar(block, "scenario_name") or ""
        description = block_first_scalar(block, "business_description") or ""
        executing_role = block_first_scalar(block, "executing_role") or ""
        design_status = normalize_yaml_value(block_first_scalar(block, "design_status"))
        executable_status = normalize_yaml_value(block_first_scalar(block, "executable_status"))
        interfaces = block_list_values(block, "interfaces")
        source_refs = block_list_values(block, "source_refs")
        test_point_ids = block_list_values(block, "related_test_point_ids")
        coverage_rule_ids = block_list_values(block, "related_coverage_rule_ids")
        interface_counts = yaml_int_values(block, "interface_count")
        step_counts = yaml_int_values(block, "step_count")
        interface_count = interface_counts[0] if interface_counts else len(interfaces)
        step_count = step_counts[0] if step_counts else 0

        if invalid_coverage_point_value(chain_id) or invalid_coverage_point_value(case_id):
            errors.append(f"{path.name} {chain_id} chain_id/case_id 不能为空或占位")
        if require_passed and priority != "p0":
            errors.append(f"{path.name} {chain_id} 业务长链路设计用例必须为 p0：{priority}")
        if invalid_coverage_point_value(business_domain) or not has_chinese(business_domain):
            errors.append(f"{path.name} {chain_id} business_domain 必须为中文业务域")
        if invalid_coverage_point_value(scenario_name) or not has_chinese(scenario_name):
            errors.append(f"{path.name} {chain_id} scenario_name 必须为中文业务场景名称")
        if invalid_coverage_point_value(description) or not has_chinese(description):
            errors.append(f"{path.name} {chain_id} business_description 必须为中文真实业务场景")
        if invalid_coverage_point_value(executing_role) or not has_chinese(executing_role):
            errors.append(f"{path.name} {chain_id} executing_role 必须为中文执行角色")
        elif description and executing_role not in description:
            errors.append(f"{path.name} {chain_id} business_description 必须包含执行角色：{executing_role}")
        if looks_like_path_bucket_long_chain(business_domain, scenario_name, description):
            errors.append(f"{path.name} {chain_id} 疑似按路径/接口前缀拼接长链路，必须改为真实业务场景")
        if interface_count < LONG_CHAIN_INTERFACE_THRESHOLD and step_count < LONG_CHAIN_STEP_THRESHOLD:
            errors.append(
                f"{path.name} {chain_id} 不满足业务长链路阈值："
                f"interface_count={interface_count}，step_count={step_count}"
            )
        if len(interfaces) < LONG_CHAIN_INTERFACE_THRESHOLD and step_count < LONG_CHAIN_STEP_THRESHOLD:
            errors.append(f"{path.name} {chain_id} interfaces 少于 3 且未提供 5 步以上业务步骤")
        for list_key, values in (
            ("interfaces", interfaces),
            ("source_refs", source_refs),
            ("related_test_point_ids", test_point_ids),
            ("related_coverage_rule_ids", coverage_rule_ids),
        ):
            if not values:
                errors.append(f"{path.name} {chain_id} {list_key} 不能为空")
        if require_passed and design_status != "covered":
            errors.append(f"{path.name} {chain_id} design_status 必须为 covered：{design_status}")
        if executable_status not in BUSINESS_LONG_CHAIN_EXECUTABLE_STATUSES:
            errors.append(f"{path.name} {chain_id} executable_status 非法：{executable_status}")
    if len(chain_ids) != len(set(chain_ids)):
        errors.append(f"{path.name} chain_id 存在重复：{chain_ids}")


def parse_number(text: str) -> float | None:
    normalized = text.strip().replace(",", "")
    if re.fullmatch(r"\d+(?:\.\d+)?", normalized):
        return float(normalized)
    return None


def require_quality_gate_sections(text: str, errors: list[str], label: str) -> None:
    for name, keywords in QUALITY_MARKER_GROUPS.items():
        if not collect_sections(text, keywords):
            errors.append(f"{label} 缺少可识别的交接门禁章节：{name}")


def read_sidecar(path: Path, errors: list[str], label: str) -> str:
    require(path.is_file(), errors, f"{label} 缺少结构化 sidecar：{path.name}")
    if not path.is_file():
        return ""
    try:
        return read_text(path)
    except ValueError as exc:
        errors.append(str(exc))
        return ""


def first_yaml_scalar(text: str, key: str) -> str | None:
    values = yaml_scalar_values(text, key)
    return values[0] if values else None


def first_top_level_yaml_scalar(text: str, key: str) -> str | None:
    for line in text.splitlines():
        match = YAML_TOP_LEVEL_SCALAR_RE.match(line)
        if match and match.group(1) == key:
            return match.group(2).strip().strip("\"'")
    return None


def yaml_top_level_keys(text: str) -> set[str]:
    return set(YAML_TOP_LEVEL_KEY_RE.findall(text))


def require_yaml_top_level_keys(text: str, keys: tuple[str, ...], errors: list[str], label: str) -> None:
    present = yaml_top_level_keys(text)
    for key in keys:
        if key not in present:
            errors.append(f"{label} 缺少 schema 顶层字段：{key}")


def require_stage_status_schema_keys(text: str, errors: list[str], label: str, expected_stage: str) -> None:
    present = yaml_top_level_keys(text)
    base_keys = ("schema_version", "stage", "status", "next_stage_allowed", "blocking_issues")
    for key in base_keys:
        if key not in present:
            errors.append(f"{label} 缺少 schema 顶层字段：{key}")
    if {"input_paths", "output_paths", "gate_checks"} <= present:
        return
    if expected_stage == "pre_doc_analysis" and {"source_files", "stage_results", "output_files"} <= present:
        return
    for key in ("input_paths", "output_paths", "gate_checks"):
        if key not in present:
            errors.append(f"{label} 缺少 schema 顶层字段：{key}")


def require_coverage_matrix_schema_keys(text: str, errors: list[str], label: str, expected_stage: str) -> None:
    present = yaml_top_level_keys(text)
    base_keys = ("schema_version", "stage", "coverage_summary")
    for key in base_keys:
        if key not in present:
            errors.append(f"{label} 缺少 schema 顶层字段：{key}")
    if {"coverage_items", "missing_items", "upstream_downstream_mappings"} <= present:
        return
    if expected_stage == "pre_doc_analysis" and "coverage_objects" in present:
        return
    for key in ("coverage_items", "missing_items", "upstream_downstream_mappings"):
        if key not in present:
            errors.append(f"{label} 缺少 schema 顶层字段：{key}")


def yaml_int_value(text: str, key: str, errors: list[str], label: str) -> int | None:
    values = yaml_int_values(text, key)
    if not values:
        errors.append(f"{label} 缺少可解析的整数字段：{key}")
        return None
    if len(set(values)) != 1:
        errors.append(f"{label} 字段 {key} 多处取值不一致：{values}")
        return None
    return values[0]


def require_yaml_empty_list(text: str, key: str, errors: list[str], label: str) -> None:
    values = yaml_scalar_values(text, key)
    if not values:
        errors.append(f"{label} 缺少空缺失列表字段：{key}")
        return
    if not yaml_scalar_is_empty_list(values[0]):
        errors.append(f"{label} 缺失列表未清空：{key}={values[0]}")


def yaml_scalar_is_empty_list(value: str) -> bool:
    normalized = value.strip().strip("\"'").strip()
    return normalized == "[]"


def yaml_scalar_list_items(value: str) -> list[str]:
    normalized = value.strip()
    if not (normalized.startswith("[") and normalized.endswith("]")):
        return []
    inner = normalized[1:-1].strip()
    if not inner:
        return []
    return [item.strip().strip("\"'") for item in split_top_level_csv(inner)]


def yaml_section_has_sequence_items(text: str, key: str) -> bool:
    values = yaml_scalar_values(text, key)
    if values and values[0].strip():
        return bool(yaml_scalar_list_items(values[0]))
    section = yaml_section(text, key)
    return any(re.match(r"^\s*-\s+", line) for line in section.splitlines())


def parse_yaml_rate(value: str | None) -> float | None:
    if value is None:
        return None
    normalized = value.strip().strip("\"'").rstrip("%").strip()
    if re.fullmatch(r"\d+(?:\.\d+)?", normalized):
        return float(normalized)
    return None


def validate_status_section_passed(
    text: str,
    section_key: str,
    errors: list[str],
    label: str,
    allowed_passed: set[str] | None = None,
    require_items: bool = True,
) -> None:
    allowed = allowed_passed or {"passed", "通过"}
    values = yaml_scalar_values(text, section_key)
    if values and yaml_scalar_is_empty_list(values[0]):
        if require_items:
            errors.append(f"{label} {section_key} 不能为空")
        return
    section = yaml_section(text, section_key)
    status_values = yaml_scalar_values(section, "status")
    if not status_values:
        if require_items:
            errors.append(f"{label} {section_key} 缺少 status 明细")
        return
    for status in status_values:
        if status.strip().strip("\"'") not in allowed:
            errors.append(f"{label} {section_key}.status 不是 passed：{status}")


def normalize_yaml_value(value: str | None) -> str:
    return (value or "").strip().strip("\"'").strip()


def yaml_value_is_missing(value: str | None, list_value: bool = False) -> bool:
    normalized = normalize_yaml_value(value)
    if not normalized:
        return True
    if normalized in {"[]", "{}"}:
        return True
    if normalized in COVERAGE_POINT_PLACEHOLDERS:
        return True
    if list_value and normalized.startswith("[") and normalized.endswith("]"):
        return not yaml_scalar_list_items(normalized)
    return False


def extract_yaml_sequence_blocks(text: str, section_key: str) -> list[dict[str, str]]:
    section = yaml_section(text, section_key)
    blocks: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    pending_list_key: str | None = None
    for raw_line in section.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        inline_match = re.match(r"^-\s*\{(.+)\}\s*$", stripped)
        if inline_match:
            if current is not None:
                blocks.append(current)
                current = None
            mapping = parse_inline_mapping(inline_match.group(1))
            if mapping:
                blocks.append(mapping)
            pending_list_key = None
            continue
        item_match = re.match(r"^-\s+([A-Za-z0-9_]+)\s*:\s*(.*?)\s*$", stripped)
        if item_match:
            if current is not None:
                blocks.append(current)
            value = item_match.group(2).strip().strip("\"'")
            current = {item_match.group(1): value}
            pending_list_key = item_match.group(1) if not value else None
            continue
        if current is None:
            continue
        scalar_match = re.match(r"^([A-Za-z0-9_]+)\s*:\s*(.*?)\s*$", stripped)
        if scalar_match:
            value = scalar_match.group(2).strip().strip("\"'")
            current[scalar_match.group(1)] = value
            pending_list_key = scalar_match.group(1) if not value else None
            continue
        list_item_match = re.match(r"^-\s+(.+?)\s*$", stripped)
        if list_item_match and pending_list_key:
            value = list_item_match.group(1).strip().strip("\"'")
            previous = current.get(pending_list_key, "")
            current[pending_list_key] = ",".join(item for item in (previous, value) if item)
    if current is not None:
        blocks.append(current)
    return blocks


def coverage_type_for_total_key(total_key: str) -> str | None:
    mapping = {
        "object_total": "object",
        "test_point_total": "test_point",
        "rule_total": "rule",
        "main_flow_total": "main_flow",
        "contract_rule_total": "contract_rule",
        "status_code_total": "status_code",
        "p0_p1_total": "p0_p1",
        "design_case_total": "design_case",
        "executable_case_total": "executable_case",
        "coverage_rule_total": "coverage_rule",
        "source_interface_total": "source_interface",
        "source_contract_rule_total": "source_contract_rule",
        "source_business_rule_total": "source_business_rule",
        "source_error_code_total": "source_error_code",
        "source_db_side_effect_total": "source_db_side_effect",
        "source_scenario_total": "source_scenario",
        "chain_scenario_total": "chain_scenario",
        "chain_function_total": "chain_function",
        "chain_process_total": "chain_process",
    }
    return mapping.get(total_key)


def extract_mapping_blocks(text: str) -> list[dict[str, str]]:
    return extract_yaml_sequence_blocks(text, "upstream_downstream_mappings")


def validate_coverage_item_alignment(
    text: str,
    errors: list[str],
    label: str,
    count_pairs: tuple[tuple[str, str], ...],
) -> None:
    items = extract_coverage_item_blocks(text)
    mappings = extract_mapping_blocks(text)
    mapped_upstream_ids = {
        normalize_yaml_value(mapping.get("upstream_id"))
        for mapping in mappings
        if normalize_yaml_value(mapping.get("mapping_status")) == "mapped"
    }
    for total_key, _ in count_pairs:
        expected_values = yaml_int_values(text, total_key)
        if not expected_values:
            continue
        expected_total = expected_values[0]
        coverage_type = coverage_type_for_total_key(total_key)
        if not coverage_type:
            continue
        typed_items = [item for item in items if normalize_yaml_value(item.get("coverage_type")) == coverage_type]
        coverage_ids = [normalize_yaml_value(item.get("coverage_id")) for item in typed_items]
        coverage_ids = [coverage_id for coverage_id in coverage_ids if coverage_id]
        if len(coverage_ids) != len(set(coverage_ids)):
            errors.append(f"{label} coverage_items 存在重复 coverage_id：{coverage_type}")
        if len(set(coverage_ids)) != expected_total:
            errors.append(
                f"{label} {coverage_type} 覆盖明细数量与 {total_key} 不一致："
                f"{len(set(coverage_ids))} != {expected_total}"
            )
        for item in typed_items:
            coverage_id = normalize_yaml_value(item.get("coverage_id")) or "UNKNOWN"
            if yaml_value_is_missing(item.get("coverage_id")):
                errors.append(f"{label} {coverage_type} 覆盖项缺少 coverage_id")
            if normalize_yaml_value(item.get("status")) != "covered":
                errors.append(f"{label} 覆盖项 {coverage_id} status 不是 covered：{item.get('status')}")
            if yaml_value_is_missing(item.get("evidence_refs"), list_value=True):
                errors.append(f"{label} 覆盖项 {coverage_id} 缺少 evidence_refs")
        missing_mapping_ids = sorted(set(coverage_ids) - mapped_upstream_ids)
        if missing_mapping_ids:
            errors.append(f"{label} upstream_downstream_mappings 缺少覆盖项映射：{missing_mapping_ids}")


def validate_coverage_release_details(
    text: str,
    errors: list[str],
    label: str,
    expected_stage: str,
    count_pairs: tuple[tuple[str, str], ...],
) -> None:
    top_level_keys = yaml_top_level_keys(text)
    legacy_pre_doc = (
        expected_stage == "pre_doc_analysis"
        and "coverage_objects" in top_level_keys
        and "coverage_items" not in top_level_keys
    )
    summary_block = yaml_key_block(text, "coverage_summary")
    coverage_rate = parse_yaml_rate(scalar_from_block(summary_block, "coverage_rate"))
    if coverage_rate is None:
        errors.append(f"{label} coverage_summary.coverage_rate 缺失或不可解析")
    elif coverage_rate != 100:
        errors.append(f"{label} coverage_summary.coverage_rate 不是 100：{coverage_rate:g}")

    total_sum = 0
    for total_key, _ in count_pairs:
        values = yaml_int_values(text, total_key)
        if values:
            total_sum += values[0]

    coverage_items_values = yaml_scalar_values(text, "coverage_items")
    coverage_items_empty = bool(coverage_items_values and yaml_scalar_is_empty_list(coverage_items_values[0]))
    coverage_section = yaml_section(text, "coverage_items")
    coverage_statuses = yaml_scalar_values(coverage_section, "status")
    if total_sum > 0 and not legacy_pre_doc and (coverage_items_empty or not coverage_statuses):
        errors.append(f"{label} coverage_items 为空，不能证明非零分母的覆盖明细")
    for status in coverage_statuses:
        if status.strip().strip("\"'") != "covered":
            errors.append(f"{label} coverage_items.status 不是 covered：{status}")

    if not legacy_pre_doc:
        require_yaml_empty_list(text, "missing_items", errors, label)

    mapping_values = yaml_scalar_values(text, "upstream_downstream_mappings")
    mapping_empty = bool(mapping_values and yaml_scalar_is_empty_list(mapping_values[0]))
    mapping_section = yaml_section(text, "upstream_downstream_mappings")
    mapping_statuses = yaml_scalar_values(mapping_section, "mapping_status")
    if total_sum > 0 and not legacy_pre_doc and (mapping_empty or not mapping_statuses):
        errors.append(f"{label} upstream_downstream_mappings 为空，不能证明非零分母的上下游映射")
    for status in mapping_statuses:
        if status.strip().strip("\"'") != "mapped":
            errors.append(f"{label} upstream_downstream_mappings.mapping_status 不是 mapped：{status}")
    if not legacy_pre_doc:
        validate_coverage_item_alignment(text, errors, label, count_pairs)


def validate_required_chain_independent_coverage(
    text: str,
    errors: list[str],
    label: str,
    required_flow_ids: set[str],
    generated_count_key: str | None = None,
    require_item_mappings: bool = False,
) -> None:
    if not required_flow_ids:
        return
    text = textwrap_dedent_yaml_block(text)

    denominator_values = [
        value.strip().strip("\"'")
        for key in ("denominator_scope", "coverage_denominator", "coverage_scope")
        for value in yaml_scalar_values(text, key)
    ]
    if "long_chain_only" not in denominator_values:
        errors.append(f"{label} 必须声明长链路覆盖率独立计算：denominator_scope/coverage_denominator=long_chain_only")

    parsed_totals: dict[str, int] = {}
    for total_key, covered_key in CHAIN_COVERAGE_PAIRS:
        total = yaml_int_value(text, total_key, errors, label)
        covered = yaml_int_value(text, covered_key, errors, label)
        if total is None or covered is None:
            continue
        parsed_totals[total_key] = total
        if total <= 0:
            errors.append(f"{label} {total_key} 必须大于 0，不能把长链路覆盖率混入单接口覆盖率")
        if total != covered:
            errors.append(f"{label} 长链路覆盖计数不是 100%：{covered_key}/{total_key} = {covered}/{total}")
    scenario_total = parsed_totals.get("chain_scenario_total")
    if scenario_total is not None and scenario_total < len(required_flow_ids):
        errors.append(
            f"{label} chain_scenario_total 小于上游必需 flow 数："
            f"{scenario_total} < {len(required_flow_ids)}"
        )
    for key in CHAIN_COVERAGE_MISSING_LISTS:
        require_yaml_empty_list(text, key, errors, label)
    require_yaml_empty_list(text, "missing_required_flow_ids", errors, label)
    required_count = yaml_int_value(text, "required_chain_flow_count", errors, label)
    if required_count is not None and required_count != len(required_flow_ids):
        errors.append(
            f"{label} required_chain_flow_count 与必测 flow 数不一致："
            f"{required_count} != {len(required_flow_ids)}"
        )
    if generated_count_key:
        generated_count = yaml_int_value(text, generated_count_key, errors, label)
        if generated_count is not None and generated_count != len(required_flow_ids):
            errors.append(
                f"{label} {generated_count_key} 与必测 flow 数不一致："
                f"{generated_count} != {len(required_flow_ids)}"
            )
    validate_chain_coverage_items(text, errors, label, required_flow_ids)
    if require_item_mappings:
        validate_chain_coverage_item_mappings(text, errors, label)


def textwrap_dedent_yaml_block(text: str) -> str:
    lines = text.splitlines()
    indents = [len(line) - len(line.lstrip(" ")) for line in lines if line.strip()]
    if not indents:
        return text
    min_indent = min(indents)
    if min_indent <= 0:
        return text
    return "\n".join(line[min_indent:] if len(line) >= min_indent else line for line in lines)


def extract_coverage_item_blocks(text: str) -> list[dict[str, str]]:
    return extract_yaml_sequence_blocks(text, "coverage_items")


def validate_chain_coverage_items(
    text: str,
    errors: list[str],
    label: str,
    required_flow_ids: set[str],
) -> None:
    if not required_flow_ids:
        return
    items = extract_coverage_item_blocks(text)
    chain_items = [item for item in items if item.get("coverage_type") in {"chain_scenario", "chain_function", "chain_process"}]
    if not chain_items:
        errors.append(f"{label} coverage_items 缺少长链路覆盖明细：chain_scenario/chain_function/chain_process")
        return
    for item in chain_items:
        coverage_id = item.get("coverage_id", "UNKNOWN")
        if item.get("status") != "covered":
            errors.append(f"{label} 长链路覆盖项 {coverage_id} status 不是 covered：{item.get('status')}")
        if not item.get("evidence_refs"):
            errors.append(f"{label} 长链路覆盖项 {coverage_id} 缺少 evidence_refs")
    scenario_items = [item for item in chain_items if item.get("coverage_type") == "chain_scenario"]
    scenario_ids = {item.get("flow_id") or item.get("coverage_id") for item in scenario_items}
    missing_flow_ids = sorted(flow_id for flow_id in required_flow_ids if flow_id not in scenario_ids)
    if missing_flow_ids:
        errors.append(f"{label} chain_scenario 覆盖明细缺少上游必需 flow_id：{missing_flow_ids}")
    for coverage_type, total_key in (
        ("chain_scenario", "chain_scenario_total"),
        ("chain_function", "chain_function_total"),
        ("chain_process", "chain_process_total"),
    ):
        expected_values = yaml_int_values(text, total_key)
        if not expected_values:
            continue
        actual_ids = {
            item.get("coverage_id", "")
            for item in chain_items
            if item.get("coverage_type") == coverage_type and item.get("coverage_id")
        }
        if len(actual_ids) != expected_values[0]:
            errors.append(
                f"{label} {coverage_type} 覆盖明细数量与 {total_key} 不一致："
                f"{len(actual_ids)} != {expected_values[0]}"
            )


def validate_chain_coverage_item_mappings(text: str, errors: list[str], label: str) -> None:
    chain_items = [
        item
        for item in extract_coverage_item_blocks(text)
        if item.get("coverage_type") in {"chain_scenario", "chain_function", "chain_process"}
    ]
    chain_coverage_ids = {
        normalize_yaml_value(item.get("coverage_id"))
        for item in chain_items
        if normalize_yaml_value(item.get("coverage_id"))
    }
    if not chain_coverage_ids:
        return
    mapped_upstream_ids = {
        normalize_yaml_value(mapping.get("upstream_id"))
        for mapping in extract_mapping_blocks(text)
        if normalize_yaml_value(mapping.get("mapping_status")) == "mapped"
    }
    missing_mapping_ids = sorted(chain_coverage_ids - mapped_upstream_ids)
    if missing_mapping_ids:
        errors.append(f"{label} upstream_downstream_mappings 缺少长链路覆盖项映射：{missing_mapping_ids}")


def validate_stage_status_sidecar(
    text: str,
    errors: list[str],
    label: str,
    expected_stage: str,
    require_passed: bool,
) -> None:
    require_stage_status_schema_keys(text, errors, label, expected_stage)
    schema_version = yaml_int_value(text, "schema_version", errors, label)
    if schema_version is not None and schema_version != 1:
        errors.append(f"{label} schema_version 不是 1：{schema_version}")

    stage = first_yaml_scalar(text, "stage")
    if stage != expected_stage:
        errors.append(f"{label} stage 不匹配：{stage} != {expected_stage}")

    status = first_yaml_scalar(text, "status")
    if status not in SIDECAR_STATUS_VALUES:
        errors.append(f"{label} status 非法或缺失：{status}")
    elif require_passed and status != "passed":
        errors.append(f"{label} status 不是 passed：{status}")

    if require_passed:
        next_stage_allowed = first_yaml_scalar(text, "next_stage_allowed")
        if next_stage_allowed is None or not is_yaml_true(next_stage_allowed):
            errors.append(f"{label} next_stage_allowed 不是 true：{next_stage_allowed}")
        require_yaml_empty_list(text, "blocking_issues", errors, label)
        if "gate_checks" in yaml_top_level_keys(text):
            validate_status_section_passed(text, "gate_checks", errors, label)
        elif "stage_results" in yaml_top_level_keys(text):
            validate_status_section_passed(
                text,
                "stage_results",
                errors,
                label,
                allowed_passed={"passed", "通过", "测试点覆盖率100%", "接口测试用例设计覆盖率100%"},
                require_items=False,
            )


def validate_coverage_sidecar(
    text: str,
    errors: list[str],
    label: str,
    expected_stage: str,
    count_pairs: tuple[tuple[str, str], ...],
    missing_lists: tuple[str, ...],
    require_passed: bool,
) -> None:
    require_coverage_matrix_schema_keys(text, errors, label, expected_stage)
    schema_version = yaml_int_value(text, "schema_version", errors, label)
    if schema_version is not None and schema_version != 1:
        errors.append(f"{label} schema_version 不是 1：{schema_version}")

    stage = first_yaml_scalar(text, "stage")
    if stage != expected_stage:
        errors.append(f"{label} stage 不匹配：{stage} != {expected_stage}")

    if not require_passed:
        return

    for total_key, covered_key in count_pairs:
        total = yaml_int_value(text, total_key, errors, label)
        covered = yaml_int_value(text, covered_key, errors, label)
        if total is None or covered is None:
            continue
        if total <= 0:
            errors.append(f"{label} {total_key} 必须大于 0，不能用 0/0 声明 100% 覆盖")
        if total != covered:
            errors.append(f"{label} 覆盖计数不是 100%：{covered_key}/{total_key} = {covered}/{total}")

    for key in missing_lists:
        require_yaml_empty_list(text, key, errors, label)
    validate_coverage_release_details(text, errors, label, expected_stage, count_pairs)


def validate_stage_sidecars(
    base: Path,
    errors: list[str],
    label: str,
    expected_stage: str,
    count_pairs: tuple[tuple[str, str], ...],
    missing_lists: tuple[str, ...],
    require_passed: bool,
) -> None:
    stage_status_text = read_sidecar(base / "stage_status.yaml", errors, label)
    coverage_matrix_text = read_sidecar(base / "coverage_matrix.yaml", errors, label)
    if stage_status_text:
        validate_stage_status_sidecar(stage_status_text, errors, f"{label}/stage_status.yaml", expected_stage, require_passed)
    if coverage_matrix_text:
        validate_coverage_sidecar(
            coverage_matrix_text,
            errors,
            f"{label}/coverage_matrix.yaml",
            expected_stage,
            count_pairs,
            missing_lists,
            require_passed,
        )


def section_exists(text: str, keyword: str) -> bool:
    for match in SECTION_HEADING_RE.finditer(text):
        title = normalize_heading(match.group(1))
        if keyword in title:
            return True
    return False


def validate_doc_entry_quality(entry_dir: Path, errors: list[str]) -> None:
    report_path = entry_dir / "03_skill执行报告.md"
    design_path = entry_dir / "01_接口测试用例设计文档.md"
    contract_path = entry_dir / "02_接口结构化契约清单.md"

    try:
        report_text = read_text(report_path)
        design_text = read_text(design_path)
        contract_text = read_text(contract_path)
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
        return

    for section_name in DOC_ENTRY_REQUIRED_REPORT_SECTIONS:
        if not section_exists(report_text, section_name):
            errors.append(f"文档入口 03_skill执行报告.md 缺少阶段1准出章节：{section_name}")

    require(section_exists(report_text, "二阶段测试点分析报告"), errors, "文档入口 03_skill执行报告.md 缺少二阶段测试点分析报告章节")
    for section_name in DOC_ENTRY_TEST_POINT_SECTIONS:
        if not section_exists(report_text, section_name):
            errors.append(f"文档入口二阶段测试点拆分缺少章节或表：{section_name}")

    combined_entry_text = "\n".join([report_text, design_text, contract_text])
    for marker in DOC_ENTRY_TRACE_MARKERS:
        if marker not in combined_entry_text:
            errors.append(f"文档入口缺少可追溯覆盖字段：{marker}")

    coverage_text = collect_sections(report_text, ("覆盖率准出摘要", "覆盖矩阵", "覆盖结论"))
    conclusion_text = collect_sections(report_text, ("交付结论", "准出结论", "放行结论", "发布结论"))
    if not coverage_text:
        errors.append("文档入口缺少覆盖率准出证据，不能进入测试用例生成阶段")
    elif not ("100" in coverage_text or "已覆盖" in coverage_text):
        errors.append("文档入口覆盖率准出证据缺少 100% 或已覆盖结论")
    if coverage_text:
        validate_coverage_numbers(coverage_text, errors, "文档入口覆盖率准出摘要")
        for percent_text in PERCENT_PATTERN.findall(coverage_text):
            if float(percent_text) != 100:
                errors.append(f"文档入口覆盖率不是 100%：{percent_text}%")

    conclusion_block = "\n".join([coverage_text, conclusion_text])
    if any(pattern.search(conclusion_block) for pattern in DENY_PATTERNS):
        errors.append("文档入口准出结论不允许声明 100% 覆盖或不允许进入下一阶段")
    if "是否允许" in conclusion_block and not ALLOW_100_PATTERN.search(conclusion_block):
        errors.append("文档入口准出结论缺少允许声明 100% 覆盖的明确结论")
    if not any(marker in conclusion_text for marker in ("结论：通过", "结果：通过", "允许进入下一阶段", "允许声明")):
        errors.append("文档入口交付结论缺少明确通过或允许进入下一阶段的结论")

    validate_stage_sidecars(
        entry_dir,
        errors,
        "文档入口",
        "pre_doc_analysis",
        PRE_DOC_COVERAGE_PAIRS,
        PRE_DOC_MISSING_LISTS,
        require_passed=True,
    )


def collect_json_status_values(value: object) -> list[str]:
    values: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in {"status", "result", "quality_status", "conclusion"}:
                values.append(str(item).strip())
            values.extend(collect_json_status_values(item))
    elif isinstance(value, list):
        for item in value:
            values.extend(collect_json_status_values(item))
    return values


def validate_source_entry_quality(entry_dir: Path, errors: list[str]) -> None:
    quality_path = entry_dir / "source-api-quality-report.json"
    try:
        quality_text = read_text(quality_path)
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
        return
    try:
        quality_data = json.loads(quality_text)
    except json.JSONDecodeError as exc:
        errors.append(f"源码入口 source-api-quality-report.json 不是合法 JSON：{exc}")
        return

    status_values = collect_json_status_values(quality_data)
    if not status_values:
        errors.append("源码入口 source-api-quality-report.json 缺少 status/result 质检结论")
        return
    for value in status_values:
        normalized = value.lower()
        if normalized in SOURCE_FAILED_STATUS_VALUES:
            errors.append(f"源码入口质检结论未通过：{value}")


def validate_source_artifact_manifest(entry_dir: Path, errors: list[str]) -> None:
    path = entry_dir / "source_api_fact_artifacts.yaml"
    require(path.is_file(), errors, "源码入口缺少 source_api_fact_artifacts.yaml")
    if not path.is_file():
        return
    try:
        text = read_text(path)
    except ValueError as exc:
        errors.append(str(exc))
        return
    for artifact_name in SOURCE_ARTIFACT_REQUIRED_NAMES:
        if artifact_name not in text:
            errors.append(f"源码入口 source_api_fact_artifacts.yaml 缺少必需 artifact：{artifact_name}")


def normalize_http_method(value: object) -> str | None:
    method = str(value).strip().upper()
    return method if method in HTTP_METHODS else None


def normalize_endpoint_path(value: object) -> str | None:
    path = str(value).strip().strip("\"'`")
    if not path.startswith("/"):
        return None
    path = re.sub(r"\s.*$", "", path)
    path = re.sub(r"/+", "/", path)
    if len(path) > 1:
        path = path.rstrip("/")
    return path


def endpoint_key(method: object, path: object) -> str | None:
    normalized_method = normalize_http_method(method)
    normalized_path = normalize_endpoint_path(path)
    if not normalized_method or not normalized_path:
        return None
    return f"{normalized_method} {normalized_path}"


def extract_markdown_table_endpoints(text: str) -> set[str]:
    endpoints: set[str] = set()
    header: list[str] | None = None
    method_index: int | None = None
    path_index: int | None = None
    for raw_line in text.splitlines():
        cells = split_markdown_row(raw_line)
        if not cells:
            continue
        normalized_cells = [cell.strip().lower() for cell in cells]
        if any(cell in {"method", "http method", "请求方法", "接口方法"} for cell in normalized_cells) and any(
            cell in {"path", "url", "接口路径", "请求路径"} for cell in normalized_cells
        ):
            header = normalized_cells
            method_index = next(
                (index for index, cell in enumerate(header) if cell in {"method", "http method", "请求方法", "接口方法"}),
                None,
            )
            path_index = next(
                (index for index, cell in enumerate(header) if cell in {"path", "url", "接口路径", "请求路径"}),
                None,
            )
            continue
        if header is None or method_index is None or path_index is None:
            continue
        if len(cells) <= max(method_index, path_index):
            continue
        key = endpoint_key(cells[method_index], cells[path_index])
        if key:
            endpoints.add(key)
    return endpoints


def extract_text_endpoints(text: str) -> set[str]:
    endpoints = extract_markdown_table_endpoints(text)
    method_pattern = "|".join(HTTP_METHODS)
    for method, path in re.findall(rf"\b({method_pattern})\b\s+(`?/[^`\s|，。；;]+`?)", text, re.IGNORECASE):
        key = endpoint_key(method, path)
        if key:
            endpoints.add(key)
    return endpoints


def collect_json_endpoint_keys(value: object, endpoints: set[str]) -> None:
    if isinstance(value, dict):
        method = None
        path = None
        for key, item in value.items():
            normalized_key = str(key).lower()
            if normalized_key in {"method", "http_method", "httpmethod", "request_method", "请求方法"}:
                method = item
            elif normalized_key in {"path", "url", "uri", "request_path", "接口路径", "请求路径"}:
                path = item
        key = endpoint_key(method, path) if method is not None and path is not None else None
        if key:
            endpoints.add(key)
        for item in value.values():
            collect_json_endpoint_keys(item, endpoints)
    elif isinstance(value, list):
        for item in value:
            collect_json_endpoint_keys(item, endpoints)


def empty_endpoint_detail() -> dict[str, set[str]]:
    return {"statuses": set(), "errors": set(), "fields": set()}


def split_detail_values(value: object) -> set[str]:
    values: set[str] = set()
    if isinstance(value, dict):
        for key in ("name", "field", "field_name", "code", "value", "status", "状态码", "错误码", "字段"):
            if key in value:
                values.update(split_detail_values(value[key]))
        return values
    if isinstance(value, list):
        for item in value:
            values.update(split_detail_values(item))
        return values
    text = str(value).strip().strip("\"'`")
    if not text or text in {"-", "无", "暂无", "UNKNOWN", "N/A", "NA", "null", "None"}:
        return values
    for item in re.split(r"[,，、;；\s]+", text):
        normalized = item.strip().strip("\"'`")
        if normalized and normalized not in {"-", "无", "暂无"}:
            values.add(normalized)
    return values


def normalized_detail_key(key: object) -> str:
    return str(key).strip().lower().replace("-", "_").replace(" ", "_")


def collect_json_endpoint_details(value: object, details: dict[str, dict[str, set[str]]]) -> None:
    if isinstance(value, dict):
        method = None
        path = None
        for key, item in value.items():
            normalized_key = normalized_detail_key(key)
            if normalized_key in {"method", "http_method", "httpmethod", "request_method", "请求方法"}:
                method = item
            elif normalized_key in {"path", "url", "uri", "request_path", "接口路径", "请求路径"}:
                path = item
        endpoint = endpoint_key(method, path) if method is not None and path is not None else None
        if endpoint:
            detail = details.setdefault(endpoint, empty_endpoint_detail())
            for key, item in value.items():
                normalized_key = normalized_detail_key(key)
                if normalized_key in STATUS_DETAIL_KEYS:
                    detail["statuses"].update(split_detail_values(item))
                elif normalized_key in ERROR_DETAIL_KEYS:
                    detail["errors"].update(split_detail_values(item))
                elif normalized_key in FIELD_DETAIL_KEYS:
                    detail["fields"].update(split_detail_values(item))
        for item in value.values():
            collect_json_endpoint_details(item, details)
    elif isinstance(value, list):
        for item in value:
            collect_json_endpoint_details(item, details)


def extract_markdown_table_endpoint_details(text: str) -> dict[str, dict[str, set[str]]]:
    details: dict[str, dict[str, set[str]]] = {}
    header: list[str] | None = None
    indexes: dict[str, int] = {}
    for raw_line in text.splitlines():
        cells = split_markdown_row(raw_line)
        if not cells:
            continue
        normalized_cells = [cell.strip().lower().replace("-", "_").replace(" ", "_") for cell in cells]
        if any(cell in {"method", "http_method", "请求方法", "接口方法"} for cell in normalized_cells) and any(
            cell in {"path", "url", "接口路径", "请求路径"} for cell in normalized_cells
        ):
            header = normalized_cells
            indexes = {}
            for index, cell in enumerate(header):
                if cell in {"method", "http_method", "请求方法", "接口方法"}:
                    indexes["method"] = index
                elif cell in {"path", "url", "接口路径", "请求路径"}:
                    indexes["path"] = index
                elif cell in STATUS_DETAIL_KEYS:
                    indexes["statuses"] = index
                elif cell in ERROR_DETAIL_KEYS:
                    indexes["errors"] = index
                elif cell in FIELD_DETAIL_KEYS:
                    indexes["fields"] = index
            continue
        if header is None or "method" not in indexes or "path" not in indexes:
            continue
        if len(cells) <= max(indexes["method"], indexes["path"]):
            continue
        endpoint = endpoint_key(cells[indexes["method"]], cells[indexes["path"]])
        if not endpoint:
            continue
        detail = details.setdefault(endpoint, empty_endpoint_detail())
        for detail_key in ("statuses", "errors", "fields"):
            index = indexes.get(detail_key)
            if index is not None and len(cells) > index:
                detail[detail_key].update(split_detail_values(cells[index]))
    return details


def merge_endpoint_details(target: dict[str, dict[str, set[str]]], source: dict[str, dict[str, set[str]]]) -> None:
    for endpoint, detail in source.items():
        target_detail = target.setdefault(endpoint, empty_endpoint_detail())
        for key in ("statuses", "errors", "fields"):
            target_detail[key].update(detail.get(key, set()))


def extract_source_entry_endpoints(source_entry: Path, errors: list[str]) -> set[str]:
    endpoints: set[str] = set()
    facts_path = source_entry / "source-api-facts.json"
    if facts_path.is_file():
        try:
            facts_data = json.loads(read_text(facts_path))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"源码入口 source-api-facts.json 无法解析接口事实：{exc}")
        else:
            collect_json_endpoint_keys(facts_data, endpoints)
    for filename in ("02_接口结构化契约清单.md", "01_接口测试用例设计文档.md"):
        path = source_entry / filename
        if path.is_file():
            try:
                endpoints.update(extract_text_endpoints(read_text(path)))
            except (OSError, ValueError) as exc:
                errors.append(str(exc))
    return endpoints


def extract_doc_entry_endpoints(doc_entry: Path, errors: list[str]) -> set[str]:
    endpoints: set[str] = set()
    for filename in ("02_接口结构化契约清单.md", "01_接口测试用例设计文档.md", "03_skill执行报告.md"):
        path = doc_entry / filename
        if not path.is_file():
            continue
        try:
            endpoints.update(extract_text_endpoints(read_text(path)))
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
    return endpoints


def extract_source_entry_details(source_entry: Path, errors: list[str]) -> dict[str, dict[str, set[str]]]:
    details: dict[str, dict[str, set[str]]] = {}
    facts_path = source_entry / "source-api-facts.json"
    if facts_path.is_file():
        try:
            facts_data = json.loads(read_text(facts_path))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"源码入口 source-api-facts.json 无法解析接口细节：{exc}")
        else:
            collect_json_endpoint_details(facts_data, details)
    for filename in ("02_接口结构化契约清单.md", "01_接口测试用例设计文档.md"):
        path = source_entry / filename
        if path.is_file():
            try:
                merge_endpoint_details(details, extract_markdown_table_endpoint_details(read_text(path)))
            except (OSError, ValueError) as exc:
                errors.append(str(exc))
    return details


def extract_doc_entry_details(doc_entry: Path, errors: list[str]) -> dict[str, dict[str, set[str]]]:
    details: dict[str, dict[str, set[str]]] = {}
    for filename in ("02_接口结构化契约清单.md", "01_接口测试用例设计文档.md", "03_skill执行报告.md"):
        path = doc_entry / filename
        if not path.is_file():
            continue
        try:
            merge_endpoint_details(details, extract_markdown_table_endpoint_details(read_text(path)))
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
    return details


def validate_entry_alignment(root: Path, errors: list[str]) -> None:
    doc_entry = root / "01-pre-doc-analysis"
    source_entry = root / "02-source-api-facts" / "docs" / "source-facts"
    if not doc_entry.is_dir() or not source_entry.is_dir():
        return
    doc_endpoints = extract_doc_entry_endpoints(doc_entry, errors)
    source_endpoints = extract_source_entry_endpoints(source_entry, errors)
    if not doc_endpoints or not source_endpoints:
        return
    doc_only = sorted(doc_endpoints - source_endpoints)
    source_only = sorted(source_endpoints - doc_endpoints)
    if doc_only or source_only:
        errors.append(
            "入口一致性冲突：文档入口与源码入口 method/path 不一致；"
            f"文档独有={doc_only or '[]'}；源码独有={source_only or '[]'}"
        )
    doc_details = extract_doc_entry_details(doc_entry, errors)
    source_details = extract_source_entry_details(source_entry, errors)
    for endpoint in sorted(doc_endpoints & source_endpoints):
        doc_detail = doc_details.get(endpoint, empty_endpoint_detail())
        source_detail = source_details.get(endpoint, empty_endpoint_detail())
        for detail_key, label in (("statuses", "状态码"), ("errors", "错误码"), ("fields", "字段")):
            doc_values = doc_detail.get(detail_key, set())
            source_values = source_detail.get(detail_key, set())
            if doc_values and source_values and doc_values != source_values:
                errors.append(
                    f"入口一致性冲突：{endpoint} 的{label}不一致；"
                    f"文档入口={sorted(doc_values)}；源码入口={sorted(source_values)}"
                )


def validate_coverage_numbers(coverage_text: str, errors: list[str], label: str) -> None:
    for numerator_text, denominator_text in RATIO_PATTERN.findall(coverage_text):
        numerator = float(numerator_text)
        denominator = float(denominator_text)
        if denominator <= 0 or numerator != denominator:
            errors.append(f"{label} 覆盖分子/分母不是 100%：{numerator_text}/{denominator_text}")

    for raw_line in coverage_text.splitlines():
        cells = split_markdown_row(raw_line)
        if len(cells) < 4:
            continue
        if any(header in cell for cell in cells for header in ("分子", "分母", "结果", "是否达标")):
            continue
        numerator = parse_number(cells[1])
        denominator = parse_number(cells[2])
        if numerator is not None and denominator is not None:
            if denominator <= 0 or numerator != denominator:
                errors.append(f"{label} 覆盖表分子/分母不是 100%：{' | '.join(cells)}")
        if any(cell == "否" for cell in cells):
            errors.append(f"{label} 覆盖表存在未达标结论：{' | '.join(cells)}")


def validate_coverage_response_gate(text: str, errors: list[str], label: str) -> None:
    require_quality_gate_sections(text, errors, label)
    quality_text = collect_sections(text, ("质检结论", "质量结论"))
    coverage_text = collect_sections(text, ("覆盖矩阵", "覆盖结论", "覆盖率准出摘要"))
    blocker_text = collect_sections(text, ("阻塞项",))
    conclusion_text = collect_sections(text, ("准出结论", "交付结论", "放行结论", "发布结论"))

    if "不通过" in quality_text:
        errors.append(f"{label} 质检结论为不通过，不能继续后续阶段")
    if not ("100" in coverage_text or "已覆盖" in coverage_text):
        errors.append(f"{label} 覆盖结论缺少 100% 或已覆盖证据")
    if any(term in coverage_text for term in COVERAGE_BLOCKING_TERMS):
        errors.append(f"{label} 覆盖矩阵存在未达标状态：覆盖不足/未覆盖/待补充/阻塞")
    validate_coverage_numbers(coverage_text, errors, label)
    for percent_text in PERCENT_PATTERN.findall(coverage_text):
        if float(percent_text) != 100:
            errors.append(f"{label} 覆盖率不是 100%：{percent_text}%")
    if has_meaningful_blocker(blocker_text):
        errors.append(f"{label} 阻塞项未清空，不能继续后续阶段")
    if any(term in conclusion_text for term in CONCLUSION_BLOCKING_TERMS):
        errors.append(f"{label} 准出结论未通过或存在覆盖不足/阻塞")
    if any(pattern.search(conclusion_text) for pattern in DENY_PATTERNS):
        errors.append(f"{label} 准出结论不允许声明 100% 覆盖或不允许进入下一阶段")
    if "是否允许" in conclusion_text and not ALLOW_100_PATTERN.search(conclusion_text):
        errors.append(f"{label} 准出结论缺少允许声明 100% 覆盖的明确结论")
    if not any(marker in conclusion_text for marker in ("结论：通过", "结果：通过", "允许进入下一阶段", "允许声明")):
        errors.append(f"{label} 准出结论缺少明确通过结论")


def validate_entry_outputs(
    root: Path,
    errors: list[str],
    required: bool = True,
    require_release: bool = False,
    allow_partial_entry: bool = False,
) -> bool:
    doc_entry = root / "01-pre-doc-analysis"
    source_entry = root / "02-source-api-facts" / "docs" / "source-facts"
    has_doc_entry = doc_entry.exists()
    has_source_entry = source_entry.exists()
    if required:
        require(has_doc_entry or has_source_entry, errors, "至少需要一个入口产物：01-pre-doc-analysis 或 02-source-api-facts/docs/source-facts")
    if has_doc_entry:
        require(doc_entry.is_dir(), errors, f"文档入口路径不是目录：{doc_entry}")
        if doc_entry.is_dir():
            if allow_partial_entry and not require_release:
                existing_entry_docs = [name for name in ENTRY_DOCS if (doc_entry / name).is_file()]
                require(bool(existing_entry_docs), errors, f"文档入口质检失败时至少需要保留一个入口阶段报告文件：{doc_entry}")
                require_files(doc_entry, tuple(existing_entry_docs), errors, "文档入口")
            else:
                require_files(doc_entry, ENTRY_DOCS, errors, "文档入口")
            if require_release:
                validate_doc_entry_quality(doc_entry, errors)
    if has_source_entry:
        require(source_entry.is_dir(), errors, f"源码入口路径不是目录：{source_entry}")
        if source_entry.is_dir():
            if allow_partial_entry and not require_release:
                existing_entry_docs = [name for name in ENTRY_DOCS if (source_entry / name).is_file()]
                require(bool(existing_entry_docs), errors, f"源码入口质检失败时至少需要保留一个入口阶段报告文件：{source_entry}")
                require_files(source_entry, tuple(existing_entry_docs), errors, "源码入口")
            else:
                require_files(source_entry, ENTRY_DOCS, errors, "源码入口")
            if not allow_partial_entry or require_release:
                require((source_entry / "source-api-facts.json").is_file(), errors, "源码入口缺少 source-api-facts.json")
                require((source_entry / "source-api-quality-report.json").is_file(), errors, "源码入口缺少 source-api-quality-report.json")
            if (source_entry / "source-api-facts.json").is_file():
                try:
                    read_text(source_entry / "source-api-facts.json")
                except ValueError as exc:
                    errors.append(str(exc))
            if require_release:
                validate_source_entry_quality(source_entry, errors)
                validate_source_artifact_manifest(source_entry, errors)
                validate_stage_sidecars(
                    source_entry,
                    errors,
                    "源码入口",
                    "source_api_facts",
                    SOURCE_COVERAGE_PAIRS,
                    SOURCE_MISSING_LISTS,
                    require_passed=True,
                )
    return has_doc_entry or has_source_entry


def validate_data_model(root: Path, errors: list[str]) -> None:
    path = root / DATA_MODEL_REQUIRED[0] / DATA_MODEL_REQUIRED[1]
    require(path.is_file(), errors, f"执行级或脚本阶段缺少数据模型输入：{path}")
    if path.is_file():
        try:
            text = read_text(path)
        except ValueError as exc:
            errors.append(str(exc))
            return
        for name, markers in DATA_MODEL_EXECUTION_MARKER_GROUPS.items():
            if not data_model_group_has_confirmed_content(text, markers):
                errors.append(f"执行级或脚本阶段数据模型缺少执行闭环信息：{name}")


def validate_database_mcp_alignment(root: Path, errors: list[str]) -> None:
    evidence_path = root / DATABASE_MCP_EVIDENCE_REQUIRED[0] / DATABASE_MCP_EVIDENCE_REQUIRED[1]
    alignment_path = root / SOURCE_DB_ALIGNMENT_REQUIRED[0] / SOURCE_DB_ALIGNMENT_REQUIRED[1]
    report_path = root / SOURCE_DB_ALIGNMENT_REPORT_REQUIRED[0] / SOURCE_DB_ALIGNMENT_REPORT_REQUIRED[1]
    data_model_path = root / DATA_MODEL_REQUIRED[0] / DATA_MODEL_REQUIRED[1]
    if not (evidence_path.exists() or alignment_path.exists() or report_path.exists()):
        return

    require(evidence_path.is_file(), errors, f"数据库 MCP 证据索引缺失：{evidence_path}")
    require(alignment_path.is_file(), errors, f"源码-数据库一致性 sidecar 缺失：{alignment_path}")
    require(report_path.is_file(), errors, f"源码-数据库一致性报告缺失：{report_path}")
    require(data_model_path.is_file(), errors, f"数据库 MCP 归一化后缺少数据模型：{data_model_path}")

    evidence_text = ""
    alignment_text = ""
    for label, path in (
        ("数据库 MCP 证据索引", evidence_path),
        ("源码-数据库一致性 sidecar", alignment_path),
        ("源码-数据库一致性报告", report_path),
        ("数据模型", data_model_path),
    ):
        if not path.is_file():
            continue
        try:
            text = read_text(path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if label == "数据库 MCP 证据索引":
            evidence_text = text
        if label == "源码-数据库一致性 sidecar":
            alignment_text = text

    if evidence_text:
        require_yaml_top_level_keys(evidence_text, DATABASE_MCP_EVIDENCE_REQUIRED_KEYS, errors, "数据库 MCP 证据索引")
        schema_version = yaml_int_value(evidence_text, "schema_version", errors, "数据库 MCP 证据索引")
        if schema_version is not None and schema_version != 1:
            errors.append(f"数据库 MCP 证据索引 schema_version 不是 1：{schema_version}")
        stage = first_yaml_scalar(evidence_text, "stage")
        if stage != "database_mcp_data_model_normalization":
            errors.append(f"数据库 MCP 证据索引 stage 不匹配：{stage} != database_mcp_data_model_normalization")
        status = first_yaml_scalar(evidence_text, "status")
        require(status == "passed", errors, f"数据库 MCP 证据索引 status 不是 passed：{status}")
        if not yaml_section_has_sequence_items(evidence_text, "evidence_items"):
            errors.append("数据库 MCP 证据索引 evidence_items 为空或无法解析")
        evidence_levels = set(yaml_scalar_values(evidence_text, "evidence_level"))
        for required_level in DATABASE_MCP_REQUIRED_EVIDENCE_LEVELS:
            if required_level not in evidence_levels:
                errors.append(f"数据库 MCP 证据索引缺少 evidence_level：{required_level}")
        source_status_values = yaml_scalar_values(evidence_text, "source_status")
        blocked_source_statuses = [value for value in source_status_values if value in {"missing", "conflict", "blocked"}]
        if blocked_source_statuses:
            errors.append(f"数据库 MCP 证据索引存在未确认 source_status：{blocked_source_statuses}")
        require_yaml_empty_list(evidence_text, "conflict_items", errors, "数据库 MCP 证据索引")
        require_yaml_empty_list(evidence_text, "blocking_issues", errors, "数据库 MCP 证据索引")

    if alignment_text:
        schema_version = yaml_int_value(alignment_text, "schema_version", errors, "源码-数据库一致性 sidecar")
        if schema_version is not None and schema_version != 1:
            errors.append(f"源码-数据库一致性 sidecar schema_version 不是 1：{schema_version}")
        status = first_yaml_scalar(alignment_text, "status")
        require(status == "passed", errors, f"源码-数据库一致性 sidecar status 不是 passed：{status}")
        next_stage_allowed = first_yaml_scalar(alignment_text, "next_stage_allowed")
        require(next_stage_allowed is not None and is_yaml_true(next_stage_allowed), errors, "源码-数据库一致性 sidecar next_stage_allowed 不是 true")
        check_ids = set(yaml_scalar_values(alignment_text, "check_id"))
        for required_check in SOURCE_DB_ALIGNMENT_REQUIRED_CHECKS:
            if required_check not in check_ids:
                errors.append(f"源码-数据库一致性 sidecar 缺少 alignment check：{required_check}")
        blocked_check_statuses = [
            value for value in yaml_scalar_values(alignment_text, "status") if value in {"blocked", "failed"}
        ]
        if blocked_check_statuses:
            errors.append(f"源码-数据库一致性 sidecar 存在未通过检查状态：{blocked_check_statuses}")
        for key in (
            "missing_tables",
            "missing_columns",
            "incompatible_columns",
            "unresolved_side_effects",
            "unresolved_relationships",
            "missing_cleanup_keys",
            "blocking_issues",
        ):
            require_yaml_empty_list(alignment_text, key, errors, "源码-数据库一致性 sidecar")


def text_contains_any(text: str, terms: tuple[str, ...]) -> bool:
    normalized = text.lower()
    return any(term.lower() in normalized for term in terms)


def validate_runtime_execution_config_blocker_artifacts(
    root: Path,
    report_text: str,
    stage_status: str | None,
    target_depth: str | None,
    errors: list[str],
) -> None:
    if stage_status != "BLOCKED_NEED_EXECUTION_INPUT" or target_depth not in {"executable", "framework"}:
        return
    if not text_contains_any(report_text, RUNTIME_CONFIG_BLOCKER_TERMS):
        return

    template_path = root / RUNTIME_EXECUTION_CONFIG_TEMPLATE_REQUIRED[0] / RUNTIME_EXECUTION_CONFIG_TEMPLATE_REQUIRED[1]
    guide_path = root / RUNTIME_EXECUTION_CONFIG_GUIDE_REQUIRED[0] / RUNTIME_EXECUTION_CONFIG_GUIDE_REQUIRED[1]
    missing_fields_path = root / RUNTIME_EXECUTION_CONFIG_MISSING_FIELDS[0] / RUNTIME_EXECUTION_CONFIG_MISSING_FIELDS[1]

    require(template_path.is_file(), errors, f"缺少执行配置待填写模板：{template_path}")
    require(guide_path.is_file(), errors, f"缺少前置执行配置待填写说明：{guide_path}")

    if template_path.is_file():
        try:
            read_text(template_path)
        except ValueError as exc:
            errors.append(str(exc))

    if guide_path.is_file():
        try:
            guide_text = read_text(guide_path)
        except ValueError as exc:
            errors.append(str(exc))
        else:
            for section in RUNTIME_CONFIG_GUIDE_REQUIRED_SECTIONS:
                if section not in guide_text:
                    errors.append(f"前置执行配置待填写.md 缺少章节：{section}")

    if text_contains_any(report_text, RUNTIME_CONFIG_KNOWN_MISSING_TERMS):
        require(missing_fields_path.is_file(), errors, f"缺少执行配置缺失字段清单：{missing_fields_path}")
    if missing_fields_path.is_file():
        try:
            missing_fields_text = read_text(missing_fields_path)
        except ValueError as exc:
            errors.append(str(exc))
        else:
            has_missing_items = any(
                yaml_section_has_sequence_items(missing_fields_text, key)
                for key in ("missing_fields", "required_missing_fields", "fields")
            )
            if not has_missing_items:
                errors.append("runtime_execution_config.missing_fields.yaml 缺少可解析的缺失字段列表")


def validate_source_data_model_mcp_attempt(
    root: Path,
    report_text: str,
    stage_status: str | None,
    target_depth: str | None,
    source_entry: Path,
    doc_entry: Path,
    errors: list[str],
) -> None:
    if stage_status != "BLOCKED_NEED_EXECUTION_INPUT" or target_depth not in {"executable", "framework"}:
        return
    if not source_entry.exists() or doc_entry.exists():
        return
    data_model_path = root / DATA_MODEL_REQUIRED[0] / DATA_MODEL_REQUIRED[1]
    evidence_path = root / DATABASE_MCP_EVIDENCE_REQUIRED[0] / DATABASE_MCP_EVIDENCE_REQUIRED[1]
    alignment_path = root / SOURCE_DB_ALIGNMENT_REQUIRED[0] / SOURCE_DB_ALIGNMENT_REQUIRED[1]
    report_path = root / SOURCE_DB_ALIGNMENT_REPORT_REQUIRED[0] / SOURCE_DB_ALIGNMENT_REPORT_REQUIRED[1]
    if data_model_path.exists() or evidence_path.exists() or alignment_path.exists() or report_path.exists():
        return
    if not text_contains_any(report_text, ("数据模型", "data model")):
        return
    if not text_contains_any(report_text, DB_MCP_ATTEMPT_TERMS) or not text_contains_any(report_text, DB_MCP_BLOCKER_TERMS):
        errors.append(
            "源码入口执行级/脚本目标缺少数据模型时，00_流水线执行报告.md 必须证明已尝试数据库 MCP "
            "且说明不可用、不可读、未授权或无法确认身份/图谱/清理证据"
        )


def yaml_scalar_values(text: str, key: str) -> list[str]:
    values: list[str] = []
    for line in text.splitlines():
        match = YAML_SCALAR_RE.match(line)
        if match and match.group(1) == key:
            values.append(match.group(2).strip().strip("\"'"))
    return values


def yaml_int_values(text: str, key: str) -> list[int]:
    values: list[int] = []
    for value in yaml_scalar_values(text, key):
        if re.fullmatch(r"\d+", value):
            values.append(int(value))
    return values


def yaml_section(text: str, key: str) -> str:
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if re.match(rf"^{re.escape(key)}\s*:\s*$", line):
            start = index + 1
            break
    if start is None:
        return ""
    end = len(lines)
    for index in range(start, len(lines)):
        if re.match(r"^[A-Za-z0-9_]+\s*:", lines[index]):
            end = index
            break
    return "\n".join(lines[start:end])


def is_yaml_true(value: str) -> bool:
    return value.strip().lower() in {"true", "yes", "是", "passed"}


def split_top_level_csv(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    bracket_depth = 0
    quote_char = ""
    for char in text:
        if quote_char:
            current.append(char)
            if char == quote_char:
                quote_char = ""
            continue
        if char in {"'", '"'}:
            quote_char = char
            current.append(char)
            continue
        if char == "[":
            bracket_depth += 1
        elif char == "]" and bracket_depth > 0:
            bracket_depth -= 1
        if char == "," and bracket_depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    if current:
        parts.append("".join(current).strip())
    return [part for part in parts if part]


def parse_inline_mapping(text: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for part in split_top_level_csv(text):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        mapping[key.strip()] = value.strip().strip("\"'")
    return mapping


def extract_pytest_mapping_blocks(section: str) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw_line in section.splitlines():
        if re.match(r"^\s*-\s+flow_id\s*:", raw_line):
            if current is not None:
                blocks.append(current)
                current = None
            continue
        item_match = re.match(r"^\s*-\s+executable_case_id\s*:\s*(.+?)\s*$", raw_line)
        if item_match:
            if current is not None:
                blocks.append(current)
            current = {"executable_case_id": item_match.group(1).strip().strip("\"'")}
            continue
        if current is None:
            continue
        scalar_match = YAML_SCALAR_RE.match(raw_line)
        if scalar_match:
            current[scalar_match.group(1)] = scalar_match.group(2).strip().strip("\"'")
    if current is not None:
        blocks.append(current)
    for inline_match in re.finditer(r"^\s*mappings\s*:\s*\[(.*)\]\s*$", section, re.MULTILINE):
        for object_text in re.findall(r"\{([^{}]+)\}", inline_match.group(1)):
            block = parse_inline_mapping(object_text)
            if block:
                blocks.append(block)
    return blocks


def extract_pytest_flow_mapping_blocks(section: str) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw_line in section.splitlines():
        if re.match(r"^\s*-\s+executable_case_id\s*:", raw_line):
            if current is not None:
                blocks.append(current)
                current = None
            continue
        item_match = re.match(r"^\s*-\s+flow_id\s*:\s*(.+?)\s*$", raw_line)
        if item_match:
            if current is not None:
                blocks.append(current)
            current = {"flow_id": item_match.group(1).strip().strip("\"'")}
            continue
        if current is None:
            continue
        scalar_match = YAML_SCALAR_RE.match(raw_line)
        if scalar_match:
            current[scalar_match.group(1)] = scalar_match.group(2).strip().strip("\"'")
    if current is not None:
        blocks.append(current)
    for inline_match in re.finditer(r"^\s*mappings\s*:\s*\[(.*)\]\s*$", section, re.MULTILINE):
        for object_text in re.findall(r"\{([^{}]+)\}", inline_match.group(1)):
            block = parse_inline_mapping(object_text)
            if block.get("flow_id"):
                blocks.append(block)
    return blocks


def validate_case_list_case_blocks(case_yaml_text: str, errors: list[str], label: str) -> None:
    case_blocks = extract_yaml_sequence_blocks(case_yaml_text, "cases")
    if not case_blocks:
        errors.append(f"{label} passed 状态下 cases 缺少可解析用例明细")
        return
    seen_case_ids: set[str] = set()
    for index, case in enumerate(case_blocks, start=1):
        case_label = normalize_yaml_value(case.get("case_id")) or f"第 {index} 条用例"
        for field in CASE_LIST_YAML_REQUIRED_CASE_MARKERS:
            value = case.get(field)
            if field == "confidence_cap_reasons":
                if value is None:
                    errors.append(f"{label} {case_label} 缺少有效设计级用例字段：{field}")
                continue
            if yaml_value_is_missing(value, list_value=field in CASE_LIST_YAML_REQUIRED_LIST_FIELDS):
                errors.append(f"{label} {case_label} 缺少有效设计级用例字段：{field}")
        case_id = normalize_yaml_value(case.get("case_id"))
        if case_id:
            if case_id in seen_case_ids:
                errors.append(f"{label} case_id 重复：{case_id}")
            seen_case_ids.add(case_id)
        method = normalize_yaml_value(case.get("method")).upper()
        if method and method not in HTTP_METHODS:
            errors.append(f"{label} {case_label} method 非法：{case.get('method')}")
        path = normalize_yaml_value(case.get("path"))
        if path and not path.startswith("/"):
            errors.append(f"{label} {case_label} path 必须以 / 开头：{path}")
        priority = normalize_yaml_value(case.get("priority")).lower()
        if priority and priority not in COVERAGE_POINT_PRIORITY_VALUES:
            errors.append(f"{label} {case_label} priority 必须为 p0/p1/p2：{case.get('priority')}")


def confidence_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if 0.0 <= number <= 1.0 else None


def confidence_band(score: float) -> str:
    if score < 0.60:
        return "insufficient"
    if score < 0.70:
        return "contract_confirmed"
    if score < 0.80:
        return "request_confirmed"
    if score < 0.90:
        return "scenario_confirmed"
    return "runtime_closed"


def confidence_level(score: float) -> str:
    if score < 0.70:
        return "low"
    if score < 0.90:
        return "medium"
    return "high"


def calculate_confidence_score(dimensions: dict[str, Any], cap_reasons: list[str]) -> float | None:
    weighted_total = 0.0
    applicable_weight = 0.0
    for dimension, weight in CONFIDENCE_DIMENSION_WEIGHTS.items():
        value = dimensions.get(dimension)
        if value == "not_applicable":
            continue
        number = confidence_number(value)
        if number is None:
            return None
        weighted_total += number * weight
        applicable_weight += weight
    if applicable_weight <= 0:
        return None
    raw_score = weighted_total / applicable_weight
    active_caps = [CONFIDENCE_CAPS[reason] for reason in cap_reasons if reason in CONFIDENCE_CAPS]
    capped_score = min([raw_score, *active_caps]) if active_caps else raw_score
    return int((capped_score + 1e-9) * 20) / 20


def validate_case_confidence(
    item: dict[str, Any],
    label: str,
    errors: list[str],
    *,
    require_runtime_dimension: bool,
    enforce_live_boundary: bool,
) -> bool:
    required_fields = (
        "confidence_score",
        "confidence_level",
        "confidence_band",
        "confidence_scope",
        "scenario_relevance",
        "confidence_dimensions",
        "confidence_reason_codes",
        "confidence_cap_reasons",
        "confidence_evidence_refs",
    )
    missing = [field for field in required_fields if field not in item]
    if missing:
        errors.append(f"{label} 缺少置信度字段：{missing}")
        return False

    score = confidence_number(item.get("confidence_score"))
    if score is None:
        errors.append(f"{label} confidence_score 必须是 0 到 1 的数字")
        return False
    if abs(score * 20 - round(score * 20)) > 1e-8:
        errors.append(f"{label} confidence_score 必须按 0.05 量化：{score}")

    scope = str(item.get("confidence_scope") or "").strip()
    if scope not in CONFIDENCE_SCOPES:
        errors.append(f"{label} confidence_scope 非法：{scope}")
    relevance = str(item.get("scenario_relevance") or "").strip()
    if relevance not in CONFIDENCE_SCENARIO_RELEVANCE:
        errors.append(f"{label} scenario_relevance 非法：{relevance}")

    dimensions = item.get("confidence_dimensions")
    if not isinstance(dimensions, dict):
        errors.append(f"{label} confidence_dimensions 必须是对象")
        return False
    for dimension in CONFIDENCE_DIMENSION_WEIGHTS:
        value = dimensions.get(dimension)
        if value == "not_applicable":
            if require_runtime_dimension or scope != "design":
                errors.append(f"{label} {dimension} 仅可在 design 范围使用 not_applicable")
        elif confidence_number(value) is None:
            errors.append(f"{label} confidence_dimensions.{dimension} 必须是 0 到 1 的数字")

    reason_codes = item.get("confidence_reason_codes")
    if not isinstance(reason_codes, list) or not reason_codes:
        errors.append(f"{label} confidence_reason_codes 必须是非空列表")
        reason_codes = []
    else:
        for reason in reason_codes:
            if not isinstance(reason, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", reason):
                errors.append(f"{label} confidence_reason_codes 包含非法原因码：{reason}")

    cap_reasons = item.get("confidence_cap_reasons")
    if not isinstance(cap_reasons, list):
        errors.append(f"{label} confidence_cap_reasons 必须是列表")
        cap_reasons = []
    for reason in cap_reasons:
        if reason not in CONFIDENCE_CAPS:
            errors.append(f"{label} confidence_cap_reasons 包含未知硬上限原因：{reason}")
        if reason not in reason_codes:
            errors.append(f"{label} 硬上限原因未同步到 confidence_reason_codes：{reason}")

    evidence_refs = item.get("confidence_evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs:
        errors.append(f"{label} confidence_evidence_refs 必须是非空列表")
    else:
        for evidence_ref in evidence_refs:
            if invalid_coverage_point_value(str(evidence_ref or "")):
                errors.append(f"{label} confidence_evidence_refs 包含无效引用：{evidence_ref}")

    if dimensions.get("runtime_repeatability") == "not_applicable" and "RUNTIME_NOT_VERIFIED" not in cap_reasons:
        errors.append(f"{label} runtime_repeatability=not_applicable 时必须声明 RUNTIME_NOT_VERIFIED 硬上限")

    expected_score = calculate_confidence_score(dimensions, cap_reasons)
    if expected_score is not None and abs(score - expected_score) > 1e-8:
        errors.append(f"{label} confidence_score 不可重算：声明 {score:g}，期望 {expected_score:g}")
    expected_level = confidence_level(score)
    if item.get("confidence_level") != expected_level:
        errors.append(f"{label} confidence_level 与分数不一致：期望 {expected_level}")
    expected_band = confidence_band(score)
    if item.get("confidence_band") != expected_band:
        errors.append(f"{label} confidence_band 与分数不一致：期望 {expected_band}")
    if score >= 0.90 and (
        dimensions.get("runtime_repeatability") == "not_applicable"
        or "RUNTIME_NOT_VERIFIED" in cap_reasons
    ):
        errors.append(f"{label} runtime_closed 缺少运行时闭合证据")

    automation_decision = str(item.get("automation_decision") or "").strip()
    explicitly_non_live = item.get("live_pytest_release_ready") is False or automation_decision in CONFIDENCE_NON_LIVE_DECISIONS
    if enforce_live_boundary and score < 0.70 and not explicitly_non_live:
        errors.append(f"{label} 低置信度用例不能进入 live 分母，需显式 non-live/manual 决策")
    return not missing


def validate_case_list_confidence(path: Path, errors: list[str]) -> None:
    payload = read_yaml_file(path, errors, path.name)
    if not isinstance(payload, dict):
        return
    for index, item in enumerate(payload.get("cases") or [], start=1):
        if not isinstance(item, dict):
            errors.append(f"{path.name} 第 {index} 条 cases 不是对象")
            continue
        case_id = str(item.get("case_id") or f"第 {index} 条用例")
        validate_case_confidence(
            item,
            f"{path.name} {case_id}",
            errors,
            require_runtime_dimension=False,
            enforce_live_boundary=False,
        )


def validate_case_list_yaml_file(path: Path, errors: list[str], require_passed: bool) -> None:
    require(path.is_file(), errors, f"缺少设计级用例机器可读产物：{path}")
    if not path.is_file():
        return
    try:
        text = read_text(path)
    except ValueError as exc:
        errors.append(str(exc))
        return
    require_yaml_top_level_keys(text, CASE_LIST_YAML_REQUIRED_KEYS, errors, path.name)
    schema_version = yaml_int_value(text, "schema_version", errors, path.name)
    if schema_version is not None and schema_version != 1:
        errors.append(f"{path.name} schema_version 不是 1：{schema_version}")
    stage = first_yaml_scalar(text, "stage")
    if stage != "interface_testcase_generation":
        errors.append(f"{path.name} stage 不匹配：{stage} != interface_testcase_generation")
    status = first_yaml_scalar(text, "status")
    if status not in {"passed", "blocked", "coverage_insufficient"}:
        errors.append(f"{path.name} status 非法或缺失：{status}")
    if require_passed:
        if status != "passed":
            errors.append(f"{path.name} status 不是 passed：{status}")
        if re.search(r"(?m)^cases\s*:\s*\[\]\s*$", text) or not yaml_section_has_sequence_items(text, "cases"):
            errors.append(f"{path.name} passed 状态下 cases 不能为空")
        quality_gate_block = yaml_key_block(text, "quality_gate")
        quality_gate_status = gate_pass_status_from_block(quality_gate_block)
        if quality_gate_status != "passed":
            errors.append(f"{path.name} quality_gate.status/result 不是 passed：{quality_gate_status}")
        coverage_summary_block = yaml_key_block(text, "coverage_summary")
        coverage_rate = parse_yaml_rate(scalar_from_block(coverage_summary_block, "coverage_rate"))
        if coverage_rate is None:
            errors.append(f"{path.name} coverage_summary.coverage_rate 缺失或不可解析")
        elif coverage_rate != 100:
            errors.append(f"{path.name} coverage_summary.coverage_rate 不是 100：{coverage_rate:g}")
        require_yaml_empty_list(text, "blocking_issues", errors, path.name)
        for marker in CASE_LIST_YAML_REQUIRED_CASE_MARKERS:
            if marker not in text:
                errors.append(f"{path.name} 缺少设计级用例字段：{marker}")
        validate_case_list_case_blocks(text, errors, path.name)
        validate_case_list_confidence(path, errors)



def validate_generation_status(
    text: str,
    errors: list[str],
    required_flow_ids: set[str] | None = None,
    long_chain_required: bool = False,
) -> None:
    required_flow_ids = required_flow_ids or set()
    for field in GENERATION_STATUS_FIELDS:
        require(field in text, errors, f"generation_status.yaml 缺少覆盖到 pytest 的映射字段：{field}")

    coverage_section = yaml_section(text, "coverage_traceability")
    pytest_section = yaml_section(text, "pytest_collection_mapping")
    chain_section = yaml_section(text, "chain_script_coverage")
    require(bool(coverage_section), errors, "generation_status.yaml 缺少 coverage_traceability 明细")
    require(bool(pytest_section), errors, "generation_status.yaml 缺少 pytest_collection_mapping 明细")
    require(bool(chain_section), errors, "generation_status.yaml 缺少 chain_script_coverage 明细")

    for section_name, section_text in (
        ("coverage_traceability", coverage_section),
        ("pytest_collection_mapping", pytest_section),
    ):
        status_values = yaml_scalar_values(section_text, "status")
        if not status_values or status_values[0] != "passed":
            errors.append(f"generation_status.yaml {section_name}.status 不是 passed")

    for missing_key in ("missing_executable_mappings", "missing_pytest_mappings"):
        values = yaml_scalar_values(coverage_section, missing_key)
        if not values:
            errors.append(f"generation_status.yaml coverage_traceability 缺少 {missing_key}")
        elif values[0] != "[]":
            errors.append(f"generation_status.yaml coverage_traceability.{missing_key} 未清空：{values[0]}")

    executable_counts = yaml_int_values(text, "executable_case_count")
    e2e_counts = yaml_int_values(text, "e2e_flow_case_count")
    collected_counts = yaml_int_values(text, "collected_test_count")
    if not executable_counts:
        errors.append("generation_status.yaml 缺少可解析的 executable_case_count")
        executable_count = None
    elif len(set(executable_counts)) != 1:
        errors.append(f"generation_status.yaml executable_case_count 多处不一致：{executable_counts}")
        executable_count = None
    else:
        executable_count = executable_counts[0]

    if not e2e_counts:
        e2e_count = 0
    elif len(set(e2e_counts)) != 1:
        errors.append(f"generation_status.yaml e2e_flow_case_count 多处不一致：{e2e_counts}")
        e2e_count = None
    else:
        e2e_count = e2e_counts[0]

    if not collected_counts:
        errors.append("generation_status.yaml 缺少可解析的 collected_test_count")
        collected_count = None
    elif len(set(collected_counts)) != 1:
        errors.append(f"generation_status.yaml collected_test_count 多处不一致：{collected_counts}")
        collected_count = None
    else:
        collected_count = collected_counts[0]

    expected_count = (
        executable_count + e2e_count
        if executable_count is not None and e2e_count is not None
        else None
    )
    if expected_count is not None and collected_count is not None and expected_count != collected_count:
        errors.append(
            "generation_status.yaml 执行级用例数 + E2E flow 数与 pytest 收集数不一致："
            f"{expected_count} != {collected_count}"
        )

    blocks = extract_pytest_mapping_blocks(pytest_section)
    flow_blocks = extract_pytest_flow_mapping_blocks(pytest_section)
    if executable_count is not None and len(blocks) != executable_count:
        errors.append(f"generation_status.yaml pytest 映射条数与执行级用例数不一致：{len(blocks)} != {executable_count}")
    if e2e_count is not None and len(flow_blocks) != e2e_count:
        errors.append(f"generation_status.yaml E2E flow 映射条数与 flow 数不一致：{len(flow_blocks)} != {e2e_count}")
    for block in blocks:
        for field in ("design_case_id", "coverage_object_ids", "coverage_rule_ids", "test_point_id", "pytest_nodeid"):
            if not block.get(field):
                case_id = block.get("executable_case_id", "UNKNOWN")
                errors.append(f"generation_status.yaml 映射 {case_id} 缺少 {field}")
    for block in flow_blocks:
        for field in ("flow_id", "source_executable_case_ids", "pytest_nodeid"):
            if not block.get(field):
                flow_id = block.get("flow_id", "UNKNOWN")
                errors.append(f"generation_status.yaml E2E flow 映射 {flow_id} 缺少 {field}")

    if chain_section:
        chain_status_values = yaml_scalar_values(chain_section, "status")
        if not chain_status_values or chain_status_values[0] != "passed":
            errors.append("generation_status.yaml chain_script_coverage.status 不是 passed")
        for missing_key in ("missing_required_flow_ids", "single_interface_only_flow_ids"):
            values = yaml_scalar_values(chain_section, missing_key)
            if not values:
                errors.append(f"generation_status.yaml chain_script_coverage 缺少 {missing_key}")
            elif values[0] != "[]":
                errors.append(f"generation_status.yaml chain_script_coverage.{missing_key} 未清空：{values[0]}")

    if required_flow_ids or long_chain_required:
        if e2e_count is None:
            errors.append("generation_status.yaml 存在必需链路但 e2e_flow_case_count 不可解析")
        elif e2e_count < max(1, len(required_flow_ids)):
            errors.append(
                "generation_status.yaml 存在必需链路但 E2E flow 数不足："
                f"{e2e_count} < {max(1, len(required_flow_ids))}"
            )
        if chain_section:
            required_counts = yaml_int_values(chain_section, "required_flow_count")
            generated_counts = yaml_int_values(chain_section, "generated_flow_count")
            required_chain_counts = yaml_int_values(chain_section, "required_chain_flow_count")
            generated_pytest_counts = yaml_int_values(chain_section, "generated_pytest_flow_count")
            if required_counts and required_flow_ids and required_counts[0] != len(required_flow_ids):
                errors.append(
                    "generation_status.yaml chain_script_coverage.required_flow_count 与上游必需 flow 数不一致："
                    f"{required_counts[0]} != {len(required_flow_ids)}"
                )
            elif long_chain_required and required_counts and required_counts[0] <= 0:
                errors.append("generation_status.yaml 存在必需链路场景但 required_flow_count 不是正数")
            if required_counts and generated_counts and generated_counts[0] != required_counts[0]:
                errors.append(
                    "generation_status.yaml chain_script_coverage.generated_flow_count 与 required_flow_count 不一致："
                    f"{generated_counts[0]} != {required_counts[0]}"
                )
            if not required_chain_counts:
                errors.append("generation_status.yaml chain_script_coverage 缺少 required_chain_flow_count")
            elif required_flow_ids and required_chain_counts[0] != len(required_flow_ids):
                errors.append(
                    "generation_status.yaml chain_script_coverage.required_chain_flow_count 与必测 flow 数不一致："
                    f"{required_chain_counts[0]} != {len(required_flow_ids)}"
                )
            if not generated_pytest_counts:
                errors.append("generation_status.yaml chain_script_coverage 缺少 generated_pytest_flow_count")
            elif required_flow_ids and generated_pytest_counts[0] != len(required_flow_ids):
                errors.append(
                    "generation_status.yaml chain_script_coverage.generated_pytest_flow_count 与必测 flow 数不一致："
                    f"{generated_pytest_counts[0]} != {len(required_flow_ids)}"
                )
            mapped_flow_ids = {block.get("flow_id", "") for block in flow_blocks}
            missing_mapped_ids = sorted(flow_id for flow_id in required_flow_ids if flow_id not in mapped_flow_ids)
            if missing_mapped_ids:
                errors.append(f"generation_status.yaml E2E flow 映射缺少上游必需 flow_id：{missing_mapped_ids}")
            for flow_id in sorted(required_flow_ids):
                if flow_id not in chain_section:
                    errors.append(f"generation_status.yaml chain_script_coverage 未列出上游必需 flow_id：{flow_id}")
            validate_required_chain_independent_coverage(
                chain_section,
                errors,
                "generation_status.yaml/chain_script_coverage",
                required_flow_ids,
                "generated_pytest_flow_count",
            )

    next_stage_values = yaml_scalar_values(text, "next_stage_allowed")
    if not next_stage_values:
        errors.append("generation_status.yaml 缺少 next_stage_allowed")
    elif not is_yaml_true(next_stage_values[0]):
        errors.append(f"generation_status.yaml next_stage_allowed 不是 true：{next_stage_values[0]}")


def strip_pytest_parameter(name: str) -> str:
    return name.split("[", 1)[0].strip()


def validate_python_compile(path: Path, errors: list[str]) -> bool:
    try:
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
        return True
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        errors.append(f"pytest 静态校验失败：{path} 不能通过 Python 编译：{exc}")
        return False


def parse_python_tree(path: Path, errors: list[str]) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        errors.append(f"pytest 静态校验失败：{path} 无法解析为 Python AST：{exc}")
        return None


def collect_test_defs(tree: ast.Module) -> tuple[set[str], dict[str, set[str]]]:
    top_level_functions: set[str] = set()
    class_methods: dict[str, set[str]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            top_level_functions.add(node.name)
        elif isinstance(node, ast.ClassDef):
            methods = {
                item.name
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            class_methods[node.name] = methods
    return top_level_functions, class_methods


def collect_test_def_nodes(tree: ast.Module) -> tuple[dict[str, ast.AST], dict[str, dict[str, ast.AST]]]:
    top_level_functions: dict[str, ast.AST] = {}
    class_methods: dict[str, dict[str, ast.AST]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            top_level_functions[node.name] = node
        elif isinstance(node, ast.ClassDef):
            methods = {
                item.name: item
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            class_methods[node.name] = methods
    return top_level_functions, class_methods


def run_flow_call_matches(call: ast.Call, flow_id: str) -> bool:
    if isinstance(call.func, ast.Name):
        func_name = call.func.id
    elif isinstance(call.func, ast.Attribute):
        func_name = call.func.attr
    else:
        return False
    if func_name != "run_flow" or len(call.args) < 4:
        return False
    first_arg = call.args[0]
    if not isinstance(first_arg, ast.Constant) or first_arg.value != flow_id:
        return False
    expected_args = ("authenticated_client", "env_config", "runtime_context")
    for actual, expected in zip(call.args[1:4], expected_args):
        if not isinstance(actual, ast.Name) or actual.id != expected:
            return False
    return True


def test_function_calls_run_flow(function_node: ast.AST, flow_id: str) -> bool:
    for node in ast.walk(function_node):
        if isinstance(node, ast.Call) and run_flow_call_matches(node, flow_id):
            return True
    return False


def attribute_chain_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = attribute_chain_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def test_function_has_parametrize(function_node: ast.AST) -> bool:
    decorators = getattr(function_node, "decorator_list", [])
    for decorator in decorators:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if attribute_chain_name(target) in {"pytest.mark.parametrize", "mark.parametrize"}:
            return True
    return False


def python_file_has_parametrize(path: Path, errors: list[str]) -> bool:
    tree = parse_python_tree(path, errors)
    if tree is None:
        return False
    for node in all_pytest_function_nodes(tree):
        if test_function_has_parametrize(node):
            return True
    return False


def format_path_options(paths: tuple[Path, ...]) -> str:
    return " 或 ".join(path.as_posix() for path in paths)


def existing_framework_files(framework: Path, paths: tuple[Path, ...]) -> list[Path]:
    return [framework / relative_path for relative_path in paths if (framework / relative_path).is_file()]


def module_docstring_node(node: ast.AST) -> bool:
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)


def assignment_target_names(node: ast.AST) -> tuple[list[str], ast.AST | None]:
    if isinstance(node, ast.Assign):
        names: list[str] = []
        for target in node.targets:
            if not isinstance(target, ast.Name):
                return [], None
            names.append(target.id)
        return names, node.value
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
        return [node.target.id], node.value
    return [], None


def validate_python_data_module(
    path: Path,
    framework: Path,
    kind: str,
    errors: list[str],
) -> dict[str, object]:
    relative_path = path.relative_to(framework)
    tree = parse_python_tree(path, errors)
    if tree is None:
        return {}
    required_exports = PY_DATA_EXPORTS_BY_KIND[kind]
    allowed_exports = set(required_exports) | PY_DATA_COMMON_EXPORTS
    exports: dict[str, object] = {}
    for node in tree.body:
        if module_docstring_node(node):
            continue
        names, value_node = assignment_target_names(node)
        if not names or value_node is None:
            errors.append(f"{relative_path} Python 数据文件只能包含常量赋值，不能包含 import、函数、类或执行语句")
            continue
        for name in names:
            if name not in allowed_exports:
                errors.append(f"{relative_path} Python 数据文件存在非约定变量：{name}")
                continue
            try:
                exports[name] = ast.literal_eval(value_node)
            except (TypeError, ValueError):
                errors.append(f"{relative_path} Python 数据变量必须是字面量：{name}")
    if not any(name in exports for name in required_exports):
        choices = " 或 ".join(sorted(required_exports))
        errors.append(f"{relative_path} Python 数据文件缺少导出变量：{choices}")
    return exports


def python_export_value(exports: dict[str, object], kind: str) -> object:
    for name in PY_DATA_EXPORTS_BY_KIND[kind]:
        if name in exports:
            return exports[name]
    return None


def framework_confidence_records(framework: Path, errors: list[str]) -> list[tuple[str, dict[str, Any]]]:
    records: list[tuple[str, dict[str, Any]]] = []
    case_dir = framework / "data" / "cases"
    if case_dir.is_dir():
        for path in sorted([*case_dir.glob("*.yaml"), *case_dir.glob("*.py")]):
            relative = str(path.relative_to(framework))
            if path.suffix == ".py":
                exports = validate_python_data_module(path, framework, "cases", errors)
                items = python_export_value(exports, "cases")
            else:
                payload = read_yaml_file(path, errors, relative)
                items = payload.get("cases") if isinstance(payload, dict) else None
            if not isinstance(items, list):
                continue
            for index, item in enumerate(items, start=1):
                if isinstance(item, dict):
                    records.append((f"{relative} {item.get('case_id') or index}", item))

    optional_path = framework / "data" / "optional_async_cases.yaml"
    if optional_path.is_file():
        payload = read_yaml_file(optional_path, errors, "data/optional_async_cases.yaml")
        items = payload.get("cases") if isinstance(payload, dict) else None
        if isinstance(items, list):
            for index, item in enumerate(items, start=1):
                if isinstance(item, dict):
                    records.append((f"data/optional_async_cases.yaml {item.get('case_id') or index}", item))

    for path in existing_framework_files(framework, DATA_DRIVEN_FLOW_FILES):
        relative = str(path.relative_to(framework))
        if path.suffix == ".py":
            exports = validate_python_data_module(path, framework, "flows", errors)
            items = python_export_value(exports, "flows")
        else:
            payload = read_yaml_file(path, errors, relative)
            items = payload.get("flows") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items, start=1):
            if isinstance(item, dict):
                records.append((f"{relative} {item.get('flow_id') or index}", item))
    return records


def validate_live_automation_decision(
    item: dict[str, Any],
    label: str,
    errors: list[str],
    *,
    require_ready_flag: bool,
) -> None:
    """校验 live-ready 与 runnable 的双向一致性，不改写 non-live 决策。"""

    ready = item.get("live_pytest_release_ready")
    decision = str(item.get("automation_decision") or "").strip()
    if require_ready_flag and not isinstance(ready, bool):
        errors.append(f"{label} 缺少布尔 live_pytest_release_ready")
    elif ready is True and decision != "runnable":
        errors.append(f"{label} automation_decision 非法：{decision or '<empty>'}")
    elif decision == "runnable" and ready is not True:
        errors.append(f"{label} runnable 与 live_pytest_release_ready 不一致")


def validate_optional_transfer_release(
    framework: Path,
    generation_status_data: dict[str, Any],
    errors: list[str],
) -> None:
    """当存在最终准出审计时，校验可传输分母与 live 决策的一致性。"""

    audit_path = framework / "configs" / "final_release_audit.yaml"
    if not audit_path.is_file():
        return
    audit = read_yaml_file(audit_path, errors, "configs/final_release_audit.yaml")
    if not isinstance(audit, dict):
        return
    if audit.get("status") != "passed":
        errors.append("final_release_audit.yaml status 不是 passed")
    release_decision = audit.get("release_decision") or {}
    if not isinstance(release_decision, dict) or release_decision.get("script_generation_ready") is not True:
        errors.append("final_release_audit.yaml release_decision.script_generation_ready 不是 true")

    ordinary_cases: list[tuple[str, dict[str, Any]]] = []
    case_dir = framework / "data" / "cases"
    if case_dir.is_dir():
        for path in sorted(case_dir.glob("*.yaml")):
            payload = read_yaml_file(path, errors, str(path.relative_to(framework)))
            items = payload.get("cases") if isinstance(payload, dict) else None
            if not isinstance(items, list):
                continue
            for index, item in enumerate(items, start=1):
                if isinstance(item, dict):
                    ordinary_cases.append((str(item.get("case_id") or f"{path.name}#{index}"), item))

    for case_id, item in ordinary_cases:
        validate_live_automation_decision(
            item,
            f"可传输普通案例 {case_id}",
            errors,
            require_ready_flag=True,
        )

    flow_path = framework / "data" / "flow_cases.yaml"
    if flow_path.is_file():
        flow_payload = read_yaml_file(flow_path, errors, "data/flow_cases.yaml")
        flows = flow_payload.get("flows") if isinstance(flow_payload, dict) else None
        if isinstance(flows, list):
            for index, item in enumerate(flows, start=1):
                if not isinstance(item, dict):
                    continue
                flow_id = str(item.get("flow_id") or f"flow#{index}")
                validate_live_automation_decision(
                    item,
                    f"结构化 E2E Flow {flow_id}",
                    errors,
                    require_ready_flag=True,
                )

    ordinary_total = len(ordinary_cases)
    ordinary_runnable = sum(item.get("live_pytest_release_ready") is True for _, item in ordinary_cases)
    ordinary_non_live = ordinary_total - ordinary_runnable
    raw_e2e_count = generation_status_data.get("e2e_flow_case_count")
    e2e_count = raw_e2e_count if isinstance(raw_e2e_count, int) and not isinstance(raw_e2e_count, bool) else 0
    raw_collected_count = generation_status_data.get("collected_test_count")
    collected_count = (
        raw_collected_count
        if isinstance(raw_collected_count, int) and not isinstance(raw_collected_count, bool)
        else None
    )
    raw_selected_count = generation_status_data.get("selected_case_count")
    selected_count = (
        raw_selected_count
        if isinstance(raw_selected_count, int) and not isinstance(raw_selected_count, bool)
        else ordinary_total
    )
    expected_scope_counts: dict[str, int | None] = {
        "generated_candidate_case_count": ordinary_total,
        "selected_case_count": selected_count,
        "runnable_case_count": ordinary_runnable,
        "non_live_case_count": ordinary_non_live,
        "e2e_flow_count": e2e_count,
        "runnable_node_count": ordinary_runnable + e2e_count,
        "collected_node_count": collected_count,
    }
    scope = audit.get("scope") or {}
    if not isinstance(scope, dict):
        errors.append("final_release_audit.yaml scope 必须是对象")
        scope = {}
    for field, expected in expected_scope_counts.items():
        if field not in scope or expected is None:
            continue
        actual = scope.get(field)
        if isinstance(actual, bool) or not isinstance(actual, int) or actual != expected:
            errors.append(f"final_release_audit.yaml scope.{field} 与当前产物不一致：{actual} != {expected}")

    pytest_check = (audit.get("checks") or {}).get("pytest_collect_only") or {}
    if isinstance(pytest_check, dict) and "collected_node_count" in pytest_check and collected_count is not None:
        actual = pytest_check.get("collected_node_count")
        if actual != collected_count:
            errors.append(
                "final_release_audit.yaml checks.pytest_collect_only.collected_node_count "
                f"与 generation_status 不一致：{actual} != {collected_count}"
            )


def validate_framework_case_confidence(
    framework: Path,
    generation_status_data: dict[str, Any],
    errors: list[str],
) -> None:
    section = generation_status_data.get("case_confidence_gate")
    if not isinstance(section, dict):
        errors.append("generation_status.yaml 缺少 case_confidence_gate 明细")
        return
    if section.get("status") != "passed":
        errors.append("generation_status.yaml case_confidence_gate.status 不是 passed")

    records = framework_confidence_records(framework, errors)
    levels = {"high": 0, "medium": 0, "low": 0}
    declared_count = 0
    for label, item in records:
        valid = validate_case_confidence(
            item,
            label,
            errors,
            require_runtime_dimension=True,
            enforce_live_boundary=True,
        )
        validate_live_automation_decision(
            item,
            label,
            errors,
            require_ready_flag=False,
        )
        if valid:
            declared_count += 1
        level = item.get("confidence_level")
        if level in levels:
            levels[level] += 1

    case_scores = {
        str(item.get("case_id")): float(item["confidence_score"])
        for _, item in records
        if item.get("case_id") and confidence_number(item.get("confidence_score")) is not None
    }
    for label, item in records:
        if not item.get("flow_id"):
            continue
        raw_source_case_ids = item.get("source_executable_case_ids") or []
        if isinstance(raw_source_case_ids, str):
            source_case_ids = [raw_source_case_ids]
        elif isinstance(raw_source_case_ids, list):
            source_case_ids = raw_source_case_ids
        else:
            source_case_ids = []
        steps = item.get("steps") if isinstance(item.get("steps"), list) else []
        if not source_case_ids:
            source_case_ids = [
                step.get("case_id") or step.get("source_case_id") or step.get("source_executable_case_id")
                for step in steps
                if isinstance(step, dict)
            ]
        source_case_ids = [str(case_id) for case_id in source_case_ids if case_id]
        step_scores: list[float] = []
        missing_step_confidence_ids: list[str] = []
        consolidated_case_id = str(item.get("case_id") or "")
        consolidated_score = case_scores.get(consolidated_case_id)
        if consolidated_score is not None:
            step_scores.append(consolidated_score)
        inline_steps = {
            str(step.get("case_id") or step.get("source_case_id") or step.get("source_executable_case_id")): step
            for step in steps
            if isinstance(step, dict)
            and (step.get("case_id") or step.get("source_case_id") or step.get("source_executable_case_id"))
        }
        for source_case_id in source_case_ids:
            if source_case_id in case_scores:
                step_scores.append(case_scores[source_case_id])
                continue
            inline_step = inline_steps.get(source_case_id) or {}
            inline_score = confidence_number(inline_step.get("confidence_score"))
            if inline_score is not None:
                validate_case_confidence(
                    inline_step,
                    f"{label} step {source_case_id}",
                    errors,
                    require_runtime_dimension=True,
                    enforce_live_boundary=True,
                )
                step_scores.append(inline_score)
            elif consolidated_score is not None:
                # 一个生成的长链路支撑 case 可以承载未单独物化步骤的聚合置信度。
                continue
            else:
                missing_step_confidence_ids.append(source_case_id)
        if missing_step_confidence_ids:
            errors.append(f"{label} 缺少必需步骤置信度：{sorted(set(missing_step_confidence_ids))}")
        flow_score = confidence_number(item.get("confidence_score"))
        if step_scores and flow_score is not None and flow_score > min(step_scores) + 1e-8:
            errors.append(f"{label} 的长链路置信度高于最弱必需步骤：{flow_score:g} > {min(step_scores):g}")

    expected_counts = {
        "candidate_case_count": len(records),
        "declared_confidence_case_count": declared_count,
        "high_count": levels["high"],
        "medium_count": levels["medium"],
        "low_count": levels["low"],
    }
    for field, expected in expected_counts.items():
        actual = section.get(field)
        if actual != expected:
            errors.append(f"generation_status.yaml case_confidence_gate.{field} 不一致：{actual} != {expected}")

    for field in (
        "missing_confidence_case_ids",
        "invalid_confidence_case_ids",
        "low_confidence_live_case_ids",
        "archive_missing_confidence_case_ids",
    ):
        if section.get(field) != []:
            errors.append(f"generation_status.yaml case_confidence_gate.{field} 未清空：{section.get(field)}")

    archive_path = framework / "接口案例.md"
    if archive_path.is_file() and records:
        archive_text = read_optional_text(archive_path, errors)
        for field in (
            "置信度分数",
            "置信度等级",
        ):
            if field not in archive_text:
                errors.append(f"接口案例.md 缺少置信度归档字段：{field}")
        for label, item in records:
            record_id = str(item.get("flow_id") or item.get("case_id") or "")
            start_marker = f"<!-- CASE_CONFIDENCE_INLINE:{record_id} START -->"
            end_marker = f"<!-- CASE_CONFIDENCE_INLINE:{record_id} END -->"
            if archive_text.count(start_marker) != 1 or archive_text.count(end_marker) != 1:
                errors.append(f"接口案例.md {record_id} 缺少唯一内联置信度块")
                continue
            inline_match = re.search(
                rf"{re.escape(start_marker)}(.*?){re.escape(end_marker)}",
                archive_text,
                re.DOTALL,
            )
            inline_block = inline_match.group(1) if inline_match else ""
            for field in (
                "置信度分数",
                "置信度等级",
            ):
                if field not in inline_block:
                    errors.append(f"接口案例.md {record_id} 内联置信度块缺少字段：{field}")
            scalar_expectations = {
                "置信度分数": item.get("confidence_score"),
                "置信度等级": item.get("confidence_level"),
            }
            for field, expected in scalar_expectations.items():
                match = re.search(rf"{field}\s*[：:]\s*`?([^`\n]+?)`?\s*$", inline_block, re.MULTILINE)
                actual = match.group(1).strip() if match else ""
                if field == "置信度分数":
                    try:
                        matches = abs(float(actual) - float(expected)) <= 1e-8
                    except (TypeError, ValueError):
                        matches = False
                else:
                    matches = actual == str(expected)
                if not matches:
                    errors.append(f"接口案例.md {record_id} {field} 与机器数据不一致：{actual} != {expected}")


def executable_confidence_case_paths(executable_dir: Path, errors: list[str]) -> list[Path]:
    """按执行级入口声明读取非分片文件或有序分片，避免分片用例逃过纵向校验。"""

    entry_path = executable_dir / "执行级接口用例集.md"
    if not entry_path.is_file():
        return []
    try:
        entry_text = read_text(entry_path)
    except ValueError as exc:
        errors.append(str(exc))
        return []
    if line_value(entry_text, "分片模式") != "启用":
        return [entry_path]

    index_path = executable_dir / EXECUTABLE_SHARD_INDEX_FILE
    if not index_path.is_file():
        errors.append(f"执行级置信度分片模式缺少 {EXECUTABLE_SHARD_INDEX_FILE}")
        return []
    try:
        index_text = read_text(index_path)
    except ValueError as exc:
        errors.append(str(exc))
        return []

    shard_refs: list[tuple[str, str]] = []
    seen_orders: set[str] = set()
    seen_refs: set[str] = set()
    for raw_line in index_text.splitlines():
        cells = split_markdown_row(raw_line)
        if len(cells) < 3 or not re.fullmatch(r"\d{3}", cells[0]):
            continue
        order = cells[0]
        file_ref = cells[2].strip().strip(chr(96))
        expected_pattern = rf"{re.escape(EXECUTABLE_SHARD_DIR)}/\d{{3}}_[^/]+\.md"
        if re.fullmatch(expected_pattern, file_ref) is None:
            errors.append(f"{EXECUTABLE_SHARD_INDEX_FILE} 分片文件路径非法：{file_ref}")
            continue
        if not Path(file_ref).name.startswith(f"{order}_"):
            errors.append(f"{EXECUTABLE_SHARD_INDEX_FILE} 分片文件前缀与顺序不一致：{file_ref}")
            continue
        if order in seen_orders or file_ref in seen_refs:
            errors.append(f"{EXECUTABLE_SHARD_INDEX_FILE} 存在重复顺序或文件：{order}/{file_ref}")
            continue
        seen_orders.add(order)
        seen_refs.add(file_ref)
        shard_refs.append((order, file_ref))

    if not shard_refs:
        errors.append(f"{EXECUTABLE_SHARD_INDEX_FILE} 未读取到有效分片记录")
        return []
    shard_refs.sort()
    expected_orders = [f"{index:03d}" for index in range(1, len(shard_refs) + 1)]
    actual_orders = [order for order, _ in shard_refs]
    if actual_orders != expected_orders:
        errors.append(f"{EXECUTABLE_SHARD_INDEX_FILE} 顺序必须从 001 连续递增：{actual_orders}")

    paths: list[Path] = []
    for _, file_ref in shard_refs:
        path = executable_dir / file_ref
        if not path.is_file():
            errors.append(f"执行级置信度分片文件不存在：{file_ref}")
            continue
        paths.append(path)
    return paths


def executable_confidence_records(root: Path, errors: list[str]) -> list[tuple[str, dict[str, Any]]]:
    executable_dir = root / "05-executable-interface-case-set"
    records: list[tuple[str, dict[str, Any]]] = []
    seen_case_ids: set[str] = set()
    if not executable_dir.is_dir():
        return records
    case_paths = executable_confidence_case_paths(executable_dir, errors)
    for path in case_paths:
        try:
            text = read_text(path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        for fence_index, match in enumerate(re.finditer(r"```yaml\s*\n(.*?)\n```", text, re.DOTALL), start=1):
            try:
                payload = yaml.safe_load(match.group(1))
            except yaml.YAMLError as exc:
                errors.append(f"{path.name} 第 {fence_index} 个 YAML 块无法解析置信度：{exc}")
                continue
            if isinstance(payload, dict):
                items = payload.get("cases") or payload.get("用例") or []
            else:
                items = payload
            if not isinstance(items, list):
                continue
            for index, raw_item in enumerate(items, start=1):
                if not isinstance(raw_item, dict) or not raw_item.get("用例ID"):
                    continue
                case_id = str(raw_item["用例ID"])
                if case_id in seen_case_ids:
                    errors.append(f"执行级置信度用例ID重复：{case_id}")
                    continue
                seen_case_ids.add(case_id)
                item = {
                    "case_id": case_id,
                    "design_case_id": raw_item.get("设计级用例ID"),
                    **{
                        machine_field: raw_item.get(display_field)
                        for machine_field, display_field in EXECUTABLE_CONFIDENCE_FIELD_MAP.items()
                        if display_field in raw_item
                    },
                }
                records.append((f"{path.name} {case_id}", item))
    if case_paths and not records:
        errors.append("执行级置信度产物未读取到任何机器可识别用例")
    return records


def confidence_upstream_candidates(item: dict[str, Any]) -> list[str]:
    traceability = item.get("traceability") if isinstance(item.get("traceability"), dict) else {}
    candidates = (
        item.get("design_case_id"),
        traceability.get("design_case_id"),
        traceability.get("supplemental_design_case_ref"),
        item.get("source_case_id"),
        traceability.get("source_case_id"),
        item.get("case_id"),
    )
    result: list[str] = []
    for value in candidates:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def validate_confidence_score_change(
    label: str,
    upstream: dict[str, Any],
    downstream: dict[str, Any],
    errors: list[str],
) -> None:
    upstream_score = confidence_number(upstream.get("confidence_score"))
    downstream_score = confidence_number(downstream.get("confidence_score"))
    if upstream_score is None or downstream_score is None or abs(downstream_score - upstream_score) <= 1e-8:
        return
    upstream_refs = {str(value) for value in upstream.get("confidence_evidence_refs") or []}
    downstream_refs = {str(value) for value in downstream.get("confidence_evidence_refs") or []}
    has_new_evidence = bool(downstream_refs - upstream_refs)
    dimensions_changed = downstream.get("confidence_dimensions") != upstream.get("confidence_dimensions")
    caps_changed = downstream.get("confidence_cap_reasons") != upstream.get("confidence_cap_reasons")
    reasons_changed = downstream.get("confidence_reason_codes") != upstream.get("confidence_reason_codes")
    if downstream_score > upstream_score:
        if not has_new_evidence:
            errors.append(f"{label} 置信度从 {upstream_score:g} 升至 {downstream_score:g}，但没有新增证据引用")
        if not dimensions_changed and not caps_changed:
            errors.append(f"{label} 置信度升高但维度和硬上限条件均未变化")
        return
    if not has_new_evidence:
        errors.append(f"{label} 置信度从 {upstream_score:g} 降至 {downstream_score:g}，但没有新增证据引用")
    if not dimensions_changed and not caps_changed:
        errors.append(f"{label} 置信度降低但维度和硬上限条件均未变化")
    if not reasons_changed and not caps_changed:
        errors.append(f"{label} 置信度降低但原因码和硬上限原因均未变化")


def validate_confidence_stage_progression(root: Path, framework: Path, errors: list[str]) -> None:
    design_path = root / "04-design-case-handoff" / "case_list.yaml"
    if not design_path.is_file():
        design_path = root / "03-interface-testcase-generation" / "case_list.yaml"
    if not design_path.is_file():
        return
    design_payload = read_yaml_file(design_path, errors, str(design_path.relative_to(root)))
    if not isinstance(design_payload, dict):
        return
    design_cases: dict[str, dict[str, Any]] = {}
    for item in design_payload.get("cases") or []:
        if not isinstance(item, dict):
            continue
        for key in ("case_id", "design_case_id"):
            alias = str(item.get(key) or "").strip()
            if alias:
                design_cases[alias] = item
    if not design_cases:
        return

    executable_records = executable_confidence_records(root, errors)
    executable_cases: dict[str, dict[str, Any]] = {}
    for label, item in executable_records:
        validate_case_confidence(
            item,
            label,
            errors,
            require_runtime_dimension=True,
            enforce_live_boundary=False,
        )
        if item.get("confidence_scope") not in {"executable", "design_and_execution"}:
            errors.append(f"{label} confidence_scope 必须是 executable/design_and_execution")
        case_id = str(item.get("case_id") or "")
        if case_id:
            executable_cases[case_id] = item
        upstream = next((design_cases[value] for value in confidence_upstream_candidates(item) if value in design_cases), None)
        if upstream:
            validate_confidence_score_change(label, upstream, item, errors)

    for label, item in framework_confidence_records(framework, errors):
        case_id = str(item.get("case_id") or "")
        upstream = executable_cases.get(case_id)
        if upstream is None:
            upstream = next((design_cases[value] for value in confidence_upstream_candidates(item) if value in design_cases), None)
        if upstream:
            validate_confidence_score_change(label, upstream, item, errors)


def flow_marks_account_specific(flow: dict[str, object]) -> bool:
    for key in ("specific_account_required", "requires_specific_account", "account_specific"):
        value = flow.get(key)
        if value is True or is_yaml_true(str(value or "")):
            return True
    for key in ("required_account_role", "required_account_business_state", "required_tenant", "required_permission"):
        if account_marker_value_requires_login(str(flow.get(key) or "")):
            return True
    return "account_specific_chain" in str(flow)


def step_marks_login_entry(step: dict[str, object]) -> bool:
    for key in ("login_entry", "is_login_step"):
        value = step.get(key)
        if value is True or is_yaml_true(str(value or "")):
            return True
    for key in ("step_type", "auth_step", "request_role"):
        value = str(step.get(key) or "").strip().strip("\"'").lower()
        if value in LOGIN_STEP_TYPE_VALUES:
            return True
    return bool(re.search(r"(?:/|_|-|\b)(login|signin|auth|oauth|token)(?:/|_|-|\b)", str(step).lower()))


def validate_account_specific_flow_login_entry_items(
    flows: object,
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(flows, list):
        errors.append(f"{label} 必须包含 FLOWS/flows 列表")
        return
    for flow in flows:
        if not isinstance(flow, dict) or not flow_marks_account_specific(flow):
            continue
        flow_id = str(flow.get("flow_id") or "UNKNOWN")
        steps = flow.get("steps")
        if not isinstance(steps, list) or not steps or not isinstance(steps[0], dict):
            errors.append(f"{label} 账号型长链路缺少首个登录/授权步骤：{flow_id}")
            continue
        first_step = steps[0]
        first_step_text = str(first_step)
        if not step_marks_login_entry(first_step):
            errors.append(f"{label} 账号型长链路首步不是登录/授权接口：{flow_id}")
            continue
        lowered = first_step_text.lower()
        if ("extract" not in lowered and "extraction" not in lowered) or "token" not in lowered:
            errors.append(f"{label} 账号型长链路登录首步缺少 token 提取规则：{flow_id}")
        if "account_context_not_required" not in first_step_text and not any(
            marker in first_step_text for marker in ("account_context", "user_id", "userId", "appUserId", "tenant", "role")
        ):
            errors.append(f"{label} 账号型长链路登录首步缺少账号上下文提取或不需要说明：{flow_id}")


def all_pytest_function_nodes(tree: ast.Module) -> list[ast.AST]:
    top_level_functions, class_methods = collect_test_def_nodes(tree)
    nodes = [node for name, node in top_level_functions.items() if name.startswith("test_")]
    for class_name, methods in class_methods.items():
        if not class_name.startswith("Test"):
            continue
        nodes.extend(node for name, node in methods.items() if name.startswith("test_"))
    return nodes


def flow_file_contains_run_flow_call(path: Path, flow_id: str, errors: list[str]) -> bool:
    tree = parse_python_tree(path, errors)
    if tree is None:
        return False
    return any(test_function_calls_run_flow(node, flow_id) for node in all_pytest_function_nodes(tree))


def mapped_test_function_node(framework: Path, nodeid: str, errors: list[str]) -> ast.AST | None:
    parts = [part.strip() for part in nodeid.split("::") if part.strip()]
    if len(parts) < 2:
        return None
    path = resolve_nodeid_file(framework, nodeid)
    if path is None or not path.is_file() or path.suffix != ".py":
        return None
    tree = parse_python_tree(path, errors)
    if tree is None:
        return None
    top_level_functions, class_methods = collect_test_def_nodes(tree)
    target_name = strip_pytest_parameter(parts[-1])
    if len(parts) == 2:
        return top_level_functions.get(target_name)
    class_name = strip_pytest_parameter(parts[-2])
    return class_methods.get(class_name, {}).get(target_name)


def resolve_nodeid_file(framework: Path, nodeid: str) -> Path | None:
    file_part = nodeid.split("::", 1)[0].strip()
    if not file_part or file_part.startswith("/") or ".." in Path(file_part).parts:
        return None
    path = framework / file_part
    try:
        path.resolve().relative_to(framework.resolve())
    except ValueError:
        return None
    return path


def validate_pytest_nodeid_targets(
    framework: Path,
    generation_status_text: str,
    errors: list[str],
    required_flow_ids: set[str] | None = None,
) -> None:
    pytest_section = yaml_section(generation_status_text, "pytest_collection_mapping")
    blocks = extract_pytest_mapping_blocks(pytest_section)
    flow_blocks = extract_pytest_flow_mapping_blocks(pytest_section)
    nodeids = [
        block.get("pytest_nodeid", "").strip()
        for block in blocks + flow_blocks
        if block.get("pytest_nodeid")
    ]
    if not nodeids:
        errors.append("pytest 静态校验失败：generation_status.yaml 没有可验证的 pytest_nodeid")
        return
    if len(set(nodeids)) != len(nodeids):
        errors.append("pytest 静态校验失败：pytest_nodeid 存在重复映射")

    compile_results: dict[Path, bool] = {}
    parsed_files: dict[Path, tuple[set[str], dict[str, set[str]]]] = {}
    for path in sorted(framework.rglob("*.py")):
        compile_results[path] = validate_python_compile(path, errors)

    for nodeid in nodeids:
        parts = [part.strip() for part in nodeid.split("::") if part.strip()]
        if len(parts) < 2:
            errors.append(f"pytest 静态校验失败：pytest_nodeid 缺少测试函数：{nodeid}")
            continue
        path = resolve_nodeid_file(framework, nodeid)
        if path is None:
            errors.append(f"pytest 静态校验失败：pytest_nodeid 文件路径非法：{nodeid}")
            continue
        if not path.is_file():
            errors.append(f"pytest 静态校验失败：pytest_nodeid 指向的测试文件不存在：{nodeid}")
            continue
        if path.suffix != ".py":
            errors.append(f"pytest 静态校验失败：pytest_nodeid 指向的不是 Python 文件：{nodeid}")
            continue
        if path not in compile_results:
            compile_results[path] = validate_python_compile(path, errors)
        if not compile_results[path]:
            continue

        if path not in parsed_files:
            tree = parse_python_tree(path, errors)
            if tree is None:
                continue
            parsed_files[path] = collect_test_defs(tree)
        top_level_functions, class_methods = parsed_files[path]
        target_name = strip_pytest_parameter(parts[-1])
        if len(parts) == 2:
            if target_name not in top_level_functions:
                errors.append(f"pytest 静态校验失败：pytest_nodeid 找不到测试函数：{nodeid}")
            continue

        class_name = strip_pytest_parameter(parts[-2])
        if class_name not in class_methods:
            errors.append(f"pytest 静态校验失败：pytest_nodeid 找不到测试类：{nodeid}")
            continue
        if target_name not in class_methods[class_name]:
            errors.append(f"pytest 静态校验失败：pytest_nodeid 找不到测试方法：{nodeid}")

    validate_pytest_flow_entrypoints(framework, flow_blocks, required_flow_ids or set(), errors)
    validate_pytest_collection(framework, nodeids, errors)


def validate_pytest_flow_entrypoints(
    framework: Path,
    flow_blocks: list[dict[str, str]],
    required_flow_ids: set[str],
    errors: list[str],
) -> None:
    mapped_flow_ids = {
        block.get("flow_id", "").strip()
        for block in flow_blocks
        if block.get("flow_id")
    }
    missing_flow_ids = sorted(flow_id for flow_id in required_flow_ids if flow_id not in mapped_flow_ids)
    for flow_id in missing_flow_ids:
        errors.append(f"pytest 静态校验失败：E2E flow 映射缺少上游必需 flow_id：{flow_id}")
    expected_flow_ids = set(required_flow_ids) or {
        block.get("flow_id", "").strip()
        for block in flow_blocks
        if block.get("flow_id")
    }
    for flow_id in sorted(flow_id for flow_id in expected_flow_ids if flow_id):
        matching_blocks = [block for block in flow_blocks if block.get("flow_id") == flow_id]
        for block in matching_blocks:
            nodeid = block.get("pytest_nodeid", "").strip()
            if not nodeid:
                continue
            function_node = mapped_test_function_node(framework, nodeid, errors)
            if function_node is None:
                continue
            if not test_function_calls_run_flow(function_node, flow_id):
                errors.append(
                    "pytest 静态校验失败：E2E flow 映射的测试函数必须直接调用 "
                    f"run_flow(\"{flow_id}\", authenticated_client, env_config, runtime_context)：{nodeid}"
                )


def pytest_collection_command(errors: list[str]) -> list[str] | None:
    configured = os.environ.get(PYTEST_EXECUTABLE_ENV, "").strip()
    if configured:
        pytest_executable = Path(configured)
        if not pytest_executable.is_file():
            errors.append(f"pytest 收集校验失败，{PYTEST_EXECUTABLE_ENV} 指向的 pytest 可执行文件不存在：{pytest_executable}")
            return None
        return [str(pytest_executable), "--collect-only", "-q"]
    return [sys.executable, "-m", "pytest", "--collect-only", "-q"]


def validate_pytest_collection(framework: Path, expected_nodeids: list[str], errors: list[str]) -> None:
    command = pytest_collection_command(errors)
    if command is None:
        return
    try:
        result = subprocess.run(
            command,
            cwd=framework,
            text=True,
            capture_output=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired as exc:
        errors.append(f"pytest 收集校验超时，不能声明脚本覆盖闭环：{exc}")
        return
    if result.returncode != 0:
        output = "\n".join((result.stdout + result.stderr).splitlines()[:8])
        errors.append(f"pytest 收集校验失败，不能声明脚本覆盖闭环：{output}")
        return

    collected = {
        line.strip()
        for line in result.stdout.splitlines()
        if "::" in line and not line.lstrip().startswith(("ERROR", "FAILED"))
    }
    if not collected:
        errors.append("pytest 收集校验未发现任何测试 nodeid，不能声明脚本覆盖闭环")
        return
    missing = sorted(set(expected_nodeids) - collected)
    extra = sorted(collected - set(expected_nodeids))
    if missing:
        errors.append(f"pytest 收集结果缺少 generation_status.yaml 声明的 nodeid：{missing}")
    if extra:
        errors.append(f"pytest 收集结果存在未映射 nodeid：{extra}")


def extract_table_case_records(text: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    header: list[str] | None = None
    for raw_line in text.splitlines():
        cells = split_markdown_row(raw_line)
        if not cells:
            if not raw_line.strip():
                header = None
            continue
        if all(field in cells for field in EXECUTABLE_TRACE_FIELDS):
            header = cells
            continue
        if header is None or len(cells) != len(header):
            continue
        records.append({name: value for name, value in zip(header, cells)})
    return records


def extract_block_case_records(text: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    field_pattern = re.compile(r"^(?:[-*]\s*)?(用例ID|设计级用例ID|覆盖对象ID|覆盖规则ID|追溯测试点)\s*[：:]\s*(.*?)\s*$")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = field_pattern.match(line)
        if not match:
            continue
        field, value = match.group(1), match.group(2).strip()
        if field == "用例ID":
            if current is not None:
                records.append(current)
            current = {}
        if current is not None:
            current[field] = value
    if current is not None:
        records.append(current)
    return records


def invalid_trace_value(value: str | None) -> bool:
    if value is None:
        return True
    normalized = value.strip().strip("|").strip()
    return normalized in {"", "-", "无", "暂无", "UNKNOWN", "N/A", "NA", "null", "None"}


def invalid_source_ref(value: str | None) -> bool:
    if value is None:
        return True
    normalized = value.strip().strip("\"'").strip()
    return normalized in {"", "-", "无", "暂无", "UNKNOWN", "N/A", "NA", "null", "None"}


def yaml_key_block(text: str, key: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = re.match(rf"^(\s*){re.escape(key)}\s*:\s*(.*?)\s*$", line)
        if not match:
            continue
        base_indent = len(match.group(1))
        block = [match.group(2).strip()]
        for nested in lines[index + 1 :]:
            if nested.strip() and len(nested) - len(nested.lstrip(" ")) <= base_indent:
                break
            block.append(nested)
        return "\n".join(block)
    return ""


def scalar_from_block(block: str, key: str) -> str | None:
    first_line = block.splitlines()[0].strip() if block.splitlines() else ""
    if first_line.startswith("{") and first_line.endswith("}"):
        inline = parse_inline_mapping(first_line.strip("{}"))
        if key in inline:
            return inline[key]
    return first_yaml_scalar(block, key)


def gate_pass_status_from_block(block: str) -> str | None:
    return scalar_from_block(block, "status") or scalar_from_block(block, "result")


def extract_fact_source_items(text: str) -> list[dict[str, str]]:
    section = yaml_section(text, "fact_sources")
    items: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw_line in section.splitlines():
        stripped = raw_line.strip()
        inline_match = re.match(r"^-\s*\{(.+)\}\s*$", stripped)
        if inline_match:
            if current is not None:
                items.append(current)
                current = None
            items.append(parse_inline_mapping(inline_match.group(1)))
            continue
        item_match = re.match(r"^-\s+([A-Za-z0-9_]+)\s*:\s*(.*?)\s*$", stripped)
        if item_match:
            if current is not None:
                items.append(current)
            current = {item_match.group(1): item_match.group(2).strip().strip("\"'")}
            continue
        if current is None:
            continue
        scalar_match = re.match(r"^([A-Za-z0-9_]+)\s*:\s*(.*?)\s*$", stripped)
        if scalar_match:
            current[scalar_match.group(1)] = scalar_match.group(2).strip().strip("\"'")
    if current is not None:
        items.append(current)
    return items


def account_marker_value_requires_login(value: str | None) -> bool:
    normalized = (value or "").strip().strip("\"'").lower()
    return normalized not in ACCOUNT_NOT_REQUIRED_VALUES


def item_marks_account_specific(item: dict[str, str]) -> bool:
    fact_type = item.get("fact_type")
    if fact_type == ACCOUNT_SPECIFIC_CHAIN_FACT_TYPE:
        return True
    for key in ACCOUNT_SPECIFIC_MARKER_KEYS:
        if key not in item:
            continue
        if key in {"specific_account_required", "requires_specific_account", "account_specific"}:
            if is_yaml_true(item.get(key) or ""):
                return True
            continue
        if account_marker_value_requires_login(item.get(key)):
            return True
    return False


def fact_sources_need_login_entry_rule(fact_items: list[dict[str, str]]) -> bool:
    return any(item_marks_account_specific(item) for item in fact_items)


def has_confirmed_fact_type(
    facts_by_type: dict[str, list[dict[str, str]]],
    fact_type: str,
) -> bool:
    return any(
        item.get("source_status") == CONFIRMED_FACT_STATUS and not invalid_source_ref(item.get("source_ref"))
        for item in facts_by_type.get(fact_type, [])
    )


def runtime_ref_id(source_ref: str | None) -> str | None:
    if invalid_source_ref(source_ref):
        return None
    normalized = (source_ref or "").strip().strip("\"'")
    if "#" not in normalized:
        return None
    return normalized.rsplit("#", 1)[1].strip()


def secret_value_is_redacted(value: str | None) -> bool:
    normalized = (value or "").strip().strip("\"'")
    if not normalized:
        return True
    lowered = normalized.lower()
    if lowered in {"redacted", "<redacted>", "***", "******", "已脱敏", "脱敏", "masked", "none", "null"}:
        return True
    if normalized.startswith("${") and normalized.endswith("}"):
        return True
    if normalized.startswith("$."):
        return True
    return False


def validate_no_plain_runtime_secrets(text: str, errors: list[str], label: str) -> None:
    secret_key_pattern = re.compile(
        r"(?im)^\s*(?:-\s*)?(password|passwd|pwd|authorization|cookie|set_cookie|access_token|refresh_token|token)\s*:\s*(.+?)\s*$"
    )
    for match in secret_key_pattern.finditer(text):
        key, value = match.group(1), match.group(2).strip()
        if not secret_value_is_redacted(value):
            errors.append(f"{label} 存在未脱敏敏感字段：{key}")

    for pattern_name, pattern in (
        ("Authorization", re.compile(r"(?i)\bAuthorization\s*[:=]\s*(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{8,}")),
        ("Cookie", re.compile(r"(?i)\bCookie\s*[:=]\s*[^,\n;=]+=[^,\n;]{4,}")),
        ("password", re.compile(r"(?i)\bpassword\s*[:=]\s*(?!\$\{|\*{3,}|<redacted>|redacted)[^\s,\n]{4,}")),
    ):
        if pattern.search(text):
            errors.append(f"{label} 存在疑似未脱敏 {pattern_name} 明文")

    for block in yaml_sequence_raw_blocks(text, "evidence_items", "evidence_id"):
        evidence_id = block_first_scalar(block, "evidence_id") or "UNKNOWN"
        if block_first_scalar(block, "value_type") != "token":
            continue
        field_value = block_first_scalar(block, "field_value")
        redacted = is_yaml_true(block_first_scalar(block, "redacted") or "")
        if not redacted and not secret_value_is_redacted(field_value):
            errors.append(f"{label} {evidence_id} token 证据必须脱敏，不得写入明文 token")


def validate_runtime_plan_common(
    text: str,
    errors: list[str],
    label: str,
    required_keys: tuple[str, ...],
    expected_stage: str,
) -> str | None:
    require_yaml_top_level_keys(text, required_keys, errors, label)
    schema_version = yaml_int_value(text, "schema_version", errors, label)
    if schema_version is not None and schema_version != 1:
        errors.append(f"{label} schema_version 不是 1：{schema_version}")
    stage = first_yaml_scalar(text, "stage")
    if stage != expected_stage:
        errors.append(f"{label} stage 不匹配：{stage} != {expected_stage}")
    status = first_yaml_scalar(text, "status")
    if status not in RUNTIME_PLAN_STATUS_VALUES:
        errors.append(f"{label} status 非法或缺失：{status}")
    validate_no_plain_runtime_secrets(text, errors, label)
    return status


def validate_runtime_risk_audit_file(text: str, errors: list[str]) -> set[str]:
    label = RUNTIME_RISK_AUDIT
    status = validate_runtime_plan_common(
        text,
        errors,
        label,
        RUNTIME_RISK_AUDIT_REQUIRED_KEYS,
        "runtime_evidence_planning",
    )
    if status == "passed":
        next_stage_allowed = first_yaml_scalar(text, "next_stage_allowed")
        if next_stage_allowed is None or not is_yaml_true(next_stage_allowed):
            errors.append(f"{label} next_stage_allowed 不是 true：{next_stage_allowed}")
    policy_project_values = first_yaml_scalar(text, "project_specific_values_allowed")
    if policy_project_values is not None and is_yaml_true(policy_project_values):
        errors.append(f"{label} 不得允许项目专属值沉淀到通用规划策略")
    blind_execution = first_yaml_scalar(text, "blind_all_interface_execution_allowed")
    if blind_execution is not None and is_yaml_true(blind_execution):
        errors.append(f"{label} 不得允许无差别请求所有接口")

    allowed_case_ids: set[str] = set()
    observed_risk_counts = {risk_level: 0 for risk_level in RUNTIME_RISK_LEVELS}
    observed_decision_counts = {decision: 0 for decision in RUNTIME_REQUEST_DECISIONS}
    item_blocks = yaml_sequence_raw_blocks(text, "items", "item_id")
    if status == "passed" and not item_blocks:
        errors.append(f"{label} passed 状态下 items 不能为空")
    for block in item_blocks:
        item_id = block_first_scalar(block, "item_id") or "UNKNOWN"
        case_id = block_first_scalar(block, "case_id")
        risk_level = block_first_scalar(block, "risk_level")
        request_decision = block_first_scalar(block, "request_decision")
        if not case_id or invalid_coverage_point_value(case_id):
            errors.append(f"{label} {item_id} 缺少有效 case_id")
        if risk_level not in RUNTIME_RISK_LEVELS:
            errors.append(f"{label} {item_id} risk_level 非法或缺失：{risk_level}")
        else:
            observed_risk_counts[risk_level] += 1
        if request_decision not in RUNTIME_REQUEST_DECISIONS:
            errors.append(f"{label} {item_id} request_decision 非法或缺失：{request_decision}")
        else:
            observed_decision_counts[request_decision] += 1
        if not block_list_values(block, "reason_codes"):
            errors.append(f"{label} {item_id} 缺少 reason_codes")
        if invalid_source_ref(block_first_scalar(block, "source_case_ref")):
            errors.append(f"{label} {item_id} source_case_ref 为空或无效")
        if request_decision in {"request_allowed", "request_allowed_with_user_config"} and case_id:
            allowed_case_ids.add(case_id)
    risk_summary_section = yaml_section(text, "risk_summary")
    for risk_level in sorted(RUNTIME_RISK_LEVELS):
        actual_count = yaml_int_value(risk_summary_section, risk_level, errors, f"{label}.risk_summary")
        if actual_count is not None and actual_count != observed_risk_counts[risk_level]:
            errors.append(
                f"{label} risk_summary.{risk_level} 与 items 明细不一致："
                f"{actual_count} != {observed_risk_counts[risk_level]}"
            )
    decision_summary_section = yaml_section(text, "request_decision_summary")
    for decision in sorted(RUNTIME_REQUEST_DECISIONS):
        actual_count = yaml_int_value(decision_summary_section, decision, errors, f"{label}.request_decision_summary")
        if actual_count is not None and actual_count != observed_decision_counts[decision]:
            errors.append(
                f"{label} request_decision_summary.{decision} 与 items 明细不一致："
                f"{actual_count} != {observed_decision_counts[decision]}"
            )
    return allowed_case_ids


def validate_runtime_request_plan_skeleton_file(
    text: str,
    errors: list[str],
    allowed_case_ids: set[str],
) -> None:
    label = RUNTIME_REQUEST_PLAN_SKELETON
    validate_runtime_plan_common(
        text,
        errors,
        label,
        RUNTIME_REQUEST_PLAN_SKELETON_REQUIRED_KEYS,
        "runtime_request_plan_skeleton",
    )
    next_stage_allowed = first_yaml_scalar(text, "next_stage_allowed")
    if next_stage_allowed is not None and is_yaml_true(next_stage_allowed):
        errors.append(f"{label} 是 skeleton，不应直接允许进入请求执行")

    for block in yaml_sequence_raw_blocks(text, "steps", "step_id"):
        step_id = block_first_scalar(block, "step_id") or "UNKNOWN"
        case_id = block_first_scalar(block, "case_id")
        if not case_id or invalid_coverage_point_value(case_id):
            errors.append(f"{label} {step_id} 缺少有效 case_id")
            continue
        if allowed_case_ids and case_id not in allowed_case_ids:
            errors.append(f"{label} {step_id} 引用了未被风险审计允许请求的 case_id：{case_id}")
        if invalid_source_ref(block_first_scalar(block, "assertions_ref")):
            errors.append(f"{label} {step_id} assertions_ref 为空或无效")
        if invalid_source_ref(block_first_scalar(block, "risk_audit_ref")):
            errors.append(f"{label} {step_id} risk_audit_ref 为空或无效")


def validate_db_before_after_probe_plan_file(text: str, errors: list[str]) -> None:
    label = DB_BEFORE_AFTER_PROBE_PLAN
    validate_runtime_plan_common(
        text,
        errors,
        label,
        DB_BEFORE_AFTER_PROBE_PLAN_REQUIRED_KEYS,
        "db_before_after_probe_planning",
    )
    for block in yaml_sequence_raw_blocks(text, "probes", "probe_id"):
        probe_id = block_first_scalar(block, "probe_id") or "UNKNOWN"
        if not block_first_scalar(block, "case_id"):
            errors.append(f"{label} {probe_id} 缺少 case_id")
        if not is_yaml_true(block_first_scalar(block, "ownership_key_required") or ""):
            errors.append(f"{label} {probe_id} ownership_key_required 必须为 true")
        if not is_yaml_true(block_first_scalar(block, "cleanup_strategy_required") or ""):
            errors.append(f"{label} {probe_id} cleanup_strategy_required 必须为 true")
        if invalid_source_ref(block_first_scalar(block, "expected_delta_source_ref")):
            errors.append(f"{label} {probe_id} expected_delta_source_ref 为空或无效")
        if invalid_source_ref(block_first_scalar(block, "risk_audit_ref")):
            errors.append(f"{label} {probe_id} risk_audit_ref 为空或无效")


def validate_runtime_blocker_candidates_file(text: str, errors: list[str]) -> None:
    label = RUNTIME_BLOCKER_CANDIDATES
    validate_runtime_plan_common(
        text,
        errors,
        label,
        RUNTIME_BLOCKER_CANDIDATES_REQUIRED_KEYS,
        "runtime_blocker_candidate_collection",
    )
    for block in yaml_sequence_raw_blocks(text, "blocking_items", "blocker_id"):
        blocker_id = block_first_scalar(block, "blocker_id") or "UNKNOWN"
        if not block_first_scalar(block, "case_id"):
            errors.append(f"{label} {blocker_id} 缺少 case_id")
        if block_first_scalar(block, "risk_level") not in RUNTIME_RISK_LEVELS:
            errors.append(f"{label} {blocker_id} risk_level 非法")
        if not block_list_values(block, "reason_codes"):
            errors.append(f"{label} {blocker_id} 缺少 reason_codes")
        if not block_list_values(block, "needed_input"):
            errors.append(f"{label} {blocker_id} 缺少 needed_input")
        if invalid_source_ref(block_first_scalar(block, "risk_audit_ref")):
            errors.append(f"{label} {blocker_id} risk_audit_ref 为空或无效")


def validate_runtime_evidence_plan(root: Path, errors: list[str]) -> None:
    plan_dir = root / RUNTIME_EVIDENCE_PLAN_DIR
    if not plan_dir.exists():
        return
    require(plan_dir.is_dir(), errors, f"运行时取证规划路径不是目录：{plan_dir}")
    if not plan_dir.is_dir():
        return

    for filename in RUNTIME_EVIDENCE_PLAN_REQUIRED_FILES:
        require((plan_dir / filename).is_file(), errors, f"运行时取证规划目录缺少文件：{filename}")

    texts: dict[str, str] = {}
    for filename in RUNTIME_EVIDENCE_PLAN_REQUIRED_FILES:
        path = plan_dir / filename
        if not path.is_file():
            continue
        try:
            texts[filename] = read_text(path)
        except ValueError as exc:
            errors.append(str(exc))

    allowed_case_ids: set[str] = set()
    if RUNTIME_RISK_AUDIT in texts:
        allowed_case_ids = validate_runtime_risk_audit_file(texts[RUNTIME_RISK_AUDIT], errors)
    if RUNTIME_REQUEST_PLAN_SKELETON in texts:
        validate_runtime_request_plan_skeleton_file(
            texts[RUNTIME_REQUEST_PLAN_SKELETON],
            errors,
            allowed_case_ids,
        )
    if DB_BEFORE_AFTER_PROBE_PLAN in texts:
        validate_db_before_after_probe_plan_file(texts[DB_BEFORE_AFTER_PROBE_PLAN], errors)
    if RUNTIME_BLOCKER_CANDIDATES in texts:
        validate_runtime_blocker_candidates_file(texts[RUNTIME_BLOCKER_CANDIDATES], errors)


def validate_runtime_queue_section(text: str, errors: list[str], label: str, section_name: str = "continuation_queue") -> None:
    section = yaml_section(text, section_name)
    if not section:
        return
    if re.search(r"(?m)^\s+status\s*:", section):
        errors.append(f"{label} {section_name} 内禁止使用 status 字段，请使用 queue_state")
    for raw_value in re.findall(r"(?m)^\s+queue_state\s*:\s*([^\n#]+)", section):
        value = raw_value.strip().strip("\"'")
        if value not in RUNTIME_QUEUE_STATE_VALUES:
            errors.append(f"{label} {section_name}.queue_state 非法：{value}")


def validate_runtime_queue_file(text: str, errors: list[str]) -> None:
    label = RUNTIME_EVIDENCE_QUEUE
    require_yaml_top_level_keys(text, ("schema_version", "stage", "status", "queue_state_field", "items"), errors, label)
    schema_version = yaml_int_value(text, "schema_version", errors, label)
    if schema_version is not None and schema_version != 1:
        errors.append(f"{label} schema_version 不是 1：{schema_version}")
    stage = first_top_level_yaml_scalar(text, "stage")
    if stage != "runtime_evidence_continuation_queue":
        errors.append(f"{label} stage 不匹配：{stage} != runtime_evidence_continuation_queue")
    status = first_top_level_yaml_scalar(text, "status")
    if status not in RUNTIME_STATUS_VALUES:
        errors.append(f"{label} status 非法或缺失：{status}")
    if first_top_level_yaml_scalar(text, "queue_state_field") != "queue_state":
        errors.append(f"{label} queue_state_field 必须为 queue_state")
    validate_runtime_queue_section(text, errors, label, "items")


def validate_runtime_stage_status(text: str, errors: list[str], require_passed: bool) -> None:
    label = RUNTIME_STAGE_STATUS
    require_yaml_top_level_keys(text, RUNTIME_STAGE_STATUS_REQUIRED_KEYS, errors, label)
    schema_version = yaml_int_value(text, "schema_version", errors, label)
    if schema_version is not None and schema_version != 1:
        errors.append(f"{label} schema_version 不是 1：{schema_version}")
    validate_runtime_queue_section(text, errors, label)
    stage = first_top_level_yaml_scalar(text, "stage")
    if stage != "runtime_live_evidence":
        errors.append(f"{label} stage 不匹配：{stage} != runtime_live_evidence")
    status = first_top_level_yaml_scalar(text, "status")
    if status not in RUNTIME_STATUS_VALUES:
        errors.append(f"{label} status 非法或缺失：{status}")
    next_stage_allowed = first_top_level_yaml_scalar(text, "next_stage_allowed")
    if require_passed and status not in {"passed", "partial"}:
        errors.append(f"{label} 被执行事实引用时 status 必须为 passed 或 partial：{status}")
    if status == "passed" or require_passed:
        if next_stage_allowed is None or not is_yaml_true(next_stage_allowed):
            errors.append(f"{label} next_stage_allowed 不是 true：{next_stage_allowed}")
        require_yaml_empty_list(text, "blocking_issues", errors, label)
    elif next_stage_allowed is not None and is_yaml_true(next_stage_allowed):
        require_yaml_empty_list(text, "blocking_issues", errors, label)


def validate_runtime_script_materialization_contract(block: str, evidence_id: str, errors: list[str]) -> None:
    label = RUNTIME_EVIDENCE
    required_groups = (
        ("case_id_or_flow_id", ("case_id", "flow_id"), True),
        ("step_id_or_step_order", ("step_id", "step_order"), True),
        ("module", ("module",), True),
        ("method", ("method",), True),
        ("path", ("path",), True),
        ("base_url_alias", ("base_url_alias",), True),
        ("session_role", ("session_role",), True),
        ("auth_policy", ("auth_policy",), True),
        ("token_injection_location", ("token_injection_location", "token_injection"), True),
        ("request_plaintext", ("request_plaintext", "request_plaintext_ref"), False),
        ("response_plaintext", ("response_plaintext", "response_plaintext_ref"), False),
        ("assertion_candidates", ("assertion_candidates", "assertions_ref"), False),
        ("setup_data", ("setup_data", "setup"), False),
        ("cleanup", ("cleanup", "cleanup_data"), False),
        ("assertion_strength", ("assertion_strength",), True),
        ("result_observation_mode", ("result_observation_mode",), True),
        ("script_materialization_ready", ("script_materialization_ready",), True),
        ("missing_materialization_items", ("missing_materialization_items",), False),
    )
    for field_label, keys, require_non_empty_scalar in required_groups:
        if require_non_empty_scalar:
            has_field = block_has_any_scalar(block, keys)
        else:
            has_field = block_has_any_key(block, keys)
        if not has_field:
            errors.append(f"{label} {evidence_id} 缺少可脚本化 evidence 字段：{field_label}")

    ready = is_yaml_true(block_first_scalar(block, "script_materialization_ready") or "")
    missing_items = block_first_scalar(block, "missing_materialization_items")
    if ready and missing_items not in {"[]", None}:
        errors.append(f"{label} {evidence_id} missing_materialization_items 未清空：{missing_items}")


def validate_runtime_evidence_file(text: str, errors: list[str], require_usable: bool) -> set[str]:
    label = RUNTIME_EVIDENCE
    require_yaml_top_level_keys(text, RUNTIME_EVIDENCE_REQUIRED_KEYS, errors, label)
    schema_version = yaml_int_value(text, "schema_version", errors, label)
    if schema_version is not None and schema_version != 1:
        errors.append(f"{label} schema_version 不是 1：{schema_version}")
    stage = first_yaml_scalar(text, "stage")
    if stage != "runtime_live_evidence":
        errors.append(f"{label} stage 不匹配：{stage} != runtime_live_evidence")
    status = first_yaml_scalar(text, "status")
    if status not in RUNTIME_STATUS_VALUES:
        errors.append(f"{label} status 非法或缺失：{status}")
    if require_usable and status not in {"passed", "partial"}:
        errors.append(f"{label} 被执行事实引用时 status 必须为 passed 或 partial：{status}")
    if status in {"passed", "partial"} or require_usable:
        require_yaml_empty_list(text, "conflict_items", errors, label)
    if status == "passed":
        require_yaml_empty_list(text, "blocking_issues", errors, label)

    validate_no_plain_runtime_secrets(text, errors, label)
    confirmed_ids: set[str] = set()
    blocks = yaml_sequence_raw_blocks(text, "evidence_items", "evidence_id")
    if status == "passed" and not blocks:
        errors.append(f"{label} passed 状态下 evidence_items 不能为空")
    for block in blocks:
        evidence_id = block_first_scalar(block, "evidence_id") or "UNKNOWN"
        source_status = block_first_scalar(block, "source_status")
        if source_status not in RUNTIME_ALLOWED_SOURCE_STATUS:
            errors.append(f"{label} {evidence_id} source_status 非法或缺失：{source_status}")
        usable = is_yaml_true(block_first_scalar(block, "usable_for_execution_case") or "")
        if usable and source_status != "confirmed":
            errors.append(f"{label} {evidence_id} 可用于执行级用例时 source_status 必须为 confirmed")
        if block_has_key(block, "script_materialization_ready"):
            validate_runtime_script_materialization_contract(block, evidence_id, errors)
        if source_status == "confirmed" and usable:
            confirmed_ids.add(evidence_id)
    return confirmed_ids


def validate_runtime_value_catalog_file(text: str, errors: list[str], require_usable: bool) -> set[str]:
    label = RUNTIME_VALUE_CATALOG
    require_yaml_top_level_keys(text, RUNTIME_VALUE_CATALOG_REQUIRED_KEYS, errors, label)
    schema_version = yaml_int_value(text, "schema_version", errors, label)
    if schema_version is not None and schema_version != 1:
        errors.append(f"{label} schema_version 不是 1：{schema_version}")
    stage = first_yaml_scalar(text, "stage")
    if stage != "runtime_value_catalog":
        errors.append(f"{label} stage 不匹配：{stage} != runtime_value_catalog")
    status = first_yaml_scalar(text, "status")
    if status not in RUNTIME_STATUS_VALUES:
        errors.append(f"{label} status 非法或缺失：{status}")
    if require_usable and status not in {"passed", "partial"}:
        errors.append(f"{label} 被执行事实引用时 status 必须为 passed 或 partial：{status}")
    if status in {"passed", "partial"} or require_usable:
        require_yaml_empty_list(text, "conflict_values", errors, label)
    if status == "passed":
        require_yaml_empty_list(text, "blocking_issues", errors, label)

    validate_no_plain_runtime_secrets(text, errors, label)
    confirmed_ids: set[str] = set()
    blocks = yaml_sequence_raw_blocks(text, "values", "value_id")
    if status == "passed" and not blocks:
        errors.append(f"{label} passed 状态下 values 不能为空")
    for block in blocks:
        value_id = block_first_scalar(block, "value_id") or "UNKNOWN"
        source_status = block_first_scalar(block, "source_status")
        if source_status not in RUNTIME_ALLOWED_SOURCE_STATUS:
            errors.append(f"{label} {value_id} source_status 非法或缺失：{source_status}")
        if source_status == "confirmed":
            confirmed_ids.add(value_id)
    return confirmed_ids


def validate_runtime_evidence(root: Path, errors: list[str], required: bool, require_usable: bool) -> dict[str, set[str]]:
    runtime_dir = root / RUNTIME_EVIDENCE_DIR
    result = {"evidence_ids": set(), "value_ids": set()}
    if not runtime_dir.exists():
        if required:
            errors.append(f"执行事实引用 live_request_evidence 时缺少运行时取证目录：{runtime_dir}")
        return result
    require(runtime_dir.is_dir(), errors, f"运行时取证路径不是目录：{runtime_dir}")
    if not runtime_dir.is_dir():
        return result

    for filename in RUNTIME_EVIDENCE_REQUIRED_FILES:
        require((runtime_dir / filename).is_file(), errors, f"运行时取证目录缺少文件：{filename}")

    texts: dict[str, str] = {}
    for filename in RUNTIME_EVIDENCE_REQUIRED_FILES:
        path = runtime_dir / filename
        if not path.is_file():
            continue
        try:
            texts[filename] = read_text(path)
        except ValueError as exc:
            errors.append(str(exc))
    queue_path = runtime_dir / RUNTIME_EVIDENCE_QUEUE
    if queue_path.is_file():
        try:
            texts[RUNTIME_EVIDENCE_QUEUE] = read_text(queue_path)
        except ValueError as exc:
            errors.append(str(exc))
    if RUNTIME_STAGE_STATUS in texts:
        validate_runtime_stage_status(texts[RUNTIME_STAGE_STATUS], errors, require_usable)
    if RUNTIME_EVIDENCE in texts:
        result["evidence_ids"] = validate_runtime_evidence_file(texts[RUNTIME_EVIDENCE], errors, require_usable)
    if RUNTIME_VALUE_CATALOG in texts:
        result["value_ids"] = validate_runtime_value_catalog_file(texts[RUNTIME_VALUE_CATALOG], errors, require_usable)
    if RUNTIME_EVIDENCE_QUEUE in texts:
        validate_runtime_queue_file(texts[RUNTIME_EVIDENCE_QUEUE], errors)
    return result


def validate_live_request_fact_source_refs(
    fact_text: str,
    runtime_index: dict[str, set[str]],
    errors: list[str],
) -> None:
    live_items = [
        item for item in extract_fact_source_items(fact_text)
        if item.get("source_type") == "live_request_evidence"
    ]
    if not live_items:
        return
    valid_ids = runtime_index["evidence_ids"] | runtime_index["value_ids"]
    if not valid_ids:
        errors.append("execution_fact_sources.yaml 引用 live_request_evidence，但未找到可用的 confirmed 运行时证据 ID")
        return
    for item in live_items:
        fact_id = item.get("fact_id") or item.get("fact_type") or "UNKNOWN"
        if item.get("source_status") != CONFIRMED_FACT_STATUS:
            errors.append(f"execution_fact_sources.yaml live_request_evidence[{fact_id}].source_status 不是 confirmed")
        ref_id = runtime_ref_id(item.get("source_ref"))
        if not ref_id:
            errors.append(f"execution_fact_sources.yaml live_request_evidence[{fact_id}].source_ref 必须引用运行时证据 ID")
            continue
        if ref_id not in valid_ids:
            errors.append(f"execution_fact_sources.yaml live_request_evidence[{fact_id}] 引用的证据 ID 不存在或不可用：{ref_id}")


def validate_execution_fact_sources_passed(text: str, errors: list[str]) -> None:
    for input_key in REQUIRED_HUMAN_INPUTS:
        block = yaml_key_block(text, input_key)
        if not block:
            errors.append(f"execution_fact_sources.yaml 缺少必填人工输入状态：{input_key}")
            continue
        status = scalar_from_block(block, "status")
        source_ref = scalar_from_block(block, "source_ref")
        if status != "provided":
            errors.append(f"execution_fact_sources.yaml {input_key}.status 不是 provided：{status}")
        if invalid_source_ref(source_ref):
            errors.append(f"execution_fact_sources.yaml {input_key}.source_ref 为空或无效")

    fact_items = extract_fact_source_items(text)
    if not fact_items:
        errors.append("execution_fact_sources.yaml fact_sources 为空或无法解析")
        return
    facts_by_type: dict[str, list[dict[str, str]]] = {}
    for item in fact_items:
        fact_type = item.get("fact_type", "")
        if fact_type:
            facts_by_type.setdefault(fact_type, []).append(item)
        status = item.get("source_status")
        fact_id = item.get("fact_id") or fact_type or "UNKNOWN"
        if status != CONFIRMED_FACT_STATUS:
            errors.append(f"execution_fact_sources.yaml fact_sources[{fact_id}].source_status 不是 confirmed：{status}")
        if invalid_source_ref(item.get("source_ref")):
            errors.append(f"execution_fact_sources.yaml fact_sources[{fact_id}].source_ref 为空或无效")

    for fact_type in REQUIRED_EXECUTION_FACT_TYPES:
        items = facts_by_type.get(fact_type, [])
        if not items:
            errors.append(f"execution_fact_sources.yaml 缺少执行事实类型索引：{fact_type}")
            continue
        if not any(
            item.get("source_status") == CONFIRMED_FACT_STATUS and not invalid_source_ref(item.get("source_ref"))
            for item in items
        ):
            errors.append(f"execution_fact_sources.yaml {fact_type} 缺少 confirmed 且 source_ref 有效的事实来源")

    if fact_sources_need_login_entry_rule(fact_items) and not has_confirmed_fact_type(facts_by_type, LOGIN_ENTRY_FACT_TYPE):
        errors.append("execution_fact_sources.yaml 账号型长链路缺少 confirmed 且 source_ref 有效的 login_entry_rule")

    database_backed_setup_or_cleanup = any(
        item.get("fact_type") in {"test_data_rule", "cleanup_strategy"}
        and (
            item.get("source_type") == "data_model"
            or "数据模型" in (item.get("source_ref") or "")
            or "database" in (item.get("source_ref") or "").lower()
            or "sql" in (item.get("source_ref") or "").lower()
        )
        for item in fact_items
    )
    precondition_seeded_values = any(
        item.get("fact_type") in {"seed_value", "test_data_rule"}
        and item.get("source_type") in {"precondition_api_response", "db_seed_evidence", "data_model"}
        for item in fact_items
    )
    if database_backed_setup_or_cleanup:
        for fact_type in DATABASE_EXECUTION_FACT_TYPES:
            items = facts_by_type.get(fact_type, [])
            if not items:
                errors.append(f"execution_fact_sources.yaml 数据库铺数/清理缺少执行事实类型索引：{fact_type}")
                continue
            if not any(
                item.get("source_status") == CONFIRMED_FACT_STATUS and not invalid_source_ref(item.get("source_ref"))
                for item in items
            ):
                errors.append(f"execution_fact_sources.yaml 数据库铺数/清理的 {fact_type} 缺少 confirmed 且 source_ref 有效的事实来源")
    elif precondition_seeded_values:
        items = facts_by_type.get("seed_scope_guard", [])
        if not any(
            item.get("source_status") == CONFIRMED_FACT_STATUS and not invalid_source_ref(item.get("source_ref"))
            for item in items
        ):
            errors.append("execution_fact_sources.yaml 前置造数缺少 confirmed 且 source_ref 有效的 seed_scope_guard")


def validate_execution_fact_sources(executable_dir: Path, errors: list[str], require_passed: bool) -> str:
    path = executable_dir / "execution_fact_sources.yaml"
    text = read_sidecar(path, errors, "执行事实来源索引")
    if not text:
        return ""
    require_yaml_top_level_keys(text, EXECUTION_FACT_SOURCE_REQUIRED_KEYS, errors, "execution_fact_sources.yaml")
    schema_version = yaml_int_value(text, "schema_version", errors, "execution_fact_sources.yaml")
    if schema_version is not None and schema_version != 1:
        errors.append(f"execution_fact_sources.yaml schema_version 不是 1：{schema_version}")
    stage = first_yaml_scalar(text, "stage")
    if stage != "executable_interface_case_set":
        errors.append(f"execution_fact_sources.yaml stage 不匹配：{stage} != executable_interface_case_set")
    status = first_yaml_scalar(text, "status")
    if status not in {"passed", "blocked", "failed"}:
        errors.append(f"execution_fact_sources.yaml status 非法或缺失：{status}")
    for required_marker in REQUIRED_HUMAN_INPUTS:
        if required_marker not in text:
            errors.append(f"execution_fact_sources.yaml 缺少必填人工输入状态：{required_marker}")
    for fact_type in REQUIRED_EXECUTION_FACT_TYPES:
        if fact_type not in text:
            errors.append(f"execution_fact_sources.yaml 缺少执行事实类型索引：{fact_type}")
    if require_passed:
        if status != "passed":
            errors.append(f"execution_fact_sources.yaml status 不是 passed：{status}")
        for key in ("missing_required_facts", "conflict_facts", "blocking_issues"):
            require_yaml_empty_list(text, key, errors, "execution_fact_sources.yaml")
        validate_execution_fact_sources_passed(text, errors)
    return text


def validate_apifox_evidence_index(
    executable_dir: Path,
    errors: list[str],
    require_passed: bool,
    required: bool,
) -> None:
    path = executable_dir / "apifox_evidence_index.yaml"
    if not path.is_file():
        if required:
            errors.append(f"Apifox 证据索引 缺少结构化 sidecar：{path.name}")
        return
    text = read_sidecar(path, errors, "Apifox 证据索引")
    if not text:
        return
    require_yaml_top_level_keys(text, APIFOX_EVIDENCE_REQUIRED_KEYS, errors, "apifox_evidence_index.yaml")
    schema_version = yaml_int_value(text, "schema_version", errors, "apifox_evidence_index.yaml")
    if schema_version is not None and schema_version != 1:
        errors.append(f"apifox_evidence_index.yaml schema_version 不是 1：{schema_version}")
    stage = first_yaml_scalar(text, "stage")
    if stage != "executable_interface_case_set":
        errors.append(f"apifox_evidence_index.yaml stage 不匹配：{stage} != executable_interface_case_set")
    status = first_yaml_scalar(text, "status")
    if status not in {"passed", "partial", "blocked", "failed"}:
        errors.append(f"apifox_evidence_index.yaml status 非法或缺失：{status}")
    for level in APIFOX_EVIDENCE_LEVELS:
        if level not in text:
            errors.append(f"apifox_evidence_index.yaml 缺少 Apifox 证据等级或处理策略：{level}")
    if "structured contract" not in text and "结构化契约" not in text:
        errors.append("apifox_evidence_index.yaml 冲突优先级缺少结构化契约冲突处理规则")
    if require_passed:
        if status != "passed":
            errors.append(f"apifox_evidence_index.yaml status 不是 passed：{status}")
        require_yaml_empty_list(text, "conflict_items", errors, "apifox_evidence_index.yaml")


def validate_retry_history(root: Path, errors: list[str], stage_status: str | None) -> None:
    path = root / "retry_history.yaml"
    if not path.is_file():
        if stage_status == "BLOCKED_RETRY_EXHAUSTED":
            errors.append("BLOCKED_RETRY_EXHAUSTED 状态必须存在 retry_history.yaml")
        return
    try:
        text = read_text(path)
    except ValueError as exc:
        errors.append(str(exc))
        return

    require_yaml_top_level_keys(text, RETRY_HISTORY_REQUIRED_KEYS, errors, "retry_history.yaml")
    schema_version = yaml_int_value(text, "schema_version", errors, "retry_history.yaml")
    if schema_version is not None and schema_version != 1:
        errors.append(f"retry_history.yaml schema_version 不是 1：{schema_version}")
    max_attempts = yaml_int_value(text, "max_attempts", errors, "retry_history.yaml")
    if max_attempts is not None and max_attempts != 3:
        errors.append(f"retry_history.yaml max_attempts 不是 3：{max_attempts}")

    status = first_yaml_scalar(text, "status")
    if status not in RETRY_HISTORY_STATUSES:
        errors.append(f"retry_history.yaml status 非法或缺失：{status}")
    if stage_status == "BLOCKED_RETRY_EXHAUSTED" and status != "blocked":
        errors.append(f"retry_history.yaml status 必须为 blocked：{status}")
    next_stage_allowed = first_yaml_scalar(text, "next_stage_allowed")
    if stage_status == "BLOCKED_RETRY_EXHAUSTED" and is_yaml_true(next_stage_allowed or ""):
        errors.append("retry_history.yaml next_stage_allowed 在重试耗尽时不能为 true")

    for key in ("retry_key", "gate_id", "producer_stage", "consumer_stage", "final_blocker"):
        if not first_yaml_scalar(text, key):
            errors.append(f"retry_history.yaml 缺少有效字段：{key}")
    for marker in ("retry_key", "gate_id", "regenerated_output_paths", "gate_result", "gate_evidence_refs"):
        if marker not in text:
            errors.append(f"retry_history.yaml attempts 缺少字段：{marker}")

    retry_keys = yaml_scalar_values(text, "retry_key")
    if retry_keys and len(set(retry_keys)) != 1:
        errors.append(f"retry_history.yaml 同一文件内 retry_key 不一致：{retry_keys}")
    gate_ids = yaml_scalar_values(text, "gate_id")
    if gate_ids and len(set(gate_ids)) != 1:
        errors.append(f"retry_history.yaml 同一文件内 gate_id 不一致：{gate_ids}")

    attempts = yaml_int_values(text, "attempt")
    if stage_status == "BLOCKED_RETRY_EXHAUSTED":
        if sorted(set(attempts)) != [1, 2, 3]:
            errors.append(f"retry_history.yaml 重试耗尽时必须记录 attempt 1、2、3：{attempts}")
    elif attempts and max(attempts) > 3:
        errors.append(f"retry_history.yaml attempt 不得超过 3：{attempts}")


def required_chain_flow_ids_from_root(root: Path, errors: list[str]) -> set[str]:
    path = root / REQUIRED_CHAIN_FLOWS
    if not path.is_file():
        return set()
    local_errors: list[str] = []
    flow_ids = validate_required_chain_flows_file(path, local_errors, require_passed=False)
    errors.extend(local_errors)
    return flow_ids


def long_chain_required_from_root(root: Path, errors: list[str]) -> bool:
    # 测试覆盖点报告和 business_scenario_map.yaml 只作为候选证据；脚本准入以 required_chain_flows.yaml 为准。
    return False


def flow_block_marks_account_specific(block: str) -> bool:
    for key in ("specific_account_required", "requires_specific_account", "account_specific"):
        if is_yaml_true(block_first_scalar(block, key) or ""):
            return True
    for key in ("required_account_role", "required_account_business_state", "required_tenant", "required_permission"):
        if account_marker_value_requires_login(block_first_scalar(block, key)):
            return True
    return "account_specific_chain" in block


def first_step_block(flow_block: str) -> str:
    steps_block = nested_yaml_block(flow_block, "steps")
    if not steps_block:
        return ""
    lines = steps_block.splitlines()
    start = None
    start_indent = 0
    for index, line in enumerate(lines):
        match = re.match(r"^(\s*)-\s+", line)
        if match:
            start = index
            start_indent = len(match.group(1))
            break
    if start is None:
        return ""
    end = len(lines)
    for index in range(start + 1, len(lines)):
        match = re.match(r"^(\s*)-\s+", lines[index])
        if match and len(match.group(1)) == start_indent:
            end = index
            break
    return "\n".join(lines[start:end])


def step_is_login_entry(step_block: str) -> bool:
    if not step_block:
        return False
    for key in ("login_entry", "is_login_step"):
        if is_yaml_true(block_first_scalar(step_block, key) or ""):
            return True
    for key in ("step_type", "auth_step", "request_role"):
        value = (block_first_scalar(step_block, key) or "").strip().strip("\"'").lower()
        if value in LOGIN_STEP_TYPE_VALUES:
            return True
    lowered = step_block.lower()
    return bool(re.search(r"(?:/|_|-|\b)(login|signin|auth|oauth|token)(?:/|_|-|\b)", lowered))


def step_has_token_extraction(step_block: str) -> bool:
    lowered = step_block.lower()
    return ("extract" in lowered or "extraction" in lowered) and "token" in lowered


def validate_account_specific_flow_login_entry(flow_cases_text: str, errors: list[str]) -> None:
    for block in yaml_sequence_raw_blocks(flow_cases_text, "flows", "flow_id"):
        if not flow_block_marks_account_specific(block):
            continue
        flow_id = block_first_scalar(block, "flow_id") or "UNKNOWN"
        step_block = first_step_block(block)
        if not step_is_login_entry(step_block):
            errors.append(f"data/flow_cases.yaml 账号型长链路首步不是登录/授权接口：{flow_id}")
            continue
        if not step_has_token_extraction(step_block):
            errors.append(f"data/flow_cases.yaml 账号型长链路登录首步缺少 token 提取规则：{flow_id}")
        if "account_context_not_required" not in step_block and not any(
            marker in step_block for marker in ("account_context", "user_id", "userId", "appUserId", "tenant", "role")
        ):
            errors.append(f"data/flow_cases.yaml 账号型长链路登录首步缺少账号上下文提取或不需要说明：{flow_id}")


def validate_required_flow_framework_files(framework: Path, required_flow_ids: set[str], long_chain_required: bool, errors: list[str]) -> None:
    if not required_flow_ids and not long_chain_required:
        return
    flow_case_files = existing_framework_files(framework, DATA_DRIVEN_FLOW_FILES)
    flow_runner = framework / "core" / "flow_runner.py"
    flow_tests = framework / "testcases" / "test_flows.py"
    if not flow_case_files:
        errors.append(f"存在必需链路脚本但缺少文件：{format_path_options(DATA_DRIVEN_FLOW_FILES)}")
    for path in (flow_runner, flow_tests):
        require(path.is_file(), errors, f"存在必需链路脚本但缺少文件：{path.relative_to(framework).as_posix()}")
    flow_text_by_file: dict[Path, str] = {}
    for flow_cases in flow_case_files:
        try:
            flow_text_by_file[flow_cases] = read_text(flow_cases)
        except ValueError as exc:
            errors.append(str(exc))
            continue
    for flow_id in sorted(required_flow_ids):
        if not any(flow_id in text for text in flow_text_by_file.values()):
            errors.append(f"{format_path_options(DATA_DRIVEN_FLOW_FILES)} 缺少上游必需 flow_id：{flow_id}")
    for flow_cases, flow_case_text in flow_text_by_file.items():
        if flow_cases.suffix == ".py":
            exports = validate_python_data_module(flow_cases, framework, "flows", errors)
            validate_account_specific_flow_login_entry_items(
                python_export_value(exports, "flows"),
                str(flow_cases.relative_to(framework)),
                errors,
            )
        else:
            validate_account_specific_flow_login_entry(flow_case_text, errors)
    if flow_tests.is_file():
        for flow_id in sorted(required_flow_ids):
            if not flow_file_contains_run_flow_call(flow_tests, flow_id, errors):
                errors.append(
                    "testcases/test_flows.py 缺少对应必测 flow 的 pytest 入口调用："
                    f"run_flow(\"{flow_id}\", authenticated_client, env_config, runtime_context)"
                )


def validate_data_driven_framework_files(framework: Path, generation_status_text: str, errors: list[str]) -> None:
    executable_counts = yaml_int_values(generation_status_text, "executable_case_count")
    executable_count = executable_counts[0] if executable_counts and len(set(executable_counts)) == 1 else 0
    if executable_count <= 0:
        return

    interface_files = existing_framework_files(framework, DATA_DRIVEN_INTERFACE_FILES)
    case_dir = framework / DATA_DRIVEN_CASE_DIR
    flow_files = existing_framework_files(framework, DATA_DRIVEN_FLOW_FILES)
    if not interface_files:
        errors.append(f"普通接口脚本必须集中维护接口定义文件：{format_path_options(DATA_DRIVEN_INTERFACE_FILES)}")
    require(case_dir.is_dir(), errors, f"普通接口脚本必须集中维护用例目录：{DATA_DRIVEN_CASE_DIR}")
    if not flow_files:
        errors.append(f"场景化自动化链路必须集中维护链路文件：{format_path_options(DATA_DRIVEN_FLOW_FILES)}")

    active_interface_sources = 0
    for interface_file in interface_files:
        try:
            interface_text = read_text(interface_file)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        relative_interface = interface_file.relative_to(framework)
        if interface_file.suffix == ".py":
            exports = validate_python_data_module(interface_file, framework, "interfaces", errors)
            interfaces = python_export_value(exports, "interfaces")
            if not isinstance(interfaces, list):
                errors.append(f"{relative_interface} INTERFACES 必须是列表")
            elif interfaces:
                active_interface_sources += 1
                for marker in ("interface_id", "method", "path"):
                    if not any(isinstance(item, dict) and item.get(marker) for item in interfaces):
                        errors.append(f"{relative_interface} 缺少接口定义字段：{marker}")
            continue
        if "interfaces" not in yaml_top_level_keys(interface_text):
            errors.append(f"{relative_interface} 缺少顶层 interfaces")
        if any(marker in interface_text for marker in ("interface_id", "method", "path")):
            active_interface_sources += 1
            for marker in ("interface_id", "method", "path"):
                if marker not in interface_text:
                    errors.append(f"{relative_interface} 缺少接口定义字段：{marker}")
    if interface_files and active_interface_sources == 0:
        errors.append(
            f"{format_path_options(DATA_DRIVEN_INTERFACE_FILES)} 缺少有效接口定义字段：interface_id/method/path"
        )

    for flow_file in flow_files:
        if flow_file.suffix == ".py":
            validate_python_data_module(flow_file, framework, "flows", errors)

    case_ids: set[str] = set()
    if case_dir.is_dir():
        case_files = sorted(
            [*case_dir.glob("*.yaml"), *case_dir.glob("*.py")],
            key=lambda path: str(path.relative_to(framework)),
        )
        if not case_files:
            errors.append(f"{DATA_DRIVEN_CASE_DIR} 下缺少可维护的用例 YAML/Python 文件")
        for case_file in case_files:
            try:
                case_text = read_text(case_file)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            relative_case = case_file.relative_to(framework)
            if case_file.suffix == ".py":
                exports = validate_python_data_module(case_file, framework, "cases", errors)
                cases = python_export_value(exports, "cases")
                if not isinstance(cases, list):
                    errors.append(f"{relative_case} CASES 必须是列表")
                    continue
                for item in cases:
                    if not isinstance(item, dict):
                        errors.append(f"{relative_case} CASES 中存在非字典用例")
                        continue
                    case_id = str(item.get("case_id") or "").strip()
                    if not case_id or invalid_coverage_point_value(case_id):
                        errors.append(f"{relative_case} 用例缺少 case_id")
                    else:
                        case_ids.add(case_id)
                    if not str(item.get("interface_id") or "").strip():
                        errors.append(f"{relative_case} 用例缺少 interface_id，无法通过接口定义文件维护 method/path")
            else:
                if "cases" not in yaml_top_level_keys(case_text):
                    errors.append(f"{relative_case} 缺少顶层 cases")
                if "interface_id" not in case_text:
                    errors.append(f"{relative_case} 用例缺少 interface_id，无法通过接口定义文件维护 method/path")
                case_ids.update(
                    value for value in yaml_scalar_values(case_text, "case_id") if not invalid_coverage_point_value(value)
                )

    pytest_section = yaml_section(generation_status_text, "pytest_collection_mapping")
    mapped_case_ids = {
        block.get("executable_case_id", "").strip()
        for block in extract_pytest_mapping_blocks(pytest_section)
        if block.get("executable_case_id")
    }
    missing_case_data = sorted(case_id for case_id in mapped_case_ids if case_id not in case_ids)
    if missing_case_data:
        errors.append(f"pytest 映射中的执行级用例未写入 data/cases 用例数据：{missing_case_data}")

    test_files = [
        path
        for path in sorted((framework / "testcases").glob("test*.py"))
        if path.name != "test_flows.py"
    ]
    if not test_files:
        errors.append("普通接口脚本缺少 pytest 参数化入口文件：testcases/test*.py")
        return
    if not any(python_file_has_parametrize(path, errors) for path in test_files):
        errors.append("普通接口脚本必须使用 pytest.mark.parametrize 从 data/cases 调用测试用例")


def dict_path(data: Any, keys: tuple[str, ...]) -> Any:
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def status_value(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    return str(data.get("status") or "").strip()


def bool_value(data: Any) -> bool:
    if isinstance(data, bool):
        return data
    return str(data).strip().lower() in {"true", "yes", "1", "passed", "是"}


def python_function_signature_args(text: str, function_name: str) -> str:
    match = re.search(rf"def\s+{re.escape(function_name)}\s*\((.*?)\)\s*(?:->[^:]+)?\:", text, re.S)
    return match.group(1) if match else ""


def python_function_source(text: str, function_name: str) -> str:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return ""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return ast.get_source_segment(text, node) or ""
    return ""


def python_method_source(text: str, class_name: str, method_name: str) -> str:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return ""
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name:
                return ast.get_source_segment(text, item) or ""
    return ""


def python_function_calls(text: str, function_name: str, target_name: str) -> bool:
    """确认目标函数内存在真实调用，避免注释、导入或属性引用造成假通过。"""

    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False
    function_node = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name
        ),
        None,
    )
    if function_node is None:
        return False
    return any(
        isinstance(node, ast.Call) and attribute_chain_name(node.func) == target_name
        for node in ast.walk(function_node)
    )


def framework_flow_has_login_step(framework: Path, errors: list[str]) -> bool:
    """仅在 E2E flow 确实包含显式登录步骤时启用登录上下文门禁。"""

    for path in existing_framework_files(framework, DATA_DRIVEN_FLOW_FILES):
        if path.suffix == ".py":
            exports = validate_python_data_module(path, framework, "flows", errors)
            flows = python_export_value(exports, "flows")
        else:
            payload = read_yaml_file(path, errors, str(path.relative_to(framework)))
            flows = payload.get("flows") if isinstance(payload, dict) else None
        if not isinstance(flows, list):
            continue
        for flow in flows:
            if not isinstance(flow, dict):
                continue
            steps = flow.get("steps")
            if not isinstance(steps, list):
                continue
            for step in steps:
                if not isinstance(step, dict):
                    continue
                step_type = str(step.get("step_type") or "").strip().lower()
                if step_type in LOGIN_STEP_TYPE_VALUES or bool_value(step.get("login_entry")):
                    return True
    return False


def validate_framework_runtime_resilience(
    framework: Path,
    errors: list[str],
    *,
    ordinary_case_required: bool = True,
    flow_required: bool | None = None,
    flow_login_required: bool | None = None,
) -> None:
    """校验生成框架的运行变量隔离、显式抽取、可靠清理和诊断证据能力。"""

    flow_runner_path = framework / "core" / "flow_runner.py"
    if flow_required is None:
        flow_required = flow_runner_path.is_file()
    if flow_login_required is None:
        flow_login_required = bool(flow_required)
    if not ordinary_case_required and not flow_required:
        return

    conftest_text = read_optional_text(framework / "conftest.py", errors)
    runtime_context_text = read_optional_text(framework / "core" / "runtime_context.py", errors)
    data_manager_text = read_optional_text(framework / "core" / "data_manager.py", errors)
    auth_manager_text = read_optional_text(framework / "core" / "auth_manager.py", errors)
    client_text = read_optional_text(framework / "core" / "client.py", errors)
    transport_text = read_optional_text(framework / "core" / "transport_crypto.py", errors)
    test_api_text = read_optional_text(framework / "testcases" / "test_api_cases.py", errors)
    flow_runner_text = read_optional_text(flow_runner_path, errors) if flow_runner_path.is_file() else ""

    if "def prepare_case_runtime_context" not in runtime_context_text:
        errors.append("运行韧性门禁：core/runtime_context.py 缺少用例/长链路业务变量作用域初始化")
    if ordinary_case_required:
        if "def case_runtime_scope" not in conftest_text:
            errors.append("运行韧性门禁：conftest.py 缺少 case_runtime_scope fixture")
        if "case_runtime_scope" not in python_function_signature_args(conftest_text, "case_account_login"):
            errors.append("运行韧性门禁：case_account_login 必须在账号组登录前初始化用例运行作用域")

        role_collection = python_function_source(conftest_text, "_collect_case_session_roles")
        if not all(marker in role_collection for marker in ("preconditions", "cleanup")):
            errors.append("运行韧性门禁：多角色扫描必须覆盖业务步骤、API 前置和 API 清理")
        data_manager_fixture = python_function_source(conftest_text, "case_data_manager")
        if not all(marker in data_manager_fixture for marker in ("try:", "finally:", "executor.cleanup")):
            errors.append("运行韧性门禁：case_data_manager 必须在 finally 中执行 API cleanup")
        cleanup_source = python_method_source(data_manager_text, "DataRuleExecutor", "cleanup")
        if not all(marker in cleanup_source for marker in ("cleanup_errors", "for rule in rules", "raise AssertionError")):
            errors.append("运行韧性门禁：API cleanup 必须继续独立规则并汇总清理失败")

        test_signature = python_function_signature_args(test_api_text, "test_api_case")
        for fixture_name in ("case_account_login", "case_data_manager", "case_sql_manager"):
            if fixture_name not in test_signature:
                errors.append(f"运行韧性门禁：test_api_case 缺少 {fixture_name} fixture")
        if not python_function_calls(test_api_text, "_extract_step_values", "publish_runtime_value"):
            errors.append("运行韧性门禁：普通多步骤用例缺少显式、类型保持的运行变量抽取")
        if not python_function_calls(
            test_api_text,
            "_extract_step_values",
            "AuthManager.apply_login_step_context",
        ):
            errors.append("运行韧性门禁：显式登录步骤未复用统一账号组上下文更新器")

    if ordinary_case_required or flow_login_required:
        if "def apply_login_step_context" not in auth_manager_text:
            errors.append("运行韧性门禁：core/auth_manager.py 缺少统一显式登录上下文更新器")
        if 'set_auth_context({"enabled": False})' not in auth_manager_text:
            errors.append("运行韧性门禁：动态登录请求未屏蔽旧业务 token")

    if flow_required:
        if not flow_runner_text:
            errors.append("运行韧性门禁：存在 E2E flow 但缺少 core/flow_runner.py")
        elif not python_function_calls(flow_runner_text, "run_flow", "prepare_case_runtime_context"):
            errors.append("运行韧性门禁：core/flow_runner.py 未在完整 flow 开始前初始化共享作用域")
        if flow_login_required and not python_function_calls(
            flow_runner_text,
            "_extract_step_values",
            "AuthManager.apply_login_step_context",
        ):
            errors.append("运行韧性门禁：core/flow_runner.py 未复用统一显式登录上下文更新器")

    for marker, message in (
        ("def _attach_transport_raw_response", "缺少解密前响应证据"),
        ("def _attach_transport_decode_failure", "缺少解密失败上下文"),
        ("max_attachment_text_chars", "缺少有界附件配置"),
        ("request_envelope_field", "加密 envelope 字段未保持策略驱动"),
    ):
        if marker not in client_text:
            errors.append(f"运行韧性门禁：core/client.py {message}")
    redaction_path = framework / "core" / "security_redaction.py"
    shared_redaction = redaction_path.read_text(encoding="utf-8") if redaction_path.is_file() else ""
    uses_shared_redaction = "from core.security_redaction import redact" in transport_text
    redaction_text = shared_redaction if uses_shared_redaction else transport_text
    if "authorization" not in redaction_text.lower() or not any(name in redaction_text for name in ("SENSITIVE_TEXT_PATTERN", "TEXT_SECRET.sub")):
        errors.append("运行韧性门禁：传输证据脱敏未覆盖 Authorization 和密钥赋值文本")


def validate_setup_cleanup_materialization_ledger(
    framework: Path,
    generation_status_data: dict[str, Any],
    errors: list[str],
) -> None:
    """校验 setup/cleanup ledger，允许 configs、data 或 generation_status 等价记录。"""

    section = generation_status_data.get("setup_cleanup_materialization")
    candidate_paths = (
        framework / "configs" / "setup_cleanup_materialization.yaml",
        framework / "data" / "setup_cleanup_materialization.yaml",
    )
    existing_paths = [path for path in candidate_paths if path.is_file()]
    for path in existing_paths:
        ledger = read_yaml_file(path, errors, str(path.relative_to(framework)))
        if not isinstance(ledger, dict):
            errors.append(f"{path.relative_to(framework)} 顶层必须是 YAML 对象")
            continue
        ledger_status = status_value(ledger)
        if ledger_status and ledger_status != "passed":
            errors.append(f"{path.relative_to(framework)}.status 非法：{ledger_status}，期望 passed")
        has_detail = any(key in ledger for key in ("items", "cases", "case_items", "materialized_case_count"))
        if not has_detail:
            errors.append(f"{path.relative_to(framework)} 缺少 items/cases/materialized_case_count 等可审计明细")
    if existing_paths:
        return

    if not isinstance(section, dict):
        errors.append("setup_cleanup_materialization 缺少可机器验证的 ledger 文件或 generation_status 等价对象")
        return
    has_equivalent_summary = any(
        key in section
        for key in (
            "generated_candidate_case_count",
            "selected_case_count",
            "runnable_case_count",
            "executable_cleanup_case_count",
            "cleanup_evidence_not_materialized",
            "materialization_note",
        )
    )
    if not has_equivalent_summary:
        errors.append("generation_status.yaml.setup_cleanup_materialization 缺少可审计的 setup/cleanup 摘要字段")


RUNTIME_CONTEXT_PATTERN = re.compile(r"\$\{runtime_context\.([A-Za-z_][A-Za-z0-9_]*)\}")
SQL_ALIAS_PATTERN = re.compile(r"\bAS\s+`?([A-Za-z_][A-Za-z0-9_]*)`?", re.I)
SQL_SELECT_PATTERN = re.compile(r"^\s*SELECT\s+(.+?)\s+FROM\s+", re.I | re.S)


def to_snake_case(name: str) -> str:
    first_pass = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", first_pass).lower()


def to_lower_camel_case(name: str) -> str:
    parts = name.split("_")
    if not parts:
        return name
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


def collect_runtime_context_refs(value: Any) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, str):
        refs.update(RUNTIME_CONTEXT_PATTERN.findall(value))
    elif isinstance(value, dict):
        for item in value.values():
            refs.update(collect_runtime_context_refs(item))
    elif isinstance(value, list):
        for item in value:
            refs.update(collect_runtime_context_refs(item))
    return refs


def runtime_variables_available_before_sql_setup(framework: Path) -> set[str]:
    allowed = {
        "nowIso",
        "now_iso",
        "run_marker",
        "runMarker",
        "task_time_marker",
        "taskTimeMarker",
        "task_window_start",
        "taskWindowStart",
        "task_window_end",
        "taskWindowEnd",
        "caseId",
        "current_case_id",
    }
    for config_name in ("dev.yaml", "test.yaml", "prod.yaml"):
        config_path = framework / "configs" / config_name
        if not config_path.is_file():
            continue
        config_data = read_yaml_file(config_path, [], str(config_path.relative_to(framework)))
        if not isinstance(config_data, dict):
            continue
        runtime_variables = config_data.get("runtime_variables") or {}
        if not isinstance(runtime_variables, dict):
            continue
        for variable_name in runtime_variables:
            if not isinstance(variable_name, str):
                continue
            snake_name = to_snake_case(variable_name)
            allowed.add(variable_name)
            allowed.add(snake_name)
            allowed.add(to_lower_camel_case(snake_name))
    return allowed


def select_aliases(sql: Any) -> set[str]:
    if not isinstance(sql, str):
        return set()
    aliases = set(SQL_ALIAS_PATTERN.findall(sql))
    match = SQL_SELECT_PATTERN.search(sql)
    if not match:
        return aliases
    for raw_part in match.group(1).split(","):
        part = raw_part.strip()
        if not part:
            continue
        last_token = part.split()[-1].strip("`")
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", last_token):
            aliases.add(last_token)
    return aliases


def sql_references_field(sql: Any, field_name: str) -> bool:
    if not isinstance(sql, str) or not field_name:
        return False
    escaped_field = re.escape(field_name)
    return bool(
        re.search(rf":{escaped_field}\b", sql)
        or re.search(rf"\b`?{escaped_field}`?\b", sql)
    )


def sql_bind_params(sql: Any) -> set[str]:
    if not isinstance(sql, str):
        return set()
    return set(re.findall(r":([A-Za-z_][A-Za-z0-9_]*)\b", sql))


def command_sql_bind_params(command: dict[str, Any]) -> set[str]:
    bind_params = sql_bind_params(command.get("sql"))
    for query in (command.get("queries") or {}).values():
        bind_params.update(sql_bind_params(query))
    return bind_params


def command_runtime_refs_used_by_sql(command: dict[str, Any]) -> set[str]:
    params = command.get("params") or command.get("params_source") or {}
    if not isinstance(params, dict):
        return set()
    bind_params = command_sql_bind_params(command)
    return collect_runtime_context_refs(
        {param_name: value for param_name, value in params.items() if param_name in bind_params}
    )


def command_unused_runtime_param_names(command: dict[str, Any]) -> set[str]:
    params = command.get("params") or command.get("params_source") or {}
    if not isinstance(params, dict):
        return set()
    bind_params = command_sql_bind_params(command)
    return {
        param_name
        for param_name, value in params.items()
        if param_name not in bind_params and collect_runtime_context_refs(value)
    }


COMMON_NON_UNIQUE_BIND_PARAMS = {
    "user_id",
    "provider_id",
    "target_user_id",
    "blocked_id",
    "reporter_id",
    "reported_id",
    "other_user_id",
    "from_user_id",
    "to_user_id",
    "dialer_id",
    "picker_id",
    "type",
    "source_type",
    "report_type",
    "content_type",
    "status",
    "deleted",
    "enabled",
}


def verification_has_run_unique_boundary(sql: Any) -> bool:
    bind_params = sql_bind_params(sql)
    return bool(bind_params - COMMON_NON_UNIQUE_BIND_PARAMS)


def framework_non_live_case_ids(framework: Path) -> set[str]:
    """读取显式非 live 决策，避免用 live 重复执行门禁误拦人工或隔离场景。"""

    non_live_decisions = {"generated_non_live", "manual_review_only"}
    case_ids: set[str] = set()
    for relative_path, collection_key in (
        ("data/flow_cases.yaml", "flows"),
        ("data/cases/ordinary_api_observable_cases.yaml", "cases"),
    ):
        path = framework / relative_path
        if not path.is_file():
            continue
        payload = read_yaml_file(path, [], relative_path)
        if not isinstance(payload, dict):
            continue
        for item in payload.get(collection_key) or []:
            if not isinstance(item, dict) or item.get("automation_decision") not in non_live_decisions:
                continue
            case_id = item.get("case_id")
            if isinstance(case_id, str) and case_id:
                case_ids.add(case_id)
    return case_ids


def validate_sql_fixture_deep_static_gate(framework: Path, errors: list[str]) -> None:
    """校验 SQL fixture 内部生命周期、断言字段和表结构约束，防止生成后才运行失败。"""

    command_path = framework / "data" / "case_sql_commands.yaml"
    if not command_path.is_file():
        return
    sql_commands = read_yaml_file(command_path, errors, "data/case_sql_commands.yaml")
    if not isinstance(sql_commands, dict):
        return
    cases = sql_commands.get("cases") or {}
    if not isinstance(cases, dict):
        return
    initial_setup_refs = runtime_variables_available_before_sql_setup(framework)
    non_live_case_ids = framework_non_live_case_ids(framework)
    for case_id, case_commands in cases.items():
        if not isinstance(case_commands, dict):
            continue
        if case_id in non_live_case_ids:
            continue
        allowed_setup_refs = set(initial_setup_refs)
        setup_refs = collect_runtime_context_refs(case_commands.get("params") or {})
        invalid_setup_refs = sorted(ref for ref in setup_refs if ref not in allowed_setup_refs)
        if invalid_setup_refs:
            errors.append(
                "data/case_sql_commands.yaml "
                f"{case_id} 的顶层 params 引用了 SQL setup 前尚未产生的 runtime_context 变量：{invalid_setup_refs}"
            )
        for command in case_commands.get("setup") or []:
            if not isinstance(command, dict):
                continue
            command_id = command.get("command_id") or command.get("query_id") or "未命名命令"
            command_refs = collect_runtime_context_refs(command.get("params") or {})
            invalid_command_refs = sorted(ref for ref in command_refs if ref not in allowed_setup_refs)
            if invalid_command_refs:
                errors.append(
                    "data/case_sql_commands.yaml "
                    f"{case_id}/{command_id} 的 setup.params 引用了该命令执行前尚未产生的 runtime_context 变量：{invalid_command_refs}"
                )
            for variable_name in command.get("extract_to_runtime_context") or []:
                if isinstance(variable_name, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", variable_name):
                    allowed_setup_refs.add(variable_name)
            for variable_name in (command.get("queries") or {}):
                if isinstance(variable_name, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", variable_name):
                    allowed_setup_refs.add(variable_name)
            setup_identity_ref = (command.get("setup_identity") or {}).get("value_ref")
            if isinstance(setup_identity_ref, str) and setup_identity_ref.startswith("runtime_context."):
                variable_name = setup_identity_ref.split(".", 1)[1]
                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", variable_name):
                    allowed_setup_refs.add(variable_name)
        runtime_extract_commands = {
            str(command.get("command_id") or command.get("query_id")): command
            for command in case_commands.get("runtime_extract") or []
            if isinstance(command, dict) and (command.get("command_id") or command.get("query_id"))
        }
        cleanup_commands = {
            str(command.get("command_id") or command.get("query_id")): command
            for command in case_commands.get("cleanup") or []
            if isinstance(command, dict) and (command.get("command_id") or command.get("query_id"))
        }
        final_verify_commands = {
            str(command.get("command_id") or command.get("query_id")): command
            for command in case_commands.get("final_verify") or []
            if isinstance(command, dict) and (command.get("command_id") or command.get("query_id"))
        }
        primary_late_vars: set[str] = set()
        for stage_key in ("runtime_extract", "cleanup", "final_verify"):
            for command in case_commands.get(stage_key) or []:
                if not isinstance(command, dict):
                    continue
                command_id = command.get("command_id") or command.get("query_id") or "未命名命令"
                unused_runtime_params = sorted(command_unused_runtime_param_names(command))
                if unused_runtime_params:
                    errors.append(
                        "data/case_sql_commands.yaml "
                        f"{case_id}/{command_id} 的参数包含 SQL 未使用的运行变量：{unused_runtime_params}"
                    )
                if stage_key != "cleanup":
                    continue
                late_refs = command_runtime_refs_used_by_sql(command) - allowed_setup_refs
                if not late_refs:
                    continue
                side_effect_class = command.get("side_effect_class")
                skip_vars = command.get("skip_if_missing_runtime_vars") or []
                if isinstance(skip_vars, str):
                    skip_vars = [skip_vars]
                if not isinstance(skip_vars, list):
                    errors.append(
                        "data/case_sql_commands.yaml "
                        f"{case_id}/{command_id} 的 skip_if_missing_runtime_vars 必须是列表"
                    )
                    skip_vars = []
                uncovered_late_refs = sorted(late_refs - set(skip_vars))
                if uncovered_late_refs:
                    errors.append(
                        "data/case_sql_commands.yaml "
                        f"{case_id}/{command_id} 清理依赖请求后变量但未声明缺失策略：{uncovered_late_refs}"
                    )
                if side_effect_class not in {"primary", "conditional", "prestate_restore"}:
                    errors.append(
                        "data/case_sql_commands.yaml "
                        f"{case_id}/{command_id} 清理依赖请求后变量时必须声明 side_effect_class"
                    )
                if side_effect_class == "prestate_restore":
                    errors.append(
                        "data/case_sql_commands.yaml "
                        f"{case_id}/{command_id} prestate_restore 不得依赖请求后变量：{sorted(late_refs)}"
                    )
                if side_effect_class == "primary":
                    primary_late_vars.update(late_refs)
                if side_effect_class == "conditional" and not final_verify_commands:
                    errors.append(
                        "data/case_sql_commands.yaml "
                        f"{case_id}/{command_id} 可选副作用跳过清理时缺少 scoped final_verify"
                    )

        if primary_late_vars:
            failure_contract = case_commands.get("failure_path_cleanup") or {}
            ownership_vars = failure_contract.get("request_ownership_vars") or []
            fallback_ids = failure_contract.get("fallback_runtime_extract_command_ids") or []
            restore_ids = failure_contract.get("always_run_restore_command_ids") or []
            final_verify_ids = failure_contract.get("final_verify_command_ids") or []
            if failure_contract.get("transport_outcome") != "ambiguous":
                errors.append(
                    "data/case_sql_commands.yaml "
                    f"{case_id} 主对象清理依赖请求后变量，但未声明 ambiguous failure_path_cleanup"
                )
            if not isinstance(ownership_vars, list) or not ownership_vars:
                errors.append(f"data/case_sql_commands.yaml {case_id} 缺少请求侧唯一归属变量")
                ownership_vars = []
            unknown_ownership_vars = sorted(set(ownership_vars) - allowed_setup_refs)
            if unknown_ownership_vars:
                errors.append(
                    "data/case_sql_commands.yaml "
                    f"{case_id} failure_path_cleanup 使用了响应前不可用的归属变量：{unknown_ownership_vars}"
                )
            missing_fallback_ids = sorted(set(fallback_ids) - set(runtime_extract_commands))
            missing_restore_ids = sorted(set(restore_ids) - set(cleanup_commands))
            missing_final_verify_ids = sorted(set(final_verify_ids) - set(final_verify_commands))
            if not fallback_ids or missing_fallback_ids:
                errors.append(
                    "data/case_sql_commands.yaml "
                    f"{case_id} 缺少有效的 failure-path fallback runtime_extract：{missing_fallback_ids}"
                )
            if missing_restore_ids:
                errors.append(
                    "data/case_sql_commands.yaml "
                    f"{case_id} 引用了不存在的 always-run restore：{missing_restore_ids}"
                )
            if not final_verify_ids or missing_final_verify_ids:
                errors.append(
                    "data/case_sql_commands.yaml "
                    f"{case_id} 缺少有效的 failure-path final_verify：{missing_final_verify_ids}"
                )
            fallback_outputs = {
                str(output_name)
                for command_id in fallback_ids
                for output_name in (
                    (runtime_extract_commands.get(command_id) or {}).get("queries") or {}
                )
            }
            missing_fallback_outputs = sorted(primary_late_vars - fallback_outputs)
            if missing_fallback_outputs:
                errors.append(
                    "data/case_sql_commands.yaml "
                    f"{case_id} fallback runtime_extract 未生产主对象清理变量：{missing_fallback_outputs}"
                )
            for command_id in fallback_ids:
                fallback_command = runtime_extract_commands.get(command_id) or {}
                unsafe_fallback_refs = sorted(
                    command_runtime_refs_used_by_sql(fallback_command) & primary_late_vars
                )
                if unsafe_fallback_refs:
                    errors.append(
                        "data/case_sql_commands.yaml "
                        f"{case_id}/{command_id} 兜底抽取仍依赖缺失响应变量：{unsafe_fallback_refs}"
                    )
            for command_id in restore_ids:
                restore_command = cleanup_commands.get(command_id) or {}
                if restore_command.get("side_effect_class") != "prestate_restore":
                    errors.append(
                        "data/case_sql_commands.yaml "
                        f"{case_id}/{command_id} always-run restore 必须声明 prestate_restore"
                    )
        for stage_key in ("setup", "cleanup", "final_verify"):
            for command in case_commands.get(stage_key) or []:
                if not isinstance(command, dict):
                    continue
                command_id = command.get("command_id") or command.get("query_id") or "未命名命令"
                expected_effect = command.get("expected_effect") or {}
                if not isinstance(expected_effect, dict):
                    continue
                for key in expected_effect:
                    if key.endswith("verification_query") and key != "verification_query":
                        errors.append(
                            "data/case_sql_commands.yaml "
                            f"{case_id}/{command_id} 使用了执行器不支持的 {key}；应拆成 final_verify 独立查询或扩展执行器"
                        )
                verification_query = expected_effect.get("verification_query")
                aliases = select_aliases(verification_query)
                for key in expected_effect:
                    if not key.startswith("expected_") or key in {"expected_count", "expected_row_count"}:
                        continue
                    field_name = key[len("expected_"):]
                    if aliases and field_name not in aliases:
                        errors.append(
                            "data/case_sql_commands.yaml "
                            f"{case_id}/{command_id} 断言字段 {field_name} 不在 verification_query 返回字段 {sorted(aliases)} 中"
                        )
                cleanup_identity = command.get("cleanup_identity") or {}
                cleanup_field = cleanup_identity.get("field")
                if (
                    stage_key == "cleanup"
                    and cleanup_field
                    and verification_query
                    and re.search(r"\bDELETE\b", str(command.get("sql") or ""), re.I)
                    and not sql_references_field(verification_query, str(cleanup_field))
                    and not verification_has_run_unique_boundary(verification_query)
                    and any(key.startswith("expected_") for key in expected_effect)
                ):
                    errors.append(
                        "data/case_sql_commands.yaml "
                        f"{case_id}/{command_id} cleanup 按 {cleanup_field} 清理，但 verification_query 未包含同一归属键，"
                        "需证明 pair/entity 级前置隔离或改为验证本次运行归属键"
                    )
        for command in case_commands.get("setup") or []:
            if not isinstance(command, dict):
                continue
            params = command.get("params") or {}
            sql_text = str(command.get("sql") or "")
            command_id = command.get("command_id") or command.get("query_id") or "未命名命令"
            if (
                isinstance(params, dict)
                and params.get("task_type") == "${runtime_context.task_time_marker}"
                and "subscription_server_task" in sql_text
            ):
                errors.append(
                    "data/case_sql_commands.yaml "
                    f"{case_id}/{command_id} 将 task_type 绑定到 task_time_marker；该标记可能超过表字段长度，"
                    "应使用字段长度内的短业务 marker 或由表结构约束生成"
                )


def framework_has_post_request_cleanup_dependencies(framework: Path) -> bool:
    command_path = framework / "data" / "case_sql_commands.yaml"
    if not command_path.is_file():
        return False
    sql_commands = read_yaml_file(command_path, [], "data/case_sql_commands.yaml")
    if not isinstance(sql_commands, dict):
        return False
    initial_refs = runtime_variables_available_before_sql_setup(framework)
    non_live_case_ids = framework_non_live_case_ids(framework)
    for case_id, case_commands in (sql_commands.get("cases") or {}).items():
        if not isinstance(case_commands, dict):
            continue
        if case_id in non_live_case_ids:
            continue
        available_before_request = set(initial_refs)
        for setup_command in case_commands.get("setup") or []:
            if not isinstance(setup_command, dict):
                continue
            available_before_request.update(setup_command.get("extract_to_runtime_context") or [])
            available_before_request.update((setup_command.get("queries") or {}).keys())
        for cleanup_command in case_commands.get("cleanup") or []:
            if not isinstance(cleanup_command, dict):
                continue
            if command_runtime_refs_used_by_sql(cleanup_command) - available_before_request:
                return True
    return False


def auth_bootstrap_section(generation_status_data: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    paths = (
        ("runtime_usability", "auth_bootstrap_materialization"),
        ("runtime_evidence_script_materialization", "auth_bootstrap_materialization"),
        ("script_auth_bootstrap_materialization",),
    )
    for path in paths:
        section = dict_path(generation_status_data, path)
        if isinstance(section, dict):
            return section, ".".join(path)
    return None, ""


def framework_uses_dynamic_auth(framework: Path, generation_status_data: dict[str, Any]) -> bool:
    if auth_bootstrap_section(generation_status_data)[0] is not None:
        return True
    conftest_path = framework / "conftest.py"
    if conftest_path.is_file():
        try:
            conftest_text = read_text(conftest_path)
        except ValueError:
            conftest_text = ""
        if "case_account_login" in conftest_text:
            return True
    for config_name in ("dev.yaml", "test.yaml", "prod.yaml"):
        config_path = framework / "configs" / config_name
        if not config_path.is_file():
            continue
        try:
            config_text = read_text(config_path)
        except ValueError:
            continue
        if "token_request" in config_text or "thirdLogin" in config_text:
            return True
    return False


def validate_auth_bootstrap_materialization(
    framework: Path,
    generation_status_data: dict[str, Any],
    errors: list[str],
) -> None:
    """校验动态鉴权脚本的账号组登录物化证据。"""

    if not framework_uses_dynamic_auth(framework, generation_status_data):
        return
    section, section_path = auth_bootstrap_section(generation_status_data)
    if section is None:
        errors.append("动态鉴权脚本缺少 auth_bootstrap_materialization 或等价 section")
        return
    section_status = status_value(section)
    if section_status != "passed":
        errors.append(f"generation_status.yaml {section_path}.status 非法：{section_status}，期望 passed")

    if section.get("per_case_requester_created") is True:
        errors.append(f"generation_status.yaml {section_path}.per_case_requester_created 必须为 false")

    fixture_or_registry = (
        section.get("ordinary_fixture_or_registry")
        or section.get("ordinary_fixture")
        or section.get("ordinary_case_policy")
    )
    if not str(fixture_or_registry or "").strip():
        errors.append(f"generation_status.yaml {section_path} 缺少普通用例账号组 fixture/registry 说明")

    conftest_path = framework / "conftest.py"
    test_api_path = framework / "testcases" / "test_api_cases.py"
    auth_manager_path = framework / "core" / "auth_manager.py"
    conftest_text = read_optional_text(conftest_path, errors)
    test_api_text = read_optional_text(test_api_path, errors)
    auth_manager_text = read_optional_text(auth_manager_path, errors)

    if "case_account_login" in str(fixture_or_registry):
        if "def case_account_login" not in conftest_text:
            errors.append("generation_status.yaml 声明 case_account_login，但 conftest.py 未定义该 fixture")
        if "case_account_login" not in test_api_text:
            errors.append("testcases/test_api_cases.py 未接入 case_account_login fixture")
        if "def case_data_manager" in conftest_text and "case_account_login" not in python_function_signature_args(conftest_text, "case_data_manager"):
            errors.append("case_data_manager fixture 未声明 case_account_login，无法保证登录早于 API setup")
        if "def case_sql_manager" in conftest_text and "case_account_login" not in python_function_signature_args(conftest_text, "case_sql_manager"):
            errors.append("case_sql_manager fixture 未声明 case_account_login，无法保证登录早于 SQL setup")

    pre_login_blocked = section.get("pre_login_token_injection_blocked")
    if pre_login_blocked is not None and not bool_value(pre_login_blocked):
        errors.append(f"generation_status.yaml {section_path}.pre_login_token_injection_blocked 必须为 true")
    elif pre_login_blocked is None and 'set_auth_context({"enabled": False})' not in auth_manager_text:
        errors.append("动态登录请求缺少旧业务 token 屏蔽证据：core/auth_manager.py 未禁用 pre-login auth context")

    validate_account_specific_flow_login_steps(framework, errors)


def validate_account_specific_flow_login_steps(framework: Path, errors: list[str]) -> None:
    flow_path = framework / "data" / "flow_cases.yaml"
    if not flow_path.is_file():
        return
    flow_data = read_yaml_file(flow_path, errors, "data/flow_cases.yaml")
    if not isinstance(flow_data, dict):
        return
    flows = flow_data.get("flows")
    if not isinstance(flows, list):
        return
    for flow in flows:
        if not isinstance(flow, dict):
            continue
        account_specific = any(
            key in flow and str(flow.get(key)).strip().lower() not in ACCOUNT_NOT_REQUIRED_VALUES
            for key in ACCOUNT_SPECIFIC_MARKER_KEYS
        )
        if not account_specific:
            continue
        flow_id = str(flow.get("flow_id") or "未命名 flow")
        steps = flow.get("steps")
        if not isinstance(steps, list) or not steps:
            errors.append(f"账号特定 flow 缺少步骤：{flow_id}")
            continue
        first_step = steps[0]
        if not isinstance(first_step, dict):
            errors.append(f"账号特定 flow 首步骤结构非法：{flow_id}")
            continue
        step_type = str(first_step.get("step_type") or "").strip().lower()
        if step_type not in LOGIN_STEP_TYPE_VALUES and not first_step.get("login_entry"):
            errors.append(f"账号特定 flow 首步骤不是 login/auth：{flow_id}")
        extract = first_step.get("extract")
        if not isinstance(extract, dict) or "token" not in extract:
            errors.append(f"账号特定 flow 首步骤缺少 token 抽取：{flow_id}")
        account_context = first_step.get("account_context")
        if not isinstance(account_context, dict) or not account_context.get("role"):
            errors.append(f"账号特定 flow 首步骤缺少 account_context.role：{flow_id}")


def validate_framework_quality_gates(framework: Path, generation_status_text: str, errors: list[str]) -> None:
    """校验 framework 阶段从软说明迁出的关键可运行门禁。"""

    try:
        generation_status_data = yaml.safe_load(generation_status_text) or {}
    except yaml.YAMLError as exc:
        errors.append(f"generation_status.yaml YAML 解析失败：{exc}")
        generation_status_data = {}
    if not isinstance(generation_status_data, dict):
        errors.append("generation_status.yaml 顶层必须是 YAML 对象")
        generation_status_data = {}

    def require_section_status(section_name: str, allowed: set[str], required: bool = True) -> str:
        section = yaml_section(generation_status_text, section_name)
        if not section:
            if required:
                errors.append(f"generation_status.yaml 缺少 {section_name} 明细")
            return ""
        values = yaml_scalar_values(section, "status")
        if not values:
            errors.append(f"generation_status.yaml {section_name}.status 缺失")
            return ""
        status = values[0]
        if status not in allowed:
            errors.append(
                f"generation_status.yaml {section_name}.status 非法：{status}，期望 {sorted(allowed)}"
            )
        return status

    closure_section = yaml_section(generation_status_text, "execution_fact_closure")
    if not closure_section:
        has_equivalent_closure = all(
            marker in generation_status_text
            for marker in (
                "request_input_closure",
                "business_state_closure",
                "session_closure",
            )
        )
        if not has_equivalent_closure:
            errors.append(
                "generation_status.yaml 缺少 execution_fact_closure，且未找到 request/business/session 三类等价闭合证据"
            )
    else:
        require_section_status("execution_fact_closure", {"passed"})
        for key in (
            "unresolved_main_flow_business_fields",
            "stateful_cases_without_setup_cleanup",
            "pre_login_steps_with_token_injection",
            "unresolved_auth_placeholders",
            "cross_role_identity_mismatches",
        ):
            values = yaml_scalar_values(closure_section, key)
            if values and values[0] not in {"0", "[]"}:
                errors.append(f"generation_status.yaml execution_fact_closure.{key} 未清零：{values[0]}")

    require_section_status("assertion_strength_gate", {"passed"})
    require_section_status("case_confidence_gate", {"passed"})
    validate_framework_case_confidence(framework, generation_status_data, errors)
    validate_optional_transfer_release(framework, generation_status_data, errors)
    require_section_status("business_readable_input_quality", {"passed"})
    require_section_status("business_result_observability", {"passed"})
    require_section_status("setup_cleanup_materialization", {"passed"})
    validate_setup_cleanup_materialization_ledger(framework, generation_status_data, errors)
    validate_sql_fixture_deep_static_gate(framework, errors)
    if framework_has_post_request_cleanup_dependencies(framework):
        require_section_status("failure_path_cleanup_resilience", {"passed"})
        failure_path_section = generation_status_data.get("failure_path_cleanup_resilience") or {}
        for field_name in (
            "missing_fallback_case_ids",
            "unsafe_skip_primary_cleanup_case_ids",
            "restore_with_late_variable_case_ids",
        ):
            field_value = failure_path_section.get(field_name)
            if field_value not in ([], None):
                errors.append(
                    f"generation_status.yaml failure_path_cleanup_resilience.{field_name} 未清空：{field_value}"
                )
    validate_auth_bootstrap_materialization(framework, generation_status_data, errors)
    executable_counts = yaml_int_values(generation_status_text, "executable_case_count")
    flow_counts = yaml_int_values(generation_status_text, "e2e_flow_case_count")
    ordinary_case_required = any(count > 0 for count in executable_counts)
    flow_required = any(count > 0 for count in flow_counts)
    validate_framework_runtime_resilience(
        framework,
        errors,
        ordinary_case_required=ordinary_case_required,
        flow_required=flow_required,
        flow_login_required=framework_flow_has_login_step(framework, errors) if flow_required else False,
    )

    archive_status = require_section_status("final_case_archive", {"passed"})
    archive_path = framework / "接口案例.md"
    require(archive_path.is_file(), errors, "api-test-framework 缺少最终案例台账：接口案例.md")
    if archive_path.is_file():
        try:
            read_text(archive_path)
        except ValueError as exc:
            errors.append(str(exc))

    runtime_evidence_used = (
        "live_request_evidence" in generation_status_text
        or "runtime_evidence" in generation_status_text
        or (framework / "configs" / "runtime_evidence_script_mapping_audit.yaml").is_file()
    )
    if runtime_evidence_used:
        require_section_status("runtime_evidence_script_materialization", {"passed"})
        audit_path = framework / "configs" / "runtime_evidence_script_mapping_audit.yaml"
        require(
            audit_path.is_file(),
            errors,
            "使用 runtime evidence 生成脚本时缺少 configs/runtime_evidence_script_mapping_audit.yaml",
        )
        if audit_path.is_file():
            try:
                read_text(audit_path)
            except ValueError as exc:
                errors.append(str(exc))

    defect_path = framework / "缺陷列表.md"
    if defect_path.exists():
        require(defect_path.is_file(), errors, "api-test-framework/缺陷列表.md 不是 Markdown 文件")
        if defect_path.is_file():
            try:
                defect_text = read_text(defect_path)
            except ValueError as exc:
                errors.append(str(exc))
            else:
                require("#" in defect_text, errors, "缺陷列表.md 必须是 Markdown 并包含章节标题")

def validate_framework_case_denominator_conservation(root: Path, framework: Path, errors: list[str]) -> None:
    """复用生成器的集合守恒校验，不复制 pytest 收集或归档门禁。"""

    if not CASE_DENOMINATOR_VALIDATOR.is_file():
        errors.append(f"缺少用例分母守恒校验器：{CASE_DENOMINATOR_VALIDATOR}")
        return
    try:
        spec = importlib.util.spec_from_file_location(
            "api_framework_case_denominator_conservation",
            CASE_DENOMINATOR_VALIDATOR,
        )
        if spec is None or spec.loader is None:
            raise ImportError("无法创建校验器模块规格")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        local_errors = module.validate_case_denominator_conservation(
            framework,
            executable_case_set=root / "05-executable-interface-case-set" / "执行级接口用例集.md",
            required_chain_flows=root / REQUIRED_CHAIN_FLOWS,
        )
    except Exception as exc:  # noqa: BLE001 - 总校验必须把插件装载失败转成明确门禁错误。
        errors.append(f"用例分母守恒校验器执行失败：{exc}")
        return
    errors.extend(f"用例分母守恒：{error}" for error in local_errors)


def validate_framework(root: Path, errors: list[str]) -> None:
    framework = root / "api-test-framework"
    if not framework.exists():
        return
    require(framework.is_dir(), errors, f"api-test-framework 不是目录：{framework}")
    if not framework.is_dir():
        return
    for name in FRAMEWORK_REQUIRED:
        path = framework / name
        require(path.exists(), errors, f"api-test-framework 缺少骨架项：{name}")
    configs = framework / "configs"
    for name in FRAMEWORK_CONFIG_REQUIRED:
        path = configs / name
        require(path.is_file(), errors, f"api-test-framework 缺少配置文件：configs/{name}")
        if path.is_file():
            try:
                read_text(path)
            except ValueError as exc:
                errors.append(str(exc))
    generation_status = configs / "generation_status.yaml"
    required_flow_ids = required_chain_flow_ids_from_root(root, errors)
    long_chain_required = long_chain_required_from_root(root, errors)
    validate_required_flow_framework_files(framework, required_flow_ids, long_chain_required, errors)
    if generation_status.is_file():
        try:
            text = read_text(generation_status)
        except ValueError as exc:
            errors.append(str(exc))
            return
        validate_generation_status(text, errors, required_flow_ids, long_chain_required)
        validate_framework_quality_gates(framework, text, errors)
        validate_data_driven_framework_files(framework, text, errors)
        validate_framework_case_denominator_conservation(root, framework, errors)
        validate_pytest_nodeid_targets(framework, text, errors, required_flow_ids)


def validate_executable_traceability(executable_dir: Path, errors: list[str]) -> None:
    case_file = executable_dir / "执行级接口用例集.md"
    if not case_file.is_file():
        return
    try:
        text = read_text(case_file)
    except ValueError as exc:
        errors.append(str(exc))
        return
    records = extract_table_case_records(text) + extract_block_case_records(text)
    if not records:
        errors.append("执行级接口用例集.md 缺少可机器识别的逐条执行级用例追溯记录")
        return
    for index, record in enumerate(records, start=1):
        case_id = record.get("用例ID") or f"第 {index} 条执行级用例"
        for field in EXECUTABLE_TRACE_FIELDS:
            if invalid_trace_value(record.get(field)):
                errors.append(f"执行级接口用例集.md {case_id} 缺少有效覆盖继承字段：{field}")


def validate_output_root(root: Path) -> list[str]:
    errors: list[str] = []
    require(root.exists(), errors, f"输出目录不存在：{root}")
    require(root.is_dir(), errors, f"输出路径不是目录：{root}")
    if errors:
        return errors

    report_path = root / "00_流水线执行报告.md"
    require(report_path.is_file(), errors, "缺少 00_流水线执行报告.md")
    report_text = ""
    if report_path.is_file():
        try:
            report_text = read_text(report_path)
        except ValueError as exc:
            errors.append(str(exc))

    stage_status = None
    target_depth = None
    if report_text:
        target_depth = line_value(report_text, "目标阶段") or line_value(report_text, "目标深度")
        require(target_depth in TARGET_DEPTHS, errors, f"目标阶段非法或缺失：{target_depth}")
        stage_status = line_value(report_text, "流水线状态") or line_value(report_text, "阶段状态")
        require(stage_status in STAGE_STATUSES, errors, f"流水线状态非法或缺失：{stage_status}")

    validate_retry_history(root, errors, stage_status)
    validate_database_mcp_alignment(root, errors)
    validate_runtime_evidence_plan(root, errors)
    runtime_evidence_dir = root / RUNTIME_EVIDENCE_DIR
    if runtime_evidence_dir.exists():
        validate_runtime_evidence(root, errors, required=False, require_usable=False)

    case_file = root / "03-interface-testcase-generation" / "04_接口测试用例清单.md"
    case_yaml_file = root / "03-interface-testcase-generation" / "case_list.yaml"
    coverage_point_file = root / "03-interface-testcase-generation" / COVERAGE_POINT_REPORT
    business_long_chain_file = root / "03-interface-testcase-generation" / BUSINESS_LONG_CHAIN_CASES
    business_long_chain_doc_file = root / "03-interface-testcase-generation" / BUSINESS_LONG_CHAIN_DOC
    handoff_dir = root / "04-design-case-handoff"
    handoff_coverage_point_file = handoff_dir / COVERAGE_POINT_REPORT
    handoff_business_map_file = handoff_dir / BUSINESS_SCENARIO_MAP
    handoff_business_doc_file = handoff_dir / BUSINESS_SCENARIO_DOC
    handoff_business_long_chain_file = handoff_dir / BUSINESS_LONG_CHAIN_CASES
    handoff_business_long_chain_doc_file = handoff_dir / BUSINESS_LONG_CHAIN_DOC
    executable_dir = root / "05-executable-interface-case-set"
    framework_dir = root / "api-test-framework"
    doc_entry = root / "01-pre-doc-analysis"
    source_entry = root / "02-source-api-facts" / "docs" / "source-facts"
    doc_business_map_file = doc_entry / BUSINESS_SCENARIO_MAP
    doc_business_doc_file = doc_entry / BUSINESS_SCENARIO_DOC
    source_business_map_file = source_entry / BUSINESS_SCENARIO_MAP
    source_business_doc_file = source_entry / BUSINESS_SCENARIO_DOC
    selected_business_map_file = doc_business_map_file if doc_entry.exists() else source_business_map_file
    selected_business_doc_file = doc_business_doc_file if doc_entry.exists() else source_business_doc_file
    has_entry_output = doc_entry.exists() or source_entry.exists()
    downstream_started = case_file.exists() or handoff_dir.exists() or executable_dir.exists() or framework_dir.exists()
    selected_required_flow_ids: set[str] = set()

    validate_runtime_execution_config_blocker_artifacts(root, report_text, stage_status, target_depth, errors)
    validate_source_data_model_mcp_attempt(root, report_text, stage_status, target_depth, source_entry, doc_entry, errors)

    entry_required = True
    if stage_status == "BLOCKED_MISSING_ENTRY_INPUT":
        entry_required = downstream_started
        require(not downstream_started, errors, "入口缺失阻塞时不应生成后续阶段产物")
    elif stage_status == "FAILED_ENTRY_QUALITY_GATE":
        entry_required = has_entry_output
        require(not downstream_started, errors, "入口质检或测试点拆分失败时不应生成后续阶段产物")
    elif stage_status == "BLOCKED_NEED_BUSINESS_SCENARIO_MAPPING":
        entry_required = has_entry_output
        require(not downstream_started, errors, "业务场景映射阻塞时不应生成后续阶段产物")
    elif stage_status == "BLOCKED_NEED_CHAIN_FLOW_DENOMINATOR":
        entry_required = has_entry_output
        require(not downstream_started, errors, "长链路闭环分母阻塞时不应生成阶段2或后续产物")
    elif stage_status == "BLOCKED_NEED_EXECUTION_INPUT" and not has_entry_output and not downstream_started:
        entry_required = False

    retry_exhausted = stage_status == "BLOCKED_RETRY_EXHAUSTED"
    require_entry_release = stage_status == "PASSED" or (downstream_started and not retry_exhausted)
    validate_entry_outputs(
        root,
        errors,
        required=entry_required,
        require_release=require_entry_release,
        allow_partial_entry=stage_status == "FAILED_ENTRY_QUALITY_GATE",
    )
    if require_entry_release and not retry_exhausted:
        validate_entry_alignment(root, errors)
        selected_candidate_flow_ids = validate_business_scenario_map_file(
            selected_business_map_file,
            errors,
            require_passed=True,
            label="选定入口 business_scenario_map.yaml",
        )
        validate_business_scenario_doc_file(selected_business_doc_file, errors, require_records=True)
        selected_required_flow_ids = validate_chain_flow_denominator(
            root,
            errors,
            require_passed=True,
            require_alignment=doc_entry.exists() and source_entry.exists(),
            expected_candidate_flow_ids=selected_candidate_flow_ids,
        )
    elif stage_status == "BLOCKED_NEED_CHAIN_FLOW_DENOMINATOR":
        selected_required_flow_ids = validate_chain_flow_denominator(
            root,
            errors,
            require_passed=False,
            require_alignment=doc_entry.exists() and source_entry.exists(),
        )

    validate_chain_execution_readiness_reconciliation(
        root,
        target_depth,
        selected_required_flow_ids,
        errors,
    )

    if case_file.exists() or case_yaml_file.exists() or coverage_point_file.exists() or business_long_chain_file.exists():
        require_interface_release = (
            stage_status
            in {
                "PASSED",
                "BLOCKED_NEED_HANDOFF_REPAIR",
                "BLOCKED_NEED_EXECUTION_INPUT",
                "FAILED_EXECUTION_READINESS",
                "FAILED_SCRIPT_GENERATION_GATE",
            }
            or (handoff_dir.exists() and not retry_exhausted)
            or (executable_dir.exists() and not retry_exhausted)
            or (framework_dir.exists() and not retry_exhausted)
        )
        validate_case_list_yaml_file(case_yaml_file, errors, require_passed=require_interface_release)
        validate_business_scenario_map_file(selected_business_map_file, errors, require_passed=require_interface_release, label="选定入口 business_scenario_map.yaml")
        validate_business_scenario_doc_file(selected_business_doc_file, errors, require_records=require_interface_release)
        coverage_report_required = stage_status == "PASSED"
        validate_coverage_point_report_file(coverage_point_file, errors, require_records=coverage_report_required)
        validate_business_long_chain_cases_file(business_long_chain_file, errors, require_passed=require_interface_release)
        validate_business_long_chain_doc_file(business_long_chain_doc_file, errors, require_records=require_interface_release)
        if coverage_point_file.is_file():
            validate_coverage_point_case_mapping(case_yaml_file, coverage_point_file, errors, require_interface_release)
        validate_stage_sidecars(
            (case_file.parent if case_file.exists() else case_yaml_file.parent),
            errors,
            "设计级用例生成",
            "interface_testcase_generation",
            INTERFACE_COVERAGE_PAIRS,
            INTERFACE_MISSING_LISTS,
            require_passed=require_interface_release,
        )
        stage2_coverage_matrix = (case_file.parent if case_file.exists() else case_yaml_file.parent) / "coverage_matrix.yaml"
        if require_interface_release and selected_required_flow_ids and stage2_coverage_matrix.is_file():
            try:
                validate_required_chain_independent_coverage(
                    read_text(stage2_coverage_matrix),
                    errors,
                    "设计级用例生成/coverage_matrix.yaml",
                    selected_required_flow_ids,
                    "generated_design_chain_case_count",
                    require_item_mappings=True,
                )
            except ValueError as exc:
                errors.append(str(exc))
        if stage_status == "FAILED_DESIGN_CASE_GATE":
            stage_sidecar = case_file.parent / "stage_status.yaml"
            if stage_sidecar.is_file():
                try:
                    sidecar_status = first_yaml_scalar(read_text(stage_sidecar), "status")
                except ValueError as exc:
                    errors.append(str(exc))
                else:
                    if sidecar_status == "passed":
                        errors.append("设计级用例生成失败时 stage_status.yaml 不应标记为 passed")

    if stage_status == "PASSED":
        require(case_file.is_file(), errors, "流水线 PASSED 时必须存在 03-interface-testcase-generation/04_接口测试用例清单.md")
        require(case_yaml_file.is_file(), errors, "流水线 PASSED 时必须存在 03-interface-testcase-generation/case_list.yaml")
        require(coverage_point_file.is_file(), errors, "流水线 PASSED 时必须存在 03-interface-testcase-generation/测试覆盖点报告.md")
        require(business_long_chain_file.is_file(), errors, "流水线 PASSED 时必须存在 03-interface-testcase-generation/business_long_chain_cases.yaml")
        require(business_long_chain_doc_file.is_file(), errors, "流水线 PASSED 时必须存在 03-interface-testcase-generation/业务长链路设计清单.md")
        if target_depth in ("executable", "framework"):
            require(executable_dir.is_dir(), errors, f"目标阶段为 {target_depth} 时必须存在执行级用例目录：{executable_dir}")
        if target_depth == "framework":
            require(framework_dir.is_dir(), errors, f"目标阶段为 framework 时必须存在 api-test-framework 目录：{framework_dir}")

    if (case_file.exists() and stage_status == "PASSED") or (not retry_exhausted and (handoff_dir.exists() or executable_dir.exists() or framework_dir.exists())):
        require(case_file.is_file(), errors, "进入交接或后续阶段前必须存在 03-interface-testcase-generation/04_接口测试用例清单.md")
        require(case_yaml_file.is_file(), errors, "进入交接或后续阶段前必须存在 03-interface-testcase-generation/case_list.yaml")
        validate_business_scenario_map_file(selected_business_map_file, errors, require_passed=True, label="选定入口 business_scenario_map.yaml")
        validate_business_scenario_doc_file(selected_business_doc_file, errors, require_records=True)
        if case_yaml_file.is_file():
            validate_case_list_yaml_file(case_yaml_file, errors, require_passed=True)
        if coverage_point_file.is_file():
            validate_coverage_point_report_file(coverage_point_file, errors, require_records=True)
            validate_coverage_point_case_mapping(case_yaml_file, coverage_point_file, errors, require_passed=True)
        validate_business_long_chain_cases_file(business_long_chain_file, errors, require_passed=True)
        validate_business_long_chain_doc_file(business_long_chain_doc_file, errors, require_records=True)
        if case_file.is_file():
            try:
                case_text = read_text(case_file)
                validate_coverage_response_gate(case_text, errors, "设计级用例生成产物")
            except ValueError as exc:
                errors.append(str(exc))

    if stage_status == "PASSED" or (not retry_exhausted and (handoff_dir.exists() or executable_dir.exists() or framework_dir.exists())):
        require(handoff_dir.is_dir(), errors, f"设计级用例交接目录不存在或不是目录：{handoff_dir}")
        if handoff_dir.is_dir():
            require_files(handoff_dir, HANDOFF_REQUIRED, errors, "设计级用例交接")
            validate_business_scenario_map_file(handoff_business_map_file, errors, require_passed=True, label="设计级用例交接 business_scenario_map.yaml")
            validate_business_scenario_doc_file(handoff_business_doc_file, errors, require_records=True)
            validate_business_long_chain_cases_file(handoff_business_long_chain_file, errors, require_passed=True)
            validate_business_long_chain_doc_file(handoff_business_long_chain_doc_file, errors, require_records=True)
            if handoff_coverage_point_file.is_file():
                validate_coverage_point_report_file(handoff_coverage_point_file, errors, require_records=True)
                validate_coverage_point_case_mapping(handoff_dir / "case_list.yaml", handoff_coverage_point_file, errors, require_passed=True)
            if coverage_point_file.is_file() and handoff_coverage_point_file.is_file():
                try:
                    source_report = read_text(coverage_point_file)
                    handoff_report = read_text(handoff_coverage_point_file)
                except ValueError as exc:
                    errors.append(str(exc))
                else:
                    if source_report != handoff_report:
                        errors.append("设计级用例交接 测试覆盖点报告.md 必须从阶段2原样复制")
            for source_file, handoff_file, display_name in (
                (business_long_chain_file, handoff_business_long_chain_file, BUSINESS_LONG_CHAIN_CASES),
                (business_long_chain_doc_file, handoff_business_long_chain_doc_file, BUSINESS_LONG_CHAIN_DOC),
            ):
                if source_file.is_file() and handoff_file.is_file():
                    try:
                        source_text = read_text(source_file)
                        handoff_text = read_text(handoff_file)
                    except ValueError as exc:
                        errors.append(str(exc))
                    else:
                        if source_text != handoff_text:
                            errors.append(f"设计级用例交接 {display_name} 必须从阶段2原样复制")
            for file_name, display_name in (
                (REQUIRED_CHAIN_FLOWS, "required_chain_flows.yaml"),
                (CHAIN_FLOW_CANDIDATE_AUDIT, "chain_flow_candidate_audit.yaml"),
            ):
                source_file = root / file_name
                handoff_file = handoff_dir / file_name
                if source_file.is_file() and handoff_file.is_file():
                    try:
                        source_text = read_text(source_file)
                        handoff_text = read_text(handoff_file)
                    except ValueError as exc:
                        errors.append(str(exc))
                    else:
                        if source_text != handoff_text:
                            errors.append(f"设计级用例交接 {display_name} 必须从根级分母产物原样复制")
            if selected_business_map_file.is_file() and handoff_business_map_file.is_file():
                try:
                    source_map = read_text(selected_business_map_file)
                    handoff_map = read_text(handoff_business_map_file)
                except ValueError as exc:
                    errors.append(str(exc))
                else:
                    if source_map != handoff_map:
                        errors.append("设计级用例交接 business_scenario_map.yaml 必须从选定入口原样复制")
            if selected_business_doc_file.is_file() and handoff_business_doc_file.is_file():
                try:
                    source_doc = read_text(selected_business_doc_file)
                    handoff_doc = read_text(handoff_business_doc_file)
                except ValueError as exc:
                    errors.append(str(exc))
                else:
                    if source_doc != handoff_doc:
                        errors.append("设计级用例交接 业务场景链路清单.md 必须从选定入口原样复制")

    if executable_dir.exists() or framework_dir.exists():
        validate_data_model(root, errors)
        require_files(executable_dir, ("执行级接口用例集.md", "前置数据构造规则.md"), errors, "执行级用例阶段")
        executable_release_required = stage_status == "PASSED" or (framework_dir.exists() and not retry_exhausted)
        validate_stage_sidecars(
            executable_dir,
            errors,
            "执行级用例阶段",
            "executable_interface_case_set",
            EXECUTABLE_COVERAGE_PAIRS,
            EXECUTABLE_MISSING_LISTS,
            require_passed=executable_release_required,
        )
        executable_coverage_matrix = executable_dir / "coverage_matrix.yaml"
        if executable_release_required and selected_required_flow_ids and executable_coverage_matrix.is_file():
            try:
                validate_required_chain_independent_coverage(
                    read_text(executable_coverage_matrix),
                    errors,
                    "执行级用例阶段/coverage_matrix.yaml",
                    selected_required_flow_ids,
                    "generated_executable_chain_case_count",
                    require_item_mappings=True,
                )
            except ValueError as exc:
                errors.append(str(exc))
        fact_source_text = validate_execution_fact_sources(executable_dir, errors, require_passed=executable_release_required)
        if "live_request_evidence" in fact_source_text:
            runtime_index = validate_runtime_evidence(root, errors, required=True, require_usable=True)
            validate_live_request_fact_source_refs(fact_source_text, runtime_index, errors)
        apifox_required = "apifox_mcp" in fact_source_text or (executable_dir / "apifox_evidence_index.yaml").is_file()
        validate_apifox_evidence_index(
            executable_dir,
            errors,
            require_passed=executable_release_required,
            required=apifox_required,
        )
        validate_executable_traceability(executable_dir, errors)

    if framework_dir.exists() and not retry_exhausted:
        validate_framework(root, errors)

    if executable_dir.exists() or framework_dir.exists():
        validate_confidence_stage_progression(root, framework_dir, errors)

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="校验接口自动化流水线总控阶段产物")
    parser.add_argument("output_root", help="流水线输出根目录")
    args = parser.parse_args()

    errors = validate_output_root(Path(args.output_root))
    if errors:
        print("校验结果：不通过")
        for index, error in enumerate(errors, start=1):
            print(f"{index}. {error}")
        return 1

    print("校验结果：通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
