from __future__ import annotations

import re
from typing import Any

from extract_java_api import FRAMEWORK_INJECTED, NO_REQUEST, UNKNOWN, JavaClass, clean_type, field_to_contract

UNSTRUCTURED_REQUEST_TYPES = {
    "String",
    "Object",
    "Map",
    "HashMap",
    "JSONObject",
    "JsonNode",
    "Long",
    "Integer",
    "Boolean",
}


def build_contracts(apis: list[dict[str, Any]], classes: dict[str, JavaClass]) -> dict[str, dict[str, Any]]:
    contracts: dict[str, dict[str, Any]] = {}
    for api in apis:
        request_types = [
            clean_type(t)
            for t in split_type_list(api.get("request_type", UNKNOWN))
            if t.strip() and clean_type(t) not in {UNKNOWN, NO_REQUEST}
        ]
        response_body_type = clean_type(api.get("response_body_type", UNKNOWN))
        request_fields: list[dict[str, Any]] = []
        response_fields: list[dict[str, Any]] = []
        unknowns: list[dict[str, Any]] = []

        for param in api.get("params", []):
            source = param.get("source", UNKNOWN)
            param_type = clean_type(param.get("type", UNKNOWN))
            if source == FRAMEWORK_INJECTED:
                continue
            if source == UNKNOWN:
                unknowns.append(
                    unknown(
                        api,
                        "REQUEST_BINDING_SOURCE",
                        f"参数 {param.get('name', UNKNOWN)} 缺少显式绑定注解，无法确认框架绑定来源。",
                    )
                )
            if source != "RequestBody" and source != "RPC DTO":
                request_fields.append(
                    {
                        "field_name": param.get("name", UNKNOWN),
                        "field_type": param.get("type", UNKNOWN),
                        "required": UNKNOWN,
                        "default_value": UNKNOWN,
                        "validation_annotation": ", ".join(param.get("annotations", [])) or UNKNOWN,
                        "enum_values": UNKNOWN,
                        "nested_object": "NO",
                        "collection_type": UNKNOWN,
                        "param_source": source,
                        "evidence": api["source_evidence"],
                    }
                )
                continue
            java_class = classes.get(param_type)
            if java_class:
                request_fields.extend(field_to_contract(f, classes, java_class) for f in java_class.fields)
            elif param_type not in {UNKNOWN, NO_REQUEST} and param_type not in UNSTRUCTURED_REQUEST_TYPES:
                unknowns.append(unknown(api, "REQUEST_FIELDS", f"请求类型 {param_type} 未在已解析源码类中找到。"))

        if not request_fields and request_types:
            for request_type in request_types:
                java_class = classes.get(request_type)
                if java_class:
                    request_fields.extend(field_to_contract(f, classes, java_class) for f in java_class.fields)
                elif request_type not in {UNKNOWN, NO_REQUEST} and request_type not in UNSTRUCTURED_REQUEST_TYPES:
                    unknowns.append(
                        unknown(api, "REQUEST_FIELDS", f"请求类型 {request_type} 未在已解析源码类中找到。")
                    )

        response_class = classes.get(response_body_type)
        if response_class:
            response_fields = [field_to_contract(f, classes, response_class) for f in response_class.fields]
        elif response_body_type not in {UNKNOWN, "Void", "void", "Boolean", "boolean", "String", "Long", "Integer"}:
            unknowns.append(
                unknown(api, "RESPONSE_FIELDS", f"响应类型 {response_body_type} 未在已解析源码类中找到。")
            )

        contracts[api["api_id"]] = {
            "api_id": api["api_id"],
            "entry": {
                "class_name": api["class_name"],
                "method_name": api["method_name"],
                "http_method": api["http_method"],
                "path": api["path"],
                "evidence": api["source_evidence"],
            },
            "request_parameters": api.get("params", []),
            "request_fields": request_fields,
            "response_wrapper": api.get("response_wrapper", UNKNOWN),
            "response_body_type": api.get("response_body_type", UNKNOWN),
            "response_fields": response_fields,
            "unknowns": unknowns,
        }
    return contracts


def split_type_list(type_text: str) -> list[str]:
    if not type_text.strip():
        return []
    chunks: list[str] = []
    depth = 0
    start = 0
    for idx, char in enumerate(type_text):
        if char == "<":
            depth += 1
        elif char == ">":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            chunks.append(type_text[start:idx].strip())
            start = idx + 1
    chunks.append(type_text[start:].strip())
    return [chunk for chunk in chunks if chunk]


def unknown(api: dict[str, Any], unknown_type: str, description: str) -> dict[str, Any]:
    suffix = re.sub(r"[^A-Za-z0-9_]+", "-", description).strip("-")[:48] or "item"
    return {
        "unknown_id": f"{api['api_id']}:{unknown_type}:{suffix}",
        "api_id": api["api_id"],
        "scope": "API",
        "unknown_type": unknown_type,
        "severity": "MEDIUM",
        "action_required": "CONDITIONAL",
        "description": description,
        "why_unknown": "源码扫描未找到被引用的类型或事实证据。",
        "evidence_or_location": api["source_evidence"],
        "suggested_manual_check": "人工检查源码定义、生成代码或框架绑定关系。",
    }
