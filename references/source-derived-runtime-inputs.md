# 源码推导入参与真实请求回填策略

## 目录

- [读取时机](#读取时机)
- [核心原则](#核心原则)
- [推进流程](#推进流程)
- [源码取参规则](#源码取参规则)
- [候选值生成规则](#候选值生成规则)
- [真实请求验证规则](#真实请求验证规则)
- [失败回填队列规则](#失败回填队列规则)
- [禁止事项](#禁止事项)

## 读取时机

当用户要求“从源码获取入参”、“按规则自己填写剩余接口真实业务入参”、“规则推导候选值 + 真实请求验证 + 失败回填队列原因”、或需要在 `04-runtime-evidence/` 中继续补齐可执行请求事实时读取。

## 核心原则

源码给出候选事实，真实请求确认候选是否可用，失败响应反向修正队列原因。不要把源码推导值直接当成执行级事实；只有真实响应、DB before/after、或明确用户配置闭合后，才可标记为 `confirmed` 和 `usable_for_execution_case=true`。

运行时补值必须保持队列驱动。单个接口失败不停止整体推进；失败项写清楚未闭合原因并进入 `retryable` 或 `skipped_recoverable`，继续处理其它可行动项。

## 推进流程

1. 从 `04-design-case-handoff/case_list.yaml` 和源码契约定位目标接口、case 类型、优先级、请求 schema、必填字段、状态码和 source refs。
2. 回到源码阅读 Controller、DTO、Service、Repository/Mapper、枚举、错误码、配置读取、鉴权注解和加解密入口，判断字段语义、默认值、是否只读、是否变更状态、是否依赖外部服务。
3. 将接口分为可直接请求、需登录态、需 DB ownership/cleanup、需外部 sandbox/mock/callback、需人工确认、不可执行等队列类别。
4. 对可请求项按源码规则生成候选入参，并记录每个字段的来源和推导理由。
5. 使用复用 requester 发送真实请求：复用 HTTP session/连接池、模块 client、加解密适配器、角色 token/session 上下文；不要为每个接口重新构造 requester。
6. 用真实响应判定候选是否成立。成立则写入 `runtime_evidence.yaml`、`runtime_value_catalog.yaml`、`runtime_request_plan.yaml` 并把队列项置为 `evidenced`。
7. 不成立则保留响应证据，按失败原因回填 `runtime_evidence_queue.yaml` 和 `runtime_stage_status.yaml.continuation_queue`，不要删除失败证据。
8. 每个批次后运行 runtime evidence validator、总控 validator、敏感信息扫描和 UTF-8/乱码扫描；报告里写明这只是 partial/blocked 门禁，不代表脚本生成完成。

## 源码取参规则

- DTO 字段和 validation 注解决定必填、空值、类型、集合形态、缺字段异常候选。常见信号包括 `@NotNull`、`@NotBlank`、`@NotEmpty`、`@Valid`、枚举转换和手写参数校验。
- Controller 和 Service 决定字段业务语义。字段名相同不代表可直接复制，必须核对角色、对象、生命周期、上下游关系、登录用户上下文和 source refs。
- 默认公共参数、token 注入、请求加密、响应解密优先从前端源码或网关/拦截器源码获取；缺失时写运行时配置缺口，不在 skill 中固化项目密钥、账号、token、base URL 或设备值。
- 错误码枚举、异常类、BusinessException、message 文案可作为异常分支断言候选；只有真实响应命中后才写 confirmed。
- 配置读取类接口、健康检查、纯查询服务、`@Transactional(readOnly=true)` 可作为低风险优先项；仍需验证是否需要登录态、网关前缀或公共参数。
- 变更类接口必须先闭合 source-bound DB before/after、ownership key、delta assertion 和 cleanup boundary。源码只说明可能影响哪些表，不能代替真实 DB delta。

## 候选值生成规则

- 优先使用用户提供的测试环境、账号、验证码、授权范围和外部依赖说明。
- 其次使用已确认的登录响应、已确认的前序接口响应、DB MCP 有界样本、源码枚举/默认值、只读配置接口响应。
- ID 类字段必须说明来源：登录用户、目标用户、provider、context、task、product、tier、moment、call、relationship 等；角色和业务对象不匹配时不得填充。
- 异常用例可通过缺必填字段、非法枚举、不存在 ID、空集合、业务状态冲突等构造，但必须确保不会产生未声明状态变更。
- 对缺必填异常，允许省略目标字段并补齐其它公共参数；真实返回若为鉴权失败、网关失败或未登录，应判定为会话/请求物化失败，而不是目标异常分支 confirmed。
- 对只读主流程，可使用已登录测试账号、已知用户 ID、DB 有界样本和源码默认值构造最小请求体。
- 对正向主流程、live 用例、长链路和页面可见字段，候选值必须优先取源码枚举、字典接口、配置接口、DB 有界样本、已确认运行时响应或用户配置中的合法真实值。若字段是用户可编辑资料、页面展示文本、标准地区或标准本地化类普通入参，且源码/契约未要求项目专属 ID、枚举码、状态码或外部依赖值，可使用通用真实样例，例如省市用 `广东省/深圳市`、`浙江省/杭州市`，国家/币种/时区用 `CN/CNY/Asia/Shanghai` 等合法组合。
- 页面可见或业务可读字段不得使用明显占位值，例如 `自动化省`、`测试市`、`xxx`、`UNKNOWN`、`示例值`。只有当用例目标是非法值、未知枚举或参数校验分支时，才允许这类值进入请求，并且断言必须绑定到对应错误码、错误消息或校验结果。
- 对地区这类存在层级关系的字段，省市、国家城市、币种时区等组合必须自洽；不能为了凑齐字段而填入不匹配的层级组合。无法确认合法组合时，只有普通展示/资料字段可使用通用真实样例并写明来源类别；ID、状态、金额、权限、关系键、外部依赖返回值必须记录为待补值或阻塞项。

## 真实请求验证规则

- 请求必须限定在用户授权的测试环境和 `case_list.yaml` 选定分母内，不做生产请求，不做分母外扫描。
- 先确认请求物化正确：base URL、网关前缀、method/path、公共参数、token 注入、加密 envelope、响应解密、角色上下文。
- 登录态接口返回未登录、token 失效、解密失败、HTTP 404/500、网关路径异常时，优先归类为 requester/session/path/materialization 问题，不能直接认定业务接口失败。
- 主流程以 HTTP 状态、业务 code、响应结构、关键字段、源码断言和必要 DB delta 共同确认。
- 异常分支以目标错误码/message 或源码可追溯异常为确认依据；如果命中的是未登录、公共参数缺失、网关错误或其它前置失败，标为 `retryable`。
- 失败响应也要保留为 evidence，但 `source_status=missing` 且 `usable_for_execution_case=false`，除非它确实命中目标异常分支。

## 失败回填队列规则

队列项必须写 `queue_state`，不要在 item 内写 `status`。

推荐 reason_code：

- `runtime_evidence_confirmed`：真实请求已确认，可用于执行级候选。
- `requires_business_value_materialization_before_request`：还缺业务入参，可继续用源码、DB 样本、前序响应或配置接口补齐。
- `requires_db_before_after_ownership_key_or_cleanup_closure`：涉及变更或状态依赖，必须先闭合 DB before/after、ownership key、delta 和 cleanup。
- `runtime_request_rejected_by_business_state_or_candidate_value`：已请求但业务状态或候选值不满足，需要换数据或准备状态后重试。
- `request_materialization_or_session_not_closed`：请求物化、登录态、token、加解密、公共参数或网关路径未闭合。
- `external_sandbox_or_callback_required`：支付、Apple/Google、OSS、回调、审核、三方校验等外部依赖缺 sandbox/mock/callback payload。
- `blocked_outside_selected_scope`：接口不在当前选定 case 分母或用户授权范围内。

每次失败回填都要记录 `last_attempt`、`next_action`、`evidence_refs` 和可复现的响应摘要。能继续补的写 `retryable` 或 `skipped_recoverable`；只有授权缺失、外部依赖缺失、清理边界无法闭合、证据冲突、分母外范围等才写 `blocked_final` 或 `excluded`。

## 禁止事项

- 不把源码推导值直接升级为 confirmed。
- 不把真实请求失败直接升级为产品缺陷；先排除请求物化、会话、候选值、业务状态、DB 前置和清理闭环问题。
- 不用 DB 宽表扫描、宽删除或按用户 ID 清空基线数据来制造可执行条件。
- 不在 skill 中沉淀项目专属账号、手机号、验证码、token、AES key、base URL、业务 ID 或测试数据。
- 不在 `05-executable-interface-case-set/` 或 `api-test-framework/` 中重新发 live request；它们只能消费 `04-runtime-evidence/` 的归一化 sidecar。
