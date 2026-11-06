---
name: interface-testcase-generation
description: Generate interface test case lists from pre-doc-analysis-pipeline deliverables after strict quality gating of the interface test case design document and interface structured contract list. Use when Codex needs 承接接口测试用例设计文档、接口结构化契约清单、测试点覆盖材料，通过总agent和最多五个子agent按不同测试方法生成接口测试用例，并保证测试点、主要测试流程、契约规则和状态码来源可追溯且覆盖率100%。
---

# Interface Testcase Generation

## Goal

Generate interface test cases from the approved outputs of `$pre-doc-analysis-pipeline`.

This skill consumes upstream design and contract artifacts. It does not replace `$pre-doc-analysis-pipeline`, `$test-point-analysis`, or `$interface-testcase-design`. It turns already-designed coverage objects and structured interface contracts into concrete interface test case lists.

The workflow is gated:

```text
接口测试用例设计文档 + 接口结构化契约清单
-> 质量门禁
-> 总agent规划测试方法
-> 最多五个子agent生成候选用例
-> 总agent合并、去重、反向覆盖校验
-> 接口测试用例清单
```

## Required Inputs

Require these two Markdown artifacts:

| 输入 | 默认文件名 | 用途 |
|---|---|---|
| 接口测试用例设计文档 | `01_接口测试用例设计文档.md` | 提供测试点、主要流程、状态迁移、异常流程、依赖补偿、覆盖对象和设计依据 |
| 接口结构化契约清单 | `02_接口结构化契约清单.md` | 提供接口 method、path、鉴权、请求参数、响应结构、字段规则、状态码、错误码和依赖约束 |

Optional but useful:

| 输入 | 默认文件名 | 用途 |
|---|---|---|
| skill执行报告 | `03_skill执行报告.md` | 复核上游阶段结论、覆盖率口径、风险和阻塞项 |

Do not generate test cases from only one required document. If either required document is missing, unreadable, or cannot be mapped to the other, stop at the quality gate.

## Final Deliverable

Default to one human-readable Markdown deliverable and one machine-readable case list:

| 文件名 | 生成条件 | 内容 |
|---|---|---|
| `04_接口测试用例清单.md` | Always, if writing files is requested or appropriate | 质检结论、生成分工、接口测试用例展示、覆盖矩阵、准出结论、待确认项 |
| `case_list.yaml` | Always, if writing files is requested or appropriate | 设计级用例主数据、覆盖继承字段、契约引用、状态码、断言点和优先级 |

When writing files, also write two machine-readable sidecars beside `case_list.yaml` and `04_接口测试用例清单.md`:

| 文件名 | 内容 | 用途 |
|---|---|---|
| `stage_status.yaml` | 阶段状态、准出结论、输入输出路径、阻塞项 | 供 orchestrator 判断是否可进入执行级用例阶段 |
| `coverage_matrix.yaml` | 测试点、主要流程、契约规则、状态码和 P0/P1 到用例的映射 | 供 orchestrator 精确对账 100% 覆盖 |

If the quality gate fails, `04_接口测试用例清单.md` must contain only the quality report, blockers, impact, and repair suggestions. It must not contain generated test cases.
If the quality gate fails, `case_list.yaml` must still be written with `status: blocked`, `cases: []`, parsed coverage gaps, and repair-oriented blockers; it must not contain executable or passing cases.
If the quality gate fails, `stage_status.yaml` must still be written with `status: "blocked"` when file output is requested; `coverage_matrix.yaml` may contain only parsed inputs and missing mappings, but must not mark coverage as passed.

If the user requests inline output instead of files, keep the same sections and deliver them in the response.

## Non-Goals

- Do not generate executable automation code, request fixtures, mock files, assertions, scripts, or runner configuration.
- Do not generate performance, pressure, UI, security scanning, compatibility, or full end-to-end chain tests unless the input documents explicitly require them as interface coverage objects.
- Do not invent request bodies, response bodies, state codes, error codes, database fields, user states, dependencies, or business states.
- Do not create extra deliverable files unless required by this skill contract (`case_list.yaml`, `stage_status.yaml`, `coverage_matrix.yaml`) or explicitly requested by the user.

