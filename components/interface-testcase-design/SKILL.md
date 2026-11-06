---
name: interface-testcase-design
description: Generate one fully traceable interface test case design document from precheck-approved coverage artifacts, including requirement-interface-state matrices, field-rule-assertion mappings, error-code exception mappings, state-transition mappings, dependency-compensation mappings, interface structured contract lists, and coverage matrices. Use when Codex needs 接口测试用例设计, 测试点转用例, 覆盖率100%用例设计, or coverage-object-driven API test case design after document precheck has passed.
---

# Interface Testcase Design

## Goal

Generate exactly one Chinese Markdown (`.md`) document: **接口测试用例设计文档**.

Use the principle: **先建覆盖对象池，再填充用例，最后反向验收覆盖率**. Do not directly write test cases from intuition. Every test case must bind to coverage object IDs and source evidence.

This skill produces test case design, not executable automation scripts. Do not generate code, request body fixtures, mock setup files, non-Markdown files, or separate coverage documents unless the user explicitly asks.

Core gate principle:

- Every coverage object must have a unique ID.
- Every test case must bind to coverage object IDs.
- The coverage matrix must reverse-check to **0 uncovered objects** before claiming 100% coverage.

## Required Inputs

Require Markdown (`.md`) test point analysis artifacts or equivalent Markdown sources that contain the same coverage objects. Do not use the previous skill's consolidated precheck report as an input file for this skill.

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
- 剩余风险清单, if any

If the user provides only the previous skill's consolidated precheck report, output a minimal **接口测试用例设计文档** with a blocker section explaining that test point analysis artifacts are required. Do not claim 100% coverage from the precheck report alone.

If the previous skill's consolidated precheck report is provided together with valid artifacts, do not extract coverage objects from that report. Use it only as optional risk context, and base coverage objects exclusively on the matrices, test point documents, coverage matrix, or equivalent Markdown coverage-object sources.

To claim `覆盖率 100%`, all required coverage-object artifacts above or equivalent coverage-object Markdown sources must be available. Equivalent Markdown sources must contain fields equivalent to `$test-point-analysis` schemas, including coverage object ID, object type, source artifact/document, source location, source summary, core flag, mapping relationship, minimum coverage rule, coverage status, and covered test point or case IDs. If an artifact is missing but its coverage objects are available in another provided Markdown source, continue and cite that source. If core coverage objects cannot be identified, mark the relevant section as `阻塞`.

The `接口结构化契约清单` is required contract context when available from Stage 2. Use it to design trigger interfaces, parameter structures, input designs, and response assertions. Do not treat it as an independent coverage-object source and do not change the case generation strategy. It may refine the coverage denominator through contract coverage rules (`契约覆盖规则`) that bind to existing `API-*`, `FIELD-*`, and `ERR-*` objects. If it is missing but the same contract facts are available in other Stage 2 Markdown artifacts, continue and cite those artifacts. If required contract facts are missing everywhere, mark impacted cases or objects as `阻塞`.

## Output Scope Rule

Produce only one deliverable:

- **接口测试用例设计文档** in Markdown (`.md`) format

Do not output standalone files for coverage object pool, interface skeleton cases, business rule cases, state-machine cases, exception cases, reverse validation, or coverage statistics. These can appear only as sections inside the single design document.

## Workflow

1. Verify required Markdown artifacts and coverage object availability.
2. Verify interface structured contract context and align it with `API-*` IDs.
3. Build the coverage object pool from coverage-object artifacts.
4. Assign stable coverage IDs.
5. Define minimum coverage rules for each object type.
6. Generate interface base cases.
7. Add business rule and scenario cases.
8. Add state-machine cases.
9. Add error-code, dependency, async, idempotency, and compensation cases.
10. Bind every case to coverage object IDs and coverage rule IDs.
11. Run reverse coverage validation from coverage object pool back to cases.
12. Output only the final **接口测试用例设计文档**.

## Coverage Object Pool

Extract all required coverage objects before writing cases.

