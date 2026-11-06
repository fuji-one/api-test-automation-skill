# 数据库 MCP 与数据模型归一化策略

## 目录

- [读取时机](#读取时机)
- [适用范围](#适用范围)
- [核心门禁](#核心门禁)
- [规则正文](#规则正文)
- [`database_mcp_evidence_index.yaml`](#database_mcp_evidence_indexyaml)
- [`source_db_alignment.yaml`](#source_db_alignmentyaml)
- [来源](#来源)

## 读取时机

源码入口缺少数据模型且目标为 executable/framework 时读取；运行时 DB before/after、清理、数据模型归一化时也读取。

## 适用范围

重点关注 `database_mcp_evidence_index.yaml`、`source_db_alignment.yaml`、`数据模型.md` 的执行级可用性。数据库 MCP 只能作为上游证据源；脚本阶段不得保留 MCP 调用。

## 核心门禁

- 未提供数据模型的源码入口不能直接阻塞，必须先检查可用数据库 MCP。
- MCP 归一化后的数据模型必须通过源码-数据库一致性门禁。
- 字段清单不等于执行级数据模型；必须有表关系、归属键、setup 顺序、cleanup 逆序和清理边界。

## 规则正文

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

`数据模型.md` is execution-ready only when it contains both table structure and a lightweight table knowledge graph for setup/cleanup: table names, columns, primary/unique keys, required/default fields, status enums, logical-delete fields, ownership keys, parent-child relationships, setup order, cleanup reverse order, and cleanup boundaries. When the database has no declared foreign keys, infer candidate edges only from source-visible DB side effects, field names, indexes, comments, and repository joins, and label them as inferred. If the graph, ownership key, or cleanup order cannot be determined for a table used by executable setup/cleanup, block before `$executable-interface-case-set`; do not pass a field-list-only data model downstream. A section title or keyword alone is not enough: content such as `缺失`、`待补充`、`待确认`、`未知`、`不详`、`暂无`、`TBD`、`UNKNOWN` must be treated as missing execution evidence.

For source-entry runs targeting `executable` or `framework`, a missing user-provided `数据模型.md` is not an immediate blocker. After `$source-api-fact-extractor` completes, first check whether an available database MCP can read the target database identity and metadata; only when database MCP is unavailable, unreadable, identity cannot be matched, schema/relationship/setup/cleanup evidence cannot be generated, or source-DB alignment fails may the run stop before executable filling. Database MCP should read metadata first: database, schema, table, column, index, constraint, comment, and relationship evidence; row data may be read only when the user explicitly authorizes runtime evidence or DB before/after probing. The database MCP connection is evidence, not a downstream dependency: it must produce `00-inputs/数据模型.md`, `00-inputs/database_mcp_evidence_index.yaml`, `00-inputs/source_db_alignment.yaml`, and `00-inputs/source_db_alignment_report.md`; downstream stages consume only the normalized files. If no available MCP can be used, record the attempted connector/tool/environment and blocker reason in `00-inputs/source_db_alignment_report.md` or `00_流水线执行报告.md`. If source DB facts and MCP schema conflict, stop before executable filling with `FAILED_EXECUTION_READINESS`; if MCP access or evidence is missing after the required check, stop with `BLOCKED_NEED_EXECUTION_INPUT`.

## 来源

本文件从 `SKILL.md` 原主契约拆分而来；完整历史契约保存在 `references/full-contract.md`。
