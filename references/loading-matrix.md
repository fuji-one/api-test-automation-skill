# 加载矩阵与阶段边界

## 目录

- [读取时机](#读取时机)
- [固定阶段状态机](#固定阶段状态机)
- [必读矩阵](#必读矩阵)
- [容易混乱点标记](#容易混乱点标记)
- [规则正文](#规则正文)
- [Goal](#goal)
- [Bundled Component Layout](#bundled-component-layout)
- [Initial Preflight](#initial-preflight)
- [Entry Routing Rules](#entry-routing-rules)
- [来源](#来源)

## 读取时机

每次触发 suite 后先读。本文件定义阶段顺序、目标深度、每个阶段必须加载的规则文件和容易混乱的边界。

## 固定阶段状态机

不得因规则拆分改变阶段顺序。固定顺序为：

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

## 必读矩阵

| 阶段 | 必读文件 | 说明 |
|---|---|---|
| preflight | `references/loading-matrix.md`, `references/pipeline-gates.md` | 判断目标深度、step-by-step 模式、入口完整性。 |
| entry 文档入口 | `components/pre-doc-analysis-pipeline/SKILL.md`, `references/sidecar-contracts.md` | 生成文档入口三件套和 sidecar。 |
| entry 源码入口 | `components/source-api-fact-extractor/SKILL.md`, `references/sidecar-contracts.md` | 生成源码事实、业务场景映射和 sidecar。 |
| required chain denominator | `references/chain-flow-contract.md` | 在阶段2前生成 `required_chain_flows.yaml` 和候选审计。 |
| design cases | `components/interface-testcase-generation/SKILL.md`, `references/chain-flow-contract.md`, `references/sidecar-contracts.md`, `references/case-confidence-contract.md` | 生成设计级用例、业务长链路设计分母、覆盖点报告，并计算逐用例置信度。 |
| handoff | `references/pipeline-gates.md`, `references/sidecar-contracts.md` | 原样复制结构化产物，不新增事实。 |
| runtime evidence optional | `references/runtime-evidence-policy.md`, `references/source-derived-runtime-inputs.md`, `references/db-mcp-alignment-policy.md` | 只在用户要求 requester 取证、执行级补值、源码推导入参或真实请求回填队列时进入。 |
| chain execution-readiness reconciliation | `references/chain-flow-contract.md`, `references/pipeline-gates.md` | 任一执行就绪事实变化时，按事实文件哈希作废旧分母并重算；按目标深度能力判定，不绑定项目名或固定断言等级。 |
| executable cases | `components/executable-interface-case-set/SKILL.md`, `components/executable-interface-case-set/references/io-contract.md`, `references/execution-fact-closure.md`, `references/apifox-boundary.md`, `references/case-confidence-contract.md` | 执行事实闭合、长链路补值、Apifox 证据边界和置信度重算。 |
| framework | `components/api-test-framework-generator/SKILL.md`, `references/case-confidence-contract.md` 及其 `references/*.md` | 按组件声明读取 conversion、runtime usability、materialization、archive 等规则，并投影置信度。 |
| final validation | `references/failure-and-completion-policy.md`, `scripts/validate_pipeline_outputs.py` | 运行总体验证并按最终脚本是否生成给结论。 |

## 容易混乱点标记

- `business_long_chain_cases.yaml` 是设计级业务长链路分母；`required_chain_flows.yaml` 是执行/脚本必测闭环分母。两者不能混用。
- `required_chain_flows.yaml` 的初始版本不是不可变结果。运行时证据、长链路补值、setup/cleanup 或外部隔离事实变化后，必须通过 `chain_execution_readiness_reconciliation.yaml` 重算并重新复制到 handoff；旧事实哈希不匹配时禁止继续。
- 重算后的 execution-ready 集合必须守恒为 generated 与 explicitly-excluded 两个互斥集合；每条 ready chain 只能出现一次。`filled_count > 0` 且零必测分母只有在所有 ready chain 均有明确排除理由和证据时才合法。
- `04-runtime-evidence-plan/` 和 `04-runtime-evidence/` 只能在 `04-design-case-handoff/` 之后、`05-executable-interface-case-set/` 之前按需执行。
- `测试覆盖点报告.md` 是人工复核材料，不是执行级或脚本级硬分母。
- Apifox MCP 不是运行时 requester。真实请求证据只能来自 `04-runtime-evidence/`。
- 数据库 MCP 是上游证据源，pytest 工程只能消费归一化 sidecar，不能保留 MCP 调用。
- Framework 阶段新增的 runtime materialization、setup/cleanup、final archive 规则以 `components/api-test-framework-generator/references/` 为细节权威，并由 validator 做最终准出。
- 逐用例置信度以 `references/case-confidence-contract.md` 为唯一权威；它是证据质量摘要，不替代场景相关性、断言强度、自动化决策或 live 门禁。

## 规则正文

## Goal

Run one complete staged API automation workflow without weakening the gates of the component skills:

```text
初始预检: 入口输入 + 目标阶段 + 执行级准备状态
阶段1: 入口质检与测试点拆分
  文档入口: PRD/API/系统分析/数据模型 -> $pre-doc-analysis-pipeline
  源码入口: Java 后端源码 -> $source-api-fact-extractor
阶段1.5: 数据模型归一化与源码-数据库一致性门禁（执行级/脚本目标按需）
  既有数据模型: 复制为 00-inputs/数据模型.md
  数据库 MCP: 读取库表结构、键约束、表关系证据 -> 生成含轻量知识图谱的 00-inputs/数据模型.md -> 与源码 DB 事实对账
阶段1.6: 长链路闭环分母生成与审计
  文档入口/源码入口闭环证据 -> required_chain_flows.yaml + chain_flow_candidate_audit.yaml
-> 入口产物选择与一致性检查
阶段2: 基于测试点生成设计级测试用例 -> $interface-testcase-generation
  业务场景长链路设计分母 -> business_long_chain_cases.yaml + 业务长链路设计清单.md
-> 设计级用例交接适配
阶段2.8: 运行时取证规划与补值（可选）-> risk audit + DB before/after probe plan + direct requester
阶段3: 生成可执行接口用例 -> $executable-interface-case-set
阶段4: 生成可执行 pytest+allure 代码与可读 E2E flow 套件 -> $api-test-framework-generator
```

This skill is an orchestrator suite. It must not replace or weaken the component skill instructions. Always load and follow each component skill before executing that stage.

## Bundled Component Layout

This skill is structured as one self-contained folder. Resolve bundled resources from the current skill directory first:

```text
api-automation-pipeline-suite/
├── SKILL.md
├── agents/openai.yaml
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

When this SKILL.md refers to a component skill such as `$source-api-fact-extractor`, load the bundled component file at `components/source-api-fact-extractor/SKILL.md` and follow it completely before executing that stage. Resolve any relative `scripts/`, `references/`, or `assets/` paths mentioned by that component relative to its own component directory. Use a globally installed skill with the same name only if the bundled component is missing, and state that fallback explicitly to the user.

Root-level orchestrator scripts remain under this suite's `scripts/` directory. Component-owned scripts remain inside their component folders, for example `components/source-api-fact-extractor/scripts/scan_source.py`, `components/executable-interface-case-set/scripts/validate_outputs.py`, and `components/api-test-framework-generator/assets/api-test-framework-template/`.

When runtime execution configuration is missing or incomplete, materialize a run-specific fillable package under `00-inputs/`: copy or present `components/executable-interface-case-set/assets/templates/runtime_execution_config.template.yaml`, write `前置执行配置待填写.md` with the same required sections in Chinese, and write `runtime_execution_config.missing_fields.yaml` when the missing fields are known. The filled user artifact is run-specific input and must not be copied into this skill as a permanent project rule.

Runtime environment, accounts, token placement, concrete test data, DB authorization, external sandbox configuration, and transport-crypto keys are execution-level readiness inputs. They must not block stage 1 source/document fact extraction or stage 2 design-level case generation. Design-level cases are generated from coverage objects, source/document facts, interface contracts, business scenarios, and test strategies, and must aim for 100% coverage of real business scenarios without depending on executable runtime values. Only stage 3 and stage 4 may block on missing runtime data, precondition construction, auth, environment, DB before/after, cleanup, or external dependency configuration.

## Initial Preflight

Run this check before any component skill:

1. Decide target depth from the user request:
   - `design`: stop after design-level case generation and handoff.
   - `executable`: continue through `$executable-interface-case-set`.
   - `framework`: continue through pytest+allure generation; this is the default for a full pipeline request.
   - If the user says `一步步来`、`分阶段来`、`先处理到某阶段`、`不要一次跑完`, enter step-by-step mode. In this mode, do not jump to execution-level cases, runtime requester evidence, DB mutation, or framework generation unless the user explicitly asks to continue to that next depth. If no explicit target depth is given, default to `design`, finish the current gated segment through `04-design-case-handoff/`, run validation, summarize the highest completed gate, and wait for the user's next `继续`.
   - In step-by-step mode, keep a visible short checklist for the current segment, update it as gates pass, and stop at every durable handoff boundary: entry facts, chain denominator, design-case handoff, execution readiness, executable-case release, and framework release. Do not treat missing execution configuration, runtime values, DB authorization, or crypto runtime details as blockers for the design segment; record them as next-segment inputs.
2. Validate entry existence:
   - Complete document entry means PRD、API、系统分析、数据模型四个 Markdown are readable, non-empty, UTF-8, and contain no replacement characters.
   - Source entry means the Java source root exists and contains Java/Spring related source files.
3. Validate execution readiness at the start:
   - Entry stages may run when either the complete document entry or source entry is satisfied. These two entry stages are mutually substitutable for starting the pipeline, with document entry taking priority. Do not block the source entry only because data model or execution configuration is not yet available.
   - Stage 2 design-level case generation must run when stage 1 facts, coverage objects, business scenario mapping, contracts, and chain denominators pass. Missing environment, account, token, verifier code, device ID, concrete DB rows, DB authorization, external sandbox, or transport-crypto key source must be recorded as execution-level pending input, not as a design-level blocker.
   - If target depth is `executable` or `framework`, require a readable, non-empty, UTF-8 data model Markdown file before entering `$executable-interface-case-set` or `$api-test-framework-generator`; it must include table structure plus setup/cleanup graph evidence. Source-only entry must first run `$source-api-fact-extractor`, then, when no normalized data model exists, check available database MCP metadata before blocking. Do not stop only because the user did not provide `数据模型.md`; stop only after MCP is unavailable/unreadable, the database identity cannot be confirmed, the schema cannot generate the required graph/setup/cleanup evidence, or `source_db_alignment.yaml` cannot pass.
   - If target depth is `executable` or `framework`, require environment reference and authentication account inputs before execution-level filling; token rules, test-data rules, variable extraction/injection rules, precise assertion rules, and cleanup strategy may be derived only from source-present materials.
   - If target depth is `executable` or `framework` and environment/account/auth/crypto facts are missing, materialize `00-inputs/runtime_execution_config.template.yaml`, `00-inputs/前置执行配置待填写.md`, and `00-inputs/runtime_execution_config.missing_fields.yaml` when fields are known; stop before execution-level filling with `BLOCKED_NEED_EXECUTION_INPUT`. Continue only after the user uploads a filled configuration or equivalent artifact that satisfies the required fields.
   - Environment is mandatory in the filled execution configuration. If `is_test_environment=false`, any default test-environment DB before/after or cleanup authorization is not valid for this run; require explicit non-test DB authorization before DB probing, cleanup, rollback, or status recovery.
   - If target depth is `executable` or `framework`, enforce API-first precondition construction: SQL construction is allowed only when upstream rules explicitly state why API construction cannot satisfy the case.
   - If target depth is `framework` and upstream or user-confirmed policy contains encrypted interfaces, require an executable transport encryption contract before `$api-test-framework-generator`; missing algorithm reference, key source, request payload scope, request plaintext serialization, request envelope, or response envelope must stop with `BLOCKED_NEED_EXECUTION_INPUT`.
   - If environment reference or authentication account input is missing, do not block a valid entry stage. Continue through entry and design stages when their inputs are complete, then stop before execution-level filling or script generation with `BLOCKED_NEED_EXECUTION_INPUT` unless the user explicitly narrows the target to `design`.
4. Normalize provided data model to `00-inputs/数据模型.md` by copying source-present content only. Do not infer tables, columns, constraints, SQL, cleanup rules, or relationships from thin air; if the provided data model lacks setup/cleanup graph evidence required by the target depth, block before execution filling.
5. When the data model is produced from database MCP, write MCP-observed schema facts plus explicitly labeled relationship/cleanup inferences to `00-inputs/数据模型.md`, write `database_mcp_evidence_index.yaml`, and require `source_db_alignment.yaml.status=passed` before executable/script stages.

## Entry Routing Rules

Route from user inputs, not from guessed intent:

| 用户输入满足情况 | 默认入口 | 执行规则 |
|---|---|---|
| 同时提供 PRD Markdown、API Markdown、系统分析 Markdown、数据模型 Markdown | `$pre-doc-analysis-pipeline` | 走文档入口；四个文件缺一不可 |
| 只提供 Java 后端源码根目录，且未提供完整四件套文档入口 | `$source-api-fact-extractor` | 走源码入口；源码入口不要求同时提供 PRD/API/系统分析/数据模型 |
| 同时满足完整四件套文档入口和 Java 后端源码 | `$pre-doc-analysis-pipeline` | 优先走文档入口；默认不跑源码入口 |
| 两类入口都不满足 | 无 | 写 `BLOCKED_MISSING_ENTRY_INPUT` |

If both entry groups are satisfied and the user explicitly asks to include source implementation evidence, run `$source-api-fact-extractor` as an auxiliary evidence stage after `$pre-doc-analysis-pipeline`; then compare `01_接口测试用例设计文档.md`、`02_接口结构化契约清单.md`、`03_skill执行报告.md`. If method/path/field/status/error-code facts conflict, stop before case generation and record `FAILED_ENTRY_ALIGNMENT_GATE`.

Use `数据模型.md` to determine whether the document entry is complete. Do not use it to reject a valid source entry; source-only runs may proceed to source fact extraction and then block at execution readiness if no normalized data model is available.

Use `scripts/select_entry_route.py` when a deterministic route decision is useful:

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


## 来源

本文件从 `SKILL.md` 原主契约拆分而来；完整历史契约保存在 `references/full-contract.md`。
