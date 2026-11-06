#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from extract_business_rules import build_business_rules
from extract_call_chain import build_call_chains
from extract_contracts import build_contracts
from extract_db_side_effects import build_db_side_effects, parse_sql_operations
from extract_encryption_policy import build_encryption_policy
from extract_java_api import UNKNOWN, build_api_inventory, discover_source_files, parse_java_files
from extract_security_transforms import build_security_transforms
from render_docs import render_all


def scan(src: str | Path, out: str | Path) -> dict[str, Any]:
    src_path = Path(src).resolve()
    files = discover_source_files(src_path)
    classes = parse_java_files(files)
    inventory = build_api_inventory(classes)
    contracts = build_contracts(inventory, classes)
    call_chains = build_call_chains(inventory, classes)
    business_rules = build_business_rules(inventory, classes, contracts, call_chains)
    sql_operations = parse_sql_operations(files, classes)
    db_side_effects = build_db_side_effects(inventory, classes, call_chains, sql_operations)
    security_transform_bundle = build_security_transforms(inventory, classes, files, call_chains)
    encryption_policy = build_encryption_policy(inventory, classes)
    encryption_policy_by_api = {
        item["api_id"]: item for item in encryption_policy.get("policy_items", []) if item.get("api_id")
    }

    apis: list[dict[str, Any]] = []
    for item in inventory:
        contract = contracts.get(item["api_id"], {})
        api_unknowns = collect_unknowns(item, contract, db_side_effects.get(item["api_id"], []))
        api = {
            "api_id": item["api_id"],
            "module": item["module"],
            "entry": {
                "entry_type": item["entry_type"],
                "class_name": item["class_name"],
                "method_name": item["method_name"],
                "http_method": item["http_method"],
                "path": item["path"],
                "rpc_interface": item["rpc_interface"],
                "request_type": item["request_type"],
                "response_type": item["response_type"],
                "auth_hint": item["auth_hint"],
                "source_evidence": item["source_evidence"],
            },
            "contract": public_contract(contract),
            "call_chain": call_chains.get(item["api_id"], []),
            "business_rules": business_rules.get(item["api_id"], []),
            "db_side_effects": db_side_effects.get(item["api_id"], []),
            "security_transforms": security_transform_bundle.get("api_transforms", {}).get(item["api_id"], []),
            "transport_encryption_policy": encryption_policy_by_api.get(item["api_id"], {}),
            "unknowns": api_unknowns,
        }
        apis.append(api)

    project_unknowns = collect_project_unknowns(apis)
    facts = {
        "project": {
            "name": src_path.name or UNKNOWN,
            "scan_root": str(src_path),
            "language": "Java" if any(f.path.suffix == ".java" for f in files) else UNKNOWN,
            "frameworks_detected": detect_frameworks(files),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "project_unknowns": project_unknowns,
        "project_security_transforms": security_transform_bundle.get("project_transforms", []),
        "project_encryption_policy": encryption_policy,
        "secret_config_refs": security_transform_bundle.get("secret_config_refs", []),
        "apis": apis,
        "summary": build_summary(apis, project_unknowns, security_transform_bundle.get("secret_config_refs", [])),
    }
    render_all(facts, out)
    return facts


def public_contract(contract: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in contract.items() if key != "unknowns"}


def detect_frameworks(files: list[Any]) -> list[str]:
    text = "\n".join(f.text[:5000] for f in files)
    frameworks: list[str] = []
    if "org.springframework" in text or "@RestController" in text:
        frameworks.append("Spring")
    if "FeignClient" in text:
        frameworks.append("Feign")
    if "org.apache.ibatis" in text or "<mapper" in text or "BaseMapper" in text:
        frameworks.append("MyBatis")
    if "javax.persistence" in text or "jakarta.persistence" in text:
        frameworks.append("JPA")
    if "Dubbo" in text or "DubboService" in text:
        frameworks.append("Dubbo")
    return frameworks


def collect_unknowns(
    api: dict[str, Any],
    contract: dict[str, Any],
    db_effects: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    unknowns: list[dict[str, Any]] = []
    for field_name in ("path", "http_method", "request_type", "response_type"):
        if api.get(field_name) == UNKNOWN:
            unknowns.append(
                unknown(
                    api,
                    field_name.upper(),
                    f"无法从源码注解或方法签名确认 {field_name}。",
                    api["source_evidence"],
                    "人工检查路由注解、拦截器、生成源码或框架配置。",
                )
            )
    unknowns.extend(contract.get("unknowns", []))
    for effect in db_effects:
        operation_type = effect.get("operation_type", UNKNOWN)
        if operation_type != UNKNOWN and effect.get("tables") == UNKNOWN:
            unknowns.append(
                unknown(
                    api,
                    "DB_TABLE",
                    "无法从 Mapper XML、SQL 注解或 Entity 元数据确认 DB 表名。",
                    effect.get("evidence", api["source_evidence"]),
                    "人工检查 Mapper XML、SQL Provider、Entity 注解或生成 SQL。",
                )
            )
        if operation_type != UNKNOWN and effect.get("side_effect_level") == UNKNOWN:
            unknowns.append(
                unknown(
                    api,
                    "DB_SIDE_EFFECT",
                    "无法通过静态源码扫描确认 DB 副作用级别。",
                    effect.get("evidence", api["source_evidence"]),
                    "人工追踪数据访问调用，包括动态 SQL 和框架基类方法。",
                )
            )
    return dedupe_unknowns(unknowns)


def collect_project_unknowns(apis: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unknowns: list[dict[str, Any]] = []
    auth_unknown_apis = [
        api["api_id"]
        for api in apis
        if api.get("entry", {}).get("auth_hint") == UNKNOWN
    ]
    if auth_unknown_apis:
        unknowns.append(
            project_unknown(
                "AUTH_HINT_GLOBAL",
                "接口入口未通过注解或方法签名声明鉴权线索。",
                "鉴权可能由网关、Filter、Interceptor、AOP 或统一安全配置完成，不能按接口逐条从入口源码确认。",
                "统一检查安全配置、网关规则、拦截器和白名单，再决定是否需要补充接口级权限表。",
                auth_unknown_apis,
                severity="MEDIUM",
                action_required="CONDITIONAL",
            )
        )

    db_unknown_apis = [
        api["api_id"]
        for api in apis
        if any(
            effect.get("operation_type") == UNKNOWN
            and effect.get("tables") == UNKNOWN
            and effect.get("mapper_or_repository") == UNKNOWN
            for effect in api.get("db_side_effects", [])
        )
    ]
    if db_unknown_apis:
        unknowns.append(
            project_unknown(
                "DB_SIDE_EFFECT_NOT_VISIBLE",
                "部分接口未发现源码可见 DB 访问链路。",
                "静态调用链未追踪到 Repository、Mapper、DAO 或 SQL 证据；这可能表示接口无 DB 副作用，也可能是动态调用、外部依赖、回调逻辑或扫描边界导致。",
                "只有当这些接口需要 DB 前置或后置断言时，再按 affected_api_ids 做人工复核。",
                db_unknown_apis,
                severity="LOW",
                action_required="CONDITIONAL",
            )
        )
    return unknowns


def project_unknown(
    unknown_type: str,
    description: str,
    why_unknown: str,
    suggested_manual_check: str,
    affected_api_ids: list[str],
    severity: str,
    action_required: str,
) -> dict[str, Any]:
    return {
        "unknown_id": f"PROJECT:{unknown_type}",
        "api_id": "PROJECT",
        "scope": "PROJECT",
        "unknown_type": unknown_type,
        "severity": severity,
        "action_required": action_required,
        "affected_api_count": len(affected_api_ids),
        "affected_api_ids": affected_api_ids,
        "description": description,
        "why_unknown": why_unknown,
        "evidence_or_location": f"{len(affected_api_ids)} 个接口，详见 affected_api_ids",
        "suggested_manual_check": suggested_manual_check,
    }


def unknown(
    api: dict[str, Any],
    unknown_type: str,
    description: str,
    location: str,
    suggested_manual_check: str,
) -> dict[str, Any]:
    return {
        "unknown_id": f"{api['api_id']}:{unknown_type}",
        "api_id": api["api_id"],
        "scope": "API",
        "unknown_type": unknown_type,
        "severity": "HIGH" if unknown_type in {"PATH", "HTTP_METHOD", "DB_TABLE", "DB_SIDE_EFFECT"} else "MEDIUM",
        "action_required": "YES" if unknown_type in {"PATH", "HTTP_METHOD", "DB_TABLE", "DB_SIDE_EFFECT"} else "CONDITIONAL",
        "description": description,
        "why_unknown": "扫描器未找到可由源码支撑的证据。",
        "evidence_or_location": location,
        "suggested_manual_check": suggested_manual_check,
    }


def dedupe_unknowns(unknowns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict[str, Any]] = []
    for item in unknowns:
        key = (item["api_id"], item["unknown_type"], item["description"])
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def build_summary(
    apis: list[dict[str, Any]],
    project_unknowns: list[dict[str, Any]] | None = None,
    secret_config_refs: list[dict[str, Any]] | None = None,
) -> dict[str, int]:
    project_unknowns = project_unknowns or []
    secret_config_refs = secret_config_refs or []
    return {
        "api_count": len(apis),
        "http_api_count": sum(1 for api in apis if api["entry"]["http_method"] != UNKNOWN),
        "rpc_api_count": sum(1 for api in apis if api["entry"]["rpc_interface"] != UNKNOWN),
        "unknown_path_count": sum(1 for api in apis if api["entry"]["path"] == UNKNOWN),
        "write_api_count": sum(
            1
            for api in apis
            if any(effect.get("operation_type") in {"CREATE", "UPDATE", "DELETE", "UPSERT"} for effect in api["db_side_effects"])
        ),
        "read_api_count": sum(
            1 for api in apis if any(effect.get("operation_type") == "READ" for effect in api["db_side_effects"])
        ),
        "business_rule_count": sum(len(api["business_rules"]) for api in apis),
        "security_transform_count": sum(len(api.get("security_transforms", [])) for api in apis),
        "secret_config_ref_count": len(secret_config_refs),
        "error_code_count": sum(
            1 for api in apis for rule in api["business_rules"] if rule.get("error_code", UNKNOWN) != UNKNOWN
        ),
        "unknown_count": sum(len(api["unknowns"]) for api in apis) + len(project_unknowns),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="从后端源码中抽取带源码证据的接口事实基线。")
    parser.add_argument("--src", required=True, help="需要扫描的源码根目录")
    parser.add_argument("--out", required=True, help="输出根目录，会在其中生成 docs/source-facts")
    args = parser.parse_args()
    facts = scan(args.src, args.out)
    print(
        f"已生成 {facts['summary']['api_count']} 条 API 事实："
        f"{Path(args.out).resolve() / 'docs' / 'source-facts'}"
    )


if __name__ == "__main__":
    main()
