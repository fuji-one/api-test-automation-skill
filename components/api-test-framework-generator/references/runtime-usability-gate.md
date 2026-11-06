# Runtime Usability Gate

## 目录

- General Principle
- Gate Checklist
- Failure Classification
- Minimum Status Recording

Use this reference before declaring generated pytest/allure scripts runnable, and whenever a user reports that generated scripts cannot run. The goal is to prevent syntactically generated projects from failing immediately at runtime because of stale paths, invalid extraction rules, incomplete auth/crypto contracts, or obsolete run artifacts.

## General Principle

Generation success is not runtime usability. A framework may be structurally complete and still fail before the first business assertion. Treat these failures as script-generation quality issues until proven to be environment-only.

Script-generation readiness and live-execution readiness are separate. Missing concrete runtime values such as secrets, DB URLs, local drivers, or network tunnels are environment-only only when the framework exposes a clear runtime configuration entrypoint through `configs/{env}.yaml`, `configs/database.yaml`, environment-variable references, and pytest `--env`. In that case, record `live_execution_readiness.status: pending_runtime_config`; do not use the missing runtime values as the reason to block generated scripts or `next_stage_allowed`.

## Gate Checklist

- **Flow response assertion binding gate**: apply only when a generated flow step changes an identity、primary-key、role or tenant request dimension relative to its source case. In that scope, every source business assertion category must be explicitly rebound in `expected_overrides`, or the step must declare `assertion_binding.status: passed`, `mode: same_request_variant_evidence|response_contract_rebound`, and non-empty source evidence. Stable envelope assertions such as HTTP status、business code、`$.code`、`$.success` may remain inherited. Pagination-only、sorting-only and other non-identity request overrides do not trigger this gate.
- **Bounded write-followup observation gate**: apply only when a flow producer creates/extracts a current-run value and a later collection assertion consumes that value. The consumer must narrow the request by current-run id or source-bound unique marker, use a detail-by-id request, use a scoped DB assertion, or declare evidence-backed bounded pagination with explicit ownership fields. Page number、page size、sort or common status alone do not establish ownership scope. Read-only flows and writes without a collection follow-up do not trigger this gate.
- Run `scripts/validate_flow_semantics_gate.py <framework-root> --output <framework-root>/configs/flow_runtime_semantics_gate.json` after generated case and flow data are final. Keep the two subchecks separate from SQL lifecycle validation; `not_required` is a valid non-blocking result when the corresponding capability is absent.
- **Mutable runtime business dependency gate**: consume the upstream full-case audit for dictionary/configuration participation、eligibility、quota/limit and external runtime state. Require executable API/SQL/fixture/isolated-state precheck only for audited applicable cases; allow a full-scan `not_required` result for all others. Preserve upstream dependency predicates and automation decisions in case data, require restore when precheck changes state, and run `scripts/validate_runtime_business_dependency_gate.py <framework-root>`. This gate does not replace payload validation、response binding、write-followup observation or SQL lifecycle checks.

