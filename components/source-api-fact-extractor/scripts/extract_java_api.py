from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


UNKNOWN = "UNKNOWN"
NO_REQUEST = "NONE"
FRAMEWORK_INJECTED = "N/A"

JAVA_SUFFIXES = {".java", ".xml", ".yml", ".yaml", ".properties"}
IGNORED_SOURCE_PARTS = {
    ".git",
    ".idea",
    ".gradle",
    ".mvn",
    ".agents",
    ".codex",
    ".understand-anything",
    ".windsurf",
    "__pycache__",
    "target",
    "build",
    "dist",
    "node_modules",
    "out",
    "output",
    "outputs",
    "docs",
    "doc",
    "prd",
    "test",
    "tests",
}
HTTP_MAPPING_METHODS = {
    "GetMapping": "GET",
    "PostMapping": "POST",
    "PutMapping": "PUT",
    "DeleteMapping": "DELETE",
    "PatchMapping": "PATCH",
}
ENTRY_ANNOTATIONS = {
    "RestController",
    "Controller",
    "FeignClient",
    "DubboService",
    "RequestMapping",
}
AUTH_TOKENS = (
    "PreAuthorize",
    "Secured",
    "RolesAllowed",
    "RequiresPermissions",
    "RequiresRoles",
    "SaCheck",
    "Permission",
    "Auth",
    "Login",
)
VALIDATION_REQUIRED = {"NotNull", "NotBlank", "NotEmpty"}
FRAMEWORK_INJECTED_TYPES = {
    "BindingResult",
    "Errors",
    "HttpHeaders",
    "HttpServletRequest",
    "HttpServletResponse",
    "Locale",
    "Principal",
    "Authentication",
    "Model",
    "ModelMap",
    "NativeWebRequest",
    "ServletRequest",
    "ServletResponse",
    "UriComponentsBuilder",
    "WebRequest",
}
INVALID_METHOD_RETURN_TOKENS = {
    "return",
    "throw",
    "new",
    "if",
    "for",
    "while",
    "switch",
    "catch",
}


@dataclass
class SourceFile:
    path: Path
    rel_path: str
    text: str


@dataclass
class JavaField:
    name: str
    type: str
    annotations: list[str] = field(default_factory=list)
    default_value: str = UNKNOWN
    line: int = 0


@dataclass
class JavaMethod:
    name: str
    return_type: str
    params: str
    annotations: list[str] = field(default_factory=list)
    body: str = ""
    signature: str = ""
    line: int = 0


@dataclass
class JavaClass:
    name: str
    package: str
    kind: str
    path: str
    declaration: str = UNKNOWN
    annotations: list[str] = field(default_factory=list)
    fields: list[JavaField] = field(default_factory=list)
    methods: list[JavaMethod] = field(default_factory=list)
    enum_values: list[str] = field(default_factory=list)
    table_name: str = UNKNOWN


def discover_source_files(src: str | Path) -> list[SourceFile]:
    root = Path(src).resolve()
    files: list[SourceFile] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in JAVA_SUFFIXES:
            continue
        rel_path = path.relative_to(root)
        if any(part in IGNORED_SOURCE_PARTS for part in rel_path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="ignore")
        files.append(SourceFile(path=path, rel_path=rel_path.as_posix(), text=text))
    return files


def annotation_name(annotation: str) -> str:
    match = re.match(r"@([\w.]+)", annotation.strip())
    if not match:
        return UNKNOWN
    return match.group(1).split(".")[-1]


def has_annotation(annotations: list[str], names: set[str] | tuple[str, ...]) -> bool:
    return any(annotation_name(a) in names for a in annotations)


def extract_annotation_value(annotation: str) -> str:
    match = re.search(r"['\"]([^'\"]*)['\"]", annotation)
    return match.group(1) if match else UNKNOWN


def extract_annotation_attr(annotation: str, attr: str) -> str:
    match = re.search(rf"\b{re.escape(attr)}\s*=\s*['\"]([^'\"]*)['\"]", annotation)
    return match.group(1) if match else UNKNOWN


