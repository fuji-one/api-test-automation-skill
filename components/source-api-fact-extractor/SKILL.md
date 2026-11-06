---
name: source-api-fact-extractor
description: Use when 用户要求从 Java 后端源码抽取接口事实、接口资产、契约、调用链、业务规则、错误码或源码可见 DB 副作用，适用于 Spring MVC Boot、Feign、Dubbo RPC、MyBatis、JPA 或 Repository 项目。
---

# 源码接口事实抽取

## 何时使用

当用户要求从后端项目源码中整理接口事实基线时使用本 skill。典型场景包括 Java Spring Boot、Spring MVC、Feign、Dubbo/RPC、MyBatis、MyBatis-Plus、JPA、Repository、Controller、Resource、Endpoint、DTO、VO、ErrorCode、Validator、Checker、Manager、DomainService、ApplicationService 等代码库。

本 skill 的核心任务是把源码中可证明的接口事实整理成结构化 JSON 和 Markdown 文档，作为后续接口自动化设计、用例生成或人工评审的事实输入。

## 输入

- `--src <source_root>`：需要扫描的后端源码根目录。
- `--out <output_dir>`：输出根目录，扫描结果会写入 `docs/source-facts/`。

扫描器只读取源码文件：`.java`、`.xml`、`.yml`、`.yaml`、`.properties`。

扫描器默认聚焦可执行源码和配置，跳过工程产物、agent/skill 目录、历史文档、PRD、测试目录和依赖目录，避免样例代码或生成文档进入接口事实清单。

## 输出

运行扫描器和质检器后生成：

- `docs/source-facts/01_接口测试用例设计文档.md`
- `docs/source-facts/02_接口结构化契约清单.md`
- `docs/source-facts/03_skill执行报告.md`
- `docs/source-facts/stage_status.yaml`
- `docs/source-facts/coverage_matrix.yaml`
- `docs/source-facts/business_scenario_map.yaml`
- `docs/source-facts/业务场景链路清单.md`
- `docs/source-facts/source_api_fact_artifacts.yaml`
- `docs/source-facts/01-api-inventory.md`
- `docs/source-facts/02-api-contracts.md`
- `docs/source-facts/03-call-chain.md`
- `docs/source-facts/04-business-rules.md`
- `docs/source-facts/05-source-db-side-effects.md`
- `docs/source-facts/06-unknown-and-risk.md`
- `docs/source-facts/08-security-transform-facts.md`
- `docs/source-facts/09-interface-encryption-policy.md`
- `docs/source-facts/07-extraction-quality-report.md`
- `docs/source-facts/source-api-facts.json`
- `docs/source-facts/source-api-quality-report.json`

其中中文三件套和三个 sidecar 是后续 `interface-testcase-generation` / `api-automation-pipeline-orchestrator` 的主交付；英文拆分文档保留为人工复核兼容视图。

`source_api_fact_artifacts.yaml` 是后续节点的产物调用清单，必须为每个关键文件提供稳定的 `artifact_name`、`path`、`role`、`format` 和 `downstream_consumers`。后续节点优先按 `artifact_name` 引用文件，例如：

- `source_api_design_doc`
- `source_api_contract_list`
- `source_api_security_transform_facts`
- `source_api_interface_encryption_policy`
- `source_api_business_scenario_map`
- `source_api_business_scenario_doc`
- `source_api_fact_json`
- `source_api_coverage_matrix`

## 抽取原则