- **Validation scope gate**: before patching or rerunning an existing generated framework, declare whether the run is `same_chain_patch`, `selected_subset`, or `all_generated_cases`. For `same_chain_patch`, identify the target `flow_id` or `case_id` set, its producer/consumer steps, setup/cleanup rules, role contexts, and shared utility files touched by the fix. Validate that same chain plus any changed shared utilities; do not rewrite unrelated chain data, expectations, cleanup, or assertions to satisfy a local failure. Use full-suite gates only when `target_run_scope=all_generated_cases` or the user asks for broad execution/readiness.
- **Actual run path**: identify the directory the user is executing, not only the canonical output directory. If a copy exists, patch or synchronize both the canonical output and the actual run path. Confirm imported modules with `module.__file__`.
- **Stale artifact check**: search the run path for obsolete error strings, old env names, placeholder crypto config, and generated report files that can mislead debugging. Clear stale `reports/allure-results` before re-running after code changes. Remove project `__pycache__`; do not delete virtualenv dependency caches.
- **Dependency gate**: run the generated dependency checker first. Missing Python packages are environment blockers; mismatched generated code/config is a generator defect.
- **Syntax gate**: compile generated Python in memory or with cleanup afterward. Do not leave temporary cache files in deliverables.
- **Config-code alignment**: verify `configs/{env}.yaml` keys match helper signatures and runtime behavior. No generated code may still request env vars or fields removed from config.
- **Unified runtime configuration entry gate**: apply only when local operators otherwise need multiple files/categories or explicitly request one form, and skip it when one authoritative secure entrypoint already exists. Follow `unified-runtime-configuration-entry.md`: require one declared source, deterministic no-network preflight, placeholder/duplicate/unknown-key rejection, special-character-safe parsing, mapping into existing env/auth/database layers, redaction, version-control exclusion, and no silent legacy fallback. A filled form does not authorize non-live or irreversible execution.
- **Auth bootstrap gate**: when auth is dynamic, run or simulate the configured auth request path. Verify status assertion, response decoding, extraction paths, token placement, and runtime context writes. If the runtime contract provides token/session/user context from login, prefer extraction from that response over asking the user to hand-fill duplicate secrets. For multi-account or multi-role suites, generate a stable `account_group_key` before execution. Prefer an explicit upstream grouping key; otherwise derive it from session role, account type, tenant/permission scope, required account business state, and source-bound user identity placeholders. Authenticate once per group, extract token/session/user/device/key-material context, reuse one requester/session for all compatible cases in that group, and record per-group executed/passed/failed counts. Do not build a new requester or login for every case unless the case itself is testing login, refresh, logout, session invalidation, or requires an explicitly fresh/isolated account. `reauth_before_case` is allowed only as an auth-isolation strategy for token/session/context pollution and requires a dynamic auth contract that can be executed safely before the case.
- **Auth bootstrap materialization gate**: generated ordinary API tests that use non-anonymous dynamic auth must contain an executable pre-business auth bootstrap path, such as a `case_account_login` fixture or an auth-context registry keyed by `account_group_key`/`session_role`. It must run before API setup, SQL setup, and business request execution; update the active auth context from extracted token/session/user/device/key-material; skip duplicate bootstrap for cases whose first step is an explicit `auth`/`login` step; and disable any previous business token while calling the pre-login auth request unless the source contract explicitly requires it. Account-specific E2E flows must not rely on that hidden fixture: their first flow step must be visible `auth` or `login`, must extract token/account context, and the flow runner must validate that contract before business steps.
- **Runtime scope materialization gate**: generated code must initialize a fresh business-variable scope before each ordinary case and once before each complete E2E flow. Preserve only the configured account-group auth/session registry and its role aliases across compatible scopes; clear prior business ids, markers, timestamps, SQL/API extracts, and response payloads. All steps inside one flow share the same scope. The initializer must run before auth bootstrap, API setup, SQL setup, and business requests so a stale variable cannot satisfy a later placeholder accidentally.
- **Step extraction and login-context gate**: ordinary multi-step runners and flow runners must consume explicit source-bound extraction rules through the same normalized extractor/auth-context behavior. Preserve extracted scalar/list/object types, fail on missing required paths, and publish only into the active scope. A step marked `auth` or `login` must name its target role/account group, extract token plus every downstream-required account field, and update the shared auth registry; URL naming alone is not login evidence.
- **API teardown resilience gate**: after API setup starts, generated teardown must attempt ownership-scoped cleanup even when setup partially fails, the request fails, or an assertion fails. Cleanup execution must continue across independent rules, aggregate failures, restore the previously active client auth context, and retain the original failure in pytest reporting. A cleanup without a current-run ownership key, snapshot, or source-bound state-restore boundary remains blocked.
- **Transport crypto gate**: distinguish pre-login, login, post-login, no-encrypt, callback, internal, and health-check channels from confirmed gateway/client evidence. Generated client code must use the same request envelope, response decrypt rule, key source, suffix/header/query conventions, and path classification as the confirmed contract. Do not require manual crypto env vars when the runtime secret can be obtained from a source-bound login/precondition response. Enforce one shared requester and one shared crypto adapter; reject per-case requester construction for the same transport contract. Record `configs/shared_requester_crypto_adapter_status.yaml` with `not_required|blocked|failed|passed_static|passed_live_smoke`. Treat `passed_static` as smoke-candidate readiness only; require `passed_live_smoke` before claiming encrypted live execution readiness.
- **Transport diagnostic evidence gate**: before raising an encrypted-response decode error, retain bounded pre-decryption HTTP metadata, bounded response text, and bounded decode-failure context in Allure. Apply recursive key and assignment-text redaction to Authorization, proxy authorization, cookies, API keys, tokens, passwords, identity values, and exception messages. Attachment length must be configurable with a hard cap, and request/response envelope fields must come from the confirmed transport policy rather than a hardcoded `data` key. Diagnostic evidence cannot be used as a fallback response or change assertion outcomes.
- **JSONPath gate**: generated extractors must support standard root `$`, dot paths, and array indexes such as `$.data.items[0].id`. Validate every configured extraction path against a representative response shape from execution facts, runtime evidence, or a small synthetic payload that matches the contract. If a path is absent, report the actual payload shape and block; do not silently fall back to another path.
- **Assertion JSONPath gate**: generated response assertions must support the same normalized JSONPath dialect as extraction paths, including root `$`, dot paths, and array indexes. Apply the normalization consistently to `business_code_path`, `json_equals`, `required_fields`, `array_length_equals`, `string_min_lengths`, archive cases, and generated collection assertions. A response assertion path may be stored as `$.data.id` or `data.id`, but execution must normalize it before lookup; do not treat `$` as a literal field name. Validate this with a decoded representative response or a small synthetic payload that includes nested fields and arrays.
- **Variable resolution gate**: resolve a sample case payload through the same runtime-context resolver used by pytest. Fail on unresolved placeholders, invalid Python identifiers, keyword variable names, or variables with dots/hyphens/spaces.
- **Runtime evidence materialization gate**: when generated runnable cases cite runtime evidence candidates, runtime value catalogs, supplemental request results, or replay evidence, run the mapping audit from `runtime-evidence-script-materialization.md` before live pytest. Generated plaintext request fields, semantic role variables, expected business code/message, and evidence ids must match the source evidence exactly.
- **Request shape fidelity gate**: generated ordinary cases, flow steps, optional async cases, `接口案例.md`, and generated collection artifacts must preserve source-visible scalar/list/object/map field kinds, nesting, array order, `null`, and intentional omission. Stringified JSON/text forms are allowed only when a confirmed transport or persistence boundary requires them, and the business-plaintext model must still be retained for assertions and review.
- **Business-readable input quality gate**: for positive-path, live, long-chain, and page-visible request fields, verify values are source-bound legal values; bounded generic real-world legal samples are allowed only for ordinary user-entered/profile/display fields whose contract permits legal literals. Obvious placeholders are valid only for explicit invalid-value/error-branch cases with matching expected error assertions.
- **Assertion strength gate**: verify every runnable case records `assertion_strength` and `result_observation_mode`. Live cases need at least `L2_response_field`; long-chain or write-side-effect cases need at least `L3_business_observable`; high-risk write-side-effect or cleanup-sensitive cases need `L4_persistence_verified` or `L5_cleanup_verified`, unless they are explicitly non-live/manual review.
- **Business result observability gate**: for every side-effect or business-result case, require either a follow-up API/detail/list/status assertion or a scoped DB assertion. If neither API nor DB can observe the result, keep the case out of the live denominator as `generated_non_live` or `manual_review_only`.
- **Slow/optional async gate**: cases whose only safe closure requires a long wait, delayed queue consumption, cron/job completion, push/callback settlement, or TTL expiry must be routed to `optional_async` instead of the default fast live denominator. They must have explicit `async_observation.wait_seconds`, a collection gate such as `--run-slow-async`, an optional wait override such as `--slow-async-wait-seconds`, and an API or DB observability assertion after the wait. Default `pytest --collect-only --flow=all` must exclude these cases; a separate collect with the explicit gate must include only the optional async nodes.
- **Setup/cleanup materialization gate**: inspect the selected live denominator before broad runs. Mutable live cases must have executable API/SQL cleanup through `case_data_manager` or `case_sql_manager`, same-interface restore, isolated-account/snapshot containment, or an explicit source-bound no-cleanup rule; `cleanup_refs`、`cleanup_id`、DB before/after files, and narrative cleanup evidence are audit links only. DB before/after is not a blanket requirement for source-confirmed no-persistent-side-effect, runtime no-delta, sandbox/mock-isolated, or explicit non-live business-exception cases. If `data/case_sql_commands.yaml` is empty or `not_required` while selected live cases need SQL setup/cleanup, runtime usability is blocked. When SQL commands exist, partition them by generated flow-step case ids and ordinary case ids before applying chain coverage or long-chain extraction gates; the total SQL entry count is not a long-chain count. `generated_non_live` and `manual_review_only` cases may remain in status/archive, but they cannot count as live-executed cases. When `target_run_scope=all_generated_cases`, any excluded candidate, blocked readiness row, non-live decision, cleanup_refs-only mutable case, or pending SQL rollback validation blocks broad real execution.
- **SQL fixture materialization gate**: derive SQL-driven cases from the same predicate used by generated data and validators: an enabled `sql_fixture_required`, an active SQL/DB `setup_cleanup_materialization` or `db_assertion_materialization`, DB assertion materialization, or a matching case id in `data/case_sql_commands.yaml`. Status strings or objects that explicitly mean `not_required`、`no_cleanup_required`、API-only snapshot/restore, or another non-SQL strategy are classification evidence but are not active SQL signals merely because the field is non-empty. Every SQL-driven case must have a `case_id` marker, `case_sql_manager` fixture, a resolvable `case_data.case_id`, matching SQL commands when commands are required, and the full lifecycle `setup -> business request -> runtime_extract -> cleanup -> final_verify` when those stages exist. If DB env vars, driver, or tunnel are missing, record the affected case ids under `live_execution_readiness.pending_inputs` or an equivalent DB readiness ledger before execution; do not let them fail later as unresolved runtime variables.
- **SQL lifecycle deep static gate**: before broad execution, statically inspect `data/case_sql_commands.yaml` against the generated fixture lifecycle. Reject setup or case-level params that reference post-request runtime ids, reject SQL setup values that violate target column length/type/enum evidence, reject `expected_*` fields that are not returned by the same `verification_query`, reject ad-hoc extra verification query keys that the executor does not run, and reject cleanup/final verification pairs whose ownership boundary differs without explicit pre-isolation or pre-clean evidence.
- **Post-request failure-path cleanup gate**: for SQL-driven mutating cases, partition response/DB-produced variables from request/setup/auth variables before live release. Commands that consume late variables must declare `side_effect_class`; optional derived cleanup may skip missing values, primary cleanup requires request-known fallback lookup or snapshot containment, and prestate restore must remain independent. Treat timeout, TLS/SSL EOF, connection reset, and proxy disconnect as ambiguous write outcomes. Record `failure_path_cleanup_resilience.status`, checked case count, fallback-covered case count, and missing/unsafe case ids in `generation_status.yaml`; broad live readiness requires `status: passed` whenever such cases exist.
- **SQL persisted-value assertion gate**: when SQL assertions compare values created by the request, verify the expected value matches the actual stored representation after application serialization, JSON wrapping, type conversion, defaults, trimming, or date/time formatting. Lists/objects, enums, markers, and display values must not be compared as guessed strings.
- **Derived assertion gate**: counters, balances, scores, rates, task progress, latest-time fields, and other derived/aggregate assertions must use source formulas, before/after snapshots, current-run extraction, or scoped follow-up queries. A fixed historical aggregate value is valid only for a source-confirmed fixed test-owned configuration row.
- **SQL lifecycle idempotence gate**: if the same SQL case entry can be invoked by ordinary parametrization, optional async tests, or an E2E flow runner, the runtime must record completed case/stage keys so `runtime_extract`, delayed waits, cleanup, and final verification execute once per intended case/stage or take an explicit safe no-op path.
- **Database pooled-connection liveness gate**: session-scoped database engines must validate a pooled connection when it is checked out and expose a bounded recycle interval through `configs/database.yaml` or an equivalent environment configuration entry. When SQL runtime extraction includes delayed observation windows, the next query, cleanup, and final verification must not trust an unchecked idle connection. The generated framework should enable `pool_pre_ping` and a configurable `pool_recycle` value by default; database URL, credentials, and hosts remain runtime environment inputs.
- **SQL bounded polling gate**: when an asynchronous write, aggregate, callback, or scheduled result is observable through safe SELECT assertions, prefer `poll_until_expected.timeout_seconds` plus `interval_seconds` over an unconditional long sleep. The executor must evaluate the complete query batch, publish runtime values only after all expected effects pass, return immediately on success, and raise the final assertion on timeout. Only assertion-not-ready mismatches are retryable; connection, SQL, transport, and configuration errors fail immediately. Reject commands that declare both fixed wait and bounded polling. This gate does not move slow/optional async cases into the default fast denominator.
- **Existing-state closure gate**: positive write-side-effect cases whose result depends on prior uniqueness, idempotency, review/pending state, or relationship existence must prove a clean starting state before live release. Examples include report/feedback/subscription/order/message/evaluation/relation/status-transition records, but the rule is based on source/runtime state dependence rather than endpoint names. Accept source-bound precheck API, precise API cleanup, bounded SQL pre-clean, isolated account/state, or a non-live/manual decision. A later business error caused by old data is a setup/runtime-state defect unless the correct pre-state closure already ran.
- **Historical-shape SQL setup gate**: for SQL setup INSERT/UPDATE commands, verify the command carries passed historical-shape evidence derived from bounded same-table/same-business-state rows or equivalent normalized DB evidence. Block runtime usability when setup values use technical markers in page-visible fields, violate historical enum/time/JSON shape, or create invalid actor/counterparty relationships such as self-relations outside an explicit error branch.
- **Evidence retention gate**: when a run is used for defect triage, retain the complete plaintext request before encryption and the complete decoded plaintext response after decryption. Status/shape summaries can support triage, but they cannot support a confirmed defect list.
- **Account grouping evidence gate**: when more than one account or role is used, retain `account_group_key`, grouping dimensions, auth bootstrap evidence id, extracted auth-context fields, requester/session reuse id, group case ids, executed count, passed count, failed count, and failed case ids. If cases are executed with one requester/login per case without an allowed exception, classify the run as a requester-materialization defect and do not promote it to live pytest readiness.
- **Case runtime isolation gate**: account grouping is not business-state isolation. For each selected live case, record whether it is read-only/no-delta, auth-isolated by `reauth_before_case`, cleanup/restore protected, isolated-account protected, ordered in a flow, or non-live/manual. If a same-account group contains write side effects, one-time actions, balance/quota/task progress changes, relationship/message/order/subscription state changes, or account-state transitions, re-login alone is insufficient. Require cleanup/restore, isolated account state, explicit `depends_on`/`execution_order`, or convert the cases to a flow before live pytest release.
- **Collection gate**: run `pytest --collect-only --flow=all` when dependencies are installed. The collected nodeids must match `generation_status.yaml`.
- **Optional live smoke gate**: when the user has supplied a runnable test environment and expects execution, run the smallest safe smoke path before claiming runnable success: dependency check, auth bootstrap, one read-only or explicitly selected safe case, then any requested subset. Do not run broad mutating suites without the requested execution denominator, target-run-scope consistency, and cleanup/rollback evidence.

