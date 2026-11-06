---
name: executable-interface-case-set
description: "Generate execution-level Chinese API test case sets and precondition data construction rules from design-level interface test cases, gate reports, database models, lightweight table knowledge graphs, optional Apifox MCP evidence, structured API contracts, and interface test design documents. Use when Codex needs to prepare source-bound cases that can be converted into pytest+allure scripts with complete concrete request parameters, expected outputs, assertions, dynamic variable extraction, setup data, cleanup rules, and execution readiness gates."
---

# Executable Interface Case Set

## Goal

Use this stage skill after `gated-interface-testcases` has produced a released design-level case list. Combine these inputs into execution-level API cases that can be converted into pytest+allure scripts. The output must be sufficient to generate complete test scripts except for three external integration inputs: 环境配置、pytest 工程规范、allure 标注规范。

- `case_list.yaml`（优先）或 `测试用例清单.md`（兼容展示）
- `执行报告.md`
- `接口结构化契约清单.md`
- `接口测试用例设计文档.md`
- `required_chain_flows.yaml` 和 `chain_flow_candidate_audit.yaml`：用于承接已确认必须生成链路脚本的多接口业务场景及候选链路审计结果
- `business_scenario_map.yaml`、`业务场景链路清单.md` 和 `测试覆盖点报告.md`：仅作为链路候选、上下文和人工复核参考，不得单独作为必须生成链路脚本的依据
- `09-interface-encryption-policy.md` 或 `source-api-facts.json#project_encryption_policy`：用于识别接口级请求加密、响应解密、明文豁免候选和待确认策略
- `数据模型.md` 或数据库结构 Markdown 文档：必须包含表结构、键约束、状态/枚举、轻量表关系知识图谱、铺数顺序、清理逆序、归属键和清理边界
- Optional `04-runtime-evidence-plan/runtime_risk_audit.yaml`、`db_before_after_probe_plan.yaml` and `runtime_blocker_candidates.yaml` when requester-backed evidence planning was run before this stage
- Optional `04-runtime-evidence/runtime_evidence.yaml` and `runtime_value_catalog.yaml` when direct runtime evidence was collected before this stage
- Optional Apifox MCP contract/testcase/example evidence when available, explicitly requested, or referenced by execution facts
- 环境引用、鉴权账号配置，以及可从源材料提取或用户提供的清理策略

By default, the stage writes two human-readable Markdown deliverables and three machine-readable sidecars in a dedicated output directory:

- `执行级接口用例集.md`
- `前置数据构造规则.md`
- `stage_status.yaml`
- `coverage_matrix.yaml`
- `execution_fact_sources.yaml`

When Apifox MCP evidence is consulted or referenced by `execution_fact_sources.yaml`, also write:

- `apifox_evidence_index.yaml`

When any long-chain execution case still needs user-provided values after all allowed source, DB, precondition API, runtime evidence, and execution-config completion attempts, also write:

- `长链路缺失码值补充清单.md`
- `long_chain_missing_value_fields.yaml`

These two files are a blocking user-input handoff, not downstream script inputs. After the user fills the missing values, update `执行级接口用例集.md`, `前置数据构造规则.md`, `execution_fact_sources.yaml`, and `long_chain_missing_value_fields.yaml` before allowing script generation.

When the case volume is too large for a single reviewable file, or when the user explicitly asks for splitting, the stage may use sharded output. Sharded output must keep the same root deliverables and sidecars and add only:

- `执行级用例分片索引.md`
- `执行级用例分片/001_<稳定名称>.md`, `执行级用例分片/002_<稳定名称>.md`, ...

In sharded mode, downstream skills must read files in this order: `执行级接口用例集.md` -> `前置数据构造规则.md` -> `执行级用例分片索引.md` -> shard files by the index `顺序` column from `001` upward. Do not rely on filesystem listing order.

Do not generate pytest code, runnable scripts, mock files, request demo JSON files, README files, or extra Markdown documents from this stage unless explicitly requested. The required YAML sidecars are part of this stage contract, not extra documentation. In sharded mode, only the shard index and shard files above are allowed as extra Markdown deliverables.

## Stage Resources

- Read `references/io-contract.md` when the user asks about required inputs, missing data, stage status, downstream pytest handoff, output fields, or validation rules.
- Use `assets/templates/执行级接口用例集.template.md` and `assets/templates/前置数据构造规则.template.md` as the canonical output templates.
- Use `assets/templates/长链路缺失码值补充清单.template.md` and `assets/templates/long_chain_missing_value_fields.template.yaml` after execution-level long-chain cases are generated and before script generation whenever any required long-chain field still lacks a confirmed executable value.
- Use `assets/templates/runtime_execution_config.template.yaml` when environment, account, auth, crypto, execution authorization, or DB authorization input is missing before execution-level filling. Present it to the user as a fillable run-specific artifact, not as a project-specific skill rule.
- After writing the Markdown deliverables and YAML sidecars, run `python3 scripts/validate_outputs.py <输出目录>` from the skill directory or by absolute path.
- Treat validator success as structural readiness for the execution-case stage only. It does not mean generated pytest code has already run.

## Required Sequence

```text
输入存在性初检
-> 全输入前置校验
-> gated 设计级准出检查
-> 建立接口/用例/契约/数据模型索引，按需建立 Apifox 证据索引
-> 执行级输入缺口分析
-> 运行时取证规划消费与执行事实补齐
-> 可变字典/配置/资格状态依赖审计
-> 前置数据构造与变量链路设计
-> 精确断言与动态断言设计
-> 清理策略与可重复执行校验
-> 长链路缺失码值扫描与人工补充清单生成
-> 执行级用例合并去重
-> 脚本生成准出门禁
-> 输出 Markdown 产物、结构化 sidecar、按需 Apifox 证据索引或有序分片产物
-> 运行 validator
```

Do not invent concrete request values, response values, business codes, account credentials, environment URLs, database facts, cleanup SQL, Apifox responses, or runtime evidence. This stage must not directly request live interfaces; when live values are needed, consume only confirmed facts from `04-runtime-evidence/` and use `04-runtime-evidence-plan/` only to preserve risk, DB before/after, cleanup, blocker, and manual-confirmation traceability. If a required execution fact is missing, mark the stage as `BLOCKED_NEED_EXECUTION_INPUT`.

## Precheck Gate

Run this gate before indexing, optional Apifox evidence collection, or execution-case generation. Record the result in `前置数据构造规则.md`.

