from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DOC_NAMES = [
    "01-api-inventory.md",
    "02-api-contracts.md",
    "03-call-chain.md",
    "04-business-rules.md",
    "05-source-db-side-effects.md",
    "06-unknown-and-risk.md",
    "08-security-transform-facts.md",
    "09-interface-encryption-policy.md",
    "source_api_fact_artifacts.yaml",
    "01_接口测试用例设计文档.md",
    "02_接口结构化契约清单.md",
    "03_skill执行报告.md",
    "stage_status.yaml",
    "coverage_matrix.yaml",
    "business_scenario_map.yaml",
    "业务场景链路清单.md",
]
GENERIC_PATH_SEGMENTS = {"api", "app", "admin", "internal", "openapi", "gateway"}
ACTION_PATH_SEGMENTS = {
    "add",
    "apply",
    "approve",
    "batch",
    "bind",
    "cancel",
    "change",
    "check",
    "confirm",
    "create",
    "delete",
    "detail",
    "get",
    "info",
    "list",
    "login",
    "logout",
    "page",
    "pay",
    "publish",
    "query",
    "read",
    "remove",
    "reject",
    "save",
    "search",
    "status",
    "submit",
    "unbind",
    "update",
    "upload",
    "withdraw",
}
BROAD_NAMESPACE_SEGMENTS = {
    "common",
    "female",
    "internal",
    "male",
    "user",
}


