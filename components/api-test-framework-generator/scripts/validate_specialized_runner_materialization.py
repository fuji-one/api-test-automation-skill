#!/usr/bin/env python3
"""校验专用执行器的来源、消费者、适配入口和冷启动语义一致性。"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml


MANIFEST_PATH = Path("configs/specialized_runner_materialization.yaml")
STATUS_PATH = Path("configs/generation_status.yaml")
REQUIRED_INPUTS = {
    "definition",
    "client",
    "env_config",
    "runtime_context",
    "auth_contexts",
}
REQUIRED_CONTRACT_LISTS = (
    "inputs",
    "ordered_actions",
    "result_fields",
    "assertion_obligations",
    "cleanup_guarantees",
    "failure_path_guarantees",
)
GENERATED_PREFIXES = {
    "api",
    "configs",
    "core",
    "data",
    "reports",
    "scripts",
    "testcases",
}
GENERATED_DOCUMENTS = {"接口案例.md", "自动化运行配置.md", "缺陷列表.md"}


def _read_yaml(path: Path, errors: list[str], label: str) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        errors.append(f"{label} 读取或 YAML 解析失败：{exc}")
        return None


def _python_records(path: Path, export_name: str, errors: list[str]) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        errors.append(f"{path.name} 读取或 Python 解析失败：{exc}")
        return []
    value: Any = None
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == export_name for target in targets):
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, TypeError) as exc:
            errors.append(f"{path.name} 的 {export_name} 不是可静态读取的常量：{exc}")
            return []
    if value is None:
        return []
    if not isinstance(value, list):
        errors.append(f"{path.name} 的 {export_name} 必须是列表")
        return []
    return [item for item in value if isinstance(item, dict)]


def _records(paths: list[Path], yaml_key: str, python_export: str, errors: list[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in paths:
        if path.suffix == ".py":
            items.extend(_python_records(path, python_export, errors))
            continue
        payload = _read_yaml(path, errors, str(path))
        values = payload.get(yaml_key) if isinstance(payload, dict) else None
        if values is None:
            continue
        if not isinstance(values, list):
            errors.append(f"{path.name} 的 {yaml_key} 必须是列表")
            continue
        items.extend(item for item in values if isinstance(item, dict))
    return items


def _runner_id(item: dict[str, Any]) -> str:
    return str(item.get("specialized_runner_id") or item.get("custom_runner") or "").strip()


def _discover(framework: Path, errors: list[str]) -> dict[str, dict[str, set[str]]]:
    case_dir = framework / "data" / "cases"
    case_paths = sorted([*case_dir.glob("*.yaml"), *case_dir.glob("*.yml"), *case_dir.glob("*.py")])
    flow_paths = [
        path
        for path in (
            framework / "data" / "flow_cases.yaml",
            framework / "data" / "flow_cases.yml",
            framework / "data" / "flow_cases.py",
        )
        if path.is_file()
    ]
    discovered: dict[str, dict[str, set[str]]] = {}
    for item in _records(case_paths, "cases", "CASES", errors):
        runner_id = _runner_id(item)
        if not runner_id:
            continue
        case_id = str(item.get("case_id") or "").strip()
        if not case_id:
            errors.append(f"专用执行器 {runner_id} 的普通用例缺少 case_id")
            continue
        discovered.setdefault(runner_id, {"case_ids": set(), "flow_ids": set()})["case_ids"].add(case_id)

    for item in _records(flow_paths, "flows", "FLOWS", errors):
        runner_id = _runner_id(item)
        dedicated = bool(item.get("runner_ref")) or "dedicated" in str(item.get("execution_mode") or "").lower()
        if dedicated and not runner_id:
            errors.append(
                f"专用 Flow {item.get('flow_id') or '<unknown>'} 必须声明 specialized_runner_id"
            )
            continue
        if not runner_id:
            continue
        flow_id = str(item.get("flow_id") or "").strip()
        if not flow_id:
            errors.append(f"专用执行器 {runner_id} 的 Flow 缺少 flow_id")
            continue
        discovered.setdefault(runner_id, {"case_ids": set(), "flow_ids": set()})["flow_ids"].add(flow_id)
    return discovered


def _string_list(value: Any, label: str, errors: list[str], *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{label} 必须是列表")
        return []
    values = [str(item).strip() for item in value if str(item).strip()]
    if len(values) != len(value):
        errors.append(f"{label} 只能包含非空字符串")
    duplicates = sorted(item for item, count in Counter(values).items() if count > 1)
    if duplicates:
        errors.append(f"{label} 存在重复项：{duplicates}")
    if not allow_empty and not values:
        errors.append(f"{label} 不能为空")
    return values


def _is_generated_source_ref(framework: Path, source_ref: str) -> bool:
    value = source_ref.split("#", 1)[0].strip().replace("\\", "/")
    if not value or "://" in value or "@" in value.split("/", 1)[0]:
        return False
    if value.startswith("../"):
        return False
    if value.startswith("/"):
        try:
            Path(value).resolve().relative_to(framework.resolve())
            return True
        except ValueError:
            return False
    normalized = value.removeprefix("./")
    first = normalized.split("/", 1)[0]
    return first in GENERATED_PREFIXES or normalized in GENERATED_DOCUMENTS


def _validate_adapter(framework: Path, runner_id: str, runner: dict[str, Any], generated_files: list[str], errors: list[str]) -> None:
    adapter = runner.get("adapter")
    if not isinstance(adapter, dict):
        errors.append(f"专用执行器 {runner_id} 缺少 adapter")
        return
    module_name = str(adapter.get("module") or "").strip()
    callable_name = str(adapter.get("callable") or "").strip()
    if not module_name.startswith("core."):
        errors.append(f"专用执行器 {runner_id} adapter.module 必须位于 core.*")
        return
    if not callable_name.isidentifier():
        errors.append(f"专用执行器 {runner_id} adapter.callable 必须是合法标识符")
        return
    module_path = Path(*module_name.split(".")).with_suffix(".py")
    if module_path.as_posix() not in generated_files:
        errors.append(f"专用执行器 {runner_id} generated_files 未包含适配模块：{module_path}")
    source_path = framework / module_path
    if not source_path.is_file():
        errors.append(f"专用执行器 {runner_id} 适配模块不存在：{module_path}")
        return
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        errors.append(f"专用执行器 {runner_id} 适配模块无法编译：{exc}")
        return
    functions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == callable_name
    ]
    if not functions:
        errors.append(f"专用执行器 {runner_id} 缺少适配函数：{callable_name}")
        return
    function = functions[0]
    argument_names = {
        argument.arg
        for argument in [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs]
    }
    if argument_names != REQUIRED_INPUTS:
        errors.append(
            f"专用执行器 {runner_id} 适配函数参数不一致：{sorted(argument_names)} != {sorted(REQUIRED_INPUTS)}"
        )


def _validate_generated_files(framework: Path, runner_id: str, value: Any, errors: list[str]) -> list[str]:
    generated_files = _string_list(value, f"专用执行器 {runner_id} generated_files", errors)
    for relative in generated_files:
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            errors.append(f"专用执行器 {runner_id} generated_files 必须是框架内相对路径：{relative}")
            continue
        target = framework / path
        if not target.is_file():
            errors.append(f"专用执行器 {runner_id} 生成文件不存在：{relative}")
            continue
        if target.suffix == ".py":
            try:
                ast.parse(target.read_text(encoding="utf-8"), filename=str(target))
            except (OSError, UnicodeError, SyntaxError) as exc:
                errors.append(f"专用执行器 {runner_id} 生成 Python 文件无法编译：{relative}：{exc}")
    return generated_files


def _validate_manifest(
    framework: Path,
    discovered: dict[str, dict[str, set[str]]],
    errors: list[str],
) -> dict[str, Any]:
    manifest_path = framework / MANIFEST_PATH
    if not manifest_path.is_file():
        if discovered:
            errors.append(f"发现专用执行器但缺少 {MANIFEST_PATH.as_posix()}")
        return {}
    manifest = _read_yaml(manifest_path, errors, MANIFEST_PATH.as_posix())
    if not isinstance(manifest, dict):
        return {}
    if manifest.get("schema_version") != 1:
        errors.append("专用执行器物化清单 schema_version 必须为 1")
    if str(manifest.get("status") or "").strip() != "passed":
        errors.append("专用执行器物化清单 status 必须为 passed")
    runners = manifest.get("runners")
    if not isinstance(runners, list):
        errors.append("专用执行器物化清单 runners 必须是列表")
        return manifest

    ids = [str(item.get("runner_id") or "").strip() for item in runners if isinstance(item, dict)]
    duplicates = sorted(item for item, count in Counter(ids).items() if item and count > 1)
    if duplicates:
        errors.append(f"专用执行器物化清单 runner_id 重复：{duplicates}")
    declared = {runner_id for runner_id in ids if runner_id}
    expected = set(discovered)
    if missing := sorted(expected - declared):
        errors.append(f"专用执行器物化清单缺少 runner_id：{missing}")
    if extra := sorted(declared - expected):
        errors.append(f"专用执行器物化清单存在无消费者 runner_id：{extra}")

    for index, runner in enumerate(runners, start=1):
        if not isinstance(runner, dict):
            errors.append(f"专用执行器物化清单第 {index} 条必须是对象")
            continue
        runner_id = str(runner.get("runner_id") or "").strip()
        if not runner_id:
            errors.append(f"专用执行器物化清单第 {index} 条缺少 runner_id")
            continue
        expected_consumers = discovered.get(runner_id, {"case_ids": set(), "flow_ids": set()})
        case_ids = set(
            _string_list(
                runner.get("consumer_case_ids"),
                f"专用执行器 {runner_id} consumer_case_ids",
                errors,
                allow_empty=True,
            )
        )
        flow_ids = set(
            _string_list(
                runner.get("consumer_flow_ids"),
                f"专用执行器 {runner_id} consumer_flow_ids",
                errors,
                allow_empty=True,
            )
        )
        if not case_ids and not flow_ids:
            errors.append(f"专用执行器 {runner_id} 至少需要一个消费者")
        if case_ids != expected_consumers["case_ids"]:
            errors.append(
                f"专用执行器 {runner_id} 普通用例消费者不一致：{sorted(case_ids)} != {sorted(expected_consumers['case_ids'])}"
            )
        if flow_ids != expected_consumers["flow_ids"]:
            errors.append(
                f"专用执行器 {runner_id} Flow 消费者不一致：{sorted(flow_ids)} != {sorted(expected_consumers['flow_ids'])}"
            )
        if not str(runner.get("reason_generic_runner_insufficient") or "").strip():
            errors.append(f"专用执行器 {runner_id} 缺少通用执行器不适用原因")
        source_refs = _string_list(
            runner.get("authoritative_source_refs"),
            f"专用执行器 {runner_id} authoritative_source_refs",
            errors,
        )
        circular_refs = [ref for ref in source_refs if _is_generated_source_ref(framework, ref)]
        if circular_refs:
            errors.append(f"专用执行器 {runner_id} 权威来源反向引用生成物：{circular_refs}")

        contract = runner.get("generation_contract")
        if not isinstance(contract, dict):
            errors.append(f"专用执行器 {runner_id} 缺少 generation_contract")
        else:
            for field in REQUIRED_CONTRACT_LISTS:
                values = _string_list(
                    contract.get(field),
                    f"专用执行器 {runner_id} generation_contract.{field}",
                    errors,
                )
                if field == "inputs" and set(values) != REQUIRED_INPUTS:
                    errors.append(
                        f"专用执行器 {runner_id} generation_contract.inputs 不符合统一适配合同"
                    )
        generated_files = _validate_generated_files(framework, runner_id, runner.get("generated_files"), errors)
        _validate_adapter(framework, runner_id, runner, generated_files, errors)
    return manifest


def _validate_status(framework: Path, discovered: dict[str, dict[str, set[str]]], errors: list[str]) -> None:
    if not discovered:
        return
    status_path = framework / STATUS_PATH
    if not status_path.is_file():
        errors.append(f"缺少 {STATUS_PATH.as_posix()}，无法记录专用执行器门禁")
        return
    status = _read_yaml(status_path, errors, STATUS_PATH.as_posix())
    section = status.get("specialized_runner_materialization") if isinstance(status, dict) else None
    if not isinstance(section, dict) or str(section.get("status") or "").strip() != "passed":
        errors.append("generation_status.yaml specialized_runner_materialization.status 必须为 passed")
        return
    expected = {
        "runner_count": len(discovered),
        "consumer_case_count": sum(len(value["case_ids"]) for value in discovered.values()),
        "consumer_flow_count": sum(len(value["flow_ids"]) for value in discovered.values()),
    }
    if str(section.get("manifest_path") or "").strip() != MANIFEST_PATH.as_posix():
        errors.append("generation_status.yaml specialized_runner_materialization.manifest_path 非法或缺失")
    for field, expected_value in expected.items():
        if section.get(field) != expected_value:
            errors.append(
                f"generation_status.yaml specialized_runner_materialization.{field} 不一致："
                f"{section.get(field)} != {expected_value}"
            )
    if section.get("errors") != []:
        errors.append("generation_status.yaml specialized_runner_materialization.errors 必须是空列表")


def _semantic_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    semantic: dict[str, Any] = {}
    for runner in manifest.get("runners") or []:
        if not isinstance(runner, dict):
            continue
        runner_id = str(runner.get("runner_id") or "").strip()
        if not runner_id:
            continue
        semantic[runner_id] = {
            "consumer_case_ids": sorted(runner.get("consumer_case_ids") or []),
            "consumer_flow_ids": sorted(runner.get("consumer_flow_ids") or []),
            "reason_generic_runner_insufficient": str(
                runner.get("reason_generic_runner_insufficient") or ""
            ).strip(),
            "authoritative_source_refs": sorted(runner.get("authoritative_source_refs") or []),
            "adapter": runner.get("adapter") or {},
            "generation_contract": runner.get("generation_contract") or {},
            "generated_files": sorted(runner.get("generated_files") or []),
        }
    return semantic


def validate_framework(framework: Path) -> dict[str, Any]:
    errors: list[str] = []
    discovered = _discover(framework, errors)
    manifest = _validate_manifest(framework, discovered, errors)
    _validate_status(framework, discovered, errors)
    if not discovered and not errors:
        status = "not_required"
    else:
        status = "failed" if errors else "passed"
    return {
        "schema_version": 1,
        "gate": "specialized_runner_materialization",
        "status": status,
        "runner_count": len(discovered),
        "consumer_case_count": sum(len(value["case_ids"]) for value in discovered.values()),
        "consumer_flow_count": sum(len(value["flow_ids"]) for value in discovered.values()),
        "runner_ids": sorted(discovered),
        "errors": errors,
        "semantic_manifest": _semantic_manifest(manifest),
    }


def compare_rebuild(baseline: dict[str, Any], rebuilt: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if baseline.get("status") != "passed":
        errors.append("被评审框架的专用执行器门禁未通过")
    if rebuilt.get("status") != "passed":
        errors.append("冷启动重建框架的专用执行器门禁未通过")
    if baseline.get("semantic_manifest") != rebuilt.get("semantic_manifest"):
        baseline_ids = set((baseline.get("semantic_manifest") or {}).keys())
        rebuilt_ids = set((rebuilt.get("semantic_manifest") or {}).keys())
        if missing := sorted(baseline_ids - rebuilt_ids):
            errors.append(f"冷启动重建缺少专用执行器：{missing}")
        if extra := sorted(rebuilt_ids - baseline_ids):
            errors.append(f"冷启动重建新增分母外专用执行器：{extra}")
        for runner_id in sorted(baseline_ids & rebuilt_ids):
            if baseline["semantic_manifest"][runner_id] != rebuilt["semantic_manifest"][runner_id]:
                errors.append(f"冷启动重建专用执行器语义合同不一致：{runner_id}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="校验专用执行器物化和冷启动语义一致性")
    parser.add_argument("framework", type=Path, help="被评审的 api-test-framework 目录")
    parser.add_argument("--rebuilt-framework", type=Path, help="从上游事实冷启动生成的临时框架目录")
    args = parser.parse_args()

    baseline = validate_framework(args.framework)
    output: dict[str, Any] = {key: value for key, value in baseline.items() if key != "semantic_manifest"}
    exit_code = 0 if baseline["status"] in {"passed", "not_required"} else 1
    if args.rebuilt_framework is not None:
        rebuilt = validate_framework(args.rebuilt_framework)
        comparison_errors = compare_rebuild(baseline, rebuilt)
        output["cold_start_reproduction"] = {
            "status": "failed" if comparison_errors else "passed",
            "rebuilt_framework": str(args.rebuilt_framework),
            "errors": comparison_errors,
        }
        output["rebuilt_gate_status"] = rebuilt["status"]
        if comparison_errors:
            exit_code = 1
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
