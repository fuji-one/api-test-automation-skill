# pytest 全局夹具和收集规则，负责串联环境、鉴权、前置数据、SQL 铺数和清理流程。
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import pytest
from sqlalchemy.exc import OperationalError as SQLAlchemyOperationalError

from core.dependency_check import DependencyChecker


# 导入业务框架模块前先做依赖检查，依赖缺失时尽早失败。
DependencyChecker.check_required()

from core.auth_manager import AuthManager
from core.client import HttpClient
from core.data_manager import DataRuleExecutor
from core.runtime_context import prepare_case_runtime_context, publish_runtime_variables, resolve_runtime_value
from utils.yaml_util import YamlUtil


ROOT_DIR = Path(__file__).parent


# 注册命令行参数，所有测试都必须显式选择运行环境。
def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--env", action="store", default=None, help="指定运行环境：dev/test/prod")
    parser.addoption("--flow", action="store", default="all", choices=("main", "branch", "all"), help="指定执行流程：main/branch/all")
    parser.addoption("--run-slow-async", action="store_true", default=False, help="显式收集并执行可选慢异步用例")
    parser.addoption("--slow-async-wait-seconds", action="store", default=None, help="覆盖可选慢异步用例等待秒数")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "main_flow: 标记主流程用例")
    config.addinivalue_line("markers", "branch_flow: 标记分支流程用例")
    config.addinivalue_line("markers", "e2e_flow: 标记 E2E 长链路脚本入口")
    config.addinivalue_line("markers", "optional_async: 标记默认不收集的可选慢异步用例")
    config.addinivalue_line("markers", "case_id(value): 标记源文档中的用例编号")
    config.addinivalue_line("markers", "preconditions(rules): 标记用例前置铺数规则")
    config.addinivalue_line("markers", "cleanup(rules): 标记用例执行后清理规则")
    config.addinivalue_line("markers", "db_assertions(rules): 标记需要数据库 fixture 查询的落库断言")


def pytest_ignore_collect(collection_path: Any, config: pytest.Config) -> bool | None:
    path = Path(str(collection_path))
    if path.name == "test_optional_async_cases.py" and not config.getoption("--run-slow-async", default=False):
        return True
    return None


# 收集阶段校验用例标记和 fixture 契约，防止不完整用例进入执行。
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        # 收集期先失败，避免有缺陷的用例进入真实接口执行。
        _validate_flow_markers(item)
        _validate_fixture_contract(item)

    flow = config.getoption("--flow")
    if flow == "all":
        return
    # flow 过滤只打 skip 标记，保留收集结果便于检查用例映射。
    skip_marker = pytest.mark.skip(reason=f"当前 --flow={flow}，跳过非目标流程用例")
    for item in items:
        is_branch_flow = item.get_closest_marker("branch_flow") is not None
        if flow == "main" and is_branch_flow:
            item.add_marker(skip_marker)
        if flow == "branch" and not is_branch_flow:
            item.add_marker(skip_marker)


def _validate_flow_markers(item: pytest.Item) -> None:
    flow_markers = [
        marker_name
        for marker_name in ("main_flow", "branch_flow")
        if item.get_closest_marker(marker_name) is not None
    ]
    if len(flow_markers) != 1:
        raise pytest.UsageError(f"用例必须且只能标记一个流程类型：{item.nodeid}")


def _validate_fixture_contract(item: pytest.Item) -> None:
    fixture_names = set(getattr(item, "fixturenames", ()))
    if (
        item.get_closest_marker("preconditions") is not None
        or item.get_closest_marker("cleanup") is not None
    ) and "case_data_manager" not in fixture_names:
        raise pytest.UsageError(f"包含 preconditions/cleanup 标记的用例必须使用 case_data_manager fixture：{item.nodeid}")
    if item.get_closest_marker("case_id") is not None and "case_sql_manager" not in fixture_names:
        raise pytest.UsageError(f"包含 case_id 标记的 SQL 用例必须使用 case_sql_manager fixture：{item.nodeid}")
    if item.get_closest_marker("db_assertions") is not None and "database_assertor" not in fixture_names:
        raise pytest.UsageError(f"包含 db_assertions 标记的用例必须使用 database_assertor fixture：{item.nodeid}")