| 来源产物 | 抽取对象 |
|---|---|
| 需求-接口-状态三向追踪矩阵 | 需求点、业务动作、接口、状态 |
| 字段-规则-断言映射表 | 字段、字段规则、业务断言 |
| 错误码-异常场景映射表 | 错误码、异常触发条件 |
| 状态迁移-触发入口映射表 | 初始状态、目标状态、触发接口、非法迁移 |
| 依赖失败-补偿场景映射表 | 下游依赖、失败类型、补偿规则 |
| 业务场景测试点文档 | 主流程、分支流程、角色差异、业务规则、状态限制、跨接口组合 |
| 接口测试点文档 | 接口、字段、鉴权、权限、幂等、响应结构、错误码、参数校验 |
| 接口结构化契约清单 | 契约上下文：method、path、headers、path/query/body、字段约束、响应结构、状态码、错误码、幂等、分页、文件、回调 |
| 状态机与数据一致性测试点文档 | 状态、状态迁移、非法迁移、终态保护、数据一致性断言 |
| 异常、补偿、依赖测试点文档 | 下游依赖、失败、超时、重试、补偿、回调、消息、异步事件 |
| 覆盖率矩阵 | 已覆盖对象、未覆盖对象、覆盖不足对象 |

Assign stable IDs:

- `REQ-001`: requirement
- `ACTION-001`: business action
- `API-001`: interface endpoint
- `FIELD-001`: request/response field
- `RULE-001`: business or field rule
- `ASSERT-001`: assertion
- `ERR-001`: error code
- `STATE-001`: state
- `TRANS-001`: state transition
- `DEP-001`: dependency system
- `COMP-001`: compensation rule
- `EVENT-001`: async event or callback

Each coverage object must record:

- 覆盖对象 ID
- 对象类型
- 对象名称
- 来源产物
- 来源位置
- 原文摘要
- 是否核心对象
- 映射关系
- 最低覆盖规则

When both mapping matrices and test point documents provide the same object, merge them by business identity and preserve all source evidence. Do not create duplicate coverage objects for the same requirement, interface, field, state, error code, dependency, or compensation rule.

If a test point document contains an object that is absent from all mapping matrices, include it in the coverage object pool and mark the source as that test point document. If the object is core but cannot be traced to any requirement, interface, state, or rule, mark it as `待补充` or `阻塞` according to impact.

Do not create new coverage objects from `接口结构化契约清单` alone. If the contract list contains an interface, field, error code, or rule that is absent from all coverage-object artifacts, mark the inconsistency as `待补充` or `阻塞` and require Stage 2 artifact repair instead of silently expanding the coverage object pool.

When `接口结构化契约清单` provides contract coverage rules (`契约覆盖规则`) for existing objects, include those rules in the relevant object's minimum coverage requirements for reverse validation. This changes the coverage calculation, not the case generation strategy.

## Minimum Coverage Rules

An object is covered only when its minimum rules are satisfied.

| 对象类型 | 最低覆盖规则 |
|---|---|
| 需求 | 至少 1 条正向场景；有分支或异常时必须覆盖分支和异常 |
| 接口 | 正常成功、鉴权失败、权限不足、参数异常、业务异常、响应结构 |
| 字段 | 合法值、必填缺失、类型错误、边界值、非法枚举、字段依赖 |
| 业务规则 | 满足规则、不满足规则、边界条件、组合规则 |
| 错误码 | 每个错误码至少 1 条可触发用例 |
| 状态 | 进入状态、离开状态、终态保护 |
| 状态迁移 | 合法迁移、非法迁移、重复触发、并发触发 |
| 依赖系统 | 成功、失败、超时、重试、补偿 |
| 异步事件 | 触发、消费成功、消费失败、重复消费、延迟消费 |
| 幂等 | 首次请求、重复请求、幂等窗口内、幂等窗口外 |

If a minimum rule cannot be satisfied because the source artifact lacks information, mark the coverage object as `阻塞`; do not invent a case.

## Case Generation Rules

### Interface Base Cases

