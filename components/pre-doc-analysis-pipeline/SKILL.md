---
name: pre-doc-analysis-pipeline
description: Orchestrate the full pre-document analysis pipeline for Markdown PRD, API, and system-analysis documents by sequencing document precheck, standardized test point analysis, business scenario mapping, interface structured contracts, interface test case design, and skill execution reporting. Use when Codex needs 前置文档解析分析, PRD/API/系统分析整体解析, 测试点分析流水线, 业务场景链路映射, 接口结构化契约清单, 接口测试用例设计覆盖率100%, skill执行报告, or an end-to-end gated workflow that uses $doc-precheck-coverage, $test-point-analysis, and $interface-testcase-design while producing three final primary Markdown deliverables plus machine-readable sidecars and auxiliary handoff views.
---

# Pre Doc Analysis Pipeline

## Goal

Run the full gated Markdown document analysis pipeline:

```text
PRD/API/系统分析
-> $doc-precheck-coverage
-> $test-point-analysis
-> $interface-testcase-design
```

This skill is an orchestrator. Do not replace or rewrite the three component skills. Preserve their existing responsibilities and gates.

## Component Skills

Use these skills in order:

| 阶段 | Skill | 职责 | 产出 |
|---|---|---|---|
| 1 | `$doc-precheck-coverage` | 校验 PRD、API、系统分析是否具备后续分析条件 | 写入 `03_skill执行报告.md` 的前置校验章节 |
| 2 | `$test-point-analysis` | 生成标准化测试点分析、覆盖对象 ID、覆盖率矩阵、业务场景映射和接口契约 | 写入 `03_skill执行报告.md` 的二阶段报告，单独输出 `02_接口结构化契约清单.md`，并输出业务场景映射 handoff 产物 |
| 3 | `$interface-testcase-design` | 基于测试点分析产物生成接口测试用例设计并反向验收覆盖率 | 单独输出 `01_接口测试用例设计文档.md` |

## Required Source Inputs

Require Markdown (`.md`) source documents:

- PRD document
- API document
- System-analysis document

If any source document is missing, run only stage 1 and stop with `阻塞`.

## Pipeline Rules

- All user-facing generated artifacts must be Markdown (`.md`). Structured sidecars are YAML validation artifacts.
- Final primary user-facing output must contain only the three Markdown deliverables defined in this skill. Stage handoff Markdown artifacts such as `业务场景链路清单.md` are auxiliary downstream inputs, not additional final primary deliverables.
- When writing files, also write `stage_status.yaml`, `coverage_matrix.yaml`, and `business_scenario_map.yaml` as machine-readable sidecars. They are validation evidence, not additional user-facing Markdown deliverables.
- Stage 1 and Stage 2 intermediate matrices, reports, coverage matrices, business scenario mapping, and risk lists must be embedded as sections in `03_skill执行报告.md`; an auxiliary `业务场景链路清单.md` may be written only as a lossless handoff view derived from the same `business_scenario_map.yaml`.
- Do not generate executable automation code, mock files, request fixtures, or scripts.
- Do not use the stage 1 precheck report as the coverage-object source for stage 3.
- Stage 2 must extract coverage objects from PRD/API/system-analysis documents and use the precheck report only as readiness and risk context.
- Stage 3 must consume Stage 2 analysis sections from `03_skill执行报告.md` and `02_接口结构化契约清单.md`, not the Stage 1 precheck section, to generate test case design.
- Do not claim 100% coverage unless every stage gate passes.
- The target is always 100% coverage. Do not present partial coverage as acceptable progress.
- Output a real non-100% coverage percentage only when the pipeline has already proven that 100% cannot be reached because of `阻塞`, `未覆盖`, `覆盖不足`, or insufficient source evidence.
- When reporting non-100% coverage, be factual: use the actual coverage matrix and reverse validation results. Do not round up, estimate optimistically, or hide blockers.
- If artifacts are too large for downstream context, use lossless internal shards. Sharding is for context management only; it must not summarize, omit, merge, rewrite, or weaken any source row, field, rule, assertion, coverage object, test point, contract fact, or coverage status.
- Every shard must be machine-recognizable by downstream skills through stable metadata, deterministic shard IDs, parent artifact name, schema name, object ID range or explicit object ID list, source locations, row counts, completeness status, and previous/next shard links.
- Internal shards are not additional final deliverables. They must be listed in `03_skill执行报告.md` and used only as process inputs for downstream reading, validation, and merge.