- 以源码中的注解、方法签名、DTO 字段、校验注解、枚举、异常分支、Repository/Mapper/SQL 和事务注解为事实来源。
- 每个关键结论都带源码证据：文件路径、类名、方法名、字段名；可获取行号时记录行号。
- 命名、注释、目录结构只能作为辅助线索；结论以可定位源码为准。
- 证据不足的内容统一记录为 `UNKNOWN`，并写入 `01_接口测试用例设计文档.md` 的风险章节和 `06-unknown-and-risk.md`。
- 为满足后续用例生成，渲染阶段必须为每个接口生成稳定的 `覆盖对象ID`、`追溯测试点`、`覆盖规则ID`、主要流程 ID 和状态码/错误码索引。
- 为满足后续测试覆盖点报告生成，渲染阶段必须生成 `business_scenario_map.yaml` 和 `业务场景链路清单.md`。源码入口只能输出源码可推断的业务场景，必须标记 `source_entry: source`、`scenario_source_status: source_inferred` 和 `confidence`；不得把源码推断描述伪装成 PRD 确认语义。
- 为满足后续节点调用，每个关键输出必须登记稳定的 `artifact_name`，并同步写入 `source_api_fact_artifacts.yaml`；`stage_status.yaml` 的核心 `output_paths` 也必须包含 `name`。
- 正常返回状态码以 Spring MVC/Feign 的正常返回语义登记为 `HTTP_200`；业务错误码只来自源码显式异常分支，不得编造业务成功码、请求样例、响应样例或执行级断言。
- 必须抽取源码可见的加密、解密、哈希、密码校验、Token、签名、预签名 URL 和外部验签事实，并生成 `security_transforms`、`project_security_transforms`、`secret_config_refs`。
- 对源码配置中已经明文可见的密钥、secret、password、token、key，`source-api-facts.json` 只能保留稳定的 `secret_ref`、敏感级别和遮蔽值；真实值必须由环境变量、测试配置或密钥管理系统在运行时注入，机器产物和 Markdown 均不得保留明文。
- 加密签名规则必须进入下游 `覆盖规则ID`，使脚本生成阶段能区分可确定性哈希、不可确定性 BCrypt、随机 Redis token、HMAC 签名和 OSS 预签名 URL。
- 必须区分“字段/签名/哈希/Token 转换事实”和“接口传输层请求加密、响应解密策略”。前者来自源码内算法调用，后者来自入口类型、路径、调用方、网关/客户端约定或用户确认。
- 源码入口必须生成 `project_encryption_policy` 和每个 API 的 `transport_encryption_policy`，并渲染 `09-interface-encryption-policy.md`。策略字段至少包含 `channel_type`、`policy_hint`、`confidence`、`reason_codes`、`evidence_refs`、`requires_manual_confirmation`。
- 接口传输加解密识别必须使用泛化分类机制：健康检查、内部服务接口、第三方回调、登录/认证入口、App 公开业务接口、未知入口等流量类型只作为分类规则，不得把某个项目的路径清单硬编码为通用白名单。
- `no_encrypt_candidate` 只表示源码候选结论；只有用户确认、网关配置、客户端协议或执行配置确认后，后续脚本才可固化为明文调用。`policy_required` 必须阻塞或要求补充策略，不得猜测。

## 工作流

1. 运行扫描器：

   ```bash
   python3 <skill_dir>/scripts/scan_source.py --src <source_root> --out <output_dir>
   ```

2. 运行抽取后质检：

   ```bash
   python3 <skill_dir>/scripts/quality_check_source_facts.py \
     --src <source_root> \
     --facts <output_dir>/docs/source-facts/source-api-facts.json \
     --out <output_dir>/docs/source-facts
   ```

3. 优先查看 `source-api-quality-report.json`、`07-extraction-quality-report.md` 和 `03_skill执行报告.md`。质检结论为 `FAILED` 时，先处理 ERROR，再重新抽取和质检。
4. 再查看 `source-api-facts.json`、`stage_status.yaml`、`coverage_matrix.yaml`、`business_scenario_map.yaml` 和 `source_api_fact_artifacts.yaml`，确认机器可读结构化覆盖情况。
5. 最后查看中文三件套、`业务场景链路清单.md` 和 8 份事实 Markdown 文档，供人工复核或下游消费。
6. 如后续要生成可执行脚本，优先读取 `08-security-transform-facts.md`、`09-interface-encryption-policy.md` 和 `source-api-facts.json` 中的 `security_transforms`、`secret_config_refs`、`project_encryption_policy`，避免把密文、哈希、签名、随机 token 和接口传输加解密策略断言错。
7. 所有结论必须限制在源码可证明范围内。
8. 所有歧义、动态逻辑和无法确认项必须集中进入 `01_接口测试用例设计文档.md` 的无法确认项章节和 `06-unknown-and-risk.md`。

