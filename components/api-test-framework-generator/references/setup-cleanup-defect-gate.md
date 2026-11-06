# Setup Cleanup And Defect Gate

## 目录

- Core Principles
- Risk-Tiered Cleanup Closure
- Denominator Classification
- Materialization Requirements
- SQL Runtime Preflight Compatibility
- Generated Framework Gate
- Runtime Evidence Retention
- Defect List Rules


Use this reference when generating or reviewing executable API automation scripts that may touch persistent data, and when producing a defect list from runtime evidence.

## Core Principles

- `cleanup_refs`、`cleanup_id`、`source_ref`、`db_before_after` files, or narrative cleanup strategies are evidence, not executable cleanup.
- A case is runnable only when every required setup and cleanup action is materialized as a fixture-executed API action or bounded SQL action.
- `data/case_sql_commands.yaml` is a shared SQL fixture ledger for ordinary cases and flow-step cases; setup/cleanup gates must validate each SQL-driven case without treating the whole file as a long-chain denominator.
- The executable denominator is the set of cases that can run repeatedly without contaminating the test environment. Do not keep unsafe cases in the denominator just to preserve a larger case count.
- A live case or flow that contains a write-side-effect interface defaults to cleanup-required. No-cleanup is an auditable exemption, not the default for mutating behavior.
- Target run scope controls exclusion semantics. In `all_generated_cases`, every generated candidate remains in scope and any unsafe case blocks real execution. In `safe_subset`, exclusions are allowed only when explicitly requested and must be listed with reasons.
- Runtime evidence can support defect triage only when it records the real request, the decoded plaintext response, and DB before/after evidence when persistence changes.
- Positive write-side-effect cases must also close their starting business state. If an existing row, relationship, pending review, idempotency key, quota, subscription/order/message/evaluation state, or uniqueness constraint can change the expected main-path result, the generated case needs a precheck or precise pre-clean before the request, not only a post-test cleanup.

## Risk-Tiered Cleanup Closure

Do not apply one cleanup proof to every case. Classify each candidate with:

- `closure_mode`: `no_cleanup_required`, `api_cleanup`, `sql_cleanup`, `same_interface_restore`, `isolated_account`, `environment_snapshot`, `manual_review_only`, or `blocked_missing_evidence`.
- `evidence_strength`: `source_confirmed`, `runtime_no_delta`, `db_before_after`, `cleanup_after_verified`, `sandbox_isolated`, or `business_exception_accepted`.
- `automation_decision`: `runnable`, `safe_subset_only`, `generated_non_live`, `manual_review_only`, or `blocked_live_execution`.
- `cleanup_required`: true for write-side-effect live cases unless a source/runtime exemption is recorded.
- `cleanup_exemption_reason`: required when `cleanup_required=false` for a mutating or state-changing candidate.

DB before/after evidence is required for local persistent mutation unless stronger source/runtime evidence proves no persistent side effect or a materialized containment strategy exists. It is not a blanket requirement for source-confirmed read-only cases, no-op validation cases, runtime no-delta cases, sandbox/mock-isolated dependencies, or explicit business exceptions that are generated only as non-live/manual-review cases.

Valid business scenarios must not be dropped only because cleanup cannot yet be automated. If an irreversible, one-way, asynchronous, manual-review, third-party, or environment-destructive case is source-confirmed but cannot be safely restored, record it as `generated_non_live` or `manual_review_only`, keep its evidence and assertion/observation boundary, and exclude it from live execution. In `all_generated_cases`, such a case blocks the claim that every generated case was live-executed; it does not erase the candidate from the ledger.

## Denominator Classification

Classify every candidate before generating pytest. First set `target_run_scope` to `all_generated_cases` for full-suite execution requests, or `safe_subset` only for an explicitly requested safe subset:

| Classification | Rule | Generation decision |
| --- | --- | --- |
| `runnable_with_materialized_cleanup` | Mutable case has executable API/SQL cleanup, id/ownership boundary, and fixture attachment | Generate pytest and keep in denominator |
| `cleanup_evidence_not_materialized` | Cleanup evidence exists only as refs or DB before/after files | Do not mark runnable; materialize cleanup first; block in `all_generated_cases` |
| `blocked_missing_cleanup_evidence` | Case mutates or destroys state but no cleanup evidence exists | Block in `all_generated_cases`; exclude only in an explicit `safe_subset` with reason |
| `missing_unified_before_after_cleanup_gate` | Evidence says DB before/after/cleanup gate is still needed | Block until upstream closes the gate |
| `precondition_only_needs_materialization` | Setup evidence exists but fixture action is missing | Materialize setup and paired cleanup before running |
| `existing_state_needs_materialization` | Positive write case depends on absence or shape of prior state, but no executable precheck/pre-clean/isolated state exists | Block live execution until state closure is materialized |
| `readonly_or_no_cleanup_required` | Source/runtime evidence proves no persistent side effect | Generate only with executable response assertions |
| `business_exception_non_live` | Source confirms the scenario is valid but irreversible, async, manual-review, third-party, or unsafe to restore automatically | Keep as `generated_non_live` or `manual_review_only`; exclude from live denominator; block `all_generated_cases` live-execution claims |
| `isolated_account_or_snapshot_required` | Case can run only with isolated account, sandbox, or environment snapshot evidence | Generate runnable only after containment is materialized; otherwise keep non-live or block live execution |

Risk signals that require setup/cleanup review include mutation, destructive state, DB mock, DB seed, restore, audit, send, upload, external callback, account balance, order/payment, relationship write, logical delete, and status transition.

Risk signals that require existing-state closure include uniqueness checks, duplicate-submit branches, pending-review or unprocessed state, relationship direction, mutual exclusion, self-relation guards, balance/quota/task progress preconditions, and source-visible business errors that mean "already exists", "already submitted", "already reported", "already subscribed", "already evaluated", "relationship exists", or equivalent.

## Materialization Requirements

For no-cleanup acceptance, require source-confirmed read-only behavior, runtime no-delta evidence, sandbox/mock isolation evidence, failed-request no-side-effect proof, or non-live/manual-review classification plus executable response/assertion boundary. Do not require DB before/after for these cases unless local persistence may change.

For write-side-effect live cases, cleanup must be materialized unless an exemption is recorded. The cleanup action must use the current-run ownership key, such as response ID, request ID, message/order/conversation/evaluation/audit ID, idempotency key, trace ID, or a run-unique marker. Broad cleanup by user ID, tenant ID, status, time range, or other non-unique predicates is forbidden unless the whole target entity was created by the current run and isolated ownership is proven.

For conditional side effects, do not require a mutation row count of exactly one unless source or runtime evidence proves the side-effect row is always produced for the same request variant. Conditional side effects include notification messages, helper conversation rows, cache or queue artifacts, async callback rows, derived linkage rows, and similar optional records. Their cleanup may allow zero affected rows only when the command uses a current-run ownership key and a final verification query proves no matching residue remains. This rule does not weaken cleanup for the primary persisted business object created or updated by the case.

### Post-request variable dependency gate

Apply `post_request_variable_dependency_gate` only to SQL-driven cases whose post-request lifecycle consumes values produced by an API response or a post-request DB query. Classify affected cleanup commands as `primary`, `conditional`, or `prestate_restore` through `side_effect_class`:

- `conditional` commands may declare `skip_if_missing_runtime_vars` for optional or derived records. Every skipped boundary still requires scoped `final_verify` evidence proving no current-run residue remains.
- `primary` commands may declare a missing-variable skip only when the case also declares `failure_path_cleanup` with a request-known fallback lookup, an always-available ownership boundary, and same-boundary final verification. Skipping must not be the only primary cleanup strategy.
- `prestate_restore` commands restore setup snapshots or known target state and must remain executable when response-produced ids are absent. Do not place unrelated late variables in their params, even when the SQL does not bind those params.