## Final Deliverables

The overall pipeline must output only these three final Markdown documents:

| 文件名 | 来源阶段 | 用途 |
|---|---|---|
| `01_接口测试用例设计文档.md` | Stage 3 | 最终接口测试用例设计、反向覆盖率矩阵和准出结论 |
| `02_接口结构化契约清单.md` | Stage 2 | 接口 method、path、鉴权、请求参数、字段约束、响应结构、错误码、幂等、分页、文件和回调契约 |
| `03_skill执行报告.md` | Pipeline | 前置校验结论、二阶段测试点分析报告、阶段门禁、覆盖率矩阵、真实覆盖率、风险和缺口 |

Do not deliver Stage 1 precheck report, Stage 2 mapping matrices, test point documents, coverage matrix, or risk list as standalone final primary Markdown files. Embed them into `03_skill执行报告.md`; keep `coverage_matrix.yaml` and `business_scenario_map.yaml` as machine-readable sidecars. If `业务场景链路清单.md` is generated, mark it as `辅助交接产物` in `03_skill执行报告.md` and keep its rows losslessly aligned with `business_scenario_map.yaml`.

## Structured Sidecars

When files are written, create these sidecars beside the three Markdown outputs. They must be derived from the same source rows used in `03_skill执行报告.md`; do not summarize, invent, or loosen gates in sidecars.

`stage_status.yaml` must include `schema_version: 1`, `stage: "pre_doc_analysis"`, `status`, `next_stage_allowed`, `source_files`, `stage_results`, `blocking_issues`, and `output_files`.

`coverage_matrix.yaml` must include `schema_version: 1`, `stage: "pre_doc_analysis"`, `coverage_summary`, and `coverage_objects`. `coverage_summary` must include `object_total/object_covered`, `test_point_total/test_point_mapped`, `rule_total/rule_covered`, `missing_object_ids`, `missing_test_point_ids`, and `missing_rule_ids`.

Sidecar gate: `status=passed`, `next_stage_allowed=true`, all covered/mapped counts equal their totals, and all missing ID lists are `[]` before downstream test case generation may use this stage as approved input.

If a blocking gate prevents a downstream document from being validly generated, output fewer than three documents rather than fabricating content. Never output a fourth user-facing document type.

### `business_scenario_map.yaml`

Required when Stage 2 reaches test-point analysis and mandatory before downstream test case generation consumes document-entry outputs.

```yaml
schema_version: 1
stage: business_scenario_mapping
status: passed | blocked | partial
next_stage_allowed: true | false
source_entry: doc
scenario_items:
  - scenario_id: "BS-001"
    scenario_name: "用户完成支付单支付"
    business_description: "用户在业务系统下单后进入统一支付，系统创建支付单、发起支付并回查支付结果，验证支付单从创建到支付完成的业务链路"
    roles: ["用户", "统一支付系统"]
    source_refs: ["PRD.md#支付流程", "API.md#支付接口", "系统分析.md#支付状态流转"]
    related_interfaces: ["创建支付单接口", "支付单支付接口", "查询支付单接口"]
    business_chain: ["创建支付单", "发起支付", "查询支付结果"]
    state_chain: ["待支付", "支付中", "支付完成"]
    chain_type: e2e_flow_candidate
    flow_generation_required: true
    flow_id: "FLOW-BS-001"
    ordered_step_count: 3
    ordered_steps:
      - step_order: 1
        interface: "创建支付单接口"
        test_point_id: "TP-001"
        source_ref: "API.md#创建支付单"
      - step_order: 2
        interface: "支付单支付接口"
        test_point_id: "TP-001"
        source_ref: "API.md#支付单支付"
      - step_order: 3
        interface: "查询支付单接口"
        test_point_id: "TP-001"
        source_ref: "API.md#查询支付单"
    related_test_point_ids: ["TP-001"]
    related_coverage_rule_ids: ["RULE-001"]
    confidence: high | medium | low
    blockers: []
blocking_issues: []
```