def collect_annotation(lines: list[str], start_idx: int) -> tuple[str, int]:
    annotation = lines[start_idx].strip()
    balance = annotation.count("(") - annotation.count(")")
    idx = start_idx
    while balance > 0 and idx + 1 < len(lines):
        idx += 1
        part = lines[idx].strip()
        annotation += " " + part
        balance += part.count("(") - part.count(")")
    return annotation, idx


def extract_request_mapping_method(annotation: str) -> str:
    for method in ("GET", "POST", "PUT", "DELETE", "PATCH"):
        if f"RequestMethod.{method}" in annotation or f"method = {method}" in annotation:
            return method
    return UNKNOWN


def normalize_path(*parts: str) -> str:
    clean: list[str] = []
    for part in parts:
        if not part or part == UNKNOWN:
            continue
        clean.append(part.strip("/"))
    if not clean:
        return UNKNOWN
    return "/" + "/".join(p for p in clean if p)


def extract_package(text: str) -> str:
    match = re.search(r"^\s*package\s+([\w.]+)\s*;", text, flags=re.MULTILINE)
    return match.group(1) if match else UNKNOWN


def line_offsets(text: str) -> list[int]:
    offsets = [0]
    for match in re.finditer(r"\n", text):
        offsets.append(match.end())
    return offsets


def offset_to_line(offsets: list[int], offset: int) -> int:
    line = 1
    for idx, start in enumerate(offsets):
        if start > offset:
            break
        line = idx + 1
    return line


def parse_java_files(files: list[SourceFile]) -> dict[str, JavaClass]:
    classes: dict[str, JavaClass] = {}
    for source in files:
        if source.path.suffix != ".java":
            continue
        parsed = parse_java_class(source)
        if parsed:
            classes[parsed.name] = parsed
            if parsed.package != UNKNOWN:
                classes[f"{parsed.package}.{parsed.name}"] = parsed
    return classes


def parse_java_class(source: SourceFile) -> JavaClass | None:
    text = strip_block_comments(source.text)
    package = extract_package(text)
    lines = text.splitlines()
    class_annotations: list[str] = []
    class_line = 0
    kind = UNKNOWN
    class_name = UNKNOWN
    declaration = UNKNOWN

    pending_annotations: list[str] = []
    class_re = re.compile(r"\b(public\s+)?(class|interface|enum)\s+(\w+)")
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()
        if stripped.startswith("@"):
            annotation, end_idx = collect_annotation(lines, idx)
            pending_annotations.append(annotation)
            idx = end_idx + 1
            continue
        match = class_re.search(line)
        if match:
            kind = match.group(2)
            class_name = match.group(3)
            class_annotations = pending_annotations[:]
            class_line = idx + 1
            declaration = collect_declaration(lines, idx)
            break
        if stripped and not stripped.startswith("import") and not stripped.startswith("package"):
            pending_annotations = []
        idx += 1

    if class_name == UNKNOWN:
        return None

    enum_values = parse_enum_values(text, class_name) if kind == "enum" else []
    table_name = UNKNOWN
    for ann in class_annotations:
        if annotation_name(ann) == "TableName":
            table_name = extract_annotation_value(ann)

    return JavaClass(
        name=class_name,
        package=package,
        kind=kind,
        path=source.rel_path,
        declaration=declaration,
        annotations=class_annotations,
        fields=parse_fields(text),
        methods=parse_methods(text),
        enum_values=enum_values,
        table_name=table_name,
    )


def strip_block_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", preserve_comment_lines, text, flags=re.DOTALL)


def preserve_comment_lines(match: re.Match[str]) -> str:
    return "\n" * match.group(0).count("\n")


def collect_declaration(lines: list[str], start_idx: int) -> str:
    declaration = lines[start_idx].strip()
    idx = start_idx
    while "{" not in declaration and ";" not in declaration and idx + 1 < len(lines):
        idx += 1
        declaration += " " + lines[idx].strip()
        if len(declaration) > 2000:
            break
    return declaration