## Pipeline Rules

- All user-facing generated content must be Markdown. The two structured sidecars are YAML validation artifacts.
- The target is 100% coverage for explicit test points and main interface flows.
- Do not claim 100% coverage unless every gate in this skill passes.
- When 100% cannot be reached, report the real coverage percentage and the exact blockers or gaps.
- Use the interface structured contract list as the only source of allowed status codes and error codes.
- Use the interface test case design document as the primary source of test points and main flows.
- Use the skill execution report only as audit context. Do not let it create new test points that are absent from the design document.
- Preserve existing upstream IDs when the design document provides coverage object IDs, test point IDs, interface IDs, or rule IDs.

## Stage 1: Input Indexing

Build a working index before quality review:

| 索引 | 来源 | 必须记录 |
|---|---|---|
| 接口索引 | 契约清单 | interface ID if present, method, path, name, auth, dependencies |
| 字段规则索引 | 契约清单 | request fields, response fields, required, type, enum, boundary, format, conditional rules |
| 状态码索引 | 契约清单 | HTTP status codes, business status codes, error codes, meaning, applicable interface |
| 测试点索引 | 用例设计文档 | test point ID if present, scenario, expected assertion, priority, source coverage object |
| 主要流程索引 | 用例设计文档 | main flow step, state transition, dependency, compensation, expected result |
| 追溯索引 | 两个文档 | mapping between test points, interfaces, fields, status codes, and contract rules |

If stable IDs are missing but the relationship is clear, create temporary local IDs for the deliverable and mark them as `临时追溯ID`. Do not present temporary IDs as upstream source IDs.

## Stage 2: Quality Gate

Quality review must pass before any test case generation starts.

Gate checks:

| 门禁 | 通过标准 |
|---|---|
| 文档完整性 | Two required documents exist and are readable |
| 上游准出 | If `03_skill执行报告.md` exists, upstream Stage 3 is not `阻塞` and does not forbid downstream use |
| 接口可追溯 | Each target test point can map to at least one interface contract entry |
| 契约完整性 | Each target interface has method, path, request or no-request rule, response or no-content rule, and defined status code or error code |
| 状态码来源 | Every status code and error code candidate exists in the contract list or explicit API source |
| 字段规则闭环 | Required, type, enum, boundary, format, conditional required, mutual exclusion, and combination rules can map to request or response schema fields |
| 主要流程完整性 | Main flows, core state transitions, key exceptions, and dependency or compensation scenarios from the design document are identifiable |
| 前置条件可表达 | Interface dependency, database information acquisition, user state, and business state can be expressed from the documents or marked as blocking |
| 冲突检查 | Method, path, field name, field type, status code, error code, and business state have no unexplained conflict across the two documents |

Blocking conditions:

- Missing either required document.
- A target interface lacks all defined status codes and error codes.
- A main flow or explicit P0/P1 test point cannot be mapped to any interface.
- The design document and contract list conflict on method, path, field type, or status code and the conflict affects expected test behavior.
- Required preconditions depend on undocumented user state, database information, or upstream interface data.

Non-blocking reminders may be reported, but they cannot be used to relax coverage.

Quality report format:

```markdown
## 质检结论
- 结果：通过/不通过
- 是否进入生成阶段：是/否
- 判断依据：...

## 阻塞项
| 编号 | 问题 | 涉及接口/测试点 | 影响 | 修正建议 |

## 非阻塞提醒
| 编号 | 提醒 | 涉及接口/测试点 | 建议 |

## 可进入生成阶段的依据
- ...
```

If the result is `不通过`, stop and output only the quality report plus `待确认项`.

## Stage 3: Generation Planning

After the quality gate passes, the total agent must create a generation plan.

Rules:

- Use no more than five subagents.
- Assign each subagent exactly one test method.
- Choose only useful methods for the provided documents. Do not create low-value subagents just to reach five.
- If real subagent tools are unavailable or not allowed in the current session, keep the same subagent roles as internal work sections and do not claim that external agents were launched.

Recommended test methods:

| 测试方法 | 适用范围 | 重点覆盖 |
|---|---|---|
| 正向流程测试 | Main success path and core business closure | P0 main flows, required valid inputs, success status codes |
| 字段规则测试 | Request and response field constraints | Required, type, enum, boundary, format, conditional required, mutually exclusive fields |
| 异常与错误码测试 | Explicit abnormal scenarios and contract errors | Defined error codes, invalid actions, unauthorized or forbidden states |
| 状态迁移测试 | Stateful interfaces and repeated operations | State preconditions, allowed transitions, forbidden transitions, idempotency |
| 依赖与补偿测试 | Interface dependency, external dependency, data consistency | Dependency acquisition, dependency failure, compensation, rollback, consistency |

Generation plan format:

```markdown
## 生成分工
| 子Agent | 测试方法 | 覆盖范围 | 输入依据 | 预期输出 |
```

## Stage 4: Case Generation

Each subagent must generate candidate cases only from its assigned method and source evidence.

Every final test case must include these seven business fields plus the confidence fields defined by the suite confidence contract:

| 字段 | 要求 |
|---|---|
| 用例名称 | Chinese name in `场景+对象+动作` or `对象+条件+动作` form |
| 用例类型 | One selected test method name |
| 前置条件 | Necessary state before execution, including applicable interface dependency, database information acquisition, user state, and business state |
| 入参 | JSON Schema, not a raw JSON example |
| 出参 | JSON Schema, not a raw JSON example |
| 状态码 | Only status code or error code defined by the contract |
| 用例优先级 | `P0`, `P1`, or `P2` |
| 置信度 | `confidence_score`、`confidence_level`、`confidence_band`、`confidence_scope`、`scenario_relevance`、五维得分、原因码、硬上限原因和证据引用 |

For traceability, also keep these audit fields in the coverage matrix or an internal column:

| 审计字段 | 用途 |
|---|---|
| 追溯接口 | method and path or interface ID |
| 追溯测试点 | test point ID or temporary local ID |
| 追溯契约规则 | field rule, status code, error code, state rule, or dependency rule |
| 来源依据 | source document and section summary |

Case object format:

```yaml
用例名称: ""
用例类型: ""
前置条件: ""
入参:
  type: object
  properties: {}
  required: []
出参:
  type: object
  properties: {}
  required: []
状态码: ""
用例优先级: "P0"
confidence_score: 0.85
confidence_level: medium
confidence_band: scenario_confirmed
confidence_scope: design
scenario_relevance: reachable_business_branch
confidence_dimensions:
  contract: 1.0
  request_materialization: 0.8
  scenario_precondition: 0.8
  business_assertion: 0.8
  runtime_repeatability: not_applicable
confidence_reason_codes: [SOURCE_CONTRACT_CONFIRMED]
confidence_cap_reasons: [RUNTIME_NOT_VERIFIED]
confidence_evidence_refs: ["02_接口结构化契约清单.md#API-001"]
```

Calculate and validate this object with `../../references/case-confidence-contract.md`. Priority, positive/negative type, and scenario popularity must not directly change the score.

JSON Schema rules:

- Use `type`, `properties`, and `required` for object schemas.
- Preserve field names and types from the contract.
- Use `enum`, `minimum`, `maximum`, `minLength`, `maxLength`, `pattern`, or `format` only when the contract defines them.
- Use an empty object schema only when the contract explicitly has no request body or no response body.
- Do not put sample values in place of schema definitions.

Priority rules:

| 优先级 | 适用场景 |
|---|---|
| P0 | Main flow, core state transition, key exception, authorization, funds, data consistency, or mandatory dependency |
| P1 | Important field rule, common abnormal flow, non-core state constraint, secondary dependency |
| P2 | Low-risk boundary, uncommon optional field, low-impact variation |

## Stage 5: Merge And De-Duplicate

The total agent must merge candidate cases and remove duplicates.

Duplicate criteria:

- Same interface.
- Same precondition.
- Same input condition or equivalent schema rule.
- Same expected status code.
- Same covered test point or contract rule.

Do not delete cases that cover different status codes, different state transitions, different dependency outcomes, or different field rules.

When two cases overlap, keep the one with clearer traceability, stricter contract alignment, and higher priority.

