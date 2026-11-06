# Runtime Evidence To Script Materialization Gate

## 目录

- Core Principle
- Script Materialization Readiness Gate
- Source Precedence
- Request Materialization Rules
- Expected Response Materialization Rules
- Step Binding Rules
- Cross-Check Gate
- Failure Triage Rules
- Required Status Recording


Use this reference when executable pytest/allure scripts are generated from runtime evidence candidates, direct-request observations, or patched execution-level artifacts that cite `runtime_evidence.yaml`, `runtime_value_catalog.yaml`, `runtime_evidence_candidate_cases.yaml`, supplemental request plans/results, or replay evidence.

The purpose is to prevent a valid runtime observation from becoming an invalid generated script because request values, role variables, expected business codes, or per-step assertions were changed during conversion.

## Core Principle

Runtime evidence is a source-bound execution fact. Script generation may normalize format, but it must not reinterpret, collapse, or replace the observed request and expected response. A script failure caused by conversion loss is a generator defect, not a product defect.

## Script Materialization Readiness Gate

Runtime evidence may enter the runnable pytest denominator only when the source item has `script_materialization_ready: true`. If this field is missing or false, keep the item as runtime observation, retry input, candidate evidence, or manual-review evidence; do not count it as live pytest ready.

An evidence-backed scriptable step must retain:

- `case_id` or `flow_id`, `step_id` or `step_order`, module, method, path, base-url alias, session role, auth policy, and token injection location.
- `account_group_key` or an equivalent role/account grouping key when multiple accounts are used, plus evidence that the requester authenticated once per group and reused the account context for all compatible cases in that group.
- `case_runtime_isolation` when order sensitivity, auth contamination, or same-account business-state pollution is possible. It must distinguish auth re-login from business-state cleanup/restore/isolated-account/flow-order protection.
- Plaintext request model for path/query/header/body after runtime variable resolution and before encryption, with secrets replaced by stable placeholders.
- Source-visible request shape metadata for scalar/list/object/map fields, nesting, array order, `null`, and intentional omissions. Serialized strings are evidence only for confirmed transport or persistence boundaries; they do not replace the business-plaintext request model.
- Decoded plaintext response model after decryption, including HTTP status, business code/message, `data` shape, and key business fields.
- Assertion candidates and selected executable assertions with `assertion_strength` and `result_observation_mode`.
- Setup classification and cleanup classification. `not_required` is valid only when the evidence records why setup/cleanup is not required.
- For SQL setup, `historical_shape_reference` or equivalent normalized evidence proving same-table/same-business-state shape review before insertion or update. This evidence must not contain copied sensitive row values.
- DB before/after or SELECT assertion evidence when the business result, cleanup, or no-dirty-data proof is not API-observable.
- `missing_materialization_items: []`; non-empty missing lists block runnable script generation.

Do not promote evidence to runnable just because it has `usable_for_execution_case=true` if it lacks materialized plaintext request/response, executable assertions, required cleanup, or required observability proof. `usable_for_execution_case` may support value propagation only when the specific value is confirmed; it does not by itself prove the whole case is scriptable.

## Account Group Materialization Rules

When runtime evidence uses more than one account, role, tenant, permission scope, or account business state, generated scripts must materialize account grouping explicitly:

- Generate a stable `account_group_key` for each compatible account context. Prefer an upstream key; otherwise derive a semantic key from session role, account type, tenant/permission scope, required business state, and source-bound user identity placeholder.
- Keep each case or step bound to exactly one `account_group_key` unless the source evidence is a cross-account flow; cross-account flows must name both active and target account groups separately.
- Authenticate once per group and extract token, session secret, user id, device id, and any transport key material from the group bootstrap response or source-bound fixture. Reuse that context for every compatible case in the group.
- Do not create one requester, one login, or one auth context per case unless the case itself is login, token refresh, logout, session invalidation, or explicitly requires a fresh/isolated account.
- Record group evidence with group key, grouping dimensions, auth bootstrap evidence id, requester/session reuse id, case ids, executed count, passed count, failed count, and failed case ids.
- When pytest scripts are generated, materialize the grouping as an auth-context registry or fixture keyed by `account_group_key`/session role. The test data should select a group; the shared client should switch to that context before sending the request.
- For ordinary API cases, the generated fixture or registry must authenticate before the first business step for the selected account group, write extracted token/session/user/device/key-material into runtime context, and then let setup, SQL fixtures, and business requests consume that context. Do not add this hidden bootstrap to explicit login/auth cases; those cases must execute their visible login step and update the same auth-context registry from its extraction rules.
- For account-specific long-chain flows, do not replace the first login/auth step with an ordinary-case fixture. The flow data must keep a visible first `auth`/`login` step, the flow runner must validate it before execution, and extracted auth context must be available to every later business step that declares that role.
- Before either ordinary execution or a flow begins, initialize the matching runtime scope. Keep the account-group auth/session registry, clear unrelated prior business variables, and preserve one scope across all producer/consumer steps in the same flow. Evidence used by a later step must come from the current scope, environment/auth configuration, or an explicit upstream reference.
- API setup and cleanup materialization must remain paired on failure paths: after setup starts, teardown attempts all independent ownership-scoped cleanup rules, restores the prior request auth context, and reports cleanup failures separately from the request/setup failure.

