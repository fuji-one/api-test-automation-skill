---
name: doc-precheck-coverage
description: Validate Markdown PRD, API, and system-analysis documents before generating test scenarios or interface test points. Use when Codex needs to perform document precheck, coverage readiness review, requirement/API/system-analysis consistency validation, PRD文档/API文档/系统分析文档前置校验, 覆盖率100%准入检查, or produce modification points and suggestions so later generated scenarios can achieve 100% traceable coverage of explicit document content.
---

# Doc Precheck Coverage

## Goal

Before generating test scenarios, validate the provided `.md` PRD, API, and system-analysis documents from both macro and fine-grained perspectives. The coverage target is **100% traceable coverage of all explicit, testable content in the documents**.

Do not claim coverage for missing, oral, hidden, or inferred requirements. If the documents are insufficient, output blocking issues, modification points, and concrete modification suggestions before any scenario generation.

## Required Inputs

Require these three Markdown documents:

- PRD document
- API document
- System-analysis document

If any document is missing, mark the precheck as `阻塞`. Continue only by listing the missing document and the coverage dimension that cannot be guaranteed.

## Workflow

1. Identify the three source documents and their business scope.
2. Run macro admission checks.
3. Run fine-grained checks for PRD, API, and system analysis.
4. Run internal consistency checks for each document.
5. Run cross-document consistency checks.
6. Run coverage guarantee checks.
7. Produce a precheck conclusion: `通过`, `有风险通过`, or `阻塞`.
8. For every failed or risky item, provide source location, modification points, and modification suggestions.
9. If passed, list the downstream documents that can be generated to prove 100% traceable coverage.

## Output Scope Rule

Keep precheck outputs lightweight. Before test point analysis, produce only one consolidated precheck report. Do not create separate standalone documents for input recognition, macro checks, fine-grained checks, internal consistency checks, additional coverage checks, unmapped items, statistics, or risk lists.

Use those checks as report sections or summarized evidence inside the single report. Generate separate artifacts only when they directly support downstream test point analysis.

Output format must be Markdown (`.md`). Do not generate non-Markdown output files for this skill.

This consolidated precheck report is not an input artifact for interface test case design. To continue toward test case design, first generate the downstream Markdown test point analysis artifacts listed in this skill. The next skill must consume those artifacts, not this precheck report, as coverage-object sources.

## Coverage Definition

Use this definition consistently:

- `100%覆盖` means every explicit requirement, interface, field rule, error code, state, transition, dependency, exception, and acceptance criterion in the provided documents has a traceable test design target.
- `100%覆盖` does not mean covering undocumented implementation details, oral agreements, or missing rules.
- Never fabricate missing rules, request bodies, response bodies, error codes, states, or system behaviors.

## Macro Admission Checks

Evaluate whether the document set is complete enough to start test design.

| 校验方向 | 必查问题 | 不通过影响 |
|---|---|---|
| 文档齐全性 | 是否同时提供 PRD、API、系统分析 | 缺少业务、契约或内部行为覆盖 |
| 版本一致性 | 三份文档是否对应同一业务版本 | 需求、接口、状态可能错配 |
| 范围一致性 | 三份文档描述的模块、功能、边界是否一致 | 业务动作可能无接口或无状态依据 |
| 术语一致性 | 同一概念是否名称一致 | 容易重复、漏测或误判 |
| 业务闭环 | 是否有主流程、分支流程、失败流程 | 只能覆盖单点，无法覆盖端到端场景 |
| 接口闭环 | 是否有完整接口清单和接口契约 | 无法覆盖参数、响应、错误码 |
| 状态闭环 | 是否有状态定义、初始态、终态、流转规则 | 无法覆盖状态机和非法流转 |
| 异常闭环 | 是否描述失败、超时、重试、补偿、回滚 | 异常场景会缺失 |
| 数据闭环 | 是否说明核心对象、关键字段、对象关系 | 无法覆盖数据一致性 |
| 权限闭环 | 是否说明角色、鉴权、权限边界 | 权限场景会缺失 |
| 依赖闭环 | 是否说明下游系统、消息、回调、定时任务 | 依赖失败和异步场景会缺失 |
| 可验证性 | 每条规则是否能判断通过或失败 | 无法形成可执行测试点 |

