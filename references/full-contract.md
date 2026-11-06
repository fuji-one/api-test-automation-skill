---
name: api-automation-pipeline-suite
description: Run a self-contained, gated Chinese API automation pipeline from either complete PRD/API/system-analysis/data-model documents or Java source code into design cases, execution-level cases, and pytest+allure scripts. Use when Codex needs one bundled skill folder that includes the orchestrator plus local component skills for pre-document analysis, source API fact extraction, interface testcase generation, executable case generation, and API test framework generation, while preserving strict stage gates and final-script completion notices.
---

# API Automation Pipeline Suite

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

## Four-Stage Coverage Contract

The pipeline must preserve a 100% coverage response at every executed stage. A stage may stop with an explicit blocked or failed status, but it must never pass partial coverage downstream as acceptable.

Coverage denominator and base release conclusions come from the producer stage sidecars. Consumer stages may only perform stricter downstream mapping checks, such as design-case to executable-case mapping, executable-case to pytest nodeid mapping, or E2E flow nodeid mapping. If a consumer stage finds a more precise coverage or mapping gap, block the pipeline and require the producer stage to regenerate from its source inputs; do not redefine the producer coverage denominator in the consumer copy.

| 流水线阶段 | 目标 | 100% 覆盖准出要求 | 主要产物 |
|---|---|---|---|
| 阶段1：入口质检与测试点拆分 | 完成输入文件质检，形成可追溯测试点、覆盖对象、覆盖规则、业务场景映射和接口契约 | 文档入口必须证明前置质检通过、二阶段测试点拆分完整、业务场景映射可追溯、规则级覆盖率 100%、允许声明 100% 覆盖；当文档入口不满足时，源码入口作为替代主入口，必须证明源码事实抽取质检通过、源码契约/实现事实/源码可推断业务场景可追溯，并以源码抽取出的覆盖对象和规则作为阶段1覆盖分母 | `01_接口测试用例设计文档.md`、`02_接口结构化契约清单.md`、`03_skill执行报告.md`、`business_scenario_map.yaml`、`业务场景链路清单.md` |
| 阶段2：测试点生成测试用例 | 针对阶段1测试点生成设计级接口测试用例，并形成供人工检查的测试覆盖点报告 | 测试点、主要流程、契约规则、状态码和 P0/P1 对象覆盖率均为 100%，且无设计级阻塞项；设计级用例只依赖覆盖点、接口契约、源码/文档事实、真实业务场景和测试策略，不得因环境、账号、验证码、token、数据库当前数据、执行授权、外部沙箱或加密 key 缺失而阻塞；真实业务场景长链路必须先形成独立设计分母 `business_long_chain_cases.yaml`，并证明每个纳入分母的业务长链路都有 P0 设计级用例覆盖；若 `required_chain_flows.yaml` 含 required flows，长链路设计级用例还必须单独声明 `chain_scenario`、`chain_function`、`chain_process` 三类闭环覆盖分母和 100% 覆盖，并满足 `generated_design_chain_case_count == required_chain_flow_count`；人工覆盖点报告必须字段齐全、可映射设计级用例，并新增 `业务域` 字段；该报告仅作为人工复核材料，后续阶段不得把它作为强准入依赖 | `04_接口测试用例清单.md`、`case_list.yaml`、`business_long_chain_cases.yaml`、`业务长链路设计清单.md`、`测试覆盖点报告.md`、交接用 `case_list.yaml`、`测试用例清单.md`、`required_chain_flows.yaml`、`chain_flow_candidate_audit.yaml`、`business_scenario_map.yaml`、`业务场景链路清单.md`、`执行报告.md` |
| 阶段3：生成可执行测试用例 | 将设计级用例补齐为可重复执行的接口用例 | 每条设计级用例至少映射一条执行级用例，每条执行级用例保留 `覆盖对象ID`、`覆盖规则ID`、`设计级用例ID`、`追溯测试点`；若存在 required flows，执行级 `coverage_matrix.yaml` 必须单独证明长链路场景、功能、流程覆盖率均为 100%，并满足 `generated_executable_chain_case_count == required_chain_flow_count`，缺失执行事实时阻塞 | `执行级接口用例集.md`、`前置数据构造规则.md` |
| 阶段4：生成可执行代码 | 将执行级用例转换为 pytest+allure 工程，并把 `required_chain_flows.yaml` 中的 required flows 生成为可读 E2E flow 链路脚本 | 每条执行级用例映射到 pytest nodeid；每个 required flow 必须映射到独立 E2E flow pytest nodeid；`chain_script_coverage` 必须以 `long_chain_only` 为分母单独证明长链路场景、功能、流程覆盖率均为 100%，并满足 `generated_pytest_flow_count == required_chain_flow_count`；pytest 收集用例数等于执行级用例数加 E2E flow 数；覆盖规则全部有 pytest 映射；可执行分母必须完成 setup/cleanup 物化，`cleanup_refs` 或 DB before/after 引用不能替代可执行清理；若脚本使用运行时取证候选、运行时值目录或补充请求证据，必须通过 runtime-evidence 到脚本物化审计，确保请求明文字段、角色变量、逐步骤期望业务码/消息和 evidence_id 未被转换丢失；最终留档用例台账必须覆盖同一执行分母并记录明文业务入参/出参；不得只生成单接口脚本后声明链路已覆盖；不得以 `business_scenario_map.yaml` 或 `测试覆盖点报告.md` 的长链路摘要作为脚本准入分母 | `api-test-framework/`、`configs/input_precheck_report.yaml`、`configs/generation_status.yaml`、`configs/runtime_evidence_script_mapping_audit.yaml`、`接口案例.md`、按需 `缺陷列表.md`、`data/flow_cases.yaml` 或 `data/flow_cases.py`、`core/flow_runner.py`、`testcases/test_flows.py` |

For stages 1 and 2, require two machine-readable sidecars whenever the stage writes files and is used by a downstream stage:

- `stage_status.yaml`: stage status, `next_stage_allowed`, input/output paths, blocker list.
- `coverage_matrix.yaml`: coverage denominator, covered counts, missing IDs, and upstream/downstream ID mappings.

For every selected entry feeding stage 2, also require `business_scenario_map.yaml` and the auxiliary `业务场景链路清单.md`. These artifacts are the structured source for scenario traceability, roles, business domains, and E2E flow candidates. `测试覆盖点报告.md` may reference or losslessly adapt their scenario descriptions for human review, but downstream stages must consume `case_list.yaml`, `coverage_matrix.yaml`, and `required_chain_flows.yaml` for long-chain release instead of binding to report text. Stage 2 must block with `BLOCKED_NEED_BUSINESS_SCENARIO_MAPPING` when the selected entry lacks a passed business scenario map.

For source-route projects that use App transport encryption, require the source fact stage to produce `source_api_interface_encryption_policy` and `source-api-facts.json#project_encryption_policy`. This policy is a generalized classification mechanism, not a project-specific whitelist: it must distinguish health checks, internal service APIs, third-party callbacks, auth/login entries, app public APIs, and unknown channels by evidence-backed `channel_type`, `policy_hint`, `confidence`, and `reason_codes`. Downstream executable-case and framework-generation stages may treat `no_encrypt_candidate` as final only after user confirmation, gateway/client protocol evidence, or execution config confirmation. Interfaces with `requires_encryption_if_project_default_enabled` need request-encryption and response-decryption support when the project default says App APIs are encrypted. Interfaces with `policy_required` must block or request policy input; do not guess.

When `required_chain_flows.yaml` contains required flows, those flows form an independent coverage family. Long-chain scenario coverage, function coverage, and process coverage must each reach 100% with their own denominators. Do not combine long-chain coverage with single-interface or unit-style case counts to claim 100%.

## Business Scenario Long-Chain Design Denominator Contract

Stage 2 must distinguish two long-chain concepts:

- 业务场景长链路设计分母: the design-level denominator for real business scenarios that naturally span multiple interfaces or multiple ordered steps. It is used to ensure realistic scenario coverage and P0 design-case coverage.
- 可执行闭环必测分母: the execution/script denominator in `required_chain_flows.yaml`, used only when evidence proves pre-action, observable change, verification, link keys, ordered steps, and source refs.

Do not collapse these two denominators. A source-inferred business scenario may be a valid design-level long-chain even when it lacks enough runtime link keys or execution facts for pytest E2E flow generation. Conversely, a closed-loop required flow must always be included in the design-level long-chain denominator.

Business long-chain discovery must start from business meaning, not from endpoint topology. Enumerate candidates by:

- 业务域: account, payment, wallet, subscription, onboarding, identity, interaction, messaging, relationship, review, operation, or any domain evidenced by PRD/API/system analysis/source facts.
- 执行角色: user, merchant, operator, partner, admin, internal scheduler, callback provider, or another source-evidenced actor.
- 业务目标: what the actor is trying to finish, undo, verify, settle, configure, publish, notify, consume, or recover.
- 对象生命周期: statuses, state transitions, creation/update/activation/expiration/cancel/refund/withdraw/review/feedback/cleanup paths.
- 跨接口副作用: DB status/amount/relationship/content/task changes, message/callback/MQ effects, permission changes, quota changes, and follow-up reads.
- 用户旅程 and operation journeys: login-to-token, onboarding-to-review, subscribe-to-service, request-to-feedback, recharge-to-ledger, create-to-query, block-to-unblock, publish-to-read, callback-to-state, withdraw-to-record.

A candidate may enter `business_long_chain_cases.yaml` only when all of these are true:

- It describes a real Chinese business scenario with `执行角色 + 业务动作 + 前置业务状态 + 预期业务结果/价值`.
- It has a coherent business object or lifecycle, or an explicit cross-domain business process, not just a shared URL prefix, controller package, API module, or arbitrary route grouping.
- It contains at least 3 related interfaces, or at least 5 ordered business steps. A verification/read step may count only when it proves a before/after business meaning.
- It has source refs, related test point IDs, related coverage rule IDs, and a P0 design-level case ID.
- It records whether execution is ready: `closed_loop_required` only when it also exists in `required_chain_flows.yaml`; otherwise use `need_execution_input`, `manual_confirm_required`, `not_required`, or another allowed non-script-required status.
- It has `confidence=high/medium` evidence in the upstream scenario map or source facts. Low-confidence scenarios must block or stay out of the passed denominator.

Reject endpoint buckets, then try to split them into real business chains before blocking:

- Treat path or prefix chains such as `/api/v1/**`, `/app/**`, `/internal/**`, `Controller` package groupings, or `模块接口串联` as invalid denominator rows. Do not pass them through as business long chains.
- Before stopping, inspect the same evidence and split the bucket into real business chains when source/doc facts support actor, business object, action, state or record change, and verification. A valid split may reuse endpoints from the rejected bucket, but the new chain name and description must be business-first rather than prefix-first.
- Keep source-evidenced two-interface scenarios with clear business meaning as design-level short-chain or state-transition cases, even when they do not meet the business long-chain threshold. Do not delete them. Do not count them in `business_long_chain_cases.yaml` unless they naturally reach at least 3 related interfaces or at least 5 ordered business steps.
- If a two-interface scenario has a natural read/verification endpoint already evidenced, add that endpoint and upgrade it only when the resulting chain remains a real business process. Never add arbitrary reads only to satisfy the threshold.
- Generic labels such as `接口集合`、`API链路`、`平台接口`、`资源从业务处理到结果校验` are audit signals, not release-ready chain names.
- Reject arbitrary permutations created only to increase the count.
- Reject flows without a business actor, object lifecycle, source refs, or observable business result.

Useful source-backed chain archetypes include:

- 账户钱包：商品列表 -> 充值下单 -> 支付验签 -> 钱包/钻石流水查询。
- 女性提现：查询提现账户 -> 绑定账户 -> 申请提现 -> 执行提现 -> 查询记录或汇总。
- 女性入驻审核：查询入驻状态 -> 提交人脸照/资料/身份/活体 -> 审核通过或拒绝 -> 查询状态。
- 订阅服务：订阅档位列表 -> 创建订阅 -> 查询订阅 -> 激活权益或生成任务 -> 状态任务处理。
- 即时通讯：消息发送前校验 -> 发送私信 -> 会话列表/详情 -> 标记已读 -> 删除会话。
- 通话互动：通话前校验 -> 发起通话 -> 查询状态 -> RTC/IM 回调 -> 计费 -> 结算事件处理。
- 动态内容：发布动态 -> 列表浏览 -> 详情查询。
- 安全治理：拉黑 -> 查询黑名单 -> 解除拉黑 -> 再次查询。

Useful design-level short-chain or state-transition archetypes include:

- 账号注销 -> 撤销注销。
- 短信发送 -> 短信登录。
- 登录 -> 登出。
- 举报类型查询 -> 提交举报。
- 用户反馈提交 -> 反馈列表查询。
- 资料更新 -> 资料详情查询。
- 音频上传 -> 音频列表查询。
- 服务配置变更 -> 配置列表查询。
- 通话状态变更 -> 通话状态查询。

Stage 2 must write both machine and human views:

```yaml
schema_version: 1
stage: business_long_chain_design_denominator
status: passed
next_stage_allowed: true
denominator_scope: business_scenario_long_chain_design
business_long_chain_total: 1
business_long_chain_covered: 1
script_closed_loop_ready_total: 0
missing_business_long_chain_ids: []
chains:
  - chain_id: BLC-001
    case_id: DC-LC-001
    priority: p0
    business_domain: 账户认证
    scenario_name: 短信验证码登录后获取聊天令牌
    business_description: 用户作为账号持有人在短信验证码登录成功后获取个人资料并申请聊天令牌，保证后续会话能力可用
    executing_role: 用户
    chain_kind: user_journey | lifecycle | callback | settlement | operation | configuration | recovery
    interface_count: 3
    step_count: 3
    interfaces:
      - POST /api/v1/user/sendSms
      - POST /api/v1/user/smsLogin
      - GET /api/v1/user/chatToken
    source_refs:
      - source-api-facts.json#API-001
    related_test_point_ids:
      - TP-001
    related_coverage_rule_ids:
      - RULE-001
    required_flow_id: ""
    design_status: covered
    executable_status: need_execution_input
blocking_issues: []
```

`business_long_chain_total == business_long_chain_covered`, `missing_business_long_chain_ids=[]`, and every chain must map to a P0 design case in `case_list.yaml`. If no design-level business long chain is supported by source evidence, write `business_long_chain_total: 0`, `business_long_chain_covered: 0`, `chains: []`, and state `不涉及`; do not claim `0/0` coverage.

`业务长链路设计清单.md` is the reviewer-facing projection of the sidecar. It must include at least `长链路ID`、`设计级用例ID`、`业务域`、`业务场景`、`执行角色`、`接口链路`、`来源`、`覆盖状态`、`可执行状态`.

## Required Chain Flow Denominator Contract

Long-chain 100% coverage must switch to the unified closed-loop denominator in `required_chain_flows.yaml`. Existing long-chain artifacts, `business_scenario_map.yaml`, interface-count rules, and step-count rules remain compatibility evidence and candidate discovery signals only; they are not the authoritative denominator for long-chain 100% release.

The closed-loop criterion is evidence-based, not template-based:

```text
前序业务动作 -> 可观察状态/数据/金额/关系/权限/内容/任务变化 -> 后序查询或消费验证
```

If the document route or source route can prove all three parts, the flow must enter `required_chain_flows.yaml`. A candidate can be excluded only for evidence insufficiency or pure read-only behavior, never because it is outside a predefined business template.

Candidate reclassification must separate business coverage from executable closed-loop readiness. Do not classify all non-required business scenarios as `excluded_readonly` only because they are not selected into `required_chain_flows.yaml`. For every scenario candidate from `business_scenario_map.yaml`, assign exactly one downstream path:

- `included`: closed-loop evidence is complete and the flow must enter `required_chain_flows.yaml`.
- `design_long_chain_only`: a real multi-interface or 5-step business chain exists, but execution closure evidence such as verification endpoint, observable DB/status change, link key, account state, external sandbox, or runtime evidence is incomplete. Keep it in `business_long_chain_cases.yaml` with `executable_status: need_execution_input` or `manual_confirm_required`.
- `design_short_chain_state_transition`: a meaningful two-interface or short state-transition scenario exists, such as 账号注销 -> 撤销注销, 登录 -> 登出, 举报类型查询 -> 提交举报, 通话状态变更 -> 状态查询. Keep it as design-level short-chain/state-transition coverage and generate executable cases when ordinary execution facts are available; do not force it into the long-chain denominator.
- `single_interface_mutation`: one interface carries a create/update/delete/status-change/business-submit behavior. Keep it as single-interface design/executable coverage and require DB/assertion/cleanup evidence when mutating.
- `single_interface_readonly`: one interface is a true query/list/config/status-read scenario. Keep it as single-interface design coverage; it may become executable as a read-only case, but it is not a closed-loop long-chain flow.
- `external_or_callback`: the scenario depends on third-party callbacks, payment/settlement, scheduler jobs, internal service triggers, uploads, risk-control, Apple/Google/SMS, or another external actor. Keep it as a scenario with sandbox/mock/callback/manual evidence requirements; do not mark it `excluded_readonly`.
- `excluded_missing_verification`, `excluded_missing_change_evidence`, or `excluded_missing_link_key`: use only when the candidate appears to be a closed-loop candidate but lacks the named proof. Record the missing proof and do not pass it downstream as required.
- `excluded_readonly`: use only for genuinely read-only route buckets or scenarios whose business result is only observing current state and has no setup/action/change/verification chain. The reason must mention the actual read-only evidence, not a generic statement such as "已纳入设计级覆盖".

Reclassification must preserve all candidates in `chain_flow_candidate_audit.yaml` with `classification`, `downstream_target`, `scenario_id` or `flow_id`, source refs, and a specific reason. If a previously excluded candidate has create/update/delete/status-change/callback/submit semantics, reclassify it into the proper downstream path before declaring coverage.

Both entry routes must produce the same denominator artifacts before stage 2 is allowed:

- Document route: PRD + API + 系统分析 + 数据模型 evidence -> `required_chain_flows.yaml` and `chain_flow_candidate_audit.yaml`.
- Source route: Controller + Service + Mapper/Repository + status enum/constant + DB side effect/query evidence -> `required_chain_flows.yaml` and `chain_flow_candidate_audit.yaml`.
- When both routes are executed, also produce `chain_flow_alignment.yaml` and classify differences as `doc_only`、`source_only`、`both_step_diff`、`both_consistent`. Do not silently drop `doc_only` or `source_only` flows when their closed-loop evidence is complete.

`required_chain_flows.yaml` is a root-level pipeline artifact and the only authoritative denominator for required long-chain coverage:

```yaml
schema_version: 1
stage: required_chain_flow_denominator
status: passed | blocked
next_stage_allowed: true | false
required_chain_flow_count: 1
unclassified_candidate_flows: []
flows:
  - flow_id: FLOW-001
    source_route: doc | source
    evidence_routes: [doc, source]
    business_domain: 账户钱包
    scenario_name: 充值下单验签到钱包明细链路
    pre_action:
      interface: POST /api/v1/account/recharge/createOrder
    observable_change:
      type: amount_change
      evidence: 钱包余额或钻石流水发生变化
    verification:
      interface: POST /api/v1/account/wallet/diamond-records
    link_keys:
      - userId
      - orderId
    steps:
      - POST /api/v1/account/product/productList
      - POST /api/v1/account/recharge/createOrder
      - POST /api/v1/account/recharge/verify/googlePay
      - POST /api/v1/account/wallet/diamond-records
    evidence_refs:
      - PRD章节/API接口/源码文件/表字段
    status: required
blocking_issues: []
```

`chain_flow_candidate_audit.yaml` must classify every discovered closed-loop candidate:

```yaml
schema_version: 1
stage: chain_flow_candidate_audit
status: passed | blocked
next_stage_allowed: true | false
candidate_summary:
  included: 1
  design_long_chain_only: 0
  design_short_chain_state_transition: 0
  single_interface_mutation: 0
  single_interface_readonly: 0
  external_or_callback: 0
  excluded_missing_verification: 0
  excluded_missing_change_evidence: 0
  excluded_missing_link_key: 0
  excluded_readonly: 0
  unclassified: 0
candidates:
  - candidate_id: CAND-001
    classification: included | design_long_chain_only | design_short_chain_state_transition | single_interface_mutation | single_interface_readonly | external_or_callback | excluded_missing_verification | excluded_missing_change_evidence | excluded_missing_link_key | excluded_readonly
    flow_id: FLOW-001
    scenario_id: BS-001
    source_route: doc | source
    downstream_target: required_chain_flows | business_long_chain_cases | design_short_chain_or_state_transition_case | single_interface_design_and_executable_case | single_interface_design_case | external_dependency_or_callback_evidence | blocked_need_verification_evidence | blocked_need_change_evidence | blocked_need_link_key_or_ordered_steps | not_required_as_closed_loop_flow
    evidence_refs: ["..."]
    reason: "..."
unclassified_candidate_flows: []
blocking_issues: []
```

