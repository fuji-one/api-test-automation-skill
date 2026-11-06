from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from extract_java_api import UNKNOWN, JavaClass, SourceFile, annotation_name, evidence


XML_SQL_RE = re.compile(
    r"<(?P<op>insert|update|delete|select)\b[^>]*\bid=[\"'](?P<id>[^\"']+)[\"'][^>]*>(?P<body>.*?)</(?P=op)>",
    flags=re.DOTALL | re.IGNORECASE,
)
ANNOTATION_SQL_RE = re.compile(r"@(Insert|Update|Delete|Select)\s*\((?P<body>.*?)\)", flags=re.DOTALL)
CALL_RE = re.compile(r"\b(?P<receiver>[A-Za-z_]\w*)\.(?P<method>[A-Za-z_]\w*)\s*\(")


def parse_sql_operations(files: list[SourceFile], classes: dict[str, JavaClass]) -> dict[str, dict[str, Any]]:
    operations: dict[str, dict[str, Any]] = {}
    for source in files:
        if source.path.suffix == ".xml":
            namespace = extract_namespace(source.text)
            mapper_name = namespace.split(".")[-1] if namespace != UNKNOWN else Path(source.rel_path).stem
            for match in XML_SQL_RE.finditer(source.text):
                op = match.group("op").lower()
                method_id = match.group("id")
                sql = re.sub(r"\s+", " ", match.group("body")).strip()
                operations[f"{mapper_name}.{method_id}"] = {
                    "mapper_or_repository": mapper_name,
                    "method_name": method_id,
                    "sql_operation": op,
                    "tables": extract_tables(sql, op),
                    "evidence": f"{source.rel_path} | {mapper_name}.{method_id}",
                }
        elif source.path.suffix == ".java":
            java_class = class_for_path(classes, source.rel_path)
            if not java_class:
                continue
            for method in java_class.methods:
                for annotation in method.annotations:
                    ann_name = annotation_name(annotation)
                    if ann_name in {"Insert", "Update", "Delete", "Select"}:
                        op = ann_name.lower()
                        operations[f"{java_class.name}.{method.name}"] = {
                            "mapper_or_repository": java_class.name,
                            "method_name": method.name,
                            "sql_operation": op,
                            "tables": extract_tables(annotation, op),
                            "evidence": evidence(java_class.path, java_class.name, method.name, method.line),
                        }
    return operations