For each `API-*`, generate at least:

- 正常成功用例
- 必填字段缺失用例
- 字段类型错误用例
- 字段边界值用例
- 枚举非法用例
- 鉴权失败用例
- 权限不足用例
- 幂等或重复提交用例
- 错误码触发用例
- 响应结构校验用例

### Business Rule Cases

From `REQ-*`, `ACTION-*`, `RULE-*`, and `ASSERT-*`, add:

- 主流程用例
- 分支流程用例
- 业务规则满足用例
- 业务规则不满足用例
- 跨接口组合用例
- 角色差异用例
- 状态限制用例

### State-Machine Cases

From `STATE-*` and `TRANS-*`, add:

- 每个状态进入用例
- 每个合法状态迁移用例
- 每个终态不可变更用例
- 每个非法迁移拒绝用例
- 重复触发同一状态迁移用例
- 并发触发状态迁移用例

### Error, Dependency, and Async Cases

From `ERR-*`, `DEP-*`, `COMP-*`, and `EVENT-*`, add:

- 每个错误码触发用例
- 下游成功用例
- 下游失败用例
- 下游超时用例
- 下游重试用例
- 补偿成功用例
- 补偿失败用例
- 回调失败或重复回调用例
- 消息重复或消息延迟用例

## Test Case Fields

Every test case must include:

| 字段 | 要求 |
|---|---|
| 用例 ID | 唯一编号，建议 `TC-API-001` |
| 用例标题 | 简短描述测试目标 |
| 覆盖对象 ID | 绑定需求、接口、字段、错误码、状态、依赖等 ID |
| 覆盖规则 ID | 绑定最低覆盖规则 |
| 优先级 | P0 / P1 / P2 |
| 用例类型 | 正常 / 异常 / 边界 / 状态 / 依赖 / 幂等 / 权限 |
| 前置条件 | 角色、数据、状态、配置 |
| 触发接口 | method + path |
| 测试步骤 | 接口调用顺序 |
| 输入设计 | 描述参数设计，不写死具体请求体值，除非来源文档明确给出 |
| 预期结果 | 业务结果、接口响应、状态变化、事件、补偿 |
| 断言点 | 响应断言、状态断言、数据断言、事件断言 |
| 来源依据 | 来源产物、来源位置、原文摘要 |
| 置信度 | 按 suite `../../references/case-confidence-contract.md` 输出分数、等级、区间、场景相关性、维度、原因码和证据引用 |
| 覆盖状态 | 已覆盖 / 待补充 / 覆盖不足 / 阻塞 |

Reject any test case that lacks coverage object ID, source evidence, or assertion points.
Do not infer confidence from priority or scenario frequency. Design scope may mark execution-only dimensions `not_applicable`, but every applicable score and cap must be evidence-backed.

## Reverse Coverage Validation

After cases are generated, validate from coverage object pool back to cases:

- Every PRD requirement has at least one case.
- Every API has at least one normal case and one abnormal case.
- Every key field has legal, illegal, and boundary cases.
- Every error code has a trigger case.
- Every state has entry, legal transition, and illegal transition cases.
- Every dependency has success, failure, timeout, retry, and compensation cases.
- Every generated case can trace back to source evidence.
- Interface method, path, parameter, and response details used in cases are consistent with `接口结构化契约清单` when that artifact is provided.
- Every contract coverage rule from `接口结构化契约清单` that binds to an existing `API-*`, `FIELD-*`, or `ERR-*` object is satisfied by at least one case or assertion.

Coverage states:

- `已覆盖`: Has cases and all minimum coverage rules are satisfied.
- `待补充`: Has partial design information but still needs additional cases or source details.
- `覆盖不足`: Has cases but misses one or more minimum rules.
- `未覆盖`: No case binds to the object.
- `阻塞`: Source artifacts lack enough information to design valid cases.

Do not declare 100% coverage if any core object is `待补充`, `覆盖不足`, `未覆盖`, or `阻塞`.

## Exit Gate