Each command-level skip list must contain valid runtime variable names and only variables actually consumed by that command. Do not generate a case-level rule that skips every post-request stage, because it can suppress independent snapshot restoration and final verification. Teardown must attempt all independent cleanup/restore commands and final verification even when runtime extraction or another cleanup command fails, then report the lifecycle errors together without hiding which stage caused them.

### Ambiguous write outcome cleanup gate

Apply `ambiguous_write_outcome_cleanup_gate` to repeatable live mutating requests when normal cleanup depends on an API-response id. Timeout, TLS/SSL EOF, connection reset, proxy disconnect, and equivalent transport failures mean `transport_outcome: ambiguous`; they do not prove that the service rolled back.

Require one of these failure-path strategies:

- A request-known business id, idempotency key, trace id, or current-run unique marker can locate the primary object without the response.
- A known target id plus before snapshot can restore the modified state without a response id.
- An isolated account/entity or environment snapshot contains the entire mutation and has executable restore evidence.
- The case is classified `generated_non_live` or `manual_review_only`.

When the request-known lookup strategy is used, record this machine-readable case contract:

```yaml
failure_path_cleanup:
  transport_outcome: ambiguous
  request_ownership_vars: [run_marker]
  fallback_runtime_extract_command_ids: [SQL-EXTRACT-CREATED-ID-BY-MARKER]
  always_run_restore_command_ids: [SQL-RESTORE-PRESTATE]
  final_verify_command_ids: [SQL-VERIFY-RUN-MARKER-NO-RESIDUE]
```

Fallback extraction must use only request/setup/auth variables available before the response, may return no row when the service did not commit, and must publish the same ownership id consumed by primary cleanup when a row exists. Use a bounded settle or polling window when source/runtime evidence shows the write may become visible after the transport disconnect. Final verification must use the same request-known ownership boundary and must not depend solely on the missing response id.

For existing-state closure, require one of these source-bound strategies before live release:

- A precheck API/detail/list/status request proves the relevant row or relationship is absent or in the required state.
- A precise API cleanup or restore action removes only the conflicting state by response id, request id, relationship id, marker, or exact actor/counterparty ownership key.
- A bounded SQL pre-clean or restore action uses the current-run or explicitly test-owned ownership key and records setup/cleanup/final verification in `data/case_sql_commands.yaml`.
- An isolated account, isolated target entity, or environment snapshot proves old state cannot collide with the run.
- The case is preserved as `generated_non_live` or `manual_review_only` with the missing state-closure evidence listed.

If existing-state closure relies on DB access and the runner lacks DB URL, driver, or tunnel, classify the affected case ids under live runtime readiness (`pending_runtime_db_env` or equivalent). Do not classify the downstream business error as a product defect until the state closure has actually run.

For business-exception acceptance, require source reason, affected environment boundary, assertion or observation boundary, owner/reviewer note when available, and `automation_decision: generated_non_live` or `manual_review_only`. These cases may be generated into the ledger/archive, but they must not be counted as live-executed cases.

For API setup or cleanup, require:

- Source evidence for method, path, request body/query/path/header fields, expected status, and response assertion.
- `cleanup_identity` with an id source such as `json.id`, `params.id`, `path.id`, `runtime_context.id`, or a precise ownership key.
- An API cleanup that consumes an ID emitted only by a successful request declares `skip_if_missing_runtime_vars`. Missing variables may skip only the explicitly conditional rule; available-identity cleanup rules still run and their failures are aggregated.
- A pytest marker or case-data rule consumed by `case_data_manager`.
- Cleanup finalizer execution after the test, including failure paths.

For SQL setup or cleanup, require:

- Source evidence that API construction or API cleanup cannot satisfy the state.
- Data model table/field/key evidence and knowledge-graph setup/cleanup order.
- `seed_scope_guard` for setup values and `cleanup_identity.field: "id"` for generated rows.
- `historical_shape_reference` for SQL setup values, proving that same-table/same-business-state historical shape evidence or equivalent normalized DB evidence was used to confirm field formats, enum/status values, JSON/null/time conventions, page-visible value quality, and role relationship direction before INSERT/UPDATE.
- Stage-correct variable placement. SQL `setup` runs before the business request; therefore setup params and case-level params must not reference ids or values that are produced by the request, response extraction, runtime DB extraction, or cleanup stage. Put post-request ids in `runtime_extract`/`cleanup`/`final_verify`, and keep setup values limited to pre-existing runtime variables, auth/account context, source-bound constants, or same-stage setup outputs.
- Table-structure-constrained values. Before inserting or updating a value, verify the target column exists and the generated value respects type, nullability, enum/status domain, max length, JSON/time format, and historical-shape evidence. Runtime marker templates must be shortened or moved when the target column cannot hold them.
- Persisted-value assertion shape. When SQL assertions compare values created by the request, expected values must match the actual stored representation after source-confirmed serialization, JSON wrapping, type conversion, defaults, trimming, or date/time formatting. Lists, objects, maps, enums, markers, and display values cannot be compared as guessed strings.
- Derived-value assertion shape. Aggregate or derived values such as counters, balances, scores, rates, task progress, and latest-time fields must be asserted through source formulas, before/after snapshots, current-run extraction, or scoped follow-up queries. Historical values are not repeatable expectations unless they belong to fixed test-owned configuration data.
- Verifiable assertion shape. A cleanup command's `verification_query` may assert only fields returned by that query. Multiple verification concerns must be separate `final_verify` entries with their own query and expected fields, unless the generated executor explicitly supports a documented multi-query schema.
- Conditional side-effect cleanup shape. Optional downstream records must be declared as conditional with source/runtime evidence, use `affected_rows_min: 0` or an equivalent conditional expectation, and include scoped final verification. Do not use this shape for the primary business row, destructive cleanup, balance/order/payment records, or any record that the source contract guarantees to be created.
- Failure-path variable shape. Post-request commands that consume API-response or DB-extracted variables must declare `side_effect_class`; command-level missing-variable skips are allowed only under the producer-aware rules above. Primary cleanup with a late variable requires a request-known fallback contract, while `prestate_restore` commands must not consume unrelated late variables.
- Ambiguous transport cleanup shape. A repeatable live mutating case whose cleanup normally consumes a response id must provide `failure_path_cleanup` with a request-known ownership boundary, fallback lookup or snapshot restore, independent restore commands, and same-boundary final verification, or remain non-live/manual.
- Boundary-aligned cleanup verification. Current-run row cleanup can verify current-run row absence; pair/entity/global absence requires matching setup isolation or pre-clean of that same wider boundary. Do not assert a wider boundary after deleting only one current-run id.
- Bounded SQL in `data/case_sql_commands.yaml`, with `sql_generation_gate.status: "passed"`.
- Static SQL validation and, when DB config is available, rollback-based runtime validation.
- A pytest `case_id` marker and `case_sql_manager` fixture attachment. SQL-driven status must be derived from a shared predicate: enabled `sql_fixture_required`、active SQL/DB `setup_cleanup_materialization`、active `db_assertion_materialization`、DB assertion materialization, or a matching `data/case_sql_commands.yaml` case id. Explicit `not_required`、`no_cleanup_required` and API-only strategies remain non-SQL statuses.

If selected cases need SQL setup/cleanup, `data/case_sql_commands.yaml` must not be empty and must not use `sql_generation_gate.status: "not_required"`.

## SQL Runtime Preflight Compatibility

Apply these checks independently and only when the generated framework exposes the relevant capability. This section refines the existing setup/cleanup, variable-resolution, runtime-usability, and validation-scope rules; it must not report the same blocker twice.