Gate:

- `status=passed` requires `next_stage_allowed=true`, `scenario_items` 非空，所有 `blockers` 和 `blocking_issues` 为空。
- 每个 `scenario_item` 必须绑定 PRD/API/系统分析中的 source refs，并至少绑定一个测试点或覆盖规则 ID。
- `business_description` 必须是中文业务链路描述，不能只复述接口名、方法、路径或测试类型。
- `related_interfaces` 必须使用业务接口名称而不是实现调用栈；多接口链路必须保持业务顺序。
- 多接口业务链路必须设置 `chain_type: e2e_flow_candidate`、`flow_generation_required: true`、稳定 `flow_id`、`ordered_step_count >= 2` 和 `ordered_steps`，供执行级用例与 pytest 阶段生成链路脚本。
- `confidence=low`、source refs 缺失、测试点/覆盖规则无法绑定、状态链无法从文档证明，均视为 `blocked` 或 `partial`，不得放行给下游。

Auxiliary Markdown view:

- `业务场景链路清单.md` may be generated as a human-readable handoff view of this sidecar.
- It must include `业务场景ID`、`业务场景名称`、`业务场景描述`、`链路类型`、`是否必须生成链路脚本`、`flow_id`、`步骤数`、`角色`、`来源`、`业务链路`、`接口链路`、`状态链路`、`关联测试点ID`、`关联覆盖规则ID`、`置信度`、`阻塞项`.
- It must not contain rows absent from `business_scenario_map.yaml`.

## Lossless Sharding Contract

Use lossless internal shards only when a stage artifact or handoff input is too large for the downstream skill to safely read in one pass.

Sharding rules:

- Do not replace full details with summaries. Each shard must preserve the original table schema, every row, every column, every ID, every source location, every assertion point, every contract rule, every coverage status, and every gap or risk description.
- Do not split one logical row across shards. If a row is too long, keep it in one shard and mark the shard as `大行分片`.
- Do not change generated IDs during sharding. ID stability is the merge key.
- Do not deduplicate by natural language during sharding. Merge or deduplicate only by stable coverage object ID, test point ID, contract rule ID, or case ID.
- Do not let a downstream skill infer missing rows from neighboring shards. Missing shard, missing row count, or broken sequence is `阻塞`.
- Keep original source evidence in every shard row, including source document, source location, and original summary.
- The full artifact can be reconstructed by concatenating shards in `分片序号` order under the same `父产物` and `表结构名称`.

Each internal shard document must start with this metadata header:

```markdown
# 内部分片文档

| 元数据项 | 值 |
|---|---|
| 分片ID | SHARD-STAGE2-001 |
| 父产物 | 03_skill执行报告.md / 02_接口结构化契约清单.md |
| 表结构名称 | 覆盖率矩阵 |
| 分片序号 | 1/5 |
| 覆盖对象ID范围 | API-001..API-020 |
| 覆盖对象ID清单 | API-001, API-002 |
| 来源文档 | PRD/API/系统分析 |
| 来源位置范围 | 文件名 + 章节/表名/接口路径 |
| 行数 | 20 |
| 字段完整性 | 完整 |
| 分片完整性 | 完整 / 大行分片 / 阻塞 |
| 前序分片ID | 无 / SHARD-STAGE2-000 |
| 后续分片ID | SHARD-STAGE2-002 / 无 |
| 下游读取用途 | Stage 3 覆盖对象池 / 契约校准 / 反向验收 |

## 分片内容
```

`03_skill执行报告.md` must include a shard manifest when internal shards exist:

```markdown
### 分片清单
| 分片ID | 父产物 | 表结构名称 | 分片序号 | 覆盖对象ID范围 | 覆盖对象ID清单 | 行数 | 字段完整性 | 分片完整性 | 下游读取用途 |
|---|---|---|---|---|---|---:|---|---|---|
```

Downstream reading rules:

- Read the shard manifest first.
- Read shards by explicit `分片ID` and `覆盖对象ID清单`, not by natural language matching.
- When generating Stage 3, first load coverage matrix shards and contract list shards, then load only the shards that contain impacted `REQ-*`, `ACTION-*`, `API-*`, `FIELD-*`, `RULE-*`, `ASSERT-*`, `ERR-*`, `STATE-*`, `TRANS-*`, `DEP-*`, `COMP-*`, or `EVENT-*` IDs.
- Before claiming 100%, confirm every shard in the manifest is present, every sequence is complete, every row count matches, and every shard has `字段完整性=完整`.
- If any required shard is missing, out of order, duplicated, or marked `分片完整性=阻塞`, set the pipeline or downstream stage conclusion to `阻塞`.

## Skill Execution Report

Always generate `03_skill执行报告.md` as the pipeline-level audit and handoff artifact.

The skill execution report must include these sections:

1. `输入文档清单`
   - PRD 文件名、版本、来源路径或用户提供位置
   - API 文件名、版本、来源路径或用户提供位置
   - 系统分析文件名、版本、来源路径或用户提供位置

2. `阶段执行结果`
   - Stage 1 结论：`通过` / `有风险通过` / `阻塞`
   - Stage 2 结论：`测试点覆盖率100%` / `覆盖不足` / `阻塞` / `未执行`
   - Stage 3 结论：`接口测试用例设计覆盖率100%` / `覆盖不足` / `阻塞` / `未执行`
   - 每个阶段的阻塞原因、风险项数量、核心覆盖缺口数量

3. `产物清单`
   - 文件名
   - 类型：最终产物 / 内部阶段产物
   - 阶段
   - 生成状态：`已生成` / `未生成` / `部分生成`
   - 是否作为最终交付输出
   - 作为哪些后续分析的输入
   - 是否参与最终覆盖率验收

4. `数据流转关系`
   - 源文档 -> Stage 1 前置校验报告
   - 源文档 + Stage 1 结论 -> Stage 2 测试点分析产物
   - Stage 2 测试点分析章节 + `02_接口结构化契约清单.md` -> `01_接口测试用例设计文档.md`
   - Stage 1 前置校验章节不得作为 Stage 3 覆盖对象来源
   - 接口结构化契约清单不得单独新增覆盖对象，也不得改变测试用例设计生成策略
   - 接口结构化契约清单可以通过绑定到现有 `API-*`、`FIELD-*`、`ERR-*` 对象的契约覆盖规则，校准覆盖率分母

5. `二阶段测试点分析报告`
   - 需求-接口-状态三向追踪矩阵
   - 字段-规则-断言映射表
   - 错误码-异常场景映射表
   - 状态迁移-触发入口映射表
   - 依赖失败-补偿场景映射表
   - 业务场景链路清单
   - 业务场景测试点
   - 接口测试点
   - 状态机与数据一致性测试点
   - 异常、补偿、依赖测试点
   - 覆盖率矩阵
   - 剩余风险清单, only when risks remain

6. `覆盖率准出摘要`
   - 核心覆盖对象总数
   - 已覆盖核心对象数
   - 待补充核心对象数
   - 覆盖不足核心对象数
   - 未覆盖核心对象数
   - 阻塞核心对象数
   - 是否允许声明最终 100% 覆盖
   - 当无法声明 100% 时，必须输出真实对象级覆盖率和真实规则级覆盖率
   - 对象级覆盖率 = 已完全覆盖核心对象数 / 核心覆盖对象总数 * 100%
   - 规则级覆盖率 = 已满足覆盖规则数 / 应满足覆盖规则总数 * 100%
   - 应满足覆盖规则总数 = 覆盖对象最低覆盖规则数 + 可绑定到现有 API/FIELD/ERR 对象的契约覆盖规则数
   - 契约清单中无法绑定到现有覆盖对象的接口、字段、错误码或规则，不得直接进入分母；必须标记为 `待补充` 或 `阻塞` 并要求修复二阶段产物
   - 最终覆盖率口径以规则级覆盖率为准，对象级覆盖率只作为辅助指标
   - P0/P1 高风险规则覆盖率 = 已满足 P0/P1 覆盖规则数 / 应满足 P0/P1 覆盖规则总数 * 100%，仅作为风险辅助指标
   - P0/P1 高风险规则覆盖率不得替代规则级覆盖率，也不得用于放宽最终 100% 准出门禁

