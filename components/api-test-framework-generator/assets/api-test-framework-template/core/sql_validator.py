# SQL 校验层，负责静态校验、事务回滚式运行预检和影响行数检查。
import re
from typing import Any, Dict, Iterable, List, Mapping

from sqlalchemy import create_engine, text

from core.sql_executor import CaseSqlCommandLoader, SqlSafetyValidator
from core.runtime_context import resolve_runtime_value


RUNTIME_CONTEXT_PATTERN = re.compile(r"\$\{runtime_context\.([A-Za-z_][A-Za-z0-9_]*)\}")


class SqlCommandValidator:
    """校验 SQL 语法、参数、逻辑边界和运行准确性。"""

    @classmethod
    def validate_static(cls, sql_commands: Dict[str, Any]) -> None:
        allowed_tables = CaseSqlCommandLoader.validate_generation_gate(sql_commands, require_runtime=False)
        cases = sql_commands.get("cases") or {}
        if not cases:
            raise ValueError("SQL 生成准出通过时，cases 不能为空")

        # 静态校验逐用例检查，确保每个 case 的 setup/cleanup 都满足边界约束。
        for case_id, case_commands in cases.items():
            commands = CaseSqlCommandLoader.get_case_commands(sql_commands, case_id, require_runtime=False)
            CaseSqlCommandLoader.validate_case_tables(case_id, commands, allowed_tables)
            cls._validate_cleanup_contract(case_id, commands)
            cls._validate_failure_path_cleanup_contract(case_id, commands)
            case_params = commands.get("params") or {}
            enforce_failure_path_policy = bool(commands.get("failure_path_cleanup"))
            cls._validate_stage_commands(
                case_id,
                "SQL 前置铺数",
                commands["setup"],
                case_params,
                enforce_failure_path_policy,
            )
            cls._validate_stage_commands(
                case_id,
                "SQL 运行期抽取",
                commands["runtime_extract"],
                case_params,
                enforce_failure_path_policy,
            )
            cls._validate_stage_commands(
                case_id,
                "SQL 后置清理",
                commands["cleanup"],
                case_params,
                enforce_failure_path_policy,
            )
            cls._validate_stage_commands(
                case_id,
                "SQL 最终验证",
                commands["final_verify"],
                case_params,
                enforce_failure_path_policy,
            )

    @classmethod
    def validate_runtime(cls, database_config: Dict[str, Any], sql_commands: Dict[str, Any]) -> None:
        # 运行预检先复用静态校验，再进入真实数据库事务检查。
        cls.validate_static(sql_commands)
        if not database_config.get("enabled", False):
            raise ValueError("SQL 运行预检要求启用 database.enabled")
        connection_url = database_config.get("connection_url")
        if not connection_url:
            raise ValueError("SQL 运行预检要求配置 database.connection_url")

        engines = cls._create_runtime_engines(database_config, connection_url)
        default_engine = next(iter(engines.values()))
        with default_engine.connect() as connection:
            # 运行预检只验证 SQL 行为，最后统一回滚，避免污染环境数据。
            transaction = connection.begin()
            try:
                for case_id, case_commands in (sql_commands.get("cases") or {}).items():
                    cls._execute_for_validation(connection, case_id, "SQL 前置铺数", case_commands.get("setup") or [])
                    cls._execute_for_validation(connection, case_id, "SQL 后置清理", case_commands.get("cleanup") or [])
            finally:
                # 无论校验成功或失败都回滚，运行预检不允许留下测试数据。
                transaction.rollback()
                for engine in engines.values():
                    engine.dispose()

    @classmethod
    def _validate_cleanup_contract(cls, case_id: str, commands: Dict[str, List[Dict[str, Any]]]) -> None:
        if commands["setup"] and not commands["cleanup"]:
            raise ValueError(f"存在 SQL 前置铺数时必须提供后置清理：{case_id}")

    @classmethod
    def _validate_stage_commands(
        cls,
        case_id: str,
        stage_name: str,
        commands: Iterable[Dict[str, Any]],
        case_params: Dict[str, Any],
        enforce_failure_path_policy: bool = False,
    ) -> None:
        for command in commands:
            cls._validate_command_missing_variable_policy(
                case_id,
                stage_name,
                command,
                enforce_failure_path_policy,
            )
            if command.get("queries"):
                cls._validate_runtime_queries(
                    case_id,
                    command,
                    case_params,
                    enforce_failure_path_policy,
                )
                continue
            if SqlSafetyValidator.detect_operation(command.get("sql", "")) == "select":
                SqlSafetyValidator.validate_select_sql(case_id, command["sql"])
                command_params = command.get("params") or command.get("params_source") or {}
                cls._validate_bind_params(
                    case_id,
                    command,
                    {**case_params, **command_params},
                    command_params,
                    enforce_failure_path_policy,
                )
                continue
            command_params = command.get("params") or {}
            params = {**case_params, **command_params}
            SqlSafetyValidator.validate_command(case_id, stage_name, command, params)
            cls._validate_bind_params(
                case_id,
                command,
                params,
                command_params,
                enforce_failure_path_policy,
            )

    @staticmethod
    def _validate_bind_params(
        case_id: str,
        command: Dict[str, Any],
        params: Dict[str, Any],
        command_params: Dict[str, Any] | None = None,
        enforce_runtime_param_usage: bool = False,
    ) -> None:
        statement = text(command["sql"])
        # SQL 绑定参数必须都能从命令参数或 case 级公共参数中取得。
        bind_keys = set(statement._bindparams.keys())
        param_keys = set(params.keys())
        missing_params = bind_keys - param_keys
        if missing_params:
            raise ValueError(f"SQL 缺少绑定参数：{case_id}，{', '.join(sorted(missing_params))}")
        unsafe_unused_params = {
            param_name
            for param_name, value in (command_params or {}).items()
            if param_name not in bind_keys and SqlCommandValidator._runtime_context_refs(value)
        }
        if enforce_runtime_param_usage and unsafe_unused_params:
            raise ValueError(
                f"SQL 命令参数包含未被 SQL 使用的运行变量：{case_id}，"
                f"{', '.join(sorted(unsafe_unused_params))}"
            )

    @staticmethod
    def _validate_runtime_queries(
        case_id: str,
        command: Dict[str, Any],
        case_params: Dict[str, Any],
        enforce_runtime_param_usage: bool = False,
    ) -> None:
        params = {**case_params, **(command.get("params_source") or command.get("params") or {})}
        for variable_name, sql in (command.get("queries") or {}).items():
            if not isinstance(variable_name, str) or not variable_name:
                raise ValueError(f"运行期抽取变量名不能为空：{case_id}")
            SqlSafetyValidator.validate_select_sql(case_id, sql)
            SqlCommandValidator._validate_bind_params(
                case_id,
                {"sql": sql},
                params,
                command.get("params_source") or command.get("params") or {},
                enforce_runtime_param_usage,
            )

    @classmethod
    def _validate_command_missing_variable_policy(
        cls,
        case_id: str,
        stage_name: str,
        command: Dict[str, Any],
        enforce_failure_path_policy: bool = False,
    ) -> None:
        variable_names = command.get("skip_if_missing_runtime_vars") or []
        if isinstance(variable_names, str):
            variable_names = [variable_names]
        if not isinstance(variable_names, list) or any(
            not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name)
            for name in variable_names
        ):
            raise TypeError(f"skip_if_missing_runtime_vars 必须是合法变量名列表：{case_id}")
        if not variable_names:
            return
        side_effect_class = command.get("side_effect_class")
        if side_effect_class is None and not enforce_failure_path_policy:
            return
        if side_effect_class not in {"primary", "conditional"}:
            raise ValueError(
                f"配置缺失变量跳过的 SQL 命令必须声明 side_effect_class=primary|conditional："
                f"{case_id}/{command.get('command_id', stage_name)}"
            )
        command_refs = cls._runtime_context_refs(command.get("params") or command.get("params_source") or {})
        unused_skip_vars = set(variable_names) - command_refs
        if unused_skip_vars:
            raise ValueError(
                f"SQL 命令缺失变量策略引用了命令未消费的变量：{case_id}/"
                f"{command.get('command_id', stage_name)}，{sorted(unused_skip_vars)}"
            )

    @classmethod
    def _validate_failure_path_cleanup_contract(cls, case_id: str, commands: Dict[str, Any]) -> None:
        cleanup_commands = commands.get("cleanup") or []
        primary_skip_commands = [
            command
            for command in cleanup_commands
            if command.get("side_effect_class") == "primary"
            and command.get("skip_if_missing_runtime_vars")
        ]
        conditional_skip_commands = [
            command
            for command in cleanup_commands
            if command.get("side_effect_class") == "conditional"
            and command.get("skip_if_missing_runtime_vars")
        ]
        if conditional_skip_commands and not commands.get("final_verify"):
            raise ValueError(f"可选副作用跳过清理时必须提供 scoped final_verify：{case_id}")
        for command in cleanup_commands:
            if command.get("side_effect_class") == "prestate_restore" and command.get("skip_if_missing_runtime_vars"):
                raise ValueError(f"prestate_restore 不得因响应变量缺失而跳过：{case_id}")
        if not primary_skip_commands:
            return

        contract = commands.get("failure_path_cleanup") or {}
        if contract.get("transport_outcome") != "ambiguous":
            raise ValueError(f"主对象清理可能缺少响应 ID 时必须声明 ambiguous transport contract：{case_id}")
        ownership_vars = cls._validated_name_list(case_id, contract, "request_ownership_vars")
        fallback_ids = cls._validated_name_list(case_id, contract, "fallback_runtime_extract_command_ids")
        final_verify_ids = cls._validated_name_list(case_id, contract, "final_verify_command_ids")
        always_restore_ids = cls._validated_name_list(
            case_id,
            contract,
            "always_run_restore_command_ids",
            required=False,
        )
        if not ownership_vars or not fallback_ids or not final_verify_ids:
            raise ValueError(f"failure_path_cleanup 缺少归属键、兜底抽取或最终验证：{case_id}")

        runtime_extract_by_id = cls._commands_by_id(commands.get("runtime_extract") or [])
        cleanup_by_id = cls._commands_by_id(cleanup_commands)
        final_verify_by_id = cls._commands_by_id(commands.get("final_verify") or [])
        cls._require_command_ids(case_id, "runtime_extract", fallback_ids, runtime_extract_by_id)
        cls._require_command_ids(case_id, "cleanup", always_restore_ids, cleanup_by_id)
        cls._require_command_ids(case_id, "final_verify", final_verify_ids, final_verify_by_id)

        missing_primary_vars = {
            str(name)
            for command in primary_skip_commands
            for name in (command.get("skip_if_missing_runtime_vars") or [])
        }
        fallback_outputs = {
            str(name)
            for command_id in fallback_ids
            for name in (runtime_extract_by_id[command_id].get("queries") or {})
        }
        if not missing_primary_vars <= fallback_outputs:
            raise ValueError(
                f"兜底 runtime_extract 未生产主对象清理变量：{case_id}，"
                f"{sorted(missing_primary_vars - fallback_outputs)}"
            )
        for command_id in fallback_ids:
            fallback_refs = cls._runtime_context_refs(
                runtime_extract_by_id[command_id].get("params_source")
                or runtime_extract_by_id[command_id].get("params")
                or {}
            )
            if fallback_refs & missing_primary_vars:
                raise ValueError(f"兜底抽取仍依赖缺失的响应变量：{case_id}/{command_id}")
        for command_id in always_restore_ids:
            command = cleanup_by_id[command_id]
            if command.get("side_effect_class") != "prestate_restore":
                raise ValueError(f"always_run_restore 命令必须声明 prestate_restore：{case_id}/{command_id}")
        final_verify_refs = set().union(
            *(
                cls._runtime_context_refs(final_verify_by_id[command_id].get("params") or {})
                for command_id in final_verify_ids
            )
        )
        if not final_verify_refs & set(ownership_vars):
            raise ValueError(f"failure_path final_verify 未使用请求侧归属变量：{case_id}")

    @staticmethod
    def _runtime_context_refs(value: Any) -> set[str]:
        refs: set[str] = set()
        if isinstance(value, str):
            refs.update(RUNTIME_CONTEXT_PATTERN.findall(value))
        elif isinstance(value, dict):
            for item in value.values():
                refs.update(SqlCommandValidator._runtime_context_refs(item))
        elif isinstance(value, list):
            for item in value:
                refs.update(SqlCommandValidator._runtime_context_refs(item))
        return refs

    @staticmethod
    def _validated_name_list(
        case_id: str,
        contract: Dict[str, Any],
        field_name: str,
        required: bool = True,
    ) -> List[str]:
        values = contract.get(field_name) or []
        if not isinstance(values, list) or any(not isinstance(value, str) or not value for value in values):
            raise TypeError(f"failure_path_cleanup.{field_name} 必须是字符串列表：{case_id}")
        if required and not values:
            raise ValueError(f"failure_path_cleanup.{field_name} 不能为空：{case_id}")
        return values

    @staticmethod
    def _commands_by_id(commands: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        return {
            str(command.get("command_id") or command.get("query_id")): command
            for command in commands
            if command.get("command_id") or command.get("query_id")
        }

    @staticmethod
    def _require_command_ids(
        case_id: str,
        stage_name: str,
        command_ids: Iterable[str],
        commands_by_id: Dict[str, Dict[str, Any]],
    ) -> None:
        missing = sorted(set(command_ids) - set(commands_by_id))
        if missing:
            raise ValueError(f"failure_path_cleanup 引用了不存在的 {stage_name} 命令：{case_id}，{missing}")

    @classmethod
    def _execute_for_validation(cls, connection: Any, case_id: str, stage_name: str, commands: Iterable[Dict[str, Any]]) -> None:
        for command in commands:
            params = command.get("params") or {}
            SqlSafetyValidator.validate_command(case_id, stage_name, command, params)
            boundary = SqlSafetyValidator.capture_mutation_boundary(connection, case_id, stage_name, command, params)
            result = connection.execute(text(command["sql"]), params)
            effect = command.get("expected_effect") or {}
            expected_rows = effect.get("affected_rows")
            if expected_rows is not None and result.rowcount != expected_rows:
                raise AssertionError(
                    f"SQL 运行影响行数不符合预期：{case_id}，"
                    f"实际 {result.rowcount}，期望 {expected_rows}"
                )
            if result.rowcount < effect.get("affected_rows_min", 0) or result.rowcount > effect.get("affected_rows_max", expected_rows if expected_rows is not None else 0):
                raise AssertionError(f"SQL 运行影响行数超出安全边界：{case_id}")
            SqlSafetyValidator.validate_mutation_boundary_after(connection, case_id, stage_name, boundary, params)

    @staticmethod
    def _create_runtime_engines(database_config: Dict[str, Any], connection_url: str) -> Mapping[str, Any]:
        aliases = database_config.get("database_aliases") or {}
        if not aliases:
            return {"default": create_engine(connection_url)}
        engines: Dict[str, Any] = {}
        for alias, alias_url in aliases.items():
            resolved_url = resolve_runtime_value(alias_url, {})
            engines[alias] = create_engine(resolved_url)
        return engines
