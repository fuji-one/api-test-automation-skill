# Apifox MCP 证据边界

## 读取时机

执行级用例使用 Apifox MCP 证据、用户要求 Apifox 对齐、或 `execution_fact_sources.yaml` 引用 `apifox_mcp` 时读取。

## 边界声明

Apifox MCP 是辅助证据源，不是运行时 requester。它可以帮助定位项目结构、校验接口契约、读取保存用例或响应示例，但不能代表真实运行时响应，不能覆盖结构化契约，也不能成为 pytest 运行依赖。

`apifox_evidence_index.yaml` 的详细 schema 见 `references/sidecar-contracts.md`。

## 规则正文

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


## 来源

本文件从 `SKILL.md` 原主契约拆分而来；完整历史契约保存在 `references/full-contract.md`。
