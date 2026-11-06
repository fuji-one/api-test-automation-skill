"""用例数据加载器，统一从 data/cases 和 data/interfaces.* 组装 pytest 参数。"""
import ast
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

import pytest

from utils.yaml_util import YamlUtil


ROOT_DIR = Path(__file__).resolve().parents[1]
CASE_DIR = ROOT_DIR / "data" / "cases"
INTERFACE_FILES = (
    ROOT_DIR / "data" / "interfaces.yaml",
    ROOT_DIR / "data" / "interfaces.py",
)
PY_DATA_EXPORTS = {"CASES", "INTERFACES", "FLOWS", "SCHEMA_VERSION"}
SQL_COMMAND_FILE = ROOT_DIR / "data" / "case_sql_commands.yaml"
NON_SQL_MATERIALIZATION_PREFIXES = (
    "not_required",
    "no_cleanup_required",
    "api_state_",
)


def load_case_parameters() -> List[Dict[str, Any]]:
    interface_index = load_interface_index(INTERFACE_FILES)
    sql_case_ids = load_sql_case_ids(SQL_COMMAND_FILE)
    case_files = sorted(
        [*CASE_DIR.glob("*.yaml"), *CASE_DIR.glob("*.py")],
        key=lambda path: str(path.relative_to(ROOT_DIR)),
    )
    cases: List[Dict[str, Any]] = []
    for case_file in case_files:
        raw_cases = load_case_records(case_file)
        if not isinstance(raw_cases, list):
            raise ValueError(f"用例文件必须包含 cases 列表：{case_file}")
        for raw_case in raw_cases:
            cases.append(build_case_parameter(raw_case, interface_index, case_file, sql_case_ids))
    return cases


def load_case_pytest_parameters() -> List[Any]:
    params: List[Any] = []
    for case_data in load_case_parameters():
        marker = pytest.mark.branch_flow if case_data.get("flow_type") == "branch" else pytest.mark.main_flow
        marks = [marker]
        if case_data.get("preconditions"):
            marks.append(pytest.mark.preconditions(case_data["preconditions"]))
        if case_data.get("cleanup"):
            marks.append(pytest.mark.cleanup(case_data["cleanup"]))
        if case_data.get("sql_fixture_required"):
            marks.append(pytest.mark.case_id(case_data["case_id"]))
        if is_generated_non_live_case(case_data):
            marks.append(pytest.mark.skip(reason=non_live_skip_reason(case_data)))
        params.append(pytest.param(case_data, marks=tuple(marks), id=case_data["case_id"]))
    return params


def load_interface_index(paths: Iterable[Path]) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    loaded = False
    for path in paths:
        if not path.is_file():
            continue
        loaded = True
        interfaces = load_interface_records(path)
        if not isinstance(interfaces, list):
            raise ValueError(f"接口定义文件必须包含 interfaces 列表：{path}")
        for item in interfaces:
            interface_id = required_text(item, "interface_id", path)
            if interface_id in index:
                raise ValueError(f"接口定义重复：{interface_id}")
            for key in ("method", "path"):
                required_text(item, key, path)
            index[interface_id] = item
    if not loaded:
        choices = " 或 ".join(str(path.relative_to(ROOT_DIR)) for path in paths)
        raise ValueError(f"缺少接口定义文件：{choices}")
    return index


def load_interface_records(path: Path) -> Any:
    if path.suffix == ".py":
        return load_python_data_export(path, "INTERFACES")
    data = YamlUtil.load(path)
    return data.get("interfaces")


def load_case_records(path: Path) -> Any:
    if path.suffix == ".py":
        return load_python_data_export(path, "CASES")
    data = YamlUtil.load(path)
    return data.get("cases")


def load_sql_case_ids(path: Path) -> Set[str]:
    """读取 SQL 台账中的用例 ID；台账不存在时保留显式 SQL 信号判定。"""

    if not path.is_file():
        return set()
    data = YamlUtil.load(path) or {}
    cases = data.get("cases") or {}
    if not isinstance(cases, dict):
        raise ValueError(f"SQL 命令文件 cases 必须是对象：{path}")
    return {str(case_id).strip() for case_id in cases if str(case_id).strip()}


def materialization_requires_sql(value: Any, field_name: str) -> bool:
    """区分真正的 SQL/DB 物化信号与 no-cleanup/not-required 状态。"""

    if value is None or value is False:
        return False
    if value is True:
        return True
    if isinstance(value, str):
        normalized = value.strip().lower()
        if not normalized or normalized in {"false", "none", "null"}:
            return False
        if normalized.startswith(NON_SQL_MATERIALIZATION_PREFIXES):
            return False
        if field_name == "db_assertion_materialization":
            return True
        return "sql" in normalized or "database" in normalized or normalized.startswith("db_")
    if isinstance(value, dict):
        status = str(value.get("status") or "").strip().lower()
        if status.startswith(NON_SQL_MATERIALIZATION_PREFIXES):
            return False
        for key, item in value.items():
            normalized_key = str(key).strip().lower()
            # 嵌套布尔值只表示清理、恢复等通用能力，不能单独证明需要 SQL。
            if isinstance(item, bool):
                if item and any(signal in normalized_key for signal in ("sql", "database", "db_")):
                    return True
                continue
            if materialization_requires_sql(item, field_name):
                return True
        return False
    if isinstance(value, (list, tuple, set)):
        return any(materialization_requires_sql(item, field_name) for item in value)
    return False


def case_requires_sql_fixture(raw_case: Dict[str, Any], case_id: str, sql_case_ids: Set[str]) -> bool:
    """使用统一谓词识别需要 SQL 生命周期 fixture 的用例。"""

    return bool(
        raw_case.get("sql_fixture_required")
        or case_id in sql_case_ids
        or materialization_requires_sql(
            raw_case.get("setup_cleanup_materialization"),
            "setup_cleanup_materialization",
        )
        or materialization_requires_sql(
            raw_case.get("db_assertion_materialization"),
            "db_assertion_materialization",
        )
    )


