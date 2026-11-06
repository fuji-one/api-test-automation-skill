"""按生成合同加载专用执行器，并统一校验结构化执行结果。"""

from __future__ import annotations

import importlib
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = PROJECT_ROOT / "configs" / "specialized_runner_materialization.yaml"


def resolve_specialized_runner_id(definition: Dict[str, Any]) -> str:
    """优先读取新合同字段，并兼容既有 custom_runner 数据。"""

    return str(
        definition.get("specialized_runner_id") or definition.get("custom_runner") or ""
    ).strip()


def run_specialized_runner(
    definition: Dict[str, Any],
    client: Any,
    env_config: Dict[str, Any],
    runtime_context: Dict[str, Any],
    auth_contexts: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """通过统一适配入口执行专用逻辑，避免 pytest 主入口积累业务分支。"""

    runner_id = resolve_specialized_runner_id(definition)
    if not runner_id:
        raise ValueError("专用执行器 ID 不能为空")
    runner = _runner_index().get(runner_id)
    if runner is None:
        raise ValueError(f"专用执行器未在物化清单中声明：{runner_id}")

    adapter = runner.get("adapter") or {}
    module_name = str(adapter.get("module") or "").strip()
    callable_name = str(adapter.get("callable") or "").strip()
    if not module_name.startswith("core.") or not callable_name.isidentifier():
        raise ValueError(f"专用执行器适配入口非法：{runner_id}")

    module = importlib.import_module(module_name)
    entrypoint = getattr(module, callable_name, None)
    if not callable(entrypoint):
        raise ValueError(f"专用执行器入口不可调用：{module_name}.{callable_name}")

    result = entrypoint(
        definition=definition,
        client=client,
        env_config=env_config,
        runtime_context=runtime_context,
        auth_contexts=auth_contexts,
    )
    if not isinstance(result, dict):
        raise TypeError(f"专用执行器必须返回字典：{runner_id}")
    _assert_result(
        result,
        definition.get("specialized_runner_assertions")
        or definition.get("custom_runner_assertions")
        or {},
    )
    return result


@lru_cache(maxsize=1)
def _runner_index() -> Dict[str, Dict[str, Any]]:
    if not MANIFEST_PATH.is_file():
        raise FileNotFoundError(f"缺少专用执行器物化清单：{MANIFEST_PATH}")
    payload = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8")) or {}
    if payload.get("schema_version") != 1 or payload.get("status") != "passed":
        raise ValueError("专用执行器物化清单未通过")

    runners = payload.get("runners")
    if not isinstance(runners, list):
        raise TypeError("专用执行器物化清单 runners 必须是列表")
    index: Dict[str, Dict[str, Any]] = {}
    for item in runners:
        if not isinstance(item, dict):
            raise TypeError("专用执行器物化清单条目必须是对象")
        runner_id = str(item.get("runner_id") or "").strip()
        if not runner_id or runner_id in index:
            raise ValueError(f"专用执行器 ID 缺失或重复：{runner_id}")
        index[runner_id] = item
    return index


def _assert_result(result: Dict[str, Any], assertions: Dict[str, Any]) -> None:
    if not isinstance(assertions, dict):
        raise TypeError("specialized_runner_assertions 必须是对象")
    equals = assertions.get("equals") or {}
    if not isinstance(equals, dict):
        raise TypeError("specialized_runner_assertions.equals 必须是对象")
    for path, expected in equals.items():
        actual = _resolve_path(result, str(path))
        assert actual == expected, f"专用执行器结果不符合预期：{path}，实际 {actual!r}，期望 {expected!r}"

    for path in _string_list(assertions.get("true_fields"), "true_fields"):
        actual = _resolve_path(result, path)
        assert actual is True, f"专用执行器结果字段应为 true：{path}，实际 {actual!r}"
    for path in _string_list(assertions.get("required_fields"), "required_fields"):
        _resolve_path(result, path)
    for path in _string_list(assertions.get("all_true_fields"), "all_true_fields"):
        actual = _resolve_path(result, path)
        if isinstance(actual, dict):
            values = list(actual.values())
        elif isinstance(actual, (list, tuple, set)):
            values = list(actual)
        else:
            raise TypeError(f"all_true_fields 目标必须是集合或对象：{path}")
        assert all(value is True for value in values), f"专用执行器结果未全部为 true：{path}"


def _string_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise TypeError(f"specialized_runner_assertions.{field} 必须是非空字符串列表")
    return [item.strip() for item in value]


def _resolve_path(payload: Dict[str, Any], path: str) -> Any:
    normalized = path.strip()
    if normalized.startswith("$."):
        normalized = normalized[2:]
    if not normalized:
        raise ValueError("专用执行器结果路径不能为空")
    current: Any = payload
    for part in normalized.split("."):
        if not isinstance(current, dict) or part not in current:
            raise AssertionError(f"专用执行器结果缺少字段：{path}")
        current = current[part]
    return current