## 业务场景映射产物

源码入口必须输出与文档入口一致的业务场景映射 schema，作为后续 `测试覆盖点报告.md` 的 `业务场景` 字段来源。

```yaml
schema_version: 1
stage: business_scenario_mapping
status: passed | blocked | partial
next_stage_allowed: true | false
source_entry: source
scenario_source_status: source_inferred
scenario_items:
  - scenario_id: "BS-SRC-001"
    scenario_name: "用户触发支付单支付接口"
    business_description: "用户调用支付单支付入口，系统校验请求字段、执行业务规则并按源码可见副作用更新支付相关数据，验证该接口在源码可证明范围内的主业务链路"
    roles: ["用户", "后端服务"]
    source_refs: ["OrderPayController.java#pay"]
    related_interfaces: ["支付单支付接口"]
    business_chain: ["接收支付请求", "校验业务规则", "返回支付结果"]
    state_chain: ["HTTP_200"]
    chain_type: single_interface | e2e_flow_candidate
    flow_generation_required: false
    flow_id: ""
    ordered_step_count: 1
    ordered_steps:
      - step_order: 1
        interface: "支付单支付接口"
        test_point_id: "TP-SRC-001-MAIN"
        source_ref: "OrderPayController.java#pay"
    related_test_point_ids: ["TP-SRC-001-MAIN"]
    related_coverage_rule_ids: ["RULE-SRC-001-CONTRACT"]
    confidence: medium
    blockers: []
blocking_issues: []
```

Rules:

- `business_description` 必须为中文业务链路描述，不能只写 method/path、类名、方法名或测试类型。
- `source_refs` 来自 Controller/RPC 入口、ApplicationService/DomainService、业务规则、异常分支、状态/枚举、事件或 DB 副作用等源码证据。
- `related_interfaces` 使用业务接口名称；当源码只能确认单接口时，只登记单接口，不编造跨接口链路。
- 当源码事实能稳定识别同一资源或同一业务动作下的多接口顺序时，必须新增 `chain_type: e2e_flow_candidate` 的场景，设置 `flow_generation_required: true`、稳定 `flow_id`、`ordered_step_count >= 2` 和 `ordered_steps`，供下游生成链路脚本。
- `business_chain` 可从入口方法语义、业务规则、DB 副作用和返回语义推断；推断项必须保持保守。
- `state_chain` 只能使用源码显式状态、错误码、枚举、事件或框架正常返回语义。
- 每个可放行 scenario 必须绑定 `related_test_point_ids` 和 `related_coverage_rule_ids`。
- 源码无法推断清楚的业务场景必须进入 `blockers` 或 `blocking_issues`，不得进入 passed 映射。
- 当同一业务对象或资源下存在 3 个及以上相关接口，且同时包含写入/提交/状态变更动作与查询/详情/状态/列表校验动作时，不允许全部输出为 `single_interface`；必须先按执行角色、业务动作、前置状态和预期业务结果拆成真实业务链路候选。
- 如果证据不足以确认接口顺序或校验闭环，也必须写入 `design_long_chain_only` 或阻塞原因，不得用单接口拆散来规避长链路分母。
- `业务场景链路清单.md` 是同一 sidecar 的人工视图，字段必须包含 `业务场景ID`、`业务场景名称`、`业务场景描述`、`链路类型`、`是否必须生成链路脚本`、`flow_id`、`步骤数`、`角色`、`来源`、`业务链路`、`接口链路`、`状态链路`、`关联测试点ID`、`关联覆盖规则ID`、`置信度`、`阻塞项`。

## 证据要求

每个接口、字段、规则、调用链节点和 DB 副作用都要记录源码证据：

