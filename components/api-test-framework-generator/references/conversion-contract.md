# Conversion Contract

## 目录

- 1. Stage Contract
- 2. Required Inputs
- 3. Required Input Evidence
- 4. Input Precheck Gate
- 5. Gate Rules
- 6. Output Schema
- 7. Mapping Rules
- 8. Framework Rules
- 9. Validation
- 10. Downstream Boundary
- 11. SQL Command Generation


## 1. Stage Contract

This skill is a pipeline stage that converts execution cases, precondition rules, and a data model artifact into an `api-test-framework/` project. It must be source-bound: every generated URL, method, request value, expected status, assertion, extraction rule, SQL setup command, SQL cleanup command, and Allure title must trace back to `执行级接口用例集.md`, `前置数据构造规则.md`, or the data model artifact such as `数据模型.md`.

Stage statuses:

- `blocked`: a required input is missing, unreadable, case-free, gate-failed, or lacks executable values.
- `generated`: framework files and tests were generated, but pytest collection or execution has not been completed.
- `validated`: generation completed and structural/syntax/collection validation passed.

When blocked, keep output case-free: do not generate `api/*.py`, `data/*.yaml`, Python data modules under `data/`, or `testcases/test_*.py` from guessed data. Write a machine-readable status file at `api-test-framework/configs/generation_status.yaml` if a framework directory is still created.

## 2. Required Inputs

Require all input files before generation:

- `执行级接口用例集.md`: executable API cases, or explicit case-free status.
- `前置数据构造规则.md`: environment, auth, precondition, cleanup, variable flow, repeatability, and pytest+allure conversion gate.
- Data model artifact, recommended name `数据模型.md`: table structures, fields, primary keys, unique keys, indexes, enum/status values, required/default rules, entity relationships, foreign-key or knowledge-graph edges, aggregate boundaries, setup order, and cleanup order.
- `required_chain_flows.yaml`: required when upstream produced it; authoritative denominator for E2E flow scripts that must be generated.
- `business_scenario_map.yaml` and `测试覆盖点报告.md`: required when upstream produced them; used only as candidate/context evidence and human-review reference. They must not by themselves require E2E flow script generation.
- Interface transport encryption policy or runtime contract: required when upstream confirms encrypted interfaces; it must define whether scripts use plain HTTP, confirmed encrypted transport, or are blocked for missing crypto execution input.

Accept Markdown, YAML, or JSON for the data model when the user provides a concrete path. Treat missing, unreadable, empty, or mojibake input as a blocking precheck failure.

## 3. Required Input Evidence

Require these fields before script generation:

- Interface identity: case id, interface name, HTTP method, and path.
- Coverage identity: design case id, coverage object ids, coverage rule ids, and test point id inherited from `执行级接口用例集.md`.
- Environment: target env names and source-bound `base_url` for each requested env.
- Runtime configuration entry: when concrete secrets, DB URLs, live-only drivers, or network tunnels are intentionally runtime-provided, the generated project must expose config entrypoints such as `configs/{env}.yaml`, `configs/database.yaml`, environment-variable references, and pytest `--env`. These pending runtime values block live execution only, not script generation.
- Authentication: auth type, token/header/cookie location, acquisition or injection rule, and variable name.
- Request: path/query/header/body fields with concrete values or source-bound variable references.
- Request shape contract: source-visible scalar/list/object/map field kinds, nesting, array order, `null`, and intentional omission rules for every generated request field. When a field crosses a confirmed transport or persistence boundary as serialized JSON/text, record the boundary and source evidence instead of changing the business-plaintext request shape.
- Request validation closure: positive-path runnable cases must satisfy source-visible required-field rules from request DTO annotations, OpenAPI required fields, or equivalent contracts. A required field may be omitted only in an explicit validation/error branch with matching expected assertions.
- Validation branch isolation: when a branch targets one missing, blank, invalid, enum, length, boundary, or conflict field, all unrelated required fields and auth/account context must remain valid so the response proves that intended branch instead of an earlier validation failure.
- Request variant consistency: ordinary cases, required E2E flow steps, optional async cases, and archive cases that share the same method/path and compatible request variant must preserve the confirmed required field set and source-bound business parameters unless a source/runtime reason explains the difference.
- Assertions: expected HTTP status code and at least one response assertion, error-code assertion, field assertion, or state-change assertion.
- Preconditions: setup data rules for all required upstream state, including whether each rule runs before every test or only a named case group.
- Variable flow: extraction paths and injection targets for cross-step values.
- E2E flow suite evidence: every required flow in `required_chain_flows.yaml`, `flow_id`, producer executable case, consumer executable case, variable name, extraction path or regex, injection target, step order, flow title/story, chain assertion, cleanup boundary, and source evidence when multiple APIs form a business chain. Candidate signals from `business_scenario_map.yaml` or `测试覆盖点报告.md` are review evidence only unless confirmed in `required_chain_flows.yaml`.
- Cleanup: cleanup API/SQL/manual rule, execution timing, and explicit source statement when cleanup is not required.
- Cleanup closure strategy: every candidate must record `closure_mode`, `evidence_strength`, and `automation_decision` (`runnable`, `safe_subset_only`, `generated_non_live`, `manual_review_only`, or `blocked_live_execution`). DB before/after is required only for local persistent mutation that lacks stronger source/runtime no-side-effect or containment evidence. Source-confirmed read-only, runtime no-delta, sandbox/mock-isolated, same-interface restore, isolated account/snapshot, and accepted non-live business exceptions must be represented explicitly instead of forcing every case through DB before/after.
- Conditional side-effect cleanup: optional notification/message/cache/queue/callback/linkage records must be distinguished from primary business objects. Conditional side-effect cleanup may allow zero affected rows only with exact current-run ownership keys and scoped final verification; primary persisted business rows still require strict cleanup or restore evidence.
- Setup/cleanup materialization: cleanup references alone are not executable. Mutable, destructive, DB-mock, DB-seed, restore, status-transition, send/upload, or external-callback cases that enter live execution require materialized API/SQL setup and cleanup actions with fixture attachment, id/ownership boundary, and before/after or stronger closure evidence. Source-confirmed business-valid cases that cannot be safely cleaned may be generated only as `generated_non_live` or `manual_review_only`, with source reason and assertion/observation boundary.
- SQL-driven case classification: cases that require SQL setup, SQL cleanup, runtime variable extraction, final DB verification, DB restore, DB assertion, or DB-mock cleanup must be classified by the shared predicate `enabled sql_fixture_required OR active SQL/DB setup_cleanup_materialization OR active db_assertion_materialization OR matching case id in data/case_sql_commands.yaml`. Explicit `not_required`、`no_cleanup_required` and API-only materialization values are non-SQL statuses, not active SQL signals. Validators and generated pytest markers must not rely on only one field when the runtime evidence has already proved another SQL materialization signal.
- Existing-state closure: positive write-side-effect cases constrained by uniqueness, idempotency, pending-review records, relationship state, quota state, or other existing data must prove the starting state through precheck API, precise API cleanup/restore, bounded SQL pre-clean/restore, isolated account/snapshot, or an explicit non-live/manual decision before they are counted as live runnable.
- Target run scope: classify the requested execution target as `all_generated_cases` or `safe_subset` before generating code. When the user wants all cases to run, exclusions, cleanup_refs-only mutable cases, pending SQL runtime validation, or unresolved setup/cleanup materialization are blocking items, not denominator reductions.
- Repeatability: idempotency or unique-data strategy for repeated runs.
- Flow type: main flow or branch flow for every generated case.
- Data model evidence: table names, columns, primary keys, unique keys, required fields, default rules, indexes, and status enums used by setup or cleanup SQL.
- Knowledge graph evidence: entity relationships, foreign-key direction, creation order, cleanup order, aggregate boundaries, and upstream/downstream dependency paths.
- Database execution evidence: database type, connection URL source, required driver package, transaction rule, and whether SQL execution is allowed in the target environment.
- Transport encryption execution evidence when encrypted interfaces are confirmed: algorithm reference, key source reference, request payload scope, request plaintext serialization, request envelope, response envelope, confirmed encrypted interface list, confirmed no-encrypt interface list, and evidence. Request templates, response assertions, extraction rules, injection rules, and runtime variables must remain plaintext business data.
- Shared requester/crypto adapter evidence when encrypted interfaces are confirmed: generated shared client/helper files, dependency check rule, static contract validation result, optional safe live smoke result, status sidecar path, and release boundary. Static validation can unblock smoke-candidate classification but cannot make a case live-execution-ready by itself.
- For the confirmed whole-parameter request contract, the client must merge common parameters and business parameters into one plaintext dictionary, serialize the whole dictionary into a UTF-8 JSON string, encrypt the string, and send JSON body `{"data": "<ciphertext>"}`. This contract forbids field-level encryption, `param` wrapping, and raw ciphertext body transport.
- For the confirmed encrypted-`data` response contract, the outer response JSON remains plaintext. The client decrypts only `data` when `data` is a string, parses the decrypted JSON string into an object, and exposes that plaintext object to assertions, extraction rules, and flow variable injection.

