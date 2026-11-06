# Runtime Failure Diagnosis

Use this reference before rerunning a broad generated suite after failures, and whenever a report shows many failed or broken API cases. The goal is to separate real interface defects from generator defects, execution-state defects, and environment/auth contamination.

## Classification Rules

- Diagnose and repair failures within the same chain first. A failed `flow_id` or `case_id` may justify changes to its ordered steps, producer/consumer variables, setup/cleanup, role context, and shared utility code that demonstrably affects that chain. It must not trigger expectation, cleanup, or request-payload rewrites for unrelated chains unless the same root cause is independently reproduced there or the user requested full-suite repair.
- `broken` with unresolved `${variable}` is a script-generation defect unless the variable is explicitly documented as a required runtime environment variable. Redacted placeholders such as `RUNTIME_*_REDACTED` are not runnable values.
- HTTP 200 with business failure code is not an HTTP status defect. If an exception branch expected HTTP 500 but the API returns HTTP 200 plus business code, fix the executable expectation to the actual contract.
- `forced logout`、`token expired`、`login expired` after login/auth cases usually means shared session contamination. Re-authenticate or refresh the active role context before continuing; do not classify downstream cases as product defects until this is ruled out.
- Repeated `system error` across unrelated endpoints usually means request role, account state, setup data, DB state, or dependency state is not closed. Confirm with request body, account role, DB before/after evidence, and source rules before filing product defects.
- A passed case whose response is `system error` or another generic failure is only acceptable when it is an explicit negative case with source-bound expected code/message. Otherwise treat it as weak or false-positive coverage.
- HTTP 500 is a confirmed product defect only after generator defects, stale reports, wrong run path, dependency/config mismatch, auth/session contamination, crypto-context mismatch, and unclosed setup/cleanup state are ruled out, and the run has complete plaintext request and response evidence.
- If a later rerun with corrected precondition, role, auth, or crypto context returns the expected business code, exclude the earlier failure as a false positive and record the superseding evidence id.
- If the original runtime evidence request and expected response pass but the generated script fails with different request values, role values, or expected business code/message, classify it as a runtime-evidence script materialization defect and fix generated data before product-defect triage.
- When a mutating request fails with timeout, TLS/SSL EOF, connection reset, proxy disconnect, or another transport exception, classify the write outcome as ambiguous. A later unresolved response-id cleanup error is a cascading script-lifecycle defect, not a database-connectivity defect and not independent product evidence. Preserve the transport exception as the primary failure, run request-key fallback cleanup and independent snapshot restores, and report any remaining cleanup/final-verify errors as secondary lifecycle failures.
- A health-check or read-only interface returning HTTP 500 is a high-priority defect candidate when expected HTTP 200 is source-bound, but it remains a candidate until the original response body is retained or the service contract says an empty 500 body is the complete response.

## Role And Login Rules

- If any case step declares `session_role`, the generated framework must have an `auth_roles` registry for every referenced role, including `default` or an explicit alias such as `default: female`.
- Each role auth context must maintain its own token, session secret, user id, hash user id, and runtime context. It must also publish role aliases such as `${male_user_id}` or `${female_user_id}` from the real login response when cross-role business fields need a target user. A mixed male/female/default suite must not use one global token/userId for all roles.
- Before each step, resolve `${login_user_id}`、`${auth_token}`、`${session_secret}`、`${hash_user_id}` from the active step role, then merge environment/runtime variables. Role-specific values override global defaults.
- Login/auth endpoints used as ordinary cases must be isolated: a successful login response must refresh the active role's token/session/user context, or the suite must reacquire auth before subsequent cases. Do not let a login test invalidate all following cases.

## Placeholder And Assertion Gates

- Every `${variable}` in generated case data must resolve from one of: active role auth context, environment config, deterministic runtime generator such as `nowIso`, prior step extraction, or explicit process environment reference `${env.NAME}`.
- If `${env.NAME}` appears, the final run instructions and runtime usability status must list the required env var. Missing env vars are blockers, not ignored literals.
- Support known semantic aliases only when defined, for example `${session.userId}` may map to the active role's `login_user_id`, and `${role_user_id}` may map to a configured/logged-in role's user id. Unknown dotted placeholders block.
- Do not place long-chain aggregate paths such as `$.chain.steps[*].code` in ordinary single-interface assertions. Use them only in flow-runner output or explicit chain summary objects. Single-interface responses should assert their own decoded payload paths such as `$.code`.

## Report Review Workflow

1. Count passed/failed/broken from Allure summary.
2. Declare validation scope: `same_chain_patch` for one flow/case and its dependencies, `selected_subset` for a named subset, or `all_generated_cases` for broad suite repair.
3. Group failures by status details, actual business code/message, module, path, `flow_id`/`case_id`, and `session_role`.
4. Inspect the bounded, redacted pre-decryption response metadata/body and decode-failure context before changing expectations. Treat missing diagnostics as a framework observability gap, not evidence that the service returned an empty response.
5. Identify whether failures start after login/auth cases; if yes, fix session isolation first and rerun the affected chain before product-defect triage.
6. Static-scan generated data for unresolved placeholders, missing role auth, chain paths in ordinary cases, and HTTP 500 expectations on business-error APIs.
7. If failures involve evidence-backed cases, run the runtime-evidence script materialization audit and compare generated request/assertion values with the candidate evidence before changing expectations or filing defects.
8. Only after script and execution-state defects are removed, classify stable remaining mismatches as candidate product defects.
9. Promote a candidate to a confirmed defect only when `缺陷列表.md` can include real scenario, complete plaintext request, complete plaintext response, expected/actual result, and DB table/field changes if persistence changed.

Record this review in `generation_status.yaml.runtime_failure_diagnosis` when a report is analyzed:

```yaml
runtime_failure_diagnosis:
  status: passed | blocked | needs_rerun
  failed_count: 0
  broken_count: 0
  generator_defect_count: 0
  auth_session_contamination_count: 0
  precondition_or_data_state_count: 0
  candidate_product_defect_count: 0
  confirmed_product_defect_count: 0
  excluded_false_positive_count: 0
  validation_scope:
    scope_type: same_chain_patch | selected_subset | all_generated_cases
    target_flow_ids: []
    target_case_ids: []
    changed_shared_files: []
    unrelated_chain_change_count: 0
  defect_list_path: ""
  required_fixes: []
```