The consolidated precheck report must summarize:

- 文档准入结论
- 阻塞项清单
- 非阻塞风险项清单
- 覆盖能力概览
- 建议补充内容

## Fine-Grained PRD Checks

Check the PRD at atomic requirement and rule level.

| 校验对象 | 细颗粒度检查项 |
|---|---|
| 功能点 | 是否有编号、名称、描述、所属模块、优先级 |
| 用户角色 | 是否说明角色类型、权限边界、可操作功能 |
| 页面/入口 | 是否说明入口、操作动作、跳转结果、页面、菜单、按钮、触发入口或外部入口 |
| 业务流程 | 是否有起点、终点、主流程、分支流程、失败流程 |
| 业务规则 | 是否有触发条件、判断条件、处理结果 |
| 验收标准 | 是否能转化为明确断言 |
| 数据规则 | 是否说明金额、数量、时间、次数、状态等边界 |
| 限制条件 | 是否说明黑白名单、频控、额度、有效期、区域等限制 |
| 通知规则 | 是否说明短信、站内信、消息、回调触发条件 |
| 异常处理 | 是否说明失败提示、回滚、重试、人工处理 |
| 历史兼容 | 是否说明老数据、迁移数据、灰度数据处理 |
| 非功能要求 | 是否说明性能、稳定性、安全、审计等要求 |

The consolidated precheck report must summarize PRD evidence for:

- 需求点原子清单
- 业务规则原子清单
- 用户路径清单
- 验收标准断言表
- PRD 覆盖矩阵
- PRD 缺口与修改建议

## Fine-Grained API Checks

Check every API endpoint at contract and validation level.

| 校验对象 | 细颗粒度检查项 |
|---|---|
| 接口基础信息 | method、path、接口名、模块、描述是否完整 |
| 鉴权 | token、签名、权限、租户、用户身份是否说明 |
| 请求头 | content-type、traceId、语言、渠道、版本号等是否说明 |
| Path 参数 | 类型、必填、格式、合法范围是否说明 |
| Query 参数 | 必填、默认值、枚举、组合关系是否说明 |
| Body 参数 | 字段类型、必填、长度、精度、格式、嵌套结构是否说明 |
| 字段约束 | 最小值、最大值、正则、枚举、唯一性是否说明 |
| 字段依赖 | A 字段存在时 B 是否必填，字段互斥关系是否说明 |
| 请求示例 | 正常示例、异常示例是否存在 |
| 响应结构 | 成功响应、失败响应、空数据响应是否说明 |
| 错误码 | 错误码、错误信息、触发条件是否说明 |
| 状态码 | HTTP 状态码和业务错误码是否对应 |
| 幂等 | 幂等键、重复请求结果、幂等窗口是否说明 |
| 分页排序 | page、size、sort、过滤条件是否合法 |
| 文件或二进制 | 文件大小、类型、上传方式、失败处理是否说明 |
| 回调接口 | 回调时机、验签、重试、响应要求是否说明 |

The consolidated precheck report must summarize API evidence for:

- 接口契约覆盖表
- 字段级测试点矩阵
- 错误码触发矩阵
- 鉴权权限测试矩阵
- 接口异常测试点
- API 缺口与修改建议

## Fine-Grained System-Analysis Checks

Check internal behavior, domain state, dependency, and consistency rules.