If any required evidence is absent, list it under `missing_items` and stop generation.

## 4. Input Precheck Gate

Generate `api-test-framework/configs/input_precheck_report.yaml` before any code, data, or SQL output is considered ready.

Required checks:

| Check | Pass condition |
| --- | --- |
| `file_availability` | All required input files exist, are readable, and are not empty |
| `encoding_quality` | All text inputs are UTF-8 and contain no mojibake |
| `stage_status` | Upstream artifacts are not case-free, blocked, or explicitly non-convertible |
| `case_traceability` | Every executable case has case id, design case id, coverage object ids, coverage rule ids, test point id, title, priority, flow type, request contract, expected status, and assertion evidence |
| `precondition_consistency` | Setup, token, cleanup, extraction, and injection rules are present for every case that requires them |
| `request_required_field_closure` | Positive-path runnable requests include all source-visible required fields with legal values, or missing fields are explicitly tied to validation/error assertions |
| `validation_branch_isolation` | Error/validation branch cases keep all non-target required fields and required context valid so the asserted error belongs to the intended missing/invalid field |
| `request_variant_consistency` | Compatible generated surfaces for the same method/path/request variant preserve confirmed request fields and business parameters unless a source/runtime difference is recorded |
| `request_shape_fidelity` | Generated request data, flow overrides, archive entries, and generated collection artifacts preserve source-visible scalar/list/object/map shapes, nesting, `null`, and intentional omission; serialized forms are allowed only at confirmed transport or persistence boundaries |
| `cleanup_closure_strategy` | Every candidate has `closure_mode`, `evidence_strength`, and `automation_decision`; DB before/after is required only for local persistent mutation without stronger no-side-effect or containment evidence; `generated_non_live` and `manual_review_only` are explicit and cannot count as live execution |
| `setup_cleanup_materialization` | Every selected live mutable case has executable setup/cleanup through fixtures, same-interface restore, isolated containment, or an explicit source-bound no-cleanup rule; refs-only cleanup blocks runnable generation |
| `sql_fixture_materialization` | SQL-driven cases are detected by the shared SQL predicate and have `case_id` marker, fixture attachment, matching `data/case_sql_commands.yaml` entries, and lifecycle commands required by their evidence |
| `existing_state_closure` | Positive write-side-effect cases that can be affected by existing rows, relationships, pending records, quotas, or idempotency keys have a materialized clean-start strategy or are marked non-live/manual |
| `target_run_scope_consistency` | `all_generated_cases` preserves every generated candidate in the executable denominator; exclusions are allowed only for an explicitly requested `safe_subset` and must be recorded |
| `e2e_flow_contract` | Every required flow in `required_chain_flows.yaml` is represented in `data/flow_cases.yaml` or `data/flow_cases.py`; missing source-bound producer/consumer variables, extraction paths, injection targets, chain assertions, or cleanup boundaries block generation |
| `data_model_completeness` | Referenced tables, fields, keys, enums, indexes, and relationships exist in the data model artifact |
| `cross_file_consistency` | Case ids, variable names, entity names, table names, columns, and status values are consistent across all inputs |
| `sql_readiness` | SQL setup/cleanup has table evidence, graph order, ownership keys, cleanup reverse order, and affected-row expectations |
| `sql_mutation_exit_gate` | INSERT/DELETE commands have command-level exit gates, id-bound single-row scope, and runtime before/after row-count validation plans |
| `transport_encryption_policy` | If no encrypted interfaces are confirmed, the gate is not applicable or plain HTTP; if encrypted interfaces are confirmed, algorithm, key source, request payload scope, request serialization, request envelope, and response envelope evidence are complete; unresolved policy or missing crypto runtime contract blocks generation |
| `transport_crypto_contract` | When encrypted interfaces are confirmed, request payload scope, request JSON serialization, request ciphertext field, response decrypt field, response parse rule, and key source are confirmed; missing items block generation |
| `shared_requester_crypto_adapter` | When encrypted interfaces are confirmed, generated shared requester/adapter files, dependency checks, status sidecar, and static validation are present; missing or placeholder adapter blocks live readiness |

Use this schema:

```yaml
stage: "input_precheck"
status: "passed"
source_files:
  execution_cases: "执行级接口用例集.md"
  precondition_rules: "前置数据构造规则.md"
  data_model: "数据模型.md"
checks:
  file_availability: "passed"
  encoding_quality: "passed"
  stage_status: "passed"
  case_traceability: "passed"
  precondition_consistency: "passed"
  request_required_field_closure: "passed"
  validation_branch_isolation: "passed"
  request_variant_consistency: "passed"
  request_shape_fidelity: "passed"
  cleanup_closure_strategy: "passed"
  setup_cleanup_materialization: "passed"
  sql_fixture_materialization: "passed"
  existing_state_closure: "passed"
  target_run_scope_consistency: "passed"
  e2e_flow_contract: "passed"
  data_model_completeness: "passed"
  cross_file_consistency: "passed"
  sql_mutation_exit_gate: "passed"
  sql_readiness: "passed"
  transport_encryption_policy: "passed"
  transport_crypto_contract: "passed"
  shared_requester_crypto_adapter: "passed"
  coverage_traceability: "passed"
missing_items: []
blocking_issues: []
```