Long-chain 100% may only be declared when all formulas are true:

```text
required_chain_flow_count == generated_design_chain_case_count
required_chain_flow_count == generated_executable_chain_case_count
required_chain_flow_count == generated_pytest_flow_count
missing_required_flow_ids == []
unclassified_candidate_flows == []
```

If `required_chain_flow_count` is 0, the pipeline may say no evidence-backed required long-chain flow was found, but it must not claim `0/0` long-chain 100% coverage. Existing long-chain products do not need to be modified, migrated, or re-counted; they are only evidence inputs for the new denominator.

For source-entry runs targeting `executable` or `framework`, a missing user-provided `数据模型.md` is not an immediate blocker. After `$source-api-fact-extractor` completes, first check whether an available database MCP can read the target database identity and metadata; only when database MCP is unavailable, unreadable, identity cannot be matched, schema/relationship/setup/cleanup evidence cannot be generated, or source-DB alignment fails may the run stop before executable filling. Database MCP should read metadata first: database, schema, table, column, index, constraint, comment, and relationship evidence; row data may be read only when the user explicitly authorizes runtime evidence or DB before/after probing. The database MCP connection is evidence, not a downstream dependency: it must produce `00-inputs/数据模型.md`, `00-inputs/database_mcp_evidence_index.yaml`, `00-inputs/source_db_alignment.yaml`, and `00-inputs/source_db_alignment_report.md`; downstream stages consume only the normalized files. If no available MCP can be used, record the attempted connector/tool/environment and blocker reason in `00-inputs/source_db_alignment_report.md` or `00_流水线执行报告.md`. If source DB facts and MCP schema conflict, stop before executable filling with `FAILED_EXECUTION_READINESS`; if MCP access or evidence is missing after the required check, stop with `BLOCKED_NEED_EXECUTION_INPUT`.

`数据模型.md` is execution-ready only when it contains both table structure and a lightweight table knowledge graph for setup/cleanup: table names, columns, primary/unique keys, required/default fields, status enums, logical-delete fields, ownership keys, parent-child relationships, setup order, cleanup reverse order, and cleanup boundaries. When the database has no declared foreign keys, infer candidate edges only from source-visible DB side effects, field names, indexes, comments, and repository joins, and label them as inferred. If the graph, ownership key, or cleanup order cannot be determined for a table used by executable setup/cleanup, block before `$executable-interface-case-set`; do not pass a field-list-only data model downstream. A section title or keyword alone is not enough: content such as `缺失`、`待补充`、`待确认`、`未知`、`不详`、`暂无`、`TBD`、`UNKNOWN` must be treated as missing execution evidence.

## Full Runtime Evidence Orchestration Contract

When the user asks for full execution-level case generation, broad executable coverage, or requester-backed runtime completion, the suite must add a runtime evidence planning gate before any direct request. This gate expands the design/execution denominator into a safe evidence plan instead of blindly calling every interface.

Runtime requester scope for required long chains:

- When `required_chain_flows.yaml` contains required flows and the user asks for requester-backed runtime completion, the runtime evidence plan must target full ordered-step coverage for every required flow, plus only the login/auth/setup/verification steps needed to execute those flows. Do not satisfy long-chain runtime evidence with a few convenient interfaces, and do not expand the scope to endpoints found only by broad route scanning.
- Each planned long-chain step must preserve `flow_id`, `step_order`, method/path, producer/consumer relation, link keys, source refs, risk decision, DB probe or cleanup requirement, and whether the step is requestable, externally mocked, callback-provided, manually confirmed, or blocked.
- Only `request_allowed` and `request_allowed_with_user_config` steps may be executed. External, callback, payment/settlement, destructive, or missing-cleanup steps must stay as blockers or manual/sandbox/mock/callback input items until their evidence is complete. Partial runtime evidence may help execution filling, but it must not mark the required flow passed.

Runtime evidence planning must produce `04-runtime-evidence-plan/` sidecars:

- `runtime_risk_audit.yaml`: every design or executable candidate is classified as `safe_readonly`、`auth_setup`、`mutation_requires_cleanup`、`destructive_state`、`external_or_callback`, or `unknown_requires_review`, with reason codes and source refs.
- `runtime_request_plan.skeleton.yaml`: only candidates with `request_decision=request_allowed` or `request_allowed_with_user_config` may appear as requester candidates; all credentials, base URLs, tokens, dynamic IDs, request bodies, and secrets remain runtime-injected placeholders.
- `db_before_after_probe_plan.yaml`: every mutating, destructive, or cleanup-dependent candidate records required DB before/after snapshot, ownership key, expected delta source, and cleanup strategy requirements.
- `runtime_blocker_candidates.yaml`: unsafe, external, destructive, missing-cleanup, or insufficiently traced candidates become blocker or manual confirmation items instead of guessed executable facts.

Classification must stay generalized. It may use HTTP method, path/name semantics, case type, contract channel type, source-visible DB side effects, dependency type, and cleanup evidence. It must not hardcode project-specific base URLs, phone numbers, accounts, user IDs, open IDs, tokens, app keys, AES keys, business codes, enum values, table names, or one-project-only status meanings. If a source artifact contains such values, copy them only into run-specific execution configuration or runtime evidence outputs with redaction rules; never add them to this skill.

Runtime execution configuration must be collected before requester-backed filling or execution-level release when environment, account, auth, or crypto facts are not fully source-bound:

- Use `components/executable-interface-case-set/assets/templates/runtime_execution_config.template.yaml` as the canonical user-facing template. The template must label fields with requiredness, conditional requiredness, and real meaning so users can fill it without reading this skill.
- When any required runtime section is missing, materialize the fillable package under `00-inputs/`: `runtime_execution_config.template.yaml`, `前置执行配置待填写.md`, and `runtime_execution_config.missing_fields.yaml` when the missing fields can be enumerated. The Markdown document must include these Chinese sections: 环境信息、模块 base URL 与网关前缀、账号与角色及业务状态、鉴权与 token 提取/注入、加解密策略、执行授权范围、DB before/after 与清理授权、外部依赖或沙箱/Mock、必填缺失字段清单、填写后继续条件。
- Continue only after the user returns a filled YAML, Markdown, or equivalent structured artifact whose required fields pass validation. Resume from execution readiness or execution-level filling; do not rerun source/design stages unless upstream source or design inputs changed.
- The environment section is always required for `executable` and `framework` targets: `env_name`, `is_test_environment`, module `base_url`, and gateway prefix must be filled or explicitly empty where the meaning allows an empty string.
- Account entries are required for every business role needed by selected cases or required flows, and each account must record its real business state, login method, identifier secret reference, and credential/token secret reference when applicable.
- Auth and transport-crypto configuration must identify login path, token source, token injection location/format, encryption enablement, algorithm reference, key source, request plaintext scope, request serialization, request envelope, and response envelope whenever encrypted interfaces are confirmed.
- If `environment.is_test_environment=true`, the case-scope default execution authorization and the generic source-bound DB before/after plus current-run cleanup authorization may be used when explicitly selected in the filled config.
- If `environment.is_test_environment=false`, any prior or default test-environment DB permission is invalid for this run. DB before/after queries, cleanup, rollback, or status recovery require fresh explicit non-test authorization in the filled config, including scope, environment, source-chain table boundary, ownership key boundary, and cleanup boundary. Without that reauthorization, keep DB operations and any facts depending on them blocked.
- Runtime execution configuration may contain real environment values and secret references, but runtime evidence and execution-level deliverables must redact passwords, tokens, Authorization, Cookie, raw secrets, and equivalent sensitive values.

Database MCP is used to build the full data model and cleanup graph, then to support before/after evidence collection when the user permits it. The generated scripts and executable-case stage may consume only normalized sidecars such as `数据模型.md`, `database_mcp_evidence_index.yaml`, `source_db_alignment.yaml`, `runtime_evidence.yaml`, and `runtime_value_catalog.yaml`; they must not keep live MCP database calls.

Source-to-database runtime evidence must close the loop before a mutating long-chain case can be marked executable:

- First extract the interface-to-table write/read scope from source evidence: Controller -> Service -> Repository/Mapper call chains, Mapper XML, annotated SQL, repository methods, and MyBatis/JPA entity table mappings.
- Then use database MCP to confirm the test-environment tables and columns exist and are compatible with the source-visible facts.
- Before executing the request or chain step, capture DB before snapshots only for the source-involved tables. After execution, capture DB after snapshots for the same scoped tables.
- Compare before/after deltas to confirm the real affected tables, changed fields, new business IDs, status transitions, amount changes, relationships, or records. Persist the request, response, DB refs, delta assertion, ownership key, cleanup evidence, and source refs into `runtime_evidence.yaml`.
- Do not rely on source analysis alone to claim a runtime DB side effect. Source analysis selects the candidate table scope; DB MCP and before/after deltas confirm what actually changed.

DB before/after and cleanup must use the minimal source-bound scope:

- Only inspect and clean tables explicitly involved by the current interface or required flow source chain: Controller -> Service -> Repository/Mapper, Mapper XML, annotated SQL, repository query/update methods, or entity table mappings. Do not scan or clean unrelated tables.
- Before/after query predicates must use the first available ownership key in this order: business ID returned by the current response, business ID in the current request, authenticated `userId`/`appUserId`, then a unique business key such as order number, conversation ID, idempotency key, or another source-evidenced unique value.
- If no ownership key or unique marker can be identified, block the DB probe or cleanup with `BLOCKED_NEED_EXECUTION_INPUT`; do not broaden the query scope.
- Cleanup may delete or restore only records created or changed by the current run. Prefer response-extracted IDs such as `id`、`orderId`、`messageId`、`auditId` or source-equivalent business IDs; otherwise require test account plus current-run unique marker.
- Cleanup order must follow the table relationship graph in reverse: child/detail/ledger/relation records before parent/order/master records. User, account, configuration, and other baseline tables must not be cleaned unless the current run created an isolated record and the ownership key is exact.
- High-risk domains such as payment, withdrawal, subscription, review, scheduler, callback, and settlement may be queried and cleaned only inside the current-run source-bound table scope and isolated ownership keys. Wide deletes such as deleting all rows by `userId` or other broad predicates are forbidden.
- A user or run configuration may grant the generic boundary "allow before/after queries and cleanup for source-chain involved tables, limited to current-run IDs or unique ownership keys"; this reduces manual confirmations but does not relax the ownership-key, delta, and cleanup-order gates.

Case-scope execution authorization may be configured once per run:

- When the user or run configuration explicitly declares that selected/generated test cases are executable by default and the target environment is test by default, treat only those case-scoped interfaces and ordered steps as execution-authorized. Record the declaration in `runtime_risk_audit.yaml` and `execution_fact_sources.yaml` as `source_type: user_config`.
- This default authorization removes per-interface manual execution confirmation for in-scope write, payment, withdrawal, subscription, review, scheduler, callback, and other mutating steps, but it does not permit blind execution outside the selected case denominator, production-like environments, or endpoints discovered only by broad route scanning.
- Even with default authorization, every executed step must still satisfy environment, auth, transport/encryption, external sandbox or mock input, source-bound DB before/after, ownership key, delta assertion, cleanup boundary, and redaction gates before it can be marked `PASSED`.
- If credentials, sandbox data, callback signatures, upload assets, ownership keys, DB delta, cleanup evidence, service responses, or source/DB alignment are missing or conflicting, keep the affected item blocked; do not use case-scope authorization to invent executable facts.

Direct requester execution is risk-gated:

- It may execute only the allowed items from `runtime_risk_audit.yaml`.
- For required long chains, execute allowed steps in business order and persist both step-level request/response evidence and the producer-to-consumer value derivations. The requester should attempt every requestable ordered step in the required flow before declaring the runtime evidence scope complete.
- Use real responses as evidence for inference, not as mechanical literals. Compare producer response fields, required-flow link keys, consumer request schema, authenticated account context, source contract semantics, and DB ownership keys to infer current request inputs, downstream request inputs, and expected next-response/assertion candidates. If the business meaning does not match or multiple candidates remain plausible, block the derivation instead of filling a value.
- Mutating requests require an isolated ownership key, DB before/after probe plan, cleanup strategy, and explicit user or run configuration confirmation before execution. A run-level case-scope execution authorization satisfies the confirmation requirement only for the selected case denominator in the configured test environment.
- External callbacks, payment/settlement-like actions, destructive state changes, and missing-cleanup cases must be blocked or routed to manual confirmation.
- Each executed interface must produce `runtime_evidence`: request reference, response reference, extracted variables, assertions, redaction status, source refs, and when DB evidence is used, `db_before_ref`、`db_after_ref`、`db_delta_assertion`、`db_probe_source_ref`.
- `$executable-interface-case-set` may mark execution facts `PASSED` only when evidence is closed: request/response evidence confirmed, variable links resolved, assertions source-bound, DB before/after/cleanup evidence present when required, and conflict lists empty. Otherwise it must emit `BLOCKED_NEED_EXECUTION_INPUT` or manual confirmation items.

### Runtime Evidence Continuation And Priority Policy

Requester-backed supplementation must be queue-driven, not stop-on-first-gap. When the user asks to supplement broad execution-level cases, requested observations, or all runnable candidates, maintain a continuation queue in `04-runtime-evidence/runtime_stage_status.yaml.continuation_queue`; when the queue is large, also write the same queue to optional `04-runtime-evidence/runtime_evidence_queue.yaml`. Each candidate or ordered chain step must record `case_id` or `flow_id + step_order`, `priority_bucket`, `queue_state`, `last_attempt`, `next_action`, `reason_code`, and `evidence_refs`.

Queue states are operational states, not overall pipeline statuses: `pending`、`requested`、`evidenced`、`retryable`、`skipped_recoverable`、`blocked_final`、`excluded`. Queue items must use `queue_state`; do not use a nested `status` field inside `continuation_queue.items` or `runtime_evidence_queue.yaml.items`, because `status` is reserved for stage-level sidecars. A single item in `retryable` or `skipped_recoverable` must not stop the whole runtime-evidence stage while other actionable items remain. Stop only when no `pending`、`retryable` or `skipped_recoverable` item remains, or when every remaining item is a true blocker or excluded by scope.

Supplement runtime evidence in this priority order:

1. Required or real-business long chains first. Execute every requestable ordered step in each business flow, close producer-to-consumer variables, assertions, DB before/after evidence, and cleanup boundaries, then reuse the confirmed step evidence for related single-interface candidates.
2. `p0` single-interface or branch cases after long-chain closure, prioritizing auth/setup/read-only prerequisites before mutating cases that need cleanup.
3. `p1` cases after `p0` actionable items are exhausted.
4. `p2` cases after `p1` actionable items are exhausted.
5. `p3` and low-value leftovers last, unless the user narrows the requested scope.

Within the same priority bucket, prefer cases whose request structure, auth, encryption, upstream variables, data model, DB ownership key, assertions, and cleanup strategy are already source-bound. For mutating cases, only execute after the source-bound DB before/after probe plan and current-run cleanup boundary are available.

These are not runtime-evidence blockers by themselves and must become `retryable` or `skipped_recoverable` while the queue continues: runtime evidence has not been generated yet; one case fails while other cases remain; one subset lacks assertion or DB before/after evidence; a request returns an unexpected 200 or 500 and needs defect triage; an input value is missing but source, DB MCP, requester response, bounded mock, precondition API, or execution configuration can still be tried; a single candidate is temporarily not requestable.

True runtime-evidence blockers are narrower: execution authorization is missing for the selected denominator; required environment/account/auth/crypto configuration is still absent after the fillable package is produced; the item is outside the selected case or required-flow scope; the item is external/callback/payment/destructive and lacks sandbox, mock, signed callback, ownership, or cleanup evidence; DB MCP/source/data-model evidence cannot provide the required model, ownership key, assertion, or cleanup boundary; source/contract/runtime/DB evidence conflicts; or a gate explicitly forbids continuing.

When an item cannot be solved immediately, write the attempted methods and the exact unresolved reason, mark it `skipped_recoverable` or `blocked_final` as appropriate, and continue with the next item in priority order. Do not convert unresolved items into guessed request fields, guessed response assertions, broad DB seeds, or product defects. Unexpected 200/500 results become defect candidates only after the request payload, response payload, role/session, data state, and DB before/after evidence prove the generated script or request materialization is not the cause.

Use `scripts/build_runtime_evidence_plan.py` when a deterministic helper is useful:

```bash
python3 <skill_dir>/scripts/build_runtime_evidence_plan.py \
  --case-list 04-design-case-handoff/case_list.yaml \
  --output-dir 04-runtime-evidence-plan \
  --env-name test
```


## Structured Sidecar Schemas

All stage decisions must be based on machine-readable sidecars first. Markdown reports remain human-facing evidence and may be used as a compatibility check, but they must not be the only source for pass/fail decisions once a sidecar exists.

### `stage_status.yaml`

Required for every executed stage directory.

```yaml
schema_version: 1
stage: pre_doc_analysis | source_api_facts | interface_testcase_generation | executable_interface_case_set | script_generation
status: passed | blocked | failed | coverage_insufficient
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

`status=passed` requires `next_stage_allowed=true` and `blocking_issues=[]`. Any blocked or failed status must keep `next_stage_allowed=false` and list source-bound blockers.

### `retry_history.yaml`

Required whenever a downstream gate asks an upstream stage to regenerate, and mandatory when the pipeline ends with `BLOCKED_RETRY_EXHAUSTED`.

```yaml
schema_version: 1
status: retrying | resolved | blocked
max_attempts: 3
next_stage_allowed: true | false
retry_key: "producer_stage->consumer_stage:gate_id"
gate_id: "..."
consumer_stage: interface_testcase_generation | design_case_handoff | executable_interface_case_set | script_generation
producer_stage: pre_doc_analysis | source_api_facts | interface_testcase_generation | executable_interface_case_set
final_blocker: "..."
attempts:
  - attempt: 1
    retry_key: "producer_stage->consumer_stage:gate_id"
    gate_id: "..."
    producer_stage: "..."
    consumer_stage: "..."
    reason: "..."
    regenerated_output_paths: ["..."]
    gate_result: passed | blocked | failed | coverage_insufficient
    gate_evidence_refs: ["..."]
```

Rules:

- Attempt count starts at 1 and may not exceed 3 for the same `retry_key`.
- `retry_key` is stable for the same producer stage, consumer stage, failed gate, and blocking contract type. Reworded blocker text, regenerated filenames, or a new timestamp must not create a new retry key.
- Before starting any retry, read the existing `retry_history.yaml`. If the same `retry_key` already has 3 attempts or `status: blocked`, stop immediately with `BLOCKED_RETRY_EXHAUSTED`.
- `retry_history.yaml` is append-only for the same `retry_key`: do not delete, renumber, overwrite, or reset earlier attempts after regeneration.
- Every retry must regenerate the producer stage output from its source inputs; do not patch only the downstream copy.
- After a retry passes, all downstream stages must consume only the latest regenerated files and discard earlier attempts as non-authoritative.
- If attempt 3 still cannot satisfy the consumer gate, stop the whole pipeline with `BLOCKED_RETRY_EXHAUSTED`; do not continue to later stages with partial files.
- Do not use this retry loop for missing external human inputs, missing environment/auth/data model, entry conflicts, or source evidence conflicts. Those states block directly with their existing status.

### `coverage_matrix.yaml`

Required for stages that claim coverage release or feed a downstream stage.

```yaml
schema_version: 1
stage: pre_doc_analysis | source_api_facts | interface_testcase_generation | executable_interface_case_set | script_generation
coverage_summary:
  denominator_scope: "..."
  coverage_rate: 100
long_chain_coverage_summary:
  required_when: "required_chain_flows.yaml contains required flows"
  denominator_scope: long_chain_only
  scenario_coverage_rate: 100
  function_coverage_rate: 100
  process_coverage_rate: 100
coverage_items:
  - coverage_id: "..."
    coverage_type: object | rule | test_point | main_flow | contract_rule | status_code | p0_p1 | design_case | executable_case | coverage_rule | pytest_nodeid | source_interface | source_contract_rule | source_business_rule | source_error_code | source_db_side_effect | source_scenario | chain_scenario | chain_function | chain_process
    status: covered | missing | conflict | blocked
    evidence_refs: ["..."]
missing_items: []
upstream_downstream_mappings:
  - upstream_id: "..."
    downstream_ids: ["..."]
    mapping_status: mapped | missing | conflict | blocked