7. `交付结论`
   - `通过`：全部阶段门禁通过，允许使用 `01_接口测试用例设计文档.md`
   - `覆盖不足`：存在非阻塞缺口，不允许声明 100%，必须给出真实覆盖率和缺口明细
   - `阻塞`：存在核心阻塞项，不允许进入后续阶段或不允许交付最终用例设计，必须给出真实覆盖率和阻塞原因

Use this Markdown template for `03_skill执行报告.md`:

```markdown
# skill执行报告

## 1. 输入文档清单
| 文档类型 | 文件名 | 版本/日期 | 来源路径或用户提供位置 | 业务范围 | 识别结果 |
|---|---|---|---|---|---|

## 2. 阶段执行结果
| 阶段 | 结论 | 是否执行 | 阻塞原因 | 风险项数量 | 核心覆盖缺口数量 | 后续处理 |
|---|---|---|---|---:|---:|---|

## 3. 产物清单
| 文件名或章节名 | 类型 | 阶段 | 生成状态 | 是否最终交付输出 | 作为哪些后续分析的输入 | 是否参与最终覆盖率验收 |
|---|---|---|---|---|---|---|

## 4. 数据流转关系
| 数据 | 来源 | 去向 | 是否允许作为 Stage 3 覆盖对象来源 | 约束 |
|---|---|---|---|---|

### 4.1 分片清单
| 分片ID | 父产物 | 表结构名称 | 分片序号 | 覆盖对象ID范围 | 覆盖对象ID清单 | 行数 | 字段完整性 | 分片完整性 | 下游读取用途 |
|---|---|---|---|---|---|---:|---|---|---|

## 5. 二阶段测试点分析报告
### 5.1 需求-接口-状态三向追踪矩阵
### 5.2 字段-规则-断言映射表
### 5.3 错误码-异常场景映射表
### 5.4 状态迁移-触发入口映射表
### 5.5 依赖失败-补偿场景映射表
### 5.6 业务场景链路清单
| 业务场景ID | 业务场景名称 | 业务场景描述 | 链路类型 | 是否必须生成链路脚本 | flow_id | 步骤数 | 角色 | 来源 | 业务链路 | 接口链路 | 状态链路 | 关联测试点ID | 关联覆盖规则ID | 置信度 | 阻塞项 |
|---|---|---|---|---|---|---:|---|---|---|---|---|---|---|---|---|
### 5.7 业务场景测试点
### 5.8 接口测试点
### 5.9 状态机与数据一致性测试点
### 5.10 异常、补偿、依赖测试点
### 5.11 覆盖率矩阵
### 5.12 剩余风险清单

## 6. 覆盖率准出摘要
| 指标 | 数值 | 计算口径 | 是否用于最终准出 |
|---|---:|---|---|

## 7. 阻塞与覆盖不足明细
| 编号 | 对象或规则ID | 类型 | 来源 | 缺失规则或问题 | 影响产物 | 建议修改 |
|---|---|---|---|---|---|---|

## 8. 结构化校验清单
| 校验项 | 校验结果 | 证据位置 | 未通过原因 | 处理建议 |
|---|---|---|---|---|

## 9. 交付结论
- 结论：通过 / 覆盖不足 / 阻塞
- 是否允许声明最终 100% 覆盖：是 / 否
- 最终覆盖率口径：规则级覆盖率 / 无法计算
- 结论依据：
```

If the pipeline stops before Stage 2, keep the Stage 2 subsections in the report and mark each ungenerated section as `未执行`. Do not invent rows for unexecuted matrices.

The skill execution report is an audit artifact and Stage 2 handoff container. For Stage 3, use only the Stage 2 analysis sections inside it as coverage-object sources. Do not use the Stage 1 precheck section as a coverage-object source.
Stage 2 analysis sections in `03_skill执行报告.md` must preserve the original `$test-point-analysis` table schemas so Stage 3 can use them as equivalent Markdown coverage-object sources.

## Stage 1: Document Precheck

Invoke `$doc-precheck-coverage`.

Inputs:

- PRD `.md`
- API `.md`
- System-analysis `.md`

Output:

- Write the precheck result into `03_skill执行报告.md`.

Gate:

- If conclusion is `阻塞`, stop the pipeline.
- If conclusion is `有风险通过`, continue only if risks are non-core and record them for stage 2.
- If conclusion is `通过`, continue to stage 2.

Stage 1 must prove source readiness but must not be treated as test point evidence.

## Stage 2: Test Point Analysis

Invoke `$test-point-analysis`.

Inputs:

- PRD `.md`
- API `.md`
- System-analysis `.md`
- Stage 1 前置校验章节 from `03_skill执行报告.md`

Outputs:

- Write these Stage 2 analysis sections into `03_skill执行报告.md`:
  - 需求-接口-状态三向追踪矩阵
  - 字段-规则-断言映射表
  - 错误码-异常场景映射表
  - 状态迁移-触发入口映射表
  - 依赖失败-补偿场景映射表
  - 业务场景链路清单
  - 业务场景测试点
  - 接口测试点
  - 状态机与数据一致性测试点
  - 异常、补偿、依赖测试点
  - 覆盖率矩阵
  - 剩余风险清单, only when risks remain
- Output `02_接口结构化契约清单.md` as a standalone final deliverable.
- Output `business_scenario_map.yaml` as the mandatory machine-readable business scenario mapping sidecar.
- Output `业务场景链路清单.md` as an auxiliary handoff Markdown view only when the same rows have already been written to `business_scenario_map.yaml`; also embed the same table in `03_skill执行报告.md`.

Gate:

- Every core coverage object must have stable ID, source document, source location, source summary, core flag, mapping relationship, minimum coverage rule, and coverage status.
- Every business scenario used by a test point must have a stable `scenario_id`, Chinese `business_description`, source refs, related interface chain, related test point IDs, related coverage rule IDs, and `confidence` not lower than `medium`.
- If a business scenario cannot be traced back to PRD/API/system-analysis content, mark Stage 2 as `阻塞` or `覆盖不足`; do not invent business descriptions for downstream reports.
- Core coverage objects and bound contract rules must have 0 `未覆盖`, 0 `待补充`, 0 `覆盖不足`, and 0 `阻塞` before stage 2 can claim `测试点覆盖率 100%`.
- If any core coverage object is `阻塞`, stop the pipeline and do not enter stage 3.
- If any bound contract rule is `阻塞` and it can bind to an existing `API-*`, `FIELD-*`, or `ERR-*` object, stop the pipeline unless Stage 3 is explicitly needed only to produce a `阻塞` conclusion document. Do not treat bound contract rule `阻塞` as ordinary `覆盖不足`.
- If any core coverage object or bound contract rule is `未覆盖`, `待补充`, or `覆盖不足`, stage 3 may run only to produce a coverage-insufficient interface test case design document. Do not claim 100%.

## Stage 3: Interface Test Case Design

Invoke `$interface-testcase-design`.

Inputs:

- Stage 2 analysis sections inside `03_skill执行报告.md`:
  - 需求-接口-状态三向追踪矩阵
  - 字段-规则-断言映射表
  - 错误码-异常场景映射表
  - 状态迁移-触发入口映射表
  - 依赖失败-补偿场景映射表
  - 业务场景链路清单
  - 业务场景测试点
  - 接口测试点
  - 状态机与数据一致性测试点
  - 异常、补偿、依赖测试点
  - 覆盖率矩阵
  - 剩余风险清单, if present
- `02_接口结构化契约清单.md`

Do not pass the stage 1 precheck report as a coverage-object input.
Do not use `02_接口结构化契约清单.md` as an independent coverage-object source. Use it only to align method, path, request, response, auth, idempotency, pagination, file, and callback contract details with cases and to validate bound contract coverage rules.

Output:

- `01_接口测试用例设计文档.md`

Gate:

- Every coverage object has a unique ID.
- Every test case binds coverage object IDs and coverage rule IDs.
- Every test case has source evidence and assertion points.
- The reverse coverage matrix has 0 core `未覆盖`, 0 core `待补充`, 0 core `覆盖不足`, and 0 core `阻塞`.
- All exit gates in `$interface-testcase-design` pass before claiming `接口测试用例设计覆盖率 100%`.

## Data Flow Contract

Use this data flow:

| 数据 | 来源 | 去向 | 必须保留 |
|---|---|---|---|
| 源文档内容 | PRD/API/系统分析 | Stage 1 and Stage 2 | 文件名、章节、原文摘要 |
| 准入结论 | Stage 1 | Stage 2 | 结论、阻塞项、风险项 |
| 覆盖对象 | Stage 2 | Stage 3 | ID、类型、名称、来源文档或来源产物、来源位置、原文摘要、是否核心对象、映射关系、最低覆盖规则、覆盖状态 |
| 测试点 | Stage 2 | Stage 3 | 测试点ID、覆盖对象ID、断言点、来源依据、优先级、覆盖状态 |
| 业务场景映射 | Stage 2 | Stage 3 and downstream coverage-point report | 业务场景ID、业务场景名称、中文业务场景描述、角色、来源文档或来源产物、业务链路、接口链路、状态链路、关联测试点ID、关联覆盖规则ID、置信度、阻塞项 |
| 接口契约 | Stage 2 | Stage 3 | API ID、method、path、鉴权、请求参数、字段约束、响应结构、错误码、幂等、分页、文件、回调、来源文档、来源位置、原文摘要、契约覆盖规则、契约完整性、缺口 |
| 用例设计 | Stage 3 | `01_接口测试用例设计文档.md` | 用例ID、覆盖对象ID、覆盖规则ID、断言点、来源依据、覆盖状态 |
| 执行报告 | Pipeline | `03_skill执行报告.md` | 输入清单、阶段门禁、二阶段报告、覆盖率矩阵、真实覆盖率、风险和缺口 |
| 内部分片 | Stage 1/Stage 2/Stage 3 | 下游阶段按需读取 | 分片ID、父产物、表结构名称、分片序号、覆盖对象ID范围或清单、来源位置、行数、字段完整性、分片完整性、前后分片关系 |

## Coverage Closure Rules

To claim final 100% coverage:

- Stage 1 must be `通过` or `有风险通过` with only non-core risks.
- Stage 2 coverage matrix must have no core `未覆盖`, `待补充`, `覆盖不足`, or `阻塞`.
- Stage 3 reverse validation must have no core `未覆盖`, `待补充`, `覆盖不足`, or `阻塞`.
- Every generated test case must trace back to a coverage object.
- Every coverage object must trace back to source evidence.
- Every downstream-facing business scenario description must trace back to `business_scenario_map.yaml`; a test point without scenario mapping cannot be treated as ready for downstream coverage-point reporting.
- Every contract coverage rule that can bind to an existing API, field, or error-code object must be covered by a case or assertion.
- No coverage object may be duplicated under different IDs.
- No test case may be counted toward coverage without an assertion point.

If any rule fails, final conclusion must be `覆盖不足` or `阻塞`, never `覆盖率 100%`.

When final 100% cannot be reached:

- Output the real object-level coverage and rule-level coverage in `03_skill执行报告.md`.
- If Stage 1 is blocked and the coverage object pool is not generated, mark object-level coverage and rule-level coverage as `无法计算`, list the blocking source-document gaps, and do not estimate or fabricate a percentage.
- If Stage 2 is blocked before the coverage object pool, coverage matrix, or rule denominator is complete, mark object-level coverage and rule-level coverage as `无法计算：Stage 2 阻塞，覆盖对象池或规则分母未完整生成`.
- If Stage 2 is blocked after a complete coverage matrix and rule denominator are generated, output the real object-level coverage and rule-level coverage, and keep blocked objects and blocked rules in the denominator.
- Use rule-level coverage as the final numeric coverage.
- Output P0/P1 high-risk rule coverage as an auxiliary risk indicator when priority data exists in Stage 2 or Stage 3 artifacts.
- If priority data is missing, mark P0/P1 high-risk rule coverage as `无法计算：缺少规则优先级` and do not infer priorities.
- Keep blocked objects and blocked rules in the denominator unless the source documents explicitly mark them as out of interface-test scope.
- Keep blocked contract rules in the denominator when they can bind to existing API, field, or error-code objects.
- List every object or rule that prevents 100% coverage, including its ID, type, source, missing rule, impacted artifact, and suggested document fix.
- Do not use partial coverage percentage to weaken the target. The conclusion remains `覆盖不足` or `阻塞` until every core object and rule is covered.