The design document can be marked `覆盖率 100%` only when all gates pass. These are hard gates:

| 门禁项 | 准出条件 |
|---|---|
| 契约一致性 | 用例中的 method、path、参数结构、响应断言与接口结构化契约清单一致；缺失时必须标记阻塞或引用等价 Stage 2 来源 |
| 契约规则覆盖 | 接口结构化契约清单中可绑定到现有 API/FIELD/ERR 对象的契约规则均被用例或断言覆盖 |
| 覆盖对象绑定 | 覆盖对象池中所有核心对象都有至少一条用例绑定 |
| 最低覆盖规则 | 每个核心对象都满足对应对象类型的最低覆盖规则 |
| 来源依据 | 每条用例都有来源产物、来源位置、原文摘要或等价来源说明 |
| 断言点 | 每条用例都有明确断言点，能判断通过或失败 |
| 置信度完整性 | 每条用例都有可重算的置信度对象；低置信度只阻塞 live 自动化，不得从设计覆盖分母静默删除 |
| 错误码覆盖 | 每个错误码都有至少一条可触发用例 |
| 状态迁移覆盖 | 每个状态迁移都有合法迁移和非法迁移覆盖 |
| 依赖覆盖 | 每个依赖都有成功、失败、超时、重试、补偿覆盖 |
| 未覆盖数量 | 覆盖率矩阵中核心对象 `未覆盖` 数量为 0 |
| 覆盖不足数量 | 覆盖率矩阵中核心对象 `覆盖不足` 和 `待补充` 数量为 0 |
| 核心阻塞数量 | 覆盖率矩阵中核心对象 `阻塞` 数量为 0 |

If any gate fails:

- Set conclusion to `覆盖不足` or `阻塞`.
- Do not write `覆盖率 100%`.
- List the failed gate, impacted coverage object IDs, missing cases, and required source information in the design document.
- Do not fabricate cases just to pass the gate.

## Required Output Format

Output one Chinese Markdown document:

```markdown
# 接口测试用例设计文档

## 1. 生成结论
- 结论：覆盖率 100% / 覆盖不足 / 阻塞
- 是否可声明接口测试用例设计覆盖率 100%：是 / 否
- 依据：简述覆盖对象池、最低覆盖规则、反向验收结果

## 2. 输入依据
| 产物 | 是否提供 | 用途 | 备注 |
|---|---|---|---|

## 3. 覆盖对象池摘要
| 覆盖对象 ID | 对象类型 | 对象名称 | 来源产物 | 来源位置 | 是否核心 | 最低覆盖规则 |
|---|---|---|---|---|---|---|

## 4. 接口测试用例设计
| 用例 ID | 用例标题 | 覆盖对象 ID | 覆盖规则 ID | 优先级 | 用例类型 | 前置条件 | 触发接口 | 测试步骤 | 输入设计 | 预期结果 | 断言点 | 来源依据 | 覆盖状态 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

## 5. 覆盖率反向验收矩阵
| 覆盖对象 ID | 对象类型 | 最低覆盖规则 | 已覆盖用例 ID | 覆盖状态 | 缺口 | 处理建议 |
|---|---|---|---|---|---|---|

## 6. 准出门禁检查
| 门禁项 | 准出条件 | 检查结果 | 未通过原因 | 影响对象 ID |
|---|---|---|---|---|

## 7. 阻塞与覆盖不足项
| 编号 | 覆盖对象 ID | 类型 | 问题 | 影响 | 需要补充的信息 |
|---|---|---|---|---|---|

## 8. 剩余风险
| 编号 | 风险 | 影响 | 建议 |
|---|---|---|---|
```

## Final Quality Gate

Before finalizing the document, check:

- There is exactly one output document.
- Every test case has coverage object IDs.
- Every test case has assertion points.
- Every test case has source evidence.
- Coverage reverse validation has no core `未覆盖`, `待补充`, `覆盖不足`, or `阻塞` object before claiming 100%.
- All exit gates pass before claiming 100%.
- Chinese text is UTF-8 and has no garbling.