```

For validator compatibility, the stage-specific count fields must also remain top-level:

| Stage | Required count fields | Required empty missing lists when passed |
|---|---|---|
| `pre_doc_analysis` | `object_total/object_covered`, `test_point_total/test_point_mapped`, `rule_total/rule_covered` | `missing_object_ids`, `missing_test_point_ids`, `missing_rule_ids` |
| `source_api_facts` | `source_interface_total/source_interface_covered`, `source_contract_rule_total/source_contract_rule_covered`, `source_business_rule_total/source_business_rule_covered`, `source_error_code_total/source_error_code_covered`, `source_db_side_effect_total/source_db_side_effect_covered`, `source_scenario_total/source_scenario_covered` | `missing_source_interface_ids`, `missing_source_contract_rule_ids`, `missing_source_business_rule_ids`, `missing_source_error_code_ids`, `missing_source_db_side_effect_ids`, `missing_source_scenario_ids` |
| `interface_testcase_generation` | `test_point_total/test_point_covered`, `main_flow_total/main_flow_covered`, `contract_rule_total/contract_rule_covered`, `status_code_total/status_code_covered`, `p0_p1_total/p0_p1_covered`; when required flows exist, also `chain_scenario_total/chain_scenario_covered`, `chain_function_total/chain_function_covered`, `chain_process_total/chain_process_covered` with `denominator_scope: long_chain_only` | `missing_test_point_ids`, `missing_main_flow_ids`, `missing_contract_rule_ids`, `missing_status_codes`, `missing_p0_p1_ids`; when required flows exist, also `missing_chain_scenario_ids`, `missing_chain_function_ids`, `missing_chain_process_ids` |
| `executable_interface_case_set` | `design_case_total/design_case_mapped`, `executable_case_total/executable_case_traced`, `coverage_rule_total/coverage_rule_mapped`; when required flows exist, also `chain_scenario_total/chain_scenario_covered`, `chain_function_total/chain_function_covered`, `chain_process_total/chain_process_covered` with `denominator_scope: long_chain_only` | `missing_design_case_ids`, `missing_executable_trace_ids`, `missing_coverage_rule_ids`; when required flows exist, also `missing_chain_scenario_ids`, `missing_chain_function_ids`, `missing_chain_process_ids` |

For `status=passed`, every required denominator total must be greater than 0. Non-legacy `coverage_items` must contain exactly one unique `coverage_id` for each denominator item by `coverage_type`, each item must be `status: covered` with non-empty `evidence_refs`, and `upstream_downstream_mappings` must contain a `mapped` record for every `coverage_id`. A `0/0` coverage claim is invalid.

For `pre_doc_analysis`, validators also accept the native `$pre-doc-analysis-pipeline` sidecar shape as a compatibility input: `stage_status.yaml` may use `source_files`、`stage_results`、`output_files`, and `coverage_matrix.yaml` may use `coverage_objects`. This compatibility does not relax status, `next_stage_allowed`, blocking issue, coverage count, or missing-list gates.

### `business_scenario_map.yaml`

Required for the selected entry before stage 2, regardless of document-entry or source-entry route.

```yaml
schema_version: 1
stage: business_scenario_mapping
status: passed | blocked | partial
next_stage_allowed: true | false
source_entry: doc | source
scenario_source_status: doc_confirmed | source_inferred
scenario_items:
  - scenario_id: "BS-001"
    scenario_name: "用户完成支付单支付"
    business_domain: "统一支付"
    executing_role: "用户"
    business_description: "用户作为支付发起方在业务系统下单后进入统一支付，系统创建支付单、发起支付并回查支付结果，验证支付单从创建到支付完成的业务链路"
    roles: ["用户", "统一支付系统"]
    source_refs: ["PRD.md#支付流程", "API.md#支付接口", "系统分析.md#支付状态流转"]
    related_interfaces: ["创建支付单接口", "支付单支付接口", "查询支付单接口"]
    business_chain: ["创建支付单", "发起支付", "查询支付结果"]
    state_chain: ["待支付", "支付中", "支付完成"]
    related_test_point_ids: ["TP-001"]
    related_coverage_rule_ids: ["RULE-001"]
    chain_type: single_interface | e2e_flow_candidate
    flow_generation_required: true | false
    flow_id: "FLOW-001"
    ordered_step_count: 3
    ordered_steps:
      - step_order: 1
        api_id: "API-001"
        interface: "创建支付单接口"
        test_point_id: "TP-001"
        source_ref: "API.md#创建支付单"
    confidence: high | medium | low
    blockers: []
blocking_issues: []
```

Gate:

- `status=passed`, `next_stage_allowed=true`, `scenario_items` 非空，`blocking_issues=[]`.
- Each scenario item must have non-placeholder `scenario_id`、`scenario_name`、Chinese `business_domain`、Chinese `executing_role`、Chinese `business_description`、`roles`、`source_refs`、`related_interfaces`、`business_chain`、`related_test_point_ids`、`related_coverage_rule_ids` and `blockers=[]`.
- `business_description` must explicitly include the `executing_role` and explain what that role does in the business process. Single-interface or unit-style scenarios must still use the same description standard as long-chain scenarios: `执行角色 + 业务动作 + 前置业务状态 + 结果或价值`, not only an API name or test method.
- Multi-interface scenarios should set `chain_type: e2e_flow_candidate`, `flow_generation_required: true`, stable `flow_id`, `ordered_step_count >= 2`, and ordered step records when the source evidence already identifies them as E2E flow candidates. If a scenario has `related_interfaces` count >= 3, `ordered_step_count >= 5`, `business_chain` step count >= 5, or `state_chain` step count >= 5`, validators may treat it as candidate discovery evidence, but it is not the authoritative required-flow denominator. Whether it becomes required depends on `required_chain_flows.yaml` and closed-loop evidence.
- Document entry should use `source_entry: doc` and `scenario_source_status: doc_confirmed`.
- Source entry should use `source_entry: source` and `scenario_source_status: source_inferred`; source-inferred business descriptions are acceptable only when they are traceable to source facts and `confidence` is `medium` or higher.
- `confidence=low` or unresolved blockers must stop stage 2 with `BLOCKED_NEED_BUSINESS_SCENARIO_MAPPING`.
- `业务场景链路清单.md` is the human-readable view of this sidecar and must not contain rows that are absent from `business_scenario_map.yaml`.

### `database_mcp_evidence_index.yaml`

Required under `00-inputs/` whenever a database MCP connection is used to generate or enrich `数据模型.md`.

```yaml
schema_version: 1
stage: database_mcp_data_model_normalization
status: passed | partial | blocked | failed
mcp_connection:
  connector_name: "database_mcp"
  database_product: "mysql | postgresql | other"
  host_ref: "masked host or environment alias"
  database_name: "..."
  schema_name: "..."
  source_status: confirmed | missing | conflict | blocked
evidence_items:
  - evidence_id: "DB-MCP-001"
    evidence_level: database_identity | table_schema | column_schema | index_constraint | foreign_key | relationship_graph | cleanup_key | ownership_boundary | sample_forbidden
    mcp_ref: "database/schema/table/column/index"
    supports: ["database", "schema", "table", "column", "type", "nullable", "default", "primary_key", "unique_key", "index", "relationship", "setup_order", "cleanup_order", "ownership_key", "cleanup_key"]
    source_status: confirmed | missing | conflict | blocked
conflict_items: []
blocking_issues: []
```

`status=passed` requires the MCP connection identity to be confirmed, all evidence items needed by source-visible DB side effects to be confirmed, and `conflict_items=[]` plus `blocking_issues=[]`. Do not record raw passwords, tokens, or full connection strings.

### `source_db_alignment.yaml`

Required under `00-inputs/` whenever database MCP evidence is used. It is the gate that proves the connected database matches the extracted source facts before `数据模型.md` can feed executable cases or scripts.

```yaml
schema_version: 1
stage: database_mcp_data_model_normalization
status: passed | blocked | failed
next_stage_allowed: true | false
source_fact_ref: "02-source-api-facts/docs/source-facts/source-api-facts.json"
database_evidence_ref: "00-inputs/database_mcp_evidence_index.yaml"
normalized_data_model_ref: "00-inputs/数据模型.md"
connection_identity:
  source_config_refs: ["application.yml#spring.datasource.url"]
  mcp_database_name: "..."
  mcp_schema_name: "..."
  confirmation_status: confirmed | missing | conflict | blocked
alignment_checks:
  - check_id: datasource_identity
    status: passed | blocked | failed
    evidence_refs: ["..."]
  - check_id: table_mapping
    status: passed | blocked | failed
    evidence_refs: ["..."]
  - check_id: column_mapping
    status: passed | blocked | failed
    evidence_refs: ["..."]
  - check_id: key_constraint_mapping
    status: passed | blocked | failed
    evidence_refs: ["..."]
  - check_id: relationship_graph_mapping
    status: passed | blocked | failed
    evidence_refs: ["..."]
  - check_id: seed_cleanup_strategy
    status: passed | blocked | failed
    evidence_refs: ["..."]
  - check_id: side_effect_mapping
    status: passed | blocked | failed
    evidence_refs: ["..."]
missing_tables: []
missing_columns: []
incompatible_columns: []
unresolved_side_effects: []
unresolved_relationships: []
missing_cleanup_keys: []
blocking_issues: []
```

`status=passed` requires `next_stage_allowed=true`, confirmed connection identity, source-referenced tables present in MCP schema, source-referenced columns type-compatible with MCP columns, required primary/unique/cleanup keys identified, source-visible DB side effects mapped, setup/cleanup graph edges resolved for all executable setup/cleanup tables, and all missing/conflict/blocking lists empty.

### `runtime_risk_audit.yaml`

Required under `04-runtime-evidence-plan/` when full runtime evidence planning is executed.

```yaml
schema_version: 1
stage: runtime_evidence_planning
status: passed | blocked | failed
next_stage_allowed: true | false
risk_summary:
  safe_readonly: 0
  auth_setup: 0
  mutation_requires_cleanup: 0
  destructive_state: 0
  external_or_callback: 0
  unknown_requires_review: 0
request_decision_summary:
  request_allowed: 0
  request_allowed_with_user_config: 0
  manual_confirmation_required: 0
  blocked_until_isolated_account_and_cleanup: 0
execution_authorization:
  case_scope_default_authorized: false
  environment_default: "test"
  env_name: ""
  is_test_environment: true
  scope: "selected_case_denominator"
  source_type: "user_config | none"
  source_ref: ""
db_authorization:
  allow_source_bound_before_after_query: false
  allow_current_run_cleanup: false
  non_test_reauthorization_required: false
  non_test_reauthorization_status: not_required | provided | missing
  source_ref: ""
classification_policy:
  source_signals: ["http_method", "path_semantics", "case_name_semantics", "case_type", "source_side_effect_hints"]
  project_specific_values_allowed: false
  blind_all_interface_execution_allowed: false
items:
  - item_id: "RISK-0001"
    case_id: "DC-001"
    name: "..."
    priority: "p0"
    case_type: "normal | exception | chain | ..."
    module: "..."
    method: "GET"
    path: "/..."
    risk_level: safe_readonly | auth_setup | mutation_requires_cleanup | destructive_state | external_or_callback | unknown_requires_review
    request_decision: request_allowed | request_allowed_with_user_config | manual_confirmation_required | blocked_until_isolated_account_and_cleanup
    reason_codes: ["..."]
    cleanup_required: false
    db_probe_required: false
    source_case_ref: "case_list.yaml#/cases/0"
```

`status=passed` means classification completed, not that all interfaces are executable. Runtime execution may proceed only for items whose `request_decision` permits requesting.

### `runtime_request_plan.skeleton.yaml`

Optional planning output under `04-runtime-evidence-plan/`; it is not the executable request plan consumed by the requester until runtime values and user configuration are filled.

```yaml
schema_version: 1
stage: runtime_request_plan_skeleton
status: ready_for_manual_completion | blocked_no_allowed_request
next_stage_allowed: false
env:
  env_name: test
  base_urls: {}
  secrets_ref: "${RUNTIME_SECRETS_JSON}"
request_scope:
  mutating_requests_allowed: false
  execute_only_request_allowed_items: true
  cleanup_required_before_mutation: true
steps:
  - step_id: "STEP-0001"
    case_id: "DC-001"
    module: "${MODULE_ALIAS}"
    method: "GET"
    path: "/..."
    headers: "${RUNTIME_HEADERS}"
    query: "${RUNTIME_QUERY}"
    body: "${RUNTIME_BODY}"
    assertions_ref: "case_list.yaml#/cases/0"
    extract: {}
    execution_status: needs_runtime_values
    risk_audit_ref: "runtime_risk_audit.yaml#/items/0"
```

Do not pass this skeleton directly to `scripts/run_live_request_evidence.py`; first replace placeholders through a run-specific execution configuration that supplies base URLs, auth, allowed scope, request values, expected statuses, and extraction rules.

### `db_before_after_probe_plan.yaml`

Required under `04-runtime-evidence-plan/` when any runtime candidate can change state or needs cleanup evidence.

```yaml
schema_version: 1
stage: db_before_after_probe_planning
status: ready | not_required | blocked
next_stage_allowed: true | false
probe_policy:
  db_mcp_only_for_evidence_collection: true
  scripts_must_consume_normalized_sidecars: true
  ownership_keys_required_for_mutation: true
  cleanup_graph_required_for_mutation: true
probes:
  - probe_id: "DBP-0001"
    case_id: "DC-001"
    probe_strategy: before_after_snapshot_required
    ownership_key_required: true
    expected_delta_source_ref: "case_list.yaml#/cases/0"
    cleanup_strategy_required: true
    risk_audit_ref: "runtime_risk_audit.yaml#/items/0"
```

The probe plan records what must be evidenced; it must not contain database credentials, live connection strings, or project-specific SQL values unless they come from the run-specific evidence directory.

### `runtime_blocker_candidates.yaml`

Required under `04-runtime-evidence-plan/` whenever planning finds candidates that cannot be safely requested.

```yaml
schema_version: 1
stage: runtime_blocker_candidate_collection
status: passed | has_blockers
next_stage_allowed: true
blocking_items:
  - blocker_id: "RTB-0001"
    case_id: "DC-001"
    risk_level: mutation_requires_cleanup
    reason_codes: ["state_mutation_requires_db_before_after_and_cleanup"]
    needed_input:
      - db_before_after_snapshot
      - ownership_key
      - cleanup_strategy
      - manual_execution_confirmation
    risk_audit_ref: "runtime_risk_audit.yaml#/items/0"
```

These blockers are allowed to coexist with executable-case generation only when the affected facts are not required for `PASSED`. Required facts without closed evidence must remain blocked.

### `runtime_stage_status.yaml`

Required under `04-runtime-evidence/` whenever direct runtime evidence collection is executed.

```yaml
schema_version: 1
stage: runtime_live_evidence
status: passed | partial | blocked | failed
next_stage_allowed: true | false
request_scope:
  env_name: test
  allowed_modules: []
  mutating_requests_allowed: false
  cleanup_required: true
input_paths:
  - path: "runtime_request_plan.yaml"
    role: "runtime_request_plan"
output_paths:
  - path: "runtime_evidence.yaml"
    role: "runtime_evidence"
gate_checks:
  - check_id: direct_request_execution
    status: passed | blocked | failed
    evidence_refs: ["runtime_evidence.yaml"]
continuation_queue:
  schema_version: 1
  queue_policy: long_chain_then_p0_p1_p2_p3_skip_recoverable_and_continue
  summary:
    pending: 0
    requested: 0
    evidenced: 1
    retryable: 0
    skipped_recoverable: 0
    blocked_final: 0
    excluded: 0
  items:
    - case_id: DC-001
      flow_id: FLOW-001
      step_order: 1
      step_id: STEP-0001
      priority_bucket: long_chain | p0 | p1 | p2 | p3 | other
      queue_state: evidenced | retryable | skipped_recoverable | blocked_final
      last_attempt: request_ok
      next_action: consume_confirmed_evidence
      reason_code: runtime_evidence_confirmed
      evidence_refs: ["runtime_evidence.yaml#RT-001"]
blocking_issues: []
```

`status=passed` requires `next_stage_allowed=true`, `blocking_issues=[]`, and no unredacted password、token、Authorization、Cookie or equivalent secret values in any runtime evidence output. `status=partial` may be used only when at least one confirmed evidence item is usable and the missing values are explicitly listed. Queue items must use `queue_state` and must not contain a nested `status` field.

### `runtime_evidence.yaml`

Runtime evidence is produced by a direct requester, not by Apifox MCP and not by the script generator. It records direct interface responses, extracted runtime values, redaction status, and contract/data-model conflict results.

```yaml
schema_version: 1
stage: runtime_live_evidence
status: passed | partial | blocked | failed
next_stage_allowed: true
request_scope:
  env_name: test
  allowed_modules: []
  mutating_requests_allowed: false
  cleanup_required: true
auth_evidence:
  status: confirmed | missing | failed | blocked
  token_source: login_response | user_config | none
  token_extract_path: "$.data.token"
  secret_redaction: enabled
evidence_items:
  - evidence_id: "RT-LOGIN-001"
    flow_id: "FLOW-LOGIN"
    case_id: "DC-001"
    method: "POST"
    path: "/api/v1/auth/login"
    source_contract_ref: "接口结构化契约清单.md#..."
    request_source_ref: "runtime_request_plan.yaml#..."
    response_status: 200
    business_code_path: "$.code"
    business_code_value: 0
    value_type: business_code | enum_code | status_code | field_value | token | id | assertion_value
    field_path: "$.data.userStatus"
    field_value: "ACTIVE"
    source_status: confirmed | missing | conflict | blocked
    usable_for_execution_case: true
    redacted: false
    db_before_ref: "db_before_after_probe_plan.yaml#DBP-001" # mutating cases only
    db_after_ref: "runtime_evidence.yaml#DB-AFTER-001" # mutating cases only
    db_delta_assertion: "status changed from pending to active" # source-bound, not guessed
    db_probe_source_ref: "数据模型.md#cleanup-graph" # mutating cases only
dependency_derivations:
  - derivation_id: "DRV-ORDER-001"
    flow_id: "FLOW-001"
    producer_step_id: "STEP-0002"
    consumer_step_id: "STEP-0003"
    producer_field_path: "$.data.orderId"
    consumer_field_path: "$.body.orderId"
    value_source_ref: "runtime_evidence.yaml#RT-ORDER-001"
    inference_reason: "producer response orderId matches required flow link key and consumer contract orderId"
    cross_check_refs:
      - "required_chain_flows.yaml#FLOW-001"
      - "接口结构化契约清单.md#orderId"
      - "数据模型.md#order_id"
    source_status: confirmed | missing | conflict | blocked
    usable_for_execution_case: true
conflict_items: []
blocking_issues: []
```

Only `source_status=confirmed` and `usable_for_execution_case=true` evidence may be consumed by executable cases. If runtime values conflict with `接口结构化契约清单.md`, design-level cases, `数据模型.md`, DB MCP evidence, or source-extracted facts, stop before execution-level release with `FAILED_EXECUTION_READINESS`; never auto-overwrite the contract with runtime values.

### `runtime_value_catalog.yaml`

This catalog is the normalized runtime-value feed for `$executable-interface-case-set`.

```yaml
schema_version: 1
stage: runtime_value_catalog
status: passed | partial | blocked | failed
values:
  - value_id: "VAL-USER-STATUS-ACTIVE"
    value_type: enum_code
    field: "userStatus"
    value: "ACTIVE"
    source_type: live_request_evidence
    source_ref: "runtime_evidence.yaml#RT-USER-001"
    cross_checked_by:
      - "数据模型.md#user_status"
      - "接口结构化契约清单.md#UserStatus"
    source_status: confirmed
flow_value_links:
  - link_id: "LINK-FLOW-001-ORDER-ID"
    flow_id: "FLOW-001"
    producer_step_id: "STEP-0002"
    consumer_step_id: "STEP-0003"
    producer_field_path: "$.data.orderId"
    consumer_field_path: "$.body.orderId"
    value_id: "VAL-ORDER-ID-001"
    value_source_ref: "runtime_evidence.yaml#DRV-ORDER-001"
    inference_reason: "runtime response value is the same business object key required by the next request"
    cross_checked_by:
      - "required_chain_flows.yaml#FLOW-001"
      - "接口结构化契约清单.md#orderId"
    source_status: confirmed
    usable_for_execution_case: true
usable_fact_types:
  - token_rule
  - test_data_rule
  - variable_link
  - assertion_rule
missing_values: []
conflict_values: []
blocking_issues: []
```

When `execution_fact_sources.yaml` references `source_type: live_request_evidence`, both `runtime_evidence.yaml` and `runtime_value_catalog.yaml` must exist, be `passed` or `partial`, have empty conflict lists, and contain the referenced confirmed `evidence_id` or `value_id`.

