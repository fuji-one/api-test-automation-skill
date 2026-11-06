# 结构化 Sidecar 契约

## 目录

- [读取时机](#读取时机)
- [使用原则](#使用原则)
- [规则正文](#规则正文)
- [Structured Sidecar Schemas](#structured-sidecar-schemas)
- [`stage_status.yaml`](#stage_statusyaml)
- [`retry_history.yaml`](#retry_historyyaml)
- [`coverage_matrix.yaml`](#coverage_matrixyaml)
- [`business_scenario_map.yaml`](#business_scenario_mapyaml)
- [`database_mcp_evidence_index.yaml`](#database_mcp_evidence_indexyaml)
- [`source_db_alignment.yaml`](#source_db_alignmentyaml)
- [`runtime_risk_audit.yaml`](#runtime_risk_audityaml)
- [`runtime_request_plan.skeleton.yaml`](#runtime_request_planskeletonyaml)
- [`db_before_after_probe_plan.yaml`](#db_before_after_probe_planyaml)
- [`runtime_blocker_candidates.yaml`](#runtime_blocker_candidatesyaml)
- [`runtime_stage_status.yaml`](#runtime_stage_statusyaml)
- [`runtime_evidence.yaml`](#runtime_evidenceyaml)
- [`runtime_value_catalog.yaml`](#runtime_value_catalogyaml)
- [`execution_fact_sources.yaml`](#execution_fact_sourcesyaml)
- [`apifox_evidence_index.yaml`](#apifox_evidence_indexyaml)
- [来源](#来源)

## 读取时机

生成、消费或校验任何 `stage_status.yaml`、`coverage_matrix.yaml`、业务场景、运行时证据、执行事实或 Apifox sidecar 前读取。

## 使用原则

所有阶段准出先看机器可读 sidecar，再看 Markdown 人工报告。Markdown 可以作为兼容证据，但不能替代 sidecar 的 pass/fail 判断。

## 规则正文

## Structured Sidecar Schemas

All stage decisions must be based on machine-readable sidecars first. Markdown reports remain human-facing evidence and may be used as a compatibility check, but they must not be the only source for pass/fail decisions once a sidecar exists.

### `stage_status.yaml`

Required for every executed stage directory.

```yaml
schema_version: 1
stage: pre_doc_analysis | source_api_facts | interface_testcase_generation | executable_interface_case_set | script_generation
status: passed | blocked | failed | coverage_insufficient
next_stage_allowed: true | false
input_paths:
  - path: "..."
    role: "..."
output_paths:
  - path: "..."
    role: "..."
gate_checks:
  - check_id: "..."
    status: passed | blocked | failed
    evidence_refs: ["..."]
blocking_issues: []
```

`status=passed` requires `next_stage_allowed=true` and `blocking_issues=[]`. Any blocked or failed status must keep `next_stage_allowed=false` and list source-bound blockers.

### `retry_history.yaml`

Required whenever a downstream gate asks an upstream stage to regenerate, and mandatory when the pipeline ends with `BLOCKED_RETRY_EXHAUSTED`.

```yaml
schema_version: 1
status: retrying | resolved | blocked
max_attempts: 3
next_stage_allowed: true | false
retry_key: "producer_stage->consumer_stage:gate_id"
gate_id: "..."
consumer_stage: interface_testcase_generation | design_case_handoff | executable_interface_case_set | script_generation
producer_stage: pre_doc_analysis | source_api_facts | interface_testcase_generation | executable_interface_case_set
final_blocker: "..."
attempts:
  - attempt: 1
    retry_key: "producer_stage->consumer_stage:gate_id"
    gate_id: "..."
    producer_stage: "..."
    consumer_stage: "..."
    reason: "..."
    regenerated_output_paths: ["..."]
    gate_result: passed | blocked | failed | coverage_insufficient
    gate_evidence_refs: ["..."]
```

Rules:

- Attempt count starts at 1 and may not exceed 3 for the same `retry_key`.
- `retry_key` is stable for the same producer stage, consumer stage, failed gate, and blocking contract type. Reworded blocker text, regenerated filenames, or a new timestamp must not create a new retry key.
- Before starting any retry, read the existing `retry_history.yaml`. If the same `retry_key` already has 3 attempts or `status: blocked`, stop immediately with `BLOCKED_RETRY_EXHAUSTED`.
- `retry_history.yaml` is append-only for the same `retry_key`: do not delete, renumber, overwrite, or reset earlier attempts after regeneration.
- Every retry must regenerate the producer stage output from its source inputs; do not patch only the downstream copy.
- After a retry passes, all downstream stages must consume only the latest regenerated files and discard earlier attempts as non-authoritative.
- If attempt 3 still cannot satisfy the consumer gate, stop the whole pipeline with `BLOCKED_RETRY_EXHAUSTED`; do not continue to later stages with partial files.
- Do not use this retry loop for missing external human inputs, missing environment/auth/data model, entry conflicts, or source evidence conflicts. Those states block directly with their existing status.

### `coverage_matrix.yaml`

Required for stages that claim coverage release or feed a downstream stage.

```yaml
schema_version: 1
stage: pre_doc_analysis | source_api_facts | interface_testcase_generation | executable_interface_case_set | script_generation
coverage_summary:
  denominator_scope: "..."
  coverage_rate: 100
long_chain_coverage_summary:
  required_when: "required_chain_flows.yaml contains required flows"
  denominator_scope: long_chain_only
  scenario_coverage_rate: 100
  function_coverage_rate: 100
  process_coverage_rate: 100
coverage_items:
  - coverage_id: "..."
    coverage_type: object | rule | test_point | main_flow | contract_rule | status_code | p0_p1 | design_case | executable_case | coverage_rule | pytest_nodeid | source_interface | source_contract_rule | source_business_rule | source_error_code | source_db_side_effect | source_scenario | chain_scenario | chain_function | chain_process
    status: covered | missing | conflict | blocked
    evidence_refs: ["..."]
missing_items: []
upstream_downstream_mappings:
  - upstream_id: "..."
    downstream_ids: ["..."]
    mapping_status: mapped | missing | conflict | blocked
```

For validator compatibility, the stage-specific count fields must also remain top-level:

| Stage | Required count fields | Required empty missing lists when passed |
|---|---|---|
| `pre_doc_analysis` | `object_total/object_covered`, `test_point_total/test_point_mapped`, `rule_total/rule_covered` | `missing_object_ids`, `missing_test_point_ids`, `missing_rule_ids` |
| `source_api_facts` | `source_interface_total/source_interface_covered`, `source_contract_rule_total/source_contract_rule_covered`, `source_business_rule_total/source_business_rule_covered`, `source_error_code_total/source_error_code_covered`, `source_db_side_effect_total/source_db_side_effect_covered`, `source_scenario_total/source_scenario_covered` | `missing_source_interface_ids`, `missing_source_contract_rule_ids`, `missing_source_business_rule_ids`, `missing_source_error_code_ids`, `missing_source_db_side_effect_ids`, `missing_source_scenario_ids` |
| `interface_testcase_generation` | `test_point_total/test_point_covered`, `main_flow_total/main_flow_covered`, `contract_rule_total/contract_rule_covered`, `status_code_total/status_code_covered`, `p0_p1_total/p0_p1_covered`; when required flows exist, also `chain_scenario_total/chain_scenario_covered`, `chain_function_total/chain_function_covered`, `chain_process_total/chain_process_covered` with `denominator_scope: long_chain_only` | `missing_test_point_ids`, `missing_main_flow_ids`, `missing_contract_rule_ids`, `missing_status_codes`, `missing_p0_p1_ids`; when required flows exist, also `missing_chain_scenario_ids`, `missing_chain_function_ids`, `missing_chain_process_ids` |
| `executable_interface_case_set` | `design_case_total/design_case_mapped`, `executable_case_total/executable_case_traced`, `coverage_rule_total/coverage_rule_mapped`; when required flows exist, also `chain_scenario_total/chain_scenario_covered`, `chain_function_total/chain_function_covered`, `chain_process_total/chain_process_covered` with `denominator_scope: long_chain_only` | `missing_design_case_ids`, `missing_executable_trace_ids`, `missing_coverage_rule_ids`; when required flows exist, also `missing_chain_scenario_ids`, `missing_chain_function_ids`, `missing_chain_process_ids` |

For `status=passed`, every required denominator total must be greater than 0. Non-legacy `coverage_items` must contain exactly one unique `coverage_id` for each denominator item by `coverage_type`, each item must be `status: covered` with non-empty `evidence_refs`, and `upstream_downstream_mappings` must contain a `mapped` record for every `coverage_id`. A `0/0` coverage claim is invalid.

For `pre_doc_analysis`, validators also accept the native `$pre-doc-analysis-pipeline` sidecar shape as a compatibility input: `stage_status.yaml` may use `source_files`、`stage_results`、`output_files`, and `coverage_matrix.yaml` may use `coverage_objects`. This compatibility does not relax status, `next_stage_allowed`, blocking issue, coverage count, or missing-list gates.

### `business_scenario_map.yaml`

Required for the selected entry before stage 2, regardless of document-entry or source-entry route.

```yaml
schema_version: 1
stage: business_scenario_mapping
status: passed | blocked | partial
next_stage_allowed: true | false
source_entry: doc | source
scenario_source_status: doc_confirmed | source_inferred
scenario_items:
  - scenario_id: "BS-001"
    scenario_name: "用户完成支付单支付"
    business_domain: "统一支付"
    executing_role: "用户"
    business_description: "用户作为支付发起方在业务系统下单后进入统一支付，系统创建支付单、发起支付并回查支付结果，验证支付单从创建到支付完成的业务链路"
    roles: ["用户", "统一支付系统"]
    source_refs: ["PRD.md#支付流程", "API.md#支付接口", "系统分析.md#支付状态流转"]
    related_interfaces: ["创建支付单接口", "支付单支付接口", "查询支付单接口"]
    business_chain: ["创建支付单", "发起支付", "查询支付结果"]
    state_chain: ["待支付", "支付中", "支付完成"]
    related_test_point_ids: ["TP-001"]
    related_coverage_rule_ids: ["RULE-001"]
    chain_type: single_interface | e2e_flow_candidate
    flow_generation_required: true | false
    flow_id: "FLOW-001"
    ordered_step_count: 3
    ordered_steps:
      - step_order: 1
        api_id: "API-001"
        interface: "创建支付单接口"
        test_point_id: "TP-001"
        source_ref: "API.md#创建支付单"
    confidence: high | medium | low
    blockers: []
blocking_issues: []
```

Gate:

- `status=passed`, `next_stage_allowed=true`, `scenario_items` 非空，`blocking_issues=[]`.
- Each scenario item must have non-placeholder `scenario_id`、`scenario_name`、Chinese `business_domain`、Chinese `executing_role`、Chinese `business_description`、`roles`、`source_refs`、`related_interfaces`、`business_chain`、`related_test_point_ids`、`related_coverage_rule_ids` and `blockers=[]`.
- `business_description` must explicitly include the `executing_role` and explain what that role does in the business process. Single-interface or unit-style scenarios must still use the same description standard as long-chain scenarios: `执行角色 + 业务动作 + 前置业务状态 + 结果或价值`, not only an API name or test method.
- Multi-interface scenarios should set `chain_type: e2e_flow_candidate`, `flow_generation_required: true`, stable `flow_id`, `ordered_step_count >= 2`, and ordered step records when the source evidence already identifies them as E2E flow candidates. If a scenario has `related_interfaces` count >= 3, `ordered_step_count >= 5`, `business_chain` step count >= 5, or `state_chain` step count >= 5`, validators may treat it as candidate discovery evidence, but it is not the authoritative required-flow denominator. Whether it becomes required depends on `required_chain_flows.yaml` and closed-loop evidence.
- Document entry should use `source_entry: doc` and `scenario_source_status: doc_confirmed`.
- Source entry should use `source_entry: source` and `scenario_source_status: source_inferred`; source-inferred business descriptions are acceptable only when they are traceable to source facts and `confidence` is `medium` or higher.
- `confidence=low` or unresolved blockers must stop stage 2 with `BLOCKED_NEED_BUSINESS_SCENARIO_MAPPING`.
- `业务场景链路清单.md` is the human-readable view of this sidecar and must not contain rows that are absent from `business_scenario_map.yaml`.

### `database_mcp_evidence_index.yaml`

Required under `00-inputs/` whenever a database MCP connection is used to generate or enrich `数据模型.md`.

```yaml
schema_version: 1
stage: database_mcp_data_model_normalization
status: passed | partial | blocked | failed
mcp_connection:
  connector_name: "database_mcp"
  database_product: "mysql | postgresql | other"
  host_ref: "masked host or environment alias"
  database_name: "..."
  schema_name: "..."
  source_status: confirmed | missing | conflict | blocked
evidence_items:
  - evidence_id: "DB-MCP-001"
    evidence_level: database_identity | table_schema | column_schema | index_constraint | foreign_key | relationship_graph | cleanup_key | ownership_boundary | sample_forbidden
    mcp_ref: "database/schema/table/column/index"
    supports: ["database", "schema", "table", "column", "type", "nullable", "default", "primary_key", "unique_key", "index", "relationship", "setup_order", "cleanup_order", "ownership_key", "cleanup_key"]
    source_status: confirmed | missing | conflict | blocked
conflict_items: []
blocking_issues: []
```

`status=passed` requires the MCP connection identity to be confirmed, all evidence items needed by source-visible DB side effects to be confirmed, and `conflict_items=[]` plus `blocking_issues=[]`. Do not record raw passwords, tokens, or full connection strings.

### `source_db_alignment.yaml`

Required under `00-inputs/` whenever database MCP evidence is used. It is the gate that proves the connected database matches the extracted source facts before `数据模型.md` can feed executable cases or scripts.

```yaml
schema_version: 1
stage: database_mcp_data_model_normalization
status: passed | blocked | failed
next_stage_allowed: true | false
source_fact_ref: "02-source-api-facts/docs/source-facts/source-api-facts.json"
database_evidence_ref: "00-inputs/database_mcp_evidence_index.yaml"
normalized_data_model_ref: "00-inputs/数据模型.md"
connection_identity:
  source_config_refs: ["application.yml#spring.datasource.url"]
  mcp_database_name: "..."
  mcp_schema_name: "..."
  confirmation_status: confirmed | missing | conflict | blocked
alignment_checks:
  - check_id: datasource_identity
    status: passed | blocked | failed
    evidence_refs: ["..."]
  - check_id: table_mapping
    status: passed | blocked | failed
    evidence_refs: ["..."]
  - check_id: column_mapping
    status: passed | blocked | failed
    evidence_refs: ["..."]
  - check_id: key_constraint_mapping
    status: passed | blocked | failed
    evidence_refs: ["..."]
  - check_id: relationship_graph_mapping
    status: passed | blocked | failed
    evidence_refs: ["..."]
  - check_id: seed_cleanup_strategy
    status: passed | blocked | failed
    evidence_refs: ["..."]
  - check_id: side_effect_mapping
    status: passed | blocked | failed
    evidence_refs: ["..."]
missing_tables: []
missing_columns: []
incompatible_columns: []
unresolved_side_effects: []
unresolved_relationships: []
missing_cleanup_keys: []
blocking_issues: []
```

`status=passed` requires `next_stage_allowed=true`, confirmed connection identity, source-referenced tables present in MCP schema, source-referenced columns type-compatible with MCP columns, required primary/unique/cleanup keys identified, source-visible DB side effects mapped, setup/cleanup graph edges resolved for all executable setup/cleanup tables, and all missing/conflict/blocking lists empty.

### `runtime_risk_audit.yaml`

Required under `04-runtime-evidence-plan/` when full runtime evidence planning is executed.

```yaml
schema_version: 1
stage: runtime_evidence_planning
status: passed | blocked | failed
next_stage_allowed: true | false
risk_summary:
  safe_readonly: 0
  auth_setup: 0
  mutation_requires_cleanup: 0
  destructive_state: 0
  external_or_callback: 0
  unknown_requires_review: 0
request_decision_summary:
  request_allowed: 0
  request_allowed_with_user_config: 0
  manual_confirmation_required: 0
  blocked_until_isolated_account_and_cleanup: 0
execution_authorization:
  case_scope_default_authorized: false
  environment_default: "test"
  env_name: ""
  is_test_environment: true
  scope: "selected_case_denominator"
  source_type: "user_config | none"
  source_ref: ""
db_authorization:
  allow_source_bound_before_after_query: false
  allow_current_run_cleanup: false
  non_test_reauthorization_required: false
  non_test_reauthorization_status: not_required | provided | missing
  source_ref: ""
classification_policy:
  source_signals: ["http_method", "path_semantics", "case_name_semantics", "case_type", "source_side_effect_hints"]
  project_specific_values_allowed: false
  blind_all_interface_execution_allowed: false
items:
  - item_id: "RISK-0001"
    case_id: "DC-001"
    name: "..."
    priority: "p0"
    case_type: "normal | exception | chain | ..."
    module: "..."
    method: "GET"
    path: "/..."
    risk_level: safe_readonly | auth_setup | mutation_requires_cleanup | destructive_state | external_or_callback | unknown_requires_review
    request_decision: request_allowed | request_allowed_with_user_config | manual_confirmation_required | blocked_until_isolated_account_and_cleanup
    reason_codes: ["..."]
    cleanup_required: false
    db_probe_required: false
    source_case_ref: "case_list.yaml#/cases/0"
```

`status=passed` means classification completed, not that all interfaces are executable. Runtime execution may proceed only for items whose `request_decision` permits requesting.

### `runtime_request_plan.skeleton.yaml`

Optional planning output under `04-runtime-evidence-plan/`; it is not the executable request plan consumed by the requester until runtime values and user configuration are filled.

```yaml
schema_version: 1
stage: runtime_request_plan_skeleton
status: ready_for_manual_completion | blocked_no_allowed_request
next_stage_allowed: false
env:
  env_name: test
  base_urls: {}
  secrets_ref: "${RUNTIME_SECRETS_JSON}"
request_scope:
  mutating_requests_allowed: false
  execute_only_request_allowed_items: true
  cleanup_required_before_mutation: true
steps:
  - step_id: "STEP-0001"
    case_id: "DC-001"
    module: "${MODULE_ALIAS}"
    method: "GET"
    path: "/..."
    headers: "${RUNTIME_HEADERS}"
    query: "${RUNTIME_QUERY}"
    body: "${RUNTIME_BODY}"
    assertions_ref: "case_list.yaml#/cases/0"
    extract: {}
    execution_status: needs_runtime_values
    risk_audit_ref: "runtime_risk_audit.yaml#/items/0"
```

Do not pass this skeleton directly to `scripts/run_live_request_evidence.py`; first replace placeholders through a run-specific execution configuration that supplies base URLs, auth, allowed scope, request values, expected statuses, and extraction rules.

### `db_before_after_probe_plan.yaml`

Required under `04-runtime-evidence-plan/` when any runtime candidate can change state or needs cleanup evidence.

```yaml
schema_version: 1
stage: db_before_after_probe_planning
status: ready | not_required | blocked
next_stage_allowed: true | false
probe_policy:
  db_mcp_only_for_evidence_collection: true
  scripts_must_consume_normalized_sidecars: true
  ownership_keys_required_for_mutation: true
  cleanup_graph_required_for_mutation: true
probes:
  - probe_id: "DBP-0001"
    case_id: "DC-001"
    probe_strategy: before_after_snapshot_required
    ownership_key_required: true
    expected_delta_source_ref: "case_list.yaml#/cases/0"
    cleanup_strategy_required: true
    risk_audit_ref: "runtime_risk_audit.yaml#/items/0"
```

The probe plan records what must be evidenced; it must not contain database credentials, live connection strings, or project-specific SQL values unless they come from the run-specific evidence directory.

### `runtime_blocker_candidates.yaml`

Required under `04-runtime-evidence-plan/` whenever planning finds candidates that cannot be safely requested.

```yaml
schema_version: 1
stage: runtime_blocker_candidate_collection
status: passed | has_blockers
next_stage_allowed: true
blocking_items:
  - blocker_id: "RTB-0001"
    case_id: "DC-001"
    risk_level: mutation_requires_cleanup
    reason_codes: ["state_mutation_requires_db_before_after_and_cleanup"]
    needed_input:
      - db_before_after_snapshot
      - ownership_key
      - cleanup_strategy
      - manual_execution_confirmation
    risk_audit_ref: "runtime_risk_audit.yaml#/items/0"
```

These blockers are allowed to coexist with executable-case generation only when the affected facts are not required for `PASSED`. Required facts without closed evidence must remain blocked.

### `runtime_stage_status.yaml`

Required under `04-runtime-evidence/` whenever direct runtime evidence collection is executed.

```yaml
schema_version: 1
stage: runtime_live_evidence
status: passed | partial | blocked | failed
next_stage_allowed: true | false
request_scope:
  env_name: test
  allowed_modules: []
  mutating_requests_allowed: false
  cleanup_required: true
input_paths:
  - path: "runtime_request_plan.yaml"
    role: "runtime_request_plan"
output_paths:
  - path: "runtime_evidence.yaml"
    role: "runtime_evidence"
gate_checks:
  - check_id: direct_request_execution
    status: passed | blocked | failed
    evidence_refs: ["runtime_evidence.yaml"]
continuation_queue:
  schema_version: 1
  queue_policy: long_chain_then_p0_p1_p2_p3_skip_recoverable_and_continue
  summary:
    pending: 0
    requested: 0
    evidenced: 1
    retryable: 0
    skipped_recoverable: 0
    blocked_final: 0
    excluded: 0
  items:
    - case_id: DC-001
      flow_id: FLOW-001
      step_order: 1
      step_id: STEP-0001
      priority_bucket: long_chain | p0 | p1 | p2 | p3 | other
      queue_state: evidenced | retryable | skipped_recoverable | blocked_final
      last_attempt: request_ok
      next_action: consume_confirmed_evidence
      reason_code: runtime_evidence_confirmed
      evidence_refs: ["runtime_evidence.yaml#RT-001"]
blocking_issues: []
```

`status=passed` requires `next_stage_allowed=true`, `blocking_issues=[]`, and no unredacted password、token、Authorization、Cookie or equivalent secret values in any runtime evidence output. `status=partial` may be used only when at least one confirmed evidence item is usable and the missing values are explicitly listed. Queue items must use `queue_state` and must not contain a nested `status` field.

### `runtime_evidence.yaml`

Runtime evidence is produced by a direct requester, not by Apifox MCP and not by the script generator. It records direct interface responses, extracted runtime values, redaction status, and contract/data-model conflict results.

```yaml
schema_version: 1
stage: runtime_live_evidence
status: passed | partial | blocked | failed
next_stage_allowed: true
request_scope:
  env_name: test
  allowed_modules: []
  mutating_requests_allowed: false
  cleanup_required: true
auth_evidence:
  status: confirmed | missing | failed | blocked
  token_source: login_response | user_config | none
  token_extract_path: "$.data.token"
  secret_redaction: enabled
evidence_items:
  - evidence_id: "RT-LOGIN-001"
    flow_id: "FLOW-LOGIN"
    case_id: "DC-001"
    method: "POST"
    path: "/api/v1/auth/login"
    source_contract_ref: "接口结构化契约清单.md#..."
    request_source_ref: "runtime_request_plan.yaml#..."
    response_status: 200
    business_code_path: "$.code"
    business_code_value: 0
    value_type: business_code | enum_code | status_code | field_value | token | id | assertion_value
    field_path: "$.data.userStatus"
    field_value: "ACTIVE"
    source_status: confirmed | missing | conflict | blocked
    usable_for_execution_case: true
    redacted: false
    db_before_ref: "db_before_after_probe_plan.yaml#DBP-001" # mutating cases only
    db_after_ref: "runtime_evidence.yaml#DB-AFTER-001" # mutating cases only
    db_delta_assertion: "status changed from pending to active" # source-bound, not guessed
    db_probe_source_ref: "数据模型.md#cleanup-graph" # mutating cases only
dependency_derivations:
  - derivation_id: "DRV-ORDER-001"
    flow_id: "FLOW-001"
    producer_step_id: "STEP-0002"
    consumer_step_id: "STEP-0003"
    producer_field_path: "$.data.orderId"
    consumer_field_path: "$.body.orderId"
    value_source_ref: "runtime_evidence.yaml#RT-ORDER-001"
    inference_reason: "producer response orderId matches required flow link key and consumer contract orderId"
    cross_check_refs:
      - "required_chain_flows.yaml#FLOW-001"
      - "接口结构化契约清单.md#orderId"
      - "数据模型.md#order_id"
    source_status: confirmed | missing | conflict | blocked
    usable_for_execution_case: true
conflict_items: []
blocking_issues: []
```

Only `source_status=confirmed` and `usable_for_execution_case=true` evidence may be consumed by executable cases. If runtime values conflict with `接口结构化契约清单.md`, design-level cases, `数据模型.md`, DB MCP evidence, or source-extracted facts, stop before execution-level release with `FAILED_EXECUTION_READINESS`; never auto-overwrite the contract with runtime values.

### `runtime_value_catalog.yaml`

This catalog is the normalized runtime-value feed for `$executable-interface-case-set`.

```yaml
schema_version: 1
stage: runtime_value_catalog
status: passed | partial | blocked | failed
values:
  - value_id: "VAL-USER-STATUS-ACTIVE"
    value_type: enum_code
    field: "userStatus"
    value: "ACTIVE"
    source_type: live_request_evidence
    source_ref: "runtime_evidence.yaml#RT-USER-001"
    cross_checked_by:
      - "数据模型.md#user_status"
      - "接口结构化契约清单.md#UserStatus"
    source_status: confirmed
flow_value_links:
  - link_id: "LINK-FLOW-001-ORDER-ID"
    flow_id: "FLOW-001"
    producer_step_id: "STEP-0002"
    consumer_step_id: "STEP-0003"
    producer_field_path: "$.data.orderId"
    consumer_field_path: "$.body.orderId"
    value_id: "VAL-ORDER-ID-001"
    value_source_ref: "runtime_evidence.yaml#DRV-ORDER-001"
    inference_reason: "runtime response value is the same business object key required by the next request"
    cross_checked_by:
      - "required_chain_flows.yaml#FLOW-001"
      - "接口结构化契约清单.md#orderId"
    source_status: confirmed
    usable_for_execution_case: true
usable_fact_types:
  - token_rule
  - test_data_rule
  - variable_link
  - assertion_rule
missing_values: []
conflict_values: []
blocking_issues: []
```

When `execution_fact_sources.yaml` references `source_type: live_request_evidence`, both `runtime_evidence.yaml` and `runtime_value_catalog.yaml` must exist, be `passed` or `partial`, have empty conflict lists, and contain the referenced confirmed `evidence_id` or `value_id`.

### `execution_fact_sources.yaml`

Required for `05-executable-interface-case-set/` whenever the executable stage is attempted.

```yaml
schema_version: 1
stage: executable_interface_case_set
status: passed | blocked | failed
required_human_inputs:
  runtime_execution_config:
    status: provided | missing
    source_ref: "runtime_execution_config.yaml#..."
  environment_reference:
    status: provided | missing
    source_ref: "执行配置.md#..."
    env_name: ""
    is_test_environment: true
  authentication_account:
    status: provided | missing
    source_ref: "执行配置.md#..."
  db_authorization:
    status: provided | missing | not_required
    non_test_reauthorization_status: not_required | provided | missing
    source_ref: "runtime_execution_config.yaml#db_authorization"
fact_sources:
  - fact_id: "..."
    fact_type: token_rule | test_data_rule | seed_value | enum_code | seed_scope_guard | relationship_graph | ownership_key | variable_link | assertion_rule | db_assertion | cleanup_strategy | transport_crypto_contract | external_dependency_value
    source_type: user_config | data_model | interface_contract | design_case | apifox_mcp | live_request_evidence | prior_response | precondition_api_response | db_seed_evidence | external_sandbox_evidence
    source_ref: "..."
    source_status: confirmed | missing | conflict | blocked
missing_required_facts: []
conflict_facts: []
blocking_issues: []
```

`status=passed` requires `runtime_execution_config.status=provided`, `environment_reference.status=provided`, `authentication_account.status=provided`, `missing_required_facts=[]`, `conflict_facts=[]`, and `blocking_issues=[]`. Every setup-produced value consumed by a request field, expected response, assertion, DB assertion, variable link, or cleanup rule must have a confirmed `seed_value`、`enum_code`、`db_assertion`、`cleanup_strategy`, or `external_dependency_value` source entry and must be filled into execution-level cases as a concrete value or executable variable reference. If `environment_reference.is_test_environment=false` and any DB before/after, cleanup, rollback, or status-recovery fact is required, `db_authorization.non_test_reauthorization_status` must be `provided`; otherwise block with `BLOCKED_NEED_EXECUTION_INPUT`. When encrypted interfaces are confirmed, at least one `transport_crypto_contract` fact must be `confirmed` and cite the algorithm reference, key source, request payload scope, request plaintext serialization, request envelope, and response envelope evidence.

### `apifox_evidence_index.yaml`

Apifox MCP is an optional auxiliary evidence source for `05-executable-interface-case-set/`, not a prerequisite for script generation and not a runtime requester. Write this sidecar only when Apifox MCP evidence is actually consulted, when the user explicitly requires Apifox alignment, or when `execution_fact_sources.yaml` references `source_type: apifox_mcp`. Missing, incomplete, or unavailable Apifox MCP data must not block generation when the same required execution facts are confirmed by source contracts, user configuration, database-normalized evidence, runtime evidence, or design artifacts. The only Apifox-related states that block are explicit Apifox-required user scope or conflict between used Apifox evidence and the release baseline.

```yaml
schema_version: 1
stage: executable_interface_case_set
status: passed | partial | blocked | failed
evidence_items:
  - evidence_id: "..."
    evidence_level: project_structure | interface_contract | saved_case_example | response_example
    apifox_ref: "project/interface/case/response id or path"
    supports: ["method", "path", "request_schema", "response_schema", "status_code", "business_code", "sample_value"]
    source_status: confirmed | missing | conflict | blocked
conflict_items: []
conflict_priority:
  - "structured contract conflicts with any Apifox evidence -> block release; do not overwrite"
  - "runtime values must come from 04-runtime-evidence, not Apifox MCP"
  - "saved_case_example and response_example may fill sample candidates only when aligned with contract"
  - "project_structure locates endpoints only; it cannot fill request, response, status, or assertion facts"
resolution_policy:
  project_structure: "定位项目、模块、目录、接口 ID，不作为字段、断言、环境或鉴权依据；不可用时记录未使用或缺失，不阻塞"
  interface_contract: "辅助校验 method/path/参数/schema/status/error code；与结构化契约冲突时阻塞，不能静默覆盖"
  saved_case_example: "读取保存用例、debug case、示例值，必须与契约一致；仅补样例和执行参数候选"
  response_example: "读取响应示例和值候选，必须与契约一致；不能代表真实运行时取证"
```


## 来源

本文件从 `SKILL.md` 原主契约拆分而来；完整历史契约保存在 `references/full-contract.md`。
