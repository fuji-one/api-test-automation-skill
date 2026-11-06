# 失败分支、完成提示与最终验证

## 目录

- [读取时机](#读取时机)
- [最终回复原则](#最终回复原则)
- [规则正文](#规则正文)
- [User-Facing Completion Notice](#user-facing-completion-notice)
- [Failure Branches](#failure-branches)
- [Artifact Templates](#artifact-templates)
- [Downstream Boundary](#downstream-boundary)
- [Structured Validation](#structured-validation)
- [来源](#来源)

## 读取时机

阶段结束、阻塞、失败、用户最终回复、运行 `validate_pipeline_outputs.py` 前读取。

## 最终回复原则

如果 `api-test-framework/` 未生成，最终回复必须以“未生成最终自动化脚本”开头，并说明停止状态、停止阶段、缺失输入和最高完成阶段。总体验证通过只表示当前状态符合门禁，不等于全链路已完成。

## 规则正文

## User-Facing Completion Notice

At the end of every run, make the user-facing final response impossible to confuse with a full pipeline success:

- If `api-test-framework/` was not generated, lead the final response with `未生成最终自动化脚本` and name the stopping status, stopping stage, missing inputs, and the highest completed stage.
- If the pipeline ends with any status other than `PASSED`, explicitly say that validation only proves the current blocked or partial-output state satisfies the pipeline gate, not that the full automation chain has completed.
- If execution-level cases or scripts were skipped, explicitly list the absent directories such as `05-executable-interface-case-set/` and `api-test-framework/`.
- Do not use phrases such as `全链路通过`、`跑完全链路`、`已生成自动化脚本`、or `校验通过` without immediately qualifying whether final scripts exist.
- When the target depth is `framework` and final scripts are blocked, ask the user to confirm whether they want to provide execution inputs, use database/Apifox MCP evidence, or narrow the target to `design`/`executable`.

## Failure Branches

- Missing document entry and source entry: write only `00_流水线执行报告.md` with `BLOCKED_MISSING_ENTRY_INPUT`.
- Source/full pipeline target missing data model: run valid source/design stages when their own gates pass, then perform the database MCP-first normalization check before executable filling. Only after MCP is unavailable/unreadable, identity cannot be confirmed, graph/setup/cleanup evidence cannot be generated, or source-DB alignment cannot pass may the run stop with `BLOCKED_NEED_EXECUTION_INPUT` or `FAILED_EXECUTION_READINESS`; record the attempted MCP connector/tool/environment and exact blocker.
- Full pipeline target missing execution readiness input: run valid entry/design stages when their own gates pass, materialize `00-inputs/runtime_execution_config.template.yaml`, `00-inputs/前置执行配置待填写.md`, and `runtime_execution_config.missing_fields.yaml` when fields are known. Missing concrete runtime values stop executable filling or script generation only when the framework cannot expose a source-bound configuration entrypoint. If generated scripts can expose `configs/{env}.yaml`, `configs/database.yaml`, environment-variable references, and pytest `--env`, continue script generation and record the missing values under `live_execution_readiness.status: pending_runtime_config`; do not treat them as `next_stage_allowed` blockers. Do not mark already passed design-level cases, coverage matrices, business long-chain design denominators, handoff artifacts, or generated scripts as failed only because live runtime values are not filled yet.
- Database MCP identity or source-DB alignment cannot be confirmed: stop before executable filling only after the required DB MCP check has been attempted. Missing MCP/identity confirmation is `BLOCKED_NEED_EXECUTION_INPUT`; concrete table/column/type/constraint conflicts are `FAILED_EXECUTION_READINESS`.
- Entry conflict: stop before case generation and list conflicting method/path/field/status/error-code evidence.
- Entry quality or test-point split failed: stop before case generation with `FAILED_ENTRY_QUALITY_GATE`; list failed input quality checks, missing coverage objects, missing test point mappings, non-100% coverage figures, or failed source fact quality items.
- Business scenario mapping missing or not traceable: stop before case generation with `BLOCKED_NEED_BUSINESS_SCENARIO_MAPPING`; list missing scenario IDs, missing business domains, missing executing roles, missing source refs, low-confidence mappings, missing related test point IDs, or missing coverage rule IDs.
- Business long-chain design denominator missing or fake: before stopping, try to split URL-prefix/API-module/controller-package buckets into real business chains using actor, business object, lifecycle/state change, verification endpoint, and source refs. Keep valid two-interface business scenarios as design-level short-chain or state-transition cases, but do not count them in the business long-chain denominator unless they meet the 3-interface or 5-step threshold. If no valid split remains, stop at design-case generation with `FAILED_DESIGN_CASE_GATE`; list missing `business_long_chain_cases.yaml`, missing `业务长链路设计清单.md`, missing P0 design case mapping, non-100% design coverage, or candidates rejected because they are still buckets rather than real business scenarios.
- Candidate reclassification too coarse: if `chain_flow_candidate_audit.yaml` classifies non-required scenario candidates in bulk as `excluded_readonly` or uses generic reasons such as `已纳入设计级覆盖` without proving they are pure read-only, stop before stage 2 release or downstream handoff. Reclassify them into required flow, design-only long chain, short-chain/state-transition, single-interface mutation, single-interface read-only, external/callback, or evidence-missing buckets, then regenerate the responsible producer outputs from source facts.
- Chain flow denominator missing: if the selected entry has passed but root-level `required_chain_flows.yaml` or `chain_flow_candidate_audit.yaml` is missing, malformed, not passed, has unclassified candidates, or lacks complete closed-loop evidence for any required flow, stop with `BLOCKED_NEED_CHAIN_FLOW_DENOMINATOR` before stage 2. Existing long-chain products are not repair targets for this blocker; regenerate the denominator from source evidence.
- Chain flow evidence missing: if any `required_chain_flows.yaml` flow lacks execution-level ordered steps, extraction/injection rules, chain assertions, setup, or cleanup boundaries, stop with `BLOCKED_NEED_CHAIN_FLOW_EVIDENCE` before script generation. Coverage-point report rows and `business_scenario_map.yaml` may help reviewers spot candidates, but they must not create the downstream hard denominator by themselves.
- Long-chain missing value input pending: if `long_chain_missing_value_fields.yaml.status=pending_user_input` or `open_required_count>0`, stop before script generation with `BLOCKED_NEED_EXECUTION_INPUT`; ask the user to fill `长链路缺失码值补充清单.md`, then rerun execution-level filling so values are copied into executable cases and fact sources.
- Long-chain coverage missing or mixed with unit coverage: stop at the current producer stage with `FAILED_DESIGN_CASE_GATE`, `FAILED_EXECUTION_READINESS`, or `FAILED_SCRIPT_GENERATION_GATE` according to stage. List the missing `chain_scenario`、`chain_function`、`chain_process` denominator, covered count, missing list, or missing `long_chain_only` declaration; do not pass by relying on single-interface coverage.
- Case generation gate failed: do not run executable-case filling.
- Handoff cannot be losslessly extracted: ask for repaired `case_list.yaml` and `执行报告.md`, or rerun a gated case-list stage.
- Execution input missing: keep execution-case output case-free according to `$executable-interface-case-set`.
- Script generation blocked: do not create runnable pytest files.
- Downstream gate cannot consume upstream output: regenerate the upstream producer output and rerun downstream validation. If the same producer-consumer gate fails after 3 attempts, write `retry_history.yaml`, mark `00_流水线执行报告.md` as `BLOCKED_RETRY_EXHAUSTED`, and do not continue with stale or partially compatible files.

## Artifact Templates

`00_流水线执行报告.md` must use this minimum structure:

```markdown
# API 自动化流水线执行报告

## 执行摘要
- 目标深度：
- 当前状态：
- 停止阶段：
- 最高完成阶段：

## 阶段状态
| 阶段 | 状态 | 产物 | 阻塞项 |
|---|---|---|---|

## 缺失输入
- 无

## 修复建议
- 无

## 重试历史
- 无
```

## Downstream Boundary

This skill may create a runnable `api-test-framework/` only after `$executable-interface-case-set` is `PASSED`. It may not invent request values, response values, assertions, accounts, token extraction, setup data, cleanup SQL, Apifox responses, environment URLs, database schema facts, or table graph facts. Database MCP schema and graph facts must be normalized and source-aligned before downstream use.

Runtime request values must already be normalized into `04-runtime-evidence/` and then into execution-level artifacts before script generation. Downstream stages must not use the Runtime Request Value Principle to re-request interfaces, override contracts, or backfill missing execution facts outside the runtime evidence and executable-case filling stages.

## Structured Validation

Run:

```bash
python3 <skill_dir>/scripts/validate_pipeline_outputs.py output/api-automation-pipeline
```

Validation checks:

- `00_流水线执行报告.md` exists and has a recognized target depth and stage status.
- If `retry_history.yaml` exists or the stage status is `BLOCKED_RETRY_EXHAUSTED`, it must have schema version 1, `max_attempts: 3`, explicit retry key, gate id, producer/consumer stages, attempt records, regenerated output paths, gate evidence, and a final blocker.
- At least one entry output exists.
- Each executed entry has its required three Markdown files.
- Document entry proves input-file quality review, test point analysis/splitting, coverage-object traceability, and explicit 100% coverage release before any stage 2 output exists.
- Document entry sidecars prove `status=passed`, `next_stage_allowed=true`, object/test-point/rule coverage counts are 100%, and missing ID lists are empty before any stage 2 output exists.
- Selected entry includes `business_scenario_map.yaml` and `业务场景链路清单.md` before any stage 2 output exists; the map is `status=passed`, `next_stage_allowed=true`, has non-empty `scenario_items`, no blockers, Chinese `business_domain`, Chinese `executing_role`, Chinese `business_description` that includes the executing role, source refs, related interface chains, related test point IDs, and related coverage rule IDs.
- Before any stage 2 output exists, root-level `required_chain_flows.yaml` and `chain_flow_candidate_audit.yaml` must exist after a passed entry release. Existing `flow_generation_required=true`, `chain_type=e2e_flow_candidate`, interface-count, or step-count signals in `business_scenario_map.yaml` are candidate evidence only; they do not define the authoritative long-chain denominator.
- `required_chain_flows.yaml` must be `status=passed`, `next_stage_allowed=true`, have `required_chain_flow_count` equal to the unique required `flow_id` count, and every required flow must include pre-action, observable change, verification, link keys, ordered steps, evidence refs, and `status: required`.
- `chain_flow_candidate_audit.yaml` must be `status=passed`, `next_stage_allowed=true`, classify every candidate as `included`、`design_long_chain_only`、`design_short_chain_state_transition`、`single_interface_mutation`、`single_interface_readonly`、`external_or_callback`、`excluded_missing_verification`、`excluded_missing_change_evidence`、`excluded_missing_link_key` or `excluded_readonly`, and keep `unclassified_candidate_flows=[]`. Non-required business scenarios must not be bulk-classified as `excluded_readonly`; every non-included candidate must have a `downstream_target` and a reason tied to its actual evidence gap or business shape.
- When both document and source entries exist, `chain_flow_alignment.yaml` must classify flow differences as `doc_only`、`source_only`、`both_step_diff` or `both_consistent` without silently dropping evidence-complete flows.
- Source entry quality report is readable and must not be `FAILED` before source-visible facts are used as the design source.
- Source entry artifact manifest includes `source_api_business_scenario_map` and `source_api_business_scenario_doc` before source-visible facts are used as the design source.
- Source entry sidecars use `stage: source_api_facts`, `source_*` denominator fields, denominator totals greater than 0, empty `missing_source_*` lists, and source-type `coverage_items` plus mapped upstream/downstream records.
- When both document and source entries exist, document and source method/path facts must align; conflicts block release as `FAILED_ENTRY_ALIGNMENT_GATE`.
- `case_list.yaml` and `04_接口测试用例清单.md` are present before handoff. When `case_list.yaml.status=passed`, every `cases` item has non-placeholder `case_id`、`design_case_id`、`test_point_ids`、`coverage_object_ids`、`coverage_rule_ids`、`method`、`path`、`status_codes`、`priority`、`assertion_points`.
- `03-interface-testcase-generation/测试覆盖点报告.md` is present before stage 2 release, starts with `覆盖点摘要`, states coverage rate and calculation method, lists or explicitly clears long-chain focus points, contains the eleven required columns including `业务域` and `业务场景`, has at least one mapped row when design cases passed, uses Chinese descriptions in the required review fields, uses `p0/p1/p2`, does not contain unresolved placeholders such as `待确认`、`未知`、`TBD`, and is treated as a human-review artifact rather than a downstream hard dependency.
- Handoff files, including authoritative `case_list.yaml`, are present before executable-case filling.
- Handoff may include `测试覆盖点报告.md` copied from stage 2 as a human-review reference; executable-case filling must not require this report.
- Handoff includes `required_chain_flows.yaml`, `chain_flow_candidate_audit.yaml`, `business_scenario_map.yaml`, and `业务场景链路清单.md` copied from the selected entry/root denominator before executable-case filling.
- Every required flow from `required_chain_flows.yaml` is represented in design-level chain cases, execution-level chain evidence, and `api-test-framework/configs/generation_status.yaml.chain_script_coverage` before framework release; long-chain rows in `测试覆盖点报告.md` and `business_scenario_map.yaml` may be used for review/candidate discovery only.
- Stage 2 and execution-level `coverage_matrix.yaml` must not use single-interface or unit-style cases to satisfy long-chain coverage. The long-chain coverage fields are a separate coverage family and must remain valid even if normal case coverage is already 100%.
- Handoff normalized design and contract files are present before executable-case filling.
- Handoff source has passing quality conclusion, 100% coverage evidence, no unresolved blocker, and explicit 100% release conclusion.
- Every executed `stage_status.yaml` includes `schema_version`、`stage`、`status`、`next_stage_allowed` and `blocking_issues`; non-legacy sidecars also include `input_paths`、`output_paths`、`gate_checks`. Native `$pre-doc-analysis-pipeline` sidecars may use `source_files`、`stage_results`、`output_files`.
- Every downstream `coverage_matrix.yaml` includes `schema_version`、`stage`、`coverage_summary` plus stage-specific top-level counts; passed denominator totals are greater than 0; non-legacy sidecars also include `coverage_items`、`missing_items`、`upstream_downstream_mappings`; each denominator item has exactly one matching `coverage_items.coverage_id` and one mapped upstream/downstream record. Native `$pre-doc-analysis-pipeline` sidecars may use `coverage_objects`.
- Interface testcase generation sidecars prove `status=passed`, `next_stage_allowed=true`, test-point/main-flow/contract-rule/status-code/P0/P1 coverage counts are 100%, and missing ID lists are empty before handoff.
- When `required_chain_flows.yaml` contains required flows, interface testcase generation sidecars also prove long-chain scenario/function/process coverage counts are independently 100%, record `generated_design_chain_case_count == required_chain_flow_count`, and keep `missing_required_flow_ids=[]`.
- Target depth controls required downstream outputs: `design` stops at handoff, `executable` requires execution-level files, and `framework` requires `api-test-framework/`.
- If `00-inputs/database_mcp_evidence_index.yaml` or `00-inputs/source_db_alignment.yaml` exists, the database MCP evidence index and source-DB alignment sidecar must be readable, `status=passed`, conflict/missing/blocking lists empty, relationship/cleanup checks passed, and `00-inputs/数据模型.md` present. If source-entry executable/framework depth lacks a provided data model and no database MCP sidecar exists, the run report must prove DB MCP was unavailable/unreadable or intentionally not authorized before blocking.
- If the run blocks because execution configuration is missing or incomplete, `00-inputs/runtime_execution_config.template.yaml` and `00-inputs/前置执行配置待填写.md` must exist; when required missing fields are known, `00-inputs/runtime_execution_config.missing_fields.yaml` must list them.
- If `04-runtime-evidence-plan/` exists, `runtime_risk_audit.yaml`, `runtime_request_plan.skeleton.yaml`, `db_before_after_probe_plan.yaml`, and `runtime_blocker_candidates.yaml` must exist, use `schema_version=1`, classify every candidate with source refs and reason codes, avoid project-specific hardcoded values, and ensure only request-allowed items can be moved into the executable `runtime_request_plan.yaml`.
- If `required_chain_flows.yaml` contains required flows and `04-runtime-evidence-plan/` exists, the risk audit and request-plan skeleton must reference every required `flow_id` and every ordered flow step, including steps that are blocked, manual, sandbox/mock, or callback-provided. A plan that covers only a subset of convenient interfaces is not sufficient for requester-backed long-chain completion.
- If `04-runtime-evidence/` exists, `runtime_stage_status.yaml`, `runtime_evidence.yaml`, and `runtime_value_catalog.yaml` must exist, be UTF-8, use `schema_version=1`, have legal status values, keep conflict lists empty for passed/partial evidence, and contain no plaintext password、token、Authorization、Cookie or equivalent secrets. If `runtime_stage_status.yaml.continuation_queue` or optional `runtime_evidence_queue.yaml` exists, every item must use `queue_state` with one of `pending/requested/evidenced/retryable/skipped_recoverable/blocked_final/excluded`; nested item-level `status` fields are invalid.
- If `04-runtime-evidence/` exists and its values are used as later request inputs or expected downstream responses, `runtime_evidence.yaml.dependency_derivations` and `runtime_value_catalog.yaml.flow_value_links` must record producer step, consumer step, field paths, value source ref, inference reason, cross-check refs, source status, and usability. Same-name field copying without a recorded business dependency is not valid evidence.
- If runtime evidence candidates, runtime value catalogs, supplemental request results, or replay evidence are used to generate scripts, `api-test-framework/configs/runtime_evidence_script_mapping_audit.yaml` must exist and `generation_status.yaml.runtime_evidence_script_materialization.status` must be `passed` before broad pytest execution or product-defect confirmation. The audit must prove generated plaintext request fields, role/session variables, expected HTTP status, expected business code/message, and per-step evidence ids match the source candidate exactly. A mismatch is `FAILED_RUNTIME_EVIDENCE_SCRIPT_MATERIALIZATION` and must be treated as a generator materialization issue, not a product defect.
- Execution-level files are present before script generation.
- Execution-level stage sidecars prove executable-case coverage inheritance counts are 100% and missing ID lists are empty.
- When `required_chain_flows.yaml` contains required flows, execution-level stage sidecars also prove long-chain scenario/function/process coverage counts are independently 100%, record `generated_executable_chain_case_count == required_chain_flow_count`, and keep `missing_required_flow_ids=[]`.
- If `05-executable-interface-case-set/long_chain_missing_value_fields.yaml` exists, it must use `schema_version=1` and have `status=not_required|filled` with `open_required_count=0` before script generation. If it has `status=pending_user_input|blocked` or any open required item, `api-test-framework/` must be absent and the pipeline must stop at `BLOCKED_NEED_EXECUTION_INPUT`.
- `execution_fact_sources.yaml` exists before script generation and records required human inputs, source-bound token/data/variable/assertion/cleanup facts, seeded values, external dependency values, missing facts, conflicts, and blockers; when passed, `runtime_execution_config`、`environment_reference` and `authentication_account` must be `provided`, every required fact type must have at least one `confirmed` source, and every required `source_ref` must be non-empty. Environment fields are mandatory means the environment alias, test-environment declaration, and generated configuration entrypoint must exist; concrete base URLs, account secrets, DB URLs, drivers, or tunnels may be runtime-provided through `configs/{env}.yaml`, `configs/database.yaml`, environment-variable references, and pytest `--env`, then recorded under `live_execution_readiness.status: pending_runtime_config` instead of blocking script generation. Seeded values consumed by execution cases must be confirmed and filled into the corresponding request/assertion/DB/cleanup field as concrete values or executable variable references. If any data or cleanup fact uses API/DB setup, `seed_scope_guard` must be confirmed and must prove that seeded scope does not replace 普通请求值、链路返参值、外部依赖值、token/验证码/设备/分页/运行标识字段。若 `environment_reference.is_test_environment=false`, DB before/after, cleanup, rollback, or status recovery facts require `db_authorization.non_test_reauthorization_status=provided`. When data or cleanup facts use `data_model`/database/SQL evidence, `relationship_graph` and `ownership_key` fact types are also required. When a fact uses `source_type: live_request_evidence`, the referenced `runtime_evidence.yaml#evidence_id` or `runtime_value_catalog.yaml#value_id` must exist, be confirmed, and be usable for execution cases. When a fact uses `source_type: external_sandbox_evidence`, the sandbox/mock/callback evidence must be explicit; local DB seed evidence must not substitute for the external response value. Passed execution facts must also include closure evidence for request inputs, business state, and session/auth policy; unresolved required business fields, state setup/cleanup gaps, pre-login token injection, unresolved auth placeholders, or cross-role token/userId/session mismatch must block or exclude the affected case from the runnable denominator.
- If `execution_fact_sources.yaml` marks any flow as `account_specific_chain` or uses `specific_account_required` / `required_account_role` / `required_account_business_state` 等价字段, a confirmed `login_entry_rule` fact with valid `source_ref` is mandatory before the stage can pass.
- `apifox_evidence_index.yaml` exists when executable-case filling depends on Apifox MCP, classifies evidence as project structure / interface contract / saved case example / response example, and records conflict priority.
- Execution-level cases preserve `覆盖对象ID`、`覆盖规则ID`、`设计级用例ID`、`追溯测试点`.
- If `api-test-framework/` exists, it has the expected project skeleton.
- If `api-test-framework/` exists, `configs/input_precheck_report.yaml` and `configs/generation_status.yaml` exist, and `generation_status.yaml` records `coverage_traceability`、`pytest_collection_mapping`、`pytest_nodeid`.
- If `api-test-framework/` exists, `configs/generation_status.yaml.execution_fact_closure` exists or an equivalent validation section proves request-input closure, business-state closure, and session closure passed for the runnable denominator. It must report zero unresolved main-flow business fields, zero stateful cases without executable setup/verify/cleanup, zero pre-login steps with token injection, zero unresolved auth placeholders, and zero cross-role identity mismatches before runnable success is claimed.
- If `api-test-framework/` exists and generated runnable cases use dynamic auth, `configs/generation_status.yaml.runtime_usability.auth_bootstrap_materialization` or an equivalent machine-readable section must prove ordinary API cases authenticate by account group before business steps, explicit login cases are not double-bootstrapped, pre-login auth requests do not carry stale business tokens, account-specific flows keep visible first-step login/auth, and auth secrets are redacted. Root validation must inspect the generated fixture/registry and flow first-step login shape; prose-only notes are not sufficient evidence.
- If `api-test-framework/` exists, `接口案例.md` exists and `generation_status.yaml.final_case_archive.status=passed`; its archive case and flow counts match the same executable/script denominator, and it contains plaintext business request/response models with secrets redacted.
- If `api-test-framework/` exists, `generation_status.yaml.setup_cleanup_materialization.status` must be `passed` before runnable success, and setup/cleanup evidence must be available from `configs/setup_cleanup_materialization.yaml`, `data/setup_cleanup_materialization.yaml`, or an equivalent machine-readable `generation_status.yaml.setup_cleanup_materialization` object. Mutable cases with only cleanup refs or DB before/after refs must be excluded or block script generation. Validators must not require one fixed ledger path when an equivalent ledger is present, but they must reject prose-only setup/cleanup notes.
- If runtime failure triage produces product-defect output, `缺陷列表.md` must exist as Markdown; confirmed defects must include real scenario, complete plaintext request, complete plaintext response, and DB table/field changes when persistence changed. Items without complete response or DB evidence must stay in candidate sections.
- If `api-test-framework/data/flow_cases.yaml` or `api-test-framework/data/flow_cases.py` marks a flow as account-specific, the first flow step must be a login/auth step and must record token/account-context extraction rules before any business step.
- When `required_chain_flows.yaml` contains required flows, `generation_status.yaml.chain_script_coverage` records `coverage_denominator: long_chain_only`, `generated_pytest_flow_count == required_chain_flow_count`, `missing_required_flow_ids=[]`, required flow IDs, and independent 100% coverage for chain scenarios, chain functions, and chain processes.


## 来源

本文件从 `SKILL.md` 原主契约拆分而来；完整历史契约保存在 `references/full-contract.md`。