| 校验项 | 通过标准 | 失败状态 |
|---|---|---|
| 文档完整性 | 所有必需 Markdown 文档存在、可读、非空、UTF-8、无疑似乱码 | `FAILED_DESIGN_GATE` |
| 设计级准出 | `执行报告.md` 阶段状态为 `PASSED`，且无阻塞项未关闭 | `FAILED_DESIGN_GATE` |
| 用例基础字段完整性 | 设计级每条用例具备用例名称、用例类型、追溯接口、请求方式、追溯测试点、覆盖对象ID、覆盖规则ID、设计级用例ID、前置条件、入参、出参、状态码、断言点、用例优先级 | `FAILED_DESIGN_GATE` |
| 覆盖继承完整性 | `测试用例清单.md`、`执行报告.md`、`接口测试用例设计文档.md` 中的覆盖对象、覆盖规则、设计级用例和测试点映射可对账，且无覆盖不足、未覆盖、待补充、阻塞项 | `FAILED_DESIGN_GATE` |
| 主要流程字段完整性 | 主流程/成功路径具备触发条件、接口链路、请求方式、接口路径、前置数据、成功状态码、成功业务码或成功响应、关键断言 | `FAILED_DESIGN_GATE` |
| 链路场景完整性 | `required_chain_flows.yaml` 中已确认必须生成的链路，必须能映射到执行级有序步骤、生产者/消费者变量链路、提取规则、注入目标和链路断言；`business_scenario_map.yaml`、`业务场景链路清单.md` 和 `测试覆盖点报告.md` 仅作候选参考 | `BLOCKED_NEED_CHAIN_FLOW_EVIDENCE` |
| 异常流程字段完整性 | 异常流程具备异常触发条件、异常类型、请求变体、契约来源状态码/业务码/错误码、错误响应、错误断言 | `FAILED_DESIGN_GATE` |
| 契约完整性 | 结构化契约包含 method、path、参数、响应结构、状态码、错误码，并能映射设计级用例 | `FAILED_CONTRACT_GATE` |
| 数据模型完整性 | `数据模型.md` 或数据库结构 Markdown 能识别表、字段、主键、唯一键、索引、枚举、状态、逻辑删除字段、归属键、轻量表关系知识图谱、铺数顺序、清理逆序和清理边界 | `FAILED_CONTRACT_GATE` |
| 接口传输加解密策略 | 当上游存在 `project_encryption_policy` 时，必须能区分确认加密接口、确认明文接口、候选明文接口和待确认接口；`policy_required` 或未确认候选不得进入脚本准出 | `BLOCKED_NEED_EXECUTION_INPUT` |
| 运行时取证规划状态 | 未使用 requester-backed planning 时记录 `未使用`；使用时读取 `04-runtime-evidence-plan/`，识别 `request_allowed`、DB 前后探测、清理策略、人工确认和阻塞项，不得把 blocker 当作可执行事实 | 非强门禁；若 required fact 只存在 blocker 或 manual confirmation 且未闭合，则为 `BLOCKED_NEED_EXECUTION_INPUT` |
| 运行时取证证据状态 | 未使用 direct requester 时记录 `未使用`；使用时必须读取 `04-runtime-evidence/runtime_evidence.yaml` 和 `runtime_value_catalog.yaml`，只消费 `confirmed` 且 `usable_for_execution_case=true` 的值 | 非强门禁；用户明确要求运行时取证但缺环境、缺鉴权、请求失败或证据冲突时为 `BLOCKED_NEED_EXECUTION_INPUT` 或 `FAILED_EXECUTION_READINESS` |
| Apifox MCP 可选证据状态 | 未使用 Apifox 时记录 `未使用`；使用 Apifox 时记录可读取的项目结构、契约、保存用例和响应示例等级和缺口；仅当用户要求以 Apifox 为准时才要求具备目标项目和接口范围 | 非强门禁；仅 Apifox 必选缺输入时为 `BLOCKED_NEED_EXECUTION_INPUT` |
| 可变运行时业务依赖 | 对全部执行级候选完成审计；仅当正向结果依赖可变字典、配置、资格、额度/次数或外部运行状态时，记录请求字段、成立谓词、来源和可执行预检；无此类依赖可标记 `not_required` | `BLOCKED_NEED_EXECUTION_INPUT` 或转 `generated_non_live/manual_review_only` |
| 鉴权账号与清理输入 | 鉴权账号配置、token 获取规则、清理策略能支持执行级用例可重复运行；涉及数据库铺数/清理时必须有表结构和轻量关系图证据；环境字段必须已填写，且非测试环境必须重新显式授权 DB before/after、清理、回滚或状态恢复 | `BLOCKED_NEED_EXECUTION_INPUT` |
| 特定账号长链路登录首步 | 若长链路或 required flow 需要特定账号、角色、租户、权限或账号业务状态，执行级有序步骤的第 1 个请求必须是登录/授权接口，并且能提取 token 和账号上下文供后续步骤使用；登录接口、账号 secret_ref、提取路径或注入规则缺失时阻塞 | `BLOCKED_NEED_EXECUTION_INPUT` 或 `BLOCKED_NEED_CHAIN_FLOW_EVIDENCE` |

Apifox MCP optional evidence check:

- Prefer calling Apifox MCP tools such as `listAccessibleProjects`, `getProjectSummary`, `getStructureInfo`, `readEntityDetails`, or `listTestCases` when project ID and scope are known.
- If Apifox MCP is not used, mark `MCP 连接状态：未使用` and do not treat it as a blocker.
- If Apifox MCP is unavailable, returns an authorization or connection error, cannot read environments, or lacks saved cases, record the exact missing evidence level. Continue when all required execution facts are confirmed by non-Apifox sources.
- Apifox MCP is not a runtime requester. If Apifox can read contracts but cannot provide saved examples or environment variables, record the missing evidence level; block only an explicit Apifox-required scope.
- Do not replace missing MCP evidence with guessed response codes or sample values, and do not let Apifox evidence silently override structured contracts.

## Input Gate

Required design inputs:

| 输入 | 门禁 |
|---|---|
| `case_list.yaml` 或 `测试用例清单.md` | 优先读取 `case_list.yaml`，必须存在、非空、UTF-8，且包含设计级用例、覆盖对象ID、覆盖规则ID、设计级用例ID 和追溯测试点；`测试用例清单.md` 仅作兼容展示 |
| `执行报告.md` | 必须存在、非空、UTF-8，且阶段状态为 `PASSED` |
| `接口结构化契约清单.md` | 必须包含 method、path、参数、响应、状态码、错误码 |
| `接口测试用例设计文档.md` | 必须包含测试点、覆盖对象、断言依据、流程依据 |
| `数据模型.md` 或数据库结构 Markdown 文档 | 必须存在、非空、UTF-8，并能识别表、字段、主键、唯一键、索引、枚举、状态、逻辑删除字段、归属键、轻量表关系知识图谱、铺数顺序、清理逆序和清理边界 |
| 运行时取证规划 | 可选辅助证据；仅在上游已生成 `04-runtime-evidence-plan/` 时读取，用于标记风险决策、DB 前后探测、清理策略缺口、人工确认项和阻塞项；不得把规划 skeleton 当成可执行请求计划 |
| 运行时取证证据 | 可选辅助证据；仅在上游已生成 `04-runtime-evidence/` 或执行事实引用 `live_request_evidence` 时读取；不得在本阶段直接请求接口 |
| Apifox MCP | 可选辅助证据；仅在用户要求 Apifox 对齐或执行事实引用 `apifox_mcp` 时读取对应契约、保存用例或示例证据；不得用 Apifox MCP 直接请求接口 |

Required execution inputs for `PASSED`:

Execution configuration must provide `环境引用契约` and `鉴权账号配置`. The remaining execution facts may be extracted only from source-bound materials such as Apifox MCP evidence, Markdown data model content, interface contracts, design-level cases, and prior source-present responses.

