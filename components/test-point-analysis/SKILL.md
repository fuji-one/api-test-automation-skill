---
name: test-point-analysis
description: Generate standardized Markdown test point analysis artifacts after document precheck passes and before interface test case design, including interface structured contract lists. Use when Codex needs 测试点分析, 测试点产物生成, 需求接口状态追踪矩阵, 字段规则断言映射, 错误码异常场景映射, 状态迁移触发入口映射, 依赖补偿场景映射, 接口结构化契约清单, or coverage-object source artifacts that enable downstream interface test case design to claim 100% traceable coverage.
---

# Test Point Analysis

## Goal

Generate the standardized Markdown (`.md`) test point analysis artifacts required by `$interface-testcase-design`.

This skill is the middle handoff between:

```text
$doc-precheck-coverage
-> $test-point-analysis
-> $interface-testcase-design
```

Do not change the responsibilities of the other two skills:

- `$doc-precheck-coverage` validates whether source documents are ready and outputs one consolidated precheck report.
- `$test-point-analysis` generates coverage-object source artifacts and test point analysis artifacts.
- `$interface-testcase-design` consumes those artifacts to generate one interface test case design document.

## Required Inputs

Require Markdown (`.md`) sources:

- PRD document
- API document
- System-analysis document
- 文档前置校验报告 from `$doc-precheck-coverage`

The precheck report is used only as readiness and risk context. Do not use it as the primary source for coverage objects. Extract coverage objects from PRD, API, and system-analysis documents, then validate them against precheck conclusions and risks.

If the precheck report conclusion is `阻塞`, do not generate full test point artifacts. Output only a Markdown blocker report named as a test point analysis result, explaining which source documents must be fixed first.

## Output Scope

All outputs must be Markdown (`.md`). Generate only the downstream artifacts required by interface test case design:

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
- 剩余风险清单, only when risks remain

Do not generate implementation scripts, executable test cases, mock files, request fixtures, or automation code.

The `接口结构化契约清单` is a contract context artifact for downstream design and later executable-case generation. It must not change the existing coverage object model or test point generation strategy. It may refine the coverage denominator by adding contract coverage rules that bind to existing `API-*`, `FIELD-*`, and `ERR-*` coverage objects. Coverage is still validated through coverage objects, test points, contract rules, and the coverage matrix.

## Core Coverage Principle

Every explicit and testable item from PRD, API, and system analysis must become a traceable coverage object or be listed as a blocker/risk.

Coverage can be claimed only when:

- Every coverage object has a unique stable ID.
- Every coverage object has source document, source location, and source summary.
- Every core coverage object maps to at least one downstream test point.
- Every core field, error code, state transition, dependency, compensation rule, and async event has a minimum coverage rule.
- The coverage matrix has 0 core `未覆盖`, 0 core `待补充`, 0 core `覆盖不足`, and 0 core `阻塞` items before claiming `测试点覆盖率 100%`.

## Workflow

1. Verify the precheck conclusion.
2. Extract coverage objects from PRD, API, and system-analysis documents.
3. Assign stable IDs and preserve existing IDs when already present.
4. Build the five traceability matrices.
5. Generate four test point documents from the matrices.
6. Generate the interface structured contract list from API source evidence.
7. Build the coverage matrix.
8. Validate coverage from coverage objects back to test points.
9. Output only Markdown test point analysis artifacts.

## Coverage Object IDs

Use these ID prefixes:

| 对象类型 | ID 前缀 |
|---|---|
| 需求 | `REQ-001` |
| 业务动作 | `ACTION-001` |
| 接口 | `API-001` |
| 字段 | `FIELD-001` |
| 业务规则 | `RULE-001` |
| 断言 | `ASSERT-001` |
| 错误码 | `ERR-001` |
| 状态 | `STATE-001` |
| 状态迁移 | `TRANS-001` |
| 依赖系统 | `DEP-001` |
| 补偿规则 | `COMP-001` |
| 异步事件 | `EVENT-001` |

ID rules:

- Preserve existing source IDs when stable and unique.
- Generate missing IDs deterministically by object type and source order.
- Merge duplicate objects by business identity, not by text similarity alone.
- Keep all source evidence when one object appears in multiple documents.
- Never create two IDs for the same requirement, interface, field, state, error code, dependency, or compensation rule.

Every coverage object must include:

- 覆盖对象 ID
- 对象类型
- 对象名称
- 来源文档
- 来源位置
- 原文摘要
- 是否核心对象
- 最低覆盖规则
- 映射关系
- 覆盖状态

## Minimum Coverage Rules

Use these rules when building coverage matrix and test point documents:

| 对象类型 | 最低覆盖规则 |
|---|---|
| 需求 | 主流程、分支流程、失败流程；有角色差异时覆盖角色差异 |
| 接口 | 成功、鉴权失败、权限不足、参数异常、业务异常、响应结构 |
| 字段 | 合法值、缺失、类型错误、边界、非法枚举、字段依赖 |
| 业务规则 | 满足规则、不满足规则、边界条件、组合规则 |
| 错误码 | 每个错误码至少一个触发场景 |
| 状态 | 进入状态、离开状态、终态保护 |
| 状态迁移 | 合法迁移、非法迁移、重复触发、并发触发 |
| 依赖系统 | 成功、失败、超时、重试、补偿 |
| 补偿规则 | 补偿触发、补偿成功、补偿失败、人工介入 |
| 异步事件 | 触发、消费成功、消费失败、重复消费、延迟消费 |
| 幂等 | 首次请求、重复请求、幂等窗口内、幂等窗口外 |

If the source documents lack information needed for a minimum rule, mark the coverage object as `阻塞` or `覆盖不足`; do not invent a test point.

## Artifact Schemas

### 需求-接口-状态三向追踪矩阵

```markdown
# 需求-接口-状态三向追踪矩阵

| 需求ID | 业务动作ID | 接口ID | 状态ID | 状态迁移ID | 映射关系 | 来源文档 | 来源位置 | 原文摘要 | 是否核心 | 覆盖状态 | 缺口 |
|---|---|---|---|---|---|---|---|---|---|---|---|
```

### 字段-规则-断言映射表

```markdown
# 字段-规则-断言映射表

| 字段ID | 接口ID | 字段名 | 规则ID | 断言ID | 字段约束 | 映射关系 | 来源文档 | 来源位置 | 原文摘要 | 是否核心 | 覆盖状态 | 缺口 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
```

### 错误码-异常场景映射表

```markdown
# 错误码-异常场景映射表

| 错误码ID | 接口ID | 错误码 | 异常触发条件 | 预期业务结果 | 映射关系 | 来源文档 | 来源位置 | 原文摘要 | 是否核心 | 覆盖状态 | 缺口 |
|---|---|---|---|---|---|---|---|---|---|---|---|
```

### 状态迁移-触发入口映射表

```markdown
# 状态迁移-触发入口映射表

| 状态迁移ID | 初始状态ID | 目标状态ID | 触发入口 | 触发接口ID | 是否合法迁移 | 映射关系 | 来源文档 | 来源位置 | 原文摘要 | 是否核心 | 覆盖状态 | 缺口 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
```

### 依赖失败-补偿场景映射表

```markdown
# 依赖失败-补偿场景映射表

| 依赖ID | 依赖类型 | 触发接口ID | 失败类型 | 重试规则 | 补偿规则ID | 预期状态 | 映射关系 | 来源文档 | 来源位置 | 原文摘要 | 是否核心 | 覆盖状态 | 缺口 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
```

### 业务场景测试点文档

```markdown
# 业务场景测试点文档

| 测试点ID | 测试点标题 | 覆盖对象ID | 场景类型 | 角色 | 前置条件 | 触发动作 | 预期业务结果 | 断言点 | 来源依据 | 优先级 | 覆盖状态 |
|---|---|---|---|---|---|---|---|---|---|---|---|
```

### 接口测试点文档

```markdown
# 接口测试点文档

| 测试点ID | 测试点标题 | 接口ID | 覆盖对象ID | 测试点类型 | 参数设计 | 预期响应 | 断言点 | 来源依据 | 优先级 | 覆盖状态 |
|---|---|---|---|---|---|---|---|---|---|---|
```

### 接口结构化契约清单

```markdown
# 接口结构化契约清单

| 接口ID | 接口名称 | 模块 | Method | Path | 鉴权方式 | 请求头 | Path参数 | Query参数 | Body结构 | 字段约束 | 字段依赖 | 成功响应结构 | 失败响应结构 | HTTP状态码 | 业务错误码 | 幂等规则 | 分页排序 | 文件/二进制规则 | 回调规则 | 来源文档 | 来源位置 | 原文摘要 | 契约完整性 | 缺口 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
```

Rules:

- Extract only contract facts explicitly present in the API document or cross-confirmed by source documents.
- Keep `接口ID` consistent with `API-*` IDs in the traceability matrices and coverage matrix.
- Use compact structured text in cells, such as `name:type|required|constraint`, without inventing missing schema details.
- Mark `契约完整性` as `完整`, `部分缺失`, or `阻塞缺失`.
- If core contract details required for valid case design are missing, record them in `缺口` and reflect the impact in the coverage matrix or risk list. Do not invent request or response fields.
- This artifact supports downstream parameter and response design. It does not add new coverage objects by itself unless the same interface, field, error code, or rule is already represented in coverage-object artifacts.
- Contract coverage rules must bind back to existing coverage objects. For example, `API-001` may carry method/path/auth/response contract rules, `FIELD-001` may carry type/required/enum/boundary/dependency rules, and `ERR-001` may carry business error-code trigger and response rules.
- If a contract fact cannot bind to any existing coverage object, mark it as `待补充` or `阻塞` and require artifact repair. Do not silently expand the coverage object pool.

Contract coverage rule examples:

| 绑定对象类型 | 契约覆盖规则 |
|---|---|
| 接口 `API-*` | Method、Path、鉴权方式、请求头、成功响应结构、失败响应结构、HTTP状态码、幂等、分页排序、文件/二进制、回调 |
| 字段 `FIELD-*` | 参数位置、字段类型、必填、长度、精度、格式、枚举、默认值、边界、字段依赖 |
| 错误码 `ERR-*` | 错误码、错误信息、触发条件、HTTP状态码与业务错误码对应关系 |

### 状态机与数据一致性测试点文档

```markdown
# 状态机与数据一致性测试点文档

| 测试点ID | 测试点标题 | 状态ID | 状态迁移ID | 数据对象ID | 测试点类型 | 前置状态 | 触发入口 | 预期状态/数据 | 断言点 | 来源依据 | 优先级 | 覆盖状态 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
```

### 异常、补偿、依赖测试点文档

```markdown
# 异常、补偿、依赖测试点文档

| 测试点ID | 测试点标题 | 依赖ID | 错误码ID | 补偿规则ID | 异步事件ID | 测试点类型 | 失败/异常触发 | 预期结果 | 断言点 | 来源依据 | 优先级 | 覆盖状态 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
```

### 覆盖率矩阵

```markdown
# 覆盖率矩阵

| 覆盖对象ID | 对象类型 | 对象名称 | 映射关系 | 最低覆盖规则 | 契约覆盖规则 | 已覆盖测试点ID | 覆盖状态 | 是否核心 | 缺口 | 处理建议 |
|---|---|---|---|---|---|---|---|---|---|---|
```

### 剩余风险清单

```markdown
# 剩余风险清单

| 风险ID | 来源文档 | 来源位置 | 风险描述 | 影响对象ID | 对覆盖率影响 | 建议处理 |
|---|---|---|---|---|---|---|
```

## Coverage Validation

Before claiming `测试点覆盖率 100%`, validate:

- Every core in-scope interface requirement maps to API and state. If a core requirement cannot map to API/state, mark it as `阻塞` unless it is explicitly classified as outside the interface-test scope with source evidence.
- Every core API has interface test points for success, auth, permission, parameter, business exception, and response structure.
- Every core field has legal, missing, type, boundary, enum, or dependency test points according to its constraints.
- Every core error code has at least one trigger test point.
- Every core state transition has legal and illegal transition test points.
- Every core dependency has success, failure, timeout, retry, and compensation test points.
- Every core async event has trigger, success, failure, duplicate, and delay test points when documented.
- Every test point has source evidence and assertion points.
- Contract coverage rules from `接口结构化契约清单` are bound to existing `API-*`, `FIELD-*`, or `ERR-*` objects and reflected in the coverage matrix.
- Coverage matrix has 0 core `未覆盖`, 0 core `待补充`, 0 core `覆盖不足`, and 0 core `阻塞`.

Coverage states:

- `已覆盖`: Minimum coverage rules are satisfied.
- `待补充`: Contract facts, mapping relationships, or source details exist but are not complete enough to validate coverage.
- `覆盖不足`: Some minimum rules are missing.
- `未覆盖`: No test point covers the object.
- `阻塞`: Source documents lack enough information to design valid test points.
- `有风险`: Non-core issue remains but is recorded in the risk list.

## Final Quality Gate

Before finalizing:

- Output only Markdown artifacts listed in Output Scope.
- Ensure every artifact uses the schema defined above.
- Ensure every row has stable IDs and source evidence.
- Ensure the interface structured contract list uses the same `API-*` IDs as the other Stage 2 artifacts.
- Ensure contract coverage rules are reflected as coverage requirements for existing API, field, and error-code objects, without creating duplicate coverage objects.
- Ensure no duplicate coverage objects exist.
- Ensure no core object is missing from coverage matrix.
- Do not claim 100% if any core object is `未覆盖`, `待补充`, `覆盖不足`, or `阻塞`.
- Check Chinese text for garbling.