# 会话级读取环境配置，后续 client、鉴权和数据库 fixture 都依赖它。
@pytest.fixture(scope="session")
def env_name(pytestconfig: pytest.Config) -> str:
    env_name = pytestconfig.getoption("--env")
    if not env_name:
        raise ValueError("必须通过 --env 指定运行环境，例如：--env=dev")
    return env_name


@pytest.fixture(scope="session")
def env_config(env_name: str) -> Dict[str, Any]:
    config_path = ROOT_DIR / "configs" / f"{env_name}.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"环境配置文件不存在：{config_path}")
    return YamlUtil.load(config_path)


@pytest.fixture(scope="session")
def database_config(env_name: str) -> Dict[str, Any]:
    # 数据库配置集中放在 configs/database.yaml，避免散落在用例或执行器代码里。
    database_config_path = ROOT_DIR / "configs" / "database.yaml"
    if not database_config_path.exists():
        raise FileNotFoundError(f"数据库配置文件不存在：{database_config_path}")
    all_database_config = YamlUtil.load(database_config_path)
    database_config = all_database_config.get(env_name)
    if not isinstance(database_config, dict):
        raise ValueError(f"数据库配置缺少环境节点：{env_name}")
    return database_config


@pytest.fixture(scope="session")
def api_client(env_config: Dict[str, Any]) -> HttpClient:
    return HttpClient(
        base_url=env_config["base_url"],
        timeout=env_config["timeout"],
        headers=env_config.get("headers", {}),
        modules=env_config.get("modules") or {},
        transport_config=env_config.get("transport_encryption") or {},
    )


@pytest.fixture(scope="session")
def runtime_context() -> Dict[str, Any]:
    # 会话级上下文用于跨步骤传递 token、业务 ID 和 SQL 参数。
    return {"nowIso": datetime.now().strftime("%Y%m%d%H%M%S")}


def _database_engine_options(database_config: Dict[str, Any]) -> Dict[str, Any]:
    """生成数据库连接池参数，避免长异步等待后复用已失效连接。"""
    engine_options = database_config.get("engine_options") or {}
    pool_recycle_seconds = int(engine_options.get("pool_recycle_seconds", 300))
    if pool_recycle_seconds < 0:
        raise ValueError("database.engine_options.pool_recycle_seconds 不能小于 0")
    return {
        "pool_pre_ping": bool(engine_options.get("pool_pre_ping", True)),
        "pool_recycle": pool_recycle_seconds,
    }


@pytest.fixture(scope="session")
def database_engines(database_config: Dict[str, Any], runtime_context: Dict[str, Any]) -> Dict[str, Any]:
    # 数据库实例由 fixture 统一管理生命周期，保证脚本独立执行时连接可控。
    if not database_config.get("enabled", False):
        yield {}
        return
    DependencyChecker.check_database_runtime_required()
    from sqlalchemy import create_engine

    engine_options = _database_engine_options(database_config)
    aliases = database_config.get("database_aliases") or {}
    if aliases:
        engines = {
            alias: create_engine(
                resolve_runtime_value(connection_url, runtime_context),
                **engine_options,
            )
            for alias, connection_url in aliases.items()
        }
    else:
        connection_url = database_config.get("connection_url")
        if not connection_url:
            raise ValueError("启用数据库时必须配置 connection_url")
        engines = {
            "default": create_engine(
                resolve_runtime_value(connection_url, runtime_context),
                **engine_options,
            )
        }
    yield engines
    for engine in engines.values():
        engine.dispose()


@pytest.fixture(scope="session")
def database_engine(database_engines: Dict[str, Any]) -> Optional[Any]:
    if not database_engines:
        yield None
        return
    yield next(iter(database_engines.values()))