When execution configuration is absent or incomplete, emit or point to `assets/templates/runtime_execution_config.template.yaml` and stop with `BLOCKED_NEED_EXECUTION_INPUT` before filling execution-level cases. The filled artifact must preserve the template's meaning:

- Environment is always required: `env_name`, `is_test_environment`, module `base_url`, and gateway prefix must be present. Gateway prefix may be an empty string only when the real environment has no prefix.
- Account entries are required for every role used by selected cases or required flows. Each account must include business role, current business state, login method, identifier secret reference, and credential/token secret reference when applicable.
- Auth and crypto entries are required when cases need login, token injection, or encrypted transport. Missing login path, token source, token injection, algorithm reference, key source, request envelope, or response envelope keeps the affected facts blocked.
- If any selected long-chain or required flow needs a specific account, role, tenant, permission, or account business state, the login/auth interface must be supplied as a source-bound executable first step. Static token-only execution is insufficient for that long-chain unless the chain is explicitly not account-specific.
- Case-scope default execution authorization can remove per-interface manual confirmation only when the filled environment is a test environment and the selected case scope is explicit.
- If `is_test_environment=false`, any generic test-environment DB authorization is invalid. DB before/after assertions, setup/cleanup SQL, cleanup API calls, rollback, or status recovery require explicit non-test authorization in the filled config; otherwise keep DB-dependent facts blocked.

| 输入 | 需要内容 |
|---|---|
| 环境引用契约 | 必填；环境名、是否测试环境、模块 base URL、网关前缀、超时、证书、公共 header 的变量名或占位引用；真实环境值允许由下游外部注入 |
| 鉴权账号配置 | 登录/授权接口、账号池、角色、租户、权限、token 提取规则；不得留给下游臆造 |
| 接口传输加解密策略 | 项目默认是否开启 App 传输加解密、加密算法/密钥/请求明文范围/请求序列化方式/请求报文包装/响应报文包装格式来源、确认加密接口、确认明文接口、待确认接口；不得把 `no_encrypt_candidate` 自动当成最终白名单 |
| 测试数据配置 | 正常值、边界值、枚举值、非法值、唯一值生成规则；正向和页面可见字段必须使用来源绑定的合法真实值，普通展示/资料字段才可使用通用真实样例，异常用例才允许非法/占位值 |
| 变量提取/注入规则 | 从响应、数据库或前置步骤提取变量并注入后续请求 |
| 精确断言规则 | HTTP 状态码、业务码、JSONPath、Schema、数据库、事件或回调断言 |
| 清理策略 | API 清理、SQL 清理、状态恢复、软删除、清理顺序和失败处理；数据库清理必须绑定归属键或本次生成的 `id`，并引用数据模型中的关系图和清理逆序 |

If token rules, test data, variable links, precise assertions, or cleanup strategy are not supplied as files, derive them only from explicitly available runtime evidence sidecars, Apifox MCP data, Markdown data model content, interface contracts, design-level cases, prior source-present responses, or user-provided configuration. Keep every derivation source-bound. Missing runtime or Apifox data alone is not a blocker when another source confirms the same fact. If any required fact still cannot be determined from all available sources, mark `BLOCKED_NEED_EXECUTION_INPUT`.

For positive-path executable cases, live cases, required flows, and page-visible business fields, concrete request values must pass a business-readable value quality check. Prefer source enums, dictionary/config APIs, DB bounded samples, confirmed runtime responses, or user-provided values. If none exists, use a generic real-world legal sample only for ordinary user-entered/profile/display fields whose contract permits legal literals, such as valid province/city or standard locale-style values, and record the source category. Do not use generic samples for IDs, status transitions, enum codes, amounts, permissions, relationship keys, or external dependency values. Placeholder values such as `自动化省`、`测试市`、`xxx`、`UNKNOWN`、`示例值` are invalid for positive paths; keep them only for explicit invalid-value/error-branch cases with corresponding error assertions.

Before marking a positive/live case executable, audit whether its success depends on mutable runtime business state rather than request-shape validity alone. This audit applies only to mutable dictionary participation、configuration enablement、role/creator/user eligibility、quota or limit availability、or an external runtime state named by source/runtime evidence. Immutable protocol enums、ordinary legal literals、pagination、sorting and static response schema do not trigger it.

- Record the audit under `execution_fact_sources.yaml.runtime_business_dependency_audit` for every run. `scanned_case_ids` must exactly cover all execution-level cases; `not_required` is valid only with no dependency items and no unresolved candidates.
- For each applicable case, record stable `dependency_id`、`case_id`、generic `dependency_type`、request field paths、the exact predicates required at execution time、source refs、automation decision and precheck.
- A runnable dependency must use `api_query`、`sql_query`、`fixture_assertion` or `isolated_state` and cite an executable precheck rule. Prefer a read-only API query; SQL query requires the existing DB/authorization boundaries. If the precheck changes baseline state, it must declare an executable restore reference.
- When the dependency cannot be safely observed or constructed, keep the business case traceable as `generated_non_live` or `manual_review_only` with `precheck.mode=non_live` and a source-bound reason. Do not replace a legal request value merely to bypass the dependency.
- Do not specialize this gate to endpoint names, field names or one project's status codes. The trigger is source-backed mutability and outcome dependence; unknown extension fields are allowed.

Authentication uses token first. Execution-level cases must record token source, token extraction path when dynamic login is used, default token injection placement, and any per-method injection overrides required by the interface contract. Header injection defaults to `Authorization: Bearer <token>`; query/body/cookie injection is allowed when source evidence or execution configuration requires it. If token source, extraction path, or placement cannot be determined, mark `BLOCKED_NEED_EXECUTION_INPUT`.

Account-specific long-chain login entry is mandatory. When a long-chain case or required flow declares `specific_account_required=true`, `required_account_role`, `required_account_business_state`, tenant, permission, or equivalent account-state requirement, generate the login/auth request as step 1 of that chain. The step must have `step_type: login` or an equivalent explicit login marker, reference the login/auth contract, extract token and required account context into runtime variables, and let later business steps consume those variables through normal variable injection. If the login contract, account secret reference, credential input, token/account-context extraction path, or token injection placement is missing, add the item to `长链路缺失码值补充清单.md` and block; do not silently fall back to a user-supplied static token or hidden fixture for that account-specific chain.

Interface transport encryption is a script-generation prerequisite when encrypted interfaces are confirmed. Execution-level cases and flow evidence must keep request bodies, assertions, extraction rules, injection rules, and `runtime_context` variables in plaintext business form. Do not store encrypted payloads as case input or pass ciphertext between steps. The execution rules must record one of three outcomes:

- No confirmed encrypted interfaces: mark transport encryption as `not_applicable` or `plain_http`, and allow normal script generation.
- Confirmed encrypted interfaces with complete runtime contract: record algorithm reference, key source reference, request payload scope, request plaintext serialization, request envelope, response envelope, confirmed encrypted interface list, confirmed no-encrypt interface list, and evidence; allow framework generation to add client-side request encryption and response decryption.
- Confirmed encrypted interfaces with missing algorithm, key source, request payload scope, request plaintext serialization, request envelope, or response envelope: mark `BLOCKED_NEED_EXECUTION_INPUT`; do not let the framework generator guess or emit placeholder crypto code.