Block generation when any check is not `passed`. Do not mark downstream readiness until this report has `status: "passed"`.

## 5. Gate Rules

Block generation when any condition is true:

- Any required input file is missing, unreadable, empty, or has mojibake.
- The data model artifact is missing, unreadable, empty, inconsistent, or has mojibake.
- `configs/input_precheck_report.yaml` is missing or has a status other than `passed`.
- `执行级接口用例集.md` states that it is case-free or contains no executable cases.
- `前置数据构造规则.md` states that script generation, data construction, auth, cleanup, or repeatable execution gate failed.
- Required request or assertion values are described only at a conceptual level.
- A positive-path runnable case omits a source-visible required request field or sends an empty body while the request contract requires fields. Explicit missing-field validation/error branches are allowed only when expected assertions match that branch.
- A validation/error branch claims to test one missing, blank, invalid, enum, length, boundary, or conflict field, but another unrelated required field, auth/account context, or upstream variable is absent or invalid and can cause an earlier validation failure.
- A generated ordinary case, E2E flow step, optional async case, or archive case uses the same method/path and compatible request variant as another source-backed case but silently drops required fields or source-bound business parameters without a recorded role/state/dependency/branch reason.
- A generated ordinary case, E2E flow step, optional async case, archive case, or generated collection changes a source-visible array/list/object/map into a scalar string, flattens nesting, drops array order, conflates `null` with omission, or stringifies business-plaintext fields without a confirmed transport/persistence-boundary rule.
- A case depends on an unknown upstream variable, missing token, unknown environment, or unresolved data model.
- A case is requested for live execution and requires precondition setup or cleanup, but the source does not provide an executable rule or accepted no-cleanup/containment closure mode.
- A selected live mutable case has only `cleanup_refs`, `cleanup_id`, `source_ref`, DB before/after files, or narrative cleanup evidence without generated API/SQL setup or cleanup actions consumed by fixtures, same-interface restore, isolated containment, or explicit source-bound no-cleanup proof.
- A cleanup command for an optional downstream side effect requires exactly one affected row without evidence that the side effect is always produced, or it allows zero affected rows without scoped final verification. This does not permit relaxed cleanup for the primary business object.
- A SQL-driven case is selected for live execution but the generated case data, pytest marker, fixture signature, `data/case_sql_commands.yaml`, and SQL validators do not agree on the same shared SQL predicate.
- A positive write-side-effect case is selected for live execution while existing-state conflicts can change the main-path result and no precheck, cleanup/restore, bounded SQL pre-clean, isolated account/snapshot, or non-live/manual decision is materialized.
- The requested target run scope is `all_generated_cases`, but any candidate case is excluded from the executable denominator, has `readiness: blocked`, has `automation_decision: generated_non_live` or `manual_review_only`, lacks executable setup/cleanup, or waits for SQL runtime validation.
- `data/case_sql_commands.yaml` is empty or marked `not_required` while any selected case still requires SQL setup, SQL cleanup, DB restore, or DB mock cleanup.
- A validator treats every case in `data/case_sql_commands.yaml` as a long-chain case, or compares the total SQL entry count with required flow count instead of partitioning long-chain flow SQL entries from ordinary SQL fixture entries.
- A case cannot be classified as main flow or branch flow from source evidence.
- Upstream marks a required chain scenario, but the execution-level cases cannot provide ordered steps, producer/consumer variable links, extraction rules, injection targets, chain assertions, cleanup boundaries, or a stable `flow_id`.
- SQL setup or cleanup is required but table structure, key relationship, command order, database connection, or required driver evidence is missing.
- The source asks for real execution but the environment, credentials, or base URL are absent and no generated configuration entrypoint exists. When configuration entrypoints exist, record the missing values under `live_execution_readiness` and continue script generation.
- Confirmed encrypted interfaces exist but the algorithm reference, key source, request payload scope, request serialization, request envelope, or response envelope is missing.
- Confirmed encrypted interfaces exist but `configs/shared_requester_crypto_adapter_status.yaml` is missing, blocked, failed, or records only placeholder implementation details.
- Interface encryption policy remains source-inferred only, contains `policy_required`, or contains unconfirmed `no_encrypt_candidate` / `requires_encryption_if_project_default_enabled` decisions needed for runnable scripts.

For cleanup closure, blocking runnable generation must not erase source-confirmed business candidates. Irreversible, one-way, asynchronous, manual-review, third-party, or environment-destructive scenarios may be emitted as `generated_non_live` or `manual_review_only` records with source reason and assertion/observation boundary, but they must not issue live API requests or be counted as live-executed cases.

Do not downgrade to sample scripts or placeholder assertions.

Database MCP evidence boundary:

- Upstream skills may use database MCP to collect database structure, field constraints, table relationships, ownership boundaries, and knowledge-graph evidence.
- This generator may consume MCP-derived facts only after they have been normalized into `数据模型.md`, `前置数据构造规则.md`, `execution_fact_sources.yaml`, or a source evidence index.
- Generated pytest projects must not contain MCP connection code, MCP query helpers, MCP result-file dependencies, or runtime instructions that require MCP. Database access in generated scripts must use pytest fixtures and `configs/database.yaml`.

Runtime and Apifox evidence boundary:

- Upstream stages may use a direct requester for user-requested runtime evidence collection, but only before executable-case generation; this generator consumes only the normalized facts already written into `执行级接口用例集.md`, `前置数据构造规则.md`, and `execution_fact_sources.yaml`.
- This generator must not call a direct requester, re-request live interfaces, read runtime secret files, or fill missing business codes, token rules, variables, assertions, or cleanup strategies from live traffic.
- Upstream stages may use Apifox MCP for optional contract cross-checking, saved-case examples, response-example reading, or manual synchronization planning.
- This generator may consume Apifox-derived facts only after they have been normalized into `前置数据构造规则.md`, `执行级接口用例集.md`, `execution_fact_sources.yaml`, or `apifox_evidence_index.yaml`.
- Missing Apifox environments, saved cases, or auth variables must not block script generation when required execution facts are confirmed by non-Apifox sources.
- Generated pytest projects must not contain Apifox MCP calls, Apifox environment lookups, saved-debug-case dependencies, or runtime instructions that require Apifox.

## 6. Output Schema

When blocked, create or update `api-test-framework/configs/generation_status.yaml`:

```yaml
stage: "api-test-framework-generator"
status: "blocked"
case_free: true
reason: "脚本生成门禁未通过"
source_files:
  execution_cases: "执行级接口用例集.md"
  precondition_rules: "前置数据构造规则.md"
  data_model: "数据模型.md"
missing_items:
  - "缺少测试环境 base_url 且未提供 configs/{env}.yaml、环境变量引用或 pytest --env 等运行时配置入口"
input_precheck_report: "configs/input_precheck_report.yaml"
target_run_scope: "all_generated_cases"
generated_candidate_case_count: 0
selected_case_count: 0
runnable_case_count: 0
blocked_real_run_case_count: 0
blocked_real_run_case_ids: []
cleanup_closure_stage:
  status: "blocked"
  closure_mode_counts: {}
  automation_decision_counts:
    runnable: 0
    safe_subset_only: 0
    generated_non_live: 0
    manual_review_only: 0
    blocked_live_execution: 0
  generated_non_live_case_ids: []
  manual_review_only_case_ids: []
next_stage_allowed: false
```

When generated or validated, write:

```yaml
stage: "api-test-framework-generator"
status: "validated"
case_free: false
source_files:
  execution_cases: "执行级接口用例集.md"
  precondition_rules: "前置数据构造规则.md"
  data_model: "数据模型.md"
generated_at: "YYYY-MM-DD HH:mm:ss"
input_precheck_report: "configs/input_precheck_report.yaml"
target_run_scope: "all_generated_cases"
case_count: 0
generated_candidate_case_count: 0
selected_case_count: 0
runnable_case_count: 0
blocked_real_run_case_count: 0
blocked_real_run_case_ids: []
executable_case_count: 0
e2e_flow_case_count: 0
collected_test_count: 0
flow_counts:
  main: 0
  branch: 0
  e2e: 0
coverage_traceability:
  status: "passed"
  executable_case_count: 0
  e2e_flow_case_count: 0
  design_case_count: 0
  coverage_object_count: 0
  coverage_rule_count: 0
  missing_executable_mappings: []
  missing_pytest_mappings: []
pytest_collection_mapping:
  status: "passed"
  executable_case_count: 0
  e2e_flow_case_count: 0
  collected_test_count: 0
  mappings:
    - executable_case_id: "EXE-TC-001"
      design_case_id: "TC-API-001"
      coverage_object_ids:
        - "API-001"
      coverage_rule_ids:
        - "RULE-API-001-SUCCESS"
      test_point_id: "TP-001"
      pytest_nodeid: "testcases/test_login.py::test_login_success_tc001"
    - flow_id: "recharge_apple_pay_flow"
      source_executable_case_ids:
        - "EXE-TC-014"
        - "EXE-TC-015"
        - "EXE-TC-016"
      pytest_nodeid: "testcases/test_flows.py::test_recharge_apple_pay_flow"
e2e_flow_mapping:
  status: "passed"
  flow_case_count: 0
  missing_flow_evidence: []
  mappings:
    - flow_id: "recharge_apple_pay_flow"
      title: "充值下单到支付验证端到端链路"
      story: "recharge"
      flow_type: "main"
      source_executable_case_ids:
        - "EXE-TC-014"
        - "EXE-TC-015"
        - "EXE-TC-016"
      variable_links:
        - producer_case_id: "EXE-TC-015"
          consumer_case_id: "EXE-TC-016"
          variable: "recharge_order_id"
          extract_path: "$.data.orderId"
          inject_target: "json.orderId"
      pytest_nodeid: "testcases/test_flows.py::test_recharge_apple_pay_flow"
chain_script_coverage:
  status: "passed"
  required_flow_count: 0
  generated_flow_count: 0
  required_flow_ids: []
  generated_flow_ids: []
  missing_required_flow_ids: []
  single_interface_only_flow_ids: []
sql_command_file: "data/case_sql_commands.yaml"
sql_case_count: 0
setup_cleanup_materialization:
  status: "passed"
  target_run_scope: "all_generated_cases"
  generated_candidate_case_count: 0
  selected_case_count: 0
  runnable_case_count: 0
  blocked_real_run_case_count: 0
  mutable_case_count: 0
  executable_cleanup_case_count: 0
  api_cleanup_case_count: 0
  sql_cleanup_case_count: 0
  excluded_safe_subset_only: []
  excluded_missing_cleanup_evidence: []
  cleanup_evidence_not_materialized: []
  missing_unified_before_after_cleanup_gate: []
sql_fixture_materialization:
  status: "passed"
  predicate_fields:
    - "sql_fixture_required"
    - "setup_cleanup_materialization"
    - "db_assertion_materialization"
    - "data/case_sql_commands.yaml cases"
  marker_validation: "passed"
  fixture_validation: "passed"
  lifecycle_validation: "passed"
  missing_case_id_markers: []
  missing_sql_command_entries: []
existing_state_closure:
  status: "passed"
  checked_case_count: 0
  closed_by_precheck_api: []
  closed_by_api_cleanup_or_restore: []
  closed_by_bounded_sql: []
  closed_by_isolated_account_or_snapshot: []
  generated_non_live_case_ids: []
  manual_review_only_case_ids: []
  blocked_case_ids: []
cleanup_closure_stage:
  status: "passed"
  closure_mode_counts: {}
  automation_decision_counts:
    runnable: 0
    safe_subset_only: 0
    generated_non_live: 0
    manual_review_only: 0
    blocked_live_execution: 0
  generated_non_live_case_ids: []
  manual_review_only_case_ids: []
transport_encryption:
  status: "plain_http"
  plaintext_flow_model: true
  confirmed_encrypted_interface_count: 0
  request_payload_scope: ""
  request_plaintext_serialization: ""
  request_envelope:
    ciphertext_field: ""
    body_shape: {}
  response_envelope:
    outer_json_plaintext: null
    ciphertext_field: ""
    decrypt_when: ""
    parse_decrypted_json: null
  blocked_missing_contract_items: []
api_modules:
  - "login_api.py"
test_modules:
  - "test_login.py"
  - "test_flows.py"
validation:
  input_precheck: "passed"
  e2e_flow_contract: "passed"
  split_integrity: "passed"
  dependencies: "passed"
  sql_generation_gate: "passed"
  sql_static_validation: "passed"
  sql_runtime_validation: "passed"
  syntax: "passed"
  collect_only: "passed"
next_stage_allowed: true
```

## 7. Mapping Rules

Map case fields to pytest+allure files:

| Source field | Generated location |
| --- | --- |
| Interface group/domain | `api/<group>_api.py`, `testcases/test_<group>.py`, `allure.feature` |
| Case title | `allure.title` |
| Priority P0/P1/P2 | `allure.severity` (`critical`, `normal`, `minor`) |
| Design case id | `configs/generation_status.yaml.coverage_traceability` and generated case data |
| Coverage object ids | `configs/generation_status.yaml.coverage_traceability` and generated case data |
| Coverage rule ids | `configs/generation_status.yaml.coverage_traceability` and generated case data |
| Test point id | `configs/generation_status.yaml.pytest_collection_mapping` |
| Main flow / branch flow | `@pytest.mark.main_flow` or `@pytest.mark.branch_flow`, `--flow` selector |
| Preconditions | `@pytest.mark.preconditions([...])` plus `case_data_manager` fixture |
| SQL preconditions | `data/case_sql_commands.yaml` setup list plus `case_sql_manager` fixture |
| SQL-driven case predicate | enabled `sql_fixture_required`, active SQL/DB `setup_cleanup_materialization`, active `db_assertion_materialization`, DB assertion marker, or matching case id in `data/case_sql_commands.yaml`; explicit non-SQL statuses do not activate the fixture, and all validators use this same predicate |
| Method/path | API wrapper method calling `HttpClient.request` |
| Query/body/header | generated YAML/Python data files and wrapper parameters |
| Expected status | `Assertor.status_code` |
| Response field assertions | `Assertor.json_path_equal` or explicit assertion from source |
| Extraction rule | `Extractor.extract_json_value` and `runtime_context` injection |
| E2E flow chain | Producer/consumer variable links across source executable cases map to `data/flow_cases.yaml` or `data/flow_cases.py`, `core/flow_runner.py`, `testcases/test_flows.py`, and `@pytest.mark.e2e_flow` |
| Cleanup rule | `@pytest.mark.cleanup([...])` plus `case_data_manager` fixture finalizer |
| SQL cleanup rule | `data/case_sql_commands.yaml` cleanup list plus `case_sql_manager` fixture finalizer |
| SQL runtime extract/final verify | `data/case_sql_commands.yaml` runtime_extract and final_verify lists plus `runtime_context` publication and finalizer verification |
| Token acquisition | `configs/{env}.yaml` auth section plus `auth_headers` / `authenticated_client` fixtures |
| Case id | `@pytest.mark.case_id("<source-case-id>")` for SQL command lookup |
| Pytest nodeid | `configs/generation_status.yaml.pytest_collection_mapping.mappings[].pytest_nodeid`, verified from pytest collection when available |
| Data model table/field evidence | `configs/input_precheck_report.yaml`, `data/case_sql_commands.yaml`, and SQL gate source evidence |

Name generated Python functions with source-bound case ids when possible, for example `test_login_success_tc001`. Keep names ASCII-safe and deterministic.

Normalize response assertion JSONPath inputs at the execution boundary. All response assertion surfaces, including `business_code_path`, `json_equals`, `required_fields`, `array_length_equals`, `string_min_lengths`, archive cases, and generated collection assertions, must accept both `$.foo.bar` and `foo.bar`; array paths such as `$.data.items[0].id` must remain valid. Do not make each assertion type implement a different path dialect.

## 8. Framework Rules

Use the template in `assets/api-test-framework-template/` for a fresh project.

Framework constraints:

- Do not generate executable code until input precheck passes.
- Apply `references/splitting-strategy.md` when file size or context limits require splitting. Split by complete interface capability and generate `configs/split_index.yaml` whenever splitting is used.
- Include explicit split ordering metadata in `configs/split_index.yaml`: `ordering.execution_order`, module `sequence`, `depends_on`, `run_after`, and `run_before`.
- Use `requests`, not another HTTP client.
- Use `pytest` fixtures and parametrization for test flow.
- Use `allure.step`, `allure.feature`, `allure.story`, `allure.title`, and `allure.severity`.
- Keep `core/auth_manager.py`, `core/client.py`, `core/transport_crypto.py`, `core/assertor.py`, `core/data_manager.py`, `core/extractor.py`, `core/dependency_check.py`, `core/sql_executor.py`, `core/sql_validator.py`, and `core/logger.py` generic.
- For encrypted projects, keep one shared requester path through `HttpClient` and one shared crypto adapter. Test data, flow data, assertions, and extracted runtime variables stay plaintext; ciphertext must appear only at the network boundary and redacted evidence attachments.
- Generate `configs/shared_requester_crypto_adapter_status.yaml` with `status: not_required|blocked|failed|passed_static|passed_live_smoke`. `passed_static` requires config-code alignment, dependency check, syntax/AST check, roundtrip or source-vector validation, and synthetic response decrypt where applicable. `passed_live_smoke` additionally requires a safe real encrypted request with complete plaintext request and decoded response evidence.
- For multi-account or multi-role suites, generate an account-context registry or pytest fixture keyed by `account_group_key` or session role. Case/flow data selects the group; the shared client switches auth context before each request. Do not place account secrets directly in case data, and do not generate per-case login/requester code unless the case is explicitly about login, token refresh, logout, session invalidation, or fresh-account isolation.
- Support `case_runtime_isolation` in case and flow data. `auth_isolation.reauth_before_case` refreshes only the auth context for a selected account group before the case/step, and requires executable dynamic auth configuration. `business_state_isolation` must be satisfied by cleanup, restore, isolated account, snapshot, or flow ordering; re-authentication must not be treated as cleanup or state restoration.
- Materialize runtime isolation in code, not only case metadata: ordinary cases initialize a fresh business scope, complete flows initialize one shared scope before their first step, and both preserve only the account-group auth/session registry. Explicit login steps publish source-bound extracts into that registry through the same helper used by ordinary and flow runners.
- Materialize API cleanup as teardown-safe execution. Cleanup starts after any setup attempt, continues independent rules after an error, retains ownership/snapshot boundaries, restores the previous request auth context, and reports cleanup errors without replacing the original test/setup failure.
- Keep encrypted-transport diagnostics bounded, recursively redacted, and configuration-driven. Capture pre-decryption metadata/body and decode-failure context before raising, retain policy-selected envelope fields, and never expose raw Authorization, Cookie, API key, token, identity, or secret-bearing exception content.
- Keep `requirements.txt` and `core/dependency_check.py` synchronized for `pytest`, `requests`, `PyYAML`, `allure-pytest`, and `SQLAlchemy` minimum versions. Add a source-bound database driver dependency when the upstream artifacts identify the database driver.
- Run `core/dependency_check.py` from `conftest.py` before importing request, YAML, and Allure-dependent framework modules.
- Provide `check_dependencies.py` so users can run dependency validation before pytest.
- Implement token acquisition through `auth_headers` and `authenticated_client` fixtures. Dynamic token acquisition must require `method`, `path`, `expected_status`, and `extract_path`.
- Implement per-test precondition data setup and post-test cleanup through `case_data_manager`; generated test functions that use setup or cleanup markers must include this fixture parameter.
- Treat `cleanup_refs` and evidence refs as audit links only. They do not satisfy runtime cleanup unless converted into executable marker rules or SQL command entries.
- Before generating live write-side-effect cases, close existing-state risks from historical rows, relationship records, pending-review records, idempotency keys, quota state, or uniqueness constraints. Use a source-bound precheck API, precise API cleanup/restore, bounded SQL pre-clean/restore, isolated account/snapshot, or mark the case `generated_non_live` / `manual_review_only`.
- Use API setup/cleanup rules in this schema: `type`, `name`, `method`, `path`, `headers`, `params`, `json`, `expected_status`, and optional `extract`.
- Implement SQL setup and cleanup through `case_sql_manager`; generated test functions that use SQL commands must include this fixture parameter and `@pytest.mark.case_id`.
- Detect SQL-driven tests through the shared predicate `enabled sql_fixture_required OR active SQL/DB setup_cleanup_materialization OR active db_assertion_materialization OR DB assertion marker OR matching case id in data/case_sql_commands.yaml`; explicit non-SQL statuses such as `not_required`、`no_cleanup_required` and API-only materialization do not activate SQL fixtures. Do not require upstream artifacts to duplicate all flags when one confirmed SQL materialization signal already exists.
- Generate `data/case_sql_commands.yaml` with `sql_generation_gate`, `cases.<case_id>.setup[]`, and `cases.<case_id>.cleanup[]` entries. Each command must include `name`, `source_evidence`, `target_tables`, `ownership.keys`, `sql`, `expected_effect.affected_rows`, and optional `params`.
- Support the full SQL lifecycle when evidence requires it: `setup`, `runtime_extract`, `cleanup`, and `final_verify`. Runtime extracts must publish named values into `runtime_context`; final verification must run after cleanup/restore and fail fast on mismatch.
- Keep SQL lifecycle variables stage-correct. Case-level `params` and `setup.params` are resolved before the business request, so they may reference only environment/runtime variables available at setup time, auth/account bootstrap context, or values produced by prior SQL setup in the same stage. Values produced by the business request, response extraction, `runtime_extract`, or post-request DB queries, such as order ids, feedback ids, report ids, message ids, and task-context ids, must appear only in post-request `runtime_extract`, `cleanup`, or `final_verify` commands. A setup command that references a post-request runtime id is a generator defect.
- Execute post-request SQL lifecycle stages once per case and stage key. When a test can be entered through ordinary parameterization, optional async, or a flow runner, the generated fixture/runtime state must record completed SQL stages so `runtime_extract`, long waits, cleanup, and final verification do not run twice for the same intended case/stage unless the command declares a safe reentry/no-op policy.
- Treat `data/case_sql_commands.yaml` as a shared fixture ledger. SQL entries may belong to required E2E flow steps or ordinary single-interface cases; validators must classify them from `data/flow_cases.yaml` / `data/flow_cases.py` step case ids and ordinary case metadata before applying long-chain-only checks.
- Generate `data/case_sql_validation.yaml` to record static validation and runtime validation results.
- Keep `sql_generation_gate.status` as `blocked` unless all SQL generation gate checks pass.
- Use named SQL parameters such as `:user_id`; values may be literal source-bound values or `${runtime_context_variable}`.
- Generate runtime markers from table structure, not from a global string pattern. Before binding a marker to a SQL column, verify the target column exists, its type and max length allow the value, and the value matches historical-shape evidence. For `varchar`/`char` columns, generated marker length must be within the declared column length after placeholder resolution. Use short business-scoped markers for narrow fields; never let technical markers overflow columns or become page-visible/request-visible values unless the case is an explicit invalid-value branch.
- Compare SQL expected values against the persisted representation, not the convenient request literal. For request lists/objects, JSON wrappers, enum codes, date/time values, generated markers, and display fields, cite the source/runtime evidence that proves the stored database shape before writing `expected_<field>`.
- Verify derived or aggregate fields through source formulas, before/after snapshots, or current-run extraction. Do not use fixed historical constants for mutable counters, balances, scores, rates, task progress, latest-time fields, or other aggregate/derived values unless the row is a fixed test-owned configuration row with source proof.
- Keep verification queries and expected fields one-to-one. `expected_<field>` keys under `expected_effect` must correspond to a column returned by the same `verification_query`. If multiple post-cleanup facts must be verified, materialize them as separate `final_verify` entries or extend the generated executor and template intentionally; do not add ad-hoc keys such as `active_pair_verification_query` that the executor does not run.
- Keep cleanup boundary and final verification boundary aligned. If cleanup deletes by current-run id, trace id, order id, message id, or another ownership key, the verification query must verify that same ownership key is gone. If the expected result is pair/entity-level absence, the setup phase must first materialize pair/entity-level isolation or precise pre-clean and record that wider boundary; otherwise the case must not assert pair/entity-level zero rows after deleting only the current-run row.
- Do not hardcode dynamic persistence identifiers that can change at runtime, such as `conversation_id`, `subscription_order_id`, `service_feedback_id`, `report_id`, `message_id`, or task ids, unless the upstream source proves they are fixed configuration rows owned by the test. Dynamic ids must be extracted from the response or scoped DB query and stored in `runtime_context` before downstream cleanup or assertions consume them.
- Generate producer-aware failure-path metadata for post-request SQL. A cleanup command that consumes an API-response or post-request DB variable declares `side_effect_class: primary|conditional|prestate_restore`; optional/derived commands may use `skip_if_missing_runtime_vars`, primary commands require a request-known fallback contract, and prestate restores must not carry unrelated late variables. Command params containing unresolved runtime placeholders that are not bound by that command SQL are generator defects.
- For mutating requests, treat transport disconnects as ambiguous outcomes. If normal cleanup depends on a response id, generate `failure_path_cleanup` with `transport_outcome: ambiguous`, request-known ownership variables, fallback runtime-extract command ids, always-run restore command ids, and same-boundary final-verify command ids. Fallback lookup must execute without the response id and may use a bounded settle/polling window when delayed visibility is source/runtime supported; otherwise classify the case non-live/manual.
- Generated SQL execution must attempt independent cleanup/restore commands after a sibling cleanup failure and must still attempt `final_verify`. Aggregate lifecycle errors with their stage and command ids after all safe finalizers have run. Do not generate a blanket missing-variable rule that skips every post-request stage.
- Order SQL setup by knowledge-graph dependency direction from parent entities to child entities. Order cleanup in reverse dependency direction.
- Reject SQL that may affect non-test data: DDL, multi-statement SQL, unbounded DELETE/UPDATE, `WHERE 1=1`, `OR 1=1`, full wildcard cleanup, missing ownership keys, missing target table evidence, or target tables outside `sql_generation_gate.allowed_tables`.
- Validate SQL syntax by parsing SQLAlchemy bind parameters from each statement and matching them exactly with `params`.
- Validate SQL logic by checking operation type, target table whitelist, ownership-bound WHERE conditions, graph-derived order, and `expected_effect.affected_rows`.
- Validate runtime accuracy with `check_sql_commands.py --env=<env> --runtime`; it must execute setup and cleanup SQL in one transaction, verify affected row counts, then roll back.
- Use `${variable_name}` to inject values previously stored in `runtime_context`; missing variables must fail fast.
- Support YAML data files and Python pure-data files for interface definitions, ordinary case data, and E2E flow data. Python data files must only export literal constants such as `INTERFACES`, `CASES`, `FLOWS`, and optional `SCHEMA_VERSION`; they must not contain imports, functions, classes, loops, comprehensions, runtime calls, random values, or environment reads.
- Generate E2E flow suites for every upstream required business chain. The flow suite must use explicit files (`data/flow_cases.yaml` or `data/flow_cases.py`, `core/flow_runner.py`, `testcases/test_flows.py`) and must not rely on pytest ordering between single-interface tests.
- Keep generated E2E pytest entrypoints short and readable: import `allure` and `pytest`, import `run_flow`, add `@allure.feature("e2e")`, source-bound story/title, `@pytest.mark.e2e_flow`, the flow selector marker, and call `run_flow("<flow_id>", authenticated_client, env_config, runtime_context)`.
- `data/flow_cases.yaml` or `data/flow_cases.py` must show ordered steps, source executable case ids, request overrides, extraction rules, injection targets, cleanup policy, and source evidence. This file is the canonical place to understand upstream/downstream dependencies.
- Every required upstream `flow_id` must appear exactly once in `data/flow_cases.yaml` or `data/flow_cases.py`; required chains must not be represented only by single-interface tests.
- `core/flow_runner.py` must resolve `${variable_name}` recursively from `runtime_context`, environment config, or process environment, assert status/response fields, extract JSONPath or regex variables, and fail fast on unresolved placeholders. Do not invent fallback values.
- `configs/generation_status.yaml.chain_script_coverage.status` must be `passed`; `missing_required_flow_ids` and `single_interface_only_flow_ids` must be empty before downstream readiness.
- Count readiness with `collected_test_count == executable_case_count + e2e_flow_case_count` whenever E2E flows are generated.
- Mark every generated test as exactly one of `main_flow` or `branch_flow`.
- Put interface-specific paths and wrapper methods in `api/`.
- Put concrete test data in `data/*.yaml` or pure-data `data/*.py` files.
- Put environment values in `configs/{dev,test,prod}.yaml`.
- Put runtime reports under `reports/`.
- Do not put explanatory project Markdown in the generated framework.