## Failure Classification

- `BLOCKED_RUNTIME_DEPENDENCY`: required package/driver is missing.
- `FAILED_RUNTIME_CONFIG_ALIGNMENT`: generated config and code disagree, such as removed env vars still read by code.
- `FAILED_UNIFIED_RUNTIME_CONFIG_ENTRY`: the conditional unified-entry capability is generated but its parser, preflight, internal mapping, redaction, source exclusivity, version-control exclusion is missing or inconsistent.
- `FAILED_AUTH_BOOTSTRAP`: login/token acquisition or token/session extraction fails.
- `FAILED_TRANSPORT_CRYPTO_ALIGNMENT`: request encryption, response decryption, key source, or path classification differs from confirmed contract.
- `FAILED_EXTRACTION_PATH`: JSONPath/regex extraction does not match the decoded response shape.
- `FAILED_RUNTIME_EVIDENCE_SCRIPT_MATERIALIZATION`: generated case data differs from runtime evidence in request fields, role variables, per-step expected business code/message, or evidence mapping.
- `FAILED_REQUEST_SHAPE_MATERIALIZATION`: generated data, archive, or collection output loses source-visible scalar/list/object/map shape, array order, `null`, nesting, or intentional omission without a confirmed boundary rule.
- `BLOCKED_BUSINESS_READABLE_INPUT_QUALITY`: positive-path, live, long-chain, or page-visible request fields contain placeholders or invalid combinations without being an explicit invalid-value/error-branch case.
- `BLOCKED_ASSERTION_STRENGTH_INSUFFICIENT`: runnable cases do not meet the minimum assertion strength for their scope.
- `BLOCKED_BUSINESS_RESULT_NOT_OBSERVABLE`: side-effect or business-result cases lack both follow-up API verification and scoped DB assertion.
- `BLOCKED_SETUP_CLEANUP_MATERIALIZATION`: selected live mutable cases lack executable setup/cleanup rules, SQL cleanup is required but `case_sql_commands.yaml` is empty/not-required, cleanup closure is unresolved, or full-suite execution has excluded/blocked/non-live candidates.
- `FAILED_SQL_FIXTURE_MATERIALIZATION`: SQL-driven case metadata, pytest markers, fixture attachment, SQL command ledger, or SQL lifecycle stages disagree; for example an active SQL/DB `setup_cleanup_materialization` exists but no `case_id` marker is generated, or runtime extract variables can only fail after the business request.
- `FAILED_SQL_FIXTURE_DEEP_STATIC_GATE`: SQL command data is structurally generated but cannot run safely because setup references post-request variables, generated values violate table constraints, verification aliases do not match expected fields, unsupported verification-query keys are present, dynamic ids are hardcoded without source proof, or cleanup verification asserts a wider boundary than the cleanup action materializes.
- `FAILED_SQL_PERSISTED_VALUE_ASSERTION`: SQL assertions compare against guessed request-side values instead of the source-confirmed persisted representation, or derived assertions hardcode mutable aggregate/history values.
- `FAILED_SQL_LIFECYCLE_IDEMPOTENCE`: SQL lifecycle stages can run twice for the same case/stage through multiple fixtures or runners, causing duplicate waits, extraction, cleanup, or final verification.
- `BLOCKED_EXISTING_STATE_CLOSURE`: positive write-side-effect cases can be affected by prior uniqueness/idempotency/relationship state, but no precheck, precise pre-clean, isolated state, or non-live/manual decision is materialized.
- `BLOCKED_CASE_RUNTIME_ISOLATION`: same-account cases have unresolved order sensitivity, business-state pollution, one-time actions, quota/balance/task-progress mutation, or account-state transitions; `reauth_before_case` is present but business-state isolation is needed; or required cleanup/restore/isolated-account/flow-order evidence is missing.
- `BLOCKED_DEFECT_EVIDENCE_INCOMPLETE`: runtime failure evidence lacks complete plaintext request/response or DB before/after details required for confirmed defect filing.
- `FAILED_ACTUAL_RUN_PATH_SYNC`: canonical output was fixed but the user's run directory still contains stale generated code.
- `FAILED_STALE_REPORT_ARTIFACT`: old report output continues to surface obsolete stack traces after code changes.