When the confirmed runtime contract says the whole request parameter dictionary is encrypted, record it explicitly as a transport-layer rule:

- Request plaintext source: merge common parameters and business parameters into one plaintext dictionary before encryption.
- Request serialization: serialize that whole dictionary into a UTF-8 JSON string before AES encryption.
- Request envelope: send JSON body `{"data": "<ciphertext>"}`; do not use `param` and do not send ciphertext as the raw body.
- Response envelope: outer response JSON is plaintext; when `data` is a string, decrypt only `data`, parse the decrypted JSON string into an object, and keep outer fields such as `code` and `message` unchanged.
- Variable extraction and assertions must consume the decrypted plaintext response object. If AES details or key source are missing even though this envelope is known, keep the stage blocked.

Variable extraction and injection names must be script-executable: use Python-valid identifiers only and do not use Python keywords. Do not emit variable names with spaces, hyphens, dots, or other characters that can break generated pytest code or runtime placeholder injection.

Dependencies passed to downstream cases must use JSON extraction or regex extraction only. Each dependency rule must include producer case/step, consumer case/field, variable name, extraction type (`json` or `regex`), `json_path` or `pattern/group`, source (`body`, `header.<name>`, or `json.<path>`), and source evidence. Assertions must be script-executable Python `assert` checks. Every runnable case must assert HTTP status code and response fields. If the case verifies database persistence, the stage must provide fixture-executable SELECT query rules, bind params, expected row count, and expected fields for `database_assertor`; generated scripts must execute persistence checks through pytest fixtures.

Database runtime configuration for generated scripts must be handed off as config-only data for `api-test-framework/configs/database.yaml`. Do not write database connection strings, database instances, or driver setup into executable cases, dependency payloads, SQL command files, or pytest test bodies. The script framework must expose the database instance through a pytest fixture.

Database MCP may be used by this execution-level stage to obtain database structure, table relationships, field constraints, ownership boundaries, cleanup keys, and knowledge-graph evidence for data construction. Such MCP-derived facts must be normalized into `数据模型.md`, `前置数据构造规则.md`, `execution_fact_sources.yaml`, or an evidence index before handoff. Do not pass MCP connection instructions, MCP query scripts, or MCP result files as runtime dependencies of generated pytest scripts.

For requester-backed long-chain execution, DB assertion and cleanup scope must be derived from source-visible table facts and confirmed by runtime evidence:

- Determine candidate DB tables only from the current interface or required flow source chain: Controller -> Service -> Repository/Mapper, Mapper XML, annotated SQL, repository query/update methods, and MyBatis/JPA entity mappings.
- Use database MCP to confirm those tables and columns in the test environment before using them in before/after probes, assertions, setup, or cleanup.
- Capture DB before snapshots for the scoped tables, execute the request or ordered chain step, then capture DB after snapshots for the same scoped tables. Use the before/after delta, not source inference alone, as the runtime proof for affected tables and changed fields.
- Persist every confirmed DB runtime fact as source-bound evidence: request/response ref, table refs, before/after refs, delta assertion, ownership key, cleanup rule, cleanup order, and source refs. Missing delta or cleanup evidence keeps the fact blocked.

DB before/after predicates and cleanup boundaries must stay minimal:

- Query and cleanup only tables explicitly involved by the current source chain. Do not scan or clean unrelated tables to look for changes.
- Choose the ownership key in this order: response business ID, request business ID, authenticated `userId`/`appUserId`, then a source-evidenced unique business key such as order number, conversation ID, idempotency key, or equivalent unique marker.
- If no ownership key or unique marker exists, block with `BLOCKED_NEED_EXECUTION_INPUT`; do not widen predicates to make cleanup possible.
- Cleanup only records created or changed by the current run. Prefer response-extracted IDs such as `id`、`orderId`、`messageId`、`auditId` or equivalent source-evidenced business IDs. If the response lacks an ID, require test account plus a current-run unique marker.
- Cleanup order must follow the relationship graph in reverse: child/detail/ledger/relation records before parent/order/master records. Baseline user, account, configuration, dictionary, and shared reference data must not be deleted unless the current run created a uniquely owned isolated record.
- High-risk payment, withdrawal, subscription, review, scheduler, callback, and settlement data may be queried and cleaned only within current-run IDs or exact unique ownership keys. Broad cleanup such as deleting historical rows by `userId` alone is forbidden.

Precondition data construction must follow the user-confirmed priority: use API construction first. Use SQL construction only when API construction cannot satisfy the required state, such as missing construction API, inability to prepare historical/cross-table/abnormal states, or API setup breaking case independence. Table structure alone is not enough for database setup/cleanup: every database-backed setup or cleanup rule must cite the table graph edge, parent-child order, ownership key, cleanup identity, and cleanup reverse order used by the rule. Every SQL rule must record `api_unavailable_reason`, `source_ref`, impacted case IDs, target tables, ownership keys, cleanup order, rollback/cleanup strategy, SQL exit-gate evidence, and a seed-scope guard. All database test data generated during script execution must record `id`, and cleanup rules must delete only the current script-generated data by `id`. INSERT and DELETE rules must include command-level `sql_exit_gate` checks: INSERT must write `id` through `:id` and affect exactly one row; DELETE must use `WHERE id = :id`, operate on one approved table, and affect exactly one row. If the reason for not using API is absent or weak, if graph/ownership/cleanup evidence is missing, if `id` cannot be confirmed as the cleanup identity, if the seed-scope guard cannot prove that only required business precondition fields are seeded, or if INSERT/DELETE cannot pass the SQL exit gate, block with `BLOCKED_NEED_EXECUTION_INPUT` instead of generating SQL.

Precondition seeded values must close before execution-level cases pass:

- Classify every setup-produced code/value as `precondition_api_value`、`db_seeded_value`、`dictionary_or_config_value`、`prior_runtime_response_value`, or `external_dependency_value`.
- Prefer values returned by precondition APIs or earlier chain steps. Use dictionary/config/enum values from the normalized data model or DB MCP only for locally owned business fields. Use SQL seeded values only after recording why API construction cannot satisfy the target state.
- Seed only the minimal fields needed to reach the required business precondition. Allowed seed fields are local business object IDs/states, local relationship or permission state, local account/wallet/subscription/review/session/order/config records, and local enum or dictionary values that cannot be obtained through a real precondition API. Do not seed ordinary request payload fields, pagination/sort fields, device/client metadata, runtime markers, random text, tokens, verification codes, external dependency return values, or values that a producer step in the long chain should return.
- For every setup rule, record `seed_scope_reason`、`allowed_seed_fields`、`forbidden_seed_fields`、`runtime_value_fields`、`affected_case_ids`, and `distortion_risk`. `distortion_risk` must be `low` before the rule can feed a `PASSED` execution-level case. Medium/high risk means the value must move to runtime evidence, user-filled missing-value checklist, external sandbox evidence, or a blocking item.
- For each execution-level request, expected response, assertion, DB assertion, variable link, or cleanup rule that needs a setup-produced value, fill the corresponding field with a concrete confirmed value or an executable variable reference bound to a setup output. Do not leave placeholder words such as `待填`、`示例值`、`UNKNOWN`, or human-only instructions.
- `前置数据构造规则.md` must contain a seed-value closure list with case ID, field path, value type, value or variable name, source category, source ref, setup rule ref, assertion ref, cleanup rule ref, and script usability.
- `execution_fact_sources.yaml` must cite each seeded value and seed-scope guard as `fact_type: seed_value | enum_code | seed_scope_guard | db_assertion | cleanup_strategy | external_dependency_value` with `source_type: precondition_api_response | db_seed_evidence | data_model | live_request_evidence | external_sandbox_evidence | user_config`.
- `execution_fact_sources.yaml` must cite account-specific long-chain login evidence as `fact_type: account_specific_chain | login_entry_rule` with a confirmed source. `account_specific_chain` identifies the affected flow/case and required account semantics; `login_entry_rule` identifies the login/auth interface, account secret reference, token/account-context extraction paths, and token injection rule.
- The script generator may execute only the setup and cleanup rules recorded here. It must not invent seed SQL, fabricate enum values, or move values from comments into runnable request fields.
- Values that come from external services must remain isolated as `external_dependency_value`. Payment, withdrawal, SMS, Apple/Google, audit, OSS, callback, webhook, risk-control, and similar third-party codes or IDs require sandbox/mock/callback evidence or a real precondition API response. Do not satisfy them by directly seeding local DB tables unless the tested behavior is the local callback consumer and the signed sandbox/mock callback payload is itself part of the precondition evidence.
- If a code/value could be either local seed data or an external dependency response and the source evidence cannot distinguish it, block with `BLOCKED_NEED_EXECUTION_INPUT`.

Long-chain missing value review is mandatory before script generation:

- After generating execution-level cases, scan only long-chain cases and required-flow steps for unresolved executable values in request path/query/header/cookie/body/form/file fields, expected response fields, assertion fields, variable extraction/injection, precondition setup, DB assertions, cleanup identities, external dependency values, auth/account-bound fields, and transport-crypto fields.
- Do not include fields that can be closed from source contracts, data model, DB MCP dictionary/config evidence, precondition API outputs, DB seed rules, runtime evidence, or already filled execution config. First attempt those allowed sources, then list only remaining user-required fields.
- If any required long-chain field remains missing, write `长链路缺失码值补充清单.md` for the user and `long_chain_missing_value_fields.yaml` for the gate. The Markdown must state business scenario, `flow_id`, executable case ID, step order, interface, field location, field path, missing value type, field meaning, required account role, required account business state, allowed fill forms, and fill target.
- Field meaning must be written for business users, not as only a raw DTO or database column name. Prefer `这个字段用于指定被审核资料ID` over `profileId`.
- If a field needs a specific account, role, tenant, permission, or business state, the missing-value row must make that requirement explicit so the user can fill the correct account reference.
- If the missing value prevents an account-specific long-chain from starting with login, classify it under `field_location=auth` and `missing_value_type=account_or_role_value`; the field meaning must state whether the missing item is the login interface, account secret reference, credential input, token extraction path, account-context extraction path, or token injection rule.
- The user may fill concrete values, executable variable references, `secret_ref`、`file_ref`、`sandbox_ref`、`mock_ref`、`callback_payload_ref`, or `precondition_api_ref`, according to the allowed fill forms on the row.
- After the user fills the document, update the corresponding execution-level case fields and sidecars before running `$api-test-framework-generator`. Do not let script generation read values only from the human-filled document.
- `stage_status.yaml` and `execution_fact_sources.yaml` may be `passed` only when `long_chain_missing_value_fields.yaml.status` is `not_required` or `filled`, `open_required_count=0`, and every filled value has been propagated to the execution-level artifacts.

Allowed external inputs after this stage:

| 外部输入 | 边界 |
|---|---|
| 环境配置 | 只允许补充真实 base URL、环境变量值、证书路径、超时等运行环境值 |
| pytest 工程规范 | 只允许补充目录结构、公共 client 封装、fixture 命名、配置读取方式 |
| allure 标注规范 | 只允许补充团队自定义 feature/story/severity/link/label 映射口径 |

Do not mark `PASSED` if the output still needs downstream generation to invent request values, response values, assertions, authentication accounts, token extraction, setup data, variable links, or cleanup rules.

## Coverage Inheritance Contract

Before generating execution-level cases, build a machine-readable coverage inheritance index:

| 字段 | 来源 | 要求 |
|---|---|---|
| `覆盖对象ID` | 设计级用例、覆盖矩阵 | 必须绑定到上游覆盖对象，不能使用自然语言代替 |
| `覆盖规则ID` | 设计级覆盖规则或最低覆盖规则 | 必须绑定到对应覆盖规则；缺失时阻塞 |
| `设计级用例ID` | `测试用例清单.md` 或 `接口测试用例设计文档.md` | 每条执行级用例必须可回溯到至少一条设计级用例 |
| `追溯测试点` | 设计级测试点 ID | 必须保留原测试点 ID；临时 ID 只能在上游已标记为临时追溯 ID 时继承 |
| `覆盖继承状态` | 本阶段对账结果 | `已继承` / `缺失` / `冲突` / `阻塞` |

Coverage inheritance gates:

- Every design-level case that contributes to 100% coverage must map to at least one execution-level case.
- Every executable case must preserve `覆盖对象ID`、`覆盖规则ID`、`设计级用例ID`、`追溯测试点`.
- Do not merge execution-level cases in a way that loses one of the inherited coverage rule IDs.
- If a design-level case cannot be made executable because data, auth, assertion, environment, used-Apifox fact, or cleanup evidence is missing, mark the stage as `BLOCKED_NEED_EXECUTION_INPUT` or `FAILED_EXECUTION_READINESS`; do not silently drop the case. Do not block only because optional Apifox evidence was unavailable.
- `前置数据构造规则.md` must include a coverage inheritance summary with total design cases, inherited executable cases, missing mappings, conflicting mappings, and whether execution-level coverage can still respond to 100%.

## Runtime Evidence Rules

`04-runtime-evidence-plan/` is an optional upstream planning stage. Use it to preserve why an interface was allowed, blocked, or routed to manual confirmation before runtime evidence collection.