Generated E2E flow tests should use this visible shape:

```python
import allure
import pytest

from core.flow_runner import run_flow


@allure.feature("e2e")
@allure.story("recharge")
@allure.title("充值下单到支付验证端到端链路")
@pytest.mark.e2e_flow
@pytest.mark.main_flow
def test_recharge_apple_pay_flow(authenticated_client, env_config, runtime_context):
    run_flow("recharge_apple_pay_flow", authenticated_client, env_config, runtime_context)
```

## 9. Validation

Run these validations when applicable:

```bash
python3 api-test-framework/check_dependencies.py
python3 api-test-framework/check_sql_commands.py --env=dev
python3 api-test-framework/check_sql_commands.py --env=dev --runtime
python3 -m py_compile api-test-framework/core/*.py api-test-framework/utils/*.py api-test-framework/api/*.py api-test-framework/testcases/*.py
python3 -m pytest api-test-framework --collect-only --env=dev --flow=all
```

If dependencies are missing, report the missing dependency and the command that failed. Do not install packages unless the user asks or approves dependency installation.

## 10. Downstream Boundary

Permit downstream execution, CI integration, or report publication only when all conditions are true:

- `configs/input_precheck_report.yaml` has `status: "passed"` and every input precheck item is `passed`.
- If files are split, `configs/split_index.yaml` has `status: "passed"` and every source case appears in exactly one split unit.
- If files are split, `configs/split_index.yaml` has `ordering.status: "passed"`, every split unit appears exactly once in `ordering.execution_order`, `sequence` values match that order, and no dependency cycle exists.
- `configs/generation_status.yaml` has `status: "validated"` and `next_stage_allowed: true`.
- `configs/generation_status.yaml` has `coverage_traceability.status: "passed"` and `pytest_collection_mapping.status: "passed"`.
- `configs/generation_status.yaml` proves `collected_test_count == executable_case_count + e2e_flow_case_count`.
- If upstream `required_chain_flows.yaml` contains required flows, `configs/generation_status.yaml.chain_script_coverage.status` is `passed`, `generated_flow_count == required_flow_count`, and `missing_required_flow_ids` / `single_interface_only_flow_ids` are empty.
- When `e2e_flow_case_count` is greater than 0, `configs/generation_status.yaml` has `e2e_flow_mapping.status: "passed"` and every generated flow maps to one collected pytest nodeid.
- At least one source-bound test module exists under `testcases/`.
- Every generated single-interface test has a traceable case id from `执行级接口用例集.md`.
- Every generated single-interface test has a traceable design case id, coverage object id, coverage rule id, and test point id from `执行级接口用例集.md`.
- Every generated E2E flow test has a traceable flow id and ordered source executable case ids from `执行级接口用例集.md` and `前置数据构造规则.md`.
- Every executable case maps to exactly one pytest nodeid unless it is explicitly marked non-runnable; non-runnable cases block coverage-response readiness.
- Every inherited coverage rule maps to at least one pytest nodeid.
- Every assertion and extraction rule maps to explicit source evidence.
- Generated request shapes, archive entries, and generated collection artifacts preserve source-visible list/object/map/scalar distinctions and do not introduce stringified payloads except at confirmed transport or persistence boundaries.
- Every generated test has one flow selector marker: `main_flow` or `branch_flow`; E2E flow tests additionally have `e2e_flow`.
- Setup, token, cleanup, and SQL fixtures are generated only from executable source-bound rules.
- `setup_cleanup_materialization.status` is `passed`, with empty missing/excluded lists for the selected live executable denominator.
- `sql_fixture_materialization.status` is `passed`; every SQL-driven case has matching case data predicate, `case_id` marker, fixture attachment, SQL command entry, and required lifecycle commands.
- `existing_state_closure.status` is `passed`; live write-side-effect cases with uniqueness, idempotency, pending-state, relationship-state, quota, or historical-row risk prove a clean starting state or are explicitly non-live/manual.
- `cleanup_closure_stage.status` is `passed`; any `generated_non_live` or `manual_review_only` cases are explicit and not counted as live-executed cases.
- When `target_run_scope=all_generated_cases` and the result claims full live execution, `generated_candidate_case_count == selected_case_count == runnable_case_count`, `blocked_real_run_case_count == 0`, `excluded_safe_subset_only` is empty, and `generated_non_live_case_ids` / `manual_review_only_case_ids` are empty.
- SQL-driven cases have matching `case_id` markers and entries in `data/case_sql_commands.yaml`.
- SQL denominator checks partition entries by generated flow-step case ids versus ordinary case ids; `chain_script_coverage` and long-chain extraction checks apply only to the flow-step SQL bucket.
- SQL command generation is backed by confirmed table structures and knowledge-graph relationships.
- SQL generation gate passed and every SQL command is limited to test-owned data.
- SQL expected values and derived assertions are backed by persisted-shape evidence, source formulas, before/after snapshots, or current-run extraction instead of guessed serialized strings or historical aggregate constants.
- SQL static validation and runtime validation passed.
- Runtime dependency check passed.
- Live-only runtime dependencies such as DB drivers or network tunnels may remain pending only in `live_execution_readiness` when the script-level dependency check, syntax validation, pytest collection, and SQL evidence gates have passed and the config entrypoint is present.
- Syntax validation and pytest collection both passed.