## Case Runtime Isolation Rules

Account grouping improves requester reuse, but it does not make same-account cases independent. Materialize isolation separately:

- Use `auth_isolation.reauth_before_case: true` only for token expiry, session refresh, login-state cache, or auth-context contamination. It requires a source-bound dynamic login/auth contract and must record the auth bootstrap evidence used before the case.
- Do not use `reauth_before_case` to compensate for database/business-state pollution. Re-login does not undo created orders, messages, subscriptions, relationships, evaluations, balance consumption, task progress, audit state, or once-per-day/once-per-account actions.
- For write side effects or stateful assertions, require `business_state_isolation` with one of: executable cleanup, same-interface restore, scoped SQL restore, isolated account, sandbox snapshot, or explicit `non_live/manual_review`.
- If one case intentionally prepares state for another case, do not materialize them as independent ordinary cases. Keep the dependency as `depends_on`/`execution_order` in a flow or long-chain script.
- If a case requires a specific account state, include that state in the `account_group_key` or split it into a separate group, such as role plus permission scope, onboarding state, subscription state, balance tier, or task progress state.

## Slow/Optional Async Materialization Rules

Use this route only when the case is otherwise scriptable but deterministic closure depends on a long asynchronous observation window, such as delayed queues, scheduled jobs, callback settlement, push notification processing, or TTL expiry. This route is not a shortcut for missing request values, missing assertions, missing cleanup, or unsafe side effects.

- Mark the case with `optional_async: true` and keep it outside the default fast live pytest denominator.
- Store optional async cases outside `data/cases/` unless the generated loader has an explicit exclusion rule; otherwise they will silently enter the ordinary parameterized denominator.
- Generate a separate pytest entrypoint such as `test_optional_async_cases.py` and require an explicit collection flag, for example `--run-slow-async`.
- Provide `async_observation.wait_seconds`, `wait_reason`, `run_gate`, and `override_option`; do not hide long sleeps inside ordinary tests.
- Preserve the same runtime evidence contract as normal live cases: plaintext request, decoded response, auth/session role, setup/cleanup classification, assertion strength, and observability proof.
- After the wait, verify the business result through a follow-up API or scoped DB assertion. If the correct closure is no-delta, record before/after snapshots and compare the same ownership keys.
- If the case triggers a write side effect, use executable cleanup/restore when possible. If the correct strategy is no cleanup because no persistent delta is expected, record a source-bound no-delta assertion and keep cleanup verification read-only.
- Record optional async counts separately in `generation_status.yaml`; do not add them to `collected_test_count`, ordinary live passed count, or required long-chain flow count unless the user explicitly changes the denominator.

## Source Precedence

When the same case has design-level expectations and runtime evidence:

- Runtime evidence and `runtime_value_catalog.yaml` take precedence for execution-level request values, response assertions, variable links, and downstream inputs.
- Supplemental request/result evidence can refine runtime evidence only when it cites the same case, step, method, path, role, and request variant.
- Design-level cases and default success assertions may fill only fields that runtime evidence does not cover. They must not overwrite observed business code, message, request body, `null` value, missing field, or role-specific variable.
- A candidate with `candidate_status: materialized_candidate_not_released`, `release_gate.next_stage_allowed: false`, or equivalent unreleased status is not part of the formal runnable denominator until this materialization gate passes.

## Request Materialization Rules

Generated case data must preserve the runtime-evidence request exactly at business-plaintext level:

- Keep all field names, nesting, array order, literal values, `null` values, and intentionally missing fields.
- Keep field kinds. Scalars, arrays/lists, objects, and maps must remain distinct in generated case data, flow overrides, archive entries, and generated collections. Do not turn a list/object into a string or split a map into ad-hoc scalar fields unless the evidence names the confirmed boundary that performs that serialization.
- Keep request location: path, query, header, cookie, body, and encrypted-body plaintext template must not be merged into the wrong location.
- Preserve method and path from the evidence step. Do not substitute a nearby controller path, API wrapper default, or route bucket path.
- Preserve the role context and `session_role` of the evidence step.
- Preserve business-readable value quality for positive-path, live, long-chain, and page-visible fields. Generated scripts must not replace source-bound legal values or allowed bounded generic real-world legal samples with placeholders, and must not promote placeholder values such as `自动化省`、`测试市`、`UNKNOWN` into positive-path requests.
- Preserve source-visible required request fields. If the controller/request DTO/OpenAPI contract marks a field required, for example through `@NotNull`, `@NotBlank`, `@NotEmpty`, or an equivalent required-field rule, a positive-path runnable step must include that field at the same request location with a legal value. Omitting the field or sending an empty request body is allowed only for an explicit validation/error branch whose expected response asserts that missing-field behavior.
- Preserve validation branch isolation. If a step intentionally omits or invalidates one target field, every unrelated required field, role-specific value, auth/account context, and upstream variable needed to reach that validation point must stay legal and source-bound; otherwise the generated step is evidence for the wrong branch.
- Preserve request variants across generated surfaces. When ordinary cases, flow steps, optional async cases, or archive cases share the same method/path and compatible request variant, their required field set and source-bound business parameters must not drift unless the evidence records a role, state, producer-consumer dependency, or explicit branch difference.
- Do not collapse semantic runtime variables to a generic login variable. Examples that must remain distinct include `${runtime.male.userId}`, `${runtime.female.userId}`, `${runtime.unonboarded_female.userId}`, `${runtime.nowIso}`, `${runtime_context.target_user_id}`, `${session_secret}`, and token/session placeholders.
- The same field name in different roles may resolve from the active `session_role` only when the evidence explicitly says it is the active role's own value. Cross-role target fields must keep their target-role variable.
- For encrypted transports, generated data remains plaintext business data. Encryption happens only in the client immediately before send.

## Expected Response Materialization Rules

Generated assertions must bind to the same evidence item that produced the request:

- `expected.business_code` must equal `expected_response.business_code_value` when the candidate provides it.
- `expected.message` must equal the evidence message when a concrete message is present.
- HTTP status and business code are separate assertions. Do not replace a business-error code with HTTP `200`, and do not convert a business-error API into an HTTP `500` expectation unless the evidence actually returned HTTP `500`.
- Response `data` shape assertions must use the decoded plaintext response after decryption.
- If one source case has multiple observations or retry variants, each generated step must keep its own request, expected code, expected message, `evidence_id`, and source refs. Do not duplicate the first observation's expected response across later variants.

## Step Binding Rules

Every generated ordinary case step or flow step that comes from runtime evidence must have a one-to-one evidence mapping:

```yaml
runtime_evidence_script_mapping:
  - generated_case_id: "EXE-TC-001"
    generated_step_id: "EXE-TC-001#step-01"
    source_case_id: "EXE-TC-001"
    evidence_id: "RT-001"
    request_variant_id: "primary"
    method: "POST"
    path: "/api/v1/example"
    session_role: "female"
    expected_business_code: "200"
```

If a case contains multiple evidence observations, use stable `step_order` or `step_instance_id` values so downstream audit can distinguish them. Reusing one `case_id` is acceptable only when each step instance remains uniquely traceable.

## Cross-Check Gate

After writing `data/cases/`, `data/flow_cases.*`, `接口案例.md`, and generated pytest modules, run a deterministic self-audit before pytest execution. Compare every evidence-backed generated step with its source candidate:

- Generated method/path equals the candidate method/path.
- Generated plaintext request has the same field set, nesting, literal values, `null` values, and missing-field intent as the candidate request.
- Generated plaintext request has the same scalar/list/object/map kinds, array order, and nested shape as the candidate request. Any generated collection or archive artifact must preserve the same business-plaintext shape.
- Generated positive-path request satisfies source-visible required-field rules; any intentionally missing required field is traceable to an error-branch assertion.
- Generated validation/error branch isolates the target defect: non-target required fields and required auth/account context remain legal, and the expected error assertion points to the intended branch.
- Generated requests for the same method/path and compatible request variant keep a consistent required field set across ordinary, flow, optional async, and archive outputs, except where a source/runtime difference is recorded.
- Generated runtime placeholders preserve semantic role/source names, not only value type.
- Positive-path/page-visible request fields pass the business-readable value quality rule, or the source case is explicitly an invalid-value/error-branch case with matching expected error assertions.
- Generated expected HTTP status, business code, message, and response `data` assertions equal the candidate's per-step expected response.
- Generated `assertion_strength` and `result_observation_mode` satisfy the source evidence and minimum strength required for the case type.
- Generated setup and cleanup actions match the source evidence; cleanup refs, DB before/after refs, or narrative cleanup text are not treated as executable cleanup.
- Generated SQL setup preserves the historical-shape reference evidence and does not place technical run markers, malformed values, or invalid self-relations into page-visible or relationship fields unless the source case is an explicit invalid-value/error branch.
- Generated SQL assertions compare request-produced values with the evidenced persisted representation, and generated aggregate assertions use formulas, before/after values, or current-run extraction instead of copied historical constants.
- Generated auth bootstrap shape matches the evidence and case type: ordinary cases use account-group fixture/registry bootstrap before business steps; explicit login cases update auth context from their own step extraction; account-specific flows keep visible first-step login/auth and token extraction.
- One generated step maps to exactly one evidence item or supplemental request/result item.
- Every evidence-backed generated case appears in `接口案例.md` with the same plaintext request and expected response.