- `runtime_risk_audit.yaml` may prove that a case was request-allowed, mutation-gated, destructive, external/callback-dependent, or unknown. It cannot by itself provide runtime values.
- `db_before_after_probe_plan.yaml` may prove which mutating facts require DB before/after snapshots, ownership keys, delta assertions, and cleanup strategy. If a required mutating fact lacks closed DB evidence, keep that fact blocked.
- `runtime_blocker_candidates.yaml` must be copied into execution blockers or manual confirmation items when its case/fact is required for `PASSED`.
- `runtime_request_plan.skeleton.yaml` is a planning artifact only; this stage must not execute it or convert placeholders into guessed values.
- If `runtime_risk_audit.yaml` records a `user_config` declaration that selected/generated test cases are executable by default in a test environment, treat in-scope runtime evidence as execution-authorized and do not require separate per-interface manual-confirmation blockers for those cases.
- Case-scope default authorization applies only to interfaces and ordered steps inside the inherited case list or required flow denominator. It does not authorize endpoints discovered only by broad route scanning, production-like environments, or facts outside the selected execution scope.
- This authorization satisfies only the confirmation gate. Request/response evidence, variable links, auth, transport/encryption, external sandbox or mock inputs, source-bound DB before/after, ownership keys, delta assertions, cleanup evidence, and redaction must still be closed before any fact is marked `PASSED`.
- If the filled runtime execution config says the environment is not test, DB before/after and cleanup evidence can be consumed only when the same config provides explicit non-test DB authorization. Missing reauthorization keeps DB-dependent runtime facts blocked even if the case itself is execution-authorized.

`04-runtime-evidence/` is an optional upstream evidence stage between design-case handoff and this executable-case stage. Use it only when it exists or when `execution_fact_sources.yaml` needs `source_type: live_request_evidence`.

- This stage must not directly request live interfaces, call a requester, read raw passwords, or read runtime-only secret files.
- Optional inputs are `04-runtime-evidence/runtime_evidence.yaml` and `04-runtime-evidence/runtime_value_catalog.yaml`; both must be UTF-8, `schema_version=1`, and `status=passed` or `partial` before their values can be consumed.
- Only runtime evidence with `source_status=confirmed` and `usable_for_execution_case=true` may enter execution-level cases.
- For mutating/runtime-verified facts, confirmed evidence must include request/response evidence plus DB before/after references, delta assertion, cleanup evidence, and source refs when the planning stage marked `db_probe_required=true`.
- `runtime_value_catalog.yaml` values may feed token rules, test data rules, variable links, assertion rules, and cleanup hints only when their `source_ref` points back to confirmed runtime evidence.
- Runtime evidence cannot override `接口结构化契约清单.md`, design-level cases, `数据模型.md`, database MCP evidence, or source-extracted facts. Any conflict blocks with `FAILED_EXECUTION_READINESS`; missing runtime evidence required by the user blocks with `BLOCKED_NEED_EXECUTION_INPUT`.
- `execution_fact_sources.yaml` must cite runtime evidence as `source_type: live_request_evidence` and use `source_ref: "runtime_evidence.yaml#RT-..."` or `source_ref: "runtime_value_catalog.yaml#VAL-..."`.
- Request failures, 500 responses, auth failures, service unavailability, and missing fields are recorded as evidence gaps. If runtime evidence was optional, continue with other confirmed sources; if the user required it, do not generate execution cases with guessed values.
- Runtime outputs must redact password、token、Authorization、Cookie and equivalent secrets.

## Apifox MCP Evidence Rules

Use Apifox MCP to support, not replace, the contract. Apifox MCP is optional unless the user explicitly requires Apifox alignment. Every used Apifox fact must be recorded in `apifox_evidence_index.yaml` with one evidence level. Runtime request evidence must come from `04-runtime-evidence/`, not from Apifox MCP:

| 证据等级 | 用途 | 不能做什么 |
|---|---|---|
| `project_structure` | 定位项目、模块、目录、接口 ID、接口范围 | 不能补请求字段、响应字段、状态码、断言值 |
| `interface_contract` | 读取 method、path、参数、响应 schema、状态码、错误码 | 与结构化契约冲突时不能覆盖契约，必须阻塞 |
| `saved_case_example` | 读取保存用例、debug case、请求示例、响应示例、样例值 | 只能补样例和执行参数，不能覆盖契约定义 |
| `response_example` | 读取响应示例、响应组件或样例值 | 只能补样例候选，不能代表真实运行时响应，不能覆盖契约定义 |

Conflict priority:

1. `接口结构化契约清单.md`、设计级用例和覆盖矩阵是发布基线；任何 Apifox 证据冲突都先阻塞，不自动覆盖。
2. Runtime direct request values can only be consumed through `04-runtime-evidence/runtime_evidence.yaml` and `runtime_value_catalog.yaml`; conflicts with contract, design evidence, data model, or assertion evidence block execution-level release.
3. `saved_case_example` and `response_example` only fill sample values, variable candidates, and execution parameter candidates when aligned with contract; conflicts with `interface_contract` block or require upstream repair.
4. `project_structure` 只作为查找范围和 ID 证据，不参与字段值、响应值、状态码或断言推导。
5. Apifox MCP 不可用、环境未读出、无保存用例或鉴权变量缺失时，只记录证据缺口；除用户指定 Apifox 为准外，不阻塞执行级准出。

## Output Rules

### `执行级接口用例集.md`

If all execution gates pass and sharding is not enabled, include executable cases only. Each case must include:

| 字段 | 要求 |
|---|---|
| 用例ID | 稳定 ID，可追溯设计级用例 |
| 设计级用例ID | 上游设计级用例 ID，不得为空 |
| 用例名称 | 中文 |
| 用例类型 | 与设计级测试方法一致 |
| 用例优先级 | `P0`、`P1`、`P2` |
| 覆盖对象ID | 上游覆盖对象 ID，可包含多个 |
| 覆盖规则ID | 上游覆盖规则 ID，可包含多个 |
| 请求方式 | 大写 HTTP method，来自契约 |
| 追溯接口 | 接口 ID 或 path，来自契约 |
| 追溯测试点 | 设计级测试点 ID |
| 覆盖继承状态 | `已继承`，否则不得进入 `PASSED` |
| allure 标记 | feature、story、severity、link 或 label |
| 前置条件 | 账号、环境、数据状态、依赖对象 |
| 执行步骤 | 必须保留单接口步骤或多接口链路；来自 `required_chain_flows.yaml` 的已确认必选链路必须输出多接口有序步骤；需要特定账号的长链路第 1 步必须是登录/授权接口 |
| 完整入参 | 真实 path/query/header/cookie/body/form/file 参数 |
| 出参契约 | 响应 JSON Schema 或结构约束 |
| 预期响应 | HTTP 状态码、业务码、关键字段、错误码 |
| 断言规则 | status、jsonpath、schema、db、event、callback、relation |
| 变量提取 | 从响应或数据库提取的变量 |
| 变量注入 | 注入后续步骤的位置 |
| 链路flow_id | 多接口链路用例必填；已确认必选链路必须继承 `required_chain_flows.yaml.flow_id`，候选链路可追溯引用 `business_scenario_map.yaml.flow_id` |
| 链路步骤序号 | 多接口链路用例必填，从 1 开始连续 |
| 链路生产者/消费者 | 多接口链路用例必填，记录上游 case、下游 case、变量名、提取路径和注入目标；账号型长链路必须记录登录步骤生产的 token 与账号上下文变量 |
| 账号登录首步 | 账号型长链路必填；说明是否需要特定账号、所需账号角色/业务状态、登录/授权接口、步骤序号 1、token/账号上下文提取路径和后续注入目标 |
| 前置造数码值 | 由前置 API、DB 造数、字典/配置、前序响应或外部沙箱证据确认的码值；必须填入对应请求字段、断言字段或变量引用，并引用造数规则 |
| 运行时业务依赖 | 仅在存在可变业务依赖时填写依赖 ID、类型、请求字段、成立谓词、可执行预检/恢复和来源；无依赖时由 sidecar 审计统一记录 `not_required` |
| 清理引用 | 对应清理规则 ID |
| 可转 pytest 标记 | fixture、参数化、client、allure 映射 |
| 来源依据 | 文档章节、结构化契约、按需 Apifox 接口/用例/响应、数据模型 Markdown 章节 |
| 置信度 | 继承并重算 suite `../../references/case-confidence-contract.md` 定义的分数、等级、区间、场景相关性、五维得分、原因码、硬上限原因和证据引用 |

