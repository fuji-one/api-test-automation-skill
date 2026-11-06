#!/usr/bin/env python3
"""校验运行时取证补值阶段产物。"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


REQUIRED_FILES = (
    "runtime_stage_status.yaml",
    "runtime_evidence.yaml",
    "runtime_value_catalog.yaml",
)
STATUS_VALUES = {"passed", "partial", "blocked", "failed"}
SOURCE_STATUS_VALUES = {"confirmed", "missing", "conflict", "blocked"}
QUEUE_STATE_VALUES = {"pending", "requested", "evidenced", "retryable", "skipped_recoverable", "blocked_final", "excluded"}
STAGE_STATUS_KEYS = (
    "schema_version",
    "stage",
    "status",
    "next_stage_allowed",
    "request_scope",
    "input_paths",
    "output_paths",
    "gate_checks",
    "blocking_issues",
)
EVIDENCE_KEYS = (
    "schema_version",
    "stage",
    "status",
    "next_stage_allowed",
    "request_scope",
    "auth_evidence",
    "evidence_items",
    "conflict_items",
    "blocking_issues",
)
CATALOG_KEYS = (
    "schema_version",
    "stage",
    "status",
    "values",
    "usable_fact_types",
    "missing_values",
    "conflict_values",
    "blocking_issues",
)
YAML_SCALAR_RE = re.compile(r"^\s*(?:-\s*)?([A-Za-z0-9_]+)\s*:\s*(.*?)\s*$")
YAML_TOP_LEVEL_SCALAR_RE = re.compile(r"^([A-Za-z0-9_]+)\s*:\s*(.*?)\s*$")
YAML_TOP_LEVEL_KEY_RE = re.compile(r"^([A-Za-z0-9_]+)\s*:", re.MULTILINE)


def read_text(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path.name} 不是 UTF-8 编码：{exc}") from exc
    if "\ufffd" in text:
        raise ValueError(f"{path.name} 存在疑似中文乱码字符")
    if not text.strip():
        raise ValueError(f"{path.name} 内容为空")
    return text


def require(condition: bool, errors: list[str], message: str) -> None:
    if not condition:
        errors.append(message)


def yaml_top_level_keys(text: str) -> set[str]:
    return set(YAML_TOP_LEVEL_KEY_RE.findall(text))


def yaml_scalar_values(text: str, key: str) -> list[str]:
    values: list[str] = []
    for line in text.splitlines():
        match = YAML_TOP_LEVEL_SCALAR_RE.match(line)
        if match and match.group(1) == key:
            values.append(match.group(2).strip().strip("\"'"))
    return values


def first_yaml_scalar(text: str, key: str) -> str | None:
    values = yaml_scalar_values(text, key)
    return values[0] if values else None


def yaml_int_value(text: str, key: str, errors: list[str], label: str) -> int | None:
    values = yaml_scalar_values(text, key)
    parsed = [int(value) for value in values if re.fullmatch(r"\d+", value)]
    if not parsed:
        errors.append(f"{label} 缺少可解析的整数字段：{key}")
        return None
    if len(set(parsed)) != 1:
        errors.append(f"{label} 字段 {key} 多处取值不一致：{parsed}")
        return None
    return parsed[0]


def is_yaml_true(value: str | None) -> bool:
    return (value or "").strip().lower() in {"true", "yes", "1", "是", "passed"}


def require_top_level_keys(text: str, keys: tuple[str, ...], errors: list[str], label: str) -> None:
    present = yaml_top_level_keys(text)
    for key in keys:
        if key not in present:
            errors.append(f"{label} 缺少 schema 顶层字段：{key}")


def require_empty_list(text: str, key: str, errors: list[str], label: str) -> None:
    values = yaml_scalar_values(text, key)
    if not values:
        errors.append(f"{label} 缺少空列表字段：{key}")
        return
    if values[0] != "[]":
        errors.append(f"{label} 列表未清空：{key}={values[0]}")


def yaml_section(text: str, key: str) -> str:
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if re.match(rf"^{re.escape(key)}\s*:\s*$", line):
            start = index + 1
            break
    if start is None:
        return ""
    end = len(lines)
    for index in range(start, len(lines)):
        if re.match(r"^[A-Za-z0-9_]+\s*:", lines[index]):
            end = index
            break
    return "\n".join(lines[start:end])


def extract_sequence_blocks(text: str, section_key: str, first_key: str) -> list[str]:
    section = yaml_section(text, section_key)
    starts = list(re.finditer(rf"(?m)^\s*-\s+{re.escape(first_key)}\s*:", section))
    blocks: list[str] = []
    for index, start in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(section)
        blocks.append(section[start.start():end])
    return blocks


def block_first_scalar(block: str, key: str) -> str | None:
    for line in block.splitlines():
        match = YAML_SCALAR_RE.match(line)
        if match and match.group(1) == key:
            return match.group(2).strip().strip("\"'")
    return None


def block_has_key(block: str, key: str) -> bool:
    return re.search(rf"(?m)^\s*(?:-\s*)?{re.escape(key)}\s*:", block) is not None


def block_has_any_key(block: str, keys: tuple[str, ...]) -> bool:
    return any(block_has_key(block, key) for key in keys)


def block_scalar_present(block: str, key: str) -> bool:
    value = block_first_scalar(block, key)
    if value is None:
        return False
    normalized = value.strip().strip("\"'").lower()
    return normalized not in {"", "null", "none", "~"}


def block_has_any_scalar(block: str, keys: tuple[str, ...]) -> bool:
    return any(block_scalar_present(block, key) for key in keys)


def require_materialization_field(
    block: str,
    evidence_id: str,
    field_label: str,
    keys: tuple[str, ...],
    errors: list[str],
    require_non_empty_scalar: bool = False,
) -> None:
    if require_non_empty_scalar:
        has_field = block_has_any_scalar(block, keys)
    else:
        has_field = block_has_any_key(block, keys)
    if not has_field:
        errors.append(f"runtime_evidence.yaml {evidence_id} 缺少可脚本化 evidence 字段：{field_label}")


def validate_script_materialization_contract(block: str, evidence_id: str, errors: list[str]) -> None:
    required_groups = (
        ("case_id_or_flow_id", ("case_id", "flow_id"), True),
        ("step_id_or_step_order", ("step_id", "step_order"), True),
        ("module", ("module",), True),
        ("method", ("method",), True),
        ("path", ("path",), True),
        ("base_url_alias", ("base_url_alias",), True),
        ("session_role", ("session_role",), True),
        ("auth_policy", ("auth_policy",), True),
        ("token_injection_location", ("token_injection_location", "token_injection"), True),
        ("request_plaintext", ("request_plaintext", "request_plaintext_ref"), False),
        ("response_plaintext", ("response_plaintext", "response_plaintext_ref"), False),
        ("assertion_candidates", ("assertion_candidates", "assertions_ref"), False),
        ("setup_data", ("setup_data", "setup"), False),
        ("cleanup", ("cleanup", "cleanup_data"), False),
        ("assertion_strength", ("assertion_strength",), True),
        ("result_observation_mode", ("result_observation_mode",), True),
        ("script_materialization_ready", ("script_materialization_ready",), True),
        ("missing_materialization_items", ("missing_materialization_items",), False),
    )
    for field_label, keys, require_non_empty_scalar in required_groups:
        require_materialization_field(block, evidence_id, field_label, keys, errors, require_non_empty_scalar)

    ready = is_yaml_true(block_first_scalar(block, "script_materialization_ready"))
    missing_items = block_first_scalar(block, "missing_materialization_items")
    if ready and missing_items not in {"[]", None}:
        errors.append(f"runtime_evidence.yaml {evidence_id} missing_materialization_items 未清空：{missing_items}")


def validate_continuation_queue(text: str, errors: list[str], label: str) -> None:
    queue_section = yaml_section(text, "continuation_queue")
    if not queue_section:
        return
    if re.search(r"(?m)^\s+status\s*:", queue_section):
        errors.append(f"{label} continuation_queue 内禁止使用 status 字段，请使用 queue_state")
    state_values = re.findall(r"(?m)^\s+queue_state\s*:\s*([^\n#]+)", queue_section)
    for raw_value in state_values:
        value = raw_value.strip().strip("\"'")
        if value not in QUEUE_STATE_VALUES:
            errors.append(f"{label} continuation_queue.queue_state 非法：{value}")


def validate_runtime_queue_file(text: str, errors: list[str]) -> None:
    require_top_level_keys(text, ("schema_version", "stage", "status", "queue_state_field", "items"), errors, "runtime_evidence_queue.yaml")
    schema_version = yaml_int_value(text, "schema_version", errors, "runtime_evidence_queue.yaml")
    if schema_version is not None and schema_version != 1:
        errors.append("runtime_evidence_queue.yaml schema_version 必须为 1")
    if first_yaml_scalar(text, "stage") != "runtime_evidence_continuation_queue":
        errors.append(f"runtime_evidence_queue.yaml stage 必须为 runtime_evidence_continuation_queue：{first_yaml_scalar(text, 'stage')}")
    if first_yaml_scalar(text, "status") not in STATUS_VALUES:
        errors.append(f"runtime_evidence_queue.yaml status 非法或缺失：{first_yaml_scalar(text, 'status')}")
    if first_yaml_scalar(text, "queue_state_field") != "queue_state":
        errors.append("runtime_evidence_queue.yaml queue_state_field 必须为 queue_state")
    if re.search(r"(?m)^\s+status\s*:", yaml_section(text, "items")):
        errors.append("runtime_evidence_queue.yaml items 内禁止使用 status 字段，请使用 queue_state")
    for raw_value in re.findall(r"(?m)^\s+queue_state\s*:\s*([^\n#]+)", yaml_section(text, "items")):
        value = raw_value.strip().strip("\"'")
        if value not in QUEUE_STATE_VALUES:
            errors.append(f"runtime_evidence_queue.yaml queue_state 非法：{value}")


def secret_value_is_redacted(value: str | None) -> bool:
    normalized = (value or "").strip().strip("\"'")
    if not normalized:
        return True
    lowered = normalized.lower()
    if lowered in {"redacted", "<redacted>", "***", "******", "已脱敏", "脱敏", "masked", "none", "null"}:
        return True
    if normalized.startswith("${") and normalized.endswith("}"):
        return True
    if normalized.startswith("$."):
        return True
    return False


def validate_no_plain_secrets(text: str, errors: list[str], label: str) -> None:
    secret_key_pattern = re.compile(
        r"(?im)^\s*(?:-\s*)?(password|passwd|pwd|authorization|cookie|set_cookie|access_token|refresh_token|token)\s*:\s*(.+?)\s*$"
    )
    for match in secret_key_pattern.finditer(text):
        key, value = match.group(1), match.group(2).strip()
        if not secret_value_is_redacted(value):
            errors.append(f"{label} 存在未脱敏敏感字段：{key}")
    for pattern_name, pattern in (
        ("Authorization", re.compile(r"(?i)\bAuthorization\s*[:=]\s*(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{8,}")),
        ("Cookie", re.compile(r"(?i)\bCookie\s*[:=]\s*[^,\n;=]+=[^,\n;]{4,}")),
        ("password", re.compile(r"(?i)\bpassword\s*[:=]\s*(?!\$\{|\*{3,}|<redacted>|redacted)[^\s,\n]{4,}")),
    ):
        if pattern.search(text):
            errors.append(f"{label} 存在疑似未脱敏 {pattern_name} 明文")


def validate_common(text: str, keys: tuple[str, ...], label: str, errors: list[str]) -> str | None:
    require_top_level_keys(text, keys, errors, label)
    schema_version = yaml_int_value(text, "schema_version", errors, label)
    if schema_version is not None and schema_version != 1:
        errors.append(f"{label} schema_version 必须为 1")
    status = first_yaml_scalar(text, "status")
    if status not in STATUS_VALUES:
        errors.append(f"{label} status 非法或缺失：{status}")
    validate_no_plain_secrets(text, errors, label)
    return status


def validate_stage_status(text: str, errors: list[str], require_usable: bool) -> None:
    status = validate_common(text, STAGE_STATUS_KEYS, "runtime_stage_status.yaml", errors)
    validate_continuation_queue(text, errors, "runtime_stage_status.yaml")
    stage = first_yaml_scalar(text, "stage")
    if stage != "runtime_live_evidence":
        errors.append(f"runtime_stage_status.yaml stage 必须为 runtime_live_evidence：{stage}")
    if require_usable and status not in {"passed", "partial"}:
        errors.append(f"runtime_stage_status.yaml 被引用时 status 必须为 passed 或 partial：{status}")
    if status == "passed" or require_usable:
        require(is_yaml_true(first_yaml_scalar(text, "next_stage_allowed")), errors, "runtime_stage_status.yaml next_stage_allowed 必须为 true")
        require_empty_list(text, "blocking_issues", errors, "runtime_stage_status.yaml")


def validate_evidence(text: str, errors: list[str], require_usable: bool) -> set[str]:
    status = validate_common(text, EVIDENCE_KEYS, "runtime_evidence.yaml", errors)
    stage = first_yaml_scalar(text, "stage")
    if stage != "runtime_live_evidence":
        errors.append(f"runtime_evidence.yaml stage 必须为 runtime_live_evidence：{stage}")
    if require_usable and status not in {"passed", "partial"}:
        errors.append(f"runtime_evidence.yaml 被引用时 status 必须为 passed 或 partial：{status}")
    if status in {"passed", "partial"} or require_usable:
        require_empty_list(text, "conflict_items", errors, "runtime_evidence.yaml")
    if status == "passed":
        require_empty_list(text, "blocking_issues", errors, "runtime_evidence.yaml")

    confirmed_ids: set[str] = set()
    blocks = extract_sequence_blocks(text, "evidence_items", "evidence_id")
    if status == "passed" and not blocks:
        errors.append("runtime_evidence.yaml passed 状态下 evidence_items 不能为空")
    for block in blocks:
        evidence_id = block_first_scalar(block, "evidence_id") or "UNKNOWN"
        source_status = block_first_scalar(block, "source_status")
        if source_status not in SOURCE_STATUS_VALUES:
            errors.append(f"runtime_evidence.yaml {evidence_id} source_status 非法：{source_status}")
        usable = is_yaml_true(block_first_scalar(block, "usable_for_execution_case"))
        if usable and source_status != "confirmed":
            errors.append(f"runtime_evidence.yaml {evidence_id} 可用于执行级用例时必须为 confirmed")
        if block_has_key(block, "script_materialization_ready"):
            validate_script_materialization_contract(block, evidence_id, errors)
        if block_first_scalar(block, "value_type") == "token":
            redacted = is_yaml_true(block_first_scalar(block, "redacted"))
            field_value = block_first_scalar(block, "field_value")
            if not redacted or not secret_value_is_redacted(field_value):
                errors.append(f"runtime_evidence.yaml {evidence_id} token 证据必须脱敏")
        if usable and source_status == "confirmed":
            confirmed_ids.add(evidence_id)
    return confirmed_ids


def validate_catalog(text: str, errors: list[str], require_usable: bool) -> set[str]:
    status = validate_common(text, CATALOG_KEYS, "runtime_value_catalog.yaml", errors)
    stage = first_yaml_scalar(text, "stage")
    if stage != "runtime_value_catalog":
        errors.append(f"runtime_value_catalog.yaml stage 必须为 runtime_value_catalog：{stage}")
    if require_usable and status not in {"passed", "partial"}:
        errors.append(f"runtime_value_catalog.yaml 被引用时 status 必须为 passed 或 partial：{status}")
    if status in {"passed", "partial"} or require_usable:
        require_empty_list(text, "conflict_values", errors, "runtime_value_catalog.yaml")
    if status == "passed":
        require_empty_list(text, "blocking_issues", errors, "runtime_value_catalog.yaml")

    confirmed_ids: set[str] = set()
    blocks = extract_sequence_blocks(text, "values", "value_id")
    if status == "passed" and not blocks:
        errors.append("runtime_value_catalog.yaml passed 状态下 values 不能为空")
    for block in blocks:
        value_id = block_first_scalar(block, "value_id") or "UNKNOWN"
        source_status = block_first_scalar(block, "source_status")
        if source_status not in SOURCE_STATUS_VALUES:
            errors.append(f"runtime_value_catalog.yaml {value_id} source_status 非法：{source_status}")
        if block_first_scalar(block, "value_type") == "token" and not secret_value_is_redacted(block_first_scalar(block, "value")):
            errors.append(f"runtime_value_catalog.yaml {value_id} 不得写入明文 token")
        if source_status == "confirmed":
            confirmed_ids.add(value_id)
    return confirmed_ids


def validate_runtime_dir(path: Path, require_usable: bool) -> list[str]:
    errors: list[str] = []
    evidence_dir = path / "04-runtime-evidence" if (path / "04-runtime-evidence").is_dir() else path
    require(evidence_dir.is_dir(), errors, f"运行时取证路径不是目录：{evidence_dir}")
    if errors:
        return errors
    for filename in REQUIRED_FILES:
        require((evidence_dir / filename).is_file(), errors, f"缺少运行时取证文件：{filename}")
    if errors:
        return errors

    try:
        stage_status_text = read_text(evidence_dir / "runtime_stage_status.yaml")
        evidence_text = read_text(evidence_dir / "runtime_evidence.yaml")
        catalog_text = read_text(evidence_dir / "runtime_value_catalog.yaml")
        queue_text = read_text(evidence_dir / "runtime_evidence_queue.yaml") if (evidence_dir / "runtime_evidence_queue.yaml").is_file() else ""
    except ValueError as exc:
        return [str(exc)]
    validate_stage_status(stage_status_text, errors, require_usable)
    validate_evidence(evidence_text, errors, require_usable)
    validate_catalog(catalog_text, errors, require_usable)
    if queue_text:
        validate_runtime_queue_file(queue_text, errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="校验运行时取证补值阶段产物")
    parser.add_argument("path", help="04-runtime-evidence 目录，或包含该目录的流水线根目录")
    parser.add_argument("--require-usable", action="store_true", help="要求证据可供执行级用例引用")
    args = parser.parse_args()

    errors = validate_runtime_dir(Path(args.path), args.require_usable)
    if errors:
        print("校验结果：不通过")
        for index, error in enumerate(errors, start=1):
            print(f"{index}. {error}")
        return 1
    print("校验结果：通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
