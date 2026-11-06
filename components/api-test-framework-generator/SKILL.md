---
name: api-test-framework-generator
description: Generate executable Python API automation projects with pytest, requests, and allure from Chinese execution-level interface test artifacts and a data model artifact. Use when Codex needs to read `执行级接口用例集.md`, `前置数据构造规则.md`, and a data model document such as `数据模型.md`, run a strict precheck across all input files before generation, enforce generation gates, keep case-free output when gates fail, and scaffold or update an `api-test-framework/` directory containing configs, data, API wrappers, core request/assert/extraction/SQL utilities, pytest fixtures, and Allure-ready API test scripts.
---

# API Test Framework Generator

## 目录
- [Overview](#overview)
- [Inputs](#inputs)
- [Resources](#resources)
- [Stage Workflow](#stage-workflow)
- [Failure Branches](#failure-branches)
- [Downstream Boundary](#downstream-boundary)
- [Input Precheck Gate](#input-precheck-gate)
- [Coverage To Pytest Mapping Gate](#coverage-to-pytest-mapping-gate)
- [Fixture Contract](#fixture-contract)
- [E2E Flow Suite Contract](#e2e-flow-suite-contract)
- [SQL Generation Gate](#sql-generation-gate)
- [SQL Command File Contract](#sql-command-file-contract)
- [Output Contract](#output-contract)

## Overview
Use this stage skill to convert execution-level Chinese API case artifacts and a data model artifact into an executable `pytest + requests + allure` project. Treat the work as a gated pipeline: precheck all input files, parse source artifacts, confirm the script-generation gate, generate only source-bound code, validate the project, and report the stage result.

Always follow the repository instructions: preserve already-correct functionality, write Chinese comments in UTF-8, check Chinese text for mojibake, avoid emoji, and do not invent fallback values.

## Inputs

Require these input files:

- `执行级接口用例集.md`: execution-level API cases that can be converted into pytest cases, or an explicit case-free stage result.
- `前置数据构造规则.md`: stage conclusion, input validation, environment/auth/database requirements, precondition data rules, variable extraction/injection, cleanup strategy, repeatable-execution checks, script-generation gate, missing items, and pytest+allure conversion conclusion.
- Data model artifact, recommended name `数据模型.md`: table structures, fields, primary keys, unique keys, indexes, enums, required/default rules, entity relationships, foreign-key or knowledge-graph edges, aggregate boundaries, and setup/cleanup ordering evidence. Accept Markdown, YAML, or JSON when the user provides another concrete path.
- Required for suite-generated inputs: `execution_fact_sources.yaml`, including `runtime_business_dependency_audit`. Treat `source_type: live_request_evidence` as already-normalized upstream evidence; do not read `04-runtime-evidence/` directly unless it is explicitly provided as a review-only source reference. For explicitly supplied legacy inputs that predate this sidecar, stop for upstream audit instead of inferring mutable dependencies from endpoint names.
- Optional but mandatory for chain-script runs when present upstream: `required_chain_flows.yaml`, `business_scenario_map.yaml`, and `测试覆盖点报告.md`. Use `required_chain_flows.yaml` as the authoritative required E2E flow denominator. Treat `business_scenario_map.yaml` and `测试覆盖点报告.md` only as candidate/context evidence for review; they must not by themselves require script generation.
- Optional but mandatory when present upstream: `long_chain_missing_value_fields.yaml`. If present, it must be `status=not_required` or `filled` with `open_required_count=0`; otherwise block before script generation. Do not consume `长链路缺失码值补充清单.md` as the only source of runnable values.
- Optional but mandatory when present upstream: `09-interface-encryption-policy.md` or `source-api-facts.json#project_encryption_policy`. Use it to decide interface-level request encryption and response decryption; treat source-inferred candidates as unconfirmed until execution config, gateway/client protocol evidence, or user confirmation resolves them.
- Optional but mandatory when a case or Flow requires a non-generic execution implementation: an upstream specialized-runner fact artifact such as `specialized_runner_contracts.yaml`. It must live outside the generated framework and bind stable runner IDs、consumer IDs、ordered actions、auth/runtime inputs、assertions、cleanup/failure-path guarantees and authoritative source refs. Existing generated Runner files are not valid upstream facts.

Accept an optional existing `api-test-framework/` directory. If it exists, inspect the relevant functions before editing and only patch the files needed for the current generation.

When modifying or rerunning an existing generated framework for a failure or supplementation task, declare the validation scope before editing: `same_chain_patch` for one flow/case and its direct producer/consumer dependencies, `selected_subset` for a named subset, or `all_generated_cases` for full-suite readiness. Same-chain patches must not rewrite unrelated flow/case data, assertions, cleanup, or expected responses unless the same root cause is independently reproduced there. Full root validation remains global and is required only for full-suite readiness claims.

## Resources

- Read `references/conversion-contract.md` before generating code. It defines required fields, gate rules, traceability mapping, output schema, and validation commands.
- Read `references/case-denominator-conservation.md` before building the generation model. It defines the compatibility-safe source/supplement denominator manifest and the non-duplicated set-equality gate across generated data and pytest mappings.
- Read `references/splitting-strategy.md` when any generated file may become large or when the user asks about splitting. It defines interface-complete split boundaries, indexes, and no-loss rules.
- Read `references/setup-cleanup-defect-gate.md` whenever cases may create, update, delete, mock, seed, or restore data, or when generating/rereviewing defect lists. Use its target-run-scope and risk-tiered cleanup-closure rules to separate `all_generated_cases` from `safe_subset`; when the user says all cases must run, exclusions are blockers rather than a smaller denominator, but DB before/after must not become a blanket requirement for source-confirmed no-side-effect, sandbox-isolated, or business-valid non-live cases. Apply its SQL runtime preflight compatibility section only when the generated framework exposes the corresponding runtime-stage, runtime-variable, dynamic-DB-expectation, or explicit-subset capability. Read `references/runtime-evidence-script-materialization.md` whenever generated scripts consume runtime evidence candidates, direct-request observations, runtime value catalogs, or supplemental request/replay evidence. Read `references/runtime-usability-gate.md` before marking generated scripts runnable, including its capability-triggered response-binding and bounded write-followup rules. Read `references/runtime-failure-diagnosis.md` after report failures or before broad reruns, and `references/final-case-archive.md` before writing final reviewer/archive case artifacts such as `接口案例.md` or `缺陷列表.md`.
- Read `references/unified-runtime-configuration-entry.md` when local execution needs operator-supplied values from multiple files or categories, or when the user requests one configuration form. Keep it conditional when an authoritative CI, Vault, platform-managed, or established local secure entrypoint already exists.
- Read `references/specialized-runner-materialization.md` whenever generated case or Flow data uses `specialized_runner_id`、legacy `custom_runner`、`runner_ref` or a dedicated execution mode. It defines the generic-first decision、uniform adapter、non-circular provenance and cold-start semantic reproduction gate.
- Copy `assets/api-test-framework-template/` when creating a fresh `api-test-framework/` project. Then replace placeholders and add generated `api/`, `data/`, and `testcases/` files from the source artifacts.

## Stage Workflow

1. **Precheck all input files**
   - Confirm `执行级接口用例集.md`, `前置数据构造规则.md`, and the data model artifact exist and are readable.
   - Read text inputs with UTF-8 and search all inputs for replacement characters, garbled Chinese markers, and broken Chinese punctuation.
   - Confirm each input has non-empty source content and an identifiable stage/status section or equivalent structured evidence.
   - Confirm case IDs in `执行级接口用例集.md` can be mapped to precondition rules and, when SQL is required, to data model tables and graph relationships.
   - Confirm every executable case preserves `覆盖对象ID`、`覆盖规则ID`、`设计级用例ID`、`追溯测试点`, and can later map to a generated pytest nodeid.
   - Confirm every referenced table, column, enum, status, key, and relationship used by setup/cleanup exists in the data model artifact.
   - Confirm `long_chain_missing_value_fields.yaml`, when present, has `status=not_required` or `filled`, `open_required_count=0`, and that the filled values are already reflected in `执行级接口用例集.md`, `前置数据构造规则.md`, and `execution_fact_sources.yaml`.
   - Confirm account-specific long-chain flows have already closed the login-entry gate: execution facts must include confirmed `account_specific_chain` and `login_entry_rule` evidence, and the executable chain steps must start with the login/auth request.
   - Confirm ordinary API cases that use dynamic auth have an executable account bootstrap plan: every non-anonymous `session_role` maps to a source-bound auth role or `account_group_key`; each account group has a configured login/token request or confirmed static token source; the generated runner can refresh the group context before business steps without constructing a new requester per case.
   - Confirm positive-path request validation closure: required request fields from source-visible DTO validation, OpenAPI required lists, or equivalent contract rules must have source-bound legal values before a case is counted as live runnable. Missing required fields are valid only for explicit validation/error branches whose expected assertions target the missing-field behavior.
   - Confirm validation/error branch isolation: when a branch case targets one missing, blank, invalid, enum, length, boundary, or conflict field, every unrelated required request field, auth context, account context, and upstream variable needed to reach that validation point must remain valid and source-bound. If another earlier validation error can fire first, the case does not prove the intended branch and must be blocked or repaired.
   - Confirm interface transport encryption readiness from `前置数据构造规则.md`: if no encrypted interfaces are confirmed, mark the crypto gate as not applicable; if encrypted interfaces are confirmed, require algorithm reference, key source, request payload scope, request plaintext serialization, request envelope, and response envelope before generation; otherwise block.
   - Confirm setup/cleanup materialization readiness: `cleanup_refs`、`cleanup_id`、`source_ref`、`db_before_after` references, or narrative cleanup strategy are not executable cleanup. A case that mutates persistent state may enter the executable denominator only when the generated framework can run a source-bound API/SQL setup or cleanup action through fixtures and prove the affected id/ownership boundary.
   - Confirm SQL-driven case classification readiness: use one shared predicate across case data, pytest marker generation, fixture attachment, status ledgers, and validators. A case is SQL-driven when it declares `sql_fixture_required`, `setup_cleanup_materialization`, `db_assertion_materialization`, a DB assertion materialization rule, or has a matching case id in `data/case_sql_commands.yaml`. Do not rely on `sql_fixture_required` alone.
   - Confirm existing-state closure for uniqueness/idempotency/relationship write cases before counting them as live runnable. Positive write-side-effect cases that can be affected by an existing row or relationship, such as report/feedback/subscription/order/message/evaluation/relation/status-pending records, must declare a source-bound precheck, precise API cleanup, bounded SQL pre-clean, isolated account/state, or non-live/manual-review decision. DB-required pre-state closure belongs under `live_execution_readiness` when DB env/driver/tunnel is absent.
   - Confirm cleanup-closure supplementation strategy before counting cases: classify each candidate with `closure_mode` (`no_cleanup_required`, `api_cleanup`, `sql_cleanup`, `same_interface_restore`, `isolated_account`, `environment_snapshot`, `manual_review_only`, or `blocked_missing_evidence`) and `automation_decision` (`runnable`, `safe_subset_only`, `generated_non_live`, `manual_review_only`, or `blocked_live_execution`). DB before/after evidence is mandatory only for local persistent mutation when source/runtime evidence cannot prove no persistent side effect; it is not required for source-confirmed read-only, runtime no-delta, sandbox/mock-isolated, or explicitly accepted non-live business exceptions.
   - Confirm assertion strength and business-result observability before counting cases: every runnable case must declare `assertion_strength` and `result_observation_mode`; write-side-effect and long-chain cases need a follow-up API assertion or DB assertion unless explicitly non-live/manual review.
   - Confirm write-side-effect cleanup policy before counting cases: any live chain containing a write interface defaults to cleanup-required; no-cleanup on a mutating case is valid only with source/runtime no-delta, sandbox/isolation, failed-request no-side-effect, or non-live/manual-review exemption evidence.
   - Confirm conditional side-effect cleanup policy before counting cases: optional notification/message/cache/queue/callback/linkage records must not force `affected_rows=1` unless source or runtime evidence proves they are always produced. If production is conditional, cleanup may use `affected_rows_min: 0` only with scoped final verification that the current-run ownership key has no residue.
   - Determine target real-run scope before counting cases: default to `all_generated_cases` when the user asks for all cases, full-suite, 全量, 全部, or 都要真实跑; use `safe_subset` only when the user explicitly requests a safe subset. In `all_generated_cases`, generated candidate count, selected executable denominator, runnable case count, and collected pytest count must converge; any exclusion, cleanup_refs-only mutable case, pending DB rollback validation, or missing setup/cleanup closure blocks real execution instead of shrinking scope.
   - Keep script-generation readiness separate from live-execution readiness. If concrete runtime secrets, DB connection URLs, network tunnels, or live-only drivers are missing but the generated project exposes source-bound configuration entrypoints through `configs/{env}.yaml`, `configs/database.yaml`, environment-variable references, and pytest `--env`, do not block script generation for those missing runtime values. Record them in `runtime_configuration_entry` and `live_execution_readiness` instead.
   - Keep generation scope separate from live execution scope: valid business scenarios that cannot be safely automated must remain traceable as `generated_non_live` or `manual_review_only` instead of being silently dropped. They may block `all_generated_cases` real execution, but they must still appear in the generated status or archive with source reason and assertion boundary.
   - Confirm runtime-evidence script materialization readiness when runtime evidence candidate files, runtime value catalogs, or replay evidence are present: unreleased candidates cannot enter the runnable denominator, and every evidence-backed generated step must be auditable back to one request variant, role, expected business code/message, and source evidence id.
   - Confirm specialized-runner applicability only after proving the shared ordinary runner、generic Flow runner and existing fixtures cannot safely express the source-bound behavior. When applicable, require an upstream fact contract outside the generated framework; when no specialized marker exists, record the gate as `not_required` and do not add a blocker.
   - Write the precheck result to `api-test-framework/configs/input_precheck_report.yaml` when creating an output directory.
   - Stop with `blocked` if any input precheck item fails.

2. **Evaluate gates**
   - Parse the phase conclusion and script-generation gate from `前置数据构造规则.md`.
   - Parse the case list status from `执行级接口用例集.md`.
   - Parse table/field/relationship completeness from the data model artifact.
   - If either artifact says case-free, gate-failed, missing required execution data, or not convertible to pytest+allure, do not generate test scripts. Write only stage status, generation status, and reasons as described in the reference.

3. **Build the source-bound generation model**
   - Before writing generated files, freeze the ordinary-case and Flow ID denominator according to `references/case-denominator-conservation.md`: parse all execution-level `用例ID` and required `flow_id`, inventory every source-bound supplemental group with non-empty `source_refs`, and keep the frozen sets independent from downstream generated counts. For a new or materially updated non-case-free framework, write `configs/case_denominator_manifest.yaml`; do not reconstruct this manifest from generated data after generation.
   - Extract case id, priority, feature/story, method, path, headers, auth, request body/query/path parameters, preconditions, variable extraction, variable injection, expected status code, response assertions, cleanup, and repeatability rules.
   - Extract required E2E flows from `required_chain_flows.yaml`. Use `business_scenario_map.yaml` and `测试覆盖点报告.md` only to enrich title/story/context and audit candidate coverage; candidates not confirmed in `required_chain_flows.yaml` are not mandatory script denominators.
   - Extract coverage traceability fields: `覆盖对象ID`, `覆盖规则ID`, `设计级用例ID`, `追溯测试点`, and keep them in generated data and test metadata.
   - Extract environment config, base URL, timeout, common headers, and auth/token rules from the precondition artifact.
   - Treat direct-request runtime evidence as already normalized upstream facts. Do not call `run_live_request_evidence.py`, direct requester code, live interfaces, or runtime secret files during pytest generation or runtime.
   - When runtime evidence backs an executable case, preserve the evidence request and expected response exactly at plaintext business-data level. Do not replace role-specific variables with `${login_user_id}`, do not overwrite observed business codes/messages with design defaults, and do not reuse one observation's assertion for another request variant under the same case.
   - Runtime evidence may enter the runnable denominator only when `script_materialization_ready=true`, plaintext request/response, role/auth/token placement, assertion candidates, setup/cleanup classification, and observability proof are present. Summary-only evidence remains review evidence or value evidence, not live pytest evidence.
   - Treat any Apifox-derived facts as already-normalized upstream evidence. Do not query Apifox MCP, Apifox environments, or saved debug cases during pytest generation or runtime.
   - Treat long-chain missing-value checklists as an upstream repair gate only. If the checklist sidecar is still pending or blocked, stop. If it is filled, read executable values from the patched execution-level artifacts and fact sources, not from the human checklist alone.
   - Extract confirmed interface transport encryption policy from upstream `project_encryption_policy` or execution config. Generate encryption/decryption wrappers only for interfaces confirmed as encrypted; bypass only interfaces confirmed as no-encrypt. Do not turn `no_encrypt_candidate` into a hardcoded whitelist without confirmation, and block on `policy_required`.
   - Extract confirmed seeded values from `execution_fact_sources.yaml` and `前置数据构造规则.md`. A seeded value is runnable only when it is already classified as `precondition_api_value`、`db_seeded_value`、`dictionary_or_config_value`、`prior_runtime_response_value`, or `external_dependency_value`, has a confirmed source entry, has a confirmed `seed_scope_guard` when produced by API/DB setup, and is already present in the execution-level request/assertion/DB/cleanup field as a concrete value or executable variable reference.
   - Consume `execution_fact_sources.yaml.runtime_business_dependency_audit` without reclassifying endpoint-specific behavior. Preserve each dependency id、generic type、request paths、required predicates、source refs、automation decision and precheck in generated case data. Runnable dependencies must materialize into actual `preconditions`, `case_sql_commands.yaml`, fixture-backed checks or isolated-state setup; non-live decisions must remain outside the live pytest denominator.
   - Confirm business-readable input quality: positive-path, live, long-chain, and page-visible request values use source-bound legal values; bounded generic real-world legal samples are allowed only for ordinary user-entered/profile/display fields whose contract permits legal literals. Obvious placeholders such as `自动化省`、`测试市`、`xxx`、`UNKNOWN`、`示例值` are allowed only for explicit invalid-value/error-branch cases with matching assertions.
   - Confirm required-field payload quality: positive-path requests must include required DTO/OpenAPI/validation fields with legal values at the correct request location. Do not generate an empty body or omit a required field because the endpoint also has common parameters, authentication context, or default request wrappers.
   - Confirm cross-surface request variant consistency: when an ordinary case, long-chain step, optional async case, or archive case uses the same method/path and compatible request variant, preserve the confirmed required field set and source-bound business parameters unless source/runtime evidence explains the role, state, dependency, or branch-specific difference.
   - Confirm response assertion binding when a flow step changes an identity、primary-key、role or tenant request dimension. Business-field assertions inherited from the source case must be explicitly rebound through `expected_overrides`, or the step must carry source-bound `assertion_binding` evidence. Envelope assertions alone may remain inherited. Do not apply this check to pagination-only or other non-identity overrides.
   - Confirm bounded write-followup observation when a producer step creates or extracts a current-run value and a later collection step asserts that value. The observation request must filter by the current-run id/unique marker, call a detail lookup, use a scoped DB assertion, or declare evidence-backed bounded pagination. A first-page assertion with only page/status/sort fields is not closed.
   - Confirm the upstream runtime-business-dependency audit covers every execution-level case. A dependency on mutable dictionary participation、configuration enablement、eligibility、quota/limit or external runtime state may enter the live denominator only with an executable API/SQL/fixture/isolated-state precheck; a state-changing precheck also requires executable restore. `not_required` is valid and non-blocking when the exact full case scan has no applicable dependency.
   - Confirm request shape fidelity: preserve source-visible scalar/list/object/map field kinds, nesting, array order, `null`, and intentional omission across case data, flow data, reviewer archives, and generated collection artifacts. Do not convert a list/object request field into a plain string unless the confirmed transport or persistence boundary requires that exact serialized representation and the conversion evidence is recorded.
   - Classify cleanup closure before generating tests: cases with executable setup/cleanup may run; source-confirmed read-only or no-persistent-side-effect cases may run with response assertion evidence; sandbox/mock-isolated or external-only cases may run only when isolation evidence proves no local persistent pollution; business-valid irreversible, one-way, asynchronous, manual-review, third-party, or environment-destructive cases must be preserved as `generated_non_live`/`manual_review_only` unless an isolated account, environment snapshot, same-interface restore, API cleanup, or SQL cleanup strategy is materialized.
   - Classify assertion strength before generating tests: `L1_basic` is only HTTP/business-code connectivity, `L2_response_field` adds key response fields, `L3_business_observable` verifies business state through follow-up API, `L4_persistence_verified` adds scoped DB persistence evidence, and `L5_cleanup_verified` proves cleanup/restoration. Do not mark a write or long-chain case as business-closed with only `L1_basic`.
   - Build a real-run readiness ledger before writing tests. Record `target_run_scope`, `generated_candidate_case_count`, `selected_case_count`, `runnable_case_count`, `blocked_real_run_case_count`, per-case readiness (`ready`、`blocked`、`excluded_safe_subset_only`), `closure_mode`, `evidence_strength` (`source_confirmed`, `runtime_no_delta`, `db_before_after`, `cleanup_after_verified`, `sandbox_isolated`, or `business_exception_accepted`), `automation_decision`, `assertion_strength`, `result_observation_mode`, `cleanup_required`, and `cleanup_exemption_reason`. `cleanup_refs` may remain as evidence links, but cannot populate `preconditions`, `cleanup`, or SQL commands unless transformed into fixture-executed actions.
   - Extract confirmed account-specific chain facts from `execution_fact_sources.yaml`. When a flow is marked `specific_account_required` or cites `account_specific_chain`, the generation model must keep the login/auth executable case as the first `data/flow_cases.yaml` or `data/flow_cases.py` step and must extract token plus required account context before any business step. Do not convert this login into only a hidden fixture.
   - Extract ordinary-case account grouping facts from execution facts, runtime evidence, or auth configuration. For ordinary API cases, materialize group bootstrap as a fixture or auth-context registry keyed by `account_group_key`/`session_role`: authenticate before the first business step for each group, extract token/session/user/device/key-material context, and reuse the shared requester/session for compatible cases. Do not add a hidden pre-login wrapper to cases whose first step is already an explicit `auth`/`login` step.
   - Generate one business-variable runtime scope per ordinary case and one shared scope per complete E2E flow. Preserve account-group auth/session context across compatible cases, but clear prior case/flow business ids, markers, timestamps, and extracted payloads before the next scope. Bind ordinary auth bootstrap, API setup, SQL setup, and business execution after that scope initializer.
   - Use explicit step extraction for ordinary multi-step cases and flows. JSONPath/regex rules come from execution facts, preserve scalar/list/object types, fail when a required extraction is absent, and publish into the active scope. An explicit `auth`/`login` step must update the same role/account-group auth registry used by later requests; do not depend on URL heuristics or duplicate incompatible auth-update code in ordinary and flow runners.
   - Keep external dependency values isolated. Values marked `external_dependency_value` may be injected only from explicit sandbox/mock/callback evidence or a source-bound precondition API response. Do not generate local DB setup SQL to fabricate payment, withdrawal, SMS, Apple/Google, audit, OSS, webhook, risk-control, or similar third-party return codes or IDs.
   - When the confirmed request contract is whole-parameter encryption, keep common parameters and business parameters as plaintext dictionaries in generated case data, merge them in the client immediately before send, serialize the merged dictionary into a UTF-8 JSON string, encrypt that string, and send JSON body `{"data": "<ciphertext>"}`. Do not generate field-by-field encryption, `param` wrapping, or raw ciphertext body transport for that contract.
   - When the confirmed response contract is `data`-field encryption, parse the outer response as plaintext JSON, decrypt only `data` when it is a string, parse the decrypted JSON string into an object, and return the response object with plaintext `data` to assertions and `Flow Runner`.
   - Keep the generation model plaintext: request templates, assertions, JSONPath extraction, variable injection targets, `data/flow_cases.yaml` or `data/flow_cases.py`, and `runtime_context` values must represent plaintext business data. Ciphertext must not become the variable passed to a downstream step.
   - Generate database runtime configuration only under `configs/database.yaml`; do not place database connection details in test modules, SQL command files, or data payload files.
   - Extract table structures, field rules, key relationships, enums, aggregate boundaries, and knowledge-graph dependency order from the data model artifact. The data model may include facts gathered upstream through database MCP, but this stage must treat them only as normalized evidence and must not generate MCP database calls in the pytest project.
   - Build generated scripts as a data-driven maintenance model: interface contracts live in one interface definition file, ordinary executable cases live under a case data directory, and scenario/E2E chains live in one flow-chain file. Pytest modules should be thin parameterized runners; normal maintenance should happen by editing the generated case data and interface/flow data files, not by rewriting test functions. Support both YAML data files and Python pure-data files.
   - Freeze every applicable specialized runner before implementation: use canonical `specialized_runner_id`, bind its exact consumer case/Flow IDs, preserve the upstream generation obligations, and reject source refs that point back into generated `api/`、`configs/`、`core/`、`data/`、`reports/`、`scripts/`、`testcases/` or archive files. Legacy `custom_runner` is an existing-framework read alias only.
   - When using Python data files, keep them as pure data modules only: `data/interfaces.py` exports `INTERFACES`, `data/cases/*.py` exports `CASES`, and `data/flow_cases.py` exports `FLOWS`. These files may contain only comments, an optional module docstring, `SCHEMA_VERSION`, and literal list/dict/string/number/bool/None assignments. Do not generate imports, function/class definitions, runtime calls, random/env reads, loops, comprehensions, or dynamic case construction in data files.
   - Treat missing required executable values as blockers. Do not create guessed URLs, tokens, request bodies, expected responses, or assertions.
   - If upstream execution cases still lack business codes, token rules, variable links, assertions, cleanup strategy, or concrete request/response values, block generation instead of re-requesting interfaces to fill them.

4. **Generate the framework**
   - Create or update this structure:

```text
api-test-framework/
├── configs/
│   ├── dev.yaml
│   ├── test.yaml
│   ├── prod.yaml
│   ├── database.yaml
│   ├── input_precheck_report.yaml
│   └── split_index.yaml
├── data/
│   ├── interfaces.yaml 或 interfaces.py
│   ├── cases/
│   ├── case_sql_commands.yaml
│   ├── case_sql_validation.yaml
│   ├── dependency_payloads.yaml
│   └── flow_cases.yaml 或 flow_cases.py
├── testcases/
│   ├── test_api_cases.py
│   └── test_flows.py
├── api/
├── core/
│   ├── auth_manager.py
│   ├── client.py
│   ├── crypto_codec.py          # only when confirmed encrypted interfaces exist
│   ├── transport_policy.py      # only when confirmed encrypted interfaces exist
│   ├── assertor.py
│   ├── data_manager.py
│   ├── extractor.py
│   ├── flow_runner.py
│   ├── dependency_check.py
│   ├── database_assertor.py
│   ├── sql_executor.py
│   ├── sql_validator.py
│   └── logger.py
├── utils/
│   ├── yaml_util.py
│   ├── json_util.py
│   └── random_util.py
├── conftest.py
├── check_dependencies.py
├── check_sql_commands.py
├── pytest.ini
├── requirements.txt
└── reports/
```

   - Generate `api/*_api.py` wrapper files from interface groups or bounded domains in the cases.
   - Generate `data/interfaces.yaml` or `data/interfaces.py` as the single interface definition registry. Each generated ordinary case must reference an `interface_id` from this file instead of duplicating method/path definitions inside test code.
   - Generate ordinary executable case data under `data/cases/*.yaml` or `data/cases/*.py`. Each case record must include `case_id`、`interface_id`、source-bound request data, expected status/assertions, `assertion_strength`, `result_observation_mode`, priority/flow type, traceability fields, and the complete confidence object from the suite `../../references/case-confidence-contract.md`. Do not put runnable case payloads directly in pytest functions.
   - Generate `data/*.yaml` or pure-data `data/*.py` files from concrete source-bound test data and API-first precondition rules.
   - Generate `data/dependency_payloads.yaml` for downstream dependency transfer; dependency extraction must use explicit JSON paths or regex patterns only.
   - Generate `data/flow_cases.yaml` or `data/flow_cases.py`, `core/flow_runner.py`, and `testcases/test_flows.py` for every required flow in `required_chain_flows.yaml` with source-bound ordered steps and dependency evidence. Keep single-interface tests only as supporting coverage; they must not replace confirmed chain scripts.
   - Preserve request data shapes in every generated data surface. A DTO/OpenAPI/runtime-evidence list remains a list, an object remains an object, a map remains a map, and `null` remains distinct from omission in ordinary case data, flow overrides, archive output, and generated collection output.
   - Each generated E2E flow test must be a short, readable pytest function with `import allure`, `import pytest`, `from core.flow_runner import run_flow`, `@allure.feature("e2e")`, source-bound `@allure.story(...)`, source-bound Chinese `@allure.title(...)`, `@pytest.mark.e2e_flow`, the existing flow selector marker (`main_flow` or `branch_flow`), and a single `run_flow("<flow_id>", authenticated_client, env_config, runtime_context)` call.
   - `data/flow_cases.yaml` or `data/flow_cases.py` must declare flow id, title, story, flow type, ordered steps, source case ids, request overrides, extraction rules, injection targets, cleanup policy, source evidence, and a flow-level confidence object. The flow score cannot exceed the weakest required step. It must show which upstream response field is extracted into `runtime_context` and which downstream request field consumes it. Each required upstream `flow_id` must appear exactly once. For account-specific flows, declare the account requirement and keep the first step as `step_type: login` or an equivalent explicit login/auth marker with token/account-context extraction rules.
   - When a specialized runner is applicable, generate `configs/specialized_runner_materialization.yaml`, a source-bound `core/*` implementation with the uniform `run_specialized` keyword adapter, and dispatch through the shared template `core/specialized_runner.py`. Keep business-specific dispatch and result checks out of `test_api_cases.py`; use `specialized_runner_assertions` plus stronger implementation-local assertions when required by the upstream contract.
   - `core/flow_runner.py` must load flow definitions, merge plaintext request overrides, resolve `${variable}` placeholders recursively from `runtime_context`, environment config, or process environment, send plaintext request data through the shared client, receive decrypted response data from the client, assert status and response fields, extract variables with explicit JSONPath or regex rules from the decrypted response, write plaintext values into `runtime_context`, and fail fast on unresolved placeholders. Do not create fallback request values.
   - When confirmed encrypted interfaces exist, generate or update a transport adaptation layer in `core/client.py` plus dedicated helper modules such as `core/transport_crypto.py`, `core/crypto_codec.py`, or `core/transport_policy.py`. The client must encrypt requests immediately before network send and decrypt responses immediately after receive. For the `{"data": "<ciphertext>"}` request envelope, API wrappers and tests still pass plaintext request dictionaries to the client. For the outer-JSON/plaintext and encrypted-`data` response envelope, the client returns a normal response object whose `data` is already decrypted and JSON-parsed when applicable. Algorithm implementations and key loading must come from the confirmed runtime contract; do not generate placeholder crypto.
   - On encrypted-response decode failure, attach bounded and redacted pre-decryption response metadata/body plus bounded failure context before raising. Keep attachment length under a configurable hard cap, use the confirmed envelope field instead of a hardcoded key, and redact authorization/cookie/API-key/token/identity/secret-bearing exception content. Diagnostics must not change request routing, assertions, or execution decisions.
   - Generate API cleanup as teardown-safe execution: once API setup starts, cleanup must still be attempted after partial setup failure or business assertion failure. Continue independent cleanup rules after one cleanup error, preserve ownership-key guards, report all cleanup failures, restore the previously active client auth context, and never broaden cleanup to a user/account-wide deletion merely to make teardown pass.
   - Generate `configs/shared_requester_crypto_adapter_status.yaml` when encrypted transports are confirmed. Record the source contract, request/response envelope, key source, shared requester files, dependency checks, static validation, optional live smoke validation, and release boundary. Use `passed_static` only for smoke candidacy; use `passed_live_smoke` only after auth/bootstrap and at least one safe encrypted request prove alignment. Do not set `next_stage_allowed=true` from static crypto validation alone.
   - Generate `data/case_sql_commands.yaml` only when source evidence states that API construction cannot satisfy setup or cleanup, the required data model artifact plus knowledge-graph relationships can support bounded SQL, and the upstream seed-scope guard proves SQL is limited to required business precondition fields.
   - Treat `data/case_sql_commands.yaml` as a shared SQL fixture ledger for any selected SQL-driven case, including ordinary single-interface cases and E2E flow steps. Validators must partition SQL entries by source before applying denominators: long-chain SQL entries are the case ids referenced by generated `data/flow_cases.yaml` or `data/flow_cases.py` for required flows, while ordinary SQL fixture entries are selected ordinary cases that declare SQL fixture/materialized setup-cleanup usage. Do not compare the total SQL entry count to the long-chain flow denominator, and do not require long-chain-only extraction fields from ordinary SQL fixture cases unless their own assertion or cleanup rule declares that extraction.
   - When at least one SQL runtime preflight compatibility check is applicable, write `configs/sql_runtime_lifecycle_gate.yaml`. Reuse stage-placement and derived-value evidence already owned by `setup-cleanup-defect-gate`; add only preflight phase isolation, shared runtime-context entrypoint, selected-set closure, and subset/full evidence-scope evidence. Do not create a new blocker for projects that expose only pure API or basic setup/cleanup behavior.
   - When generated flows change identity/role request variants or perform write-followup collection assertions, run `scripts/validate_flow_semantics_gate.py` and write `configs/flow_runtime_semantics_gate.json`. Record each subcheck as `passed` or `not_required`; do not block projects that expose neither capability.
   - Always write `configs/runtime_business_dependency_audit.yaml` by normalizing the upstream audit. `not_required` remains a valid status, but its `scanned_case_ids` must still equal the generated case set. Copy applicable dependency metadata into each affected case; do not store only a prose summary.
   - Generate precondition setup and post-test cleanup only from execution-level rules that already close seed-value provenance and existing-state risk. API setup runs through fixtures before the request and captures declared outputs into `runtime_context`; SQL setup runs through `case_sql_manager` only for bounded local DB seed data; cleanup runs after the test and deletes or restores only the current-run data by `id` or exact ownership key.
   - For conditional side-effect cleanup commands, keep the primary business-object cleanup strict, but model optional downstream records as conditional only when evidence names the condition. Conditional cleanup must still use exact current-run ownership keys and a final verification query; broad user-level cleanup remains invalid.
   - Generate pytest SQL attachment from the shared SQL-driven predicate, not from a single flag. Ordinary, optional-async, and flow-supporting case data must add `@pytest.mark.case_id("<source-case-id>")` whenever `sql_fixture_required`、`setup_cleanup_materialization`、`db_assertion_materialization`、or a matching SQL command ledger entry requires SQL setup/runtime extract/cleanup/final verify.
   - Generate `configs/runtime_evidence_script_mapping_audit.yaml` whenever runtime evidence is used for runnable scripts. The audit must compare generated request fields, semantic runtime placeholders, role, expected HTTP status, expected business code/message, evidence id, and archive-case plaintext values against the source candidate before broad pytest execution.
   - If a case data file contains only `cleanup_refs` without generated `preconditions`/`cleanup` marker rules or `data/case_sql_commands.yaml` entries, treat it as non-runnable for mutation/destructive cases. Do not mark `sql_generation_gate.status: not_required` when any selected case requires setup, cleanup, DB restore, or mock cleanup.
   - Generate a setup/cleanup and real-run readiness ledger at `configs/setup_cleanup_materialization.yaml` or `data/setup_cleanup_materialization.yaml`, or record an equivalent machine-readable `setup_cleanup_materialization` object in `configs/generation_status.yaml`. It must list every candidate case, whether it is selected, whether it is mutable, readiness, cleanup mode, `closure_mode`, `evidence_strength`, `automation_decision`, `assertion_strength`, `result_observation_mode`, `cleanup_required`, `cleanup_exemption_reason`, executable preconditions, executable cleanup rules, SQL command id, evidence refs, and missing items. For valid business cases that are not safe for live automation, record `generated_non_live` or `manual_review_only` with source reason and assertion/observation boundary; do not remove them from the candidate ledger. Mirror the summary fields in `configs/generation_status.yaml`; do not rely on case data files as the only denominator record.
   - When post-request SQL cleanup consumes API-response or post-request DB variables, generate `failure_path_cleanup_resilience` in `configs/generation_status.yaml` with `status`, `checked_write_case_count`, `response_id_dependent_case_count`, `fallback_cleanup_case_count`, `missing_fallback_case_ids`, `unsafe_skip_primary_cleanup_case_ids`, and `restore_with_late_variable_case_ids`. The status may pass only when every affected live case has command-level producer handling, request-known fallback or snapshot containment, independent restore, and same-boundary final verification.
   - Split generated files only by the interface-complete rules in `references/splitting-strategy.md`; never split in a way that separates one interface from its request data, assertions, setup, cleanup, SQL, or traceability evidence.
   - When splitting is used, generate `configs/split_index.yaml` with explicit `ordering.execution_order`, `sequence`, `depends_on`, `run_after`, and `run_before` fields so downstream skills can recover the correct order.
   - Set `sql_generation_gate.status: "passed"` only after SQL quality checks pass. Otherwise keep `status: "blocked"` and do not generate SQL-driven tests.
   - Generate `testcases/test_api_cases.py` or interface-complete split equivalents with `pytest.mark.parametrize`, loading cases from `data/cases/` and resolving method/path through `data/interfaces.yaml` or `data/interfaces.py`. Test functions should only call the shared client/assertion fixtures with `case_data`; they must not hardcode per-case request payloads.
   - Generate `testcases/test_*.py` with pytest parametrization and Allure metadata.
   - Generate response assertions with Python `assert` through `core/assertor.py`; every runnable case must assert HTTP status code and response fields.
   - Generate database persistence assertions through the `database_assertor` fixture only. Tests with `@pytest.mark.db_assertions([...])` must use the `database_assertor` fixture, execute SELECT queries through the `database_engine` fixture, and assert persisted row count/fields directly.
   - Generated Python scripts must include concise Chinese comments in UTF-8 for module responsibilities, fixture lifecycle, data injection, variable extraction, assertions, cleanup, coverage traceability, and key control-flow or safety lines. Comments must explain maintenance intent, not repeat obvious code.
   - Variable extraction names, `${variable}` placeholders, runtime context keys used for injection, and SQL bind parameter names must be valid Python identifiers and must not be Python keywords. Do not generate variables with spaces, hyphens, dots, or other characters that can break Python execution.
   - Use token-first authentication. Generate `auth.placement` and optional `auth.method_overrides` from source-bound auth rules so token can be injected into header/query/body/cookie according to request method. If unspecified, use header `Authorization: Bearer <token>` as the executable default.
   - Record each generated pytest test's nodeid in `configs/generation_status.yaml`. Single-interface tests must map back to the executable case ID, design case ID, coverage object IDs, coverage rule IDs, and test point ID. E2E flow tests must map back to the flow ID plus the ordered source executable case IDs they orchestrate. `chain_script_coverage.status` must be `passed` with empty missing lists before `next_stage_allowed: true`.
   - For a new or materially updated framework, record `case_denominator_conservation.status` and the manifest path in `configs/generation_status.yaml`. Collection mapping covers every ordinary case and Flow written into the default structured data exactly once, including collected nodes that intentionally skip at runtime; archive-only manual and dedicated optional-async records remain under their existing gates, and live execution selection remains owned by the readiness gates.
   - Generate `generation_status.yaml.case_confidence_gate` with candidate/declared/high/medium/low counts and empty missing, invalid, low-live, and archive-missing ID lists. Confidence labels are reporting metadata; they must not branch request execution or assertions.
   - Use fixtures for token acquisition, optional precondition data setup, post-test cleanup, and runtime variable sharing. Do not inline setup/cleanup calls directly inside test assertions.
   - Mark main path cases with `@pytest.mark.main_flow` and branch path cases with `@pytest.mark.branch_flow`.
   - Attach source-bound setup rules with `@pytest.mark.preconditions([...])` and cleanup rules with `@pytest.mark.cleanup([...])`; require generated tests that use either marker to include the `case_data_manager` fixture. API cleanup rules must declare `cleanup_identity.field: "id"` and an `id` source such as `params.id`, `json.id`, `path.id`, or `runtime_context.id`. When an API cleanup consumes a variable produced only after a request succeeds, declare that variable in `skip_if_missing_runtime_vars`; the runtime may skip only that explicitly conditional cleanup when the producer failed before emitting the variable, while every cleanup with available identity must still execute and aggregate failures.
   - Attach SQL setup/cleanup by marking each SQL-driven test with `@pytest.mark.case_id("<source-case-id>")` and including the `case_sql_manager` fixture. The fixture reads `data/case_sql_commands.yaml` and executes the full SQL lifecycle: setup before the business request, then runtime extract, cleanup, and final verify after the test. If a marker is missing but `case_data.case_id` and SQL materialization metadata prove the case is SQL-driven, the fixture may resolve the case id from case data and validators must treat the missing marker as a materialization defect to fix in generated parameters.
   - Make SQL lifecycle execution idempotent per case and stage key. If ordinary parametrization, optional async entrypoints, or E2E flow steps can reach the same case SQL entry, generated runtime state must prevent duplicate `runtime_extract`, duplicate delayed waits, duplicate cleanup, or duplicate final verification for the same intended case/stage unless the command is explicitly modeled as a safe no-op reentry.
   - Never generate MCP database connection code, Apifox MCP calls, MCP query helpers, MCP result files, or tests that depend on MCP at runtime. Database access inside generated scripts must go through pytest fixtures and `configs/database.yaml`; MCP is allowed only in upstream evidence-gathering stages before this generator runs.
   - Keep `requirements.txt`, `check_dependencies.py`, and `core/dependency_check.py` aligned so runtime dependency checks happen before loading request/allure/YAML-dependent framework code. Preserve the bundled exact-version/hash lock, `core/security_redaction.py`, and `core/sql_ownership.py` when copying the template; install with `--require-hashes --only-binary=:all:`. Confirmed AES-256-ECB/PKCS7/Base64 adapters use in-process `cryptography` without passing keys to subprocesses. SQL UPDATE/DELETE must bind every declared `ownership.keys` field in every WHERE branch; every mutation requires exact `affected_rows` or an explicit `affected_rows_max` as well as any minimum.
   - When the unified runtime configuration contract applies, generate one operator-facing placeholder form, a deterministic no-network preflight, standardized `runtime_configuration_entry` status metadata, redaction, version-control exclusion, and one authoritative source mapping into the existing env/auth/database layers. Do not embed real secrets or create silent fallback to legacy sources.
   - Keep `reports/` only for Allure runtime output; do not place project documentation there. Generate final reviewer/archive case artifact such as `api-test-framework/接口案例.md` according to `references/final-case-archive.md`; it is a case ledger, not project documentation.

5. **Validate**
   - Run structural validation: required directories and files exist.
   - Confirm `configs/input_precheck_report.yaml` has `status: "passed"` before any code generation result is marked ready.
   - Run dependency validation with `python3 api-test-framework/check_dependencies.py` before pytest collection; when `transport_encryption.enabled=true`, the dependency checker must also validate the crypto runtime dependency declared by the adapter.
   - Run SQL static validation with `python3 api-test-framework/check_sql_commands.py --env=dev` when SQL commands exist.
   - After database configuration is available, run SQL runtime validation with `python3 api-test-framework/check_sql_commands.py --env=dev --runtime`. This validates SQL in one transaction and rolls back after checking row counts.
   - Run syntax validation for generated Python files.
   - Run `python3 <component-skill-dir>/scripts/validate_case_denominator_conservation.py <framework-dir> --executable-case-set <execution-case-set> --required-chain-flows <required-chain-flows>` before pytest collection. Existing frameworks without the new manifest use compatibility checks only; a declared gate or manifest must pass the strict frozen-denominator checks.
   - Run `pytest --collect-only --flow=all` when dependencies are available.
   - When a unified runtime configuration entry is generated, run its parser/security tests and no-network preflight before collection. Missing user values may keep live execution pending, but parser drift, fallback, redaction failure, or an uploadable sensitive form blocks runtime usability.
   - Run the runtime usability gate from `references/runtime-usability-gate.md` whenever dependencies and a runnable environment are available, run report-failure triage from `references/runtime-failure-diagnosis.md` when a broad run has failures, and always run the non-network parts of those gates before final reporting.
   - When `configs/sql_runtime_lifecycle_gate.yaml` is applicable, run `python3 <component-skill-dir>/scripts/validate_sql_runtime_lifecycle_gate.py <framework-dir>/configs/sql_runtime_lifecycle_gate.yaml`. When no conditional check applies, record `not_required` in generation status and keep this gate out of the blocking path.
   - Run `python3 <component-skill-dir>/scripts/validate_flow_semantics_gate.py <framework-dir> --output <framework-dir>/configs/flow_runtime_semantics_gate.json` after case/flow data is generated. A `failed` result blocks live pytest readiness; a `not_required` result is non-blocking.
   - Run `python3 <component-skill-dir>/scripts/validate_runtime_business_dependency_gate.py <framework-dir>` after case data、preconditions and SQL ledgers are final. This is the generator-side materialization check for the upstream audit, not a duplicate of request/response or SQL lifecycle gates.
   - Run `python3 <component-skill-dir>/scripts/validate_specialized_runner_materialization.py <framework-dir>` whenever the capability is discovered. For `all_generated_cases` or cold-start reproducibility claims, regenerate into a fresh temporary framework from upstream facts, compare with `--rebuilt-framework`, run all other applicable gates against the fresh framework, then delete the temporary framework. Semantic equality is required; byte-identical Python is not.
   - For an existing framework targeted fix, validate the declared same chain or selected subset plus changed shared utilities first; run full-suite validation only when claiming `all_generated_cases` readiness or when a shared utility change could affect unrelated chains.
   - Run the runtime-evidence script materialization audit from `references/runtime-evidence-script-materialization.md` whenever generated runnable cases cite runtime evidence. If mismatches exist, mark `FAILED_RUNTIME_EVIDENCE_SCRIPT_MATERIALIZATION`, block broad pytest execution, and fix generated data before product-defect triage.
   - Validate assertion strength and business-result observability: every selected live case reaches its minimum `assertion_strength`, and every side-effect/business-result case has follow-up API verification or scoped DB assertion. Cases that cannot be observed by API or DB must be non-live/manual review and cannot count as live-executed.
   - Validate setup/cleanup materialization and cleanup-closure strategy: every selected live mutable case has either executable API cleanup, executable SQL cleanup, same-interface restore, isolated-account/snapshot containment, or an explicit source-bound no-cleanup rule; every generated cleanup fixture is attached to the pytest case that needs it; DB before/after is required only for cases whose local persistence may change and cannot be proven no-side-effect by stronger source/runtime evidence; `case_sql_commands.yaml` cannot be empty while selected live cases require SQL setup/cleanup. When `target_run_scope=all_generated_cases`, `selected_case_count` must equal `generated_candidate_case_count`, `runnable_case_count` must equal `selected_case_count`, all missing/excluded/non-live lists must be empty, and SQL runtime validation must be passed for SQL-driven cases. `generated_non_live` or `manual_review_only` candidates may remain in status/archive, but they block any claim that every generated case was live-executed.
   - Validate SQL marker materialization: every SQL-driven case according to the shared predicate has exactly one `case_id` marker, includes `case_sql_manager`, has matching commands when SQL commands are required, and is listed under runtime DB readiness when its only remaining blocker is DB env/driver/tunnel. Missing marker, missing fixture, or late unresolved SQL runtime variable is a generator/runtime-usability defect, not a product defect.
   - Validate request shape fidelity and archive/collection parity: case data, flow data, `接口案例.md`, and generated collection artifacts preserve the same plaintext field kinds, nesting, array order, `null`, and omission intent as the source evidence or execution-level artifact.
   - Validate persisted-value and aggregate assertions: SQL expected values compare against the source-confirmed stored representation after serialization/type conversion, and derived counters, balances, scores, rates, or latest-time fields use source formulas, before/after deltas, or current-run extraction instead of fixed historical constants.
   - Validate existing-state precondition closure for uniqueness/idempotency/relationship write cases: source/runtime evidence must prove there is no conflicting prior state, or the generated framework must run precise pre-clean/restore before the positive write request. If this cannot be proven, keep the case as `blocked_live_execution` or `generated_non_live` with the needed pre-state evidence.
   - Validate SQL fixture partitioning before long-chain gates: long-chain SQL checks inspect only SQL entries attached to required flow step case ids, and ordinary SQL checks inspect `case_sql_manager` attachment plus setup/cleanup materialization for ordinary case ids. Never use the total `case_sql_commands.yaml` case count as a proxy for required flow count.
   - Validate `data/flow_cases.yaml` or `data/flow_cases.py` whenever required or present: every required flow id exists, every step case id exists, every injected runtime variable has a prior producer step or an explicit environment/auth entry, every extraction path is explicit, and every generated flow test nodeid is collected.
   - Validate account-specific flow login entry whenever present: a flow marked with `specific_account_required`、`required_account_role`、`required_account_business_state` or `account_specific_chain` must have a login/auth first step, token extraction, and account-context extraction or an explicit source-bound reason that no account context beyond token is required.
   - Validate ordinary-case account bootstrap whenever non-anonymous ordinary API cases use dynamic auth: generated tests or fixtures must authenticate before business steps, update the role/account auth context, avoid token injection into pre-login auth requests, reuse the shared requester/session by account group, skip duplicate fixture login for explicit login cases, and record the strategy in `generation_status.yaml` or an equivalent runtime-usability section without storing secrets. Root validation must verify this record and the generated fixture/registry shape; prose-only notes are not sufficient evidence.
   - Compare collected pytest nodeids with the executable case index and required E2E flow index. Do not mark coverage-response readiness unless every executable case has one pytest nodeid, every required flow has one flow pytest nodeid, collected pytest case count equals `executable_case_count + e2e_flow_case_count`, and every coverage rule has at least one pytest nodeid.
   - Run real pytest execution only when the user provided a real runnable environment and explicitly expects execution.

## Failure Branches

- Missing or unreadable input: stop with `blocked`, create only `configs/generation_status.yaml` when an output directory is needed, and list missing files.
- Input precheck failure: stop with `blocked`, write `configs/input_precheck_report.yaml`, and do not generate API wrappers, test data, SQL commands, or pytest modules.
- Gate failure or case-free input: keep generated output case-free and do not create API wrappers, data files, or pytest modules.
- Missing executable values: list the exact missing request/assertion/env/auth/cleanup fields and refuse to guess.
- Missing chain flow evidence: when upstream requires chain scripts but ordered steps, producer/consumer extraction, injection target, chain assertion, setup, or cleanup boundary is missing, stop with `blocked`; do not generate a single-interface-only framework and do not mark `next_stage_allowed: true`.
- Missing cleanup materialization: when a selected live mutable case has only cleanup references or DB before/after evidence but no executable API/SQL cleanup action, stop live execution with `blocked`. If `target_run_scope=all_generated_cases`, keep the case in `blocked_real_run_case_ids`; only `safe_subset` may exclude it from the executable denominator with a recorded exclusion reason. Do not generate runnable pytest for cleanup_refs-only mutable cases. If the business scenario is source-confirmed but cannot be safely cleaned, preserve it as `generated_non_live` or `manual_review_only` in the case ledger/archive with source reason, assertion boundary, and the evidence still needed for live automation.
- Runtime evidence materialization mismatch: when generated script data differs from the runtime evidence candidate's request, role variable, per-step expected business code/message, or evidence mapping, stop with `failed` using `FAILED_RUNTIME_EVIDENCE_SCRIPT_MATERIALIZATION`; do not rerun broad pytest or confirm product defects from the mismatched scripts.
- Missing assertion strength or observability: when a runnable case lacks `assertion_strength`, lacks `result_observation_mode`, falls below the minimum strength for its scope, or cannot prove the business result through API/DB observation, stop live execution with `blocked` and list the exact cases.
- Missing runtime business dependency closure: when the upstream audit is absent/incomplete, an applicable mutable dependency lacks executable precheck, or a state-changing precheck lacks restore, keep the affected case blocked or source-bound non-live; do not substitute another legal-looking request value and do not classify the resulting business rejection as a product defect.
- Missing specialized-runner materialization: when a generated case/Flow declares a specialized runner but the upstream fact contract、uniform adapter、consumer set、authoritative non-generated source refs、assertion/cleanup/failure-path obligations or generated files are incomplete, stop with `FAILED_SPECIALIZED_RUNNER_MATERIALIZATION`. Do not inline one-off branches into pytest or remove the consumers from the denominator. Existing targeted patches that do not change any runner keep unrelated legacy runners outside patch scope, but cannot claim full cold-start reproducibility.
- Missing runtime environment values after configuration entrypoints are generated: do not block script generation; mark `live_execution_readiness.status: pending_runtime_config` with the exact config files, pytest options, environment variables, drivers, or network tunnels required before real pytest execution.
- Missing long-chain value completion: when `long_chain_missing_value_fields.yaml` exists with `status=pending_user_input|blocked` or `open_required_count>0`, stop with `blocked`; do not generate scripts from unfilled checklist rows or placeholder values.
- Validation failure after generation: keep generated files, mark status as `generated`, record the failed command, and do not claim downstream readiness.
- Split boundary conflict: stop with `blocked` if a file is too large but there is no safe interface-complete boundary for splitting.
- Split ordering conflict: stop with `blocked` if split dependencies have a cycle or if source evidence cannot determine required ordering.

## Downstream Boundary

Allow the next automation stage only when `configs/input_precheck_report.yaml` has `status: "passed"`, `generation_status.yaml` has `next_stage_allowed: true`, source-bound case count is greater than zero, generated Python compiles, pytest collection passes, non-network runtime usability gates pass, the capability-triggered SQL runtime lifecycle、flow runtime semantics and specialized-runner materialization gates are each passed or not required, the runtime business dependency materialization gate is passed or not required, and `generation_status.yaml` proves `coverage_traceability`、`pytest_collection_mapping` and required `chain_script_coverage` are complete. Concrete runtime environment values may remain pending only when `runtime_configuration_entry` exposes how to provide them and `live_execution_readiness` lists the pending inputs. For full-suite real execution, `target_run_scope` must remain `all_generated_cases` and no selected/excluded/non-live count may silently reduce the suite. Source-bound non-live or manual-review cases may remain generated/archived only with explicit `automation_decision`, and they block claims that all generated cases were live-executed. Otherwise, report the blocked items for upstream repair.

## Input Precheck Gate

Before generating any code or SQL, produce an input precheck result with these checks:

- File availability: all required input files exist, are readable, and are not empty.
- Encoding quality: all text is UTF-8 without garbled Chinese or replacement characters.
- Stage status: upstream artifacts are not case-free, blocked, or explicitly non-convertible.
- Case traceability: every executable case has a stable case ID, design case ID, coverage object ID, coverage rule ID, test point ID, title, flow type, request contract, expected status, assertion evidence, and priority.
- Precondition consistency: every case requiring setup, token, cleanup, variable extraction, or variable injection has a matching source-bound rule.
- Token auth compatibility: token source, extraction path when dynamic login is used, default injection placement, per-method overrides, and generated auth config are sufficient for executable requests.
- Account-specific chain login entry: every account-specific required flow starts with a login/auth step in `data/flow_cases.yaml` or `data/flow_cases.py`; the step extracts token and required account context into `runtime_context`, and later steps consume those variables instead of relying on a hidden fixture or guessed static token.
- Dependency payload contract: downstream dependencies are represented as JSON-path extraction rules or regex extraction rules with producer/consumer mapping and source evidence.
- E2E flow contract: every required flow from `required_chain_flows.yaml` is represented in `data/flow_cases.yaml` or `data/flow_cases.py`, each step references a source executable case, producer/consumer variable evidence is explicit, and the readable pytest entrypoint uses `run_flow`.
- Data-driven script contract: ordinary API cases are stored under `data/cases/`, interface definitions are stored in `data/interfaces.yaml` or `data/interfaces.py`, scenario chains are stored in `data/flow_cases.yaml` or `data/flow_cases.py`, and ordinary API pytest modules use `pytest.mark.parametrize` to call the generated case data.
- Long-chain missing value completion: no required long-chain field remains pending user input, and any filled values have already been propagated to executable cases and fact sources.
- Assertion executability: every runnable case has Python `assert` checks for status code and response fields.
- Assertion strength: every runnable case has `assertion_strength` and reaches the minimum level for its scope; write and long-chain cases are not treated as business-closed with only `L1_basic`.
- Case confidence: every ordinary, error, optional/non-live/manual-review case and E2E flow has a recalculable confidence object; low-confidence cases stay traceable but cannot enter the live denominator, and medium/high scores do not bypass existing gates.
- Business result observability: every side-effect or business-result case has follow-up API verification, scoped DB assertion, cleanup verification, or a non-live/manual-review decision.
- Runtime evidence script materialization: every evidence-backed generated step preserves the source request variant, role/session context, semantic runtime placeholders, expected HTTP status, expected business code/message, and evidence id; unreleased evidence candidates are excluded or block the runnable denominator.
- Specialized-runner materialization: every non-generic runner is justified by capability, declared by one upstream source-owned contract, mapped exactly to consumer IDs, exposed through the uniform adapter, backed by non-generated authoritative refs, and covered by result、cleanup and failure-path obligations; projects without such runners are `not_required`.
- Runtime business dependency audit: the upstream audit scans the exact execution-case set; applicable mutable dictionary/configuration/eligibility/quota/external-state dependencies have predicates、source refs and executable precheck/restore decisions, while a complete no-dependency scan may be `not_required`.
- Request shape fidelity: generated case data, flow data, archive entries, and generated collection artifacts preserve source-visible scalar/list/object/map shapes, nesting, array order, `null`, and intentional omissions; serialized forms are used only at confirmed transport or persistence boundaries.
- Persisted-value and aggregate assertion fidelity: DB assertions compare against the stored representation proved by source/runtime evidence, and derived or aggregate assertions are formula/current-run based instead of hardcoded historical snapshots.
- Validation/error branch isolation: branch cases that intentionally omit or invalidate one target field keep every unrelated required field and context legal, so the expected assertion proves that target branch rather than an earlier validation failure.
- Request variant consistency: ordinary cases, E2E flow steps, optional async cases, and archive cases that reuse the same method/path and compatible request variant preserve the confirmed required field set and source-bound business parameters unless a source/runtime reason explains the difference.
- Database assertion fixture readiness: every persistence assertion has a SELECT query, bind params, expected row count/fields, and can be executed through `database_assertor` using `database_engine`.
- Precondition construction priority: every setup or cleanup rule uses API construction first; SQL is allowed only when the upstream rule records API insufficiency reason, source evidence, impacted case ID, target tables, ownership keys, cleanup order, seed-scope guard, and SQL gate inputs.
- Seeded value closure: every setup-produced value consumed by request fields, assertions, DB assertions, variables, or cleanup is already filled in the execution case as a concrete value or executable variable reference, and has confirmed provenance. The same evidence must prove the value is inside the minimal allowed seed field list and does not replace normal request input, long-chain producer output, execution-config value, generated unique value, or external dependency value. External dependency values have explicit sandbox/mock/callback evidence and are not satisfied by local DB seed SQL.
- Business-readable input quality: positive-path, live, long-chain, and page-visible fields use source-bound legal values; bounded generic real-world legal samples are allowed only for ordinary user-entered/profile/display fields whose contract permits legal literals. Placeholders are allowed only for explicit invalid-value/error-branch cases and must have matching assertions.
- Seed scope guard: every API/DB setup-produced value has an upstream `seed_scope_guard` fact or equivalent rule section proving `allowed_seed_fields`、`forbidden_seed_fields`、`runtime_value_fields` and `distortion_risk=low`.
- Historical-shape SQL setup: every SQL setup INSERT/UPDATE has a passed `historical_shape_reference` or equivalent upstream fact proving bounded historical shape review for field formats, enum/status values, JSON/null/time conventions, page-visible value quality, and role relationship direction.
- Database cleanup identity: every database test datum generated during script execution records `id`; cleanup rules must delete only the current script-generated data by `id`.
- Cleanup closure strategy: every candidate has `closure_mode`, `evidence_strength`, and `automation_decision`; source-confirmed no-side-effect and sandbox-isolated cases are not forced through DB before/after, while business-valid non-live cases stay traceable and cannot be counted as live execution.
- Setup/cleanup materialization: every selected live case that creates, updates, deletes, mocks, seeds, or restores data has executable setup/cleanup rules, fixture attachment, id/ownership boundary, and before/after or stronger no-side-effect/containment evidence; references alone are not sufficient.
- Write-side cleanup policy: every selected live write-side-effect case has materialized cleanup, same-interface restore, isolated containment, or an explicit source/runtime cleanup exemption reason.
- Target real-run scope consistency: when the requested scope is `all_generated_cases`, no candidate case may be excluded from the executable denominator; blocked readiness and non-live decisions must stay visible as blockers instead of being treated as a smaller safe subset.
- SQL mutation exit gate: every INSERT or DELETE command has a command-level `sql_exit_gate`, one-table scope, id-bound SQL, exact affected-row expectation, and runtime before/after row-count validation plan.
- Variable Python compatibility: every extraction variable name, `${variable}` placeholder, runtime context key, generated Python variable, and SQL bind parameter name is a valid Python identifier and is not a Python keyword.
- Data model completeness: every table, field, enum, key, index, and relationship referenced by setup or cleanup exists in the data model artifact.
- Cross-file consistency: case IDs, variable names, entity names, table names, and status values are consistent across all inputs.
- SQL readiness: SQL generation is allowed only when data model and graph evidence can determine insert order, cleanup reverse order, ownership keys, and affected-row expectations.
- Transport crypto contract: when encrypted interfaces are confirmed, the contract must include algorithm reference, key source, request payload scope, request serialization, request envelope field, response decrypt field, response parsing rule, and confirmed interface lists.

Use this output shape:

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
  token_auth_compatibility: "passed"
  dependency_payload_contract: "passed"
  e2e_flow_contract: "passed"
  long_chain_missing_value_completion: "passed"
  assertion_executability: "passed"
  assertion_strength: "passed"
  business_result_observability: "passed"
  runtime_evidence_script_materialization: "passed"
  request_shape_fidelity: "passed"
  persisted_value_assertion_fidelity: "passed"
  database_assertion_fixture_readiness: "passed"
  precondition_construction_priority: "passed"
  seeded_value_closure: "passed"
  business_readable_input_quality: "passed"
  validation_branch_isolation: "passed"
  request_variant_consistency: "passed"
  seed_scope_guard: "passed"
  database_cleanup_identity: "passed"
  cleanup_closure_strategy: "passed"
  setup_cleanup_materialization: "passed"
  write_side_cleanup_policy: "passed"
  target_run_scope_consistency: "passed"
  sql_mutation_exit_gate: "passed"
  transport_encryption_policy: "passed"
  transport_crypto_contract: "passed"
  account_specific_chain_login_entry: "passed"
  variable_python_compatibility: "passed"
  data_model_completeness: "passed"
  cross_file_consistency: "passed"
  sql_readiness: "passed"
missing_items: []
blocking_issues: []
```

## Coverage To Pytest Mapping Gate

`configs/generation_status.yaml` must include a machine-readable mapping from coverage objects and executable cases to pytest tests:

```yaml
coverage_traceability:
  status: "passed"
  executable_case_count: 10
  e2e_flow_case_count: 1
  design_case_count: 10
  coverage_object_count: 8
  coverage_rule_count: 18
  missing_executable_mappings: []
  missing_pytest_mappings: []
pytest_collection_mapping:
  status: "passed"
  executable_case_count: 10
  e2e_flow_case_count: 1
  collected_test_count: 11
  mappings:
    - executable_case_id: "EXE-TC-001"
      design_case_id: "TC-API-001"
      coverage_object_ids: ["API-001", "FIELD-001"]
      coverage_rule_ids: ["RULE-API-001-SUCCESS"]
      test_point_id: "TP-001"
      pytest_nodeid: "testcases/test_order.py::test_create_order_success"
    - flow_id: "recharge_apple_pay_flow"
      source_executable_case_ids: ["EXE-TC-014", "EXE-TC-015", "EXE-TC-016"]
      pytest_nodeid: "testcases/test_flows.py::test_recharge_apple_pay_flow"
chain_script_coverage:
  status: "passed"
  required_flow_count: 1
  generated_flow_count: 1
  missing_required_flow_ids: []
  single_interface_only_flow_ids: []
  mappings:
    - required_flow_id: "recharge_apple_pay_flow"
      generated_flow_id: "recharge_apple_pay_flow"
      pytest_nodeid: "testcases/test_flows.py::test_recharge_apple_pay_flow"
```

Gate rules:

- The set-equality rules in `references/case-denominator-conservation.md` must pass before count checks. Counts are summaries and cannot hide a missing, extra, or duplicate ID.
- Every executable case must have exactly one generated pytest nodeid unless the source explicitly marks it as a non-runnable manual case; manual cases block coverage-response readiness.
- Every required or generated E2E flow must have exactly one collected pytest nodeid.
- If upstream `required_chain_flows.yaml` contains required flows, `chain_script_coverage.required_flow_count` must be greater than 0, `generated_flow_count` must equal it, and both `missing_required_flow_ids` and `single_interface_only_flow_ids` must be empty.
- `executable_case_count + e2e_flow_case_count` must equal `collected_test_count` before `next_stage_allowed: true`.
- Every coverage rule inherited from execution-level cases must map to at least one pytest nodeid.
- If pytest collection cannot run, keep `pytest_collection_mapping.status: "blocked"` and do not claim full coverage-response readiness.
- Do not infer pytest nodeids from filenames only; use collected nodeids when collection is available.

## Fixture Contract

- `auth_context`: obtain static or dynamic token from source-bound `configs/{env}.yaml` auth rules and keep placement/method override metadata.
- `auth_headers`: expose legacy header token mapping when placement is `header`.
- `authenticated_client`: inject token context into the shared HTTP client before test execution so each request method can place token in header/query/body/cookie as configured.
- `case_account_login`: when ordinary parameterized API cases use dynamic auth, refresh the source-bound account group before the case's business steps, publish extracted token/session/user/device/key-material into `runtime_context`, update the auth-context registry, and reuse the same shared client/session. It must no-op for anonymous cases and for cases whose first step is an explicit `auth`/`login` step. Fixture ordering must place this before API setup, SQL setup, and business request execution.
- `runtime_context`: store token and extracted cross-step variables.
- `database_config`: load database settings for the selected `--env` from `configs/database.yaml`.
- `database_engine`: create and dispose the database instance as a session-scoped fixture; SQL setup/cleanup code must consume this fixture instead of creating database connections directly.
- `case_data_manager`: execute `preconditions` marker rules before each test and `cleanup` marker rules after each test.
- `case_sql_manager`: execute per-case SQL setup and cleanup from `data/case_sql_commands.yaml` using `database_engine`; require `@pytest.mark.case_id`.
- `database_assertor`: assert database persistence through `database_engine` fixture with SELECT queries; require `@pytest.mark.db_assertions`.
- `--flow=main|branch|all`: select main-path, branch-path, or all generated cases.

## E2E Flow Suite Contract

When upstream `required_chain_flows.yaml` marks required multi-interface chains, generate a dedicated E2E flow suite in addition to the supporting single-interface cases. `business_scenario_map.yaml`, `测试覆盖点报告.md`, and execution-level cases may provide candidate/context evidence, but they are not authoritative required-flow denominators unless their flow IDs are confirmed in `required_chain_flows.yaml`. Single-interface tests cannot replace a confirmed required chain script.

Required flow files:

- `data/flow_cases.yaml` or `data/flow_cases.py`: source-bound ordered flow definitions, including `flow_id`, `title`, `story`, `flow_type`, `steps`, `source_executable_case_ids`, extraction rules, injection overrides, and cleanup policy.
- `core/flow_runner.py`: generic flow orchestration that reads `flow_cases.yaml` or `flow_cases.py`, initializes one runtime scope for the complete flow, resolves runtime variables, executes steps through the shared authenticated client, asserts responses, and writes extracted values back to `runtime_context`. It must call the same runtime-scope and login-context helpers used by ordinary cases instead of maintaining a second incompatible implementation.
- `testcases/test_flows.py`: concise pytest entrypoints. Each function should make the business chain obvious and delegate execution to `run_flow`.

Generated flow tests must use this visible shape:

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

Rules:

- Do not use pytest execution order between single-interface tests to simulate an E2E chain.
- Every upstream required `flow_id` must appear exactly once in `data/flow_cases.yaml` or `data/flow_cases.py`.
- Flow steps must be ordered inside `data/flow_cases.yaml` or `data/flow_cases.py`; each step must reference a source executable case id and the API wrapper or method/path generated for that case.
- If a flow needs a specific account, role, tenant, permission, or account business state, the first ordered step must be the login/auth request from the execution-level `login_entry_rule`. The flow runner must execute that visible login step, extract token/account context, then run the business steps. Do not hide the login request inside a fixture for these account-specific flows.
- The flow runner must validate the first step before execution for account-specific flows: `step_type` is `auth` or `login`, the step runs without a prior business token unless the source contract explicitly says otherwise, token extraction is configured, and extracted auth context is written to the target role before later steps resolve requests.
- The producer-consumer dependency must be visible in the YAML/Python data through explicit `extract` and request override entries. Example: extract `recharge_order_id` from one step, inject `${recharge_order_id}` into the next step's request body.
- Flow tests must use `@pytest.mark.e2e_flow` plus `main_flow` or `branch_flow` so existing `--flow` filtering remains useful.
- Flow tests add to pytest collection. Count readiness with `collected_test_count == executable_case_count + e2e_flow_case_count`.
- `generation_status.yaml.chain_script_coverage.status` must be `passed`; `missing_required_flow_ids` and `single_interface_only_flow_ids` must be empty before `next_stage_allowed: true`.
- If the dependency chain lacks source-bound extraction paths, injection targets, chain assertions, cleanup boundaries, or environment/auth entries, block generation with `BLOCKED_NEED_CHAIN_FLOW_EVIDENCE`. Do not downgrade a required chain to single-interface-only scripts.

Generate setup and cleanup rules only from explicit upstream evidence. Use API setup/cleanup as the default construction path. API cleanup must still be id-bound: generated cleanup paths may use `${id}`, and cleanup rules must declare the id source. If an upstream rule requires SQL because API construction cannot satisfy the case, derive commands from confirmed table structures and knowledge-graph relationships, then write them to `data/case_sql_commands.yaml` only after the seed-scope guard proves that SQL creates or changes only the minimal business precondition fields. Every generated database test datum must carry `id`, and cleanup must delete the current script-generated data by `id`. If API insufficiency reason, seed-scope guard, table names, columns, key relationships, required values, `id` cleanup identity, cleanup order, database connection, or driver requirements are missing, block generation instead of inventing SQL.

## SQL Generation Gate

Before setting SQL status to passed, confirm all checks:

- Data model evidence is complete: table names, columns, primary keys, unique keys, required fields, status enums, and relevant indexes.
- Knowledge graph evidence is complete: entity relationships, parent-child order, cleanup reverse order, and aggregate boundaries.
- Ownership boundary is explicit: every generated row has test-owned identifiers, and cleanup uses those identifiers.
- Cleanup scope is narrow: no cleanup SQL may affect rows outside the current case's generated or explicitly test-owned data.
- ID cleanup is explicit: every database test datum generated by the script declares `cleanup_identity.field: "id"`, provides `params.id`, and cleanup SQL uses `WHERE id = :id`.
- INSERT/DELETE exit gates are explicit: every SQL command that adds or deletes database rows must declare `sql_exit_gate.status: "passed"`, `passed: true`, and operation-specific checks before script execution is allowed.
- API insufficiency is explicit: every SQL-driven setup or cleanup command records why API construction cannot satisfy the case and cites source evidence.
- Seed scope is guarded: every SQL-driven setup command records the minimal business precondition it creates, allowed seeded fields, forbidden seeded fields, runtime value fields, affected case IDs, and low distortion risk; SQL must not create ordinary request fields, long-chain response-produced values, tokens, verification codes, device/page/runtime marker fields, or external dependency return values.
- Historical shape is referenced: every SQL-driven setup INSERT/UPDATE command records `historical_shape_reference.status: "passed"` from bounded same-table/same-business-state evidence or equivalent normalized DB evidence; the evidence confirms values are structurally valid and relationship fields have the correct actor/counterparty direction.
- SQL lifecycle variables are stage-correct: case-level `params` and `setup.params` may reference only values available before the business request. Runtime ids produced by response extraction or `runtime_extract`, such as order, feedback, report, message, task, conversation, and settlement ids, must be consumed only by post-request `runtime_extract`、`cleanup` or `final_verify`.
- SQL setup values satisfy table constraints: target columns exist, generated values respect type/nullability/enum/length/JSON/time shape, and runtime markers are short enough for their target columns after placeholder resolution.
- SQL expected values satisfy persistence shape: request-side lists, objects, date/time values, enums, markers, and generated display values are compared using the stored database representation proved by source code, ORM/MyBatis mappings, database evidence, or runtime evidence. Do not guess JSON strings, text wrappers, or time formats.
- SQL-derived assertions are not historical constants: aggregate counters, balances, scores, rates, task progress, latest-time fields, and other derived values must be verified through source formulas, before/after snapshots, current-run runtime extraction, or follow-up API/DB queries scoped to the current ownership key.
- SQL verification shape matches executor capability: each `expected_<field>` matches a field returned by the same `verification_query`; any additional verification concern is a separate `final_verify` command unless the generated executor explicitly supports and validates a documented multi-query schema.
- Cleanup and verification boundaries match: current-run id cleanup verifies current-run id absence; pair/entity-level absence requires setup isolation or pre-clean of that same wider boundary.
- Dynamic persistence ids are extracted, not guessed or hardcoded, unless source evidence proves a fixed test-owned configuration row.
- Dangerous SQL is rejected: no `DROP`, `TRUNCATE`, `ALTER`, `CREATE`, `GRANT`, `REVOKE`, broad `DELETE`, broad `UPDATE`, multi-statement SQL, `WHERE 1=1`, or full wildcard cleanup.
- Target tables are whitelisted by the gate and every command declares `target_tables`.
- Every command has `source_evidence`, `api_unavailable_reason`, `api_unavailable_source_evidence`, `cleanup_identity`, `target_tables`, and `ownership.keys` containing `id`. Setup commands must also have `seed_scope_reason`, `allowed_seed_fields`, `forbidden_seed_fields`, `runtime_value_fields`, `distortion_risk: "low"`, and passed `historical_shape_reference`.
- Setup SQL is limited to `INSERT` or bounded `UPDATE`; cleanup SQL is limited to bounded `DELETE` or bounded `UPDATE`.
- INSERT must explicitly list columns, write `id`, bind `id` with `:id`, declare `expected_effect.affected_rows: 1`, and pass runtime checks proving the id did not exist before insertion and exists exactly once after insertion.
- DELETE must use `WHERE id = :id`, operate on one approved table, declare `expected_effect.affected_rows: 1`, and pass runtime checks proving the id existed exactly once before deletion and no longer exists after deletion.
- SQL values are source-bound literals or runtime variables, never guessed values.
- SQL syntax and bind parameters are validated by `check_sql_commands.py`.
- SQL logic is validated through declared `expected_effect.affected_rows`, ownership keys, target table whitelist, setup/cleanup ordering, and runtime row-count checks.
- SQL fixture scope is partitioned before coverage checks: required-flow SQL entries are derived from flow step case ids, ordinary SQL entries are derived from ordinary case data and `case_sql_manager` markers, and neither bucket may be inferred from the total YAML entry count alone.
- Real pytest execution is allowed only after runtime validation sets `quality_checks.runtime_validation_verified: true`.

## SQL Command File Contract

Use this file for database setup and cleanup:

```text
api-test-framework/data/case_sql_commands.yaml
```

Each case entry must contain only source-bound SQL:

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
    seed_scope_guard_verified: true
    historical_shape_reference_verified: true
    runtime_validation_verified: true
  allowed_tables:
    - "user_account"
  validation_report: "data/case_sql_validation.yaml"
cases:
  TC001:
    setup:
      - name: "准备用户数据"
        source_evidence: "前置数据构造规则.md#TC001"
        api_unavailable_reason: "目标历史状态无可用业务构造接口"
        api_unavailable_source_evidence: "前置数据构造规则.md#TC001-API不可满足说明"
        seed_scope_reason: "仅准备目标历史状态，接口请求普通字段由用例入参或变量注入提供"
        allowed_seed_fields: ["id", "status"]
        forbidden_seed_fields: ["token", "smsCode", "pageNum", "pageSize", "deviceId", "thirdPartyOrderId"]
        runtime_value_fields: ["request.body", "auth.token", "runtime_context"]
        distortion_risk: "low"
        historical_shape_reference:
          status: "passed"
          source_ref: "database_mcp_evidence_index.yaml#user_account-valid-active-shape"
          sampled_table: "user_account"
          sample_scope: "same_business_state_recent_non_deleted"
          sample_count: 3
          verified_fields: ["id", "status"]
          privacy_status: "sampled_shape_only_redacted"
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
      - name: "清理用户数据"
        source_evidence: "前置数据构造规则.md#TC001"
        api_unavailable_reason: "前置数据使用 SQL 构造，需按同一归属键执行数据库清理"
        api_unavailable_source_evidence: "前置数据构造规则.md#TC001-API不可满足说明"
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

Require `configs/database.yaml` to contain the selected environment node with `enabled`, `connection_url`, and `sql_commands_file` before generating tests that use `case_sql_manager` or database persistence assertions.

The runtime fixture creates the database instance once per pytest session and disposes it after execution. It also validates the gate before executing SQL. If the gate is blocked, runtime validation has not passed, a command targets an unapproved table, a command that inserts or deletes rows lacks `sql_exit_gate`, an INSERT does not bind `id` through `:id`, a DELETE/UPDATE lacks `WHERE id = :id`, a command does not declare `cleanup_identity.field: "id"`, or affected row counts differ from `expected_effect.affected_rows`, execution must fail before or during the bounded database transaction.

## Output Contract

Return a concise stage report with:

- Stage status: `blocked`, `generated`, or `validated`.
- Generated path.
- Files created or changed.
- Gate decision and source evidence.
- Validation commands and results.
- Dependency check result and any missing package/version.
- Main flow and branch flow case counts.
- SQL command file path, SQL validation report path, SQL-driven case count, static validation result, runtime validation result, and database gate result.
- SQL runtime lifecycle gate applicability, audit path when applicable, and non-duplicated phase/context/selection/baseline/evidence-scope results.
- Runtime business dependency audit status, dependency/materialized counts, affected case IDs, and any missing precheck/restore items.
- Specialized-runner gate applicability、manifest path、runner/consumer counts、non-circular source result and cold-start semantic comparison result when full reproducibility is claimed.
- Split index path and any file-size or interface-boundary decisions when splitting is used.
- Split execution order and dependency graph when splitting is used.
- Blocking missing items when case-free or generation is refused.
- Defect list path when runtime failures are reviewed. Confirmed defects must be written as Markdown, separate from generated cases, and must include real scenario, complete plaintext request/response evidence, and DB table/field changes when persistence changed. Items without complete response body or DB before/after remain defect candidates, not confirmed defects.

Never write a standalone project explanation Markdown file unless the user explicitly requests it.