- `phase_isolation` applies when SQL has post-request/final-verification stages and the framework offers DB-connected SQL preflight. Reuse the stage-correct variable and post-request dependency evidence above. Add only proof that SQL-only preflight does not require or publish an API-produced row; it may validate SELECT safety, binds, and executability. Permit strict pre-request assertions when their phase and source evidence explicitly prove they are preconditions.
- `runtime_context_parity` applies when SQL runtime preflight consumes environment, deterministic, login-derived, or prior-step variables. Require the same case-level initializer and resolver used by pytest, plus representative no-network resolution for every generated environment. Do not require this check when preflight consumes only source-bound literals.
- `selection_closure` applies when a standard runner combines explicit case/flow selection with SQL runtime preflight. Require selected-set equality across pytest collection, flow-to-SQL lifecycle mapping, SQL preflight, pytest execution, and reporting. Do not require selectors in frameworks that do not expose selective execution.
- `dynamic_baseline_source` applies when a DB expectation depends on mutable state, time, counters, amounts, async results, or current rows. Reuse the existing persisted-value and derived-value assertion evidence above; do not create a second blocker. Use source invariants or before-snapshot/after-relation/restore comparison instead of frozen `None`, zero, timestamp, counter, amount, or historical live value.
- `validation_evidence_scope` applies when explicit subset selection and SQL runtime preflight are both present. Record subset and full-suite evidence separately; a subset pass must not set the full-suite runtime gate or overwrite stronger full-suite evidence.

Pure API projects, basic setup/cleanup projects, fixture-managed snapshots, and runners without explicit selectors remain valid when the corresponding checks are not applicable. Architecture-specific implementations may differ as long as they satisfy the same behavioral properties.

Create `configs/sql_runtime_lifecycle_gate.yaml` only when at least one check applies. Under `capabilities`, record boolean `sql_runtime_stages`、`sql_runtime_preflight`、`preflight_consumes_runtime_variables`、`explicit_subset_selection` and `dynamic_database_expectations`; record each check as `passed` with non-empty source/test evidence or `not_applicable` with a reason, plus `schema_version: 1`、top-level `status: passed|not_applicable` and an empty `blocking_issues` list. Unknown extension fields are allowed. Validate it with `scripts/validate_sql_runtime_lifecycle_gate.py`.

Minimum specialized tests:

- A post-request query returns zero rows before its producing request: SQL preflight passes while live extraction remains strict.
- A stale matching row exists before the request: preflight does not publish it into runtime or cleanup context.
- A deterministic variable such as `nowIso` resolves through the shared initializer in every generated environment.
- Selecting one ordinary case or one flow preflights only its mapped SQL lifecycle.
- A subset pass leaves the full-suite runtime status unchanged.
- A mutable DB expectation uses source invariant or snapshot/delta evidence instead of a historical literal.
- Pure API, basic setup/cleanup, and fixture-snapshot architectures remain non-blocked when advanced capabilities are absent.

## Generated Framework Gate

Before `next_stage_allowed: true`, verify:

- Every generated live mutable case has executable setup/cleanup, same-interface restore, isolated containment, or an explicit no-cleanup rule.
- Every generated live write-side-effect case has `cleanup_required=true` with materialized cleanup, or a non-empty source/runtime `cleanup_exemption_reason` that makes it read-only/no-delta/sandbox-isolated/failed-no-effect/non-live.
- Every candidate records `closure_mode`, `evidence_strength`, and `automation_decision`; DB before/after is required only for local persistent mutation without stronger no-side-effect or containment evidence.
- Every setup/cleanup marker is attached to a test that includes the matching fixture.
- Every SQL-driven case has a `case_id` marker, a matching command entry when commands are required, and the `case_sql_manager` fixture. Validators must reject drift where case data declares SQL materialization but pytest parameters do not attach the marker/fixture.
- SQL lifecycle stages that can be reached through more than one generated runner path have a completed-stage guard or equivalent idempotence evidence, so `runtime_extract`, delayed waits, cleanup, and final verification do not execute twice for the same intended case/stage.
- Every positive uniqueness/idempotency/relationship write case has existing-state closure through precheck, precise pre-clean, isolated state, or non-live/manual classification.
- SQL-driven cases are partitioned into flow-step SQL and ordinary-case SQL before denominator comparison; total entries in `case_sql_commands.yaml` must not be compared to required flow count.
- `case_sql_commands.yaml` is empty only when all selected cases are confirmed no-SQL.
- `generation_status.yaml` records generated candidate, selected denominator, runnable, blocked, and excluded counts by reason.
- When `target_run_scope=all_generated_cases`, generated candidate count, selected denominator count, and runnable count are equal, and all excluded/missing lists are empty.
- `runtime_usability.status` is not `passed` if mutable cases lack materialized cleanup.

Recommended status shape:

```yaml
setup_cleanup_materialization:
  status: passed | blocked
  target_run_scope: all_generated_cases | safe_subset
  generated_candidate_case_count: 0
  selected_case_count: 0
  runnable_case_count: 0
  blocked_real_run_case_count: 0
  mutable_case_count: 0
  write_side_effect_case_count: 0
  executable_cleanup_case_count: 0
  sql_cleanup_case_count: 0
  api_cleanup_case_count: 0
  cleanup_required_case_count: 0
  cleanup_exemption_case_count: 0
  cleanup_closure_stage:
    status: passed | partial | blocked
    closure_mode_counts: {}
    automation_decision_counts:
      runnable: 0
      safe_subset_only: 0
      generated_non_live: 0
      manual_review_only: 0
      blocked_live_execution: 0
    generated_non_live_case_ids: []
    manual_review_only_case_ids: []
  excluded_safe_subset_only: []
  excluded_missing_cleanup_evidence: []
  cleanup_evidence_not_materialized: []
  missing_unified_before_after_cleanup_gate: []
  cleanup_exemption_missing_reason: []
  existing_state_closure:
    status: passed | blocked | not_required
    precheck_case_ids: []
    preclean_case_ids: []
    isolated_state_case_ids: []
    blocked_case_ids: []
  blockers: []
```

## Runtime Evidence Retention

When runtime evidence is collected upstream or used to diagnose failures, retain:

- Real scenario title and source case id.
- Method, path, module, role, and base-url alias.
- Complete plaintext business request after placeholder resolution and before encryption. Keep raw secrets redacted with stable placeholders.
- Complete decoded plaintext response after decryption, including HTTP status, business code, message, and `data` object or raw body.
- DB before/after/cleanup evidence with database, table, row id, changed fields, old values, new values, and cleanup result when persistence changes.
- Evidence ids and source refs for every request, response, assertion, and DB check.

If only status/shape summaries are retained, the item can support triage but cannot become a confirmed defect.

## Defect List Rules

Generate confirmed defects in Markdown, separate from generated executable cases. Use a candidate section for incomplete evidence.

A confirmed defect must include:

- Defect id and real business scenario.
- Source case id or flow/step id.
- Interface method and path.
- Complete plaintext request, with secret values replaced only by approved stable placeholders.
- Complete plaintext response, not only status or shape summary.
- Expected result and actual result.
- DB table/field changes when persistence changed: database, table, id/ownership key, changed fields, before value, after value, and cleanup result.
- Evidence refs for request, response, assertion, and DB before/after.

Do not confirm a defect when:

- A later correct precondition, role, auth, or crypto-context rerun succeeds.
- The response body was not retained.
- The request body contains unresolved placeholders or guessed values.
- DB side effects are suspected but before/after evidence is missing.
- The failure may be caused by stale generated code, stale report artifacts, missing dependency, wrong run path, session contamination, or unclosed setup data.

Classify these as candidates or generator/runtime-state issues, not confirmed product defects.
