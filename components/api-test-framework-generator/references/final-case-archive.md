# Final Case Archive Artifact

Use this reference whenever the framework generation stage writes final reviewer/archive artifacts, normally `api-test-framework/接口案例.md` and, after runtime failure triage, `api-test-framework/缺陷列表.md`.

## Purpose

- Produce a human-readable case ledger for review and filing after execution-level cases and pytest/allure scripts are generated.
- Produce a separate Markdown defect list only after runtime evidence is reviewed. Do not mix confirmed product defects into executable case ledgers.
- This artifact is not a project README and must not explain how to use the framework. It records source-bound cases, requests, responses, assertions, and long-chain steps in a tester-readable form.
- Generate it from normalized execution-level artifacts and generated case data only. Do not call live APIs, query MCP services, read runtime secret files, or invent missing values while writing the archive.

## Required Sources

- `执行级接口用例集.md`
- `前置数据构造规则.md`
- `execution_fact_sources.yaml` when present
- Generated `api-test-framework/data/interfaces.*`
- Generated `api-test-framework/data/cases/*`
- Generated `api-test-framework/data/flow_cases.*` when E2E flows exist
- `api-test-framework/configs/generation_status.yaml`

## Required Content

- Scope statement: generation time, denominator type, executable case count, interface count, E2E flow count, excluded count, and exclusion reasons.
- Traceability for every case: case ID, design-level case ID, coverage object IDs, coverage rule IDs, traced test point IDs, priority, feature/story, flow type, source refs, and evidence refs.
- Confidence for every case and flow: show only `置信度分数` and `置信度等级` in the human archive, copied from generated machine data without manual reinterpretation. Keep all calculation dimensions, reason codes, hard caps, relevance, scope, and evidence refs in machine-readable case/status files. Put score and level in that case or flow's own archive section and wrap them in one stable `CASE_CONFIDENCE_INLINE:<case-or-flow-id>` block. A summary/index table is optional, should default to identity + score + level only, and cannot substitute for inline fields.
- Plaintext request model: method, path, module/base-url alias, path/query/header/cookie/body parameters, merged common parameters, business parameters, variable placeholders, and precondition values in plaintext business form. Preserve scalar/list/object/map shapes, nesting, array order, `null`, and intentional omission; show serialized JSON/text only as a confirmed transport or persistence boundary note.
- Plaintext response model: expected HTTP status, business code/message, decrypted `data` shape when encryption is used, required response fields, JSONPath assertions, database assertions, and cleanup expectations. Do not describe assertions as status-code-only when the script verifies response fields, follow-up APIs, DB fields, cleanup, or derived formulas; if a machine assertion is hard to list exactly, state the verification method in tester-readable natural language.
- Long-chain sections: for each flow, list `flow_id`, title, required denominator source, ordered step number, source case ID, interface, producer fields, consumer fields, extraction rules, injection targets, step request, step response/assertions, setup, and cleanup.
- Optional async sections: list each `optional_async` case separately from the default executable denominator, including explicit collection flag, default wait seconds, wait override, source evidence, request/response assertions, post-wait API or DB observability, and cleanup/no-delta strategy.
- Non-live/manual-review sections: list each `generated_non_live` and `manual_review_only` candidate separately from the executable denominator, including source reason, assertion/observation boundary, missing live-execution evidence, and why it must not issue live API requests by default.
- Setup/cleanup materialization: for mutable cases, record whether cleanup is executable API cleanup, executable SQL cleanup, or explicit no-cleanup. `cleanup_refs` alone must be shown as non-runnable evidence, not as completed cleanup.
- Post-confirmation placeholders: only fields already classified as post-confirmation may be left blank. Mark them in `待补字段` with case ID, step number, field path, reason, and required source.

## Defect List Artifact

When writing `缺陷列表.md`, use Markdown and separate sections:

- `已确认缺陷`: only issues with complete evidence.
- `待补完整出参后确认的缺陷候选`: failures with status/code/shape but without full response body or DB before/after.
- `已排除的误报`: failures superseded by a later correct precondition, role, auth, or crypto-context rerun.
- `其他待环境或请求配置确认项`: failures that may come from external dependency, environment, stale generated code, or unclosed setup data.

Each confirmed defect must include real scenario, source case or flow/step id, method/path, complete plaintext request, complete plaintext response, expected result, actual result, evidence refs, and DB table/field changes when persistence changed. DB changes must name database, table, id/ownership key, changed fields, before value, after value, and cleanup result.

Do not mark a defect confirmed when only response status, response shape, or redacted summary is available.

## Plaintext And Secret Rules

- "Plaintext" means decrypted/unenveloped business request and response data suitable for test review. It does not mean printing raw secrets.
- Do not archive raw SMS codes, passwords, tokens, session secrets, AES keys, private keys, DB credentials, Authorization/Cookie values, or ciphertext.
- Use stable placeholders such as `${auth_token}`, `${session_secret}`, `${sms_code}`, `${env.APP_TRANSPORT_KEY}`, or `${runtime_context.user_id}` for secret-bearing fields.
- If the transport uses whole-body encryption, archive the pre-encryption dictionary and note that the generated client encrypts at send time.
- If the response uses encrypted `data`, archive the decrypted response shape and assertions, not the ciphertext string.

## Validation Gate

- Every generated pytest case in `generation_status.yaml.pytest_collection_mapping` has exactly one archive entry.
- Every required flow in `generation_status.yaml.e2e_flow_mapping` has exactly one archive long-chain section and preserves ordered steps.
- Every generated case and flow has exactly one inline archive confidence block matching machine data; `archive_missing_confidence_case_ids` must be empty. Aggregate confidence indexes do not satisfy this per-entry gate.
- Archive case count equals the executable denominator declared in `generation_status.yaml`; missing IDs must be listed and block `final_case_archive.status=passed`. Non-live/manual-review and optional async cases are counted in separate sections and must not change the default executable denominator unless the user explicitly requests that denominator change.
- No generated entry may contain only ciphertext, empty request bodies, guessed response assertions, or unresolved placeholders except approved secret placeholders and explicitly listed post-confirmation blanks.
- Generated collection artifacts, when produced from the same framework output, must match the archive and script data for method/path, plaintext request shape, expected business code/message, key response assertions, variable extraction, and long-chain step order.
- Search the archive and changed source files for Chinese mojibake markers before final reporting.
- Record the result in `api-test-framework/configs/generation_status.yaml`:

```yaml
final_case_archive:
  status: passed
  path: 接口案例.md
  plaintext_request_response: true
  secret_redaction: passed
  case_count: 0
  flow_count: 0
  optional_async_case_count: 0
  non_live_case_count: 0
  manual_review_only_case_count: 0
  generated_non_live_case_ids: []
  manual_review_only_case_ids: []
  missing_archive_case_ids: []
  missing_archive_flow_ids: []
  unresolved_post_confirmation_fields: []
case_confidence_gate:
  status: passed
  candidate_case_count: 0
  declared_confidence_case_count: 0
  high_count: 0
  medium_count: 0
  low_count: 0
  missing_confidence_case_ids: []
  invalid_confidence_case_ids: []
  low_confidence_live_case_ids: []
  archive_missing_confidence_case_ids: []
defect_list:
  status: passed | blocked | not_required
  path: 缺陷列表.md
  confirmed_defect_count: 0
  candidate_defect_count: 0
  excluded_false_positive_count: 0
  missing_full_response_case_ids: []
  missing_db_before_after_case_ids: []
```

If any validation item fails, set `final_case_archive.status: blocked`, keep generated scripts' own status separate, and report the exact missing case IDs, flow IDs, or field paths.
