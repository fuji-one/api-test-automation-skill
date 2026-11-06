# 执行事实闭合与脚本准备策略

## 目录

- [读取时机](#读取时机)
- [与组件职责的关系](#与组件职责的关系)
- [规则正文](#规则正文)
- [Runtime Request Value Principle](#runtime-request-value-principle)
- [Execution Fact Closure Gate](#execution-fact-closure-gate)
- [Precondition Data Construction Policy](#precondition-data-construction-policy)
- [Seeded Value Closure Policy](#seeded-value-closure-policy)
- [Variable Injection Policy](#variable-injection-policy)
- [Assertion Policy](#assertion-policy)
- [Business Result Observability Policy](#business-result-observability-policy)
- [Authentication Policy](#authentication-policy)
- [Interface Transport Encryption Policy](#interface-transport-encryption-policy)
- [来源](#来源)

## 读取时机

进入 executable 阶段、处理执行配置、造数、变量、断言、鉴权、加解密、长链路补值或脚本生成准备时读取。

## 与组件职责的关系

本文件约束跨阶段执行事实闭合。具体执行级文档字段以 `components/executable-interface-case-set/SKILL.md` 和 `components/executable-interface-case-set/references/io-contract.md` 为准；具体 pytest 物化以 `components/api-test-framework-generator/SKILL.md` 及其 references 为准。

## 规则正文

### Runtime Request Value Principle

This principle applies only to `runtime_request_plan` generation, direct live-request evidence collection, `runtime_value_catalog` normalization, and execution-level case filling. It must not change design-case generation, source fact extraction, document precheck, interface contract generation, Apifox evidence handling, or pytest framework generation semantics.

- 请求结构以接口契约为主：method、path、path/query/header/body 字段、required 字段、字段类型、参数位置、鉴权注入位置和响应提取路径候选必须来自 `接口结构化契约清单.md`、API 文档、OpenAPI、Apifox 契约或源码 DTO 等契约证据。
- 运行值以执行配置和上游返参为主：base URL、账号引用、角色、租户、公共 header、客户端版本、登录方式、secret 引用等来自执行配置；token、业务 ID、订单号、房间号、状态字段和跨步骤变量来自前序接口返参。
- 场景选择以设计级用例为主：设计级用例只约束正向、异常、边界、状态流转、权限或长链路场景，不承担真实手机号、验证码、token、业务码、动态 ID、枚举码值或环境返回文案的确定职责。
- 合法性以数据模型和 DB MCP 交叉校验：`数据模型.md`、数据库 MCP schema、字典表、枚举表、字段约束、唯一键、归属键和清理边界只能用于校验或佐证运行值是否合法；不得替代执行配置、鉴权账号、token 来源或上游动态返参。
- `runtime_request_plan.yaml` 中每个请求参数都应能说明 `structure_source_ref`、`value_source_ref`、`scenario_source_ref` 或 `cross_check_refs` 中至少一种来源；缺少来源时不得由请求器猜字段、猜码值、猜 token 路径、猜业务状态或猜清理方式。
- 真实返参用于推理上下游业务依赖，不用于机械填值。使用返参时必须结合生产步骤、消费步骤、字段语义、长链路 `link_keys`、消费者契约、账号上下文、数据模型/DB MCP 归属键和设计场景，推导当前接口入参、下一个接口入参或下一个接口预期返参/断言候选。
- 只有业务含义匹配、来源已确认、交叉校验无冲突的返参推导，才能进入 `runtime_value_catalog.yaml` 的 `flow_value_links` 并回填执行级用例。若同一字段存在多个候选、字段名相同但业务对象不同、返参来自过期状态、或与契约/数据模型/设计场景冲突，必须记录为 missing/conflict/blocker，不得把某个字面值硬塞进请求参数。
- 对需要运行时取证补值的长链路，先生成并校验 `04-runtime-evidence/runtime_evidence.yaml` 和 `04-runtime-evidence/runtime_value_catalog.yaml`，再由 `$executable-interface-case-set` 消费这些归一化证据回填正式执行级用例；不得绕过该目录直接把请求器临时返回值写入 `执行级接口用例集.md`。
- 运行时事实只能补充执行事实，不能覆盖结构化契约、设计级用例、源码事实、文档基线或数据模型；任何冲突必须写入 `runtime_conflict_report.md` 和 runtime sidecar，并在执行级准出前阻塞。
- 脚本生成阶段不得应用本原则重新取值。`$api-test-framework-generator` 只能消费执行级产物中已经确认并归一化的事实，不能调用 direct requester、读取账号密码、重放 live request 或现场补缺失码值。

### Execution Fact Closure Gate

Before marking execution-level cases or generated scripts runnable, close three execution fact families. Missing closure is `BLOCKED_NEED_EXECUTION_INPUT` or `FAILED_EXECUTION_READINESS`; do not treat the generated script as runnable and do not classify resulting failures as product defects until the affected family is closed.

- 入参闭合：Every main-flow request must include all contract-required business fields, not only public parameters. Each business field must record a source such as interface contract, source DTO, upstream response, runtime evidence, DB MCP dictionary/config, precondition API output, bounded DB seed, deterministic unique generator, or user-filled execution config. Exception cases must explicitly mark the intentionally missing, empty, invalid, out-of-range, unauthorized, or conflicting field and the expected business error evidence. If a main-flow body has only common fields, token, userId, device/client metadata, pagination defaults, or empty body while the contract/source indicates business fields, keep the case out of the runnable denominator.
- 状态闭合：Cases that require business state must have executable setup, verification, and cleanup. Examples include existing conversation/message, withdrawal account, idle or busy call state, balance enough/insufficient, block/unblock relation, ban status, subscription tier, audit/onboarding status, report type, upload asset, or any lifecycle state. Prefer API setup and API cleanup; use SQL only when API cannot create the needed isolated state and the reason is recorded. Every state setup must expose a current-run ID or unique ownership key, DB before/after or API verification evidence when persistence matters, and cleanup bounded to the current-run object. Any chain containing a write-side-effect step defaults to cleanup-required unless source/runtime no-delta, sandbox/isolation, failed-request no-side-effect, or non-live/manual-review exemption evidence is recorded.
- 会话闭合：Every executable step must declare an auth policy and session role. Distinguish `pre_login_no_auth` for SMS/login/third-party login and other pre-auth entries, `app_user_auth` for role-bound app APIs, and `internal_or_gateway_auth` for internal/gateway APIs whose token policy is confirmed by gateway/source/runtime evidence. Role-bound app steps must keep female, male, admin/operator, or other roles in isolated token/user/session contexts; body `token`、`userId`、`appUserId`、session secret/hash values must match the selected role. Pre-login steps must not inject `${auth_token}` or logged-in user fields unless the contract explicitly requires them. If a role receives forced logout/session invalidation, refresh only that role before continuing and do not reuse its stale context.
- For each execution case, write closure evidence into `execution_fact_sources.yaml`: request field sources, state setup/cleanup sources, auth policy, session role, token source, role-context extraction/injection refs, unresolved fields, and unresolved states. The generated script may consume only these closed facts.
- Runtime failure triage must first map failures back to these three families: missing business input, missing business state, or wrong/stale session. Fix generator/materialization or move the case out of the runnable denominator before defect triage. Only after the three families are closed may unexpected 200/500 or wrong business codes become confirmed defect candidates.

### Precondition Data Construction Policy

- 前置数据规则以用户提供或确认的配置为准，不由下游脚本生成阶段自行决定。
- MCP 边界必须区分清楚：上游阶段可以通过数据库 MCP 获取数据库结构、表关系、知识图谱、字段约束和造数证据；脚本生成阶段只能消费归一化后的数据模型、SQL 规则和 fixture 配置，不得生成或保留 MCP 连接数据库调用。
- 数据库 MCP 生成的 `数据模型.md` 必须先通过源码-数据库一致性门禁：连接身份、源码引用表、源码引用字段、主键/唯一键/清理键、轻量表关系知识图谱、铺数顺序、清理逆序、源码可见 DB 副作用均需对账；任一关键项缺失或冲突，不得进入执行级用例或脚本生成。
- 表结构只解决“能不能写字段”，表关系知识图谱解决“先写谁、后写谁、按什么归属清理”。凡涉及数据库铺数、SQL 构造、数据库断言或清理策略，不能只提供字段清单；缺少关系、归属键或清理边界时阻塞为 `BLOCKED_NEED_EXECUTION_INPUT`。
- 构造方式默认优先使用 API 铺数和 API 清理，保持测试路径贴近真实业务入口。
- 只有当 API 无法满足目标前置状态、缺少必要构造入口、无法构造跨表/历史/异常状态，或 API 构造会破坏用例独立性时，才允许转为 SQL 构造。
- 造数范围必须保持最小且服务于业务前置状态。只允许构造用例无法通过真实前置接口自然获得的业务对象、对象状态、关系、权限、余额/额度、审核单、会话、订单、配置或本地枚举码值；不得为了补齐字段而把请求体、响应断言、分页排序、客户端设备信息、运行标识、随机文本、token、验证码、第三方返回码、上游接口应返回的业务 ID 全部改为数据库造数。
- 每条造数规则必须写明 `seed_scope_reason`、`allowed_seed_fields`、`forbidden_seed_fields` 和 `runtime_value_fields`：哪些字段由造数产生，为什么必须造；哪些字段必须来自执行配置、前置接口返参、运行时取证、用户补充或随机/唯一值生成器。若无法区分字段来源，阻塞为 `BLOCKED_NEED_EXECUTION_INPUT`，不得扩大造数范围。
- SQL 前置造数还必须先引用历史形态证据：通过数据库 MCP、数据模型侧车或运行时取证获取同表、同业务状态、同角色关系的少量脱敏历史样本，确认字段格式、枚举/状态、JSON 结构、空值约定、时间格式、父子表关系、页面可见字段和跨角色归属关系。历史数据只能作为形态依据，不能直接复制敏感值，也不能把运行标识写进页面可见业务字段；如果业务要求跨角色关系，必须证明 actor/counterparty 字段方向，不能造出自己订阅自己、自己给自己发消息等无效关系，除非用例本身就是异常分支。
- 转 SQL 时必须在 `前置数据构造规则.md`、`execution_fact_sources.yaml` 和脚本侧 SQL 产物中记录 API 不满足原因、来源证据、影响用例、目标表、归属键、清理策略和 SQL 门禁结果。
- 脚本执行期间生成到数据库的测试数据必须记录 `id`，清理规则必须以 `id` 为唯一标识精准删除本次脚本生成的数据；无法确认 `id` 或清理范围时不得放行到脚本执行。
- 涉及新增或删除数据库数据时，必须生成命令级 `sql_exit_gate`：INSERT 只能通过 `id` 绑定新增单行数据，DELETE 只能通过 `WHERE id = :id` 删除单行数据，并在运行预检中验证新增前后、删除前后的行数边界。
- API 无法满足的原因不明确时不得生成 SQL；应标记 `BLOCKED_NEED_EXECUTION_INPUT`，等待用户补充或确认。

### Seeded Value Closure Policy

This policy applies to business-object preconditions, enum/code candidates, DB assertions, and cleanup boundaries that can be prepared through precondition APIs or bounded database setup. It must not be used for values that originate from an external service response.

- Every generated precondition value must be classified before it can enter execution-level cases: `precondition_api_value`、`db_seeded_value`、`dictionary_or_config_value`、`prior_runtime_response_value`, or `external_dependency_value`.
- Value source priority is: prior step or precondition API response first; confirmed runtime evidence or source-present prior response second; dictionary/config/enum evidence from the normalized data model or DB MCP third; SQL seeded value last and only when API construction cannot satisfy the state.
- Seeded values must be scoped to the minimal precondition needed to make the business scenario executable. They may prepare local business state or local dictionary/config values, but they must not replace values that should be produced by the chain itself, filled by the execution configuration, generated by normal request data rules, or supplied by an external dependency. If a request field can be filled by a producer step, runtime evidence, execution config, deterministic unique generator, or user-filled missing-value checklist, do not create it by DB seed.
- Values obtainable from a precondition API must be produced by that API and captured through explicit JSONPath or regex extraction. Do not duplicate the same value by SQL unless the API cannot construct the required historical, cross-table, abnormal, or isolated state and the SQL exception reason is recorded.
- SQL seeded values must be bounded by source-chain tables, relationship graph, ownership key, cleanup identity, setup order, cleanup reverse order, and SQL exit gate. The seeded record must expose an `id` or equivalent unique ownership key before it can be consumed by a request field, assertion, or cleanup rule.
- Before `$executable-interface-case-set` can mark a case `PASSED`, every code/value produced by precondition setup must be written into the corresponding execution-level case field as either a concrete value or an executable variable reference bound to a setup output. It must not remain as `待填`、`示例值`、`占位码值`、`UNKNOWN`, or a human-only instruction.
- The execution-level artifacts must include a seed-value closure list in `前置数据构造规则.md` and source entries in `execution_fact_sources.yaml`. Each item records case ID, field path, value type, value or variable name, source category, source ref, setup rule ref, assertion ref, cleanup rule ref, and whether it is usable for script generation.
- During pytest execution, setup fixtures create or fetch the value before the request, tests inject the resolved plaintext value into request/query/header/body/path fields, DB assertions verify the expected persistence or state, and cleanup fixtures delete or restore only the current-run data after the test.
- External service response values are isolated. Payment, withdrawal, SMS, Apple/Google, audit, OSS, callback, webhook, risk-control, and other third-party return codes or IDs must be `external_dependency_value` and require sandbox/mock/callback evidence or a precondition API that genuinely returns that value. Do not backfill these values by direct DB seeding unless the tested interface is explicitly the local callback consumer and the external event itself is represented by a signed sandbox/mock callback input.
- If a value source is ambiguous between a local precondition value and an external dependency value, classify it as `external_dependency_value` or block with `BLOCKED_NEED_EXECUTION_INPUT`; do not silently downgrade it to DB seed data.

### Variable Injection Policy

- 变量提取、变量注入、`${变量}` 占位符、运行上下文 key 和 SQL 绑定参数名只要求满足 Python 可执行规则。
- 变量名必须是 Python 合法标识符且不能是 Python 关键字；不得包含空格、横线、点号或其他会导致生成 pytest 脚本不可执行的字符。
- 不额外引入业务命名约束；只要变量能稳定提取、注入并保证脚本可执行即可。
- 上游依赖传递给下游时只使用两类提取形式：JSON 路径和正则表达式。每条依赖必须记录生产用例、消费用例、变量名、提取类型、JSON 路径或 regex pattern/group、来源字段和证据引用。

### Assertion Policy

- 生成 pytest 脚本时断言统一使用 Python `assert`，不得把断言降级为日志、注释或只写入报告。
- 接口响应断言至少覆盖 HTTP 状态码和返回字段；返回字段可用 JSON 路径检查存在性或精确值。
- 每条可执行用例必须记录 `assertion_strength`、`result_observation_mode` 和 `assertion_evidence_refs`。`assertion_strength` 可取 `L1_basic`、`L2_response_field`、`L3_business_observable`、`L4_persistence_verified`、`L5_cleanup_verified`。
- 仅有 HTTP 200 加业务码 200 的断言只能算 `L1_basic`，用于连通性或基础契约证明；不能单独证明写接口、长链路或关键业务结果闭环。
- Live 自动化建议至少 `L2_response_field`；长链路和写接口建议至少 `L3_business_observable`；资金、订阅、订单、结算、任务、关系、消息、评价、审核、回调、清理可验证性等高风险场景建议 `L4_persistence_verified` 或 `L5_cleanup_verified`。
- 涉及落库且需要 DB 证明的断言必须通过 pytest 数据库 fixture 查询落库情况，并把 SELECT 查询、绑定参数、期望行数和字段断言交给 `database_assertor` 执行；下游脚本只消费 fixture 断言规则和数据库配置。
- 脚本阶段的数据库实例必须由 pytest fixture 管理，数据库连接配置只允许落到 `api-test-framework/configs/database.yaml`，不得写入测试用例正文、SQL 命令文件或数据 payload。`database.yaml` 只能保存环境变量引用、alias、driver 和 SQL 文件路径，例如 `${env.APP_DB_URL}`；真实账号、密码和连接串必须运行时注入。

### Business Result Observability Policy

业务结果必须可观测，但不要求所有用例都查库。为每条执行级用例选择并记录一个 `result_observation_mode`：

- `response_field`: 响应字段足以证明业务结果，适用于登录 token、配置查询、纯校验返回明确业务对象等场景。
- `followup_api`: 通过后续查询、详情、列表、状态、关系、消息、资料或统计接口验证创建、更新、删除、发送、发布、评价、订阅等业务结果。
- `db_assertion`: 没有等价可观测 API、API 返回太弱、cleanup 是否成功只能查库、异步/回调最终态只能落库确认，或需要证明无脏数据/恢复 before 快照。
- `cleanup_verification`: 清理或状态恢复动作本身是关键结果，需要用 API 或 DB 证明清理后不可见、恢复或无残留。
- `non_live_manual`: API 和 DB 都无法安全观测，或依赖人工审核、外部三方、不可逆动作、生产态风险；只能进入非 live 或人工复核台账。

API 断言优先于 DB 断言：能通过详情/列表/状态接口证明结果时，不强制 DB。若 API 返回只有基础成功码且没有业务 ID、业务字段或后续状态验证，则可信度不足，不能把该用例标记为业务闭环。若 API 与 DB 都不可观测，阻塞 live 自动化或标记 `generated_non_live`/`manual_review_only`，不得为了通过门禁伪造断言。

DB 断言必须保持最小范围：只查源码链路涉及的表和字段，使用当前运行的业务 ID、响应 ID、请求 ID、idempotency key、traceId 或 run-unique marker 绑定；不得宽泛按用户、租户或时间窗口证明结果。

### Authentication Policy

- 鉴权方式以 token 为主，执行级和脚本阶段必须能确定 token 来源：显式 token、登录/授权接口动态获取 token，或用户提供的可执行 token 获取规则。
- token 默认通过 header 注入，未指定字段名时使用 `Authorization: Bearer <token>`；如接口契约或执行配置要求 query、body 或 cookie 注入，可按请求方法覆盖注入位置。
- 不额外限制请求方法；GET、POST、PUT、PATCH、DELETE 等请求可通过 `method_overrides` 分别设置 token 注入方式，目标是保证生成脚本可以直接执行。
- token 来源、提取路径或注入位置无法确定时，应阻塞为 `BLOCKED_NEED_EXECUTION_INPUT`，不得生成需要人工猜测鉴权的脚本。
- 执行级和脚本阶段必须按接口类型显式选择鉴权策略：`pre_login_no_auth` 用于短信发送、登录、三方登录、验证码校验等登录前入口；`app_user_auth` 用于普通 App 用户接口；`internal_or_gateway_auth` 用于 `/internal/**`、网关转发、服务间调用或内部运维入口。不能把普通 App token 默认套到 internal 接口，也不能给 pre-login 接口默认注入登录态 token。
- 多角色运行上下文必须隔离。每个 `session_role` 都应维护自己的 token、userId/appUserId、session secret/hash、账号业务状态和刷新规则；脚本不得在 female、male、admin/operator、default 等角色之间共享可变 token 或使用上一次请求残留上下文。若某角色返回 forced logout、session invalid、token expired 或等价业务码，只能刷新该角色并重试其后续步骤，不能污染其他角色。
- 每个 step 的 body/query/header/path 中的 token、userId、appUserId、租户、角色、session secret/hash 等身份字段必须与 `session_role` 和 `auth_policy` 一致；若出现 `${auth_token}`、`${login_user_id}`、`${session.userId}` 等占位符无法解析，或解析后跨角色不一致，脚本生成前应阻塞或把该用例移出 runnable 分母。
- 当长链路用例需要特定账号、角色、租户、权限或账号业务状态时，该长链路的第一个可见请求步骤必须是登录/授权接口。登录接口、账号引用、凭据 secret_ref、token 提取路径、账号上下文字段提取路径和 token 注入位置必须来自执行配置、接口契约、运行时取证或其他源绑定证据；不得用静态 token 注入替代链路首步登录。
- 账号型长链路的登录步骤必须把 token 以及后续步骤需要的账号上下文（如用户 ID、角色、租户或业务身份字段，以实际契约为准）写入 `runtime_context`，后续业务步骤只能消费这些明文运行变量和已确认的 token 注入规则。若登录接口、凭据引用、提取路径或注入位置缺失，应阻塞为 `BLOCKED_NEED_EXECUTION_INPUT` 并进入长链路缺失码值补充清单。
- 不需要特定账号或账号状态的链路不强制登录首步，可继续使用普通鉴权规则；但一旦执行级产物声明 `specific_account_required`、`required_account_role`、`required_account_business_state` 或等价账号型链路标记，就必须提供 `login_entry_rule` 证据并在脚本流中保持登录为第一步。

### Interface Transport Encryption Policy

- 业务链路用例、执行级入参、断言、变量提取和变量注入必须始终维护明文业务数据。密文只允许出现在 HTTP 传输适配层、运行日志的安全遮蔽视图或调试附件中，不得作为业务链路变量继续传递。
- 请求加密发生在 `HttpClient` 发起请求前；响应解密发生在 `HttpClient` 收到响应后。`Flow Runner` 必须只处理明文请求模板和解密后的明文响应，再用 JSONPath 或 regex 提取变量写入 `runtime_context`，供下一个接口以明文占位符注入。
- 当不存在确认加密接口时，可按普通 HTTP 脚本生成；当存在确认加密接口，且加解密方法、key 来源、请求明文范围、请求序列化方式、请求报文包装、响应报文包装均已确认时，生成带传输适配层的脚本；当存在确认加密接口但算法、key、请求明文范围、请求序列化方式或报文包装任一缺失时，停止在脚本生成前，状态为 `BLOCKED_NEED_EXECUTION_INPUT`。
- 源码识别出的 `requires_encryption_if_project_default_enabled` 不是最终执行结论，必须结合项目默认传输策略、用户确认、网关/客户端协议或执行配置后，才能变为确认加密接口。`no_encrypt_candidate` 也必须确认后才能作为明文调用接口。`policy_required` 一律阻塞或要求补充策略。
- 运行契约必须以泛化字段表达，不得写入项目专属算法名作为通用规则：至少记录 `encryption_status`、`request_encrypt`、`response_decrypt`、`algorithm_ref`、`key_source_ref`、`request_payload_scope`、`request_plaintext_serialization`、`request_envelope`、`response_envelope`、`confirmed_no_encrypt_interfaces`、`confirmed_encrypt_interfaces` 和证据来源。
- 当确认的请求契约为“公共参数 + 业务参数整体加密”时，执行级和脚本阶段必须先合并公共参数与业务参数为一个明文参数字典，再序列化为 UTF-8 JSON 字符串后整体加密；不得逐字段加密，也不得把密文继续作为业务变量传递。
- 当确认的请求包装为 `data` 字段时，HTTP Client 必须把密文放入 JSON 请求体 `{"data": "<密文字符串>"}`；不得写入 `param`，也不得把密文字符串直接作为 body。
- 当确认的响应契约为外层 JSON 明文、`data` 字段密文时，HTTP Client 只在响应 `data` 为字符串时解密该字段，并把解密后的 JSON 字符串解析成对象后回填为明文 `data`；外层 `code`、`message` 等字段保持原样。断言、变量提取和链路注入都必须基于这个解密后的明文响应对象。
- AES、Base64、mode、padding、IV、charset 等算法细节可以来自算法目录或执行配置，但 `key_source_ref` 必须独立确认；只有代码中出现加解密函数而没有 key 来源时，仍视为加解密运行契约不完整。

## 来源

本文件从 `SKILL.md` 原主契约拆分而来；完整历史契约保存在 `references/full-contract.md`。