## Stage 6: Coverage Validation

Run reverse validation after merging.

Coverage formulas:

| 覆盖率 | 公式 | 准出要求 |
|---|---|---|
| 测试点覆盖率 | 已覆盖显式测试点数 / 显式测试点总数 * 100% | 100% |
| 主要流程覆盖率 | 已覆盖主要流程数 / 主要流程总数 * 100% | 100% |
| 契约规则覆盖率 | 已覆盖可执行契约规则数 / 可执行契约规则总数 * 100% | 100% |
| 状态码覆盖率 | 已覆盖契约状态码和错误码数 / 契约状态码和错误码总数 * 100% | 100% |
| P0/P1覆盖率 | 已覆盖P0/P1对象数 / P0/P1对象总数 * 100% | 100% |

Validation checks:

- Every explicit test point has at least one final case.
- Every main flow has at least one final case.
- Every defined status code or error code used by target interfaces is covered by at least one positive or negative case.
- Every generated status code exists in the contract.
- Every request and response is JSON Schema.
- Every case has a concrete precondition.
- Every P0 and P1 case has source evidence.
- No case is counted toward coverage without a traceable test point or contract rule.

If any coverage metric is below 100%, final conclusion must be `覆盖不足` or `阻塞`, never `通过`.

## Structured Case List

`case_list.yaml` is the authoritative design-level case source for downstream handoff. Markdown is human-readable display only. Sidecars and handoff outputs must be derived from `case_list.yaml` and coverage validation data. Do not create IDs in sidecars that are absent from `case_list.yaml`.

`case_list.yaml` minimum fields:

```yaml
schema_version: 1
stage: interface_testcase_generation
status: passed | blocked | coverage_insufficient
quality_gate:
  result: passed | blocked | coverage_insufficient
  generation_allowed: true | false
cases:
  - case_id: "TC-API-001"
    design_case_id: "DC-001"
    name: "..."
    case_type: main_flow | branch_flow | exception | boundary | state_transition | dependency_failure
    priority: P0 | P1 | P2
    method: POST
    path: "/..."
    trace_interface: "POST /..."
    test_point_ids: ["TP-001"]
    coverage_object_ids: ["OBJ-001"]
    coverage_rule_ids: ["RULE-001"]
    status_codes: ["200"]
    preconditions: ["..."]
    request_contract_refs: ["02_接口结构化契约清单.md#..."]
    response_contract_refs: ["02_接口结构化契约清单.md#..."]
    assertion_points: ["..."]
    source_refs: ["01_接口测试用例设计文档.md#..."]
    confidence_score: 0.85
    confidence_level: medium
    confidence_band: scenario_confirmed
    confidence_scope: design
    scenario_relevance: reachable_business_branch
    confidence_dimensions:
      contract: 1.0
      request_materialization: 0.8
      scenario_precondition: 0.8
      business_assertion: 0.8
      runtime_repeatability: not_applicable
    confidence_reason_codes: [SOURCE_CONTRACT_CONFIRMED, RUNTIME_NOT_VERIFIED]
    confidence_cap_reasons: [RUNTIME_NOT_VERIFIED]
    confidence_evidence_refs: ["02_接口结构化契约清单.md#API-001"]
coverage_summary:
  test_point_total: 0
  test_point_covered: 0
  main_flow_total: 0
  main_flow_covered: 0
  contract_rule_total: 0
  contract_rule_covered: 0
  status_code_total: 0
  status_code_covered: 0
  p0_p1_total: 0
  p0_p1_covered: 0
  missing_test_point_ids: []
  missing_main_flow_ids: []
  missing_contract_rule_ids: []
  missing_status_codes: []
  missing_p0_p1_ids: []
case_mappings:
  - case_id: "TC-API-001"
    test_point_ids: ["TP-001"]
    main_flow_ids: ["FLOW-001"]
    contract_rule_ids: ["RULE-001"]
    status_codes: ["200"]
    priority: P0
    trace_interface: "POST /orders"
blocking_issues: []
```

