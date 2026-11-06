# 长链路分母契约

## 目录

- [读取时机](#读取时机)
- [双分母防混淆规则](#双分母防混淆规则)
- [规则正文](#规则正文)
- [Business Scenario Long-Chain Design Denominator Contract](#business-scenario-long-chain-design-denominator-contract)
- [Required Chain Flow Denominator Contract](#required-chain-flow-denominator-contract)
- [Business Chain Candidate Inventory](#business-chain-candidate-inventory)
- [来源](#来源)

## 读取时机

阶段1释放后、阶段2生成设计用例前必须读取；阶段2、阶段3、阶段4涉及长链路覆盖时也必须读取。

## 双分母防混淆规则

- 设计级真实业务长链路写入 `business_long_chain_cases.yaml`。
- 执行/脚本闭环必测长链路写入 `required_chain_flows.yaml`。
- 只有 `required_chain_flows.yaml` 能驱动执行级 E2E flow 和 pytest flow 必测分母。
- 设计级长链路可以被覆盖但暂不具备执行闭环事实；不得因此伪造脚本级通过。

## 规则正文

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
- If the selected entry emits only `single_interface` scenarios while the same business object or resource has at least 3 related interfaces including a mutating action and a read/status/detail/list verification action, treat the business scenario map as unfinished. Split it into real business journeys first, or block with a specific missing-evidence reason.
- Evidence-insufficient multi-interface journeys may be `design_long_chain_only` or blocked; they must not be dissolved into unrelated single-interface rows merely to make `business_long_chain_total: 0` pass.
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

Long-chain 100% coverage must switch to the unified closed-loop denominator in `required_chain_flows.yaml`. Existing long-chain artifacts, `business_scenario_map.yaml`, interface-count rules, and step-count rules remain compatibility evidence and candidate discovery signals only; they are not the authoritative denominator for long-chain 100% release. The discovery process must be broad and explicit: write every scenario candidate into `business_chain_candidate_inventory.yaml`, then classify strictly before any flow can enter `required_chain_flows.yaml`.

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
- `excluded_ready_by_policy`: execution closure is complete, but the chain is explicitly excluded from the selected runnable scope. The reconciliation must provide a reason code and evidence refs; this is the only ready-but-not-generated candidate classification.
- `excluded_missing_verification`, `excluded_missing_change_evidence`, or `excluded_missing_link_key`: use only when the candidate appears to be a closed-loop candidate but lacks the named proof. Record the missing proof and do not pass it downstream as required.
- `excluded_readonly`: use only for genuinely read-only route buckets or scenarios whose business result is only observing current state and has no setup/action/change/verification chain. The reason must mention the actual read-only evidence, not a generic statement such as "已纳入设计级覆盖".

Reclassification must preserve all candidates in `business_chain_candidate_inventory.yaml` and `chain_flow_candidate_audit.yaml` with `classification`, `downstream_target`, `scenario_id` or `flow_id`, source refs, discovery signals, missing evidence, and a specific reason. If a previously excluded candidate has create/update/delete/status-change/callback/submit semantics, reclassify it into the proper downstream path before declaring coverage.

Both entry routes must produce the same denominator artifacts before stage 2 is allowed:

- Document route: PRD + API + 系统分析 + 数据模型 evidence -> `business_chain_candidate_inventory.yaml`, `required_chain_flows.yaml`, and `chain_flow_candidate_audit.yaml`.
- Source route: Controller + Service + Mapper/Repository + status enum/constant + DB side effect/query evidence -> `business_chain_candidate_inventory.yaml`, `required_chain_flows.yaml`, and `chain_flow_candidate_audit.yaml`.
- When both routes are executed, also produce `chain_flow_alignment.yaml` and classify differences as `doc_only`、`source_only`、`both_step_diff`、`both_consistent`. Do not silently drop `doc_only` or `source_only` flows when their closed-loop evidence is complete.

`business_chain_candidate_inventory.yaml` is a root-level discovery artifact. It is not a release denominator and must not drive execution/script 100% coverage by itself:

```yaml
schema_version: 1
stage: business_chain_candidate_inventory
status: passed | blocked
next_stage_allowed: true | false
candidate_total: 1
candidate_type_summary:
  business_long_chain_ready: 1
  business_long_chain_need_execution_evidence: 0
  short_state_transition: 0
  single_interface_mutation: 0
  readonly: 0
  external_or_callback: 0
  missing_evidence_candidate: 0
items:
  - candidate_id: CAND-001
    candidate_type: business_long_chain_ready | business_long_chain_need_execution_evidence | short_state_transition | single_interface_mutation | readonly | external_or_callback | missing_evidence_candidate
    classification: included | design_long_chain_only | design_short_chain_state_transition | single_interface_mutation | single_interface_readonly | external_or_callback | excluded_missing_verification | excluded_missing_change_evidence | excluded_missing_link_key | excluded_readonly
    flow_id: FLOW-001
    scenario_id: BS-001
    source_route: doc | source
    business_domain: 账户钱包
    scenario_name: 充值下单验签到钱包明细链路
    executing_role: 用户
    downstream_target: required_chain_flows
    inferred_fields:
      - pre_action_interface_from_steps
      - verification_interface_from_steps
    discovery_signals:
      - actor_evidenced
      - business_domain_evidenced
      - multi_step_business_chain
    missing_evidence: []
    steps:
      - POST /api/v1/account/recharge/createOrder
      - POST /api/v1/account/recharge/verify/googlePay
      - POST /api/v1/account/wallet/diamond-records
    evidence_refs:
      - PRD章节/API接口/源码文件/表字段
    reason: "..."
blocking_issues: []
```

Inventory rules:

- Discover broadly, classify strictly. Preserve all source-visible business candidates in inventory, including design-only chains, short state transitions, single-interface mutations, read-only scenarios, external/callback scenarios, and missing-evidence candidates.
- Conservative inference may fill `pre_action_interface` or `verification_interface` from ordered interface steps when the method/semantic signal is explicit. Do not infer `link_keys`, source refs, observable DB/status evidence, account state, sandbox evidence, or runtime values.
- A candidate in inventory can enter `required_chain_flows.yaml` only after the required-flow closure proves pre-action, observable change, verification, link keys, ordered steps, and evidence refs. Inventory expansion must never loosen the script denominator.

`required_chain_flows.yaml` is a root-level pipeline artifact and the only authoritative denominator for required long-chain coverage:

The root denominator is revisioned by execution facts. The initial file is built from document/source evidence before design generation. If runtime evidence, a filled long-chain field, setup/cleanup materialization, ownership/isolation, DB observation, sandbox/mock/callback evidence, or another execution-readiness fact changes, the previous denominator becomes stale. Create or refresh `chain_execution_readiness_reconciliation.yaml`, hash every consumed fact file, and rerun:

```bash
python3 <skill_dir>/scripts/build_chain_flow_denominator.py \
  --output-root <pipeline-root> \
  --readiness-reconciliation <pipeline-root>/chain_execution_readiness_reconciliation.yaml
```

Then copy the regenerated `required_chain_flows.yaml` and `chain_flow_candidate_audit.yaml` to `04-design-case-handoff/` before executable generation. A hash mismatch must fail without rewriting the existing denominator.

Readiness is capability-based for the requested target depth. Do not require one project-specific chain shape or one fixed `assertion_strength` such as L5. A chain may be ready through `write_restore`, `read_only_verified`, `create_delete_zero_residue`, `isolated_ownership`, `sandbox_mock_callback`, or `state_observation_verified` when source-bound evidence proves the business result and every target-depth materialization item is closed. A write still defaults to cleanup-required unless restore, zero residue, isolated ownership, sandbox containment, no-delta, or an explicit non-live exclusion is evidenced.

Minimum reconciliation shape:

```yaml
schema_version: 1
stage: chain_execution_readiness_reconciliation
status: ready_for_generation | passed
target_depth: executable | framework
fact_revisions:
  - path: 04-runtime-evidence/runtime_evidence.yaml
    sha256: "<64 lowercase hex chars>"
ready_chain_count: 1
generate_count: 1
explicit_exclusion_count: 0
pending_chain_count: 0
ready_chains:
  - flow_id: FLOW-001
    aliases: [TC-CHAIN-001]
    decision: generate | exclude
    closure_capability: write_restore | read_only_verified | create_delete_zero_residue | isolated_ownership | sandbox_mock_callback | state_observation_verified
    supported_target_depths: [executable, framework]
    materialization_status: ready
    unresolved_materialization_items: []
    closure_evidence_refs: [04-runtime-evidence/runtime_evidence.yaml#RT-001]
    executable_case_ids: [EXE-FLOW-001]
    pytest_nodeids: [testcases/test_flows.py::test_flow_001]
    required_flow:
      source_route: doc
      scenario_id: SCN-001
      business_domain: 订单
      scenario_name: 用户创建订单后查询订单状态
      pre_action: {interface: POST /orders}
      observable_change: {type: 订单创建, evidence: 订单由不存在变为可查询}
      verification: {interface: GET /orders/{id}}
      link_keys: [order_id]
      steps: [POST /orders, GET /orders/{id}]
      evidence_refs: [04-runtime-evidence/runtime_evidence.yaml#RT-001]
    exclusion_reason_code: "" # decision=exclude 时必填
    exclusion_evidence_refs: [] # decision=exclude 时必填
pending_chains: []
blocking_issues: []
```

`ready_for_generation` is the pre-generation state: every `decision=generate` item must provide a complete `required_flow`, and the builder regenerates the denominator. Before executable/framework release, refresh to `passed`: generated items must record executable case IDs and framework-depth items must also record pytest nodeids; excluded items must record a non-empty reason code and evidence refs and must not carry generated mappings.

Conservation is mandatory:

```text
execution_ready_chain_count
= generated_chain_decision_count + explicitly_excluded_chain_count
```

Every ready `flow_id` must occur exactly once, ready and pending sets must be disjoint, and the set of `decision=generate` flow IDs must equal the current `required_chain_flows.yaml` required set. A sidecar with `filled_count > 0` cannot pass while `required_chain_flow_count=0` and both generated/excluded sets are empty.

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
    candidate_inventory_type: business_long_chain_ready | business_long_chain_need_execution_evidence | short_state_transition | single_interface_mutation | readonly | external_or_callback | missing_evidence_candidate
    inferred_fields: []
    discovery_signals: ["..."]
    missing_evidence: []
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


## 来源

本文件从 `SKILL.md` 原主契约拆分而来；完整历史契约保存在 `references/full-contract.md`。