def load_python_data_export(path: Path, export_name: str) -> Any:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    exports: Dict[str, Any] = {}
    for node in tree.body:
        if is_module_docstring(node):
            continue
        target_names, value_node = assignment_export(node)
        if not target_names:
            raise ValueError(f"Python 数据文件只能包含常量赋值：{path}")
        for name in target_names:
            if name not in PY_DATA_EXPORTS:
                raise ValueError(f"Python 数据文件存在非约定变量：{path}:{name}")
            try:
                exports[name] = ast.literal_eval(value_node)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Python 数据文件变量必须是字面量：{path}:{name}") from exc
    if export_name not in exports:
        raise ValueError(f"Python 数据文件缺少导出变量：{path}:{export_name}")
    return exports[export_name]


def is_module_docstring(node: ast.AST) -> bool:
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)


def assignment_export(node: ast.AST) -> tuple[list[str], ast.AST | None]:
    if isinstance(node, ast.Assign):
        names = [target.id for target in node.targets if isinstance(target, ast.Name)]
        if len(names) != len(node.targets):
            return [], None
        return names, node.value
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
        return [node.target.id], node.value
    return [], None


def build_case_parameter(
    raw_case: Dict[str, Any],
    interface_index: Dict[str, Dict[str, Any]],
    case_file: Path,
    sql_case_ids: Set[str] | None = None,
) -> Dict[str, Any]:
    case_id = required_text(raw_case, "case_id", case_file)
    interface_id = required_text(raw_case, "interface_id", case_file)
    if interface_id not in interface_index:
        raise ValueError(f"用例引用了不存在的接口定义：{case_id} -> {interface_id}")
    interface = interface_index[interface_id]
    case_data = {
        "case_id": case_id,
        "title": raw_case.get("title") or case_id,
        "priority": raw_case.get("priority") or "P1",
        "flow_type": raw_case.get("flow_type") or "main",
        "allure": raw_case.get("allure") or {},
        "interface_id": interface_id,
        "method": interface["method"],
        "path": interface["path"],
        "module": interface.get("module") or raw_case.get("module"),
        "account_group_key": raw_case.get("account_group_key"),
        "session_role": raw_case.get("session_role") or "default",
        "required_session_roles": raw_case.get("required_session_roles") or [],
        "steps": raw_case.get("steps") or [],
        "request": raw_case.get("request") or {},
        "expected": raw_case.get("expected") or {},
        "preconditions": raw_case.get("preconditions") or [],
        "cleanup": raw_case.get("cleanup") or [],
        "database": raw_case.get("database") or {},
        "traceability": raw_case.get("traceability") or {},
        "confidence_score": raw_case.get("confidence_score"),
        "confidence_level": raw_case.get("confidence_level"),
        "confidence_band": raw_case.get("confidence_band"),
        "confidence_scope": raw_case.get("confidence_scope"),
        "scenario_relevance": raw_case.get("scenario_relevance"),
        "confidence_dimensions": raw_case.get("confidence_dimensions") or {},
        "confidence_reason_codes": raw_case.get("confidence_reason_codes") or [],
        "confidence_cap_reasons": raw_case.get("confidence_cap_reasons") or [],
        "confidence_evidence_refs": raw_case.get("confidence_evidence_refs") or [],
        "setup_cleanup_materialization": raw_case.get("setup_cleanup_materialization"),
        "db_assertion_materialization": raw_case.get("db_assertion_materialization"),
        "sql_fixture_required": case_requires_sql_fixture(raw_case, case_id, sql_case_ids or set()),
        "live_pytest_release_ready": raw_case.get("live_pytest_release_ready"),
        "automation_decision": raw_case.get("automation_decision"),
        "non_live_reason": raw_case.get("non_live_reason") or raw_case.get("live_blocker_reason"),
        "assertion_strength": raw_case.get("assertion_strength"),
        "result_observation_mode": raw_case.get("result_observation_mode"),
        "specialized_runner_id": raw_case.get("specialized_runner_id"),
        "specialized_runner_config": raw_case.get("specialized_runner_config") or {},
        "specialized_runner_assertions": raw_case.get("specialized_runner_assertions") or {},
        "custom_runner": raw_case.get("custom_runner"),
        "custom_runner_config": raw_case.get("custom_runner_config") or {},
        "custom_runner_assertions": raw_case.get("custom_runner_assertions") or {},
        "runtime_business_dependencies": raw_case.get("runtime_business_dependencies") or [],
        "case_runtime_isolation": raw_case.get("case_runtime_isolation") or {},
        "failure_path_cleanup": raw_case.get("failure_path_cleanup") or {},
        "source_file": str(case_file.relative_to(ROOT_DIR)),
    }
    return case_data


def is_generated_non_live_case(case_data: Dict[str, Any]) -> bool:
    """识别已生成但默认不 live 执行的用例，避免误跑写副作用或外部依赖链路。"""

    decision = str(case_data.get("automation_decision") or "").strip()
    return case_data.get("live_pytest_release_ready") is False or decision in {
        "generated_non_live",
        "manual_review_only",
        "blocked_live_execution",
    }


def non_live_skip_reason(case_data: Dict[str, Any]) -> str:
    reason = case_data.get("non_live_reason") or "用例为 generated_non_live/manual_review_only，默认不进入 live 执行"
    return f"{case_data['case_id']} 默认跳过：{reason}"


def required_text(data: Dict[str, Any], key: str, source: Path) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{source} 缺少必填字段：{key}")
    return value.strip()
