# 运行时上下文工具，统一处理变量发布、别名和占位符解析。
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any, Dict, Optional


PLACEHOLDER_PATTERN = re.compile(r"\$\{([A-Za-z0-9_.]+)\}")


def prepare_case_runtime_context(
    runtime_context: Dict[str, Any],
    env_config: Dict[str, Any],
    case_id: str,
    current_time: Optional[datetime] = None,
) -> None:
    """隔离当前用例或长链路的业务变量，同时保留账号组会话上下文。"""

    normalized_case_id = str(case_id or "").strip()
    if not normalized_case_id:
        raise ValueError("case_id 不能为空")
    if runtime_context.get("_active_case_id") == normalized_case_id:
        return

    role_names = set((env_config.get("auth_roles") or {}).keys())
    persistent_keys = {
        "auth_role_configs",
        "auth_roles",
        "case_account_logged_roles",
        "case_account_login_records",
    }
    persistent_keys.update(f"{role}_context" for role in role_names)
    persistent_keys.update(f"{role}_user_id" for role in role_names)
    persistent_values = {
        key: value
        for key, value in runtime_context.items()
        if key in persistent_keys
    }

    runtime_context.clear()
    runtime_context.update(persistent_values)
    case_time = current_time or datetime.now()
    runtime_context["nowIso"] = case_time.strftime("%Y%m%d%H%M%S")
    publish_runtime_value(runtime_context, "epochMillis", int(case_time.timestamp() * 1000))
    publish_runtime_value(
        runtime_context,
        "taskWindowStart",
        (case_time - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
    )
    publish_runtime_value(
        runtime_context,
        "taskWindowEnd",
        (case_time + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
    )
    runtime_context["caseId"] = normalized_case_id
    runtime_context["current_case_id"] = normalized_case_id
    runtime_context["_active_case_id"] = normalized_case_id
    publish_runtime_variables(runtime_context, env_config)


def publish_runtime_variables(runtime_context: Dict[str, Any], env_config: Optional[Dict[str, Any]] = None) -> None:
    now_iso = str(runtime_context.get("nowIso") or "")
    if now_iso:
        publish_runtime_value(runtime_context, "run_marker", f"rt-framework-{now_iso}", overwrite=False)
        publish_runtime_value(runtime_context, "task_time_marker", f"rt-framework-task-time-{now_iso}", overwrite=False)

    variables = (env_config or {}).get("runtime_variables") or {}
    for name, value in variables.items():
        publish_runtime_value(runtime_context, name, value, overwrite=False)
    _apply_runtime_identifier_limits(runtime_context, env_config)


def _apply_runtime_identifier_limits(
    runtime_context: Dict[str, Any],
    env_config: Optional[Dict[str, Any]],
) -> None:
    limits = (env_config or {}).get("runtime_identifier_limits") or {}
    if not isinstance(limits, dict):
        raise TypeError("runtime_identifier_limits 必须是字段名到最大长度的对象")
    for name, raw_limit in limits.items():
        if name not in runtime_context:
            continue
        max_length = int(raw_limit)
        if max_length < 17:
            raise ValueError(f"运行标识长度上限过小：{name}={max_length}")
        resolved = str(resolve_runtime_value(runtime_context[name], runtime_context, env_config))
        if len(resolved) <= max_length:
            publish_runtime_value(runtime_context, name, resolved)
            continue
        digest = sha256(resolved.encode("utf-8")).hexdigest()[:12]
        prefix_length = max_length - len(digest) - 1
        publish_runtime_value(runtime_context, name, f"{resolved[:prefix_length]}-{digest}")


def publish_runtime_value(runtime_context: Dict[str, Any], name: str, value: Any, overwrite: bool = True) -> None:
    if overwrite or name not in runtime_context:
        runtime_context[name] = value
    snake_name = to_snake_case(name)
    if snake_name != name and (overwrite or snake_name not in runtime_context):
        runtime_context[snake_name] = value
    camel_name = to_lower_camel_case(snake_name)
    if camel_name != name and (overwrite or camel_name not in runtime_context):
        runtime_context[camel_name] = value


def resolve_runtime_value(value: Any, runtime_context: Dict[str, Any], env_config: Optional[Dict[str, Any]] = None) -> Any:
    if isinstance(value, dict):
        return {key: resolve_runtime_value(item, runtime_context, env_config) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_runtime_value(item, runtime_context, env_config) for item in value]
    if not isinstance(value, str):
        return value

    full_match = PLACEHOLDER_PATTERN.fullmatch(value)
    if full_match:
        resolved = resolve_reference(full_match.group(1), runtime_context, env_config)
        if isinstance(resolved, str) and PLACEHOLDER_PATTERN.search(resolved):
            return resolve_runtime_value(resolved, runtime_context, env_config)
        return resolved

    resolved_text = value
    for _ in range(10):
        next_text = PLACEHOLDER_PATTERN.sub(
            lambda match: str(resolve_reference(match.group(1), runtime_context, env_config)),
            resolved_text,
        )
        if next_text == resolved_text or not PLACEHOLDER_PATTERN.search(next_text):
            return next_text
        resolved_text = next_text
    if PLACEHOLDER_PATTERN.search(resolved_text):
        raise ValueError(f"运行变量递归解析超过限制：{value}")
    return resolved_text


def resolve_reference(name: str, runtime_context: Dict[str, Any], env_config: Optional[Dict[str, Any]] = None) -> Any:
    if name.startswith("env."):
        env_name = name.split(".", 1)[1]
        if env_name not in os.environ:
            raise ValueError(f"环境变量未设置：{env_name}")
        return os.environ[env_name]

    if name.startswith("runtime_context."):
        return get_runtime_value(runtime_context, name.split(".", 1)[1])

    if name in runtime_context:
        return runtime_context[name]

    if "." in name:
        return get_runtime_value(runtime_context, name)

    variables = (env_config or {}).get("runtime_variables") or {}
    if name in variables:
        return variables[name]

    snake_name = to_snake_case(name)
    if snake_name in runtime_context:
        return runtime_context[snake_name]
    if snake_name in variables:
        return variables[snake_name]

    raise ValueError(f"运行变量未解析：{name}")


def get_runtime_value(runtime_context: Dict[str, Any], dotted_name: str) -> Any:
    current: Any = runtime_context
    for part in dotted_name.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        raise ValueError(f"运行变量未解析：{dotted_name}")
    return current


def to_snake_case(name: str) -> str:
    first_pass = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", first_pass).lower()


def to_lower_camel_case(name: str) -> str:
    parts = name.split("_")
    if not parts:
        return name
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])