- 源码路径
- 类名
- 方法名
- 字段名，如适用
- 行号，如可获取
- 证据类型，例如 annotation、signature、DTO field、validation annotation、exception throw、repository call、mapper XML、enum、transaction annotation

## UNKNOWN 处理

以下情况统一记录为 `UNKNOWN`：

- 接口路径或 HTTP method 无法从源码注解确认
- 请求字段或响应字段来自生成代码、缺失类或无法解析类型
- 鉴权和权限逻辑无法从注解或源码确认
- 动态路由
- 反射调用
- 难以静态绑定到接口的 AOP 或拦截器逻辑
- 难以静态解析的策略分发
- Mapper XML、SQL 注解或 Entity 元数据中无法确认 DB 表名
- 多模块调用链中断，无法继续从源码追踪

每个 UNKNOWN 项都必须包含 `unknown_id`、`api_id`、`unknown_type`、`description`、`why_unknown`、`evidence_or_location` 和 `suggested_manual_check`。

`06-unknown-and-risk.md` 按可行动性分层展示：

- 项目级聚合项：适合统一处理的问题，例如入口源码缺少鉴权注解、部分接口未发现源码可见 DB 访问链路。
- 接口级明细项：会影响单接口契约或后续入参生成的问题，例如项目 DTO 缺失、响应类型缺失、路径或 HTTP 方法缺失。
- 每项都要标记 `severity` 和 `action_required`。`CONDITIONAL` 表示只有当后续自动化依赖该事实时才需要人工确认。
- `String`、`Object`、`Map`、无参请求等非 DTO 类型按“无结构化请求 DTO”或原始参数事实呈现。
- 已识别 DB 操作但表名缺失属于质检错误；未发现 DB 访问链路作为项目级聚合项呈现。

## 输出结构

JSON 输出结构如下：

```json
{
  "project": {
    "name": "UNKNOWN",
    "scan_root": "",
    "language": "",
    "frameworks_detected": [],
    "generated_at": ""
  },
  "project_unknowns": [
    {
      "unknown_id": "",
      "api_id": "PROJECT",
      "scope": "PROJECT",
      "unknown_type": "",
      "severity": "",
      "action_required": "",
      "affected_api_count": 0,
      "affected_api_ids": [],
      "description": "",
      "why_unknown": "",
      "evidence_or_location": "",
      "suggested_manual_check": ""
    }
  ],
  "project_security_transforms": [],
  "project_encryption_policy": {
    "schema_version": 1,
    "source": "source_api_fact_extractor",
    "policy_source_status": "source_inferred",
    "default_policy": "",
    "confirmation_required": true,
    "classification_rules": [],
    "policy_summary": {},
    "policy_items": [],
    "blocking_issues": []
  },
  "secret_config_refs": [
    {
      "config_key": "",
      "secret_ref": "",
      "sensitivity": "",
      "value_visible": "",
      "config_value_masked": "",
      "execution_impact": "",
      "script_strategy": "",
      "evidence": ""
    }
  ],
  "apis": [
    {
      "api_id": "",
      "entry": {},
      "contract": {},
      "call_chain": [],
      "business_rules": [],
      "db_side_effects": [],
      "security_transforms": [],
      "transport_encryption_policy": {
        "api_id": "",
        "module": "",
        "http_method": "",
        "path": "",
        "entry_type": "",
        "class_name": "",
        "method_name": "",
        "channel_type": "",
        "policy_hint": "",
        "confidence": "",
        "policy_status": "source_inferred",
        "requires_manual_confirmation": true,
        "reason_codes": [],
        "evidence_refs": []
      },
      "unknowns": []
    }
  ],
  "summary": {
    "api_count": 0,
    "http_api_count": 0,
    "rpc_api_count": 0,
    "unknown_path_count": 0,
    "write_api_count": 0,
    "read_api_count": 0,
    "business_rule_count": 0,
    "security_transform_count": 0,
    "secret_config_ref_count": 0,
    "error_code_count": 0,
    "unknown_count": 0
  }
}
```

## 示例

扫描当前仓库，并把结果写入临时目录：

