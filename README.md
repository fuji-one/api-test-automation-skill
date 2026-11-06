# API Automation Pipeline Suite

面向 Codex 的中文接口自动化 Skill 套件。支持 **Java 源码路线** 和 **业务文档路线**，将输入中的接口与业务事实逐步转化为测试设计、执行级用例和 pytest + requests + Allure 工程。

核心能力是 **以 100% 可追溯覆盖为阶段准出目标，以来源证据、逐用例置信度和执行闭环约束生成准确性**。每个阶段都留下可检查的覆盖清单、来源映射和门禁结果，让遗漏、冲突和执行条件缺口能够被定位。

本项目由代理指令、事实抽取工具、校验器和工程模板组成，分析与生成阶段需要支持 Skill 的代理执行。覆盖门禁衡量的是已识别、明确且可测试的输入内容；它不等同于源码行覆盖率，也不承诺未知需求或业务推理的绝对正确率。

## 覆盖率保证措施

采用“先建立覆盖对象池，再生成用例，最后反向验收”的流程。覆盖不只按用例数量衡量，还要按稳定 ID 验证需求、规则、业务链路和脚本之间的对应关系。

| 保证措施 | 检查内容 | 未满足时的处理 |
| --- | --- | --- |
| 输入质量门禁 | 文档完整性及一致性；源码事实抽取质量及来源证据 | 报告缺失或冲突，停止受影响阶段 |
| 覆盖对象与来源追踪 | 需求、接口、字段规则、错误码、状态迁移和依赖补偿等对象具有 ID 与来源 | 补齐对象和映射后重新验收 |
| 反向覆盖校验 | 从覆盖对象检查用例，发现未覆盖项；保留 `coverage_matrix.yaml` 和 `stage_status.yaml` | 不将部分覆盖作为 100% 准出传给下游 |
| 业务链路独立覆盖 | 单接口用例与多接口业务链路分别核对，检查有序步骤及生产者—消费者依赖 | 单接口覆盖不能抵消业务链路遗漏 |
| 执行链路清单重算 | 运行证据、补值、前置状态或清理事实变化后，重新计算必须生成的链路 | 拒绝沿用过期清单或把待执行链路静默清零 |
| 用例与脚本 ID 守恒 | 执行级用例、必需 Flow、结构化数据、pytest 映射和收集结果逐项对账 | 数量相同但 ID 不同仍不能通过 |
| 非实时执行项保留 | 非实时执行、低置信度和人工复核用例仍保留来源、分类与原因 | 不通过删除困难用例缩小覆盖范围 |

设计级业务长链路由 `business_long_chain_cases.yaml` 记录；执行与脚本阶段必须生成的链路以 `required_chain_flows.yaml` 为准。两者分别验收，避免把“已设计”误报成“已生成可执行链路”。

**100% 的含义：** 对当前输入及阶段确认的覆盖对象，必须完成可追溯覆盖才能声明阶段通过。缺失的业务语义、动态代码逻辑或外部系统行为仍需补充证据；生成脚本、脚本可执行和实测通过也分别报告。

详细规则：[流水线门禁](references/pipeline-gates.md)、[业务链路契约](references/chain-flow-contract.md)、[用例 ID 守恒](components/api-test-framework-generator/references/case-denominator-conservation.md)。

## 准确性保证措施

准确性保障落实在“事实有来源、推断有标记、执行有证据、缺口有门禁”四个环节。项目没有给出经基准数据验证的统一准确率百分比。

| 保证措施 | 如何降低生成错误 |
| --- | --- |
| 来源绑定 | 接口、字段、规则、错误码及断言引用文档章节或可定位源码；命名与注释仅作辅助线索 |
| 未知项显式记录 | 源码无法证明的结论记录为 `UNKNOWN`；源码推断场景标记 `source_inferred`，不能伪装为 PRD 确认语义 |
| 禁止无证据补齐 | 不猜测业务 ID、枚举码值、Token 提取路径、成功码、数据库表结构或清理 SQL；普通合法样本仅在契约允许且无需项目专属字典时使用 |
| 交叉校验 | 对齐接口契约、源码、数据模型和可选运行证据；源码与数据库的表、字段、约束和清理边界冲突会阻止执行级准出 |
| 请求合法性与异常隔离 | 正向请求包含来源可见的必填字段并保持类型和嵌套结构；异常用例只引入目标缺陷，其他必填字段及鉴权条件保持合法 |
| 业务结果可观察 | 通过响应、后续详情/列表/状态 API 或必要数据库断言验证业务结果；不能仅凭请求成功断言业务成功 |
| 前置状态及会话闭合 | 明确角色、账号、Token、业务状态、前置数据和跨步骤变量；账号组复用鉴权，独立用例隔离业务变量 |
| 写操作与清理闭环 | 前置、写入、清理和最终验证绑定本次测试对象；请求失败或响应 ID 缺失时也考虑可执行的归属查找与清理路径 |
| 运行证据分层 | 真实请求证据先归档并归一化，再用于执行级用例；脚本生成阶段消费已确认事实，不现场猜值或补请求 |
| 确定性校验 | 使用结构化状态、校验脚本及 pytest 收集核对产物，而不是仅凭代理描述声明通过 |