### `execution_fact_sources.yaml`

Required for `05-executable-interface-case-set/` whenever the executable stage is attempted.

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
fact_sources:
  - fact_id: "..."
    fact_type: token_rule | test_data_rule | seed_value | enum_code | seed_scope_guard | relationship_graph | ownership_key | variable_link | assertion_rule | db_assertion | cleanup_strategy | transport_crypto_contract | external_dependency_value
    source_type: user_config | data_model | interface_contract | design_case | apifox_mcp | live_request_evidence | prior_response | precondition_api_response | db_seed_evidence | external_sandbox_evidence
    source_ref: "..."
    source_status: confirmed | missing | conflict | blocked
missing_required_facts: []
conflict_facts: []
blocking_issues: []
```

`status=passed` requires `runtime_execution_config.status=provided`, `environment_reference.status=provided`, `authentication_account.status=provided`, `missing_required_facts=[]`, `conflict_facts=[]`, and `blocking_issues=[]`. Every setup-produced value consumed by a request field, expected response, assertion, DB assertion, variable link, or cleanup rule must have a confirmed `seed_value`、`enum_code`、`db_assertion`、`cleanup_strategy`, or `external_dependency_value` source entry and must be filled into execution-level cases as a concrete value or executable variable reference. If `environment_reference.is_test_environment=false` and any DB before/after, cleanup, rollback, or status-recovery fact is required, `db_authorization.non_test_reauthorization_status` must be `provided`; otherwise block with `BLOCKED_NEED_EXECUTION_INPUT`. When encrypted interfaces are confirmed, at least one `transport_crypto_contract` fact must be `confirmed` and cite the algorithm reference, key source, request payload scope, request plaintext serialization, request envelope, and response envelope evidence.

### `apifox_evidence_index.yaml`

Apifox MCP is an optional auxiliary evidence source for `05-executable-interface-case-set/`, not a prerequisite for script generation and not a runtime requester. Write this sidecar only when Apifox MCP evidence is actually consulted, when the user explicitly requires Apifox alignment, or when `execution_fact_sources.yaml` references `source_type: apifox_mcp`. Missing, incomplete, or unavailable Apifox MCP data must not block generation when the same required execution facts are confirmed by source contracts, user configuration, database-normalized evidence, runtime evidence, or design artifacts. The only Apifox-related states that block are explicit Apifox-required user scope or conflict between used Apifox evidence and the release baseline.

```yaml
schema_version: 1
stage: executable_interface_case_set
status: passed | partial | blocked | failed
evidence_items:
  - evidence_id: "..."
    evidence_level: project_structure | interface_contract | saved_case_example | response_example
    apifox_ref: "project/interface/case/response id or path"
    supports: ["method", "path", "request_schema", "response_schema", "status_code", "business_code", "sample_value"]
    source_status: confirmed | missing | conflict | blocked
conflict_items: []
conflict_priority:
  - "structured contract conflicts with any Apifox evidence -> block release; do not overwrite"
  - "runtime values must come from 04-runtime-evidence, not Apifox MCP"
  - "saved_case_example and response_example may fill sample candidates only when aligned with contract"
  - "project_structure locates endpoints only; it cannot fill request, response, status, or assertion facts"
resolution_policy:
  project_structure: "定位项目、模块、目录、接口 ID，不作为字段、断言、环境或鉴权依据；不可用时记录未使用或缺失，不阻塞"
  interface_contract: "辅助校验 method/path/参数/schema/status/error code；与结构化契约冲突时阻塞，不能静默覆盖"
  saved_case_example: "读取保存用例、debug case、示例值，必须与契约一致；仅补样例和执行参数候选"
  response_example: "读取响应示例和值候选，必须与契约一致；不能代表真实运行时取证"
```

## Human Coverage Point Report Contract

Whenever stage 2 reaches design-level case-list generation, it must also produce `03-interface-testcase-generation/测试覆盖点报告.md` for human review. This report is required regardless of whether the selected design source came from the document entry or the source-code entry.

The report must start with a UTF-8 Markdown summary before the detail table. The summary must separately explain the long-chain coverage rate and single-interface coverage rate, the calculation method for each scope, and whether any long-chain test points need focused review:

```markdown
## 覆盖点摘要

- 覆盖率：100%（已映射设计级用例数 1 / 设计级用例总数 1）
- 计算口径：覆盖率 = `测试覆盖点报告.md` 中已列出且 `来源` 可映射到 `case_list.yaml` 的唯一设计级用例数 / `case_list.yaml` 中 passed 设计级用例总数 × 100%。如 `coverage_matrix.yaml` 提供 `test_point_total/test_point_covered`，同时展示阶段测试点覆盖率。
- 长链路覆盖率：100%（已映射长链路设计级用例数 1 / 长链路设计级用例总数 1）
- 单接口覆盖率：100%（已映射单接口设计级用例数 1 / 单接口设计级用例总数 1）
- 分项计算口径：长链路覆盖率和单接口覆盖率分别按 `测试覆盖点报告.md` 中对应类型且 `来源` 可映射到 `case_list.yaml` 的唯一设计级用例数 / `case_list.yaml` 中同类型 passed 设计级用例总数 × 100% 计算；长链路和单接口不得混合计算。
- 长链路重点关注：1 个。长链路定义为 `接口链路` 中接口数量大于等于 3，或操作步骤大于等于 5 步。

| ID | 测试点 | 接口链路 | 关注原因 |
|---|---|---|---|
| TCP-001 | 在订单注册后，用户去支付订单 | 创建订单接口—>支付订单接口—>查询订单接口 | 涉及 3 个接口，需重点检查上下游变量传递和状态一致性 |
```

The detail table must follow the summary, put all long-chain rows before single-interface rows, and use exactly these review-facing fields:

| ID | 测试点 | 业务域 | 业务场景 | 来源 | 接口链路 | 前置条件 | 操作步骤 | 预期结果 | 优先级 | 用例类型 |
|---|---|---|---|---|---|---|---|---|---|---|
| TCP-001 | 在订单注册后，用户去支付订单 | 统一支付 | 用户作为支付发起方在业务系统下单后进入统一支付，系统创建支付单、发起支付并回查支付结果，验证支付单从创建到支付完成的业务链路 | 需求 R-001；测试点 TP-001；设计级用例 DC-001 | 创建订单接口—>支付订单接口—>查询订单接口 | 已存在可登录用户，订单已创建且未支付 | 1. 用户登录系统；2. 创建待支付订单；3. 调用支付订单接口；4. 查询订单状态 | 订单支付成功，订单状态为支付完成 | p0 | 正向流程 |

Rules:

- `ID` must be stable and unique in the report. Prefer a review-specific prefix such as `TCP-001`; keep source IDs in `来源`.
- `测试点` must be a Chinese scenario sentence, not a raw API name or method/path. Use forms such as `场景+角色+动作`、`场景+动作+状态`、`角色+状态+场景`, for example `在订单注册后，用户去支付订单`、`用户支付订单后，订单状态的检查`、`用户在被封禁状态下去提交订单请求`.
- `业务域` must be a Chinese business domain such as `统一支付`、`订单履约`、`账户认证`; prefer `business_scenario_map.yaml.business_domain` when available, otherwise use source-bound requirement or design-case evidence. It must not be an API module name only.
- `业务场景` must be copied or losslessly adapted from source-bound business scenario evidence such as `business_scenario_map.yaml.business_description`, requirements, design cases, or source facts. It must describe the real business scenario or business chain in Chinese, explicitly include the executing role, explain who is doing what in the business process, and explain why the interface chain or single-interface behavior is meaningful. It must not repeat only the API name, method/path, or test type, and it must not be invented during stage 2.
- Single-interface or unit-style coverage points must follow the same narrative standard as long-chain points: include `执行角色 + 业务动作 + 前置业务状态 + 预期业务结果`. Do not write single-interface scenarios as short labels such as `查询接口校验` or `创建支付单接口正向`.
- `来源` must cite source-bound evidence such as requirement ID, coverage object ID, coverage rule ID, test point ID, design case ID, source file reference, or source fact ID. Do not leave it as `无`、`待确认`、`未知` or a generic stage name only.
- `接口链路` must describe the business API path in order. Use `接口1—>接口2—>接口3`; a single-interface case may contain one interface name. Do not use this field for implementation call stacks.
- `前置条件` must describe the preparation required before the test in Chinese, including account state, data state, authorization state, or prior business state when applicable.
- `操作步骤` must convert the test process into concise Chinese steps. Prefer numbered steps in one cell, separated by `；` or `<br>`.
- `操作步骤` must not be a raw method/path list such as `1. POST /api/...`. Raw method/path evidence belongs in `接口链路`、`来源`, or the machine-readable sidecars. The step text must contain Chinese business actions such as `1. 创建订单；2. 发起支付；3. 查询订单状态`; for long-chain rows, derive these actions from `business_chain` or `ordered_steps` before falling back to interface display names.
- `预期结果` must be a Chinese business result, such as `订单支付成功`、`订单状态为支付完成`、`无法提交`; it must not be only an HTTP status code.
- `优先级` must be exactly `p0`、`p1` or `p2`.
- `用例类型` must be a Chinese case classification such as `正向流程`、`异常流程`、`边界值`、`状态流转`、`幂等校验`、`权限校验`、`依赖失败补偿`.
- The summary `覆盖率` must be calculated from mapped review rows, not guessed: `已映射设计级用例数 / case_list.yaml 中 passed 设计级用例总数 × 100%`. When `coverage_matrix.yaml` includes `test_point_total/test_point_covered`, the summary must also cite that stage-level test-point coverage as supporting evidence.
- The summary must separately calculate `长链路覆盖率` and `单接口覆盖率`. Long-chain rows are rows whose `接口链路` contains 3 or more interfaces or whose `操作步骤` contains 5 or more numbered steps; single-interface rows are rows whose `接口链路` contains exactly one interface and do not meet the long-chain step rule. If either type has no rows, write `不涉及` or `无` for that type instead of mixing it into the other type.
- The summary `长链路重点关注` must list all rows whose `接口链路` contains 3 or more interfaces, or whose `操作步骤` contains 5 or more numbered steps. If no long-chain point exists, write `长链路重点关注：无`.
- The detail table must keep long-chain rows first. Once a single-interface row appears, no later row may be a long-chain row. Generate the report in this order instead of reordering it downstream.
- Every row must map to one or more records in `case_list.yaml`; every passed design-level case must have at least one row in the report. Scenario map IDs and descriptions may be cited as reference evidence, but downstream stages must not require the report's `业务场景` text to exactly match `business_scenario_map.yaml`. If the selected entry lacks enough information to write a required field without invention, stage 2 must block with `BLOCKED_NEED_BUSINESS_SCENARIO_MAPPING` or `FAILED_DESIGN_CASE_GATE` instead of creating a partial review report.

## Stage Inputs

At least one entry group is required. The document entry and source entry are an OR relationship, not an AND relationship. Prefer the document entry whenever PRD、API、系统分析、数据模型 are all present; only when the four-file document entry is not satisfied should the Java source root become the primary entry through `$source-api-fact-extractor`. Execution configuration is not an entry-route source and not a design-level source; check it before execution-level filling and script generation.

| 输入组 | 必需性 | 必需文件或目录 | 对应阶段 | 说明 |
|---|---|---|---|---|
| 文档入口 | 入口二选一 | PRD Markdown、API Markdown、系统分析 Markdown、`数据模型.md` 或数据库结构 Markdown | `$pre-doc-analysis-pipeline` | 四个文件都是必要条件；满足时优先走文档入口，并把数据模型复制为 `00-inputs/数据模型.md` |
| 源码入口 | 入口二选一 | Java 后端源码根目录 | `$source-api-fact-extractor` | 当四件套文档入口不满足时，源码入口可替代文档入口成为主入口；只要源码根目录满足 Java/Spring 源码识别即可启动源码事实阶段 |
| 数据模型 | 文档入口必需；执行级/脚本目标必需 | `数据模型.md` 或数据库结构 Markdown；源码入口可由数据库 MCP 归一化生成 | `$pre-doc-analysis-pipeline`、`$executable-interface-case-set`、`$api-test-framework-generator` | 文档入口四件套之一；执行级填数、SQL 构造、数据清理和脚本生成所需。执行级/脚本目标下必须包含表结构、轻量表关系知识图谱、铺数顺序、清理逆序和清理边界。源码入口未提供数据模型时，不得直接阻塞，必须先检查数据库 MCP 能否生成归一化数据模型并通过源码-数据库一致性门禁 |
| 执行配置 | 执行级/脚本目标必需；设计级不需要 | 使用 `runtime_execution_config.template.yaml` 或等价结构提供环境、模块 base URL、网关前缀、账号业务状态、鉴权、加解密、执行授权和 DB 授权 | `$executable-interface-case-set`、`$api-test-framework-generator` | 环境字段必填；环境或鉴权账号缺失时必须输出 `00-inputs/runtime_execution_config.template.yaml`、`00-inputs/前置执行配置待填写.md` 和按需 `runtime_execution_config.missing_fields.yaml`，用户填写并通过校验后继续；不得因执行配置缺失阻塞阶段1入口事实抽取、阶段2设计级用例生成或阶段2设计交接；若环境不是测试环境，DB before/after 和清理权限必须重新显式授权 |
| 运行时取证配置 | 用户要求直接请求接口补码值时必需；否则可选 | base_url、鉴权方式、账号引用、登录接口契约、链路请求计划、允许调用范围、清理策略、执行授权、DB 授权 | 运行时取证补值、`$executable-interface-case-set` | 缺环境、缺鉴权、服务不可用、请求失败或冲突时，不得生成伪码值；用户强制要求运行时取证时阻塞为 `BLOCKED_NEED_EXECUTION_INPUT`；非测试环境缺 DB 重新授权时不得做 DB 操作 |
| Apifox MCP | 可选辅助证据；用户明确要求对齐时按需使用 | 目标项目或接口范围 | `$executable-interface-case-set` | 辅助读取项目结构、接口契约、保存用例和响应示例；Apifox MCP 不是运行时请求器，不直接请求真实接口；不可用、不完整或未配置环境/鉴权时不得作为脚本生成强依赖，除非用户要求以 Apifox 为准 |
| 数据库 MCP | 源码入口缺少数据模型且目标为执行级/脚本时优先检查 | 目标环境数据库 MCP 连接，可读取库名、schema、表、字段、索引、约束、关系 | 数据模型归一化门禁、`$executable-interface-case-set` | 当源码入口未提供 `数据模型.md` 且目标为 `executable`/`framework` 时，必须先尝试用数据库 MCP 生成 `00-inputs/数据模型.md`，不能直接因缺少数据模型阻塞；必须产出 MCP 证据索引、轻量表知识图谱、铺数/清理策略和源码-数据库一致性报告，且不得把 MCP 连接方式下传到 pytest 脚本 |

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
- 状态闭合：Cases that require business state must have executable setup, verification, and cleanup. Examples include existing conversation/message, withdrawal account, idle or busy call state, balance enough/insufficient, block/unblock relation, ban status, subscription tier, audit/onboarding status, report type, upload asset, or any lifecycle state. Prefer API setup and API cleanup; use SQL only when API cannot create the needed isolated state and the reason is recorded. Every state setup must expose a current-run ID or unique ownership key, DB before/after or API verification evidence when persistence matters, and cleanup bounded to the current-run object.
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

### Apifox MCP Optional Evidence Boundary

- Apifox MCP is never an execution-runtime dependency. Generated pytest projects must not depend on Apifox MCP, Apifox environment APIs, saved debug cases, or MCP result files.
- Use Apifox MCP only as auxiliary evidence for contract cross-checking, example value discovery, saved-case reference, response-example reading, or later manual synchronization back to Apifox.
- Apifox MCP is not a runtime requester. Direct interface requests for runtime value evidence must be performed only by the optional direct requester stage that writes `04-runtime-evidence/`.
- If Apifox MCP is unavailable, cannot read environments, lacks saved cases, or has incomplete auth variables, continue generation when environment/auth/crypto/data/assertion facts are confirmed by user configuration, source-derived contracts, database-normalized evidence, or execution artifacts.
- If the user explicitly requires Apifox as the source of truth for a run, missing Apifox access blocks only that requested Apifox-dependent scope with `BLOCKED_NEED_EXECUTION_INPUT`.
- Any used Apifox fact must be evidence-indexed and conflict-checked. Conflicts with source-baseline contracts, design cases, coverage matrices, or execution configuration block release; Apifox evidence must not silently override them.

### Variable Injection Policy

- 变量提取、变量注入、`${变量}` 占位符、运行上下文 key 和 SQL 绑定参数名只要求满足 Python 可执行规则。
- 变量名必须是 Python 合法标识符且不能是 Python 关键字；不得包含空格、横线、点号或其他会导致生成 pytest 脚本不可执行的字符。
- 不额外引入业务命名约束；只要变量能稳定提取、注入并保证脚本可执行即可。
- 上游依赖传递给下游时只使用两类提取形式：JSON 路径和正则表达式。每条依赖必须记录生产用例、消费用例、变量名、提取类型、JSON 路径或 regex pattern/group、来源字段和证据引用。

### Assertion Policy

- 生成 pytest 脚本时断言统一使用 Python `assert`，不得把断言降级为日志、注释或只写入报告。
- 接口响应断言至少覆盖 HTTP 状态码和返回字段；返回字段可用 JSON 路径检查存在性或精确值。
- 涉及落库的断言必须通过 pytest 数据库 fixture 查询落库情况，并把 SELECT 查询、绑定参数、期望行数和字段断言交给 `database_assertor` 执行；下游脚本只消费 fixture 断言规则和数据库配置。
- 脚本阶段的数据库实例必须由 pytest fixture 管理，数据库连接配置只允许落到 `api-test-framework/configs/database.yaml`，不得写入测试用例正文、SQL 命令文件或数据 payload。

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

## Output Layout

Default to one dedicated output root:

```text
output/api-automation-pipeline/
├── 00_流水线执行报告.md
├── retry_history.yaml（仅发生再生成或三次失败阻塞时）
├── required_chain_flows.yaml
├── chain_flow_candidate_audit.yaml
├── chain_flow_alignment.yaml（文档入口和源码入口同时执行时）
├── 00-inputs/
│   ├── 数据模型.md
│   ├── database_mcp_evidence_index.yaml（使用数据库 MCP 时）
│   ├── source_db_alignment.yaml（使用数据库 MCP 时）
│   ├── source_db_alignment_report.md（使用数据库 MCP 时）
│   ├── runtime_execution_config.template.yaml（缺少执行配置时）
│   ├── 前置执行配置待填写.md（缺少执行配置时）
│   └── runtime_execution_config.missing_fields.yaml（缺少执行配置且可枚举字段时）
├── 01-pre-doc-analysis/
│   ├── 01_接口测试用例设计文档.md
│   ├── 02_接口结构化契约清单.md
│   ├── 03_skill执行报告.md
│   ├── stage_status.yaml
│   ├── coverage_matrix.yaml
│   ├── business_scenario_map.yaml
│   └── 业务场景链路清单.md
├── 02-source-api-facts/
│   └── docs/source-facts/
│       ├── 01_接口测试用例设计文档.md
│       ├── 02_接口结构化契约清单.md
│       ├── 03_skill执行报告.md
│       ├── source-api-facts.json
│       ├── source-api-quality-report.json
│       ├── source_api_fact_artifacts.yaml
│       ├── stage_status.yaml
│       ├── coverage_matrix.yaml
│       ├── business_scenario_map.yaml
│       └── 业务场景链路清单.md
├── 03-interface-testcase-generation/
│   ├── 04_接口测试用例清单.md
│   ├── case_list.yaml
│   ├── business_long_chain_cases.yaml
│   ├── 业务长链路设计清单.md
│   ├── 测试覆盖点报告.md
│   ├── stage_status.yaml
│   └── coverage_matrix.yaml
├── 04-design-case-handoff/
│   ├── 接口测试用例设计文档.md
│   ├── 接口结构化契约清单.md
│   ├── case_list.yaml
│   ├── 测试用例清单.md
│   ├── 测试覆盖点报告.md
│   ├── business_long_chain_cases.yaml
│   ├── 业务长链路设计清单.md
│   ├── required_chain_flows.yaml
│   ├── chain_flow_candidate_audit.yaml
│   ├── business_scenario_map.yaml
│   ├── 业务场景链路清单.md
│   └── 执行报告.md
├── 04-runtime-evidence-plan/（按需）
│   ├── runtime_risk_audit.yaml
│   ├── runtime_request_plan.skeleton.yaml
│   ├── db_before_after_probe_plan.yaml
│   └── runtime_blocker_candidates.yaml
├── 04-runtime-evidence/（按需）
│   ├── runtime_request_plan.yaml
│   ├── runtime_evidence.yaml
│   ├── runtime_value_catalog.yaml
│   ├── runtime_conflict_report.md
│   ├── runtime_stage_status.yaml
│   └── runtime_evidence_queue.yaml（按需，队列较大或需要单独审计时）
├── 05-executable-interface-case-set/
│   ├── 执行级接口用例集.md
│   ├── 前置数据构造规则.md
│   ├── 长链路缺失码值补充清单.md（长链路仍需用户补值时）
│   ├── long_chain_missing_value_fields.yaml（长链路补值状态 sidecar）
│   ├── stage_status.yaml
│   ├── coverage_matrix.yaml
│   ├── execution_fact_sources.yaml
│   └── apifox_evidence_index.yaml（按需）
└── api-test-framework/
    ├── data/flow_cases.yaml 或 data/flow_cases.py（生成 E2E flow 时）
    ├── core/flow_runner.py（生成 E2E flow 时）
    └── testcases/test_flows.py（生成 E2E flow 时）