## Final Delivery by Pipeline Result

Depending on the pipeline result:

### If Stage 1 Is Blocked

Output:

- `03_skill执行报告.md`

Stop. Do not generate `01_接口测试用例设计文档.md` or `02_接口结构化契约清单.md`. In `03_skill执行报告.md`, mark coverage as `无法计算：Stage 1 阻塞，覆盖对象池未生成`, and list the blocking document gaps and modification suggestions.

### If Stage 2 Is Blocked

Output:

- `02_接口结构化契约清单.md`, if it can be safely generated from the API document
- `03_skill执行报告.md`

Stop. Do not generate `01_接口测试用例设计文档.md` unless Stage 3 is explicitly needed only to expose a `阻塞` conclusion from already generated Stage 2 sections. Do not claim final 100%.

### If Stage 2 Is Coverage-Insufficient

Output:

- `01_接口测试用例设计文档.md` with conclusion `覆盖不足`
- `02_接口结构化契约清单.md`
- `03_skill执行报告.md`

Stage 3 may run only to expose missing cases and impacted coverage object IDs. Do not claim final 100%.

### If Stage 3 Is Coverage-Insufficient Or Blocked

Output:

- `01_接口测试用例设计文档.md` with conclusion `覆盖不足` or `阻塞`
- `02_接口结构化契约清单.md`
- `03_skill执行报告.md`

This branch applies when Stage 2 can enter Stage 3, but Stage 3 reverse validation, contract consistency validation, source evidence validation, assertion validation, or minimum coverage rule validation fails. The final report must include the failed Stage 3 gate, impacted coverage object IDs, impacted contract rule IDs when applicable, real object-level coverage, real rule-level coverage when the denominator is complete, and modification suggestions. Do not claim final 100%.

### If All Gates Pass

Output:

- `01_接口测试用例设计文档.md`
- `02_接口结构化契约清单.md`
- `03_skill执行报告.md`

The final interface test case design document may claim `接口测试用例设计覆盖率 100%` only if Stage 2 and Stage 3 gates both pass.

## Final Quality Check

Before finishing:

- Confirm every output is `.md`.
- Confirm final user-facing output contains no more than the three deliverables defined in this skill.
- Confirm `03_skill执行报告.md` lists every internal stage artifact/section, including ungenerated sections when the pipeline stops early.
- Confirm the Stage 1 precheck section in `03_skill执行报告.md` is not used as a coverage-object source.
- Confirm Stage 3 does not consume Stage 1 report as coverage-object source.
- Confirm Stage 2 sections in `03_skill执行报告.md` use the `$test-point-analysis` schemas.
- Confirm Stage 3 uses coverage object IDs from Stage 2.
- Confirm Stage 3 uses `02_接口结构化契约清单.md` to validate contract consistency and contract rule coverage without changing the case generation strategy.
- Confirm contract coverage rules only affect the coverage denominator when they bind to existing `API-*`, `FIELD-*`, or `ERR-*` objects.
- Confirm bound contract rule `阻塞` is handled as a Stage 2 or Stage 3 blocking branch, not as an ordinary non-blocking coverage gap.
- Confirm Stage 3 `覆盖不足` or `阻塞` has an explicit delivery branch and does not fall through to the all-gates-pass branch.
- Confirm Stage 2 blocking coverage is marked `无法计算` when the coverage object pool, coverage matrix, or rule denominator is incomplete.
- Confirm `03_skill执行报告.md` follows the required template and includes the structure validation checklist.
- If internal shards exist, confirm every shard is lossless, machine-recognizable, listed in the shard manifest, and reconstructable by `父产物 + 表结构名称 + 分片序号`.
- Confirm downstream reading uses explicit shard IDs and coverage object IDs, not natural language matching or inferred missing rows.
- If final 100% is not reached, confirm `03_skill执行报告.md` reports real object-level coverage, real rule-level coverage, and every blocking or insufficient coverage item.
- If P0/P1 priority data exists, confirm `03_skill执行报告.md` reports P0/P1 high-risk rule coverage as an auxiliary indicator and does not use it to replace final rule-level coverage.
- Confirm Chinese text has no garbling.