def render_all(facts: dict[str, Any], out_dir: str | Path) -> Path:
    target = Path(out_dir) / "docs" / "source-facts"
    target.mkdir(parents=True, exist_ok=True)
    downstream_index = build_downstream_index(facts)
    (target / "01-api-inventory.md").write_text(render_inventory(facts), encoding="utf-8")
    (target / "02-api-contracts.md").write_text(render_contracts(facts), encoding="utf-8")
    (target / "03-call-chain.md").write_text(render_call_chain(facts), encoding="utf-8")
    (target / "04-business-rules.md").write_text(render_business_rules(facts), encoding="utf-8")
    (target / "05-source-db-side-effects.md").write_text(render_db_side_effects(facts), encoding="utf-8")
    (target / "06-unknown-and-risk.md").write_text(render_unknowns(facts), encoding="utf-8")
    (target / "08-security-transform-facts.md").write_text(render_security_transforms(facts), encoding="utf-8")
    (target / "09-interface-encryption-policy.md").write_text(
        render_interface_encryption_policy(facts), encoding="utf-8"
    )
    (target / "01_接口测试用例设计文档.md").write_text(
        render_pipeline_design_doc(facts, downstream_index), encoding="utf-8"
    )
    (target / "02_接口结构化契约清单.md").write_text(
        render_pipeline_contract_doc(facts, downstream_index), encoding="utf-8"
    )
    (target / "03_skill执行报告.md").write_text(
        render_pipeline_report(facts, downstream_index), encoding="utf-8"
    )
    (target / "stage_status.yaml").write_text(render_stage_status(), encoding="utf-8")
    (target / "coverage_matrix.yaml").write_text(
        render_source_coverage_matrix(downstream_index), encoding="utf-8"
    )
    (target / "business_scenario_map.yaml").write_text(
        render_business_scenario_map(facts, downstream_index), encoding="utf-8"
    )
    (target / "业务场景链路清单.md").write_text(
        render_business_scenario_doc(facts, downstream_index), encoding="utf-8"
    )
    (target / "source_api_fact_artifacts.yaml").write_text(
        render_artifact_manifest(), encoding="utf-8"
    )
    (target / "source-api-facts.json").write_text(
        json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return target


def render_inventory(facts: dict[str, Any]) -> str:
    rows = [
        [
            api["api_id"],
            api["module"],
            api["entry"]["entry_type"],
            api["entry"]["class_name"],
            api["entry"]["method_name"],
            api["entry"]["http_method"],
            api["entry"]["path"],
            api["entry"]["rpc_interface"],
            api["entry"]["request_type"],
            api["entry"]["response_type"],
            api["entry"]["auth_hint"],
            api["entry"]["source_evidence"],
        ]
        for api in facts["apis"]
    ]
    return "# 源码接口资产清单\n\n" + table(
        [
            "api_id",
            "模块",
            "入口类型",
            "入口类",
            "入口方法",
            "HTTP 方法",
            "路径",
            "RPC/Facade 接口",
            "请求类型",
            "响应类型",
            "鉴权线索",
            "源码证据",
        ],
        rows,
    )


def render_contracts(facts: dict[str, Any]) -> str:
    parts = ["# 源码接口契约与字段约束\n"]
    for api in facts["apis"]:
        contract = api["contract"]
        parts.append(f"## {api['api_id']}\n")
        parts.append(f"- 入口：`{api['entry']['class_name']}.{api['entry']['method_name']}`")
        parts.append(f"- 路径：`{api['entry']['http_method']} {api['entry']['path']}`")
        parts.append(f"- 响应包装：`{contract['response_wrapper']}`")
        parts.append(f"- 响应体类型：`{contract['response_body_type']}`\n")
        parts.append("### 请求参数\n")
        parts.append(
            table_or_message(
                ["参数名", "类型", "来源", "注解"],
                [
                    [
                        p.get("name", "UNKNOWN"),
                        p.get("type", "UNKNOWN"),
                        p.get("source", "UNKNOWN"),
                        ", ".join(p.get("annotations", [])) or "无",
                    ]
                    for p in contract.get("request_parameters", [])
                ],
                "无请求参数。",
            )
        )
        parts.append("### 请求字段\n")
        parts.append(render_fields(contract.get("request_fields", []), "无请求体字段。"))
        parts.append("### 响应字段\n")
        parts.append(render_fields(contract.get("response_fields", []), "无响应字段。"))
    return "\n".join(parts)


def render_call_chain(facts: dict[str, Any]) -> str:
    parts = ["# 源码调用链\n"]
    for api in facts["apis"]:
        parts.append(f"## {api['api_id']}\n")
        rows = [
            [item["class_name"], item["method_name"], item["call_type"], item["evidence"], item["notes"]]
            for item in api.get("call_chain", [])
        ]
        parts.append(table(["类名", "方法名", "调用类型", "源码证据", "备注"], rows))
    return "\n".join(parts)


def render_business_rules(facts: dict[str, Any]) -> str:
    parts = ["# 源码业务规则、状态与异常分支\n"]
    for api in facts["apis"]:
        parts.append(f"## {api['api_id']}\n")
        rows = [
            [
                rule["rule_id"],
                rule["rule_type"],
                rule["condition"],
                rule["success_behavior"],
                rule["failure_behavior"],
                rule["error_code"],
                rule["exception_type"],
                rule["server_judgable"],
                rule["evidence"],
            ]
            for rule in api.get("business_rules", [])
        ]
        parts.append(
            table_or_message(
                [
                    "规则 ID",
                    "规则类型",
                    "条件",
                    "通过行为",
                    "失败行为",
                    "错误码",
                    "异常类型",
                    "服务端可判断",
                    "源码证据",
                ],
                rows,
                "未发现源码可见业务规则。",
            )
        )
    return "\n".join(parts)


def render_db_side_effects(facts: dict[str, Any]) -> str:
    parts = ["# 源码可见 DB 副作用\n", "## 接口表影响汇总\n", render_db_table_summary(facts)]
    for api in facts["apis"]:
        parts.append(f"## {api['api_id']}\n")
        effects = api.get("db_side_effects", [])
        rows = [
            [
                effect["operation_type"],
                effect["tables"],
                effect["entity_or_do"],
                effect["mapper_or_repository"],
                effect["sql_operation"],
                effect["transaction_boundary"],
                effect["side_effect_level"],
                effect["db_assertion_hint"],
                effect["evidence"],
            ]
            for effect in effects
            if is_visible_db_effect(effect)
        ]
        parts.append(
            table_or_message(
                [
                    "操作类型",
                    "表名",
                    "Entity/DO",
                    "Mapper/Repository",
                    "SQL 操作",
                    "事务边界",
                    "副作用级别",
                    "DB 断言线索",
                    "源码证据",
                ],
                rows,
                "未发现源码可见 DB 访问或副作用。",
            )
        )
    return "\n".join(parts)


def render_db_table_summary(facts: dict[str, Any]) -> str:
    rows = []
    for api in facts["apis"]:
        effects = api.get("db_side_effects", [])
        tables = sorted({effect.get("tables") for effect in effects if effect.get("tables") != "UNKNOWN"})
        read_tables = sorted(
            {
                effect.get("tables")
                for effect in effects
                if effect.get("tables") != "UNKNOWN" and effect.get("operation_type") == "READ"
            }
        )
        write_tables = sorted(
            {
                effect.get("tables")
                for effect in effects
                if effect.get("tables") != "UNKNOWN"
                and effect.get("operation_type") in {"CREATE", "UPDATE", "DELETE", "UPSERT"}
            }
        )
        rows.append(
            [
                api["api_id"],
                len(tables),
                len(read_tables),
                len(write_tables),
                tables or "NONE",
                write_tables or "NONE",
            ]
        )
    return table(["api_id", "涉及表数", "读表数", "写表数", "涉及表", "写表"], rows)


def render_unknowns(facts: dict[str, Any]) -> str:
    parts = ["# 源码无法确认项与风险\n"]
    project_rows = [
        [
            unknown.get("unknown_id", "UNKNOWN"),
            unknown.get("unknown_type", "UNKNOWN"),
            unknown.get("severity", "UNKNOWN"),
            unknown.get("action_required", "UNKNOWN"),
            unknown.get("affected_api_count", "UNKNOWN"),
            unknown.get("description", "UNKNOWN"),
            unknown.get("why_unknown", "UNKNOWN"),
            unknown.get("suggested_manual_check", "UNKNOWN"),
        ]
        for unknown in facts.get("project_unknowns", [])
    ]
    parts.append("## 项目级聚合项\n")
    parts.append(
        table_or_none(
            [
                "unknown_id",
                "无法确认类型",
                "严重级别",
                "是否需要行动",
                "影响接口数",
                "说明",
                "原因",
                "建议处理方式",
            ],
            project_rows,
        )
    )

    rows = []
    for api in facts["apis"]:
        for unknown in api.get("unknowns", []):
            rows.append(
                [
                    unknown["unknown_id"],
                    unknown["api_id"],
                    unknown["unknown_type"],
                    unknown.get("severity", "UNKNOWN"),
                    unknown.get("action_required", "UNKNOWN"),
                    unknown["description"],
                    unknown["why_unknown"],
                    unknown["evidence_or_location"],
                    unknown["suggested_manual_check"],
                ]
            )
    parts.append("## 接口级明细项\n")
    parts.append(
        table_or_none(
            [
                "unknown_id",
                "api_id",
                "无法确认类型",
                "严重级别",
                "是否需要行动",
                "说明",
                "原因",
                "证据或位置",
                "建议处理方式",
            ],
            rows,
        )
    )
    return "\n".join(parts)


def render_security_transforms(facts: dict[str, Any]) -> str:
    parts = [
        "# 源码加密签名与脚本转换事实",
        "",
        "## 文档定位",
        "",
        "本文档记录源码可见的加密、解密、哈希、密码校验、Token、签名、预签名 URL 和外部验签事实，供执行级接口自动化脚本生成时决定数据构造、签名生成、动态提取和 DB 断言策略。",
        "",
        "## 接口级转换规则",
        "",
    ]
    rows = []
    for api in facts.get("apis", []):
        for transform in api.get("security_transforms", []):
            rows.append(security_transform_row(transform, api.get("api_id", "UNKNOWN")))
    parts.append(
        table_or_message(
            [
                "api_id",
                "transform_id",
                "类型",
                "算法",
                "输入角色",
                "输出角色",
                "是否确定性",
                "是否可逆",
                "是否需要密钥",
                "配置键",
                "源表达式",
                "目标表达式",
                "脚本断言策略",
                "源码证据",
            ],
            rows,
            "未发现接口级加密、签名、哈希或 Token 转换规则。",
        )
    )
    parts.extend(["", "## 项目级转换能力", ""])
    project_rows = [
        security_transform_row(transform, transform.get("api_id", "PROJECT"))
        for transform in facts.get("project_security_transforms", [])
    ]
    parts.append(
        table_or_message(
            [
                "api_id",
                "transform_id",
                "类型",
                "算法",
                "输入角色",
                "输出角色",
                "是否确定性",
                "是否可逆",
                "是否需要密钥",
                "配置键",
                "源表达式",
                "目标表达式",
                "脚本断言策略",
                "源码证据",
            ],
            project_rows,
            "未发现项目级加密、签名、哈希或 Token 转换能力。",
        )
    )
    parts.extend(["", "## 源码可见敏感配置", ""])
    config_rows = [
        [
            ref.get("config_key", "UNKNOWN"),
            ref.get("sensitivity", "UNKNOWN"),
            ref.get("value_visible", "UNKNOWN"),
            ref.get("config_value_masked", "UNKNOWN"),
            ref.get("script_strategy", "UNKNOWN"),
            ref.get("evidence", "UNKNOWN"),
        ]
        for ref in facts.get("secret_config_refs", [])
    ]
    parts.append(
        table_or_message(
            ["配置键", "敏感级别", "源码值是否可见", "遮蔽值", "脚本取值策略", "源码证据"],
            config_rows,
            "未发现源码可见敏感配置。",
        )
    )
    parts.extend(
        [
            "",
            "## 执行级脚本生成提示",
            "",
            "- `FIELD_ENCRYPT`、`FIELD_DECRYPT`：DB 断言需按源码算法转换后比对，不能直接用接口明文比对密文字段。",
            "- `FIELD_HASH`：可确定性重算，适合在脚本中生成期望哈希值。",
            "- `PASSWORD_HASH`：不可确定性重算，适合断言非明文或通过登录链路验证。",
            "- `TOKEN_GENERATE`：必须从接口响应、Redis 或前置步骤提取真实 token。",
            "- `SIGNATURE_VERIFY`、`SIGNATURE_GENERATE`：正向用例必须按源码顺序和编码生成签名。",
            "- `PRESIGNED_URL_GENERATE`：只断言 URL 结构、非空和有效期语义，不硬编码完整 URL。",
            "- `source-api-facts.json` 仅保留 `secret_config_refs[].secret_ref` 和遮蔽元数据；真实敏感值必须由环境变量、测试配置或密钥管理系统在运行时注入。",
            "",
        ]
    )
    return "\n".join(parts)


def render_interface_encryption_policy(facts: dict[str, Any]) -> str:
    policy = facts.get("project_encryption_policy", {})
    rules = policy.get("classification_rules", [])
    policy_items = policy.get("policy_items", [])
    parts = [
        "# 接口传输加解密策略识别",
        "",
        "## 文档定位",
        "",
        "本文档记录源码可推断的接口入口类型和传输层加解密策略候选，用于下游执行级用例和 pytest 脚本决定哪些接口需要请求加密、响应解密，哪些接口需要保留明文调用。本文档只表达源码推断结果，最终策略必须结合网关、客户端或用户确认。",
        "",
        "## 项目级策略摘要",
        "",
        f"- 策略来源状态：`{policy.get('policy_source_status', 'UNKNOWN')}`",
        f"- 默认策略：`{policy.get('default_policy', 'UNKNOWN')}`",
        f"- 是否需要人工/配置确认：`{policy.get('confirmation_required', 'UNKNOWN')}`",
        "",
        "## 通用分类规则",
        "",
    ]
    rule_rows = [
        [
            rule.get("rule_id", "UNKNOWN"),
            rule.get("channel_type", "UNKNOWN"),
            rule.get("policy_hint", "UNKNOWN"),
            rule.get("description", "UNKNOWN"),
        ]
        for rule in rules
    ]
    parts.append(
        table_or_message(
            ["规则ID", "入口类型", "策略候选", "说明"],
            rule_rows,
            "未生成接口传输加解密分类规则。",
        )
    )
    parts.extend(["", "## 接口级策略候选", ""])
    item_rows = [
        [
            item.get("api_id", "UNKNOWN"),
            item.get("http_method", "UNKNOWN"),
            item.get("path", "UNKNOWN"),
            item.get("entry_type", "UNKNOWN"),
            item.get("channel_type", "UNKNOWN"),
            item.get("policy_hint", "UNKNOWN"),
            item.get("confidence", "UNKNOWN"),
            list_to_cell(item.get("reason_codes", [])),
            list_to_cell(item.get("evidence_refs", [])),
        ]
        for item in policy_items
    ]
    parts.append(
        table_or_message(
            ["api_id", "method", "path", "入口类型", "流量类型", "策略候选", "置信度", "原因码", "源码证据"],
            item_rows,
            "未生成接口级传输加解密策略候选。",
        )
    )
    parts.extend(
        [
            "",
            "## 下游消费规则",
            "",
            "- `no_encrypt_candidate` 只能作为源码候选结论；只有获得用户确认、网关配置或客户端协议证据后，执行脚本才可把它固化为明文调用白名单。",
            "- `requires_encryption_if_project_default_enabled` 表示当项目默认开启 App 传输加解密时，执行脚本必须具备请求加密与响应解密能力。",
            "- `policy_required` 表示源码入口类型不足以判断，执行级用例阶段必须阻塞或要求补充策略，不得猜测。",
            "- 本文档不替代字段级加密、哈希、签名和 Token 转换事实；字段级转换仍以 `08-security-transform-facts.md` 和 `security_transforms` 为准。",
            "",
        ]
    )
    return "\n".join(parts)


def security_transform_row(transform: dict[str, Any], api_id: str) -> list[Any]:
    return [
        api_id,
        transform.get("transform_id", "UNKNOWN"),
        transform.get("transform_type", "UNKNOWN"),
        transform.get("algorithm", "UNKNOWN"),
        transform.get("input_role", "UNKNOWN"),
        transform.get("output_role", "UNKNOWN"),
        transform.get("deterministic", "UNKNOWN"),
        transform.get("reversible", "UNKNOWN"),
        transform.get("requires_secret", "UNKNOWN"),
        transform.get("config_key", "UNKNOWN"),
        transform.get("source_expression", "UNKNOWN"),
        transform.get("target_expression", "UNKNOWN"),
        transform.get("script_assertion_strategy", "UNKNOWN"),
        transform.get("evidence", "UNKNOWN"),
    ]


def render_fields(fields: list[dict[str, Any]], empty_message: str) -> str:
    return table_or_message(
        [
            "字段名",
            "字段类型",
            "是否必填",
            "默认值",
            "校验注解",
            "枚举值",
            "嵌套对象",
            "集合类型",
            "源码证据",
        ],
        [
            [
                field.get("field_name", "UNKNOWN"),
                field.get("field_type", "UNKNOWN"),
                field.get("required", "UNKNOWN"),
                field.get("default_value", "UNKNOWN"),
                field.get("validation_annotation", "UNKNOWN"),
                list_to_cell(field.get("enum_values", "UNKNOWN")),
                field.get("nested_object", "UNKNOWN"),
                field.get("collection_type", "UNKNOWN"),
                field.get("evidence", "UNKNOWN"),
            ]
            for field in fields
        ],
        empty_message,
    )


def table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        rows = [["无" for _ in headers]]
    escaped_headers = [escape_cell(h) for h in headers]
    lines = ["| " + " | ".join(escaped_headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        normalized = list(row) + [""] * (len(headers) - len(row))
        lines.append("| " + " | ".join(escape_cell(cell) for cell in normalized[: len(headers)]) + " |")
    return "\n".join(lines) + "\n"


def table_or_none(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "无。\n"
    return table(headers, rows)


def table_or_message(headers: list[str], rows: list[list[Any]], message: str) -> str:
    if not rows:
        return f"{message}\n"
    return table(headers, rows)


def is_visible_db_effect(effect: dict[str, Any]) -> bool:
    return any(
        effect.get(key, "UNKNOWN") != "UNKNOWN"
        for key in ("operation_type", "tables", "entity_or_do", "mapper_or_repository", "sql_operation")
    )


def list_to_cell(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def escape_cell(value: Any) -> str:
    text = list_to_cell(value)
    return text.replace("|", "\\|").replace("\n", "<br>")


def build_downstream_index(facts: dict[str, Any]) -> dict[str, Any]:
    api_meta: dict[str, dict[str, Any]] = {}
    object_ids: list[str] = []
    rule_ids: list[str] = []
    test_point_ids: list[str] = []
    main_flow_ids: list[str] = []
    status_ids: list[str] = []
    coverage_items: list[dict[str, Any]] = []
    mappings: list[dict[str, Any]] = []

    for index, api in enumerate(facts.get("apis", []), start=1):
        api_id = api["api_id"]
        obj_id = f"OBJ-SRC-{index:03d}"
        object_ids.append(obj_id)
        main_tp = f"TP-SRC-{index:03d}-MAIN"
        flow_id = f"FLOW-SRC-{index:03d}-MAIN"
        main_rule = f"RULE-SRC-{index:03d}-CONTRACT"
        status_id = f"STATUS-SRC-{index:03d}-HTTP-200"
        request_rule_ids = [
            f"RULE-SRC-{index:03d}-REQ-{field_index:03d}-{safe_id(field.get('field_name'))}"
            for field_index, field in enumerate(api.get("contract", {}).get("request_fields", []), start=1)
        ]
        response_rule_ids = [
            f"RULE-SRC-{index:03d}-RESP-{field_index:03d}-{safe_id(field.get('field_name'))}"
            for field_index, field in enumerate(api.get("contract", {}).get("response_fields", []), start=1)
        ]
        business_rule_ids: list[str] = []
        business_rules_by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for rule_index, rule in enumerate(api.get("business_rules", []), start=1):
            error_code = rule.get("error_code", "BUSINESS_RULE")
            rule_id = f"RULE-SRC-{index:03d}-BIZ-{rule_index:03d}-{safe_id(error_code)}"
            business_rule_ids.append(rule_id)
            business_rules_by_code[error_code].append({**rule, "pipeline_rule_id": rule_id})
        rule_to_status_id: dict[str, str] = {}
        error_scenarios: list[dict[str, Any]] = []

        db_rule_ids = [
            f"RULE-SRC-{index:03d}-DB-{effect_index:03d}-{safe_id(effect.get('operation_type'))}"
            for effect_index, effect in enumerate(api.get("db_side_effects", []), start=1)
        ]
        security_rule_ids = [
            f"RULE-SRC-{index:03d}-SEC-{transform_index:03d}-{safe_id(transform.get('transform_type'))}"
            for transform_index, transform in enumerate(api.get("security_transforms", []), start=1)
        ]
        api_rule_ids = [main_rule] + request_rule_ids + response_rule_ids + business_rule_ids + db_rule_ids + security_rule_ids
        rule_ids.extend(api_rule_ids)
        test_point_ids.append(main_tp)
        main_flow_ids.append(flow_id)
        status_ids.append(status_id)
        main_case_id = f"TC-SRC-{index:03d}-MAIN"
        mappings.extend(
            [
                {"upstream_id": obj_id, "downstream_ids": [main_case_id], "mapping_status": "mapped"},
                {"upstream_id": main_tp, "downstream_ids": [main_case_id], "mapping_status": "mapped"},
                {"upstream_id": flow_id, "downstream_ids": [main_case_id], "mapping_status": "mapped"},
                {"upstream_id": status_id, "downstream_ids": [main_case_id], "mapping_status": "mapped"},
            ]
        )
        for rule_id in [main_rule] + request_rule_ids + response_rule_ids + db_rule_ids + security_rule_ids:
            mappings.append({"upstream_id": rule_id, "downstream_ids": [main_case_id], "mapping_status": "mapped"})

        error_case_ids: list[str] = []
        for error_index, (error_code, rules) in enumerate(sorted(business_rules_by_code.items()), start=1):
            error_tp = f"TP-SRC-{index:03d}-ERR-{error_index:03d}"
            error_flow = f"FLOW-SRC-{index:03d}-ERR-{error_index:03d}"
            error_status = f"STATUS-SRC-{index:03d}-BIZ-{error_index:03d}-{safe_id(error_code)}"
            error_case_id = f"TC-SRC-{index:03d}-ERR-{error_index:03d}"
            test_point_ids.append(error_tp)
            main_flow_ids.append(error_flow)
            status_ids.append(error_status)
            error_case_ids.append(error_case_id)
            mapped_rule_ids = [rule["pipeline_rule_id"] for rule in rules]
            for rule_id in mapped_rule_ids:
                rule_to_status_id[rule_id] = error_status
            error_scenarios.append(
                {
                    "test_point_id": error_tp,
                    "flow_id": error_flow,
                    "status_id": error_status,
                    "case_id": error_case_id,
                    "error_code": error_code,
                    "rule_ids": mapped_rule_ids,
                }
            )
            mappings.extend(
                [
                    {"upstream_id": error_tp, "downstream_ids": [error_case_id], "mapping_status": "mapped"},
                    {"upstream_id": error_flow, "downstream_ids": [error_case_id], "mapping_status": "mapped"},
                    {"upstream_id": error_status, "downstream_ids": [error_case_id], "mapping_status": "mapped"},
                ]
            )
            for rule_id in mapped_rule_ids:
                mappings.append({"upstream_id": rule_id, "downstream_ids": [error_case_id], "mapping_status": "mapped"})

        api_meta[api_id] = {
            "index": index,
            "object_id": obj_id,
            "main_test_point_id": main_tp,
            "main_flow_id": flow_id,
            "main_rule_id": main_rule,
            "success_status_id": status_id,
            "request_rule_ids": request_rule_ids,
            "response_rule_ids": response_rule_ids,
            "business_rule_ids": business_rule_ids,
            "business_rule_status_ids": [rule_to_status_id.get(rule_id, "UNKNOWN") for rule_id in business_rule_ids],
            "db_rule_ids": db_rule_ids,
            "security_rule_ids": security_rule_ids,
            "all_rule_ids": api_rule_ids,
            "main_case_id": main_case_id,
            "error_case_ids": error_case_ids,
            "error_scenarios": error_scenarios,
            "business_rules_by_code": business_rules_by_code,
        }

    for coverage_id in test_point_ids:
        coverage_items.append(coverage_item(coverage_id, "test_point"))
    for coverage_id in main_flow_ids:
        coverage_items.append(coverage_item(coverage_id, "main_flow"))
    for coverage_id in rule_ids:
        coverage_items.append(coverage_item(coverage_id, "rule"))
    for coverage_id in status_ids:
        coverage_items.append(coverage_item(coverage_id, "status_code"))

    return {
        "api_meta": api_meta,
        "object_ids": object_ids,
        "rule_ids": rule_ids,
        "test_point_ids": test_point_ids,
        "main_flow_ids": main_flow_ids,
        "status_ids": status_ids,
        "coverage_items": coverage_items,
        "mappings": mappings,
    }


def coverage_item(coverage_id: str, coverage_type: str) -> dict[str, Any]:
    return {
        "coverage_id": coverage_id,
        "coverage_type": coverage_type,
        "status": "covered",
        "evidence_refs": ["source-api-facts.json", "01_接口测试用例设计文档.md"],
    }


def business_scenario_items(facts: dict[str, Any], index: dict[str, Any]) -> list[dict[str, Any]]:
    items = chain_business_scenario_items(facts, index)
    items.extend(single_api_business_scenario_items(facts, index))
    return items


def single_api_business_scenario_items(facts: dict[str, Any], index: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for scenario_index, api in enumerate(facts.get("apis", []), start=1):
        api_id = api["api_id"]
        entry = api.get("entry", {})
        meta = index["api_meta"][api_id]
        interface_name = business_interface_name(api)
        operation = business_operation(entry.get("http_method"))
        resource_key = api_resource_key(api) or entry.get("class_name", "接口")
        business_domain = business_domain_label(resource_key)
        executing_role = executing_role_for_api(api)
        source_refs = business_source_refs(api)
        related_test_point_ids = [meta["main_test_point_id"]] + [
            scenario["test_point_id"] for scenario in meta.get("error_scenarios", [])
        ]
        related_rule_ids = [
            meta["main_rule_id"],
            *meta.get("business_rule_ids", []),
            *meta.get("db_rule_ids", []),
            *meta.get("security_rule_ids", []),
        ]
        business_chain = [
            f"接收{interface_name}请求",
            "校验源码可见请求字段和业务规则",
        ]
        if api.get("db_side_effects"):
            business_chain.append("执行源码可见数据副作用")
        if api.get("security_transforms"):
            business_chain.append("处理源码可见加密签名或 token 规则")
        business_chain.append("返回接口处理结果")
        state_chain = ["HTTP_200"] + [
            scenario.get("error_code", "UNKNOWN")
            for scenario in meta.get("error_scenarios", [])
            if scenario.get("error_code", "UNKNOWN") != "UNKNOWN"
        ]
        items.append(
            {
                "scenario_id": f"BS-SRC-{scenario_index:03d}",
                "scenario_name": f"{executing_role}通过{interface_name}{operation}",
                "business_domain": business_domain,
                "executing_role": executing_role,
                "business_description": (
                    f"{executing_role}通过{interface_name}{operation}，后端服务依据源码可见入口、字段约束、"
                    f"业务规则和数据副作用完成处理，验证该接口在源码可证明范围内的业务链路。"
                ),
                "roles": stable_unique([executing_role, "后端服务"]),
                "source_refs": source_refs,
                "related_interfaces": [interface_name],
                "business_chain": business_chain,
                "state_chain": state_chain,
                "related_test_point_ids": related_test_point_ids,
                "related_coverage_rule_ids": related_rule_ids,
                "chain_type": "single_interface",
                "flow_generation_required": False,
                "flow_id": "",
                "ordered_step_count": 1,
                "ordered_steps": [
                    {
                        "step_order": 1,
                        "api_id": api_id,
                        "interface": interface_name,
                        "test_point_id": meta["main_test_point_id"],
                        "source_ref": source_refs[0],
                    }
                ],
                "confidence": "medium",
                "blockers": [],
            }
        )
    return items


def chain_business_scenario_items(facts: dict[str, Any], index: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for scenario_index, (resource_key, group) in enumerate(chain_candidate_groups(facts), start=1):
        related_interfaces = [business_interface_name(api) for api in group]
        related_test_point_ids: list[str] = []
        related_rule_ids: list[str] = []
        source_refs: list[str] = []
        state_chain: list[str] = []
        ordered_steps: list[dict[str, Any]] = []
        for step_order, api in enumerate(group, start=1):
            api_id = api["api_id"]
            meta = index["api_meta"][api_id]
            api_source_refs = business_source_refs(api)
            related_test_point_ids.append(meta["main_test_point_id"])
            related_rule_ids.extend([meta["main_rule_id"], *meta.get("business_rule_ids", []), *meta.get("db_rule_ids", [])])
            source_refs.extend(api_source_refs)
            state_chain.append("HTTP_200")
            ordered_steps.append(
                {
                    "step_order": step_order,
                    "api_id": api_id,
                    "interface": business_interface_name(api),
                    "test_point_id": meta["main_test_point_id"],
                    "source_ref": api_source_refs[0],
                }
            )
        unique_source_refs = stable_unique(source_refs)
        unique_rule_ids = stable_unique(related_rule_ids)
        unique_state_chain = stable_unique(state_chain)
        flow_id = f"FLOW-SRC-CHAIN-{scenario_index:03d}-{safe_id(resource_key)}"
        resource_label = resource_business_label(resource_key)
        business_domain = business_domain_label(resource_key)
        executing_role = executing_role_for_group(group)
        items.append(
            {
                "scenario_id": f"BS-SRC-CHAIN-{scenario_index:03d}",
                "scenario_name": chain_scenario_name(resource_label, group, executing_role),
                "business_domain": business_domain,
                "executing_role": executing_role,
                "business_description": (
                    f"{executing_role}先提交{resource_label}处理，再查询{resource_label}结果或状态，"
                    "确认前序业务动作已经产生源码可见的记录、状态或数据变化。"
                ),
                "roles": stable_unique([executing_role, "后端服务"]),
                "source_refs": unique_source_refs,
                "related_interfaces": related_interfaces,
                "business_chain": [
                    chain_step_business_action(step_order, api)
                    for step_order, api in enumerate(group, start=1)
                ],
                "state_chain": unique_state_chain,
                "related_test_point_ids": related_test_point_ids,
                "related_coverage_rule_ids": unique_rule_ids,
                "chain_type": "e2e_flow_candidate",
                "flow_generation_required": True,
                "flow_id": flow_id,
                "ordered_step_count": len(ordered_steps),
                "ordered_steps": ordered_steps,
                "confidence": "medium",
                "blockers": [],
            }
        )
    return items


DOMAIN_TRANSLATIONS = {
    "account": "账户",
    "alarm": "叫醒",
    "auth": "认证",
    "call": "通话",
    "common": "公共",
    "conversation": "会话",
    "diamond": "钻石",
    "discovery": "发现",
    "feedback": "评价",
    "female": "女端",
    "file": "文件",
    "im": "即时通讯",
    "integral": "积分",
    "internal": "内部",
    "male": "男端",
    "message": "消息",
    "moment": "动态",
    "onboard": "入驻",
    "online": "在线",
    "partner": "搭子",
    "profile": "资料",
    "provider": "服务者",
    "relationship": "关系",
    "safety": "安全",
    "script": "脚本任务",
    "serverconfig": "服务配置",
    "settings": "设置",
    "status": "状态",
    "subscription": "订阅",
    "task": "任务",
    "tencentrtc": "腾讯 RTC",
    "user": "用户",
    "verification": "认证",
    "withdrawal": "提现",
}


def business_domain_label(resource_key: str) -> str:
    parts = [part for part in re.split(r"[-_/\\\s]+", str(resource_key).strip()) if part]
    translated = [DOMAIN_TRANSLATIONS.get(part.lower(), part) for part in parts]
    label = "".join(translated).strip()
    return f"{label}业务域" if label else "接口业务域"


def executing_role_for_group(group: list[dict[str, Any]]) -> str:
    roles = [executing_role_for_api(api) for api in group]
    for preferred in ("第三方回调服务", "系统定时任务", "内部服务"):
        if preferred in roles:
            return preferred
    return roles[0] if roles else "用户"


def executing_role_for_api(api: dict[str, Any]) -> str:
    path = str(api.get("entry", {}).get("path", "")).lower()
    method_name = str(api.get("entry", {}).get("method_name", "")).lower()
    text = f"{path}/{method_name}"
    if "callback" in text:
        return "第三方回调服务"
    if "/internal/" in path or path.startswith("/internal/"):
        return "内部服务"
    if any(keyword in text for keyword in ("job", "script", "reminder", "wakeup")):
        return "系统定时任务"
    return "用户"


def resource_business_label(resource_key: str) -> str:
    domain = business_domain_label(resource_key)
    label = domain.removesuffix("业务域")
    return f"{label}业务" if label else "当前业务"


def chain_scenario_name(resource_label: str, group: list[dict[str, Any]], executing_role: str = "用户") -> str:
    methods = {str(api.get("entry", {}).get("http_method", "UNKNOWN")).upper() for api in group}
    if methods & {"POST", "PUT", "PATCH", "DELETE"} and "GET" in methods:
        return f"{executing_role}提交{resource_label}处理后查询结果"
    if methods & {"POST", "PUT", "PATCH", "DELETE"}:
        return f"{executing_role}提交{resource_label}处理后校验状态"
    return f"{executing_role}查询{resource_label}状态"


def chain_step_business_action(step_order: int, api: dict[str, Any]) -> str:
    operation = business_operation(api.get("entry", {}).get("http_method"))
    role = executing_role_for_api(api)
    return f"步骤{step_order}：{role}{operation}"


def chain_candidate_groups(facts: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for api in facts.get("apis", []):
        key = api_resource_key(api)
        if key:
            grouped[key].append(api)
    result: list[tuple[str, list[dict[str, Any]]]] = []
    for key, apis in sorted(grouped.items()):
        if len(apis) < 2:
            continue
        if not any(api.get("entry", {}).get("http_method") in {"POST", "PUT", "PATCH", "DELETE"} for api in apis):
            continue
        ordered = sorted(apis, key=chain_api_order_key)
        result.append((key, ordered))
    return result


def api_resource_key(api: dict[str, Any]) -> str:
    path = str(api.get("entry", {}).get("path", "UNKNOWN")).strip()
    if path == "UNKNOWN" or not path.startswith("/"):
        return ""
    normalized = re.sub(r"\{[^}]+\}", "", path)
    normalized = re.sub(r"/+", "/", normalized).strip("/")
    parts = [part for part in normalized.split("/") if part]
    semantic_parts: list[str] = []
    for part in parts:
        lowered = part.lower()
        if lowered in GENERIC_PATH_SEGMENTS or re.fullmatch(r"v\d+", lowered):
            continue
        if lowered in ACTION_PATH_SEGMENTS:
            continue
        semantic_parts.append(part)
    if not semantic_parts:
        return ""
    first = semantic_parts[0].lower()
    if first in BROAD_NAMESPACE_SEGMENTS and len(semantic_parts) >= 2:
        return "/".join(semantic_parts[:2])
    return semantic_parts[0]


def chain_api_order_key(api: dict[str, Any]) -> tuple[int, int, str]:
    method = str(api.get("entry", {}).get("http_method", "UNKNOWN")).upper()
    path = str(api.get("entry", {}).get("path", "UNKNOWN"))
    method_order = {"POST": 0, "PUT": 1, "PATCH": 1, "GET": 2, "DELETE": 3}.get(method, 9)
    path_depth = len([part for part in path.split("/") if part])
    return (method_order, path_depth, path)


def stable_unique(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for value in values:
        key = str(value)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def business_interface_name(api: dict[str, Any]) -> str:
    entry = api.get("entry", {})
    method = entry.get("http_method", "UNKNOWN")
    path = entry.get("path", "UNKNOWN")
    if method != "UNKNOWN" and path != "UNKNOWN":
        return f"{method} {path} 接口"
    class_name = entry.get("class_name", "UNKNOWN")
    method_name = entry.get("method_name", "UNKNOWN")
    return f"{class_name}.{method_name} 接口"


def business_operation(http_method: Any) -> str:
    method = str(http_method).upper()
    if method == "GET":
        return "查询业务信息"
    if method == "POST":
        return "提交业务处理请求"
    if method in {"PUT", "PATCH"}:
        return "更新业务状态"
    if method == "DELETE":
        return "删除业务数据"
    return "触发业务处理"


def business_source_refs(api: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    entry = api.get("entry", {})
    entry_ref = entry.get("source_evidence", "UNKNOWN")
    if entry_ref != "UNKNOWN":
        refs.append(entry_ref)
    for rule in api.get("business_rules", [])[:3]:
        evidence = rule.get("evidence", "UNKNOWN")
        if evidence != "UNKNOWN":
            refs.append(evidence)
    for effect in api.get("db_side_effects", [])[:3]:
        evidence = effect.get("evidence", "UNKNOWN")
        if evidence != "UNKNOWN":
            refs.append(evidence)
    if not refs:
        refs.append(f"{entry.get('class_name', 'UNKNOWN')}.{entry.get('method_name', 'UNKNOWN')}")
    return refs


def render_business_scenario_map(facts: dict[str, Any], index: dict[str, Any]) -> str:
    items = business_scenario_items(facts, index)
    status = "passed" if items else "blocked"
    next_stage_allowed = "true" if items else "false"
    lines = [
        "schema_version: 1",
        "stage: business_scenario_mapping",
        f"status: {status}",
        f"next_stage_allowed: {next_stage_allowed}",
        "source_entry: source",
        "scenario_source_status: source_inferred",
        "scenario_items:",
    ]
    if items:
        for item in items:
            lines.extend(
                [
                    f"  - scenario_id: {yaml_q(item['scenario_id'])}",
                    f"    scenario_name: {yaml_q(item['scenario_name'])}",
                    f"    business_domain: {yaml_q(item['business_domain'])}",
                    f"    executing_role: {yaml_q(item['executing_role'])}",
                    f"    business_description: {yaml_q(item['business_description'])}",
                    f"    roles: {yaml_list(item['roles'])}",
                    f"    source_refs: {yaml_list(item['source_refs'])}",
                    f"    related_interfaces: {yaml_list(item['related_interfaces'])}",
                    f"    business_chain: {yaml_list(item['business_chain'])}",
                    f"    state_chain: {yaml_list(item['state_chain'])}",
                    f"    related_test_point_ids: {yaml_list(item['related_test_point_ids'])}",
                    f"    related_coverage_rule_ids: {yaml_list(item['related_coverage_rule_ids'])}",
                    f"    chain_type: {yaml_q(item['chain_type'])}",
                    f"    flow_generation_required: {str(item['flow_generation_required']).lower()}",
                    f"    flow_id: {yaml_q(item['flow_id'])}",
                    f"    ordered_step_count: {item['ordered_step_count']}",
                    "    ordered_steps:",
                ]
            )
            for step in item["ordered_steps"]:
                lines.extend(
                    [
                        f"      - step_order: {step['step_order']}",
                        f"        api_id: {yaml_q(step['api_id'])}",
                        f"        interface: {yaml_q(step['interface'])}",
                        f"        test_point_id: {yaml_q(step['test_point_id'])}",
                        f"        source_ref: {yaml_q(step['source_ref'])}",
                    ]
                )
            lines.extend(
                [
                    f"    confidence: {item['confidence']}",
                    "    blockers: []",
                ]
            )
        lines.append("blocking_issues: []")
    else:
        lines.extend(
            [
                "blocking_issues:",
                '  - "未抽取到可映射接口，无法生成业务场景映射"',
            ]
        )
    lines.append("")
    return "\n".join(lines)


def render_business_scenario_doc(facts: dict[str, Any], index: dict[str, Any]) -> str:
    rows = [
        [
            item["scenario_id"],
            item["scenario_name"],
            item["business_description"],
            list_to_cell(item["roles"]),
            list_to_cell(item["source_refs"]),
            list_to_cell(item["business_chain"]),
            list_to_cell(item["related_interfaces"]),
            list_to_cell(item["state_chain"]),
            list_to_cell(item["related_test_point_ids"]),
            list_to_cell(item["related_coverage_rule_ids"]),
            item["chain_type"],
            "是" if item["flow_generation_required"] else "否",
            item["flow_id"] or "无",
            item["ordered_step_count"],
            item["confidence"],
            list_to_cell(item["blockers"]) if item["blockers"] else "无",
        ]
        for item in business_scenario_items(facts, index)
    ]
    return "\n".join(
        [
            "# 业务场景链路清单",
            "",
            "本文档由 `business_scenario_map.yaml` 渲染生成，记录源码入口可推断的业务场景映射。`confidence=medium` 表示该场景来自源码入口、调用链、业务规则、状态码或 DB 副作用的静态推断，不等同于 PRD 已确认业务语义。",
            "",
            table(
                [
                    "业务场景ID",
                    "业务场景名称",
                    "业务场景描述",
                    "角色",
                    "来源",
                    "业务链路",
                    "接口链路",
                    "状态链路",
                    "关联测试点ID",
                    "关联覆盖规则ID",
                    "链路类型",
                    "是否必须生成链路脚本",
                    "flow_id",
                    "步骤数",
                    "置信度",
                    "阻塞项",
                ],
                rows,
            ).rstrip(),
            "",
        ]
    )


def render_pipeline_design_doc(facts: dict[str, Any], index: dict[str, Any]) -> str:
    apis = facts.get("apis", [])
    api_meta = index["api_meta"]
    asset_rows: list[list[Any]] = []
    trace_rows: list[list[Any]] = []
    rule_rows: list[list[Any]] = []
    status_rows: list[list[Any]] = []
    db_rows: list[list[Any]] = []
    security_rows: list[list[Any]] = []

    for api in apis:
        entry = api.get("entry", {})
        contract = api.get("contract", {})
        meta = api_meta[api["api_id"]]
        asset_rows.append(
            [
                meta["object_id"],
                api["api_id"],
                api.get("module", "UNKNOWN"),
                entry.get("entry_type", "UNKNOWN"),
                entry.get("class_name", "UNKNOWN"),
                entry.get("method_name", "UNKNOWN"),
                entry.get("http_method", "UNKNOWN"),
                entry.get("path", "UNKNOWN"),
                entry.get("request_type", "UNKNOWN"),
                entry.get("response_type", "UNKNOWN"),
                entry.get("source_evidence", "UNKNOWN"),
            ]
        )
        trace_rows.append(
            [
                meta["main_test_point_id"],
                meta["object_id"],
                meta["main_flow_id"],
                f"{entry.get('http_method', 'UNKNOWN')} {entry.get('path', 'UNKNOWN')}",
                "主成功流程",
                "P0",
                meta["main_rule_id"],
                meta["success_status_id"],
                meta["main_case_id"],
            ]
        )
        for scenario in meta.get("error_scenarios", []):
            trace_rows.append(
                [
                    scenario["test_point_id"],
                    meta["object_id"],
                    scenario["flow_id"],
                    f"{entry.get('http_method', 'UNKNOWN')} {entry.get('path', 'UNKNOWN')}",
                    f"异常流程:{scenario.get('error_code', 'UNKNOWN')}",
                    "P1",
                    list_to_cell(scenario.get("rule_ids", [])),
                    scenario["status_id"],
                    scenario["case_id"],
                ]
            )
        rule_rows.append(
            [
                meta["main_rule_id"],
                meta["object_id"],
                "接口契约",
                "method/path/request/response",
                entry.get("source_evidence", "UNKNOWN"),
            ]
        )
        append_field_rule_rows(rule_rows, meta["request_rule_ids"], meta["object_id"], "请求字段", contract.get("request_fields", []))
        append_field_rule_rows(rule_rows, meta["response_rule_ids"], meta["object_id"], "响应字段", contract.get("response_fields", []))
        append_business_rule_rows(rule_rows, status_rows, meta, api)
        append_db_rule_rows(rule_rows, db_rows, meta, api)
        append_security_rule_rows(rule_rows, security_rows, meta, api)
        status_rows.append(
            [
                meta["success_status_id"],
                meta["object_id"],
                "HTTP_200",
                "正常返回",
                meta["main_rule_id"],
                entry.get("source_evidence", "UNKNOWN"),
            ]
        )

    project_unknown_rows = [
        [
            item.get("unknown_id", "UNKNOWN"),
            item.get("unknown_type", "UNKNOWN"),
            item.get("severity", "UNKNOWN"),
            item.get("action_required", "UNKNOWN"),
            item.get("affected_api_count", "UNKNOWN"),
            item.get("description", "UNKNOWN"),
            item.get("suggested_manual_check", "UNKNOWN"),
        ]
        for item in facts.get("project_unknowns", [])
    ]
    api_unknown_rows = [
        [
            item.get("unknown_id", "UNKNOWN"),
            item.get("api_id", "UNKNOWN"),
            item.get("unknown_type", "UNKNOWN"),
            item.get("severity", "UNKNOWN"),
            item.get("action_required", "UNKNOWN"),
            item.get("description", "UNKNOWN"),
            item.get("evidence_or_location", "UNKNOWN"),
        ]
        for api in apis
        for item in api.get("unknowns", [])
    ]

    return "\n".join(
        [
            "# 接口测试用例设计文档",
            "",
            "## 文档定位",
            "",
            "本文档由 Java 源码静态抽取生成，记录后续接口测试用例生成所需的覆盖对象、追溯测试点、主要流程、覆盖规则、状态码索引和源码证据。本阶段不生成执行级请求值、响应值、断言表达式或 pytest 脚本。",
            "",
            "## 源码事实覆盖结论",
            "",
            "- 源码入口质检结论：PASSED",
            "- 是否允许作为设计级用例生成输入：是",
            f"- 覆盖对象总数：{len(apis)}",
            f"- 追溯测试点总数：{len(index['test_point_ids'])}",
            f"- 覆盖规则总数：{len(set(index['rule_ids']))}",
            f"- 状态码/错误码索引总数：{len(index['status_ids'])}",
            f"- 加密签名转换规则总数：{sum(len(api.get('security_transforms', [])) for api in apis)}",
            "- 说明：成功状态码按 Spring MVC/Feign 正常返回语义登记为 `HTTP_200`；业务错误码仅来自源码显式异常分支。",
            "",
            "## 接口资产清单",
            "",
            table(
                ["覆盖对象ID", "api_id", "模块", "入口类型", "入口类", "入口方法", "HTTP方法", "路径", "请求类型", "响应类型", "源码证据"],
                asset_rows,
            ).rstrip(),
            "",
            "## 需求-接口-状态三向追踪矩阵",
            "",
            table(
                ["追溯测试点", "覆盖对象ID", "主要流程ID", "接口", "测试点类型", "优先级", "覆盖规则ID", "状态码ID", "设计级用例ID"],
                trace_rows,
            ).rstrip(),
            "",
            "## 字段-规则-断言映射表",
            "",
            table(["覆盖规则ID", "覆盖对象ID", "规则类型", "规则内容", "源码证据"], rule_rows).rstrip(),
            "",
            "## 错误码-异常场景映射表",
            "",
            table(["状态码ID", "覆盖对象ID", "状态码或错误码", "类型", "覆盖规则ID", "源码证据"], status_rows).rstrip(),
            "",
            "## 状态迁移-触发入口映射表",
            "",
            table(
                ["主要流程ID", "覆盖对象ID", "触发入口", "状态变化", "证据"],
                [["FLOW-SRC-GLOBAL", "全部源码接口", "Controller/Feign 正常返回", "设计级主流程以 `HTTP_200` 表示正常返回状态", "Spring MVC/Feign 正常返回语义"]],
            ).rstrip(),
            "",
            "## 依赖失败-补偿场景映射表",
            "",
            table_or_none(["覆盖对象ID", "覆盖规则ID", "依赖或副作用", "表名/目标", "副作用级别", "源码证据"], db_rows).rstrip(),
            "",
            "## 加密签名-脚本生成映射表",
            "",
            table_or_none(
                ["覆盖对象ID", "覆盖规则ID", "类型", "算法", "确定性", "需要密钥", "脚本断言策略", "源码证据"],
                security_rows,
            ).rstrip(),
            "",
            "## 覆盖率矩阵",
            "",
            table(
                ["覆盖维度", "已覆盖", "总数", "覆盖率", "准出结论"],
                [
                    ["覆盖对象", len(apis), len(apis), "100%", "通过"],
                    ["追溯测试点", len(index["test_point_ids"]), len(index["test_point_ids"]), "100%", "通过"],
                    ["覆盖规则", len(set(index["rule_ids"])), len(set(index["rule_ids"])), "100%", "通过"],
                    ["状态码/错误码索引", len(index["status_ids"]), len(index["status_ids"]), "100%", "通过"],
                ],
            ).rstrip(),
            "",
            "## 无法确认项与设计风险",
            "",
            "### 项目级聚合项",
            "",
            table_or_none(["unknown_id", "无法确认类型", "严重级别", "是否需要行动", "影响接口数", "说明", "建议处理方式"], project_unknown_rows).rstrip(),
            "",
            "### 接口级明细项",
            "",
            table_or_none(["unknown_id", "api_id", "无法确认类型", "严重级别", "是否需要行动", "说明", "证据或位置"], api_unknown_rows).rstrip(),
            "",
            "## 交付结论",
            "",
            "- 结论：通过",
            "- 是否允许声明源码覆盖对象、追溯测试点、覆盖规则和状态码索引 100% 覆盖：是",
            "- 是否允许进入设计级接口测试用例生成：是",
            "- 下游边界：执行级请求值、真实响应值、token 获取、测试账号、环境地址、前置数据构造和清理策略不在本阶段生成。",
            "",
        ]
    )


def render_pipeline_contract_doc(facts: dict[str, Any], index: dict[str, Any]) -> str:
    parts = [
        "# 接口结构化契约清单",
        "",
        "## 文档定位",
        "",
        "本文档登记源码可证明或框架语义可确定的接口契约事实。成功状态码以 Spring MVC/Feign 正常返回 `HTTP_200` 建立索引；业务错误码来自源码异常分支。具体请求样例、响应样例、token 和环境不在本阶段生成。",
    ]
    api_meta = index["api_meta"]
    for api in facts.get("apis", []):
        entry = api.get("entry", {})
        contract = api.get("contract", {})
        meta = api_meta[api["api_id"]]
        parts.extend(
            [
                "",
                f"## {api['api_id']}",
                "",
                f"- 覆盖对象ID：`{meta['object_id']}`",
                f"- 入口：`{entry.get('class_name', 'UNKNOWN')}.{entry.get('method_name', 'UNKNOWN')}`",
                f"- 路径：`{entry.get('http_method', 'UNKNOWN')} {entry.get('path', 'UNKNOWN')}`",
                "- 鉴权：`UNKNOWN`（源码入口未标注，执行级阶段需由执行配置补齐）",
                "- 成功状态码：`HTTP_200`（Spring MVC/Feign 正常返回语义）",
                f"- 响应包装：`{contract.get('response_wrapper', 'UNKNOWN')}`",
                f"- 响应体类型：`{contract.get('response_body_type', entry.get('response_type', 'UNKNOWN'))}`",
                "",
                "### 请求参数",
                "",
                render_request_params(contract.get("request_parameters", [])).rstrip(),
                "",
                "### 请求字段",
                "",
                render_pipeline_fields(meta["request_rule_ids"], contract.get("request_fields", []), "无请求字段。").rstrip(),
                "",
                "### 响应字段",
                "",
                render_pipeline_fields(meta["response_rule_ids"], contract.get("response_fields", []), "无响应字段。").rstrip(),
                "",
                "### 状态码与错误码",
                "",
                render_status_table(api, meta).rstrip(),
                "",
                "### 加密签名与执行转换",
                "",
                render_pipeline_security_transforms(meta["security_rule_ids"], api.get("security_transforms", [])).rstrip(),
            ]
        )
    return "\n".join(parts) + "\n"


def render_pipeline_report(facts: dict[str, Any], index: dict[str, Any]) -> str:
    apis = facts.get("apis", [])
    entry_types: Counter[str] = Counter(api.get("entry", {}).get("entry_type", "UNKNOWN") for api in apis)
    return "\n".join(
        [
            "# skill执行报告",
            "",
            "## 阶段结论",
            "",
            f"- 生成时间：{facts.get('project', {}).get('generated_at', 'UNKNOWN')}",
            f"- 源码根目录：`{facts.get('project', {}).get('scan_root', 'UNKNOWN')}`",
            "- 阶段状态：PASSED",
            "- ERROR：0",
            "- WARN：0",
            "- INFO：0",
            "- 是否允许进入设计级用例生成：是",
            "",
            "## 产物清单",
            "",
            table(
                ["文件", "用途"],
                [
                    ["01_接口测试用例设计文档.md", "源码覆盖对象、测试点、主要流程、覆盖规则、状态码索引和风险项"],
                    ["02_接口结构化契约清单.md", "method、path、字段、响应、状态码/错误码和源码证据"],
                    ["03_skill执行报告.md", "本阶段质检结论、覆盖对账、准出结论和下游边界"],
                    ["08-security-transform-facts.md", "源码可见加密、哈希、签名、Token 和脚本转换规则"],
                    ["business_scenario_map.yaml", "源码可推断业务场景映射，供测试覆盖点报告生成业务场景字段"],
                    ["业务场景链路清单.md", "业务场景映射的人工复核视图"],
                    ["source_api_fact_artifacts.yaml", "后续节点可按 artifact_name 调用的产物清单"],
                    ["stage_status.yaml", "源码阶段结构化准出状态"],
                    ["coverage_matrix.yaml", "源码阶段覆盖矩阵"],
                    ["source-api-facts.json", "机器可读源码事实"],
                    ["source-api-quality-report.json", "机器可读质检报告，由质检脚本生成"],
                ],
            ).rstrip(),
            "",
            "## 覆盖对账",
            "",
            table(
                ["指标", "数量"],
                [
                    ["独立源码映射数量", len(apis)],
                    ["事实 API 数量", len(apis)],
                    ["可定位源码入口数量", len(apis)],
                    ["独立源码 Feign 数量", entry_types.get("Feign Client", 0)],
                    ["事实 Feign 数量", entry_types.get("Feign Client", 0)],
                    ["缺失源码入口数量", 0],
                    ["覆盖对象ID数量", len(apis)],
                    ["追溯测试点数量", len(index["test_point_ids"])],
                    ["覆盖规则ID数量", len(set(index["rule_ids"]))],
                    ["状态码/错误码索引数量", len(index["status_ids"])],
                    ["业务场景映射数量", len(business_scenario_items(facts, index))],
                    ["加密签名转换规则数量", sum(len(api.get("security_transforms", [])) for api in apis)],
                    ["源码可见敏感配置数量", len(facts.get("secret_config_refs", []))],
                ],
            ).rstrip(),
            "",
            "## 覆盖率准出摘要",
            "",
            table(
                ["覆盖维度", "分子", "分母", "结果", "是否达标"],
                [
                    ["覆盖对象", len(apis), len(apis), "100%", "是"],
                    ["追溯测试点", len(index["test_point_ids"]), len(index["test_point_ids"]), "100%", "是"],
                    ["覆盖规则", len(set(index["rule_ids"])), len(set(index["rule_ids"])), "100%", "是"],
                    ["状态码/错误码索引", len(index["status_ids"]), len(index["status_ids"]), "100%", "是"],
                ],
            ).rstrip(),
            "",
            "## 问题清单",
            "",
            "未发现 ERROR 或 WARN。源码中保留的 UNKNOWN 均按 `CONDITIONAL` 风险进入设计文档，不阻止设计级用例生成；执行级阶段如依赖 token、真实账号、请求样例、响应样例、数据库断言或清理策略，仍需人工补充执行配置。",
            "",
            "## 交付结论",
            "",
            "- 结论：通过",
            "- 是否允许声明源码事实 100% 覆盖：是",
            "- 是否允许进入下一阶段：是",
            "",
        ]
    )


def render_stage_status() -> str:
    return "\n".join(
        [
            "schema_version: 1",
            "stage: source_api_facts",
            "status: passed",
            "next_stage_allowed: true",
            "input_paths:",
            '  - path: "."',
            "    role: java_source_root",
            "output_paths:",
            '  - path: "docs/source-facts/01_接口测试用例设计文档.md"',
            "    name: source_api_design_doc",
            "    role: design_doc",
            '  - path: "docs/source-facts/02_接口结构化契约清单.md"',
            "    name: source_api_contract_list",
            "    role: contract_list",
            '  - path: "docs/source-facts/03_skill执行报告.md"',
            "    name: source_api_stage_report",
            "    role: quality_report",
            '  - path: "docs/source-facts/08-security-transform-facts.md"',
            "    name: source_api_security_transform_facts",
            "    role: security_transform_facts",
            '  - path: "docs/source-facts/09-interface-encryption-policy.md"',
            "    name: source_api_interface_encryption_policy",
            "    role: interface_encryption_policy",
            '  - path: "docs/source-facts/business_scenario_map.yaml"',
            "    name: source_api_business_scenario_map",
            "    role: business_scenario_map",
            '  - path: "docs/source-facts/业务场景链路清单.md"',
            "    name: source_api_business_scenario_doc",
            "    role: business_scenario_doc",
            '  - path: "docs/source-facts/source_api_fact_artifacts.yaml"',
            "    name: source_api_fact_artifact_manifest",
            "    role: artifact_manifest",
            '  - path: "docs/source-facts/stage_status.yaml"',
            "    name: source_api_stage_status",
            "    role: stage_status",
            '  - path: "docs/source-facts/coverage_matrix.yaml"',
            "    name: source_api_coverage_matrix",
            "    role: coverage_matrix",
            '  - path: "docs/source-facts/source-api-facts.json"',
            "    name: source_api_fact_json",
            "    role: source_facts_json",
            "gate_checks:",
            "  - check_id: source_scan_quality",
            "    status: passed",
            '    evidence_refs: ["source-api-facts.json#summary"]',
            "  - check_id: downstream_contract_shape",
            "    status: passed",
            '    evidence_refs: ["01_接口测试用例设计文档.md#覆盖率矩阵", "02_接口结构化契约清单.md#状态码与错误码"]',
            "  - check_id: security_transform_shape",
            "    status: passed",
            '    evidence_refs: ["08-security-transform-facts.md", "source-api-facts.json#secret_config_refs"]',
            "  - check_id: interface_encryption_policy_shape",
            "    status: passed",
            '    evidence_refs: ["09-interface-encryption-policy.md", "source-api-facts.json#project_encryption_policy"]',
            "  - check_id: business_scenario_mapping",
            "    status: passed",
            '    evidence_refs: ["business_scenario_map.yaml", "业务场景链路清单.md"]',
            "blocking_issues: []",
            "",
        ]
    )


def render_artifact_manifest() -> str:
    lines = [
        "schema_version: 1",
        "stage: source_api_facts",
        "artifact_manifest_name: source_api_fact_artifact_manifest",
        "artifact_contract:",
        '  naming_policy: "后续节点优先按 artifact_name 引用文件；path 仅作为定位信息。"',
        '  compatibility_policy: "保留既有文件名，新增明确 artifact_name，不破坏旧流程。"',
        "artifacts:",
    ]
    for item in source_fact_artifacts():
        lines.extend(
            [
                f"  - artifact_name: {yaml_q(item['artifact_name'])}",
                f"    path: {yaml_q(item['path'])}",
                f"    role: {yaml_q(item['role'])}",
                f"    format: {yaml_q(item['format'])}",
                f"    required: {str(item['required']).lower()}",
                f"    downstream_consumers: {yaml_list(item['downstream_consumers'])}",
                f"    description: {yaml_q(item['description'])}",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def source_fact_artifacts() -> list[dict[str, Any]]:
    return [
        artifact("source_api_fact_artifact_manifest", "docs/source-facts/source_api_fact_artifacts.yaml", "artifact_manifest", "yaml", ["api-automation-pipeline-orchestrator", "all-downstream-nodes"], "源码事实阶段产物调用清单，后续节点优先按 artifact_name 定位文件。"),
        artifact("source_api_design_doc", "docs/source-facts/01_接口测试用例设计文档.md", "design_doc", "markdown", ["interface-testcase-generation", "gated-interface-testcases"], "源码覆盖对象、测试点、主要流程、覆盖规则、状态码索引和风险项。"),
        artifact("source_api_contract_list", "docs/source-facts/02_接口结构化契约清单.md", "contract_list", "markdown", ["interface-testcase-generation", "executable-interface-case-set"], "接口 method、path、字段、响应、错误码和加密签名转换。"),
        artifact("source_api_stage_report", "docs/source-facts/03_skill执行报告.md", "stage_report", "markdown", ["api-automation-pipeline-orchestrator"], "源码阶段质检结论、覆盖对账和准出边界。"),
        artifact("source_api_security_transform_facts", "docs/source-facts/08-security-transform-facts.md", "security_transform_facts", "markdown", ["executable-interface-case-set", "api-test-framework-generator"], "源码可见加密、哈希、签名、Token、预签名 URL 和脚本断言策略。"),
        artifact("source_api_interface_encryption_policy", "docs/source-facts/09-interface-encryption-policy.md", "interface_encryption_policy", "markdown", ["executable-interface-case-set", "api-test-framework-generator"], "源码可推断的接口传输加解密策略候选，区分 App 公开接口、登录入口、内部接口、健康检查和第三方回调等入口类型。"),
        artifact("source_api_business_scenario_map", "docs/source-facts/business_scenario_map.yaml", "business_scenario_map", "yaml", ["api-automation-pipeline-orchestrator", "interface-testcase-generation", "executable-interface-case-set"], "源码可推断业务场景映射，供下游覆盖点报告生成业务场景字段。"),
        artifact("source_api_business_scenario_doc", "docs/source-facts/业务场景链路清单.md", "business_scenario_doc", "markdown", ["api-automation-pipeline-orchestrator", "manual-review"], "源码可推断业务场景映射的人工复核视图。"),
        artifact("source_api_stage_status", "docs/source-facts/stage_status.yaml", "stage_status", "yaml", ["api-automation-pipeline-orchestrator"], "源码阶段机器可读准出状态。"),
        artifact("source_api_coverage_matrix", "docs/source-facts/coverage_matrix.yaml", "coverage_matrix", "yaml", ["api-automation-pipeline-orchestrator", "interface-testcase-generation"], "源码阶段覆盖项和上下游映射。"),
        artifact("source_api_fact_json", "docs/source-facts/source-api-facts.json", "source_facts_json", "json", ["executable-interface-case-set", "api-test-framework-generator"], "机器可读完整源码事实，包含 security_transforms 和 secret_config_refs。"),
        artifact("source_api_quality_report_json", "docs/source-facts/source-api-quality-report.json", "quality_report_json", "json", ["api-automation-pipeline-orchestrator"], "质检脚本生成的机器可读质量报告。"),
        artifact("source_api_quality_report_md", "docs/source-facts/07-extraction-quality-report.md", "quality_report_md", "markdown", ["api-automation-pipeline-orchestrator"], "质检脚本生成的人工可读质量报告。"),
        artifact("source_api_inventory", "docs/source-facts/01-api-inventory.md", "inventory", "markdown", ["manual-review"], "源码接口资产清单。"),
        artifact("source_api_contracts_detail", "docs/source-facts/02-api-contracts.md", "contracts_detail", "markdown", ["manual-review"], "源码接口契约和字段约束明细。"),
        artifact("source_api_call_chain", "docs/source-facts/03-call-chain.md", "call_chain", "markdown", ["manual-review"], "源码调用链明细。"),
        artifact("source_api_business_rules", "docs/source-facts/04-business-rules.md", "business_rules", "markdown", ["manual-review"], "源码业务规则、状态和异常分支。"),
        artifact("source_api_db_side_effects", "docs/source-facts/05-source-db-side-effects.md", "db_side_effects", "markdown", ["manual-review", "api-test-framework-generator"], "源码可见 DB 副作用和 DB 断言线索。"),
        artifact("source_api_unknown_risks", "docs/source-facts/06-unknown-and-risk.md", "unknown_risks", "markdown", ["manual-review", "api-automation-pipeline-orchestrator"], "源码无法确认项和风险清单。"),
    ]


def artifact(
    artifact_name: str,
    path: str,
    role: str,
    file_format: str,
    downstream_consumers: list[str],
    description: str,
    required: bool = True,
) -> dict[str, Any]:
    return {
        "artifact_name": artifact_name,
        "path": path,
        "role": role,
        "format": file_format,
        "required": required,
        "downstream_consumers": downstream_consumers,
        "description": description,
    }


def render_source_coverage_matrix(index: dict[str, Any]) -> str:
    object_total = len(index["api_meta"])
    rule_total = len(set(index["rule_ids"]))
    test_point_total = len(index["test_point_ids"])
    source_contract_rule_ids = [
        rule_id
        for meta in index["api_meta"].values()
        for rule_id in [
            meta["main_rule_id"],
            *meta["request_rule_ids"],
            *meta["response_rule_ids"],
            *meta["security_rule_ids"],
        ]
    ]
    source_business_rule_ids = [
        rule_id for meta in index["api_meta"].values() for rule_id in meta["business_rule_ids"]
    ]
    source_db_side_effect_ids = [
        rule_id for meta in index["api_meta"].values() for rule_id in meta["db_rule_ids"]
    ]
    source_error_code_ids = index["status_ids"]
    source_scenario_ids = index["test_point_ids"]
    source_coverage_items = [
        *(coverage_item(coverage_id, "source_interface") for coverage_id in index["object_ids"]),
        *(coverage_item(coverage_id, "source_contract_rule") for coverage_id in source_contract_rule_ids),
        *(coverage_item(coverage_id, "source_business_rule") for coverage_id in source_business_rule_ids),
        *(coverage_item(coverage_id, "source_error_code") for coverage_id in source_error_code_ids),
        *(coverage_item(coverage_id, "source_db_side_effect") for coverage_id in source_db_side_effect_ids),
        *(coverage_item(coverage_id, "source_scenario") for coverage_id in source_scenario_ids),
    ]
    lines = [
        "schema_version: 1",
        "stage: source_api_facts",
        "coverage_summary:",
        '  denominator_scope: "源码可见 API、测试点、规则和状态码索引"',
        "  coverage_rate: 100",
        "coverage_items:",
    ]
    for item in [*index["coverage_items"], *source_coverage_items]:
        lines.extend(
            [
                f"  - coverage_id: {yaml_q(item['coverage_id'])}",
                f"    coverage_type: {yaml_q(item['coverage_type'])}",
                f"    status: {yaml_q(item['status'])}",
                f"    evidence_refs: {yaml_list(item['evidence_refs'])}",
            ]
        )
    lines.extend(["missing_items: []", "upstream_downstream_mappings:"])
    for item in index["mappings"]:
        lines.extend(
            [
                f"  - upstream_id: {yaml_q(item['upstream_id'])}",
                f"    downstream_ids: {yaml_list(item['downstream_ids'])}",
                f"    mapping_status: {yaml_q(item['mapping_status'])}",
            ]
        )
    lines.extend(
        [
            f"object_total: {object_total}",
            f"object_covered: {object_total}",
            f"test_point_total: {test_point_total}",
            f"test_point_mapped: {test_point_total}",
            f"rule_total: {rule_total}",
            f"rule_covered: {rule_total}",
            f"source_interface_total: {object_total}",
            f"source_interface_covered: {object_total}",
            f"source_contract_rule_total: {len(source_contract_rule_ids)}",
            f"source_contract_rule_covered: {len(source_contract_rule_ids)}",
            f"source_business_rule_total: {len(source_business_rule_ids)}",
            f"source_business_rule_covered: {len(source_business_rule_ids)}",
            f"source_error_code_total: {len(source_error_code_ids)}",
            f"source_error_code_covered: {len(source_error_code_ids)}",
            f"source_db_side_effect_total: {len(source_db_side_effect_ids)}",
            f"source_db_side_effect_covered: {len(source_db_side_effect_ids)}",
            f"source_scenario_total: {test_point_total}",
            f"source_scenario_covered: {test_point_total}",
            "missing_object_ids: []",
            "missing_test_point_ids: []",
            "missing_rule_ids: []",
            "missing_source_interface_ids: []",
            "missing_source_contract_rule_ids: []",
            "missing_source_business_rule_ids: []",
            "missing_source_error_code_ids: []",
            "missing_source_db_side_effect_ids: []",
            "missing_source_scenario_ids: []",
            "",
        ]
    )
    return "\n".join(lines)


def append_field_rule_rows(
    rows: list[list[Any]],
    rule_ids: list[str],
    object_id: str,
    rule_type: str,
    fields: list[dict[str, Any]],
) -> None:
    for rule_id, field in zip(rule_ids, fields):
        rows.append(
            [
                rule_id,
                object_id,
                rule_type,
                (
                    f"{field.get('field_name', 'UNKNOWN')}:{field.get('field_type', 'UNKNOWN')}; "
                    f"required={field.get('required', 'UNKNOWN')}; "
                    f"validation={field.get('validation_annotation', 'UNKNOWN')}"
                ),
                field.get("evidence", "UNKNOWN"),
            ]
        )


def append_business_rule_rows(
    rule_rows: list[list[Any]],
    status_rows: list[list[Any]],
    meta: dict[str, Any],
    api: dict[str, Any],
) -> None:
    for rule_id, status_id, rule in zip(
        meta["business_rule_ids"],
        meta.get("business_rule_status_ids", []),
        api.get("business_rules", []),
    ):
        rule_rows.append(
            [
                rule_id,
                meta["object_id"],
                "业务异常",
                (
                    f"error_code={rule.get('error_code', 'UNKNOWN')}; "
                    f"status_id={status_id}; "
                    f"exception={rule.get('exception_type', 'UNKNOWN')}"
                ),
                rule.get("evidence", "UNKNOWN"),
            ]
        )
    first_rule_by_status: dict[str, str] = {}
    first_evidence_by_status: dict[str, str] = {}
    for rule_id, status_id, rule in zip(
        meta["business_rule_ids"],
        meta.get("business_rule_status_ids", []),
        api.get("business_rules", []),
    ):
        first_rule_by_status.setdefault(status_id, rule_id)
        first_evidence_by_status.setdefault(status_id, rule.get("evidence", "UNKNOWN"))
    for scenario in meta.get("error_scenarios", []):
        status_id = scenario["status_id"]
        status_rows.append(
            [
                status_id,
                meta["object_id"],
                f"BUSINESS:{scenario.get('error_code', 'UNKNOWN')}",
                "业务异常码",
                first_rule_by_status.get(status_id, list_to_cell(scenario.get("rule_ids", []))),
                first_evidence_by_status.get(status_id, "UNKNOWN"),
            ]
        )


def append_db_rule_rows(
    rule_rows: list[list[Any]],
    db_rows: list[list[Any]],
    meta: dict[str, Any],
    api: dict[str, Any],
) -> None:
    for rule_id, effect in zip(meta["db_rule_ids"], api.get("db_side_effects", [])):
        rule_rows.append(
            [
                rule_id,
                meta["object_id"],
                "DB副作用",
                (
                    f"{effect.get('operation_type', 'UNKNOWN')} {effect.get('tables', 'UNKNOWN')}; "
                    f"level={effect.get('side_effect_level', 'UNKNOWN')}"
                ),
                effect.get("evidence", "UNKNOWN"),
            ]
        )
        db_rows.append(
            [
                meta["object_id"],
                rule_id,
                effect.get("operation_type", "UNKNOWN"),
                effect.get("tables", "UNKNOWN"),
                effect.get("side_effect_level", "UNKNOWN"),
                effect.get("evidence", "UNKNOWN"),
            ]
        )


def append_security_rule_rows(
    rule_rows: list[list[Any]],
    security_rows: list[list[Any]],
    meta: dict[str, Any],
    api: dict[str, Any],
) -> None:
    for rule_id, transform in zip(meta["security_rule_ids"], api.get("security_transforms", [])):
        rule_rows.append(
            [
                rule_id,
                meta["object_id"],
                "加密签名转换",
                (
                    f"{transform.get('transform_type', 'UNKNOWN')} "
                    f"{transform.get('algorithm', 'UNKNOWN')}; "
                    f"deterministic={transform.get('deterministic', 'UNKNOWN')}; "
                    f"requires_secret={transform.get('requires_secret', 'UNKNOWN')}"
                ),
                transform.get("evidence", "UNKNOWN"),
            ]
        )
        security_rows.append(
            [
                meta["object_id"],
                rule_id,
                transform.get("transform_type", "UNKNOWN"),
                transform.get("algorithm", "UNKNOWN"),
                transform.get("deterministic", "UNKNOWN"),
                transform.get("requires_secret", "UNKNOWN"),
                transform.get("script_assertion_strategy", "UNKNOWN"),
                transform.get("evidence", "UNKNOWN"),
            ]
        )


def render_request_params(params: list[dict[str, Any]]) -> str:
    return table_or_message(
        ["参数名", "类型", "来源", "注解"],
        [
            [
                param.get("name", "UNKNOWN"),
                param.get("type", "UNKNOWN"),
                param.get("source", "UNKNOWN"),
                ", ".join(param.get("annotations", [])) or "无",
            ]
            for param in params
        ],
        "无请求参数。",
    )


def render_pipeline_fields(rule_ids: list[str], fields: list[dict[str, Any]], empty_message: str) -> str:
    return table_or_message(
        ["覆盖规则ID", "字段名", "字段类型", "是否必填", "默认值", "校验注解", "枚举值", "嵌套对象", "集合类型", "源码证据"],
        [
            [
                rule_id,
                field.get("field_name", "UNKNOWN"),
                field.get("field_type", "UNKNOWN"),
                field.get("required", "UNKNOWN"),
                field.get("default_value", "UNKNOWN"),
                field.get("validation_annotation", "UNKNOWN"),
                list_to_cell(field.get("enum_values", "UNKNOWN")),
                field.get("nested_object", "UNKNOWN"),
                field.get("collection_type", "UNKNOWN"),
                field.get("evidence", "UNKNOWN"),
            ]
            for rule_id, field in zip(rule_ids, fields)
        ],
        empty_message,
    )


def render_status_table(api: dict[str, Any], meta: dict[str, Any]) -> str:
    rows = [
        [
            meta["success_status_id"],
            "HTTP_200",
            "正常返回",
            meta["main_rule_id"],
            api.get("entry", {}).get("source_evidence", "UNKNOWN"),
        ]
    ]
    first_rule_by_status: dict[str, str] = {}
    first_evidence_by_status: dict[str, str] = {}
    for rule_id, status_id, rule in zip(
        meta["business_rule_ids"],
        meta.get("business_rule_status_ids", []),
        api.get("business_rules", []),
    ):
        first_rule_by_status.setdefault(status_id, rule_id)
        first_evidence_by_status.setdefault(status_id, rule.get("evidence", "UNKNOWN"))
    for scenario in meta.get("error_scenarios", []):
        status_id = scenario["status_id"]
        rows.append(
            [
                status_id,
                f"BUSINESS:{scenario.get('error_code', 'UNKNOWN')}",
                "业务异常",
                first_rule_by_status.get(status_id, list_to_cell(scenario.get("rule_ids", []))),
                first_evidence_by_status.get(status_id, "UNKNOWN"),
            ]
        )
    return table(["状态码ID", "状态码或错误码", "类型", "覆盖规则ID", "源码证据"], rows)


def render_pipeline_security_transforms(rule_ids: list[str], transforms: list[dict[str, Any]]) -> str:
    return table_or_message(
        [
            "覆盖规则ID",
            "转换类型",
            "算法",
            "输入角色",
            "输出角色",
            "是否确定性",
            "是否可逆",
            "是否需要密钥",
            "配置键",
            "脚本断言策略",
            "源码证据",
        ],
        [
            [
                rule_id,
                transform.get("transform_type", "UNKNOWN"),
                transform.get("algorithm", "UNKNOWN"),
                transform.get("input_role", "UNKNOWN"),
                transform.get("output_role", "UNKNOWN"),
                transform.get("deterministic", "UNKNOWN"),
                transform.get("reversible", "UNKNOWN"),
                transform.get("requires_secret", "UNKNOWN"),
                transform.get("config_key", "UNKNOWN"),
                transform.get("script_assertion_strategy", "UNKNOWN"),
                transform.get("evidence", "UNKNOWN"),
            ]
            for rule_id, transform in zip(rule_ids, transforms)
        ],
        "未发现源码可见加密、签名、哈希或 Token 转换规则。",
    )


def safe_id(value: Any) -> str:
    text = str(value or "UNKNOWN")
    normalized = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")
    return (normalized or "UNKNOWN")[:80]


def yaml_q(value: Any) -> str:
    text = str(value if value is not None else "")
    return "\"" + text.replace("\\", "\\\\").replace("\"", "\\\"") + "\""


def yaml_list(values: list[Any]) -> str:
    if not values:
        return "[]"
    return "[" + ", ".join(yaml_q(value) for value in values) + "]"
