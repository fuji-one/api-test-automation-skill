---
name: api-automation-pipeline-suite
description: Run a self-contained, gated Chinese API automation pipeline from either complete PRD/API/system-analysis/data-model documents or Java source code into design cases, execution-level cases, and pytest+allure scripts. Use when Codex needs one bundled skill folder that includes the orchestrator plus local component skills for pre-document analysis, source API fact extraction, interface testcase generation, executable case generation, and API test framework generation, while preserving strict stage gates, long-chain denominators, runtime-evidence boundaries, and final-script completion notices.
---

# API Automation Pipeline Suite

## 目录
- [Core Role](#core-role)
- [Fixed Stage Machine](#fixed-stage-machine)
- [Required Loading Matrix](#required-loading-matrix)
- [Non-Negotiable Gates](#non-negotiable-gates)
- [Confusion Points To Mark Explicitly](#confusion-points-to-mark-explicitly)
- [Component Layout](#component-layout)
- [Required Workflow](#required-workflow)
- [Output Boundary](#output-boundary)
- [Final Response Rules](#final-response-rules)

## Core Role

Act as the suite orchestrator, not as a replacement for bundled component skills. Keep the stage state machine stable, load detailed rules only when their stage is reached, and let validators make final pass/fail decisions.

Always resolve resources from this skill directory first. When a stage references `$source-api-fact-extractor` or another component, load `components/<component>/SKILL.md` from this suite before executing that stage. Use a globally installed skill with the same name only if the bundled component is missing, and state that fallback explicitly.

## Fixed Stage Machine

Do not change the stage order during lightweight operation:

```text
preflight
-> entry(doc/source)
-> required chain denominator
-> design cases
-> design-case handoff
-> runtime evidence plan/live evidence(optional)
-> chain execution-readiness reconciliation(if execution facts changed)
-> executable cases
-> framework
-> final validation
```

Target depth controls how far to run:

- `design`: stop after `04-design-case-handoff/`.
- `executable`: continue through `05-executable-interface-case-set/`.
- `framework`: continue through `api-test-framework/`.
- Step-by-step mode: when the user says `一步步来`、`分阶段来`、`先处理到某阶段`、`不要一次跑完`, default to `design` unless an explicit target depth is given, stop at each durable handoff boundary, and wait for the user's `继续`.

## Required Loading Matrix

Read `references/loading-matrix.md` at the start of every run. It contains the full stage-to-reference matrix and the confusion-prone boundaries. Then load only the files required by the active stage:

| Stage | Required detail files |
|---|---|
| Preflight and routing | `references/pipeline-gates.md` |
| Entry sidecars and stage release | `references/sidecar-contracts.md` plus the selected component skill |
| Required chain denominator | `references/chain-flow-contract.md` |
| Design case generation | `components/interface-testcase-generation/SKILL.md`, `references/chain-flow-contract.md`, `references/sidecar-contracts.md`, `references/case-confidence-contract.md` |
| Handoff | `references/pipeline-gates.md`, `references/sidecar-contracts.md` |
| Runtime evidence, if requested | `references/runtime-evidence-policy.md`, `references/source-derived-runtime-inputs.md`, `references/db-mcp-alignment-policy.md` |
| Chain execution-readiness reconciliation | `references/chain-flow-contract.md`, `references/pipeline-gates.md` |
| Executable cases | `components/executable-interface-case-set/SKILL.md`, `components/executable-interface-case-set/references/io-contract.md`, `references/execution-fact-closure.md`, `references/apifox-boundary.md`, `references/case-confidence-contract.md` |
| Framework generation | `components/api-test-framework-generator/SKILL.md`, `components/api-test-framework-generator/references/case-denominator-conservation.md`, `references/case-confidence-contract.md`, and the other component references it instructs you to read |
| Final response and validation | `references/failure-and-completion-policy.md` |

The previous full contract is preserved at `references/full-contract.md` for audit and rollback. Do not load it by default; use it only when checking whether a migrated detail was lost.

## Non-Negotiable Gates

- Preserve 100% coverage release semantics. A stage may block or fail, but must not pass partial coverage downstream as acceptable.
- Keep `stage_status.yaml` and `coverage_matrix.yaml` as machine-readable release evidence for generated stages that feed downstream work.
- Use `business_scenario_map.yaml` and `业务场景链路清单.md` as required structured business-scenario evidence before stage 2.
- Treat `required_chain_flows.yaml` as the only execution/script required long-chain denominator. `business_long_chain_cases.yaml` is the design-level business long-chain denominator.
- Any change to runtime evidence, filled long-chain values, setup/cleanup facts, external sandbox/mock/callback evidence, or another execution-readiness fact invalidates the previous execution/script denominator. Recompute before executable generation or framework release; never preserve a stale zero denominator.
- Determine readiness by capability for the requested target depth, not by project name or one assertion-level label. Valid closure may be proved by write-and-restore, verified read-only behavior, create-delete with zero residue, isolated ownership, sandbox/mock/callback containment, or another source-bound observable-state closure, provided materialization has no unresolved required item.
- Enforce conservation after reconciliation: every execution-ready chain appears exactly once as either generated or explicitly excluded with reason and evidence. `filled_count > 0` cannot pass with `required_chain_flow_count=0` unless every ready chain is explicitly excluded.
- Do not let environment, account, token, DB row, DB authorization, external sandbox, or crypto runtime details block stage 1 or stage 2 when their own source facts are complete. Record those as execution-level pending inputs.
- Do not invent request values, response values, assertions, accounts, token extraction, setup data, cleanup SQL, Apifox responses, environment URLs, database schema facts, or table graph facts.
- Positive-path and page-visible business fields must use source-bound legal values, not obvious placeholders. For user-entered/profile/display fields whose contract permits ordinary legal literals and has no project-specific dictionary, use bounded generic real-world legal samples such as valid region or standard locale-style values. Do not use generic samples for IDs, status transitions, enum codes, amounts, permissions, relationship keys, or external dependency values. Invalid placeholders such as `自动化省`、`测试市`、`UNKNOWN` are allowed only when the case is explicitly an error/validation scenario and the expected assertion targets that invalid value.
- Database MCP and Apifox MCP are evidence sources only. Generated pytest projects must not depend on MCP calls at runtime.
- Runtime live-request evidence belongs only under `04-runtime-evidence/`; executable and framework stages consume normalized sidecars instead of making fresh live requests.
- Direct requester evidence used by downstream executable cases or scripts must pass the runtime requester evidence contract: every scriptable step keeps plaintext request before encryption, decoded plaintext response after decryption, role/auth/token placement, assertion candidates, setup/cleanup classification, optional scoped DB before/after evidence, `script_materialization_ready`, and missing-materialization reasons. Summary-only evidence cannot enter the live pytest denominator.
- Positive-path live requests must satisfy source-visible request validation constraints. Required fields from annotations or equivalent contracts such as `@NotNull`, `@NotBlank`, `@NotEmpty`, OpenAPI required fields, or DTO validation rules must be materialized with source-bound legal values, confirmed configuration/dictionary values, prior runtime values, or explicit user inputs. A positive runnable case may not send `{}` or omit required fields unless the case is explicitly an error/validation branch with matching assertions.
- Validation/error branches must isolate the intended defect. When a branch claims to verify a missing, blank, invalid, or boundary value for one target field, all unrelated source-visible required fields and auth/account context must remain legal and executable, otherwise the case is not valid evidence for that branch.
- Request materialization must stay consistent across ordinary single-interface cases and required E2E flow steps for the same method/path/request variant. A flow step may override values only with source/runtime evidence for role, state, producer-consumer dependency, or explicit branch intent; it must not silently drop required fields or previously validated business parameters from a compatible ordinary case.
- Request shape materialization must preserve source-visible field kinds across scripts, flow data, archive cases, and generated collections: scalar, list/array, object, map, nesting, `null`, and intentional omission remain distinct. Do not stringify an array/object request field or flatten nested data unless the confirmed transport or persistence boundary explicitly requires that representation and records the conversion evidence.
- Multi-account or multi-role runtime execution must group compatible cases by a stable `account_group_key` or equivalent role/account key. Authenticate once per group, reuse the same requester/session/auth context for that group, and record group-level case counts and pass/fail evidence. Per-case requester or per-case login construction is allowed only for login, refresh-token, logout, session invalidation, or explicitly isolated-account test cases.
- Framework generation must materialize that grouping as executable auth bootstrap, not only as documentation: ordinary API runners need an auth-context registry or fixture that logs in before the first business step for each account group and reuses the extracted token/session/user context; required long-chain flows need a visible first `auth`/`login` step that extracts token/account context before business steps. Hidden fixture-only login is valid for ordinary cases, but not for account-specific E2E flows.
- Generated runners must isolate business runtime variables at the ordinary-case or whole-flow boundary while preserving only source-bound account-group auth/session context. Steps inside one flow share their producer/consumer variables; unrelated cases or flows must not inherit prior business ids, timestamps, markers, or extracted payloads.
- Explicit `auth`/`login` steps and ordinary multi-step cases must use source-bound extraction rules, preserve extracted value types, and update the same account-group auth registry consumed by later steps. Do not maintain incompatible extraction/login implementations between ordinary runners and flow runners, and do not infer required token fields from URL naming alone.
- API setup/cleanup fixtures must enter teardown after setup starts, including partial setup failure. Cleanup remains ownership-scoped, continues independent cleanup rules after one failure, and reports cleanup failures without hiding the original request/setup failure. Cleanup role selection must use the same multi-role registry and restore the previously active client auth context afterward.
- Transport diagnostics must retain bounded, redacted pre-decryption response metadata/body and a bounded decode-failure context when encrypted response decoding fails. Attachment limits and envelope fields stay configuration-driven; redact Authorization, cookies, API keys, tokens, identity values, and secret-bearing exception text before logs or Allure attachments.
- Account grouping solves requester/auth reuse only; it is not business-state isolation. `reauth_before_case` may be used only for token/session/context pollution when a source-bound dynamic auth contract exists. If same-account cases contain write side effects, one-time actions, order dependencies, quota/balance/task progress changes, or account-state transitions, require cleanup/restore, isolated accounts, explicit execution order, or conversion to a flow before live pytest release.
- Database assertions are not required for every case, but observable business results are required. Prefer follow-up API/detail/list/status assertions when they prove the business result; require DB assertions when persistence, cleanup, or final state is not API-observable; keep API-and-DB-unobservable cases as non-live/manual review.
- Every generated design case, executable case, framework case, optional/non-live case, and E2E flow must carry the deterministic evidence-based confidence object defined in `references/case-confidence-contract.md`. Keep `scenario_relevance` separate from confidence, preserve existing assertion/setup/cleanup/live gates, block low-confidence cases from the live denominator, and never raise a downstream score without new evidence.
- Framework generation must freeze the ordinary-case and Flow ID denominator before writing generated files. For new or materially updated non-case-free frameworks, `configs/case_denominator_manifest.yaml` plus `generation_status.yaml.case_denominator_conservation` must prove the execution-level IDs, required Flow IDs, source-backed supplements, structured data, and pytest mappings are equal by ID; counts alone cannot pass. Existing frameworks without the manifest remain compatible but still undergo source-subset, data/mapping equality, duplicate-ID, pytest collection, and final-archive checks.
- Any live chain that contains a write-side-effect interface defaults to cleanup-required. A no-cleanup decision is allowed only with source/runtime evidence for read-only/no-delta/sandbox isolation, isolated test ownership, failed request no-side-effect, or an explicit non-live/manual-review business exception.
- SQL fixture ledgers are cross-cutting setup/cleanup assets. Do not treat `data/case_sql_commands.yaml` or its total case count as the long-chain denominator; partition SQL cases by generated flow-step case ids versus ordinary case ids before applying long-chain-only gates.
- SQL-driven runtime classification must be executable, not prose-only. A generated case is SQL-driven when it enables `sql_fixture_required`, declares an active SQL/DB `setup_cleanup_materialization` or `db_assertion_materialization`, has a DB assertion marker, or has a matching case id in `data/case_sql_commands.yaml`; explicit `not_required`、`no_cleanup_required` and API-only materialization statuses do not become SQL signals merely because the field is non-empty. Generated pytest parameters, markers, fixtures, status ledgers, and validators must use the same predicate so setup, runtime extract, cleanup, and final verify cannot drift apart.
- SQL fixture ledgers must be lifecycle-correct before live release: setup may not reference post-request runtime ids; generated setup values must respect target table type/length/enum constraints; verification query aliases must match expected fields; extra verification concerns must be explicit final-verify commands; cleanup and final verification must use the same ownership boundary unless wider pre-isolation/pre-clean evidence is materialized.
- SQL assertions that compare values produced by requests must use the actual persisted representation after source-confirmed serialization, type conversion, trimming, defaulting, or JSON wrapping. A request-side list/object, date/time, enum, or marker may not be compared against the database as a guessed string shape; the SQL expectation must cite source/runtime evidence for the stored form.
- Derived or aggregate assertions must be source-formula, before/after, or current-run evidence based. Do not hardcode historical aggregate values such as counters, scores, balances, rates, or latest-time fields as expected results unless the row is a fixed test-owned configuration row and the source proves it cannot change during the run.
- Post-request SQL lifecycle stages must be idempotent per case and stage key. If both ordinary fixtures and flow runners can touch the same case SQL entry, `runtime_extract`, delayed waits, cleanup, and final verification must execute exactly once per intended case/stage or explicitly record a safe no-op reentry guard.
- Post-request SQL commands must be producer-aware on failure paths. A cleanup or runtime-extract command that consumes an API-response or post-request DB variable must declare a command-level missing-variable policy; optional or derived side effects may skip, but primary-object cleanup may not rely on skipping. Setup-state restore commands must remain executable without unrelated response-produced variables, and teardown must continue independent restore/final-verify commands after another post-request command fails.
- A transport failure on a mutating request is an ambiguous write outcome, not proof of no side effect. Every repeatable live write case whose normal cleanup depends on a response-produced id must also expose a request-known current-run ownership key, known target snapshot, isolated containment, or equivalent fallback lookup/cleanup path. The fallback path must be executable without the missing response id and end with same-boundary final verification; otherwise keep the case non-live/manual.
- Session-scoped database engines must validate pooled connections when they are checked out and expose a bounded recycle interval through runtime database configuration. Generated SQL fixtures that contain delayed observation windows must not reuse an unchecked connection after that window; use connection-pool liveness checks such as `pool_pre_ping` and a configurable `pool_recycle` value without embedding database credentials or environment-specific hosts in generated code.
- SQL runtime extraction for asynchronously produced or aggregated results should use assertion-driven bounded polling when the result is safely observable by SELECT. Declare a positive timeout and interval, stop immediately when every expected query result matches, publish runtime variables only after the whole query batch passes, and fail on timeout. Retry only assertion-not-ready states; database, transport, SQL syntax, and configuration errors must fail immediately. Fixed waits remain compatible for source-required timing but may not be combined with bounded polling in one command.
- Optional or conditional side-effect records, including notifications, helper messages, cache/queue artifacts, async callback rows, and derived linkage rows, must not be modeled as mandatory cleanup mutations unless source or runtime evidence proves they are always produced for that request variant. For conditional side effects, cleanup may allow zero affected rows only when a scoped final verification proves no current-run residue remains; this does not relax cleanup for the primary persisted business object.
- Positive write-side-effect cases whose business result is constrained by uniqueness, idempotency, pending-review state, relationship direction, subscription/order/message/evaluation existence, or other prior state must close existing-state preconditions before live release. Use source-bound precheck API, precise API cleanup, bounded SQL pre-clean, isolated accounts, or non-live/manual review classification. If the pre-state closure needs DB runtime, missing DB env/driver/tunnel is a live-execution blocker for those case ids, not a product defect and not a reason to silently keep them runnable.
- SQL setup data must pass a historical-shape reference gate before it can be treated as repeatable live setup: inspect bounded same-table/same-business-state historical rows or equivalent normalized DB evidence to confirm field formats, enum/status values, JSON shapes, time conventions, page-visible values, and role relationship constraints. Historical data is format evidence only; generated rows must still use current-run ownership keys and must not copy sensitive values or create invalid relationships such as self-relations unless the case is explicitly an error branch.
- The final framework may be called runnable only after setup/cleanup materialization, execution fact closure, pytest mapping, required-flow coverage gates, and shared requester/transport-crypto adapter gates pass according to component rules and root validation.
- Script-generation release and live execution readiness are separate gates. Missing concrete runtime secrets, DB URLs, network tunnels, or live-only drivers must not block `api-test-framework/` generation when the scripts expose source-bound configuration entrypoints such as `configs/{env}.yaml`, `configs/database.yaml`, environment-variable references, and pytest `--env`; record those items under live execution readiness instead. Do not relax request, assertion, setup/cleanup, DB evidence, or transport-crypto materialization gates.
- When generated scripts consume runtime evidence, `generation_status.yaml.runtime_evidence_script_materialization.status` must be `passed` and `configs/runtime_evidence_script_mapping_audit.yaml` must exist before broad pytest execution or product-defect triage.
- For confirmed encrypted transports, generated pytest projects must keep one shared requester and one shared crypto adapter. Record `configs/shared_requester_crypto_adapter_status.yaml`; `passed_static` permits only smoke candidacy, while broad live execution requires `passed_live_smoke` plus case/setup/cleanup/assertion readiness.

## Confusion Points To Mark Explicitly

When working, call out these boundaries in reports and blockers whenever relevant:

| Boundary | Correct handling |
|---|---|
| Design long chain vs required flow | `business_long_chain_cases.yaml` is design coverage; `required_chain_flows.yaml` is execution/script required denominator. |
| Runtime evidence timing | Only after handoff and before executable filling; never during source/design extraction or framework generation. |
| Readiness fact changes | Rehash all fact inputs, rerun the denominator builder with `--readiness-reconciliation`, and recopy the regenerated denominator/audit to handoff before downstream generation. |
| Human coverage report | `测试覆盖点报告.md` is reviewer-facing and must not become a downstream hard denominator. |
| Apifox evidence | Optional auxiliary evidence unless user requires Apifox alignment; not a runtime requester. |
| DB MCP evidence | Normalize into `数据模型.md` and alignment sidecars; do not pass live MCP access into scripts. |
| Script-generation defects vs product defects | Run the component runtime usability and materialization gates before confirming product defects. |
| Step-by-step mode | Stop at durable boundaries and do not jump to execution/runtime/framework stages without explicit continuation. |

## Component Layout

```text
api-automation-pipeline-suite/
├── SKILL.md
├── agents/openai.yaml
├── references/
│   ├── loading-matrix.md
│   ├── pipeline-gates.md
│   ├── sidecar-contracts.md
│   ├── chain-flow-contract.md
│   ├── runtime-evidence-policy.md
│   ├── source-derived-runtime-inputs.md
│   ├── db-mcp-alignment-policy.md
│   ├── apifox-boundary.md
│   ├── execution-fact-closure.md
│   ├── case-confidence-contract.md
│   ├── failure-and-completion-policy.md
│   └── full-contract.md
├── scripts/
│   ├── select_entry_route.py
│   ├── build_chain_flow_denominator.py
│   ├── build_runtime_evidence_plan.py
│   ├── prepare_handoff.py
│   ├── run_live_request_evidence.py
│   ├── validate_runtime_evidence.py
│   └── validate_pipeline_outputs.py
└── components/
    ├── pre-doc-analysis-pipeline/
    ├── source-api-fact-extractor/
    ├── interface-testcase-generation/
    ├── executable-interface-case-set/
    ├── api-test-framework-generator/
    ├── doc-precheck-coverage/
    ├── test-point-analysis/
    └── interface-testcase-design/
```

## Required Workflow

1. Run preflight using `references/loading-matrix.md` and `references/pipeline-gates.md`.
2. Decide entry route with the deterministic script when useful:

```bash
python3 <skill_dir>/scripts/select_entry_route.py \
  --prd PRD.md \
  --api-doc API.md \
  --system-analysis 系统分析.md \
  --source-root ./backend \
  --data-model 数据模型.md \
  --execution-config 执行配置.md \
  --target-depth framework
```

3. Run the selected entry component and produce the required entry deliverables and sidecars.
4. Build `business_chain_candidate_inventory.yaml`, `required_chain_flows.yaml`, and `chain_flow_candidate_audit.yaml` before design-case generation. Inventory records broad discovery; only `required_chain_flows.yaml` is the execution/script denominator. Use `scripts/build_chain_flow_denominator.py` when deterministic help is useful.
5. Run `$interface-testcase-generation` and create design cases, business long-chain design denominator, coverage-point report, and sidecars.
6. Adapt handoff with `scripts/prepare_handoff.py` when a deterministic bridge is useful. Handoff is copying/normalizing only; do not create new facts.
7. If runtime evidence is requested or required, plan it first with `scripts/build_runtime_evidence_plan.py`. When deriving remaining request values from source, read `references/source-derived-runtime-inputs.md` and use the queue-driven pattern: source-derived candidate values -> real request validation -> failed-attempt reason backfill. Then execute only allowed request-plan items with `scripts/run_live_request_evidence.py` or an equivalent requester after runtime configuration is complete.
8. Whenever an execution-readiness fact changes, create or refresh root `chain_execution_readiness_reconciliation.yaml`, including SHA-256 revisions for every consumed fact file, one capability-based decision per ready chain, pending chains, and explicit exclusions. Run `scripts/build_chain_flow_denominator.py --readiness-reconciliation <file>` to regenerate the root inventory, required denominator, and audit; then recopy the regenerated denominator and audit to handoff. For `ready_for_generation`, generate executable cases next; before executable/framework release, refresh the same artifact to `status: passed` with executable case IDs and, for framework depth, pytest nodeids.
9. Run `$executable-interface-case-set` only after handoff and execution-readiness gates are satisfied or correctly blocked.
10. Run `$api-test-framework-generator` only after executable cases pass and long-chain missing values are not pending.
11. Run final validation:

```bash
python3 <skill_dir>/scripts/validate_pipeline_outputs.py output/api-automation-pipeline
```

Also run component validators when their stages write files.

## Output Boundary

Keep the existing output directory contract from `references/pipeline-gates.md`. Create only subdirectories for executed stages. Do not fabricate documents for skipped or blocked stages. Do not add README-style project explanations.

## Final Response Rules

Before replying, read `references/failure-and-completion-policy.md`.

If `api-test-framework/` was not generated, start with `未生成最终自动化脚本`, then name the stopping status, stopping stage, missing inputs, and highest completed stage. Never say `全链路通过`、`跑完全链路`、`已生成自动化脚本`、or unqualified `校验通过` unless final scripts exist and the framework gates passed.
