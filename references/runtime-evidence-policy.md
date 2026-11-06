# 运行时取证与补值策略

## 目录

- [读取时机](#读取时机)
- [阶段位置](#阶段位置)
- [规则正文](#规则正文)
- [Full Runtime Evidence Orchestration Contract](#full-runtime-evidence-orchestration-contract)
- [Runtime Requester Evidence Contract Gate](#runtime-requester-evidence-contract-gate)
- [Historical Shape Reference For SQL Setup](#historical-shape-reference-for-sql-setup)
- [Business Result Observability And Assertion Strength](#business-result-observability-and-assertion-strength)
- [Write-Side Cleanup Boundary](#write-side-cleanup-boundary)
- [Runtime Evidence Continuation And Priority Policy](#runtime-evidence-continuation-and-priority-policy)
- [来源](#来源)

## 读取时机

仅当用户要求 direct requester、广覆盖执行级补值、runtime evidence 补值，或执行级事实引用 live request evidence 时读取。若用户要求从源码推导剩余真实入参、按规则补候选值、真实请求验证或失败回填队列原因，同时读取 `references/source-derived-runtime-inputs.md`。

## 阶段位置

运行时取证只能发生在 `04-design-case-handoff/` 之后、`05-executable-interface-case-set/` 之前。`$executable-interface-case-set` 只能消费归一化后的 runtime sidecar，不能自己请求接口；`$api-test-framework-generator` 也不能重新请求接口。

## 执行前安全检查

`run_live_request_evidence.py` 在发出每个请求前校验授权、`expected_status` 和清理方案。名称、注释、来源引用中的 `auth`、`verify` 等词不授予写权限；常规登录路径保留兼容，其他已确认鉴权接口使用显式 `request_decision: request_allowed_with_user_config` 和有来源理由的无清理豁免。

有写入副作用的请求需要 `request_decision: request_allowed`、`request_allowed_with_user_config` 或运行级写授权。未知决策不能执行。需要清理时，`cleanup` 必须包含本次运行的 `ownership_key`、响应丢失时仍可用的 `failure_path_ownership`、引用后续实际计划步骤的 `step_ids` 和 `verification_step_ids`。清理、验证步骤仍按原计划顺序执行，失败请求不会跳过后续使用请求已知归属键的清理；不得只填一个文档引用来代替可执行动作。

```yaml
cleanup:
  required: true
  ownership_key: request.body.run_marker
  failure_path_ownership: request.body.run_marker
  step_ids: [cleanup_current_run]
  verification_step_ids: [verify_zero_residue]
```

引用步骤必须提供 `module`、`method`、`path`、`expected_status`；清理写动作需显式授权，最终验证为只读且声明 `assertions_ref` 和可执行的 `response_assertions`，例如 `{"$.remaining": 0}`。清理或最终验证失败会阻止本批取证向下游准出，不能仅凭文档引用声明验证通过。清理动作本身可声明 `cleanup_required: false` 与 `cleanup_exemption_reason: current-run cleanup action`，避免递归清理。业务请求仅在来源证明无持久副作用、隔离或其他原有豁免成立时声明 `cleanup_required: false` 并给出 `cleanup_exemption_reason`；`cleanup: {required: false}` 也必须附带理由。

请求和响应始终使用真实运行值，脱敏只作用于归档与诊断。取证器与生成模板共用 `core/security_redaction.py`，覆盖下划线、短横线、驼峰敏感字段、提取值、嵌入 JSON 文本及已知 secret 的异常回显，同时保留提取路径等结构信息。

## 规则正文

## Full Runtime Evidence Orchestration Contract

When the user asks for full execution-level case generation, broad executable coverage, or requester-backed runtime completion, the suite must add a runtime evidence planning gate before any direct request. This gate expands the design/execution denominator into a safe evidence plan instead of blindly calling every interface.

Runtime requester scope for required long chains:

- When `required_chain_flows.yaml` contains required flows and the user asks for requester-backed runtime completion, the runtime evidence plan must target full ordered-step coverage for every required flow, plus only the login/auth/setup/verification steps needed to execute those flows. Do not satisfy long-chain runtime evidence with a few convenient interfaces, and do not expand the scope to endpoints found only by broad route scanning.
- Each planned long-chain step must preserve `flow_id`, `step_order`, method/path, producer/consumer relation, link keys, source refs, risk decision, DB probe or cleanup requirement, and whether the step is requestable, externally mocked, callback-provided, manually confirmed, or blocked.
- Only `request_allowed` and `request_allowed_with_user_config` steps may be executed. External, callback, payment/settlement, destructive, or missing-cleanup steps must stay as blockers or manual/sandbox/mock/callback input items until their evidence is complete. Partial runtime evidence may help execution filling, but it must not mark the required flow passed.

Runtime evidence planning must produce `04-runtime-evidence-plan/` sidecars:

- `runtime_risk_audit.yaml`: every design or executable candidate is classified as `safe_readonly`、`auth_setup`、`mutation_requires_cleanup`、`destructive_state`、`external_or_callback`, or `unknown_requires_review`, with reason codes and source refs.
- `runtime_request_plan.skeleton.yaml`: only candidates with `request_decision=request_allowed` or `request_allowed_with_user_config` may appear as requester candidates; all credentials, base URLs, tokens, dynamic IDs, request bodies, and secrets remain runtime-injected placeholders.
- `db_before_after_probe_plan.yaml`: every mutating, destructive, or cleanup-dependent candidate records required DB before/after snapshot, ownership key, expected delta source, and cleanup strategy requirements.
- `runtime_blocker_candidates.yaml`: unsafe, external, destructive, missing-cleanup, or insufficiently traced candidates become blocker or manual confirmation items instead of guessed executable facts.

Classification must stay generalized. It may use HTTP method, path/name semantics, case type, contract channel type, source-visible DB side effects, dependency type, and cleanup evidence. It must not hardcode project-specific base URLs, phone numbers, accounts, user IDs, open IDs, tokens, app keys, AES keys, business codes, enum values, table names, or one-project-only status meanings. If a source artifact contains such values, copy them only into run-specific execution configuration or runtime evidence outputs with redaction rules; never add them to this skill.

### Runtime Requester Evidence Contract Gate

Every direct requester observation that may feed execution-level cases, generated scripts, defect triage, or downstream value propagation must persist script-generatable evidence. This is a hard gate for live pytest denominators; a status summary, response shape summary, or runtime value catalog entry alone is not enough.

For each executed step, save these generalized fields or exact equivalent fields:

- Identity: `case_id` or `flow_id`, `step_id` or `step_order`, `module`, `method`, `path`, and `base_url_alias`.
- Runtime context: `session_role`, `auth_policy`, token injection location/format, and any role/account context consumed by the request.
- Plaintext request: path/query/header/body after variable resolution and before transport encryption. Redact secrets with stable placeholders, not empty strings.
- Plaintext response: HTTP status, business code, message, decoded/decrypted `data` shape, key business fields, and complete response body or a bounded plaintext response reference when the body is too large.
- Assertion candidates: HTTP status, business code/message, field existence, field value, array length, state transition, producer-consumer variable, and business-result verification candidates.
- Setup data: setup method, setup source, API/SQL action if required, produced variables, and `not_required` reason when no setup is needed.
- Cleanup data: cleanup method, ownership key, API/SQL/restore/snapshot action if required, cleanup verification method, and `not_required` or `non_live` reason when no cleanup will run.
- DB evidence when required: DB alias, source-chain table scope, selected fields, ownership key, before/after refs, delta summary, and cleanup proof. Do not store DB credentials here.
- Business input quality: for positive-path, live, long-chain, or page-visible fields, record whether values are source-bound legal values or bounded generic real-world legal samples allowed for ordinary user-entered/display fields. Generic samples are not valid evidence for IDs, status transitions, enum codes, amounts, permissions, relationship keys, or external dependency values. Obvious placeholders are evidence gaps unless the case is explicitly an invalid-value scenario with matching error assertions.
- Script readiness: `script_materialization_ready: true|false`, `missing_materialization_items: []`, `assertion_strength`, `result_observation_mode`, and evidence refs.

Set `script_materialization_ready=false` when the requester did not retain a complete plaintext request/response, role/auth/token placement, executable assertion, required setup, required cleanup, or required observability proof. Such evidence may remain useful for manual review or retry queues, but it must not be counted as live pytest ready.

Setup and cleanup are classified, not blindly required for every case. Pure read-only, auth bootstrap, no-op validation, runtime no-delta, or sandbox-isolated steps may record `setup.required=false` or `cleanup.required=false` only with a source/runtime reason and an assertion boundary.

### Historical Shape Reference For SQL Setup

When runtime evidence or execution filling decides to use SQL setup, the setup value set must be checked against bounded historical shape evidence before the case can become `script_materialization_ready=true`.

The evidence must be generalized and privacy-safe:

- Inspect a small, scoped set of same-table and same-business-state rows, or consume an equivalent normalized DB evidence sidecar that was built from those rows. The scope must be source-chain related and bounded by business status, non-deleted state, role, or recent valid data when such filters exist.
- Record only structural facts: table, sampled field list, sample count, enum/status values, JSON key shape, null/empty conventions, date/time format, timezone convention, parent-child relationship keys, and actor/counterparty constraints. Do not copy secrets, identity numbers, personal contact data, payment data, free-form private content, or raw full rows into generated artifacts.
- Treat historical rows as shape evidence, not as data templates. The inserted or updated row must still use current-run IDs, ownership keys, cleanup IDs, generated unique values, and source-bound role variables.
- Page-visible or user-visible business fields must use legal business-readable values. Do not put trace markers such as `run_marker`、`lc015_keep_...`、`UNKNOWN`、technical task labels, or malformed strings into fields that an app/admin page displays, unless the case is explicitly an invalid-value scenario and asserts that validation failure.
- Relationship fields must match source and historical semantics. If the business action is cross-role, such as consumer subscribes to provider, sender sends to receiver, reporter reports target, or male subscribes to female, the setup evidence must prove which column is actor and which is counterparty; self-relations are forbidden unless the error branch intentionally tests self-action.
- Time windows and status transitions must be derived from source behavior plus historical/runtime evidence. If application code uses JVM/application time and DB uses another timezone, do not rely on DB `NOW()` alone; record the chosen time convention or block the setup.

SQL setup evidence should include `historical_shape_reference` or an equivalent section with `status: passed`, `source_ref`, `sampled_table`, `sample_scope`, `sample_count`, `verified_fields`, and `privacy_status: sampled_shape_only_redacted`. Missing or failed historical-shape evidence is a setup-quality blocker, not a product defect.

### Business Result Observability And Assertion Strength

Database assertions are not a blanket requirement. The required invariant is that the business result is observable.

Choose the strongest available observation path in this order:

1. Follow-up API/detail/list/status/relationship/message/profile queries that prove the business result.
2. DB assertion through scoped SELECT only when the business result is not API-observable, the API response is too weak, or cleanup/final state can only be verified in persistence.
3. Non-live/manual review when neither API nor DB can safely observe the result.

Record `assertion_strength` for every scriptable evidence item and generated case:

- `L1_basic`: HTTP status plus business code only.
- `L2_response_field`: L1 plus key response fields, field existence, values, or array length.
- `L3_business_observable`: L2 plus follow-up API verification of the business state/result.
- `L4_persistence_verified`: L3 or equivalent API verification plus scoped DB before/after or SELECT persistence assertion.
- `L5_cleanup_verified`: business verification plus API/DB cleanup verification or state restoration proof.

Live automation should reach at least `L2_response_field`. Long chains and write-side-effect cases should reach at least `L3_business_observable`. Funds, subscription, settlement, orders, relationship, messages, evaluation, audit, cleanup-only-verifiable, callback, and final-state-sensitive cases should reach `L4_persistence_verified` or `L5_cleanup_verified`. If a case remains only `L1_basic`, keep it as a connectivity/basic contract check and do not use it to prove the business result.

### Write-Side Cleanup Boundary

Any live case or required flow containing a write-side-effect interface defaults to `cleanup_required=true`. Treat POST/PUT/PATCH/DELETE and source-visible insert/update/delete/status-transition/message-send/upload/audit/order/subscription/evaluation/relationship/settlement effects as write-side-effect candidates until source/runtime evidence proves otherwise.

A write-side-effect case may set cleanup not required only with an explicit exemption reason:

- Source/runtime evidence proves no local persistent side effect or runtime DB/API no-delta.
- The write is contained by a dedicated isolated test account, sandbox, mock, or environment snapshot and cannot pollute shared business state.
- The action is irreversible, async, manual-review-only, third-party-owned, or unsafe to restore, so the case is generated as `generated_non_live` or `manual_review_only`.
- The request failed and DB/API before/after evidence proves no side effect was created.

Cleanup must bind to the current run's exact ownership key, such as response business ID, request business ID, message/order/conversation/evaluation/audit ID, idempotency key, trace ID, or a run-unique marker. Do not use broad cleanup predicates such as deleting all rows for a user unless the run created an isolated user and the ownership key boundary proves the cleanup is exact.

Runtime execution configuration must be collected before requester-backed filling or execution-level release when environment, account, auth, or crypto facts are not fully source-bound:

- Use `components/executable-interface-case-set/assets/templates/runtime_execution_config.template.yaml` as the canonical user-facing template. The template must label fields with requiredness, conditional requiredness, and real meaning so users can fill it without reading this skill.
- When any required runtime section is missing, materialize the fillable package under `00-inputs/`: `runtime_execution_config.template.yaml`, `前置执行配置待填写.md`, and `runtime_execution_config.missing_fields.yaml` when the missing fields can be enumerated. The Markdown document must include these Chinese sections: 环境信息、模块 base URL 与网关前缀、账号与角色及业务状态、鉴权与 token 提取/注入、加解密策略、执行授权范围、DB before/after 与清理授权、外部依赖或沙箱/Mock、必填缺失字段清单、填写后继续条件。
- Continue only after the user returns a filled YAML, Markdown, or equivalent structured artifact whose required fields pass validation. Resume from execution readiness or execution-level filling; do not rerun source/design stages unless upstream source or design inputs changed.
- The environment section is always required for `executable` and `framework` targets: `env_name`, `is_test_environment`, module `base_url`, and gateway prefix must be filled or explicitly empty where the meaning allows an empty string.
- Account entries are required for every business role needed by selected cases or required flows, and each account must record its real business state, login method, identifier secret reference, and credential/token secret reference when applicable.
- Auth and transport-crypto configuration must identify login path, token source, token injection location/format, encryption enablement, algorithm reference, key source, request plaintext scope, request serialization, request envelope, and response envelope whenever encrypted interfaces are confirmed.
- If `environment.is_test_environment=true`, the case-scope default execution authorization and the generic source-bound DB before/after plus current-run cleanup authorization may be used when explicitly selected in the filled config.
- If `environment.is_test_environment=false`, any prior or default test-environment DB permission is invalid for this run. DB before/after queries, cleanup, rollback, or status recovery require fresh explicit non-test authorization in the filled config, including scope, environment, source-chain table boundary, ownership key boundary, and cleanup boundary. Without that reauthorization, keep DB operations and any facts depending on them blocked.
- Runtime execution configuration may contain real environment values and secret references, but runtime evidence and execution-level deliverables must redact passwords, tokens, Authorization, Cookie, raw secrets, and equivalent sensitive values.

Database MCP is used to build the full data model and cleanup graph, then to support before/after evidence collection when the user permits it. The generated scripts and executable-case stage may consume only normalized sidecars such as `数据模型.md`, `database_mcp_evidence_index.yaml`, `source_db_alignment.yaml`, `runtime_evidence.yaml`, and `runtime_value_catalog.yaml`; they must not keep live MCP database calls.

Source-to-database runtime evidence must close the loop before a mutating long-chain case can be marked executable:

- First extract the interface-to-table write/read scope from source evidence: Controller -> Service -> Repository/Mapper call chains, Mapper XML, annotated SQL, repository methods, and MyBatis/JPA entity table mappings.
- Then use database MCP to confirm the test-environment tables and columns exist and are compatible with the source-visible facts.
- Before executing the request or chain step, capture DB before snapshots only for the source-involved tables. After execution, capture DB after snapshots for the same scoped tables.
- Compare before/after deltas to confirm the real affected tables, changed fields, new business IDs, status transitions, amount changes, relationships, or records. Persist the request, response, DB refs, delta assertion, ownership key, cleanup evidence, and source refs into `runtime_evidence.yaml`.
- Do not rely on source analysis alone to claim a runtime DB side effect. Source analysis selects the candidate table scope; DB MCP and before/after deltas confirm what actually changed.

DB before/after and cleanup must use the minimal source-bound scope:

- Only inspect and clean tables explicitly involved by the current interface or required flow source chain: Controller -> Service -> Repository/Mapper, Mapper XML, annotated SQL, repository query/update methods, or entity table mappings. Do not scan or clean unrelated tables.
- Before/after query predicates must use the first available ownership key in this order: business ID returned by the current response, business ID in the current request, authenticated `userId`/`appUserId`, then a unique business key such as order number, conversation ID, idempotency key, or another source-evidenced unique value.
- If no ownership key or unique marker can be identified, block the DB probe or cleanup with `BLOCKED_NEED_EXECUTION_INPUT`; do not broaden the query scope.
- Cleanup may delete or restore only records created or changed by the current run. Prefer response-extracted IDs such as `id`、`orderId`、`messageId`、`auditId` or source-equivalent business IDs; otherwise require test account plus current-run unique marker.
- Cleanup order must follow the table relationship graph in reverse: child/detail/ledger/relation records before parent/order/master records. User, account, configuration, and other baseline tables must not be cleaned unless the current run created an isolated record and the ownership key is exact.
- High-risk domains such as payment, withdrawal, subscription, review, scheduler, callback, and settlement may be queried and cleaned only inside the current-run source-bound table scope and isolated ownership keys. Wide deletes such as deleting all rows by `userId` or other broad predicates are forbidden.
- A user or run configuration may grant the generic boundary "allow before/after queries and cleanup for source-chain involved tables, limited to current-run IDs or unique ownership keys"; this reduces manual confirmations but does not relax the ownership-key, delta, and cleanup-order gates.

Case-scope execution authorization may be configured once per run:

- When the user or run configuration explicitly declares that selected/generated test cases are executable by default and the target environment is test by default, treat only those case-scoped interfaces and ordered steps as execution-authorized. Record the declaration in `runtime_risk_audit.yaml` and `execution_fact_sources.yaml` as `source_type: user_config`.
- This default authorization removes per-interface manual execution confirmation for in-scope write, payment, withdrawal, subscription, review, scheduler, callback, and other mutating steps, but it does not permit blind execution outside the selected case denominator, production-like environments, or endpoints discovered only by broad route scanning.
- Even with default authorization, every executed step must still satisfy environment, auth, transport/encryption, external sandbox or mock input, source-bound DB before/after, ownership key, delta assertion, cleanup boundary, and redaction gates before it can be marked `PASSED`.
- If credentials, sandbox data, callback signatures, upload assets, ownership keys, DB delta, cleanup evidence, service responses, or source/DB alignment are missing or conflicting, keep the affected item blocked; do not use case-scope authorization to invent executable facts.

Direct requester execution is risk-gated:

- It may execute only the allowed items from `runtime_risk_audit.yaml`.
- For required long chains, execute allowed steps in business order and persist both step-level request/response evidence and the producer-to-consumer value derivations. The requester should attempt every requestable ordered step in the required flow before declaring the runtime evidence scope complete.
- Use real responses as evidence for inference, not as mechanical literals. Compare producer response fields, required-flow link keys, consumer request schema, authenticated account context, source contract semantics, and DB ownership keys to infer current request inputs, downstream request inputs, and expected next-response/assertion candidates. If the business meaning does not match or multiple candidates remain plausible, block the derivation instead of filling a value.
- Mutating requests require an isolated ownership key, DB before/after probe plan, cleanup strategy, and explicit user or run configuration confirmation before execution. A run-level case-scope execution authorization satisfies the confirmation requirement only for the selected case denominator in the configured test environment.
- External callbacks, payment/settlement-like actions, destructive state changes, and missing-cleanup cases must be blocked or routed to manual confirmation.
- Each executed interface must produce `runtime_evidence`: request reference, response reference, extracted variables, assertions, redaction status, source refs, and when DB evidence is used, `db_before_ref`、`db_after_ref`、`db_delta_assertion`、`db_probe_source_ref`.
- `$executable-interface-case-set` may mark execution facts `PASSED` only when evidence is closed: request/response evidence confirmed, variable links resolved, assertions source-bound, DB before/after/cleanup evidence present when required, and conflict lists empty. Otherwise it must emit `BLOCKED_NEED_EXECUTION_INPUT` or manual confirmation items.

### Runtime Evidence Continuation And Priority Policy

Requester-backed supplementation must be queue-driven, not stop-on-first-gap. When the user asks to supplement broad execution-level cases, requested observations, or all runnable candidates, maintain a continuation queue in `04-runtime-evidence/runtime_stage_status.yaml.continuation_queue`; when the queue is large, also write the same queue to optional `04-runtime-evidence/runtime_evidence_queue.yaml`. Each candidate or ordered chain step must record `case_id` or `flow_id + step_order`, `priority_bucket`, `queue_state`, `last_attempt`, `next_action`, `reason_code`, and `evidence_refs`.

Queue states are operational states, not overall pipeline statuses: `pending`、`requested`、`evidenced`、`retryable`、`skipped_recoverable`、`blocked_final`、`excluded`. Queue items must use `queue_state`; do not use a nested `status` field inside `continuation_queue.items` or `runtime_evidence_queue.yaml.items`, because `status` is reserved for stage-level sidecars. A single item in `retryable` or `skipped_recoverable` must not stop the whole runtime-evidence stage while other actionable items remain. Stop only when no `pending`、`retryable` or `skipped_recoverable` item remains, or when every remaining item is a true blocker or excluded by scope.

Supplement runtime evidence in this priority order:

1. Required or real-business long chains first. Execute every requestable ordered step in each business flow, close producer-to-consumer variables, assertions, DB before/after evidence, and cleanup boundaries, then reuse the confirmed step evidence for related single-interface candidates.
2. `p0` single-interface or branch cases after long-chain closure, prioritizing auth/setup/read-only prerequisites before mutating cases that need cleanup.
3. `p1` cases after `p0` actionable items are exhausted.
4. `p2` cases after `p1` actionable items are exhausted.
5. `p3` and low-value leftovers last, unless the user narrows the requested scope.

Within the same priority bucket, prefer cases whose request structure, auth, encryption, upstream variables, data model, DB ownership key, assertions, and cleanup strategy are already source-bound. For mutating cases, only execute after the source-bound DB before/after probe plan and current-run cleanup boundary are available.

These are not runtime-evidence blockers by themselves and must become `retryable` or `skipped_recoverable` while the queue continues: runtime evidence has not been generated yet; one case fails while other cases remain; one subset lacks assertion or DB before/after evidence; a request returns an unexpected 200 or 500 and needs defect triage; an input value is missing but source, DB MCP, requester response, bounded mock, precondition API, or execution configuration can still be tried; a single candidate is temporarily not requestable.

True runtime-evidence blockers are narrower: execution authorization is missing for the selected denominator; required environment/account/auth/crypto configuration is still absent after the fillable package is produced; the item is outside the selected case or required-flow scope; the item is external/callback/payment/destructive and lacks sandbox, mock, signed callback, ownership, or cleanup evidence; DB MCP/source/data-model evidence cannot provide the required model, ownership key, assertion, or cleanup boundary; source/contract/runtime/DB evidence conflicts; or a gate explicitly forbids continuing.

When an item cannot be solved immediately, write the attempted methods and the exact unresolved reason, mark it `skipped_recoverable` or `blocked_final` as appropriate, and continue with the next item in priority order. Do not convert unresolved items into guessed request fields, guessed response assertions, broad DB seeds, or product defects. Unexpected 200/500 results become defect candidates only after the request payload, response payload, role/session, data state, and DB before/after evidence prove the generated script or request materialization is not the cause.

Use `scripts/build_runtime_evidence_plan.py` when a deterministic helper is useful:

```bash
python3 <skill_dir>/scripts/build_runtime_evidence_plan.py \
  --case-list 04-design-case-handoff/case_list.yaml \
  --output-dir 04-runtime-evidence-plan \
  --env-name test
```


## 来源

本文件从 `SKILL.md` 原主契约拆分而来；完整历史契约保存在 `references/full-contract.md`。