For `status=passed`, `cases` must be non-empty and every case must include `case_id`, `design_case_id`, `test_point_ids`, `coverage_object_ids`, `coverage_rule_ids`, `method`, `path`, `status_codes`, `priority`, `assertion_points`, and the complete confidence object. Confidence is recalculable metadata and does not replace any listed field or coverage rule.

## Structured Sidecars

`stage_status.yaml` minimum fields:

```yaml
schema_version: 1
stage: interface_testcase_generation
status: passed | blocked | coverage_insufficient
next_stage_allowed: true | false
input_paths:
  - path: "01_接口测试用例设计文档.md"
    role: design_doc
  - path: "02_接口结构化契约清单.md"
    role: contract_list
output_paths:
  - path: "case_list.yaml"
    role: case_list_yaml
  - path: "04_接口测试用例清单.md"
    role: markdown_report
gate_checks:
  - check_id: quality_gate
    status: passed | blocked | failed
    evidence_refs: ["04_接口测试用例清单.md#质检结论"]
blocking_issues: []
```

Allowed `status` values are `passed`, `blocked`, and `coverage_insufficient`; write exactly one value, never the enum expression itself.

`coverage_matrix.yaml` minimum fields:

```yaml
schema_version: 1
stage: interface_testcase_generation
coverage_summary:
  denominator_scope: "test points, main flows, contract rules, status codes, and P0/P1 cases"
  coverage_rate: 100
coverage_items:
  - coverage_id: "TP-001"
    coverage_type: test_point
    status: covered | missing | conflict | blocked
    evidence_refs: ["case_list.yaml#TC-API-001"]
missing_items: []
upstream_downstream_mappings:
  - upstream_id: "TP-001"
    downstream_ids: ["TC-API-001"]
    mapping_status: mapped | missing | conflict | blocked
test_point_total: 0
test_point_covered: 0
main_flow_total: 0
main_flow_covered: 0
contract_rule_total: 0
contract_rule_covered: 0
status_code_total: 0
status_code_covered: 0
p0_p1_total: 0
p0_p1_covered: 0
missing_test_point_ids: []
missing_main_flow_ids: []
missing_contract_rule_ids: []
missing_status_codes: []
missing_p0_p1_ids: []
case_mappings:
  - case_id: "TC-API-001"
    test_point_ids: ["TP-001"]
    main_flow_ids: ["FLOW-001"]
    contract_rule_ids: ["RULE-001"]
    status_codes: ["200"]
    priority: P0
    trace_interface: "POST /orders"
```

Sidecar gate: `case_list.yaml.status=passed`, `stage_status.yaml.status=passed`, `next_stage_allowed=true`, every `*_total` equals its matching `*_covered`, and all missing ID lists are empty are required before the case list may be adapted for execution-level generation.

## Final Output Structure

Use this structure for `04_接口测试用例清单.md` or inline output:

```markdown
# 接口测试用例清单

## 输入文档清单
| 类型 | 文件名 | 来源路径 | 使用状态 |

## 质检结论

## 生成分工

## 接口测试用例
| 用例名称 | 用例类型 | 前置条件 | 入参 | 出参 | 状态码 | 用例优先级 |

## 覆盖矩阵
| 覆盖对象 | 来源文档 | 对应用例 | 覆盖规则 | 覆盖结果 | 备注 |

## 覆盖率准出摘要
| 覆盖率 | 分子 | 分母 | 结果 | 是否达标 |

## 待确认项
| 编号 | 待确认内容 | 影响范围 | 建议确认对象 |

## 交付结论
- 结论：通过/覆盖不足/阻塞
- 是否允许声明测试点和主要测试流程100%覆盖：是/否
- 不能声明100%时的原因：...
```

## Exit Rules

Use one of these conclusions:

| 结论 | 条件 |
|---|---|
| 通过 | Quality gate passes, all required coverage metrics are 100%, no blocking item remains |
| 覆盖不足 | Quality gate passes and cases are generated, but any coverage metric is below 100% |
| 阻塞 | Quality gate fails, required source evidence is missing, or defined status codes and preconditions cannot be trusted |

Never use `通过` when a blocker, unmapped P0/P1 test point, undefined status code, non-schema input/output, or untraceable generated case remains.