def parse_enum_values(text: str, class_name: str) -> list[str]:
    match = re.search(rf"enum\s+{re.escape(class_name)}\s*\{{(?P<body>.*?)\n\}}", text, flags=re.DOTALL)
    if not match:
        return []
    head = match.group("body").split(";")[0]
    values: list[str] = []
    for chunk in head.split(","):
        value = re.sub(r"\(.*", "", chunk.strip()).strip()
        if re.match(r"^[A-Z][A-Z0-9_]*$", value):
            values.append(value)
    return values


def parse_fields(text: str) -> list[JavaField]:
    fields: list[JavaField] = []
    pending_annotations: list[str] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("@"):
            pending_annotations.append(stripped)
            continue
        field_match = re.match(
            r"\s*(?:private|protected|public)\s+(?:static\s+)?(?:final\s+)?"
            r"(?P<type>[\w.<>, ?\[\]]+)\s+(?P<name>\w+)\s*(?:=\s*(?P<default>[^;]+))?;",
            line,
        )
        if field_match and "(" not in line:
            fields.append(
                JavaField(
                    name=field_match.group("name"),
                    type=field_match.group("type").strip(),
                    annotations=pending_annotations[:],
                    default_value=(field_match.group("default") or UNKNOWN).strip(),
                    line=idx,
                )
            )
            pending_annotations = []
            continue
        if stripped and not stripped.startswith("//"):
            pending_annotations = []
    return fields


def parse_methods(text: str) -> list[JavaMethod]:
    methods: list[JavaMethod] = []
    offsets = line_offsets(text)
    lines = text.splitlines()
    pending_annotations: list[str] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()
        if stripped.startswith("@"):
            annotation, end_idx = collect_annotation(lines, idx)
            pending_annotations.append(annotation)
            idx = end_idx + 1
            continue
        if not stripped or stripped.startswith("}") or stripped.startswith("//"):
            idx += 1
            continue

        signature = stripped
        sig_start_idx = idx
        while signature and not re.search(r"[{;]\s*$", signature) and idx + 1 < len(lines):
            idx += 1
            signature += " " + lines[idx].strip()
            if len(signature) > 2000:
                break

        method_match = re.search(
            r"\b(?:(?:public|protected|private)\s+)?(?:static\s+)?"
            r"(?P<return>[\w.<>, ?\[\]]+?)\s+(?P<name>\w+)\s*\((?P<params>.*)\)"
            r"\s*(?:throws\s+[\w.,\s]+)?\s*[{;]",
            signature,
        )
        if (
            method_match
            and method_match.group("name") not in INVALID_METHOD_RETURN_TOKENS
            and method_match.group("return").strip() not in INVALID_METHOD_RETURN_TOKENS
        ):
            body = ""
            absolute_start = sum(len(l) + 1 for l in lines[:sig_start_idx])
            if "{" in signature:
                body = extract_body_from_offset(text, absolute_start)
            methods.append(
                JavaMethod(
                    name=method_match.group("name"),
                    return_type=method_match.group("return").strip(),
                    params=method_match.group("params").strip(),
                    annotations=pending_annotations[:],
                    body=body,
                    signature=signature,
                    line=offset_to_line(offsets, absolute_start),
                )
            )
            pending_annotations = []
        elif stripped:
            pending_annotations = []
        idx += 1
    return methods


def extract_body_from_offset(text: str, offset: int) -> str:
    start = text.find("{", offset)
    if start == -1:
        return ""
    depth = 0
    for pos in range(start, len(text)):
        char = text[pos]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : pos]
    return text[start + 1 :]


def split_params(params: str) -> list[str]:
    if not params.strip():
        return []
    chunks: list[str] = []
    depth_angle = 0
    depth_paren = 0
    start = 0
    for idx, char in enumerate(params):
        if char == "<":
            depth_angle += 1
        elif char == ">":
            depth_angle = max(0, depth_angle - 1)
        elif char == "(":
            depth_paren += 1
        elif char == ")":
            depth_paren = max(0, depth_paren - 1)
        elif char == "," and depth_angle == 0 and depth_paren == 0:
            chunks.append(params[start:idx].strip())
            start = idx + 1
    chunks.append(params[start:].strip())
    return [c for c in chunks if c]