### 逐用例置信度

每个设计用例、执行级用例和 E2E Flow 都记录置信度及证据来源。评分按契约 **25%**、请求具体化 **20%**、场景前置 **20%**、业务断言 **20%**、运行可重复性 **15%** 加权，应用证据缺口的硬上限后向下取整到 `0.05`；设计阶段不适用的执行维度按契约重新归一化。

- 来源冲突、入参未确认、业务状态不闭合、清理未落实或外部沙箱缺失都会限制得分。
- 下游提高得分必须新增证据并解除相关缺口，不能只手动修改分数。
- 低置信度用例不能进入实时执行的 pytest 清单，但保留在覆盖和复核记录中。
- 中高置信度仍须通过断言、前置、清理、加密及执行门禁。
- E2E Flow 的置信度受最弱必需步骤约束。

置信度反映证据完整性与可重复性，**不是测试通过概率或统计意义上的准确率**。详细规则见[置信度契约](references/case-confidence-contract.md)、[执行事实闭合](references/execution-fact-closure.md)、[运行证据策略](references/runtime-evidence-policy.md)。

## 源码路线与文档路线

| 对比项 | Java 源码路线 | 业务文档路线 |
| --- | --- | --- |
| 适用场景 | 有后端源码，需要从实现建立接口事实基线 | 有完整需求与设计材料，需要按业务意图设计测试 |
| 初始输入 | Java 后端源码根目录 | Markdown PRD、API、系统分析、数据模型四件套 |
| 核心依据 | 注解、方法签名、DTO、校验规则、枚举、异常分支、调用链及 Mapper/Repository/SQL | 文档中明确的需求、接口契约、业务流程、状态规则及数据关系 |
| 入口组件 | `source-api-fact-extractor` | `pre-doc-analysis-pipeline` |
| 入口检查 | 抽取后质检、接口入口复扫、证据和未知项检查 | 文档预检、内部及跨文档一致性检查、测试点与设计反向覆盖 |
| 语义边界 | 源码可证明事实；业务场景推断需显式标记 | 文档明确可测试内容；缺失、口头或隐藏需求不计为已覆盖 |
| 下游流程 | 统一进入设计用例、执行级用例与自动化工程生成 | 统一进入设计用例、执行级用例与自动化工程生成 |

同时满足完整四件套与源码入口时，默认优先文档路线；入口选择由预检和路由规则决定，事实冲突需要报告和解决。

### 路线 A：从 Java 源码建立事实基线

```text
Java 源码与配置
→ 接口、契约、调用链、业务规则、DB 副作用、加密事实抽取
→ 独立质检与未知项记录
→ 中文设计/契约/执行报告 + JSON/YAML 事实与业务场景映射
→ 设计级用例 → 执行级用例 → pytest + Allure 工程
```

适用于 Spring MVC / Spring Boot、Feign、Dubbo/RPC、MyBatis、JPA / Repository 等源码可见结构。扫描 `.java`、`.xml`、`.yml`、`.yaml`、`.properties`，默认跳过工程产物、历史文档、测试与依赖目录，降低无关样例混入事实清单的风险。

源码路线不要求同时提供 PRD、API 和系统分析文档。继续到执行级或工程级时，如缺少归一化数据模型，先检查可用数据库 MCP 能否提供 schema、关系及约束证据，并完成源码—数据库一致性对账；仍无法确认时才报告相应执行输入阻塞。数据库 MCP 是上游证据源，生成工程不依赖 MCP 运行。

调用示例：

```text
使用 $api-automation-pipeline-suite。
源码目录：<Java 后端项目绝对路径>
输出目录：<产物绝对路径>
目标深度：design
走源码路线，输出接口事实、未知项、覆盖矩阵和设计级用例。
```

### 路线 B：从业务文档建立覆盖对象

```text
PRD + API + 系统分析 + 数据模型
→ 文档预检与一致性校验
→ 测试点分析、需求—接口—状态映射及结构化契约
→ 接口测试用例设计与反向覆盖验收
→ 设计级用例 → 执行级用例 → pytest + Allure 工程
```

文档路线以明确需求和设计内容为基线。建立字段—规则—断言、错误码—异常、状态迁移—入口、依赖失败—补偿等映射，将业务意图转成可追溯覆盖对象。文档缺失、含糊或互相矛盾时输出修改建议及阻塞原因。

调用示例：

```text
使用 $api-automation-pipeline-suite。
输入：<PRD.md>、<API.md>、<系统分析.md>、<数据模型.md>
输出目录：<产物绝对路径>
目标深度：framework
走文档路线，先校验文档质量，再生成可追溯用例和自动化工程。
```

### 两条路线共用的交付深度

| 目标 | 交付范围 |
| --- | --- |
| `design` | 设计级用例、覆盖报告与可继续消费的交接材料 |
| `executable` | 进一步生成执行级接口用例、前置数据构造与清理规则、执行事实来源 |
| `framework` | 进一步生成自动化工程、pytest 映射、配置及最终校验结果 |