```

Create only the subdirectories for executed stages. Do not fabricate documents for skipped or blocked stages.

## Stage Status

| 状态 | 含义 | 可否进入下一阶段 |
|---|---|---|
| `PASSED` | 当前阶段门禁通过，产物完整 | 是 |
| `BLOCKED_MISSING_ENTRY_INPUT` | 文档入口和源码入口都缺失，或入口必需文件缺失 | 否 |
| `FAILED_ENTRY_QUALITY_GATE` | 入口质检、测试点拆分、覆盖率准出或源码事实质检未通过 | 否 |
| `FAILED_ENTRY_ALIGNMENT_GATE` | 文档入口与源码入口产物存在阻塞冲突 | 否 |
| `BLOCKED_NEED_BUSINESS_SCENARIO_MAPPING` | 选定入口缺少已通过的业务场景映射，或业务场景无法绑定测试点/覆盖规则 | 否 |
| `BLOCKED_NEED_CHAIN_FLOW_DENOMINATOR` | 入口已完成但缺少统一长链路闭环分母、候选审计未分类、或必测 flow 无法按闭环证据确认 | 否 |
| `BLOCKED_NEED_CHAIN_FLOW_EVIDENCE` | 上游存在链路场景，但执行级变量提取/注入、步骤顺序或链路断言证据不足，无法生成链路脚本 | 否 |
| `FAILED_DESIGN_CASE_GATE` | `interface-testcase-generation` 未能产出可用设计级用例 | 否 |
| `BLOCKED_NEED_HANDOFF_REPAIR` | `04_接口测试用例清单.md` 无法无损拆成 `测试用例清单.md` 和 `执行报告.md` | 否 |
| `BLOCKED_NEED_EXECUTION_INPUT` | 缺少数据模型、环境、鉴权、真实值、断言或清理策略 | 否 |
| `FAILED_EXECUTION_READINESS` | 执行级用例不可重复执行或不可转 pytest+allure | 否 |
| `FAILED_SCRIPT_GENERATION_GATE` | pytest+allure 工程生成前置门禁失败 | 否 |
| `BLOCKED_RETRY_EXHAUSTED` | 后置节点门禁要求前置节点再生成，但同一生产-消费门禁连续 3 次仍不能满足 | 否 |

`00_流水线执行报告.md` must record every stage status, consumed input paths, produced output paths, blockers, impact, repair suggestions, and retry history when regeneration is attempted.

## User-Facing Completion Notice

At the end of every run, make the user-facing final response impossible to confuse with a full pipeline success:

- If `api-test-framework/` was not generated, lead the final response with `未生成最终自动化脚本` and name the stopping status, stopping stage, missing inputs, and the highest completed stage.
- If the pipeline ends with any status other than `PASSED`, explicitly say that validation only proves the current blocked or partial-output state satisfies the pipeline gate, not that the full automation chain has completed.
- If execution-level cases or scripts were skipped, explicitly list the absent directories such as `05-executable-interface-case-set/` and `api-test-framework/`.
- Do not use phrases such as `全链路通过`、`跑完全链路`、`已生成自动化脚本`、or `校验通过` without immediately qualifying whether final scripts exist.
- When the target depth is `framework` and final scripts are blocked, ask the user to confirm whether they want to provide execution inputs, use database/Apifox MCP evidence, or narrow the target to `design`/`executable`.

## Exit Gates

| 门禁 | 通过标准 | 失败状态 |
|---|---|---|
| 入口存在性 | 至少存在完整四件套文档入口（PRD/API/系统分析/数据模型）或源码入口，且入口必需产物可读、非空、UTF-8 | `BLOCKED_MISSING_ENTRY_INPUT` |
| 入口质检与测试点拆分 | 文档入口的 `03_skill执行报告.md` 证明输入文件质检通过、二阶段测试点分析完整、覆盖对象/覆盖规则/测试点可追溯、规则级覆盖率 100%、允许声明 100% 覆盖；源码入口作为替代主入口时，`source-api-quality-report.json` 必须通过，并以源码抽取出的接口、契约、业务规则、错误码和源码可见副作用作为覆盖分母 | `FAILED_ENTRY_QUALITY_GATE` |
| 源码入口产物索引 | 源码入口用于下游时，`source_api_fact_artifacts.yaml` 必须列出 `source_api_design_doc`、`source_api_contract_list`、`source_api_stage_report`、`source_api_business_scenario_map`、`source_api_business_scenario_doc`、`source_api_stage_status`、`source_api_coverage_matrix`、`source_api_fact_json`、`source_api_fact_artifact_manifest`，后续节点按这些 artifact 名称继承前置产物 | `FAILED_ENTRY_QUALITY_GATE` |
| 阶段1结构化 sidecar | 文档入口用于下游时，`01-pre-doc-analysis/stage_status.yaml` 必须 `status=passed`、`next_stage_allowed=true`，`coverage_matrix.yaml` 必须证明覆盖对象、测试点映射和覆盖规则分子等于分母，缺失 ID 为空；源码入口用于下游时，`02-source-api-facts/docs/source-facts/stage_status.yaml` 必须 `status=passed`、`next_stage_allowed=true`，`coverage_matrix.yaml.stage=source_api_facts`，并以源码接口、源码契约规则、源码业务规则、源码错误码、源码 DB 副作用、源码业务场景作为独立分母，分子等于分母且缺失 ID 为空；所有 passed 分母必须大于 0，非 legacy sidecar 必须有逐项 `coverage_items` 和 `upstream_downstream_mappings` 证据 | `FAILED_ENTRY_QUALITY_GATE` |
| 业务场景映射 | 选定入口必须存在 `business_scenario_map.yaml` 和 `业务场景链路清单.md`；sidecar 必须 `status=passed`、`next_stage_allowed=true`、`scenario_items` 非空、`blocking_issues=[]`，每个场景必须有中文 `business_domain`、中文 `executing_role`、包含执行角色的中文 `business_description`、source refs、接口链路、关联测试点 ID 和覆盖规则 ID | `BLOCKED_NEED_BUSINESS_SCENARIO_MAPPING` |
| 长链路闭环分母 | 入口释放后、阶段2前必须存在根级 `required_chain_flows.yaml` 和 `chain_flow_candidate_audit.yaml`；`required_chain_flows.yaml.status=passed`、`next_stage_allowed=true`、`required_chain_flow_count` 等于 `flows` 中 `status=required` 的唯一 `flow_id` 数；每条 flow 必须有前序动作、可观察变化、后序验证、连接键、步骤、证据引用；`chain_flow_candidate_audit.yaml` 必须分类所有候选且 `unclassified_candidate_flows=[]`；当两入口同时执行时必须有 `chain_flow_alignment.yaml` | `BLOCKED_NEED_CHAIN_FLOW_DENOMINATOR` |
| 链路场景脚本准入 | 以 `required_chain_flows.yaml` 为唯一必测长链路分母；已有长链路产物、`business_scenario_map.yaml`、接口数和步骤数只作为候选发现或兼容证据；每个 required flow 必须在执行级阶段补齐 `flow_id`、有序步骤、生产者/消费者变量链路、提取规则、注入目标和链路断言；证据不足时不得退化为单接口脚本；`测试覆盖点报告.md` 的长链路重点关注项只能作为人工参考，不能作为后续脚本准入分母 | `BLOCKED_NEED_CHAIN_FLOW_EVIDENCE` |
| 执行准备输入 | 目标阶段为 `executable` 或 `framework` 时，`数据模型.md`、环境引用和鉴权账号已在初始预检中确认；源码入口缺少数据模型时，必须先检查数据库 MCP 并尝试归一化生成，只有 MCP 不可用/不可读、身份无法确认、图谱/铺数/清理证据无法生成或源码-数据库一致性未通过时才阻塞；环境字段必填，并应来自 `runtime_execution_config.template.yaml` 或等价结构，缺失时必须输出 `runtime_execution_config.template.yaml`、`前置执行配置待填写.md` 和按需缺失字段清单给用户填写；`数据模型.md` 必须包含表结构、轻量关系图、铺数顺序、清理逆序、归属键和清理边界；token、测试数据、变量链路、断言和清理策略必须可从源材料提取或在执行级阶段阻塞；若环境不是测试环境，DB before/after、清理、回滚或状态恢复必须有本次非测试环境显式授权 | `BLOCKED_NEED_EXECUTION_INPUT` |
| 特定账号长链路登录首步 | 任一 required flow 或执行级长链路声明需要特定账号、角色、租户、权限或账号业务状态时，执行级有序步骤和 `data/flow_cases.yaml` 或 `data/flow_cases.py` 的第一个请求步骤必须是源绑定的登录/授权接口，并提取 token 与账号上下文供后续步骤使用；缺登录接口、账号凭据 secret_ref、token/账号上下文提取路径或注入规则时，不得进入脚本生成 | `BLOCKED_NEED_EXECUTION_INPUT` 或 `BLOCKED_NEED_CHAIN_FLOW_EVIDENCE` |
| 运行时取证规划 | 当用户要求全量请求器取证、广覆盖执行级填数或 runtime evidence 补值时，必须先生成 `04-runtime-evidence-plan/runtime_risk_audit.yaml`、`runtime_request_plan.skeleton.yaml`、`db_before_after_probe_plan.yaml`、`runtime_blocker_candidates.yaml`；不得无差别请求所有接口；可请求分母、需 DB 前后探测分母、人工确认/阻塞分母必须逐项有 source ref 和 reason_codes | `BLOCKED_NEED_EXECUTION_INPUT` |
| 运行时取证补值 | 当存在 `04-runtime-evidence/` 时，`runtime_stage_status.yaml`、`runtime_evidence.yaml`、`runtime_value_catalog.yaml` 必须 schema_version=1、状态合法、无明文敏感值；当执行事实引用 `live_request_evidence` 时，运行时证据必须为 `passed` 或 `partial`、冲突列表为空，且引用的 `evidence_id/value_id` 存在并已确认 | `BLOCKED_NEED_EXECUTION_INPUT` 或 `FAILED_EXECUTION_READINESS` |
| 接口传输加解密执行契约 | 若没有确认加密接口，脚本生成可按普通 HTTP 执行；若存在确认加密接口，必须在执行级产物中确认加解密方法、key 来源、请求明文范围、请求序列化方式、请求报文包装和响应报文包装，并声明业务链路变量使用明文；任一缺失不得进入脚本生成 | `BLOCKED_NEED_EXECUTION_INPUT` |
| 源码-数据库一致性 | 当 `数据模型.md` 由数据库 MCP 生成时，`database_mcp_evidence_index.yaml` 必须证明连接身份、schema 事实来源、关系/清理证据来源，`source_db_alignment.yaml` 必须 `status=passed`、`next_stage_allowed=true`，源码引用表/字段/约束/关系/铺数清理顺序/副作用均与 MCP schema 对账通过，缺失和冲突列表为空 | 缺少 MCP/人工确认时为 `BLOCKED_NEED_EXECUTION_INPUT`；事实冲突时为 `FAILED_EXECUTION_READINESS` |
| 入口一致性 | 文档入口与源码入口的 method、path、字段、状态码、错误码无阻塞冲突 | `FAILED_ENTRY_ALIGNMENT_GATE` |
| 设计用例生成 | `interface-testcase-generation` 产出 `04_接口测试用例清单.md` 和 `case_list.yaml`，且明确准出或明确阻塞；`case_list.yaml.status=passed` 时，每条 `cases` 记录必须逐条包含有效 `case_id`、`design_case_id`、`test_point_ids`、`coverage_object_ids`、`coverage_rule_ids`、`method`、`path`、`status_codes`、`priority`、`assertion_points`，不能只在文件任意位置出现字段名 | `FAILED_DESIGN_CASE_GATE` |
| 阶段2结构化 sidecar | `03-interface-testcase-generation/stage_status.yaml` 必须 `status=passed`、`next_stage_allowed=true`，`coverage_matrix.yaml` 必须证明测试点、主要流程、契约规则、状态码和 P0/P1 覆盖分子等于分母，缺失 ID 为空；每个分母必须大于 0，`coverage_items` 必须按 `test_point/main_flow/contract_rule/status_code/p0_p1` 逐项列出唯一 `coverage_id`，且每个覆盖项都有 `mapped` 上下游映射；若 `required_chain_flows.yaml` 存在 required flows，还必须以 `denominator_scope: long_chain_only` 单独证明 `chain_scenario`、`chain_function`、`chain_process` 覆盖分子等于分母且缺失列表为空，并在 `coverage_items` 中逐项列出长链路覆盖证据 | `FAILED_DESIGN_CASE_GATE` |
| 必测 flow 设计级覆盖 | `required_chain_flows.yaml` 中每个 `status=required` 的 `flow_id` 必须映射到至少一条设计级长链路用例；`generated_design_chain_case_count` 必须等于 `required_chain_flow_count`，`missing_required_flow_ids=[]` | `FAILED_DESIGN_CASE_GATE` |
| 人工覆盖点报告 | `03-interface-testcase-generation/测试覆盖点报告.md` 必须存在，开头包含覆盖点摘要、覆盖率、计算口径和长链路重点关注项；明细表包含 `ID`、`测试点`、`业务域`、`业务场景`、`来源`、`接口链路`、`前置条件`、`操作步骤`、`预期结果`、`优先级`、`用例类型` 十一列；中文描述列必须为中文，优先级只能是 `p0/p1/p2`，每条通过的设计级用例至少映射一条覆盖点记录；该报告为人工复核材料，不作为执行级或脚本级强准入依赖 | `FAILED_DESIGN_CASE_GATE` 或 `BLOCKED_NEED_HANDOFF_REPAIR` |
| 业务场景长链路设计分母 | `03-interface-testcase-generation/business_long_chain_cases.yaml` 必须存在并使用 `denominator_scope: business_scenario_long_chain_design`；每条纳入分母的长链路必须是中文真实业务场景，包含执行角色、业务域、业务描述、至少 3 个接口或 5 个业务步骤、source refs、关联测试点 ID、关联覆盖规则 ID、P0 设计级用例 ID 和可执行状态；不得按 URL 前缀、Controller 包、API 模块或任意排列拼接；`business_long_chain_total == business_long_chain_covered` 且 `missing_business_long_chain_ids=[]`；`业务长链路设计清单.md` 必须作为人工视图同步输出 | `FAILED_DESIGN_CASE_GATE` |
| 设计交接适配 | 可从 `04_接口测试用例清单.md` 无损得到 `测试用例清单.md` 和 `执行报告.md` | `BLOCKED_NEED_HANDOFF_REPAIR` |
| 覆盖响应一致性 | 设计级用例生成产物的质检结论、覆盖矩阵、阻塞项、修正建议、准出结论均证明 100% 覆盖可声明，且无 `覆盖不足`、`未覆盖`、`待补充`、`阻塞` 或非 100% 覆盖率 | `FAILED_DESIGN_CASE_GATE` 或 `BLOCKED_NEED_HANDOFF_REPAIR` |
| 执行级填数 | `executable-interface-case-set` 阶段状态为 `PASSED`，产出两份执行级文档、`stage_status.yaml`、`coverage_matrix.yaml`、`execution_fact_sources.yaml` 和按需 `apifox_evidence_index.yaml`，且每条执行级用例保留 `设计级用例ID`、`覆盖对象ID`、`覆盖规则ID`、`追溯测试点`；执行级 `coverage_matrix.yaml` 的设计级用例、执行级用例和覆盖规则分母必须大于 0，并按 `design_case/executable_case/coverage_rule` 提供逐项 `coverage_items` 和 `mapped` 上下游映射；若 `required_chain_flows.yaml` 存在 required flows，执行级 `coverage_matrix.yaml` 必须以 `long_chain_only` 单独证明场景、功能、流程覆盖率均为 100%；执行级 runnable 分母必须通过入参闭合、状态闭合、会话闭合三类门禁：主流程业务必填字段有来源，状态型用例有 setup/verify/cleanup，pre-login/app/internal 鉴权策略和角色上下文隔离已确认；若存在 DB/API 前置造数，`前置数据构造规则.md` 和 `execution_fact_sources.yaml` 必须证明 `seed_scope_guard` 已通过：只造业务前置状态所需字段，普通请求字段、链路返参字段、外部依赖字段、token/验证码/设备/分页/运行标识等字段不由造数替代 | `BLOCKED_NEED_EXECUTION_INPUT` 或 `FAILED_EXECUTION_READINESS` |
| 长链路缺失码值补充 | 执行级长链路用例生成后，必须扫描长链路请求字段、断言字段、变量、前置造数、DB 断言、清理、外部依赖、账号和加解密字段的缺失码值；如存在缺失，产出 `长链路缺失码值补充清单.md` 和 `long_chain_missing_value_fields.yaml`，逐项说明业务场景、用例、步骤、接口、字段路径、字段含义、需补类型、需要账号角色和允许填写形式；用户补完后必须回填到 `执行级接口用例集.md`、`前置数据构造规则.md`、`execution_fact_sources.yaml`，且 `long_chain_missing_value_fields.yaml.status=filled`、`open_required_count=0` 后才能进入脚本生成 | `BLOCKED_NEED_EXECUTION_INPUT` |
| 必测 flow 执行级覆盖 | `required_chain_flows.yaml` 中每个 `status=required` 的 `flow_id` 必须映射到至少一条执行级长链路用例；`generated_executable_chain_case_count` 必须等于 `required_chain_flow_count`，`missing_required_flow_ids=[]` | `FAILED_EXECUTION_READINESS` |
| 脚本生成 | `api-test-framework-generator` 前置检查通过，`api-test-framework/` 骨架完整，`configs/generation_status.yaml` 记录 `coverage_traceability`、`pytest_collection_mapping`、`e2e_flow_mapping`、`chain_script_coverage`、`pytest_nodeid`、执行级用例数、E2E flow 数和 pytest 收集用例数；每个 required flow 必须有 `data/flow_cases.yaml` 或 `data/flow_cases.py`、`core/flow_runner.py`、`testcases/test_flows.py` 和独立 pytest nodeid；`chain_script_coverage` 必须以 `long_chain_only` 单独证明长链路场景、功能、流程覆盖率均为 100%；收集数必须等于执行级用例数加 E2E flow 数；`setup_cleanup_materialization.status` 必须通过，变更类用例只有引用而无可执行 API/SQL 清理时不得进入 runnable 分母；脚本侧 `generation_status.yaml` 必须记录 execution fact closure 结果，证明无只带公共参数的主流程、无缺 setup/cleanup 的状态型用例、无 pre-login 注入 token、无跨角色 token/userId/session 上下文污染；运行失败分析产生的确认缺陷必须写入 Markdown `缺陷列表.md`，且证据不足项只能列为候选 | `FAILED_SCRIPT_GENERATION_GATE` |
| 必测 flow pytest 覆盖 | `required_chain_flows.yaml` 中每个 `status=required` 的 `flow_id` 必须映射到独立 E2E flow pytest nodeid；`generated_pytest_flow_count` 必须等于 `required_chain_flow_count`，`missing_required_flow_ids=[]` | `FAILED_SCRIPT_GENERATION_GATE` |
| 下游契约适配 | 后置节点发现前置产物中的非阻塞项、待确认项、结构缺口或兼容展示内容影响本节点准入时，必须要求责任前置节点基于源输入重新生成；连续 3 次仍不满足则整体阻塞 | `BLOCKED_RETRY_EXHAUSTED` |

Only mark the overall pipeline as `PASSED` when all executed stages pass and no downstream stage still needs invented data.

## Required Workflow

0. Run initial preflight.
   - Determine target depth: `design`, `executable`, or `framework`.
   - Confirm at least one entry group is complete.
   - Treat PRD/API/系统分析/数据模型 as one complete document entry group; all four files must be readable, non-empty, UTF-8, and free of replacement characters.
   - Treat Java backend source root as an independent source entry group; when the four-file document entry is not satisfied, source entry becomes the primary entry and can start the pipeline even when PRD/API/系统分析/数据模型 or execution configuration are not provided.
   - For `executable` or `framework`, do not treat missing `数据模型.md` as an immediate blocker while a valid source entry can still run. After source fact extraction, if no normalized data model exists, perform the database MCP-first check and try to generate `00-inputs/数据模型.md`; only block before `$executable-interface-case-set` when MCP is unavailable/unreadable, identity cannot be confirmed, relationship/setup/cleanup evidence cannot be resolved, or source-DB alignment does not pass.
   - For `executable` or `framework`, confirm environment reference and authentication account inputs are provided in a readable, non-empty, UTF-8 execution configuration artifact before execution-level filling. If they are missing or incomplete, create the run-specific fillable package under `00-inputs/` and stop with `BLOCKED_NEED_EXECUTION_INPUT`; other execution facts may be completed only from source-bound materials and must block if still missing.
   - Copy a valid data model to `00-inputs/数据模型.md` for downstream stages whenever one is provided or normalized from source-present materials; if normalized from database MCP, also preserve `database_mcp_evidence_index.yaml` and `source_db_alignment.yaml`. Do not treat a field-list-only schema as valid for executable/script depth.
   - If execution readiness is missing for a full pipeline request, do not block a valid entry stage; finish valid entry/design stages, materialize the required data-model or execution-config blocker artifacts, then stop before execution-level filling or script generation with `BLOCKED_NEED_EXECUTION_INPUT`.
1. Decide and run the entry stage.
   - If PRD/API/system-analysis/data-model documents are all provided, use `$pre-doc-analysis-pipeline` and write its three Markdown deliverables to `01-pre-doc-analysis/`.
   - The document entry must run input-file quality review first, then standardized test point analysis and splitting, then business scenario mapping, then interface test case design. Do not enter stage 2 unless `03_skill执行报告.md`, `stage_status.yaml`, `coverage_matrix.yaml`, and `business_scenario_map.yaml` prove Stage 1, Stage 2, and Stage 3 of `$pre-doc-analysis-pipeline` passed with 100% coverage release and business scenarios are traceable.
   - If the complete four-file document group is not provided but Java source is provided, use `$source-api-fact-extractor` and write its `docs/source-facts/` deliverables under `02-source-api-facts/`.
   - Source-only entry is a valid replacement for the document entry when the four-file document entry is not satisfied. Record its coverage denominator as the interfaces, contracts, business rules, error codes, DB side effects, source-inferred business scenarios, and traceable facts extracted from source evidence. Its `coverage_matrix.yaml` must use `stage: source_api_facts` and the `source_*` count fields defined in the coverage matrix contract; do not reuse `pre_doc_analysis` count fields for source-only release.
   - If both complete four-file document group and Java source are provided, prefer `$pre-doc-analysis-pipeline`; run `$source-api-fact-extractor` only when the user explicitly asks for implementation evidence.
   - Do not use source facts to overwrite document facts silently.
2. Select the design source.
   - Prefer the document entry whenever the four-file document entry is complete.
   - If the four-file document entry is not complete and source entry exists, use the source entry as the primary design source for downstream case generation.
   - If both entries exist, source entry is optional implementation evidence and must not silently overwrite document facts.
   - Validate the selected entry `business_scenario_map.yaml` and `业务场景链路清单.md` before stage 2. If the selected entry lacks a passed map, has empty `scenario_items`, has `confidence=low`, has blockers, or cannot bind scenario items to test point IDs and coverage rule IDs, stop with `BLOCKED_NEED_BUSINESS_SCENARIO_MAPPING`.
   - Preserve multi-interface scenarios from `business_scenario_map.yaml`. Any scenario with `chain_type=e2e_flow_candidate`, `flow_generation_required=true`, or inferred long-chain signals must remain visible as candidate evidence in `case_list.yaml`, handoff files, execution-level cases, and script generation status. It should also be visible in `测试覆盖点报告.md` for human review when the report is generated, but downstream stages must not depend on the report text.
   - Treat long-chain signals from both document/file entry and source-code entry as candidate evidence for `required_chain_flows.yaml`. Stage 2 may still generate single-interface or unit-style cases, but must not use those case counts to satisfy required flow coverage.
   - If both document and source entries exist, compare business scenario IDs/names, interface chains, state chains, and source refs at the scenario level. Method/path/field/status/error-code conflicts still use `FAILED_ENTRY_ALIGNMENT_GATE`; business scenario gaps or low-confidence mappings use `BLOCKED_NEED_BUSINESS_SCENARIO_MAPPING`.
2.5. Build the required chain-flow denominator.
   - Generate root-level `required_chain_flows.yaml` and `chain_flow_candidate_audit.yaml` from selected document/source evidence before `$interface-testcase-generation` runs. Use `scripts/build_chain_flow_denominator.py` when a deterministic merge/check helper is useful.
   - Include a flow only when source-bound evidence proves pre-action, observable change, verification, link keys, ordered steps, and evidence refs. Classify every non-included candidate with the downstream path from the Required Chain Flow Denominator Contract: `design_long_chain_only`、`design_short_chain_state_transition`、`single_interface_mutation`、`single_interface_readonly`、`external_or_callback`、`excluded_missing_verification`、`excluded_missing_change_evidence`、`excluded_missing_link_key` or `excluded_readonly`. Do not use a generic excluded bucket for scenarios that should continue as design-level or single-interface coverage.
   - If any candidate cannot be classified, stop with `BLOCKED_NEED_CHAIN_FLOW_DENOMINATOR`; do not enter stage 2 and do not declare long-chain 100%.
   - If both document and source entries are executed, create `chain_flow_alignment.yaml` and classify every flow as `doc_only`、`source_only`、`both_step_diff` or `both_consistent`; keep every evidence-complete flow in the required denominator.
3. Normalize the data model when executable/script depth needs it.
   - If `00-inputs/数据模型.md` is already provided, use it as the data model input after UTF-8/non-empty checks and after confirming it includes table structure, relationship graph, setup order, cleanup reverse order, ownership keys, and cleanup boundaries for executable setup/cleanup tables.
   - If the selected entry is source-only, target depth is `executable` or `framework`, and no data model is provided, the database MCP check is mandatory before blocking. Use database MCP only as an upstream evidence source to read database identity, schema, tables, columns, indexes, constraints, comments, and relationship candidates.
   - Before trusting MCP schema, compare it with source facts from `source-api-facts.json`: datasource identity/config reference, source-referenced tables, source-referenced columns, type/nullability compatibility, primary/unique/cleanup keys, relationship graph, setup/cleanup order, and source-visible DB side effects.
   - Write `00-inputs/数据模型.md`, `00-inputs/database_mcp_evidence_index.yaml`, `00-inputs/source_db_alignment.yaml`, and `00-inputs/source_db_alignment_report.md`; do not continue to executable filling unless `source_db_alignment.yaml.status=passed` and `next_stage_allowed=true`, including passed relationship and setup/cleanup checks.
   - Do not query production row data unless the user explicitly permits it; table/column/index metadata is enough for data model normalization.
4. Run `$interface-testcase-generation`.
   - Consume `01_接口测试用例设计文档.md` and `02_接口结构化契约清单.md` from the selected entry.
   - Consume the selected entry `business_scenario_map.yaml` as the authoritative structured source for business domain, executing role, scenario traceability, and E2E flow candidates. The report `业务场景` may be copied or losslessly adapted from `business_description`, but downstream traceability must use scenario IDs and structured mappings, not exact report prose.
   - If both entries exist, cite source facts as additional evidence and record any difference in `00_流水线执行报告.md`.
   - Output `03-interface-testcase-generation/case_list.yaml` as the authoritative machine-readable design case list and `03-interface-testcase-generation/04_接口测试用例清单.md` as the human-readable report.
   - Enumerate real business long-chain design cases before writing the final case list. Use business domain, executing role, business goal, object lifecycle, state transitions, and cross-interface side effects to discover candidates; do not generate chains from URL prefixes, controller packages, API modules, or arbitrary permutations.
   - Output `03-interface-testcase-generation/business_long_chain_cases.yaml` and `03-interface-testcase-generation/业务长链路设计清单.md`. Every accepted business long-chain must map to a P0 design case in `case_list.yaml`, cite source refs, cite related test point IDs and coverage rule IDs, and declare `executable_status`. Closed-loop-ready chains must reference `required_flow_id`; design-valid but execution-incomplete chains must remain design covered while using a non-script-required executable status.
   - Write `business_long_chain_cases.yaml` in handoff-readable block YAML, not compact or indentless forms. Top-level sequence fields must be indented under their parent key, for example `chains:\n  - chain_id: ...` and nested lists such as `interfaces:\n    - POST /... 接口`. Avoid YAML anchors, aliases, inline mappings, or legal-but-fragile formatting for handoff-critical lists.
   - Output `03-interface-testcase-generation/测试覆盖点报告.md` as the mandatory human review coverage-point report. Build it from `case_list.yaml`, selected entry traceability, selected `business_scenario_map.yaml`, and `coverage_matrix.yaml`; do not invent missing business domains, business scenarios, sources, preconditions, steps, expected results, priorities, or case types.
   - Ensure `测试覆盖点报告.md` starts with a coverage summary that states the report-level coverage rate, long-chain coverage rate, single-interface coverage rate, calculation methods, and long-chain points to focus on; the detail table must contain the eleven required columns in the Human Coverage Point Report Contract, put long-chain rows before single-interface rows, uses Chinese descriptions for `测试点`、`业务域`、`业务场景`、`前置条件`、`操作步骤`、`预期结果`、`用例类型`, uses `接口1—>接口2—>接口3` style link notation, and uses only `p0/p1/p2` priorities.
   - Before adapting handoff, run a producer-level precheck for handoff-critical fields: every selected `business_scenario_map.yaml.scenario_items[]` has Chinese `business_domain` and `executing_role`; every coverage report `操作步骤` is Chinese business action text rather than raw method/path; every `business_long_chain_cases.yaml.chains[]` exposes non-empty `interfaces`、`source_refs`、`related_test_point_ids`、`related_coverage_rule_ids` in handoff-readable block-list form.
   - Also output `03-interface-testcase-generation/stage_status.yaml` and `03-interface-testcase-generation/coverage_matrix.yaml`; when `required_chain_flows.yaml` contains required flows, `coverage_matrix.yaml` must include `denominator_scope: long_chain_only`, `chain_scenario_total/chain_scenario_covered`, `chain_function_total/chain_function_covered`, `chain_process_total/chain_process_covered`, the three empty missing lists, and `coverage_items` records for `chain_scenario`、`chain_function`、`chain_process` with source-bound evidence. It must also record `generated_design_chain_case_count == required_chain_flow_count` and `missing_required_flow_ids=[]`. Do not adapt handoff unless `case_list.yaml` and these sidecars pass.
5. Adapt the design-case handoff.
   - `executable-interface-case-set` requires `case_list.yaml`, `测试用例清单.md`, and `执行报告.md`; `case_list.yaml` is the authoritative handoff source, while `测试用例清单.md` is a human-readable compatibility wrapper.
   - `executable-interface-case-set` also expects design and contract inputs as `接口测试用例设计文档.md` and `接口结构化契约清单.md`; copy the selected entry's `01_接口测试用例设计文档.md` and `02_接口结构化契约清单.md` into those normalized names.
   - Copy only source-present content from `03-interface-testcase-generation/case_list.yaml` into `04-design-case-handoff/case_list.yaml`; build `04-design-case-handoff/测试用例清单.md` from that YAML without inventing fields.
   - If `03-interface-testcase-generation/测试覆盖点报告.md` exists, copy it to `04-design-case-handoff/测试覆盖点报告.md` without rewriting rows as an optional human-review reference. Do not block executable-case filling only because this report is absent or because its `业务场景` prose differs from `business_scenario_map.yaml`; executable-case filling must use `case_list.yaml` and structured sidecars.
   - Copy `03-interface-testcase-generation/business_long_chain_cases.yaml` and `03-interface-testcase-generation/业务长链路设计清单.md` to `04-design-case-handoff/` without rewriting. These files are the design-level business long-chain denominator and reviewer view; they are not the script-generation denominator unless a chain also appears in `required_chain_flows.yaml`.
   - Copy root-level `required_chain_flows.yaml` and `chain_flow_candidate_audit.yaml` to `04-design-case-handoff/` without rewriting. These files are the authoritative execution/script long-chain denominator; `business_scenario_map.yaml` remains business context and candidate evidence.
   - Copy the selected entry `business_scenario_map.yaml` and `业务场景链路清单.md` to `04-design-case-handoff/` without rewriting rows. If the copied map does not match the selected entry, stop with `BLOCKED_NEED_HANDOFF_REPAIR`.
   - Extract or copy only source-present quality, coverage, blocker, repair, and release sections from `04_接口测试用例清单.md` into `04-design-case-handoff/执行报告.md`.
   - If the generation result lacks explicit quality conclusion, coverage matrix, blocker list, or release conclusion, stop with `BLOCKED_NEED_HANDOFF_REPAIR`; do not invent `PASSED`.
   - If the generation result contains `覆盖不足`、`未覆盖`、`待补充`、`阻塞`, a non-100% coverage rate, or a conclusion that does not explicitly allow 100% coverage declaration, stop with `BLOCKED_NEED_HANDOFF_REPAIR`.
5.8. Optionally plan and run runtime live evidence.
   - Run this when the user explicitly asks to directly request interfaces for runtime values, requests broad/full execution-level generation backed by requester evidence, or when execution readiness requires live request evidence and the user provides a runtime evidence configuration.
   - Before any direct request, build `04-runtime-evidence-plan/` from `04-design-case-handoff/case_list.yaml` using source-bound cases and contracts. Use `scripts/build_runtime_evidence_plan.py` when a deterministic helper is useful. The plan must classify every candidate, isolate request-allowed items, list DB before/after probe requirements, and emit blocker/manual-confirmation candidates. It must order requestable candidates by `long_chain -> p0 -> p1 -> p2 -> p3 -> other`, preserving source order only within the same bucket.
   - If `04-design-case-handoff/required_chain_flows.yaml` contains required flows, the runtime evidence plan must include every ordered step for every required flow, preserve step order and producer/consumer dependency, and target full request/response evidence coverage for all requestable steps. Non-requestable steps must still appear as blocked/manual/sandbox/mock/callback evidence items instead of disappearing from the flow.
   - Do not treat "full requester coverage" as permission to request all interfaces. Execute only `request_allowed` or user-configured `request_allowed_with_user_config` items. When user configuration declares selected/generated test cases executable by default in a test environment, this grants case-scope confirmation for the selected denominator only; items outside that denominator still require manual confirmation or remain blocked.
   - Mutating, destructive, external, callback, or cleanup-dependent items must have DB before/after evidence, ownership keys, cleanup strategy, and explicit confirmation before they are executed. Case-scope default authorization satisfies only the confirmation gate; it does not satisfy missing auth, encryption, sandbox/mock input, DB delta, cleanup, or source-alignment evidence.
   - If the runtime execution configuration is missing, incomplete, or lacks required environment fields, materialize `00-inputs/runtime_execution_config.template.yaml`, `00-inputs/前置执行配置待填写.md`, and `00-inputs/runtime_execution_config.missing_fields.yaml` when the missing fields are known, then stop before direct requests. The filled artifact must pass required-field validation before continuing. If the filled environment is not test, require explicit non-test DB authorization before generating DB before/after probes or cleanup steps.
   - Apply the Runtime Request Value Principle: request structure comes from interface contracts, runtime values come from execution configuration and upstream responses, legality is cross-checked by data model/DB MCP evidence, and scenario choice comes from design-level cases.
   - Input must be a configuration artifact, not skill-hardcoded project data: environment aliases/base URL placeholders, auth method, account reference, login contract, ordered request plan, allowed call scope, and cleanup strategy. Every ordered request step must include `module`、`method`、`path`、`expected_status`, and explicit extraction rules for values that will be used downstream. Secrets must be runtime injected and must not be written to output files.
   - Each parameter in `runtime_request_plan.yaml` should cite its structure source, value source, scenario source, or cross-check source. If a parameter cannot be traced to one of those sources, record it as missing input instead of guessing it.
   - Use `scripts/run_live_request_evidence.py` only as a generic direct requester when a deterministic helper is useful. It reads a request plan and writes `04-runtime-evidence/runtime_request_plan.yaml`, `runtime_evidence.yaml`, `runtime_value_catalog.yaml`, `runtime_conflict_report.md`, `runtime_stage_status.yaml`, and optional `runtime_evidence_queue.yaml`. The requester must continue after per-step recoverable failures, record each failed or skipped item in `continuation_queue`, and return a partial evidence state when at least one confirmed item is usable.
   - When a real response is used to fill or predict another step, write a derivation record first: producer step, consumer step, producer field path, consumer field path, value source ref, inference reason, cross-check refs, source status, and usability. Fill execution-level cases only from confirmed derivations in `runtime_value_catalog.yaml`, not from ad hoc requester output or same-name field matching.
   - Direct requester may extract token, business IDs, status fields, business codes, enum values, error codes, response fields, and assertion values. It must redact password、token、Authorization、Cookie and other secrets in all outputs.
   - When an executed case has DB side effects, runtime evidence must include request/response evidence plus DB before/after references, delta assertion, cleanup evidence, and source refs. If DB evidence is missing for a required mutating fact, keep that fact blocked.
   - Cross-check runtime values against `接口结构化契约清单.md`, design-level cases, `数据模型.md`, database MCP evidence, source-extracted facts, and user execution configuration when those sources are available. Any conflict blocks before execution-level release; runtime evidence never overwrites the contract.
   - If runtime evidence is optional and requests fail, record missing values and continue with other confirmed sources. If the user explicitly required runtime evidence, block with `BLOCKED_NEED_EXECUTION_INPUT` and do not generate guessed values.
   - Run `python3 <skill_dir>/scripts/validate_runtime_evidence.py 04-runtime-evidence --require-usable` before passing live evidence to `$executable-interface-case-set`.
6. Run `$executable-interface-case-set`.
   - Input `04-design-case-handoff/case_list.yaml`, `04-design-case-handoff/测试用例清单.md`, `04-design-case-handoff/执行报告.md`, `04-design-case-handoff/接口测试用例设计文档.md`, `04-design-case-handoff/接口结构化契约清单.md`, `04-design-case-handoff/business_long_chain_cases.yaml`, `04-design-case-handoff/业务长链路设计清单.md`, `04-design-case-handoff/required_chain_flows.yaml`, `04-design-case-handoff/chain_flow_candidate_audit.yaml`, `04-design-case-handoff/business_scenario_map.yaml`, `00-inputs/数据模型.md`, optional `04-runtime-evidence-plan/runtime_risk_audit.yaml`、`db_before_after_probe_plan.yaml`、`runtime_blocker_candidates.yaml`, optional `04-runtime-evidence/runtime_evidence.yaml` and `runtime_value_catalog.yaml`, optional classified Apifox MCP evidence when used or required, environment/auth inputs, and source-bound token/data/assertion/cleanup facts when available.
   - Output `05-executable-interface-case-set/执行级接口用例集.md`, `05-executable-interface-case-set/前置数据构造规则.md`, `05-executable-interface-case-set/stage_status.yaml`, `05-executable-interface-case-set/coverage_matrix.yaml`, `05-executable-interface-case-set/execution_fact_sources.yaml`, and `05-executable-interface-case-set/apifox_evidence_index.yaml` when Apifox is consulted or required.
   - Preserve the coverage chain from design to executable cases: `覆盖对象ID`、`覆盖规则ID`、`设计级用例ID`、`追溯测试点` must remain machine-readable in every executable case.
   - For every flow in `required_chain_flows.yaml`, generate execution-level chain evidence: stable `flow_id`, ordered executable case IDs, producer/consumer step relationship, extraction rule, injection target, chain-level assertions, setup and cleanup boundary. If any of these are missing, stop with `BLOCKED_NEED_CHAIN_FLOW_EVIDENCE`; do not continue to script generation with single-interface-only evidence.
   - For every required flow or execution-level long-chain that needs a specific account, role, tenant, permission, or account business state, make the first ordered executable request step the login/auth interface from source-bound evidence. Record `account_specific_chain` and `login_entry_rule` facts in `execution_fact_sources.yaml`, extract token/account context from the login response, and inject those runtime variables into later steps. If login evidence is incomplete, stop with `BLOCKED_NEED_EXECUTION_INPUT` and list the missing fields in the long-chain checklist.
   - When required flows exist, `05-executable-interface-case-set/coverage_matrix.yaml` must separately prove `chain_scenario`、`chain_function`、`chain_process` coverage are 100% with `denominator_scope: long_chain_only`, record `generated_executable_chain_case_count == required_chain_flow_count`, and keep `missing_required_flow_ids=[]`. Single-interface executable cases may be counted in the normal executable coverage, but must not be counted as long-chain coverage.
   - Build `execution_fact_sources.yaml` before claiming `PASSED`; do not pass if token, data, variable, assertion, or cleanup facts have no source-bound `source_ref`. When data or cleanup facts use `data_model`/database/SQL evidence, also require source-bound `relationship_graph` and `ownership_key` facts.
   - Before claiming `PASSED`, run the execution fact closure gate for every runnable case:
     - Request-input closure: main-flow cases must have source-bound values or variable refs for all contract-required business fields; exception cases must identify the deliberately invalid or missing field and expected error evidence.
     - Business-state closure: cases depending on conversation, withdrawal account, call state, balance, block/ban relation, subscription tier, report type, upload asset, onboarding/audit status, or other lifecycle state must have executable setup, verification, cleanup, ownership key, and DB/API evidence when applicable.
     - Session closure: every step must declare `auth_policy` and `session_role`; pre-login steps must not inject login tokens, app user steps must use isolated role contexts, and internal/gateway steps must have confirmed policy evidence.
   - Record closure results in `execution_fact_sources.yaml` with fields or equivalent evidence for `request_input_closure`、`business_state_closure`、`session_closure` and unresolved items. Any unresolved required item must keep the case out of the runnable denominator or block the stage.
   - When any precondition value is created by API setup or DB setup, require a seed-scope guard before claiming `PASSED`: record allowed seeded fields, forbidden seeded fields, runtime/generated fields, source reason, and affected case IDs. If generated setup appears to replace normal request input or chain-produced response values, block instead of generating execution-level cases.
   - If `execution_fact_sources.yaml` references `source_type: live_request_evidence`, `04-runtime-evidence/runtime_evidence.yaml` and `runtime_value_catalog.yaml` must exist; only confirmed runtime values with `usable_for_execution_case=true` may enter execution-level cases.
   - `$executable-interface-case-set` must not directly request live interfaces. It may consume only normalized runtime evidence sidecars produced before this stage.
   - Build `apifox_evidence_index.yaml` only when Apifox evidence is consulted, required by the user, or referenced by `execution_fact_sources.yaml`; Apifox evidence supports the contract and must not silently overwrite it.
   - After long-chain execution cases are generated, scan unresolved long-chain values. If any remain after source, DB, precondition API, runtime evidence, and execution-config completion, write `05-executable-interface-case-set/长链路缺失码值补充清单.md` and `05-executable-interface-case-set/long_chain_missing_value_fields.yaml`, stop with `BLOCKED_NEED_EXECUTION_INPUT`, and ask the user to fill the checklist. After the user returns it, propagate filled values into execution-level cases and sidecars, rerun `$executable-interface-case-set` validation, and only then continue.
7. Generate scripts.
   - Use `$api-test-framework-generator`, not `$source-api-fact-extractor`, for pytest+allure script generation.
   - Input `执行级接口用例集.md`, `前置数据构造规则.md`, and `00-inputs/数据模型.md`.
   - Output `api-test-framework/`, including generated pytest/allure scripts and the final reviewer/archive case ledger `api-test-framework/接口案例.md`.
   - Pass variable-link, dependency evidence, required flow denominator, and independent long-chain coverage evidence from `required_chain_flows.yaml`, `coverage_matrix.yaml`, `execution_fact_sources.yaml`, `执行级接口用例集.md`, and `前置数据构造规则.md` to `$api-test-framework-generator`.
   - Do not call the direct requester, re-request live interfaces, read account passwords, read MCP connections, or fill missing values during script generation. The script generator only consumes `执行级接口用例集.md`, `前置数据构造规则.md`, and `execution_fact_sources.yaml` facts already normalized by the executable stage.
   - If executable cases still lack business codes, token rules, variable links, assertions, cleanup strategy, or any concrete request/response value required by the generated script, stop with `FAILED_SCRIPT_GENERATION_GATE` or `BLOCKED_NEED_EXECUTION_INPUT` instead of generating placeholder scripts.
   - If `05-executable-interface-case-set/long_chain_missing_value_fields.yaml` exists with `status=pending_user_input|blocked` or `open_required_count>0`, do not run `$api-test-framework-generator`. Filled checklist values must already be reflected in the execution-level artifacts; the script generator must not read the human checklist as the only source of runnable values.
   - Require generated E2E flows to be visible as `data/flow_cases.yaml` or `data/flow_cases.py`, `core/flow_runner.py`, and `testcases/test_flows.py` whenever `required_chain_flows.yaml` contains required flows. The pytest entrypoint should make the business chain clear and call `run_flow("<flow_id>", authenticated_client, env_config, runtime_context)`.
   - For account-specific E2E flows, require `data/flow_cases.yaml` or `data/flow_cases.py` to mark the flow as account-specific and keep the first step as the login/auth step. The login step must be executed through the same flow runner, extract token/account context into `runtime_context`, and then let later business steps consume those variables; do not hide login only inside an external fixture for these flows.
   - Do not treat single-interface tests as a substitute for chain scripts. Single-interface tests may remain as coverage support, but every required flow must have its own E2E flow pytest nodeid before the framework can pass.
   - Before declaring scripts runnable, materialize the three closure families into `configs/generation_status.yaml.execution_fact_closure`: no main-flow case may have only public parameters when business fields are required; every stateful case must have executable setup/verify/cleanup or be excluded; every step must have a resolved `auth_policy`、`session_role` and role-consistent identity fields. If any of these fail, keep `pytest_collection_mapping.status` or `runtime_usability.status` blocked and do not count the case in runnable success.
   - Require `api-test-framework/configs/generation_status.yaml` to map every executable case to generated test modules and `pytest_nodeid`, and require `e2e_flow_mapping` plus `chain_script_coverage` to map every required flow id to one collected pytest nodeid. `chain_script_coverage` must separately prove `chain_scenario`、`chain_function`、`chain_process` coverage are 100% with `coverage_denominator: long_chain_only`, record `generated_pytest_flow_count == required_chain_flow_count`, and keep `missing_required_flow_ids=[]`. `collected_test_count` must equal `executable_case_count + e2e_flow_case_count` before claiming coverage-response readiness.
   - Require `$api-test-framework-generator` to apply its runtime usability gate before claiming scripts are runnable: actual run path, stale reports, dependency/syntax status, config-code alignment, auth bootstrap, transport crypto, extraction paths, and pytest collection when dependencies are available. If the user executes a copied framework directory, synchronize fixes to that actual run path before reporting completion.
   - When a generated Allure/pytest report has many failed or broken cases, require `$api-test-framework-generator` to apply its component reference `components/api-test-framework-generator/references/runtime-failure-diagnosis.md` before product-defect triage: first classify each failure against request-input closure, business-state closure, and session closure; then group by actual response code/message, role, path, unresolved variables, login/session contamination, precondition/data-state gaps, and generator defects. Fix generator/runtime closure defects or exclude affected cases from the runnable denominator before rerunning or filing defects.
   - Require `$api-test-framework-generator` to generate and validate the final reviewer/archive case ledger according to its component reference `components/api-test-framework-generator/references/final-case-archive.md`: `接口案例.md` must use plaintext business request/response models, preserve long-chain step labels and producer/consumer variables, redact secrets, cover the same executable denominator, and record `final_case_archive.status=passed` in `configs/generation_status.yaml`. If runtime failure triage is performed, `缺陷列表.md` must be Markdown and must separate confirmed defects from candidates, false positives, and environment/request-configuration items.
   - If executable-case status is not `PASSED`, do not generate runnable test scripts.
8. Validate and retry upstream when downstream cannot consume.
   - Run component validators when present.
   - If a consumer stage cannot pass its gate because a producer output contains unresolved non-blocking items, missing structured fields, incompatible section names, weak traceability, or a handoff shape that the consumer cannot safely use, do not hand-edit the consumer copy. Re-run the responsible producer stage from its source inputs.
   - Before each rerun, compute the stable `retry_key` from producer stage, consumer stage, failed gate, and blocking contract type; read `retry_history.yaml` and append the next attempt. Never reset the count by overwriting the file.
   - After each regeneration, replace the producer stage output as the authoritative version and rerun every downstream gate from that point forward. Earlier attempts may be kept only as retry evidence and must not be consumed by later stages.
   - For the same `retry_key`, retry at most 3 times. If the third regenerated output still fails the consumer gate, write `retry_history.yaml`, set the overall status to `BLOCKED_RETRY_EXHAUSTED`, and stop the whole pipeline.
   - Run this skill's `scripts/validate_pipeline_outputs.py <output-root>` before final response.

## Design-Case Handoff Rules

The handoff adapter is a controlled bridge, not a new generation stage.

Handoff-readable producer contract:

- `prepare_handoff.py` uses strict structural validation and may rely on line-level YAML patterns. Producer stages must therefore emit conservative block-style YAML for handoff-critical sidecars, especially `business_scenario_map.yaml` and `business_long_chain_cases.yaml`.
- `business_scenario_map.yaml.scenario_items[]` must include Chinese `business_domain` and Chinese `executing_role` before handoff. If they are missing, regenerate or repair the selected entry producer output from source facts; do not add them only to the handoff copy.
- `03-interface-testcase-generation/测试覆盖点报告.md` must already contain Chinese `操作步骤` before handoff. Method/path strings such as `POST /api/...` are allowed in `接口链路` and source refs, but they are not valid operation-step prose.
- `03-interface-testcase-generation/business_long_chain_cases.yaml` must expose `chains` as block-list YAML with nested `interfaces`、`source_refs`、`related_test_point_ids`、`related_coverage_rule_ids`; these lists must be non-empty for each passed long-chain row. Do not rely on inline YAML, anchors/aliases, or compact indentation that may be valid YAML but unreadable by the handoff gate.
- If handoff fails for these structural issues, fix the responsible producer artifact under `02-source-api-facts/` or `03-interface-testcase-generation/`, rerun its gate, then rerun `prepare_handoff.py`. Do not silently patch only `04-design-case-handoff/`.

| 来源 | 目标 | 规则 |
|---|---|---|
| selected entry `01_接口测试用例设计文档.md` | `接口测试用例设计文档.md` | 原样复制，只改文件名，不改正文 |
| selected entry `02_接口结构化契约清单.md` | `接口结构化契约清单.md` | 原样复制，只改文件名，不改正文 |
| selected entry `business_scenario_map.yaml` | `business_scenario_map.yaml` | 原样复制，作为执行级业务链路描述、角色、业务域和 E2E flow 候选的结构化依据 |
| selected entry `业务场景链路清单.md` | `业务场景链路清单.md` | 原样复制，作为人工复核业务场景映射的辅助视图 |
| `03-interface-testcase-generation/case_list.yaml` | `case_list.yaml` | 原样复制，作为执行级阶段优先消费的设计级用例主数据 |
| `03-interface-testcase-generation/case_list.yaml` | `测试用例清单.md` | 只做 YAML 包装展示和兼容，不新增用例字段或追溯 ID |
| `03-interface-testcase-generation/business_long_chain_cases.yaml` | `business_long_chain_cases.yaml` | 原样复制，作为设计级业务长链路分母和 P0 覆盖证据 |
| `03-interface-testcase-generation/业务长链路设计清单.md` | `业务长链路设计清单.md` | 原样复制，作为人工复核真实业务长链路场景的辅助视图 |
| `03-interface-testcase-generation/测试覆盖点报告.md` | `测试覆盖点报告.md` | 如存在则原样复制，作为人工检查覆盖点、业务域、业务链路和中文步骤的参考报告，不作为执行级强输入 |
| root `required_chain_flows.yaml` | `required_chain_flows.yaml` | 原样复制，作为执行级和脚本阶段长链路必测分母 |
| root `chain_flow_candidate_audit.yaml` | `chain_flow_candidate_audit.yaml` | 原样复制，作为候选分类审计证据 |
| `04_接口测试用例清单.md` 中的质检/覆盖/准出/阻塞区 | `执行报告.md` | 原样保留阶段状态、覆盖率、阻塞项、修正建议和准出结论 |
| 缺少显式准出结论 | 阻塞 | 记录 `BLOCKED_NEED_HANDOFF_REPAIR` |
| 单文件中只有案例而无门禁 | 阻塞 | 不得补写 `PASSED` |
| 缺少 `测试覆盖点报告.md` | 不阻塞交接 | 在执行报告中记录为人工复核材料缺失；后续阶段继续消费 `case_list.yaml` 和结构化 sidecar |
| 缺少或无法校验 `business_scenario_map.yaml` | 阻塞 | 记录 `BLOCKED_NEED_BUSINESS_SCENARIO_MAPPING`，要求重跑阶段1 |

Use `scripts/prepare_handoff.py` when a deterministic file-level bridge is useful:

```bash
python3 <skill_dir>/scripts/prepare_handoff.py \
  --output-root output/api-automation-pipeline \
  --entry doc