置信度只汇总证据质量。低置信度用例保留在执行级产物并阻塞 live 分母；中高置信度仍必须通过现有入参、断言、前置、清理、外部依赖和可重复执行门禁。

If all execution gates pass and sharding is enabled, keep this file as the ordered entry point only. It must include `阶段状态：PASSED`, `分片模式：启用`, `分片索引：执行级用例分片索引.md`, exact shard count, read order, and `规则文件：前置数据构造规则.md`. Put executable cases only in the shard files.

If gates fail, keep this file case-free and only list stage status, generation status, and the reason pointing to `前置数据构造规则.md`. Record blockers, missing data, impact, and repair suggestions in `前置数据构造规则.md`.

### Sharded Output Order

Use sharded output only for large case sets or explicit user requests. The shard index must be machine-readable and stable:

| 字段 | 要求 |
|---|---|
| 顺序 | Three-digit sequence starting at `001`, continuous with no gaps |
| 分片ID | Stable shard ID |
| 文件 | Relative path under `执行级用例分片/`, using `001_<稳定名称>.md`; filename prefix must match `顺序` |
| 接口范围 | Module/interface group covered by the shard |
| 用例ID范围 | Case IDs contained in the shard |
| 读取顺序说明 | Downstream reading hint |
| 规则引用 | Referenced precondition, variable, and cleanup IDs |

Each shard file must start with `## 执行级接口用例分片`, declare `分片ID` and `顺序`, and then include executable cases using the same YAML schema as non-sharded `执行级接口用例集.md`.

### `stage_status.yaml`

Always include the executable-stage status sidecar:

```yaml
schema_version: 1
stage: executable_interface_case_set
status: passed | blocked | failed
next_stage_allowed: true | false
input_paths:
  - path: "..."
    role: "..."
output_paths:
  - path: "..."
    role: "..."
gate_checks:
  - check_id: "..."
    status: passed | blocked | failed
    evidence_refs: ["..."]
blocking_issues: []
```

`PASSED` requires `status: passed`, `next_stage_allowed: true`, and `blocking_issues: []`.

### `coverage_matrix.yaml`

Always include executable coverage inheritance counts and mappings:

```yaml
schema_version: 1
stage: executable_interface_case_set
coverage_summary:
  denominator_scope: "design cases and coverage rules"
  coverage_rate: 100
coverage_items: []
missing_items: []
upstream_downstream_mappings: []
design_case_total: 0
design_case_mapped: 0
executable_case_total: 0
executable_case_traced: 0
coverage_rule_total: 0
coverage_rule_mapped: 0
missing_design_case_ids: []
missing_executable_trace_ids: []
missing_coverage_rule_ids: []
```

`PASSED` requires all count pairs to match and all missing lists to be empty.

### `execution_fact_sources.yaml`

Always include the source index for execution facts:

```yaml
schema_version: 1
stage: executable_interface_case_set
status: passed | blocked | failed
required_human_inputs:
  runtime_execution_config:
    status: provided | missing
    source_ref: "runtime_execution_config.yaml#..."
  environment_reference:
    status: provided | missing
    source_ref: "执行配置.md#..."
    env_name: ""
    is_test_environment: true
  authentication_account:
    status: provided | missing
    source_ref: "执行配置.md#..."
  db_authorization:
    status: provided | missing | not_required
    non_test_reauthorization_status: not_required | provided | missing
    source_ref: "runtime_execution_config.yaml#db_authorization"
runtime_business_dependency_audit:
  status: passed | not_required | blocked
  scanned_case_ids: []
  dependency_items:
    - dependency_id: "RBD-001"
      case_id: "EXE-TC-001"
      dependency_type: mutable_dictionary_state | mutable_configuration_state | mutable_eligibility_state | quota_or_limit_state | external_runtime_state
      request_paths: ["$.body.exampleId"]
      required_predicates: {status: 1}
      source_refs: ["..."]
      automation_decision: runnable | generated_non_live | manual_review_only
      precheck:
        mode: api_query | sql_query | fixture_assertion | isolated_state | non_live
        executable_ref: "前置数据构造规则.md#PRE-RBD-001"
        changes_state: false
  unresolved_candidate_case_ids: []
fact_sources:
  - fact_id: "..."
    fact_type: token_rule | test_data_rule | seed_value | enum_code | seed_scope_guard | relationship_graph | ownership_key | variable_link | chain_flow | account_specific_chain | login_entry_rule | assertion_rule | db_assertion | cleanup_strategy | transport_crypto_contract | external_dependency_value | runtime_business_dependency
    source_type: user_config | data_model | interface_contract | design_case | apifox_mcp | live_request_evidence | prior_response | precondition_api_response | db_seed_evidence | external_sandbox_evidence
    source_ref: "..."
    source_status: confirmed | missing | conflict | blocked
missing_required_facts: []
conflict_facts: []
blocking_issues: []
```

`PASSED` requires `runtime_execution_config.status=provided`, `environment_reference.status=provided`, `authentication_account.status=provided`, and source-bound `source_ref` for token, data, seeded values, variable, chain flow, assertion, cleanup, and confirmed transport crypto facts. Every setup-produced value consumed by request fields, expected responses, assertions, DB assertions, variable links, or cleanup rules must be filled in the execution case as a concrete value or executable variable reference and have a confirmed source entry. When setup or cleanup uses `data_model`/database/SQL evidence, `relationship_graph` and `ownership_key` facts are also required. If any fact declares an account-specific chain, a confirmed `login_entry_rule` fact is required and must reference the login/auth contract plus token/account-context extraction and injection evidence. If `environment_reference.is_test_environment=false` and any DB before/after, cleanup, rollback, or status-recovery fact is required, `db_authorization.non_test_reauthorization_status` must be `provided`; otherwise block with `BLOCKED_NEED_EXECUTION_INPUT`. When encrypted interfaces are confirmed, at least one `transport_crypto_contract` fact must be `confirmed` and cite algorithm, key source, request payload scope, request envelope, and response envelope evidence. In addition, `runtime_business_dependency_audit.status` must be `passed|not_required`, `scanned_case_ids` must exactly cover all execution-level cases, and `unresolved_candidate_case_ids` must be empty.

### `long_chain_missing_value_fields.yaml`

When long-chain value completion is checked, include this sidecar. It can be omitted only when no long-chain cases or required flows exist.

