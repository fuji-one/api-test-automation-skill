from __future__ import annotations

import re
from typing import Any

from dataclasses import dataclass

from extract_java_api import UNKNOWN, JavaClass, JavaMethod, evidence, split_params


CALL_RE = re.compile(r"\b(?P<receiver>[A-Za-z_]\w*)\.(?P<method>[A-Za-z_]\w*)\s*\(")
LOCAL_CALL_RE = re.compile(r"(?<![.\w])(?P<method>[A-Za-z_]\w*)\s*\(")
CONTROL_CALLS = {
    "if",
    "for",
    "while",
    "switch",
    "catch",
    "return",
    "throw",
    "new",
    "super",
    "this",
}


@dataclass(frozen=True)
class CallSite:
    receiver: str
    method_name: str
    arg_count: int | None
    line: int
    position: int


def build_call_chains(apis: list[dict[str, Any]], classes: dict[str, JavaClass]) -> dict[str, list[dict[str, Any]]]:
    unique_classes = {id(v): v for v in classes.values()}
    class_by_name = {c.name: c for c in unique_classes.values()}
    chains: dict[str, list[dict[str, Any]]] = {}
    for api in apis:
        entry_class = class_by_name.get(api["class_name"])
        if not entry_class:
            chains[api["api_id"]] = []
            continue
        entry_method = find_method(entry_class, api["method_name"])
        if not entry_method:
            chains[api["api_id"]] = []
            continue
        visited: set[tuple[str, str, str]] = set()
        chain = [
            {
                "class_name": entry_class.name,
                "method_name": entry_method.name,
                "call_type": classify_call_type(entry_class.name),
                "evidence": evidence(entry_class.path, entry_class.name, entry_method.name, entry_method.line),
                "notes": "入口",
            }
        ]
        chain.extend(trace_method_calls(entry_class, entry_method, class_by_name, visited, depth=0))
        chains[api["api_id"]] = chain
    return chains


def trace_method_calls(
    java_class: JavaClass,
    method: JavaMethod,
    class_by_name: dict[str, JavaClass],
    visited: set[tuple[str, str, str]],
    depth: int,
) -> list[dict[str, Any]]:
    if depth >= 5:
        return []
    key = method_key(java_class, method)
    if key in visited:
        return []
    visited.add(key)
    field_types = {field.name: clean_class_name(field.type) for field in java_class.fields}
    result: list[dict[str, Any]] = []
    for call in iter_call_sites(method.body, method.line):
        if call.receiver:
            target_class = resolve_receiver_target(java_class, call.receiver, field_types, class_by_name)
            if not target_class:
                continue
            notes = f"{call.receiver}.{call.method_name}()"
        else:
            target_class = java_class
            notes = f"{call.method_name}()"
            if call.method_name not in {candidate.name for candidate in java_class.methods}:
                continue

        result.append(
            {
                "class_name": target_class.name,
                "method_name": call.method_name,
                "call_type": classify_call_type(target_class.name),
                "evidence": evidence(java_class.path, java_class.name, method.name, call.line),
                "notes": notes,
            }
        )
        target_method = find_method(target_class, call.method_name, call.arg_count)
        if target_method:
            result.extend(trace_method_calls(target_class, target_method, class_by_name, visited, depth + 1))
    return dedupe_chain(result)


def iter_call_sites(body: str, start_line: int) -> list[CallSite]:
    calls: list[CallSite] = []
    qualified_spans: list[tuple[int, int]] = []
    for match in CALL_RE.finditer(body):
        receiver = match.group("receiver")
        method_name = match.group("method")
        if receiver in CONTROL_CALLS or method_name in CONTROL_CALLS:
            continue
        open_paren = match.end() - 1
        calls.append(
            CallSite(
                receiver=receiver,
                method_name=method_name,
                arg_count=count_call_args(body, open_paren),
                line=start_line + body.count("\n", 0, match.start()),
                position=match.start(),
            )
        )
        qualified_spans.append((match.start(), match.end()))

    for match in LOCAL_CALL_RE.finditer(body):
        if any(start <= match.start() < end for start, end in qualified_spans):
            continue
        method_name = match.group("method")
        if method_name in CONTROL_CALLS or method_name[:1].isupper():
            continue
        open_paren = match.end() - 1
        calls.append(
            CallSite(
                receiver="",
                method_name=method_name,
                arg_count=count_call_args(body, open_paren),
                line=start_line + body.count("\n", 0, match.start()),
                position=match.start(),
            )
        )
    return sorted(calls, key=lambda item: item.position)


def count_call_args(text: str, open_paren: int) -> int | None:
    if open_paren < 0 or open_paren >= len(text) or text[open_paren] != "(":
        return None
    depth = 0
    angle_depth = 0
    arg_text_start = open_paren + 1
    for idx in range(open_paren, len(text)):
        char = text[idx]
        if char == "<":
            angle_depth += 1
        elif char == ">":
            angle_depth = max(0, angle_depth - 1)
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                args = text[arg_text_start:idx].strip()
                if not args:
                    return 0
                return count_top_level_commas(args) + 1
    return None


def count_top_level_commas(text: str) -> int:
    comma_count = 0
    paren_depth = 0
    brace_depth = 0
    bracket_depth = 0
    angle_depth = 0
    in_string: str | None = None
    escaped = False
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == in_string:
                in_string = None
            continue
        if char in {"'", '"'}:
            in_string = char
        elif char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth = max(0, paren_depth - 1)
        elif char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth = max(0, brace_depth - 1)
        elif char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth = max(0, bracket_depth - 1)
        elif char == "<":
            angle_depth += 1
        elif char == ">":
            angle_depth = max(0, angle_depth - 1)
        elif char == "," and not any((paren_depth, brace_depth, bracket_depth, angle_depth)):
            comma_count += 1
    return comma_count


def resolve_receiver_target(
    java_class: JavaClass,
    receiver: str,
    field_types: dict[str, str],
    class_by_name: dict[str, JavaClass],
) -> JavaClass | None:
    if receiver == "this":
        return java_class
    target_type = field_types.get(receiver)
    if not target_type:
        return None
    return class_by_name.get(target_type)


def clean_class_name(type_name: str) -> str:
    return type_name.replace("final ", "").split("<")[0].split(".")[-1].strip()


def find_method(java_class: JavaClass, method_name: str, arg_count: int | None = None) -> JavaMethod | None:
    candidates = [method for method in java_class.methods if method.name == method_name]
    if arg_count is not None:
        for method in candidates:
            if len(split_params(method.params)) == arg_count:
                return method
    return candidates[0] if candidates else None


def method_key(java_class: JavaClass, method: JavaMethod) -> tuple[str, str, str]:
    return (java_class.name, method.name, method.params)


def classify_call_type(class_name: str) -> str:
    lowered = class_name.lower()
    if "controller" in lowered:
        return "Controller / Facade"
    if "applicationservice" in lowered or lowered.endswith("appservice") or lowered.endswith("service"):
        return "ApplicationService / Service"
    if any(token in lowered for token in ("domainservice", "manager", "validator", "checker", "policy")):
        return "DomainService / Manager / Validator / Checker"
    if any(token in lowered for token in ("repository", "mapper", "dao")):
        return "Repository / Mapper / DAO"
    return UNKNOWN


def dedupe_chain(chain: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict[str, Any]] = []
    for item in chain:
        key = (item["class_name"], item["method_name"], item["evidence"])
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