```

`--entry auto` prefers `01-pre-doc-analysis/` when present and falls back to `02-source-api-facts/docs/source-facts/`.


## Apifox Evidence Levels

Apifox MCP evidence is optional unless the user explicitly requires Apifox alignment. When it is used for execution-level facts, it must be indexed by level before use. Runtime request evidence belongs to `04-runtime-evidence/`, not Apifox MCP:

| 证据等级 | 用途 | 不能做什么 |
|---|---|---|
| `project_structure` | 定位项目、模块、目录、接口 ID、接口范围 | 不能补请求字段、响应字段、状态码、断言值 |
| `interface_contract` | 读取 method、path、参数、响应 schema、状态码、错误码 | 与结构化契约冲突时不能覆盖契约，必须阻塞 |
| `saved_case_example` | 读取保存用例、debug case、请求示例、响应示例、样例值 | 只能补样例和执行参数，不能覆盖契约定义 |
| `response_example` | 读取保存的响应示例、响应组件或样例值 | 只能补样例候选，不能代表真实运行时响应，不能覆盖契约定义 |

Conflict priority:

1. `接口结构化契约清单.md`、设计级用例和覆盖矩阵是发布基线；任何 Apifox 证据冲突都先阻塞，不自动覆盖。
2. Runtime values can only come from `04-runtime-evidence/` direct requester outputs; any runtime conflict with contract, design evidence, data model, or assertion basis blocks execution-level release.
3. `saved_case_example` and `response_example` only fill sample values, variable candidates, and execution parameter candidates when aligned with contract; conflicts with `interface_contract` block or require source repair.
4. `project_structure` 只作为查找范围和 ID 证据，不参与字段值、响应值、状态码或断言推导。
5. Apifox MCP 不可用、环境未读出、无保存用例或鉴权变量缺失时，只记录证据缺口；除用户指定 Apifox 为准外，不阻塞执行级准出。

## Failure Branches

- Missing document entry and source entry: write only `00_流水线执行报告.md` with `BLOCKED_MISSING_ENTRY_INPUT`.
- Source/full pipeline target missing data model: run valid source/design stages when their own gates pass, then perform the database MCP-first normalization check before executable filling. Only after MCP is unavailable/unreadable, identity cannot be confirmed, graph/setup/cleanup evidence cannot be generated, or source-DB alignment cannot pass may the run stop with `BLOCKED_NEED_EXECUTION_INPUT` or `FAILED_EXECUTION_READINESS`; record the attempted MCP connector/tool/environment and exact blocker.
- Full pipeline target missing execution readiness input: run valid entry/design stages when their own gates pass, materialize `00-inputs/runtime_execution_config.template.yaml`, `00-inputs/前置执行配置待填写.md`, and `00-inputs/runtime_execution_config.missing_fields.yaml` when fields are known, then stop before executable filling or script generation with `BLOCKED_NEED_EXECUTION_INPUT`; ask the user to fill the generated configuration and continue from execution readiness after validation. Do not mark already passed design-level cases, coverage matrices, business long-chain design denominators, or handoff artifacts as failed only because runtime execution inputs are missing.
- Database MCP identity or source-DB alignment cannot be confirmed: stop before executable filling only after the required DB MCP check has been attempted. Missing MCP/identity confirmation is `BLOCKED_NEED_EXECUTION_INPUT`; concrete table/column/type/constraint conflicts are `FAILED_EXECUTION_READINESS`.
- Entry conflict: stop before case generation and list conflicting method/path/field/status/error-code evidence.
- Entry quality or test-point split failed: stop before case generation with `FAILED_ENTRY_QUALITY_GATE`; list failed input quality checks, missing coverage objects, missing test point mappings, non-100% coverage figures, or failed source fact quality items.
- Business scenario mapping missing or not traceable: stop before case generation with `BLOCKED_NEED_BUSINESS_SCENARIO_MAPPING`; list missing scenario IDs, missing business domains, missing executing roles, missing source refs, low-confidence mappings, missing related test point IDs, or missing coverage rule IDs.
- Business long-chain design denominator missing or fake: before stopping, try to split URL-prefix/API-module/controller-package buckets into real business chains using actor, business object, lifecycle/state change, verification endpoint, and source refs. Keep valid two-interface business scenarios as design-level short-chain or state-transition cases, but do not count them in the business long-chain denominator unless they meet the 3-interface or 5-step threshold. If no valid split remains, stop at design-case generation with `FAILED_DESIGN_CASE_GATE`; list missing `business_long_chain_cases.yaml`, missing `业务长链路设计清单.md`, missing P0 design case mapping, non-100% design coverage, or candidates rejected because they are still buckets rather than real business scenarios.
- Candidate reclassification too coarse: if `chain_flow_candidate_audit.yaml` classifies non-required scenario candidates in bulk as `excluded_readonly` or uses generic reasons such as `已纳入设计级覆盖` without proving they are pure read-only, stop before stage 2 release or downstream handoff. Reclassify them into required flow, design-only long chain, short-chain/state-transition, single-interface mutation, single-interface read-only, external/callback, or evidence-missing buckets, then regenerate the responsible producer outputs from source facts.
- Chain flow denominator missing: if the selected entry has passed but root-level `required_chain_flows.yaml` or `chain_flow_candidate_audit.yaml` is missing, malformed, not passed, has unclassified candidates, or lacks complete closed-loop evidence for any required flow, stop with `BLOCKED_NEED_CHAIN_FLOW_DENOMINATOR` before stage 2. Existing long-chain products are not repair targets for this blocker; regenerate the denominator from source evidence.
- Chain flow evidence missing: if any `required_chain_flows.yaml` flow lacks execution-level ordered steps, extraction/injection rules, chain assertions, setup, or cleanup boundaries, stop with `BLOCKED_NEED_CHAIN_FLOW_EVIDENCE` before script generation. Coverage-point report rows and `business_scenario_map.yaml` may help reviewers spot candidates, but they must not create the downstream hard denominator by themselves.
- Long-chain missing value input pending: if `long_chain_missing_value_fields.yaml.status=pending_user_input` or `open_required_count>0`, stop before script generation with `BLOCKED_NEED_EXECUTION_INPUT`; ask the user to fill `长链路缺失码值补充清单.md`, then rerun execution-level filling so values are copied into executable cases and fact sources.
- Long-chain coverage missing or mixed with unit coverage: stop at the current producer stage with `FAILED_DESIGN_CASE_GATE`, `FAILED_EXECUTION_READINESS`, or `FAILED_SCRIPT_GENERATION_GATE` according to stage. List the missing `chain_scenario`、`chain_function`、`chain_process` denominator, covered count, missing list, or missing `long_chain_only` declaration; do not pass by relying on single-interface coverage.
- Case generation gate failed: do not run executable-case filling.
- Handoff cannot be losslessly extracted: ask for repaired `case_list.yaml` and `执行报告.md`, or rerun a gated case-list stage.
- Execution input missing: keep execution-case output case-free according to `$executable-interface-case-set`.
- Script generation blocked: do not create runnable pytest files.
- Downstream gate cannot consume upstream output: regenerate the upstream producer output and rerun downstream validation. If the same producer-consumer gate fails after 3 attempts, write `retry_history.yaml`, mark `00_流水线执行报告.md` as `BLOCKED_RETRY_EXHAUSTED`, and do not continue with stale or partially compatible files.

## Artifact Templates

`00_流水线执行报告.md` must use this minimum structure:

```markdown
## 阶段结论