```yaml
schema_version: 1
stage: executable_interface_case_set
status: not_required | pending_user_input | filled | blocked
long_chain_scope:
  required_flow_count: 0
  executable_long_chain_case_count: 0
open_required_count: 0
filled_count: 0
items:
  - missing_id: "LCMV-001"
    flow_id: "FLOW-001"
    business_scenario: "用户完成订阅后查询权益"
    executable_case_id: "EXE-LC-001"
    design_case_id: "DC-LC-001"
    step_order: 1
    interface: "POST /api/v1/..."
    field_location: path | query | header | cookie | body | form | file | expected_response | assertion | variable | setup | db_assertion | cleanup | auth | crypto
    field_path: "$.body.orderId"
    missing_value_type: precondition_api_value | db_seeded_value | dictionary_or_config_value | prior_runtime_response_value | external_dependency_value | account_or_role_value | file_or_certificate_value
    field_meaning: "该字段用于指定本次链路要操作的订单ID"
    required_account_role: "male | female | operator | admin | none"
    required_account_business_state: "已登录且钱包正常"
    allowed_fill_forms: ["concrete_value", "variable_ref", "secret_ref", "file_ref", "sandbox_ref", "mock_ref", "callback_payload_ref", "precondition_api_ref"]
    user_fill_status: missing | filled | blocked
    user_value_ref: ""
    fill_target_refs:
      - "执行级接口用例集.md#EXE-LC-001"
      - "前置数据构造规则.md#RULE-001"
    source_refs: []
    blocking_reason: ""
blocking_issues: []
```

If `status=pending_user_input`, script generation is forbidden. After the user fills the Markdown checklist, update this sidecar to `filled`, set `open_required_count: 0`, and propagate every value to execution-level cases and fact sources.

### `apifox_evidence_index.yaml`

When `fact_sources.source_type=apifox_mcp` appears, or when Apifox is explicitly required by the user, include this file with evidence levels and conflict priority:

```yaml
schema_version: 1
stage: executable_interface_case_set
status: passed | partial | blocked | failed
evidence_items: []
conflict_items: []
conflict_priority: []
resolution_policy:
  project_structure: "定位接口，不作为字段、断言、环境或鉴权依据；不可用时不阻塞"
  interface_contract: "读取契约用于辅助校验，冲突时阻塞"
  saved_case_example: "读取样例，必须与契约一致；仅作执行参数候选"
  response_example: "读取保存响应示例，必须与契约一致；仅作样例候选"
```

### `前置数据构造规则.md`

Always include:

- 阶段状态
- 输入前置校验
- 输入完整性检查
- 数据模型索引：表结构、主键/唯一键/索引、枚举/状态、逻辑删除字段、轻量表关系知识图谱、铺数顺序、清理逆序、归属键和清理边界
- 环境与鉴权配置需求
- token 鉴权策略：token 来源、提取路径、默认注入位置、按请求方法覆盖规则
- 接口传输加解密策略：确认加密接口、确认明文接口、请求明文范围、请求序列化方式、请求 `data` 包装、响应 `data` 解密和 key 来源
- 前置数据构造优先级：API 优先，SQL 仅在 API 无法满足且表结构、关系图、归属键、清理顺序证据充分时启用
- 前置造数码值闭环清单：每个由前置 API、DB 造数、字典/配置、前序响应或外部沙箱证据确认的码值，都必须记录来源分类、字段路径、实际值或变量名、造数规则、断言规则、清理规则和脚本可用性
- 可变运行时业务依赖审计：列出全部扫描用例、适用依赖、请求字段、成立谓词、可执行预检、必要恢复、自动化决策和来源；无适用依赖时明确 `not_required`
- 造数范围防失真门禁：每条前置造数规则必须列出 `seed_scope_reason`、`allowed_seed_fields`、`forbidden_seed_fields`、`runtime_value_fields`、`affected_case_ids` 和 `distortion_risk`；只有 `distortion_risk=low` 且禁止造数字段未被造数替代时，才能进入脚本生成
- 长链路缺失码值补充清单状态：如存在长链路缺失码值，必须引用 `长链路缺失码值补充清单.md` 和 `long_chain_missing_value_fields.yaml`，并说明是否已由用户补充且已回填执行级用例
- 数据库测试数据清理规则：记录脚本生成数据的 `id`，按 `id` 精准删除本次执行生成的数据
- 前置数据构造规则
- 变量提取与注入规则
- 链路脚本生成证据：每个必需链路的 `flow_id`、业务场景ID、执行级用例ID、连续步骤序号、生产者/消费者变量链路、链路断言和清理边界
- 变量 Python 可执行性校验：变量名、`${变量}` 占位符和 SQL 绑定参数名必须是 Python 合法标识符且不能是关键字
- 下游依赖契约：JSON 路径依赖、正则表达式依赖、生产者/消费者映射
- 断言规则：使用 `assert` 校验状态码、返回字段；落库断言必须通过数据库 fixture 查询并断言
- 数据库脚本配置：数据库连接配置进入 `configs/database.yaml`，数据库实例由 pytest fixture 提供
- 清理策略
- 可重复执行校验
- 覆盖继承对账
- 脚本生成准出门禁
- 缺失数据与待确认项
- pytest+allure 转换准出结论

Only mark `PASSED` when all generated cases have executable input values, source-bound expected outputs, assertions, authentication and token handling, setup data, variable links, cleanup rules, and script-generation readiness. For long-chain cases, `long_chain_missing_value_fields.yaml` must be absent because no long-chain scope exists, or have `status=not_required|filled` and `open_required_count=0`. Optional Apifox evidence may be absent when no execution fact depends on it and no user-required Apifox scope exists. The only missing downstream inputs may be 环境配置、pytest 工程规范、allure 标注规范.

## Stage Status

| 状态 | 含义 | 是否允许进入 pytest+allure 代码生成 |
|---|---|---|
| `PASSED` | 除环境配置、pytest 工程规范、allure 标注规范外，执行级用例、鉴权、前置数据、断言、变量链路、清理、脚本生成字段全部就绪 | 是 |
| `FAILED_DESIGN_GATE` | 设计级 `执行报告.md` 未 `PASSED` 或输入不完整 | 否 |
| `FAILED_CONTRACT_GATE` | 契约与设计级用例、已使用 Apifox 证据或数据模型存在阻塞冲突 | 否 |
| `BLOCKED_NEED_EXECUTION_INPUT` | 缺少环境、鉴权、真实数据、断言值或清理策略 | 否 |
| `BLOCKED_NEED_CHAIN_FLOW_EVIDENCE` | 链路脚本所需的有序步骤、变量提取/注入、链路断言或清理边界缺失 | 否 |
| `FAILED_EXECUTION_READINESS` | 用例已生成但不可重复执行或不可转 pytest+allure | 否 |

## Validation

After writing the Markdown deliverables and YAML sidecars, run:

```bash
python3 scripts/validate_outputs.py <输出目录>
```

`validate_outputs.py` already invokes the runtime-business-dependency validator. Run `python3 scripts/validate_runtime_business_dependencies.py <输出目录>` only for focused diagnosis; do not count it as a second release gate.

If validation fails, fix the deliverables. Remove temporary test files after validation.