@pytest.fixture(scope="session")
def auth_contexts(env_config: Dict[str, Any], api_client: HttpClient, runtime_context: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    role_configs = _resolve_role_auth_configs(env_config)
    contexts: Dict[str, Dict[str, Any]] = {}
    aliases: Dict[str, str] = {}
    for role, role_config in role_configs.items():
        if isinstance(role_config, str):
            aliases[role] = _resolve_auth_role_name(role, role_configs)
            continue
        context = _build_role_auth_context_template(role_config or {})
        contexts[role] = context
        _publish_role_runtime_context(runtime_context, role, context)
    for role, target_role in aliases.items():
        if target_role not in contexts:
            raise ValueError(f"auth_roles.{role} 引用了不存在的角色：{target_role}")
        contexts[role] = contexts[target_role]
        _publish_role_runtime_context(runtime_context, role, contexts[target_role])
    if "default" not in contexts:
        raise ValueError("auth_roles 必须提供 default 角色，或显式把 default 指向某个已配置角色")
    runtime_context["auth_role_configs"] = role_configs
    runtime_context["auth_roles"] = contexts
    return contexts


@pytest.fixture(scope="session")
def auth_context(auth_contexts: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    return auth_contexts["default"]


@pytest.fixture(scope="session")
def auth_headers(auth_context: Dict[str, Any]) -> Dict[str, str]:
    if not auth_context.get("enabled") or auth_context.get("placement") != "header":
        return {}
    return {auth_context["token_name"]: auth_context["token_text"]}


@pytest.fixture(scope="session")
def authenticated_client(api_client: HttpClient, auth_context: Dict[str, Any], auth_headers: Dict[str, str]) -> HttpClient:
    # token 上下文支持按请求方法注入 header/query/body/cookie，auth_headers 保留兼容旧用法。
    api_client.set_auth_context(auth_context)
    api_client.set_headers(auth_headers)
    return api_client


def _resolve_role_auth_configs(env_config: Dict[str, Any]) -> Dict[str, Any]:
    role_configs = env_config.get("auth_roles")
    if role_configs:
        if not isinstance(role_configs, dict):
            raise TypeError("auth_roles 必须是对象")
        return role_configs
    return {"default": env_config.get("auth") or {"enabled": False}}


def _build_role_auth_context_template(role_config: Dict[str, Any]) -> Dict[str, Any]:
    # 会话初始化只注册账号模板，真实登录延迟到账号组首次使用时执行。
    if not role_config.get("enabled", False):
        return {"enabled": False}
    placement = AuthManager._normalize_placement(role_config.get("placement") or AuthManager.DEFAULT_PLACEMENT)
    token_name = role_config.get("token_name") or AuthManager._default_token_name(placement)
    token_prefix = role_config.get("token_prefix", AuthManager.DEFAULT_TOKEN_PREFIX)
    token_value = role_config.get("token_value")
    token_text = f"{token_prefix} {token_value}".strip() if token_value else ""
    user_id = role_config.get("user_id")
    return {
        "enabled": bool(token_value),
        "type": role_config.get("type", "bearer"),
        "token_name": token_name,
        "token_value": token_value,
        "token_prefix": token_prefix,
        "token_text": token_text,
        "placement": placement,
        "method_overrides": AuthManager._normalize_method_overrides(role_config.get("method_overrides") or {}),
        "session_secret": role_config.get("session_secret_value"),
        "user_id": user_id,
        "device_id": role_config.get("device_id"),
        "hash_user_id": "",
    }


def _publish_role_runtime_context(runtime_context: Dict[str, Any], role: str, auth_context: Dict[str, Any]) -> None:
    role_context = {
        "auth_token": auth_context.get("token_value"),
        "session_secret": auth_context.get("session_secret"),
        "hash_user_id": auth_context.get("hash_user_id"),
        "deviceId": auth_context.get("device_id"),
    }
    user_id = auth_context.get("user_id")
    if user_id is not None:
        role_context.update({
            "login_user_id": user_id,
            "appUserId": user_id,
            "userId": user_id,
        })
        runtime_context[f"{role}_user_id"] = user_id
    runtime_context[f"{role}_context"] = role_context


@pytest.fixture(scope="function")
def case_runtime_scope(
    request: pytest.FixtureRequest,
    runtime_context: Dict[str, Any],
    env_config: Dict[str, Any],
) -> Dict[str, Any]:
    """隔离每条用例的业务变量，账号组鉴权上下文继续按会话复用。"""

    case_data = _get_current_case_data(request)
    case_marker = request.node.get_closest_marker("case_id")
    case_id = (case_data or {}).get("case_id")
    if not case_id and case_marker is not None and case_marker.args:
        case_id = case_marker.args[0]
    prepare_case_runtime_context(runtime_context, env_config, str(case_id or request.node.name))
    return runtime_context


# 函数级账号登录前置：普通 API 用例按账号组首次使用时刷新 token，组内复用同一 client/session。
@pytest.fixture(scope="function")
def case_account_login(
    request: pytest.FixtureRequest,
    api_client: HttpClient,
    env_config: Dict[str, Any],
    runtime_context: Dict[str, Any],
    auth_contexts: Dict[str, Dict[str, Any]],
    case_runtime_scope: Dict[str, Any],
) -> list[Dict[str, Any]]:
    case_data = _get_current_case_data(request)
    login_records: list[Dict[str, Any]] = []
    if not case_data or _case_has_explicit_login_step(case_data):
        yield login_records
        return

    role_configs = _resolve_role_auth_configs(env_config)
    logged_roles = runtime_context.setdefault("case_account_logged_roles", {})
    for role in _collect_case_session_roles(case_data):
        resolved_role = _resolve_auth_role_name(role, role_configs)
        role_config = _get_concrete_role_config(resolved_role, role_configs)
        token_request = role_config.get("token_request") or {}
        record = {
            "case_id": case_data["case_id"],
            "session_role": role,
            "resolved_role": resolved_role,
            "login_path": token_request.get("path"),
        }
        if resolved_role in logged_roles:
            record["login_reused"] = True
            login_records.append(record)
            continue

        context = _refresh_role_auth_context(resolved_role, role_configs, api_client, runtime_context, auth_contexts)
        logged_roles[resolved_role] = {
            "first_case_id": case_data["case_id"],
            "login_path": token_request.get("path"),
            "user_id": context.get("user_id"),
        }
        record["login_reused"] = False
        login_records.append(record)

    if login_records:
        runtime_context.setdefault("case_account_login_records", []).extend(login_records)
    yield login_records


def _get_current_case_data(request: pytest.FixtureRequest) -> Optional[Dict[str, Any]]:
    callspec = getattr(request.node, "callspec", None)
    if callspec is None:
        return None
    case_data = callspec.params.get("case_data")
    if isinstance(case_data, dict):
        return case_data
    return None


def _case_has_explicit_login_step(case_data: Dict[str, Any]) -> bool:
    steps = case_data.get("steps") or []
    if not steps:
        return False
    first_step = steps[0]
    return bool(first_step.get("login_entry") or first_step.get("step_type") in {"auth", "login"})


def _collect_case_session_roles(case_data: Dict[str, Any]) -> list[str]:
    roles: list[str] = []
    steps = case_data.get("steps") or [
        {
            "session_role": case_data.get("session_role") or "default",
            "step_type": "api",
        }
    ]
    for step in steps:
        if step.get("step_type") in {"auth", "login"}:
            continue
        role = step.get("session_role") or "default"
        if role == "none" or role in roles:
            continue
        roles.append(role)
    for rule in [*(case_data.get("preconditions") or []), *(case_data.get("cleanup") or [])]:
        role = rule.get("session_role")
        if not role or role == "none" or role in roles:
            continue
        roles.append(role)
    return roles


def _resolve_auth_role_name(role: str, role_configs: Dict[str, Any]) -> str:
    if role not in role_configs:
        raise ValueError(f"用例声明了未配置的 session_role：{role}")
    target_role = role
    visited_roles = set()
    while isinstance(role_configs[target_role], str):
        if target_role in visited_roles:
            raise ValueError(f"auth_roles 存在循环引用：{role}")
        visited_roles.add(target_role)
        target_role = role_configs[target_role]
        if target_role not in role_configs:
            raise ValueError(f"auth_roles.{role} 引用了不存在的角色：{target_role}")
    return target_role


def _get_concrete_role_config(role: str, role_configs: Dict[str, Any]) -> Dict[str, Any]:
    role_config = role_configs.get(role)
    if isinstance(role_config, str):
        role_config = role_configs.get(_resolve_auth_role_name(role, role_configs))
    if not isinstance(role_config, dict):
        raise TypeError(f"auth_roles.{role} 必须是对象或角色别名")
    return role_config


def _refresh_role_auth_context(
    resolved_role: str,
    role_configs: Dict[str, Any],
    api_client: HttpClient,
    runtime_context: Dict[str, Any],
    auth_contexts: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    role_config = _get_concrete_role_config(resolved_role, role_configs)
    role_runtime_context: Dict[str, Any] = {}
    context = AuthManager.build_auth_context(role_config, api_client, role_runtime_context)
    _validate_expected_user_id(resolved_role, role_config, context)
    for role in _roles_for_resolved_auth_role(resolved_role, role_configs):
        auth_contexts[role] = context
        _publish_role_runtime_context(runtime_context, role, context)
    runtime_context["auth_roles"] = auth_contexts
    return context


def _roles_for_resolved_auth_role(resolved_role: str, role_configs: Dict[str, Any]) -> list[str]:
    roles: list[str] = []
    for role in role_configs:
        if _resolve_auth_role_name(role, role_configs) == resolved_role:
            roles.append(role)
    return roles


def _validate_expected_user_id(role: str, role_config: Dict[str, Any], auth_context: Dict[str, Any]) -> None:
    expected_user_id = role_config.get("expected_user_id")
    if expected_user_id is None:
        return
    actual_user_id = auth_context.get("user_id")
    if actual_user_id is None:
        raise ValueError(f"账号角色 {role} 登录后未返回 userId，不能确认账号身份")
    if str(actual_user_id) != str(expected_user_id):
        raise ValueError(f"账号角色 {role} 登录身份不匹配：期望 userId={expected_user_id}，实际 userId={actual_user_id}")


# 函数级前置/清理 fixture：测试前铺数，测试后按声明规则清理。
@pytest.fixture(scope="function")
def case_data_manager(
    request: pytest.FixtureRequest,
    authenticated_client: HttpClient,
    runtime_context: Dict[str, Any],
    case_account_login: list[Dict[str, Any]],
    auth_contexts: Dict[str, Dict[str, Any]],
) -> DataRuleExecutor:
    executor = DataRuleExecutor(authenticated_client, runtime_context, auth_contexts)
    setup_rules = _get_marker_rules(request, "preconditions")
    cleanup_rules = _get_marker_rules(request, "cleanup")
    try:
        if setup_rules:
            executor.setup(setup_rules)
        yield executor
    finally:
        if cleanup_rules:
            executor.cleanup(cleanup_rules)


@pytest.fixture(scope="session")
def sql_commands(database_config: Dict[str, Any]) -> Dict[str, Any]:
    command_file = database_config.get("sql_commands_file")
    if not command_file:
        raise ValueError("database.sql_commands_file 不能为空")
    command_path = ROOT_DIR / command_file
    if not command_path.exists():
        raise FileNotFoundError(f"SQL 命令文件不存在：{command_path}")
    return YamlUtil.load(command_path)


# 函数级 SQL fixture：按 case_id 执行前置 SQL，并在用例结束后执行抽取、清理和最终验证。
@pytest.fixture(scope="function")
def case_sql_manager(
    request: pytest.FixtureRequest,
    runtime_context: Dict[str, Any],
    env_config: Dict[str, Any],
    case_account_login: list[Dict[str, Any]],
) -> Any:
    case_data = _get_current_case_data(request)
    if not _case_requires_sql_fixture(case_data) and request.node.get_closest_marker("case_id") is None:
        yield None
        return

    # 先读取用例的 SQL 生命周期；只有 case_id 但四个阶段都为空时，它仍是纯 API 用例。
    sql_commands = request.getfixturevalue("sql_commands")
    from core.sql_executor import CaseSqlCommandLoader, SqlExecutor

    case_id = _get_case_id(request)
    if not case_id and isinstance(case_data, dict):
        case_id = case_data.get("case_id")
    if not case_id:
        raise ValueError("无法确定当前 SQL 用例的 case_id")
    case_commands = CaseSqlCommandLoader.get_case_commands(sql_commands, case_id)
    sql_stages = ("setup", "runtime_extract", "cleanup", "final_verify")
    if not any(case_commands.get(stage) for stage in sql_stages):
        yield None
        return

    # 确认存在 SQL 命令后再懒加载数据库，避免纯 API 长链路被 DB 环境阻塞。
    database_engines = request.getfixturevalue("database_engines")
    if not database_engines:
        raise ValueError("SQL 用例必须通过 database_engines fixture 获取数据库实例")
    publish_runtime_variables(runtime_context, env_config)
    executor = SqlExecutor(database_engines, runtime_context)
    executor.bind_case(case_id, case_commands)
    try:
        executor.setup(case_id, case_commands)
    except SQLAlchemyOperationalError as exc:
        pytest.skip(f"SQL fixture 未能连接数据库，跳过该用例：{exc}")
    try:
        yield executor
    finally:
        # yield 之后统一闭合，确保测试失败时也会尝试清理当前用例数据。
        lifecycle_errors: list[tuple[str, Exception]] = []
        for stage_name, stage_action in (
            ("runtime_extract", executor.extract_runtime),
            ("cleanup", executor.cleanup),
            ("final_verify", executor.final_verify),
        ):
            try:
                stage_action(case_id, case_commands)
            except Exception as error:
                lifecycle_errors.append((stage_name, error))
        if lifecycle_errors:
            if all(isinstance(error, SQLAlchemyOperationalError) for _, error in lifecycle_errors):
                details = "；".join(f"{stage}={error}" for stage, error in lifecycle_errors)
                pytest.skip(f"SQL 后置生命周期数据库连接失败：{details}")
            details = "；".join(f"{stage}={error}" for stage, error in lifecycle_errors)
            raise AssertionError(f"SQL 后置生命周期存在 {len(lifecycle_errors)} 个失败阶段：{case_id}；{details}") from lifecycle_errors[0][1]


@pytest.fixture(scope="function")
def database_assertor(request: pytest.FixtureRequest, database_engine: Optional[Any], runtime_context: Dict[str, Any]) -> Any:
    if database_engine is None:
        raise ValueError("落库断言必须通过 database_engine fixture 获取数据库实例")
    from core.database_assertor import DatabaseAssertor

    return DatabaseAssertor(database_engine, runtime_context, _get_marker_rules(request, "db_assertions"))


def _get_marker_rules(request: pytest.FixtureRequest, marker_name: str) -> list[Dict[str, Any]]:
    marker = request.node.get_closest_marker(marker_name)
    if marker is None:
        return []
    if not marker.args:
        raise ValueError(f"{marker_name} marker 必须提供规则列表")
    rules = marker.args[0]
    if not isinstance(rules, list):
        raise TypeError(f"{marker_name} marker 的规则必须是 list")
    return rules


def _case_requires_sql_fixture(case_data: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(case_data, dict):
        return False
    # case_loader 已按统一谓词完成分类；这里不能把 API-only 物化状态误判为 SQL。
    return bool(case_data.get("sql_fixture_required"))


def _get_case_id(request: pytest.FixtureRequest) -> str:
    marker = request.node.get_closest_marker("case_id")
    if marker is None or not marker.args:
        return ""
    case_id = marker.args[0]
    if not isinstance(case_id, str) or not case_id:
        raise TypeError("case_id marker 的值必须是非空字符串")
    return case_id