- 目标阶段：design/executable/framework
- 流水线状态：PASSED/BLOCKED_MISSING_ENTRY_INPUT/FAILED_ENTRY_QUALITY_GATE/FAILED_ENTRY_ALIGNMENT_GATE/BLOCKED_NEED_BUSINESS_SCENARIO_MAPPING/BLOCKED_NEED_CHAIN_FLOW_DENOMINATOR/BLOCKED_NEED_CHAIN_FLOW_EVIDENCE/FAILED_DESIGN_CASE_GATE/BLOCKED_NEED_HANDOFF_REPAIR/BLOCKED_NEED_EXECUTION_INPUT/FAILED_EXECUTION_READINESS/FAILED_SCRIPT_GENERATION_GATE/BLOCKED_RETRY_EXHAUSTED
- 是否允许进入下一阶段：是/否
- 判断依据：...

## 输入清单

| 输入组 | 路径 | 状态 | 用途 |
|---|---|---|---|

## 阶段产物清单

| 阶段 | Skill | 产物路径 | 阶段状态 | 准出结论 |
|---|---|---|---|---|

## 入口一致性检查

| 对象 | 文档入口证据 | 源码入口证据 | 结论 | 处理建议 |
|---|---|---|---|---|

## 阻塞项与修正建议

| 编号 | 阻塞项 | 影响阶段 | 影响 | 修正建议 |
|---|---|---|---|---|