## Minimum Status Recording

`configs/generation_status.yaml` should record runtime usability separately from coverage mapping:

```yaml
runtime_usability:
  status: passed | blocked | failed
  script_generation_ready: true | false
  runtime_configuration_entry:
    status: provided | pending_values | not_required
    mode: unified_local_document | established_secure_source | not_required
    authoritative_source: ""
    local_sensitive_files: []
    preflight_command: ""
    pytest_env_option: "--env"
    env_config_files: []
    database_config_file: ""
    secret_source: process_environment | unified_local_document | established_secure_source
    legacy_sources_disabled: true
    version_control_excluded: true
  live_execution_readiness:
    status: ready | pending_runtime_config | blocked | failed
    blocks_script_generation: false
    pending_inputs: []
  validation_scope:
    scope_type: same_chain_patch | selected_subset | all_generated_cases
    target_flow_ids: []
    target_case_ids: []
    changed_shared_files: []
    unrelated_chain_change_count: 0
  actual_run_path: ""
  dependency_check: passed | blocked | failed
  syntax: passed | failed
  config_code_alignment: passed | failed
  auth_bootstrap: passed | blocked | failed | not_required
  auth_bootstrap_materialization:
    status: passed | blocked | failed | not_required
    ordinary_fixture_or_registry: ""
    ordinary_pre_business_order_verified: true
    explicit_login_case_skip_verified: true
    pre_login_token_injection_blocked: true
    flow_first_step_login_verified: true
    secrets_redacted: true
  account_grouping:
    status: passed | blocked | failed | not_required
    group_count: 0
    groups:
      - account_group_key: ""
        group_by_fields: []
        auth_bootstrap_evidence_id: ""
        requester_session_reuse_id: ""
        case_ids: []
        executed_count: 0
        passed_count: 0
        failed_count: 0
        failed_case_ids: []
  case_runtime_isolation:
    status: passed | blocked | failed | not_required
    auth_isolation_case_ids: []
    business_state_isolation_case_ids: []
    ordered_flow_case_ids: []
    isolated_account_case_ids: []
    non_live_case_ids: []
    blockers: []
  transport_crypto_alignment: passed_live_smoke | passed_static | blocked | failed | not_required
  shared_requester_crypto_adapter: "configs/shared_requester_crypto_adapter_status.yaml"
  extraction_paths: passed | failed | not_checked
  runtime_evidence_script_materialization: passed | blocked | failed | not_required
  request_shape_fidelity: passed | blocked | failed | not_required
  business_readable_input_quality: passed | blocked
  assertion_strength_gate: passed | blocked
  business_result_observability: passed | blocked
  setup_cleanup_materialization: passed | blocked
  sql_fixture_materialization: passed | blocked | failed | not_required
  sql_fixture_deep_static_gate: passed | blocked | failed | not_required
  sql_persisted_value_assertion: passed | blocked | failed | not_required
  sql_lifecycle_idempotence: passed | blocked | failed | not_required
  existing_state_closure: passed | blocked | not_required
  historical_shape_sql_setup: passed | blocked | not_required
  cleanup_closure_stage: passed | partial | blocked
  assertion_strength_counts: {}
  result_observation_mode_counts: {}
  insufficient_assertion_strength_case_ids: []
  business_result_not_observable_case_ids: []
  optional_async:
    status: passed | blocked | not_required
    default_denominator_excluded: true
    collection_gate: "--run-slow-async"
    wait_override: "--slow-async-wait-seconds"
    case_ids: []
    collect_only_default_count: 0
    collect_only_with_optional_count: 0
  target_run_scope: all_generated_cases | safe_subset
  generated_candidate_case_count: 0
  selected_case_count: 0
  runnable_case_count: 0
  blocked_real_run_case_count: 0
  defect_evidence_retention: passed | blocked | not_required
  collect_only: passed | blocked | failed
  stale_artifacts_cleared: true
  blockers: []
```

Do not set `generation_status.yaml.next_stage_allowed=true` when non-network runtime usability gates are blocked or failed. It is acceptable for `next_stage_allowed=true` to coexist with `live_execution_readiness.status: pending_runtime_config` when `script_generation_ready=true`, `runtime_configuration_entry.status=provided`, pytest collection passed, and the only remaining items are runtime-provided environment values such as secrets, DB URLs, drivers, or network tunnels.