def parse_param(param: str) -> dict[str, Any]:
    annotations = re.findall(r"@\w+(?:\([^)]*\))?", param)
    cleaned = re.sub(r"@\w+(?:\([^)]*\))?", "", param).replace("final ", "").strip()
    parts = cleaned.split()
    if len(parts) < 2:
        return {"name": UNKNOWN, "type": cleaned or UNKNOWN, "annotations": annotations, "source": UNKNOWN}
    param_type = " ".join(parts[:-1]).strip()
    return {
        "name": parts[-1],
        "type": param_type,
        "annotations": annotations,
        "source": param_source(annotations, param_type),
    }


def param_source(annotations: list[str], param_type: str = UNKNOWN) -> str:
    names = {annotation_name(a) for a in annotations}
    for candidate in ("RequestBody", "PathVariable", "RequestParam", "RequestHeader", "CookieValue"):
        if candidate in names:
            return candidate
    if clean_type(param_type) in FRAMEWORK_INJECTED_TYPES:
        return FRAMEWORK_INJECTED
    return "RPC DTO" if annotations else UNKNOWN


def class_base_path(java_class: JavaClass) -> str:
    for ann in java_class.annotations:
        if annotation_name(ann) == "RequestMapping":
            return extract_annotation_value(ann)
        if annotation_name(ann) == "FeignClient":
            path = extract_annotation_attr(ann, "path")
            if path != UNKNOWN:
                return path
    return ""


def method_mapping(method: JavaMethod) -> tuple[str, str]:
    for ann in method.annotations:
        name = annotation_name(ann)
        if name in HTTP_MAPPING_METHODS:
            return HTTP_MAPPING_METHODS[name], extract_annotation_value(ann)
        if name == "RequestMapping":
            return extract_request_mapping_method(ann), extract_annotation_value(ann)
    return UNKNOWN, UNKNOWN


def method_auth_hint(java_class: JavaClass, method: JavaMethod) -> str:
    annotations = java_class.annotations + method.annotations
    auth_annotations = [a for a in annotations if any(token in annotation_name(a) for token in AUTH_TOKENS)]
    if auth_annotations:
        return "; ".join(auth_annotations)
    if "Authorization" in method.params:
        return "RequestHeader Authorization"
    return UNKNOWN


def infer_module(rel_path: str) -> str:
    parts = Path(rel_path).parts
    for idx, part in enumerate(parts):
        if part == "src" and idx > 0:
            return parts[idx - 1]
    if parts:
        return parts[0]
    return UNKNOWN


def unwrap_response_type(return_type: str) -> tuple[str, str]:
    wrapper_match = re.match(r"(?P<wrapper>\w+)\s*<(?P<body>.*)>", return_type.strip())
    if wrapper_match:
        return wrapper_match.group("wrapper"), wrapper_match.group("body").strip()
    return UNKNOWN, return_type.strip() or UNKNOWN


def clean_type(type_name: str) -> str:
    type_name = type_name.strip()
    generic_match = re.match(r"(?:List|Set|Collection|Optional)\s*<\s*([\w.]+)\s*>", type_name)
    if generic_match:
        return generic_match.group(1).split(".")[-1]
    map_match = re.match(r"Map\s*<.*,\s*([\w.]+)\s*>", type_name)
    if map_match:
        return map_match.group(1).split(".")[-1]
    return type_name.split(".")[-1]