def build_db_side_effects(
    apis: list[dict[str, Any]],
    classes: dict[str, JavaClass],
    call_chains: dict[str, list[dict[str, Any]]],
    sql_operations: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    class_by_name = {c.name: c for c in {id(v): v for v in classes.values()}.values()}
    metadata = build_persistence_metadata(class_by_name)
    result: dict[str, list[dict[str, Any]]] = {}
    for api in apis:
        effects: list[dict[str, Any]] = []
        transaction_boundary = transaction_for_chain(call_chains.get(api["api_id"], []), class_by_name)
        for call in call_chains.get(api["api_id"], []):
            class_name = call["class_name"]
            method_name = call["method_name"]
            if not is_data_access(class_name):
                continue
            for op in resolve_operations_for_call(class_name, method_name, class_by_name, sql_operations, metadata, call):
                side_effect_level = side_effect_level_for(op["sql_operation"], op["tables"])
                effects.append(
                    {
                        "api_id": api["api_id"],
                        "operation_type": operation_type(op["sql_operation"]),
                        "tables": op["tables"] or UNKNOWN,
                        "entity_or_do": op.get("entity_or_do") or infer_entity_or_do(class_by_name.get(class_name)),
                        "mapper_or_repository": op["mapper_or_repository"],
                        "sql_operation": op["sql_operation"],
                        "transaction_boundary": transaction_boundary,
                        "side_effect_level": side_effect_level,
                        "db_assertion_hint": assertion_hint(side_effect_level),
                        "evidence": op.get("evidence", call["evidence"]),
                    }
                )
        if not effects:
            effects.append(
                {
                    "api_id": api["api_id"],
                    "operation_type": UNKNOWN,
                    "tables": UNKNOWN,
                    "entity_or_do": UNKNOWN,
                    "mapper_or_repository": UNKNOWN,
                    "sql_operation": UNKNOWN,
                    "transaction_boundary": transaction_boundary,
                    "side_effect_level": UNKNOWN,
                    "db_assertion_hint": UNKNOWN,
                    "evidence": api["source_evidence"],
                }
            )
        result[api["api_id"]] = dedupe_effects(effects)
    return result


def build_persistence_metadata(class_by_name: dict[str, JavaClass]) -> dict[str, Any]:
    entity_tables = {
        java_class.name: java_class.table_name
        for java_class in class_by_name.values()
        if java_class.table_name != UNKNOWN
    }
    mapper_entities: dict[str, str] = {}
    for java_class in class_by_name.values():
        match = re.search(r"\bBaseMapper\s*<\s*([\w.]+)\s*>", java_class.declaration)
        if match:
            mapper_entities[java_class.name] = clean_class_name(match.group(1))

    repository_impls: dict[str, JavaClass] = {}
    for java_class in class_by_name.values():
        if java_class.name.endswith("RepositoryImpl"):
            repository_impls[java_class.name[: -len("Impl")]] = java_class
        for repo_name in re.findall(r"\b(\w+Repository)\b", java_class.declaration):
            if java_class.name != repo_name and java_class.name.endswith("Impl"):
                repository_impls[repo_name] = java_class

    return {
        "entity_tables": entity_tables,
        "mapper_entities": mapper_entities,
        "repository_impls": repository_impls,
    }


def resolve_operations_for_call(
    class_name: str,
    method_name: str,
    class_by_name: dict[str, JavaClass],
    sql_operations: dict[str, dict[str, Any]],
    metadata: dict[str, Any],
    call: dict[str, Any],
) -> list[dict[str, Any]]:
    direct_sql = sql_operations.get(f"{class_name}.{method_name}")
    if direct_sql:
        return [enrich_operation(direct_sql, metadata, class_name, direct_sql.get("evidence", call["evidence"]))]

    if class_name in metadata["mapper_entities"]:
        inferred = infer_operation_from_method(class_name, method_name)
        return [enrich_operation(inferred, metadata, class_name, call["evidence"])]

    repository_ops = resolve_repository_impl_operations(class_name, method_name, class_by_name, sql_operations, metadata)
    if repository_ops:
        return repository_ops

    inferred = infer_operation_from_method(class_name, method_name)
    return [enrich_operation(inferred, metadata, class_name, call["evidence"])]


def resolve_repository_impl_operations(
    repository_name: str,
    method_name: str,
    class_by_name: dict[str, JavaClass],
    sql_operations: dict[str, dict[str, Any]],
    metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    impl_class = metadata["repository_impls"].get(repository_name)
    if not impl_class:
        return []
    method = find_method(impl_class, method_name)
    if not method:
        return []

    field_types = {field.name: clean_class_name(field.type) for field in impl_class.fields}
    operations: list[dict[str, Any]] = []
    for line_no, line in enumerate(method.body.splitlines(), start=method.line):
        for match in CALL_RE.finditer(line):
            receiver = match.group("receiver")
            called_method = match.group("method")
            mapper_name = field_types.get(receiver)
            if not mapper_name or not is_data_access(mapper_name):
                continue
            base_operation = sql_operations.get(f"{mapper_name}.{called_method}") or infer_operation_from_method(
                mapper_name, called_method
            )
            base_operation = dict(base_operation)
            base_operation["mapper_or_repository"] = f"{repository_name} -> {mapper_name}"
            base_operation["evidence"] = evidence(impl_class.path, impl_class.name, method.name, line_no)
            operations.append(enrich_operation(base_operation, metadata, mapper_name, base_operation["evidence"]))

    if operations:
        return operations

    mapper_fields = [clean_class_name(field.type) for field in impl_class.fields if is_data_access(clean_class_name(field.type))]
    fallback_mapper = mapper_fields[0] if mapper_fields else repository_name
    fallback = infer_operation_from_method(fallback_mapper, method_name)
    fallback["mapper_or_repository"] = f"{repository_name} -> {fallback_mapper}" if fallback_mapper != repository_name else repository_name
    fallback["evidence"] = evidence(impl_class.path, impl_class.name, method.name, method.line)
    return [enrich_operation(fallback, metadata, fallback_mapper, fallback["evidence"])]


def enrich_operation(
    operation: dict[str, Any],
    metadata: dict[str, Any],
    data_access_class_name: str,
    evidence_value: str,
) -> dict[str, Any]:
    result = dict(operation)
    entity = metadata["mapper_entities"].get(data_access_class_name, UNKNOWN)
    table = result.get("tables", UNKNOWN)
    if table == UNKNOWN and entity != UNKNOWN:
        table = metadata["entity_tables"].get(entity, UNKNOWN)
    result["tables"] = table
    result["entity_or_do"] = entity
    result["evidence"] = result.get("evidence") or evidence_value
    return result


def extract_namespace(text: str) -> str:
    match = re.search(r"<mapper\s+namespace=[\"']([^\"']+)[\"']", text)
    return match.group(1) if match else UNKNOWN


def extract_tables(sql: str, op: str) -> str:
    patterns = {
        "insert": r"\binsert\s+into\s+`?([A-Za-z0-9_]+)`?",
        "update": r"\bupdate\s+`?([A-Za-z0-9_]+)`?",
        "delete": r"\bdelete\s+from\s+`?([A-Za-z0-9_]+)`?",
        "select": r"\bfrom\s+`?([A-Za-z0-9_]+)`?",
    }
    match = re.search(patterns.get(op, ""), sql, flags=re.IGNORECASE)
    return match.group(1) if match else UNKNOWN


def class_for_path(classes: dict[str, JavaClass], rel_path: str) -> JavaClass | None:
    for java_class in {id(v): v for v in classes.values()}.values():
        if java_class.path == rel_path:
            return java_class
    return None


def find_method(java_class: JavaClass, method_name: str) -> Any:
    for method in java_class.methods:
        if method.name == method_name:
            return method
    return None


def clean_class_name(type_name: str) -> str:
    return type_name.replace("final ", "").split("<")[0].split(".")[-1].strip()


def is_data_access(class_name: str) -> bool:
    lowered = class_name.lower()
    return any(token in lowered for token in ("mapper", "repository", "dao"))


def infer_operation_from_method(class_name: str, method_name: str) -> dict[str, Any]:
    lowered = method_name.lower()
    if any(token in lowered for token in ("insert", "create", "save", "add")):
        sql_op = "insert"
    elif any(token in lowered for token in ("update", "modify", "change")):
        sql_op = "update"
    elif any(token in lowered for token in ("delete", "remove")):
        sql_op = "delete"
    elif any(token in lowered for token in ("select", "find", "get", "query", "list")):
        sql_op = "select"
    else:
        sql_op = UNKNOWN.lower()
    return {
        "mapper_or_repository": class_name,
        "method_name": method_name,
        "sql_operation": sql_op,
        "tables": UNKNOWN,
        "evidence": UNKNOWN,
    }


def operation_type(sql_operation: str) -> str:
    return {
        "insert": "CREATE",
        "update": "UPDATE",
        "delete": "DELETE",
        "select": "READ",
    }.get(sql_operation, UNKNOWN)


def side_effect_level_for(sql_operation: str, tables: str) -> str:
    if sql_operation in {"insert", "update", "delete"} and tables != UNKNOWN:
        return "CONFIRMED"
    if sql_operation in {"insert", "update", "delete"}:
        return "POSSIBLE"
    if sql_operation == "select":
        return "NONE"
    return UNKNOWN


def assertion_hint(side_effect_level: str) -> str:
    if side_effect_level in {"CONFIRMED", "POSSIBLE"}:
        return "YES"
    if side_effect_level == "NONE":
        return "NO"
    return UNKNOWN


def transaction_for_chain(chain: list[dict[str, Any]], class_by_name: dict[str, JavaClass]) -> str:
    for call in chain:
        java_class = class_by_name.get(call["class_name"])
        if not java_class:
            continue
        class_tx = any(annotation_name(a) == "Transactional" for a in java_class.annotations)
        method_tx = False
        for method in java_class.methods:
            if method.name == call["method_name"]:
                method_tx = any(annotation_name(a) == "Transactional" for a in method.annotations)
                break
        if class_tx or method_tx:
            return f"@Transactional 位于 {call['class_name']}.{call['method_name']}"
    return UNKNOWN


def infer_entity_or_do(java_class: JavaClass | None) -> str:
    if not java_class:
        return UNKNOWN
    for field in java_class.fields:
        if field.type.endswith("DO") or field.type.endswith("Entity"):
            return field.type
    return UNKNOWN


def dedupe_effects(effects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict[str, Any]] = []
    for effect in effects:
        key = (effect["mapper_or_repository"], effect["sql_operation"], str(effect["tables"]))
        if key in seen:
            continue
        seen.add(key)
        result.append(effect)
    return result