## 重试与再生成记录

| 生产阶段 | 消费阶段 | 尝试次数 | 最新产物 | 门禁结果 | 结论 |
|---|---:|---:|---|---|---|

## 下游边界

- ...
```

`04-design-case-handoff/执行报告.md` must preserve the source report sections from `04_接口测试用例清单.md`; if it cannot include a quality conclusion, coverage conclusion, blockers, repair suggestions, and release conclusion from source content, do not create a passing handoff.

When `required_chain_flows.yaml` contains required flows, `03-interface-testcase-generation/coverage_matrix.yaml`, `05-executable-interface-case-set/coverage_matrix.yaml`, and `api-test-framework/configs/generation_status.yaml.chain_script_coverage` must include independent long-chain coverage fields:

```yaml
long_chain_coverage_summary:
  denominator_scope: long_chain_only
  chain_scenario_coverage_rate: 100
  chain_function_coverage_rate: 100
  chain_process_coverage_rate: 100
chain_scenario_total: 1
chain_scenario_covered: 1
chain_function_total: 3
chain_function_covered: 3
chain_process_total: 1
chain_process_covered: 1
required_chain_flow_count: 1
generated_design_chain_case_count: 1
generated_executable_chain_case_count: 1
generated_pytest_flow_count: 1
missing_chain_scenario_ids: []
missing_chain_function_ids: []
missing_chain_process_ids: []
missing_required_flow_ids: []
coverage_items:
  - coverage_id: "FLOW-001"
    coverage_type: chain_scenario
    flow_id: "FLOW-001"
    status: covered
    evidence_refs: ["required_chain_flows.yaml#FLOW-001", "case_list.yaml#DC-001"]
  - coverage_id: "CHAIN-FUNC-001"
    coverage_type: chain_function
    flow_id: "FLOW-001"
    status: covered
    evidence_refs: ["接口结构化契约清单.md#API-001"]
  - coverage_id: "CHAIN-PROC-001"
    coverage_type: chain_process
    flow_id: "FLOW-001"
    status: covered
    evidence_refs: ["业务场景链路清单.md#FLOW-001"]
upstream_downstream_mappings:
  - upstream_id: "FLOW-001"
    downstream_ids: ["DC-001", "EC-001", "test_flows.py::test_flow_001"]
    mapping_status: mapped
```

For `generation_status.yaml.chain_script_coverage`, use `coverage_denominator: long_chain_only` if the section cannot reuse `denominator_scope`. These counts are for long-chain cases only. Do not include single-interface or unit-style cases in these denominators.

`03-interface-testcase-generation/测试覆盖点报告.md` must use this table structure:

```markdown
## 测试覆盖点报告

## 覆盖点摘要

- 覆盖率：100%（已映射设计级用例数 1 / 设计级用例总数 1）
- 计算口径：覆盖率 = `测试覆盖点报告.md` 中已列出且 `来源` 可映射到 `case_list.yaml` 的唯一设计级用例数 / `case_list.yaml` 中 passed 设计级用例总数 × 100%。
- 阶段测试点覆盖率：100%（来自 `coverage_matrix.yaml` 的 `test_point_covered/test_point_total`，如该字段存在）
- 长链路重点关注：1 个。长链路定义为 `接口链路` 中接口数量大于等于 3，或操作步骤大于等于 5 步。

| ID | 测试点 | 接口链路 | 关注原因 |
|---|---|---|---|
| TCP-001 | 在订单注册后，用户去支付订单 | 创建订单接口—>支付订单接口—>查询订单接口 | 涉及 3 个接口，需重点检查上下游变量传递和状态一致性 |

| ID | 测试点 | 业务域 | 业务场景 | 来源 | 接口链路 | 前置条件 | 操作步骤 | 预期结果 | 优先级 | 用例类型 |
|---|---|---|---|---|---|---|---|---|---|---|
| TCP-001 | 在订单注册后，用户去支付订单 | 统一支付 | 用户作为支付发起方在业务系统下单后进入统一支付，系统创建支付单、发起支付并回查支付结果，验证支付单从创建到支付完成的业务链路 | 需求 R-001；测试点 TP-001；设计级用例 DC-001 | 创建订单接口—>支付订单接口—>查询订单接口 | 已存在可登录用户，订单已创建且未支付 | 1. 用户登录系统；2. 创建待支付订单；3. 调用支付订单接口；4. 查询订单状态 | 订单支付成功，订单状态为支付完成 | p0 | 正向流程 |
```

Do not add rows whose required fields are unknown. If a row cannot be completed from source-bound design cases, coverage objects, contracts, selected `business_scenario_map.yaml`, or source facts, block stage 2 and record the missing evidence in `04_接口测试用例清单.md` and `stage_status.yaml`. Downstream stages may copy this report for reviewers, but must not use it as an execution prerequisite.

## Downstream Boundary

This skill may create a runnable `api-test-framework/` only after `$executable-interface-case-set` is `PASSED`. It may not invent request values, response values, assertions, accounts, token extraction, setup data, cleanup SQL, Apifox responses, environment URLs, database schema facts, or table graph facts. Database MCP schema and graph facts must be normalized and source-aligned before downstream use.

Runtime request values must already be normalized into `04-runtime-evidence/` and then into execution-level artifacts before script generation. Downstream stages must not use the Runtime Request Value Principle to re-request interfaces, override contracts, or backfill missing execution facts outside the runtime evidence and executable-case filling stages.

## Structured Validation

Run:

```bash
python3 <skill_dir>/scripts/validate_pipeline_outputs.py output/api-automation-pipeline
```

Validation checks:

- `00_流水线执行报告.md` exists and has a recognized target depth and stage status.
- If `retry_history.yaml` exists or the stage status is `BLOCKED_RETRY_EXHAUSTED`, it must have schema version 1, `max_attempts: 3`, explicit retry key, gate id, producer/consumer stages, attempt records, regenerated output paths, gate evidence, and a final blocker.
- At least one entry output exists.
- Each executed entry has its required three Markdown files.
- Document entry proves input-file quality review, test point analysis/splitting, coverage-object traceability, and explicit 100% coverage release before any stage 2 output exists.
- Document entry sidecars prove `status=passed`, `next_stage_allowed=true`, object/test-point/rule coverage counts are 100%, and missing ID lists are empty before any stage 2 output exists.
- Selected entry includes `business_scenario_map.yaml` and `业务场景链路清单.md` before any stage 2 output exists; the map is `status=passed`, `next_stage_allowed=true`, has non-empty `scenario_items`, no blockers, Chinese `business_domain`, Chinese `executing_role`, Chinese `business_description` that includes the executing role, source refs, related interface chains, related test point IDs, and related coverage rule IDs.
- Before any stage 2 output exists, root-level `required_chain_flows.yaml` and `chain_flow_candidate_audit.yaml` must exist after a passed entry release. Existing `flow_generation_required=true`, `chain_type=e2e_flow_candidate`, interface-count, or step-count signals in `business_scenario_map.yaml` are candidate evidence only; they do not define the authoritative long-chain denominator.
- `required_chain_flows.yaml` must be `status=passed`, `next_stage_allowed=true`, have `required_chain_flow_count` equal to the unique required `flow_id` count, and every required flow must include pre-action, observable change, verification, link keys, ordered steps, evidence refs, and `status: required`.
- `chain_flow_candidate_audit.yaml` must be `status=passed`, `next_stage_allowed=true`, classify every candidate as `included`、`design_long_chain_only`、`design_short_chain_state_transition`、`single_interface_mutation`、`single_interface_readonly`、`external_or_callback`、`excluded_missing_verification`、`excluded_missing_change_evidence`、`excluded_missing_link_key` or `excluded_readonly`, and keep `unclassified_candidate_flows=[]`. Non-required business scenarios must not be bulk-classified as `excluded_readonly`; every non-included candidate must have a `downstream_target` and a reason tied to its actual evidence gap or business shape.
- When both document and source entries exist, `chain_flow_alignment.yaml` must classify flow differences as `doc_only`、`source_only`、`both_step_diff` or `both_consistent` without silently dropping evidence-complete flows.
- Source entry quality report is readable and must not be `FAILED` before source-visible facts are used as the design source.
- Source entry artifact manifest includes `source_api_business_scenario_map` and `source_api_business_scenario_doc` before source-visible facts are used as the design source.
- Source entry sidecars use `stage: source_api_facts`, `source_*` denominator fields, denominator totals greater than 0, empty `missing_source_*` lists, and source-type `coverage_items` plus mapped upstream/downstream records.
- When both document and source entries exist, document and source method/path facts must align; conflicts block release as `FAILED_ENTRY_ALIGNMENT_GATE`.
- `case_list.yaml` and `04_接口测试用例清单.md` are present before handoff. When `case_list.yaml.status=passed`, every `cases` item has non-placeholder `case_id`、`design_case_id`、`test_point_ids`、`coverage_object_ids`、`coverage_rule_ids`、`method`、`path`、`status_codes`、`priority`、`assertion_points`.
- `03-interface-testcase-generation/测试覆盖点报告.md` is present before stage 2 release, starts with `覆盖点摘要`, states coverage rate and calculation method, lists or explicitly clears long-chain focus points, contains the eleven required columns including `业务域` and `业务场景`, has at least one mapped row when design cases passed, uses Chinese descriptions in the required review fields, uses `p0/p1/p2`, does not contain unresolved placeholders such as `待确认`、`未知`、`TBD`, and is treated as a human-review artifact rather than a downstream hard dependency.
- Handoff files, including authoritative `case_list.yaml`, are present before executable-case filling.
- Handoff may include `测试覆盖点报告.md` copied from stage 2 as a human-review reference; executable-case filling must not require this report.
- Handoff includes `required_chain_flows.yaml`, `chain_flow_candidate_audit.yaml`, `business_scenario_map.yaml`, and `业务场景链路清单.md` copied from the selected entry/root denominator before executable-case filling.
- Every required flow from `required_chain_flows.yaml` is represented in design-level chain cases, execution-level chain evidence, and `api-test-framework/configs/generation_status.yaml.chain_script_coverage` before framework release; long-chain rows in `测试覆盖点报告.md` and `business_scenario_map.yaml` may be used for review/candidate discovery only.
- Stage 2 and execution-level `coverage_matrix.yaml` must not use single-interface or unit-style cases to satisfy long-chain coverage. The long-chain coverage fields are a separate coverage family and must remain valid even if normal case coverage is already 100%.
- Handoff normalized design and contract files are present before executable-case filling.
- Handoff source has passing quality conclusion, 100% coverage evidence, no unresolved blocker, and explicit 100% release conclusion.
- Every executed `stage_status.yaml` includes `schema_version`、`stage`、`status`、`next_stage_allowed` and `blocking_issues`; non-legacy sidecars also include `input_paths`、`output_paths`、`gate_checks`. Native `$pre-doc-analysis-pipeline` sidecars may use `source_files`、`stage_results`、`output_files`.
- Every downstream `coverage_matrix.yaml` includes `schema_version`、`stage`、`coverage_summary` plus stage-specific top-level counts; passed denominator totals are greater than 0; non-legacy sidecars also include `coverage_items`、`missing_items`、`upstream_downstream_mappings`; each denominator item has exactly one matching `coverage_items.coverage_id` and one mapped upstream/downstream record. Native `$pre-doc-analysis-pipeline` sidecars may use `coverage_objects`.
- Interface testcase generation sidecars prove `status=passed`, `next_stage_allowed=true`, test-point/main-flow/contract-rule/status-code/P0/P1 coverage counts are 100%, and missing ID lists are empty before handoff.
- When `required_chain_flows.yaml` contains required flows, interface testcase generation sidecars also prove long-chain scenario/function/process coverage counts are independently 100%, record `generated_design_chain_case_count == required_chain_flow_count`, and keep `missing_required_flow_ids=[]`.
- Target depth controls required downstream outputs: `design` stops at handoff, `executable` requires execution-level files, and `framework` requires `api-test-framework/`.
- If `00-inputs/database_mcp_evidence_index.yaml` or `00-inputs/source_db_alignment.yaml` exists, the database MCP evidence index and source-DB alignment sidecar must be readable, `status=passed`, conflict/missing/blocking lists empty, relationship/cleanup checks passed, and `00-inputs/数据模型.md` present. If source-entry executable/framework depth lacks a provided data model and no database MCP sidecar exists, the run report must prove DB MCP was unavailable/unreadable or intentionally not authorized before blocking.
- If the run blocks because execution configuration is missing or incomplete, `00-inputs/runtime_execution_config.template.yaml` and `00-inputs/前置执行配置待填写.md` must exist; when required missing fields are known, `00-inputs/runtime_execution_config.missing_fields.yaml` must list them.
- If `04-runtime-evidence-plan/` exists, `runtime_risk_audit.yaml`, `runtime_request_plan.skeleton.yaml`, `db_before_after_probe_plan.yaml`, and `runtime_blocker_candidates.yaml` must exist, use `schema_version=1`, classify every candidate with source refs and reason codes, avoid project-specific hardcoded values, and ensure only request-allowed items can be moved into the executable `runtime_request_plan.yaml`.
- If `required_chain_flows.yaml` contains required flows and `04-runtime-evidence-plan/` exists, the risk audit and request-plan skeleton must reference every required `flow_id` and every ordered flow step, including steps that are blocked, manual, sandbox/mock, or callback-provided. A plan that covers only a subset of convenient interfaces is not sufficient for requester-backed long-chain completion.
- If `04-runtime-evidence/` exists, `runtime_stage_status.yaml`, `runtime_evidence.yaml`, and `runtime_value_catalog.yaml` must exist, be UTF-8, use `schema_version=1`, have legal status values, keep conflict lists empty for passed/partial evidence, and contain no plaintext password、token、Authorization、Cookie or equivalent secrets. If `runtime_stage_status.yaml.continuation_queue` or optional `runtime_evidence_queue.yaml` exists, every item must use `queue_state` with one of `pending/requested/evidenced/retryable/skipped_recoverable/blocked_final/excluded`; nested item-level `status` fields are invalid.
- If `04-runtime-evidence/` exists and its values are used as later request inputs or expected downstream responses, `runtime_evidence.yaml.dependency_derivations` and `runtime_value_catalog.yaml.flow_value_links` must record producer step, consumer step, field paths, value source ref, inference reason, cross-check refs, source status, and usability. Same-name field copying without a recorded business dependency is not valid evidence.
- If runtime evidence candidates, runtime value catalogs, supplemental request results, or replay evidence are used to generate scripts, `api-test-framework/configs/runtime_evidence_script_mapping_audit.yaml` must exist and `generation_status.yaml.runtime_evidence_script_materialization.status` must be `passed` before broad pytest execution or product-defect confirmation. The audit must prove generated plaintext request fields, role/session variables, expected HTTP status, expected business code/message, and per-step evidence ids match the source candidate exactly. A mismatch is `FAILED_RUNTIME_EVIDENCE_SCRIPT_MATERIALIZATION` and must be treated as a generator materialization issue, not a product defect.
- Execution-level files are present before script generation.
- Execution-level stage sidecars prove executable-case coverage inheritance counts are 100% and missing ID lists are empty.
- When `required_chain_flows.yaml` contains required flows, execution-level stage sidecars also prove long-chain scenario/function/process coverage counts are independently 100%, record `generated_executable_chain_case_count == required_chain_flow_count`, and keep `missing_required_flow_ids=[]`.
- If `05-executable-interface-case-set/long_chain_missing_value_fields.yaml` exists, it must use `schema_version=1` and have `status=not_required|filled` with `open_required_count=0` before script generation. If it has `status=pending_user_input|blocked` or any open required item, `api-test-framework/` must be absent and the pipeline must stop at `BLOCKED_NEED_EXECUTION_INPUT`.
- `execution_fact_sources.yaml` exists before script generation and records required human inputs, source-bound token/data/variable/assertion/cleanup facts, seeded values, external dependency values, missing facts, conflicts, and blockers; when passed, `runtime_execution_config`、`environment_reference` and `authentication_account` must be `provided`, every required fact type must have at least one `confirmed` source, and every required `source_ref` must be non-empty. Environment fields are mandatory. Seeded values consumed by execution cases must be confirmed and filled into the corresponding request/assertion/DB/cleanup field as concrete values or executable variable references. If any data or cleanup fact uses API/DB setup, `seed_scope_guard` must be confirmed and must prove that seeded scope does not replace 普通请求值、链路返参值、外部依赖值、token/验证码/设备/分页/运行标识字段。若 `environment_reference.is_test_environment=false`, DB before/after, cleanup, rollback, or status recovery facts require `db_authorization.non_test_reauthorization_status=provided`. When data or cleanup facts use `data_model`/database/SQL evidence, `relationship_graph` and `ownership_key` fact types are also required. When a fact uses `source_type: live_request_evidence`, the referenced `runtime_evidence.yaml#evidence_id` or `runtime_value_catalog.yaml#value_id` must exist, be confirmed, and be usable for execution cases. When a fact uses `source_type: external_sandbox_evidence`, the sandbox/mock/callback evidence must be explicit; local DB seed evidence must not substitute for the external response value. Passed execution facts must also include closure evidence for request inputs, business state, and session/auth policy; unresolved required business fields, state setup/cleanup gaps, pre-login token injection, unresolved auth placeholders, or cross-role token/userId/session mismatch must block or exclude the affected case from the runnable denominator.
- If `execution_fact_sources.yaml` marks any flow as `account_specific_chain` or uses `specific_account_required` / `required_account_role` / `required_account_business_state` 等价字段, a confirmed `login_entry_rule` fact with valid `source_ref` is mandatory before the stage can pass.
- `apifox_evidence_index.yaml` exists when executable-case filling depends on Apifox MCP, classifies evidence as project structure / interface contract / saved case example / response example, and records conflict priority.
- Execution-level cases preserve `覆盖对象ID`、`覆盖规则ID`、`设计级用例ID`、`追溯测试点`.
- If `api-test-framework/` exists, it has the expected project skeleton.
- If `api-test-framework/` exists, `configs/input_precheck_report.yaml` and `configs/generation_status.yaml` exist, and `generation_status.yaml` records `coverage_traceability`、`pytest_collection_mapping`、`pytest_nodeid`.
- If `api-test-framework/` exists, `configs/generation_status.yaml.execution_fact_closure` exists or an equivalent validation section proves request-input closure, business-state closure, and session closure passed for the runnable denominator. It must report zero unresolved main-flow business fields, zero stateful cases without executable setup/verify/cleanup, zero pre-login steps with token injection, zero unresolved auth placeholders, and zero cross-role identity mismatches before runnable success is claimed.
- If `api-test-framework/` exists, `接口案例.md` exists and `generation_status.yaml.final_case_archive.status=passed`; its archive case and flow counts match the same executable/script denominator, and it contains plaintext business request/response models with secrets redacted.
- If `api-test-framework/` exists, `generation_status.yaml.setup_cleanup_materialization.status` must be `passed` before runnable success; mutable cases with only cleanup refs or DB before/after refs must be excluded or block script generation.
- If runtime failure triage produces product-defect output, `缺陷列表.md` must exist as Markdown; confirmed defects must include real scenario, complete plaintext request, complete plaintext response, and DB table/field changes when persistence changed. Items without complete response or DB evidence must stay in candidate sections.
- If `api-test-framework/data/flow_cases.yaml` or `api-test-framework/data/flow_cases.py` marks a flow as account-specific, the first flow step must be a login/auth step and must record token/account-context extraction rules before any business step.
- When `required_chain_flows.yaml` contains required flows, `generation_status.yaml.chain_script_coverage` records `coverage_denominator: long_chain_only`, `generated_pytest_flow_count == required_chain_flow_count`, `missing_required_flow_ids=[]`, required flow IDs, and independent 100% coverage for chain scenarios, chain functions, and chain processes.