def build_api_inventory(classes: dict[str, JavaClass]) -> list[dict[str, Any]]:
    apis: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for java_class in {id(v): v for v in classes.values()}.values():
        class_ann_names = {annotation_name(a) for a in java_class.annotations}
        class_is_controller = bool(class_ann_names & {"RestController", "Controller"})
        class_is_feign = "FeignClient" in class_ann_names
        class_is_rpc = (
            "DubboService" in class_ann_names
            or class_is_feign
            or (java_class.kind == "interface" and java_class.name.endswith(("Api", "Facade", "Rpc")))
        )
        base_path = class_base_path(java_class)

        for method in java_class.methods:
            http_method, method_path = method_mapping(method)
            is_http = http_method != UNKNOWN or class_is_controller or class_is_feign
            if not is_http and not class_is_rpc:
                continue
            if http_method == UNKNOWN and not class_is_rpc:
                continue

            full_path = normalize_path(base_path, method_path)
            params = [parse_param(p) for p in split_params(method.params)]
            request_types = [p["type"] for p in params if p["source"] in {"RequestBody", "RPC DTO"}]
            if not params:
                request_types = [NO_REQUEST]
            elif not request_types:
                request_types = [p["type"] for p in params if p["source"] != FRAMEWORK_INJECTED] or [NO_REQUEST]
            wrapper, body_type = unwrap_response_type(method.return_type)
            entry_type = entry_type_for(java_class, full_path, class_is_feign, class_is_rpc)
            module = infer_module(java_class.path)
            api_id = stable_api_id(module, java_class.name, method.name, http_method, full_path)
            key = f"{java_class.path}:{method.name}:{full_path}:{http_method}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            apis.append(
                {
                    "api_id": api_id,
                    "module": module,
                    "entry_type": entry_type,
                    "class_name": java_class.name,
                    "method_name": method.name,
                    "http_method": http_method,
                    "path": full_path,
                    "rpc_interface": java_class.name if class_is_rpc and not class_is_controller else UNKNOWN,
                    "request_type": ", ".join(request_types),
                    "response_type": method.return_type or UNKNOWN,
                    "response_wrapper": wrapper,
                    "response_body_type": body_type,
                    "auth_hint": method_auth_hint(java_class, method),
                    "source_path": java_class.path,
                    "source_evidence": evidence(java_class.path, java_class.name, method.name, method.line),
                    "params": params,
                }
            )
    return sorted(apis, key=lambda a: (a["module"], a["path"], a["class_name"], a["method_name"]))


def entry_type_for(java_class: JavaClass, path: str, class_is_feign: bool, class_is_rpc: bool) -> str:
    if class_is_feign:
        return "Feign Client"
    if path.startswith("/internal/") or "/internal/" in path:
        return "Internal"
    if class_is_rpc and java_class.kind == "interface":
        return "RPC Facade"
    if has_annotation(java_class.annotations, {"RestController", "Controller"}):
        return "HTTP Controller"
    return "RPC Facade" if class_is_rpc else UNKNOWN


def stable_api_id(module: str, class_name: str, method_name: str, http_method: str, path: str) -> str:
    raw = f"{module}:{class_name}.{method_name}:{http_method}:{path}"
    return re.sub(r"[^A-Za-z0-9_.:/-]+", "-", raw)


def evidence(path: str, class_name: str, method_name: str = UNKNOWN, line: int = 0) -> str:
    suffix = f":{line}" if line else ""
    return f"{path}{suffix} | {class_name}.{method_name}"


def field_to_contract(field_item: JavaField, classes: dict[str, JavaClass], owner: JavaClass) -> dict[str, Any]:
    ann_names = [annotation_name(a) for a in field_item.annotations]
    clean = clean_type(field_item.type)
    enum_values = classes.get(clean).enum_values if clean in classes and classes[clean].kind == "enum" else []
    nested_object = "YES" if clean in classes and classes[clean].kind == "class" and not enum_values else "NO"
    collection_type = UNKNOWN
    collection_match = re.match(r"(\w+)\s*<", field_item.type)
    if collection_match:
        collection_type = collection_match.group(1)
    return {
        "field_name": field_item.name,
        "field_type": field_item.type,
        "required": "YES" if any(a in VALIDATION_REQUIRED for a in ann_names) else UNKNOWN,
        "default_value": field_item.default_value,
        "validation_annotation": ", ".join(field_item.annotations) if field_item.annotations else UNKNOWN,
        "enum_values": enum_values or UNKNOWN,
        "nested_object": nested_object,
        "collection_type": collection_type,
        "evidence": evidence(owner.path, owner.name, field_item.name, field_item.line),
    }