If any condition fails, return the framework path and blocked items, but do not run real interface execution.

## 11. SQL Command Generation

Generate `data/case_sql_commands.yaml` only when the data model artifact and upstream artifacts provide confirmed table-structure and knowledge-graph evidence.

Required SQL evidence per table:

- Table name and business meaning.
- Primary key and unique key columns.
- Required columns and non-null rules.
- Status fields, enum values, and default values.
- Foreign-key or knowledge-graph dependency edges.
- Columns needed by API request parameters, response assertions, state assertions, setup, and cleanup.

Required SQL evidence per case:

- Source case id.
- Setup objective and affected entities.
- Cleanup objective and affected entities.
- Runtime extraction objective, published variable name, and consuming request/cleanup reference when later steps need DB-derived values.
- Final verification objective when cleanup, restore, or business state must be proven after the case.
- Concrete source-bound values or runtime variables.
- Parent-child insert order and child-parent cleanup order.

Use this YAML schema:

```yaml
sql_generation_gate:
  status: "passed"
  passed: true
  reason: "SQL 生成准出门禁通过"
  source_files:
    - "执行级接口用例集.md"
    - "前置数据构造规则.md"
    - "数据模型.md"
  quality_checks:
    table_structure_verified: true
    knowledge_graph_verified: true
    ownership_boundary_verified: true
    cleanup_scope_verified: true
    id_cleanup_verified: true
    insert_exit_gate_verified: true
    delete_exit_gate_verified: true
    api_insufficiency_verified: true
    dangerous_sql_rejected: true
    sql_syntax_verified: true
    sql_logic_verified: true
    historical_shape_reference_verified: true
    runtime_validation_verified: true
  allowed_tables:
    - "user_account"
  validation_report: "data/case_sql_validation.yaml"
cases:
  TC001:
    setup:
      - name: "准备主账户"
        source_evidence: "前置数据构造规则.md#TC001"
        target_tables:
          - "user_account"
        cleanup_identity:
          field: "id"
          value_ref: "params.id"
        ownership:
          keys:
            - "id"
        sql_exit_gate:
          status: "passed"
          passed: true
          checks:
            target_table_verified: true
            ownership_boundary_verified: true
            expected_effect_verified: true
            insert_identity_verified: true
            insert_columns_verified: true
        sql: "INSERT INTO user_account (id, status) VALUES (:id, :status)"
        params:
          id: "source-bound-id"
          status: "ACTIVE"
        expected_effect:
          affected_rows: 1
    cleanup:
      - name: "清理主账户"
        source_evidence: "前置数据构造规则.md#TC001"
        target_tables:
          - "user_account"
        cleanup_identity:
          field: "id"
          value_ref: "params.id"
        ownership:
          keys:
            - "id"
        sql_exit_gate:
          status: "passed"
          passed: true
          checks:
            target_table_verified: true
            ownership_boundary_verified: true
            expected_effect_verified: true
            delete_identity_verified: true
            delete_scope_verified: true
        sql: "DELETE FROM user_account WHERE id = :id"
        params:
          id: "source-bound-id"
        expected_effect:
          affected_rows: 1
```

Block generation when SQL values are conceptual, table relationships are ambiguous, cleanup order is unknown, or the target database connection/driver is not source-bound.

### SQL Generation Gate Checks

Set `sql_generation_gate.status: "passed"` only when every check below passes:

- `table_structure_verified`: every referenced table and column exists in the data model evidence.
- `knowledge_graph_verified`: setup order and cleanup order follow graph dependencies.
- `ownership_boundary_verified`: each row can be identified as test-owned by source-bound keys.
- `cleanup_scope_verified`: cleanup affects only rows generated or explicitly reserved for the current case.
- `id_cleanup_verified`: every generated database row declares `cleanup_identity.field: "id"` and every cleanup command uses `params.id`.
- `insert_exit_gate_verified`: every INSERT command has a passed command-level `sql_exit_gate`, writes `id` through `:id`, affects exactly one row, and is runtime-checked before/after insertion.
- `delete_exit_gate_verified`: every DELETE command has a passed command-level `sql_exit_gate`, uses `WHERE id = :id`, affects exactly one row, and is runtime-checked before/after deletion.
- `api_insufficiency_verified`: every SQL command records why API construction or cleanup cannot satisfy the required state.
- `dangerous_sql_rejected`: DDL, broad DML, multi-statement SQL, wildcard cleanup, and missing WHERE ownership are absent.
- `sql_syntax_verified`: statement text is parseable by SQLAlchemy text binding and every named parameter exactly matches `params`.
- `sql_logic_verified`: operation type, target table, ownership keys, graph order, and expected row count match the case intent.
- `historical_shape_reference_verified`: every SQL setup INSERT/UPDATE command includes passed bounded historical-shape evidence or equivalent normalized DB evidence for field formats, enum/status values, JSON/null/time conventions, page-visible value quality, and role relationship direction.
- `runtime_validation_verified`: `check_sql_commands.py --env=<env> --runtime` has executed setup and cleanup in a rollback transaction and verified row counts.

Additional command-level rules:

- Use only approved tables listed in `sql_generation_gate.allowed_tables`.
- Use `INSERT` or bounded `UPDATE` for setup.
- Use bounded `DELETE` or bounded `UPDATE` for cleanup.
- Require INSERT/DELETE to declare a passed command-level `sql_exit_gate`; missing or failed command gates block generation and execution.
- Require INSERT to use `INSERT ... (id, ...) VALUES (:id, ...)` and declare `expected_effect.affected_rows: 1`.
- Require DELETE to use `WHERE id = :id`, operate on a single approved table, and declare `expected_effect.affected_rows: 1`.
- Require DELETE/UPDATE to include a `WHERE` clause using at least one `ownership.keys` parameter.
- Require every SQL command to declare `expected_effect.affected_rows`; runtime validation and real execution must fail when the actual affected row count differs.
- When `expected_effect` contains field-value assertions, require persisted-shape evidence for values transformed by application code, ORM/MyBatis mappings, JSON serialization, type conversion, defaults, or trimming. Do not compare request-side complex values directly to guessed stored text.
- When `expected_effect` asserts aggregate or derived values, require a source formula, before/after snapshot, current-run extraction, or follow-up query scoped to the current ownership key. Do not hardcode mutable historical counters, scores, balances, rates, progress values, or latest-time fields.
- When a SQL lifecycle includes `runtime_extract`, waits, cleanup, or final verification that can be reached by more than one fixture/runner path, require a completed-stage guard or equivalent idempotence evidence.
- Require every SQL setup command to declare `historical_shape_reference.status: "passed"` with `source_ref`, `sampled_table`, positive `sample_count`, non-empty `verified_fields`, and `privacy_status: "sampled_shape_only_redacted"`.
- Never generate cleanup based only on business status, date ranges, names, fuzzy matching, or environment-wide criteria.
- Never generate SQL to delete production-like shared data, reference data, enum/config tables, user accounts not created for the test, or rows without a test-owned identifier.