If any mismatch is found, block live execution and record:

```yaml
runtime_evidence_script_materialization:
  status: failed
  audit_report: "configs/runtime_evidence_script_mapping_audit.yaml"
  evidence_backed_step_count: 0
  mismatch_count: 0
  mismatches: []
  failure_code: "FAILED_RUNTIME_EVIDENCE_SCRIPT_MATERIALIZATION"
```

Do not run broad pytest, do not declare `next_stage_allowed: true`, and do not file product defects from the mismatched scripts until the generated data is corrected.

## Failure Triage Rules

When a generated script fails:

- If replaying the exact generated request fails but replaying the preserved runtime-evidence request passes, classify the issue as `generator_materialization_defect`.
- If the actual response matches runtime evidence but the generated assertion differs, classify the issue as `assertion_materialization_defect`.
- If a role-specific target value was replaced by the active login user's value, classify the issue as `role_variable_materialization_defect`.
- If an error branch fails because a non-target required field or context was omitted, classify the issue as `validation_branch_isolation_defect`.
- If a flow step drops fields that a compatible source-backed ordinary case retained, classify the issue as `request_variant_consistency_defect`.
- If a generated script, archive, or collection changes a source array/object/map into a string or otherwise loses request shape without a confirmed boundary rule, classify the issue as `request_shape_materialization_defect`.
- If multiple observations under one case reuse the same expected business code or message incorrectly, classify the issue as `per_step_expected_response_materialization_defect`.
- Promote a product defect only after generated request/expectation mapping passes, runtime request/response evidence is complete, setup/cleanup is closed, and DB before/after evidence is retained when persistence changes.

## Required Status Recording

`configs/generation_status.yaml` must include this section whenever runtime evidence candidates or direct-request observations are used to generate scripts:

```yaml
runtime_evidence_script_materialization:
  status: passed | blocked | failed | not_required
  evidence_backed_case_count: 0
  evidence_backed_step_count: 0
  script_materialization_ready_case_count: 0
  candidate_source_files: []
  audit_report: "configs/runtime_evidence_script_mapping_audit.yaml"
  mismatch_count: 0
  blocked_unreleased_candidate_ids: []
  blocked_not_ready_case_ids: []
  assertion_strength_counts: {}
  result_observation_mode_counts: {}
  account_grouping:
    status: passed | blocked | failed | not_required
    group_count: 0
    groups: []
  auth_bootstrap_materialization:
    status: passed | blocked | failed | not_required
    ordinary_pre_business_bootstrap_case_count: 0
    explicit_login_case_count: 0
    flow_first_step_login_count: 0
    duplicate_bootstrap_case_ids: []
    pre_login_token_injection_case_ids: []
    missing_flow_login_case_ids: []
  optional_async_materialization:
    status: passed | blocked | not_required
    default_denominator_excluded: true
    collection_gate: "--run-slow-async"
    wait_override: "--slow-async-wait-seconds"
    case_ids: []
    data_files: []
    pytest_nodeids: []
  case_runtime_isolation:
    status: passed | blocked | failed | not_required
    auth_isolation_case_ids: []
    business_state_isolation_case_ids: []
    ordered_flow_case_ids: []
    isolated_account_case_ids: []
    non_live_case_ids: []
    blockers: []
  minimum_assertion_strength_by_scope:
    live_default: "L2_response_field"
    long_chain_or_write: "L3_business_observable"
    high_risk_or_cleanup_sensitive: "L4_persistence_verified"
  generator_materialization_defects: []
  next_stage_allowed: true
```

Set `status: not_required` only when no generated runnable case uses runtime evidence, supplemental request/result evidence, or runtime value catalog values.