环境、账号或 Token 缺失不应阻断本身事实充分的入口和设计阶段。执行与工程阶段根据缺口性质阻塞，或在能够提供来源明确的配置入口时继续生成并标记 `pending_runtime_config`；生成完成不代表已具备实时执行条件，更不代表真实接口实测通过。

运行取证按需启用，必须具备允许调用范围、鉴权及清理条件。Apifox 可作为辅助契约或示例证据；它不替代真实运行取证。

## 功能与组成

| 路径 | 用途 |
| --- | --- |
| `SKILL.md` | 总编排、阶段顺序、覆盖及完成门禁 |
| `agents/openai.yaml` | 代理展示及调用配置 |
| `references/` | 交接契约、长链路、运行证据、置信度和准出规则 |
| `scripts/` | 入口路由、链路清单、交接、证据及最终校验 |
| `components/pre-doc-analysis-pipeline/` | 文档入口编排 |
| `components/doc-precheck-coverage/` | 文档预检 |
| `components/test-point-analysis/` | 测试点与结构化契约 |
| `components/interface-testcase-design/` | 用例设计 |
| `components/source-api-fact-extractor/` | Java 接口、业务规则及副作用抽取 |
| `components/interface-testcase-generation/` | 设计级用例生成 |
| `components/executable-interface-case-set/` | 执行级用例、前置数据与清理规则 |
| `components/api-test-framework-generator/` | 自动化工程生成与校验 |

平台传输模块已移除。项目不包含自动上传测试平台的流程。

## 安装与使用

将整个项目目录复制到 Codex 的个人 skills 目录，保持目录名为 `api-automation-pipeline-suite`，并保留所有子目录。Windows 常见路径为 `%USERPROFILE%\.codex\skills\api-automation-pipeline-suite`。

在支持 skill 的代理中显式调用，例如：

```text
使用 $api-automation-pipeline-suite，读取指定 Java 后端源码，
输出到指定目录，目标深度为 design。先报告缺失输入和门禁结果。
```

支持 `design`、`executable`、`framework` 三种深度。文档入口使用 PRD、API、系统分析和数据模型四件套；源码入口支持 Java / Spring MVC / Feign / Dubbo / MyBatis / JPA 等源码可见事实。执行级阶段仍需要充分的数据模型和运行事实。

实际接口、账号、数据库、加密或外部依赖缺失时，由门禁决定阻塞或非实时执行分类，不自动编造参数或断言。100% 覆盖指输入中明确、可测试内容的可追溯覆盖。

## 本地开发与验证

Python 3.10+。在项目根目录运行：

```sh
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install --require-hashes --only-binary=:all: -r requirements-dev.txt
python scripts/check_skill_package.py
python -m pytest -q
```

根测试集合包含流水线门禁、源码抽取、子模块校验器与安全回归测试；不会直接执行模板中的业务接口测试。生成工程自身的依赖见模板 `requirements.txt`，已固定直接及间接依赖版本并包含官方 PyPI wheel 的 SHA-256 哈希。加密适配使用进程内 `cryptography`，保持既有 AES-256-ECB/PKCS7/Base64 协议，不再通过 OpenSSL 命令行传递密钥；Allure HTML 报告仍需额外的 Allure CLI。

安全修复保持阶段流程、覆盖率口径、CLI 参数和输出文件名不变。直接取证仍支持登录、只读请求、已授权写请求和按序清理。写请求发送前必须有可执行清理及最终验证步骤（或带理由的无清理豁免）；具体字段见 [运行时取证策略](references/runtime-evidence-policy.md#执行前安全检查)。SQL UPDATE/DELETE 的每个条件分支必须等值绑定声明的归属键，写入行数必须声明精确值或上限。旧计划若仅声明清理存在、实际没有清理步骤，或 SQL 仅有行数下限，需要补齐这些安全字段后执行。

源码抽取示例：

```sh
python components/source-api-fact-extractor/scripts/scan_source.py --src components/source-api-fact-extractor/examples/sample-java-project --out output/sample
python components/source-api-fact-extractor/scripts/quality_check_source_facts.py --src components/source-api-fact-extractor/examples/sample-java-project --facts output/sample/docs/source-facts/source-api-facts.json
```

其他脚本参数通过 `python <脚本路径> --help` 查看。CI 配置覆盖 Windows/Linux 和 Python 3.10–3.12；远端运行结果以 GitHub Actions 为准。

## 发布与贡献

提交整个项目目录的源码、模板和文档。不要提交虚拟环境、输出用例、业务源码、运行证据或真实账号和密钥。模板配置保持为空或示例占位值；真实配置存储在本地忽略文件中。

修改阶段契约时，同时更新组件、相关 references 与校验器，并运行完整测试。不要仅修改计数或放宽门禁来让测试通过。

当前尚未指定开源许可证；上传到 GitHub 不会自动授予他人使用、修改或分发的权利。发布者需确认原始内容权属并自行选择许可证。