```bash
python3 <component_dir>/scripts/scan_source.py \
  --src . \
  --out /tmp/source-api-facts

python3 <component_dir>/scripts/quality_check_source_facts.py \
  --src . \
  --facts /tmp/source-api-facts/docs/source-facts/source-api-facts.json \
  --out /tmp/source-api-facts/docs/source-facts
```

扫描内置示例项目：

```bash
python3 <component_dir>/scripts/scan_source.py \
  --src <component_dir>/examples/sample-java-project \
  --out /tmp/source-api-fact-sample

python3 <component_dir>/scripts/quality_check_source_facts.py \
  --src <component_dir>/examples/sample-java-project \
  --facts /tmp/source-api-fact-sample/docs/source-facts/source-api-facts.json \
  --out /tmp/source-api-fact-sample/docs/source-facts
```

## 质量检查清单

- 输出文件齐全，`source-api-facts.json` 可解析。
- `apis` 明细结构完整，每个 API 都有稳定且唯一的 `api_id`。
- `summary` 统计值和 `apis` 明细重新计算结果一致。
- 源码证据路径存在，行号在文件范围内。
- 独立复扫 Controller、Resource、Endpoint、Feign/RPC 映射入口，并与事实文件对账。
- Feign/interface 方法需要覆盖无 `public` 修饰符的方法签名。
- 发现源码映射入口在事实文件中缺失时，记录 `MISSING_SOURCE_API` ERROR。
- 发现 Feign 数量不一致时，记录 `FEIGN_COUNT_MISMATCH` ERROR。
- 发现 DTO/VO 类型存在但字段为空时，记录 WARN 并给出复核建议。
- 已识别出 READ/CREATE/UPDATE/DELETE/UPSERT 的 DB 操作时，表名和源码证据必须明确；缺失表名记录 `DB_TABLE_UNRESOLVED` ERROR，缺失证据记录 `DB_EVIDENCE_MISSING` ERROR。
- 写操作表名明确时，副作用级别必须是 `CONFIRMED`；否则记录 `DB_WRITE_LEVEL_MISMATCH` ERROR。
- `security_transforms` 必须是数组；每条转换规则必须有 `transform_id`、`transform_type`、`algorithm`、`deterministic`、`requires_secret`、`script_assertion_strategy` 和源码证据。
- `secret_config_refs` 必须是数组；每项必须包含稳定的 `secret_ref` 和 `config_value_masked`，JSON 与 Markdown 均禁止保留明文 `config_value`。
- `project_encryption_policy.policy_items` 必须覆盖全部 API；每个 API 必须有 `transport_encryption_policy`，且包含 `channel_type`、`policy_hint`、`confidence`、`reason_codes` 和源码证据。
- `policy_hint` 只能使用 `no_encrypt_candidate`、`requires_encryption_if_project_default_enabled`、`policy_required`；候选豁免不得直接等同于确认豁免。
- `business_scenario_map.yaml` 和 `业务场景链路清单.md` 必须存在，且每个场景能追溯到源码证据、测试点 ID 和覆盖规则 ID；`flow_generation_required=true` 的场景必须具备 `flow_id` 和不少于 2 步的 `ordered_steps`。
- `source_api_fact_artifacts.yaml` 必须存在，且至少包含 `source_api_design_doc`、`source_api_contract_list`、`source_api_stage_report`、`source_api_security_transform_facts`、`source_api_interface_encryption_policy`、`source_api_business_scenario_map`、`source_api_business_scenario_doc`、`source_api_stage_status`、`source_api_coverage_matrix`、`source_api_fact_json`、`source_api_fact_artifact_manifest`。
- 缺失事实标记为 `UNKNOWN`。
- DTO 校验注解已抽取。
- 可见时区分响应包装类型和响应体类型。
- 调用链记录静态追踪可达路径，并在追踪边界处停止。
- 业务规则来自校验注解或显式代码分支。
- DB 副作用来自 Mapper、Repository、DAO、SQL、Entity/DO 或事务注解。