| 校验对象 | 细颗粒度检查项 |
|---|---|
| 领域对象 | 对象名称、字段、唯一标识、生命周期是否明确 |
| 对象关系 | 一对一、一对多、聚合关系、引用关系是否说明 |
| 状态定义 | 状态枚举、含义、初始态、终态是否说明 |
| 状态迁移 | 触发动作、前置状态、目标状态、非法迁移是否说明 |
| 数据变更 | 新增、更新、删除、冻结、归档规则是否说明 |
| 事务边界 | 本地事务、分布式事务、最终一致性是否说明 |
| 并发控制 | 锁、版本号、重复提交、竞态处理是否说明 |
| 幂等设计 | 幂等字段、幂等范围、重复调用返回是否说明 |
| 下游依赖 | 调用系统、接口、超时、失败、降级是否说明 |
| 消息事件 | 事件名称、触发条件、消费方、重试机制是否说明 |
| 定时任务 | 执行频率、扫描范围、失败补偿是否说明 |
| 缓存机制 | 缓存键、过期时间、更新策略是否说明 |
| 审计日志 | 操作日志、状态日志、异常日志是否说明 |
| 数据一致性 | 主表、明细表、流水表、状态表是否一致 |
| 补偿机制 | 补偿触发条件、补偿次数、人工介入是否说明 |

The consolidated precheck report must summarize system-analysis evidence for:

- 状态机覆盖矩阵
- 领域对象测试点
- 数据一致性测试点
- 异步事件测试点
- 补偿与重试测试点
- 系统分析缺口与修改建议

## Internal Consistency Checks

Run these checks before cross-document checks. A document cannot be considered complete if it contradicts itself.

| 文档类型 | 内部一致性校验 |
|---|---|
| PRD | 同一需求、业务规则、角色权限、流程分支、验收标准是否前后一致 |
| PRD | 是否存在同一业务动作在不同章节有不同触发条件、处理结果或失败提示 |
| API | 是否存在同 method + path 重复定义、字段类型冲突、必填规则冲突、错误码含义冲突 |
| API | 请求示例、响应示例、字段表、错误码表是否互相一致 |
| 系统分析 | 同一领域对象、状态枚举、状态迁移、数据变更规则是否前后一致 |
| 系统分析 | 是否存在同一状态在不同章节有互斥的前置条件、目标状态或补偿规则 |

The consolidated precheck report must summarize internal consistency evidence for:

- PRD 内部冲突清单
- API 内部冲突清单
- 系统分析内部冲突清单
- 冲突影响范围
- 冲突修改建议

## Additional Coverage Checks

Run these checks to avoid hidden coverage gaps that are not always visible in basic PRD/API/system-analysis structures.

| 校验方向 | 必查问题 | 不通过影响 |
|---|---|---|
| 测试前置条件 | 是否说明角色、账号、初始状态、基础数据、依赖数据、配置开关 | 无法稳定生成可执行场景 |
| 异步完成条件 | 消息、回调、定时任务是否说明完成判定、等待窗口、失败判定 | 异步场景无法判断通过或失败 |
| 环境与渠道 | 是否说明环境、渠道、客户端版本、租户、灰度开关、区域差异 | 不同范围下的覆盖边界会不清晰 |
| 数据生命周期 | 是否说明创建、更新、删除、过期、冻结、归档、保留策略 | 数据状态和历史数据场景会漏 |
| 敏感数据与合规 | 是否说明手机号、证件号、账户、支付、隐私字段的脱敏、权限、审计、日志规则 | 权限、审计和数据泄露风险场景会漏 |
| 配置化规则 | 是否说明额度、频控、开关、阈值、白名单、黑名单等配置来源和变更影响 | 边界值和配置变更场景会漏 |
| 时间规则 | 是否说明有效期、时区、自然日/工作日、节假日、跨天、超时口径 | 时间边界和定时任务场景会漏 |
| 排他与优先级 | 多条规则同时命中时是否说明优先级、互斥关系、覆盖关系 | 组合规则场景会误判 |

The consolidated precheck report must summarize additional coverage evidence for:

- 前置条件缺口清单
- 异步完成条件缺口清单
- 环境、渠道、灰度覆盖边界清单
- 数据生命周期缺口清单
- 敏感数据与合规缺口清单
- 配置化、时间、规则优先级缺口清单

## Cross-Document Checks

Run these mappings to prevent the three documents from being individually complete but mutually inconsistent.

| 交叉关系 | 细颗粒度校验 |
|---|---|
| PRD 功能点 -> API | 每个用户动作是否有接口承载 |
| PRD 规则 -> API 字段 | 每条业务规则是否能通过字段或状态验证 |
| PRD 流程 -> 系统状态 | 每个流程节点是否对应内部状态 |
| API 接口 -> PRD 场景 | 每个接口是否有业务使用场景 |
| API 错误码 -> PRD 异常 | 每个错误码是否能找到业务触发原因 |
| API 入参 -> 系统对象 | 每个关键字段是否落到领域对象 |
| API 响应 -> 系统状态 | 响应状态是否和内部状态一致 |
| 系统状态 -> API 操作 | 每个状态迁移是否有接口、任务或事件触发 |
| 系统事件 -> PRD 通知 | 每个事件是否对应业务通知或后续动作 |
| 系统依赖 -> API 异常 | 下游失败是否能反映到接口错误或状态变化 |
| 数据对象 -> PRD 规则 | 核心对象字段是否都有业务含义 |
| 补偿规则 -> 测试场景 | 每个补偿动作是否有可触发场景 |

The consolidated precheck report must summarize cross-document evidence for:

- 需求-接口-状态三向追踪矩阵
- 字段-规则-断言映射表
- 错误码-异常场景映射表
- 状态迁移-触发入口映射表
- 依赖失败-补偿场景映射表

## Coverage Guarantee Rules

After the precheck passes, guarantee coverage through traceable evidence, not verbal claims. Treat these proof rules as acceptance criteria for downstream generated artifacts. During precheck, verify that the source documents contain enough information to satisfy these proof rules:

- Every PRD requirement has at least one test scenario ID.
- Every API endpoint has at least one interface test point ID.
- Every key field has legal, illegal, and boundary test points.
- Every error code has a trigger scenario.
- Every state has entry, transition, terminal, and illegal-transition scenarios.
- Every dependency system has success, failure, timeout, retry, and compensation scenarios.
- Every generated test point can be traced back to its source requirement, interface, field, state, error code, dependency, or system rule.

Do not silently skip a proof rule because the source document lacks constraints. If a core field, state, dependency, or rule lacks enough information to satisfy these proof rules, mark it as `阻塞`. If the item is optional or outside the core flow, mark it as `有风险通过` and list it in the risk table.

## Traceability Evidence Rules

Every issue, risk, unmapped item, and modification suggestion must include enough evidence for the user to return to the source document and fix it.

Required evidence fields:

- 来源文档：PRD、API、系统分析, or cross-document.
- 来源位置：file name, heading, section, table name, API path, or state name when available.
- 原文摘要：quote or summarize the relevant source text briefly.
- 影响对象：requirement ID, API endpoint, field, error code, state, transition, dependency, or business rule.
- 影响范围：which downstream test design coverage cannot be guaranteed.

## Conclusion Rules

Use only these conclusion values:

- `通过`: All required macro, fine-grained, internal consistency, additional coverage, cross-document, traceability evidence, and coverage guarantee checks are complete. Later test design can achieve 100% traceable coverage of explicit document content.
- `有风险通过`: Core coverage is possible, but non-blocking omissions must be listed as risks and cannot be counted as guaranteed coverage.
- `阻塞`: Critical information is missing. Generating full scenarios would require fabrication or would knowingly miss coverage.

Mark as `阻塞` when any of these occur:

- PRD lacks explicit business rules or acceptance criteria for core flows.
- API lacks field constraints, response structure, or error codes for core interfaces.
- System analysis lacks state definitions, state transitions, or dependency exception rules.
- Versions or business scope conflict across the three documents.
- Key flows lack failure paths.
- State transitions lack trigger conditions.
- Downstream dependencies lack timeout, failure, retry, or compensation rules.
- Core fields have no business meaning or system object mapping.
- Acceptance criteria cannot be converted into assertions.
- Core items fail cross-document mapping, such as PRD requirement without API/state support, API without PRD scenario, or state transition without trigger.
- Any coverage guarantee rule cannot be satisfied for core flows, core fields, core states, core error codes, or core dependencies.
- Core scenario preconditions are missing, such as role, account, initial state, base data, dependency data, or configuration switch.
- Async behavior lacks completion condition, wait window, failure condition, retry rule, or callback handling.

## Required Output Format

Produce the precheck report in Chinese with this structure:

```markdown
# 文档前置校验报告

## 1. 校验结论
- 结论：通过 / 有风险通过 / 阻塞
- 覆盖目标：对文档中已明确表达的信息做到 100% 可追踪覆盖
- 是否允许进入测试场景生成：是 / 否

## 2. 输入文档识别
| 文档类型 | 文件 | 版本/日期 | 业务范围 | 识别结果 |
|---|---|---|---|---|

## 3. 覆盖准入概览
| 校验域 | 结果 | 关键结论 | 对测试点分析的影响 |
|---|---|---|---|

## 4. 必须修改项
| 编号 | 类型 | 来源文档 | 来源位置 | 原文摘要 | 问题 | 必须修改点 | 建议写法 |
|---|---|---|---|---|---|---|---|

## 5. 非阻塞风险项
| 编号 | 来源文档 | 来源位置 | 风险 | 影响 | 建议 |
|---|---|---|---|---|---|

## 6. 未映射核心对象
| 编号 | 类型 | 来源文档 | 来源位置 | 未映射对象 | 影响 | 修改建议 |
|---|---|---|---|---|---|---|

## 7. 校验统计汇总
| 分类 | 检查项总数 | 通过数 | 风险数 | 阻塞数 | 未映射数 |
|---|---:|---:|---:|---:|---:|

## 8. 后续测试点分析产物
| 产物 | 作用 | 是否可生成 |
|---|---|---|

## 9. 下一步建议
```

For failed checks, make modification suggestions concrete. Prefer this style:

- 问题：API 字段 `amount` 只有字段名，没有类型、精度、最小值、最大值。
- 影响：无法生成金额边界、非法金额、精度校验测试点。
- 修改建议：补充 `amount` 类型为 decimal，精度为 2 位小数，最小值为 0.01，最大值为业务配置上限，并说明为必填字段。

## Downstream Documents After Passing

When the precheck passes, state that these downstream artifacts can be generated for test point analysis:

- 需求-接口-状态三向追踪矩阵
- 字段-规则-断言映射表
- 错误码-异常场景映射表
- 状态迁移-触发入口映射表
- 依赖失败-补偿场景映射表
- 业务场景测试点文档
- 接口测试点文档
- 接口结构化契约清单
- 状态机与数据一致性测试点文档
- 异常、补偿、依赖测试点文档
- 覆盖率矩阵
- 剩余风险清单

Do not generate separate standalone documents for macro admission checks, fine-grained precheck results, internal consistency checks, additional coverage checks, unmapped item lists, or statistics. Keep those as sections in the consolidated precheck report unless the user explicitly asks to export them separately.

Important handoff rule:

- The **文档前置校验报告** only proves readiness and records risks.
- It must not be used as the coverage-object source for interface test case design.
- Before using `$interface-testcase-design`, generate or provide the downstream Markdown test point analysis artifacts above.

## Language and Encoding

Write reports and comments in Chinese. Preserve UTF-8 text and check generated Chinese content for garbling before final delivery.
