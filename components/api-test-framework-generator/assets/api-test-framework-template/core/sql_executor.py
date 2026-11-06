# SQL 执行层，负责用例级 SQL 前置铺数、后置清理、运行期抽取和安全边界校验。
import keyword
import re
import time as time_module
from datetime import date, datetime, time
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple

import allure
from sqlalchemy import text
from sqlalchemy.engine import Engine

from core.runtime_context import publish_runtime_value, resolve_runtime_value
from core.sql_ownership import validate_ownership_sql


class SqlExecutor:
    """统一封装用例级 SQL 前置铺数、运行期抽取、后置清理和最终验证。"""

    def __init__(self, engines: Engine | Mapping[str, Engine], runtime_context: Dict[str, Any]) -> None:
        # 数据库实例由 pytest fixture 统一创建和释放，执行器只负责消费实例执行命令。
        self.engines = dict(engines) if isinstance(engines, Mapping) else {"default": engines}
        self.runtime_context = runtime_context
        self.bound_case_id: Optional[str] = None
        self.bound_case_commands: Optional[Dict[str, Any]] = None
        self.completed_stages: Set[Tuple[str, str]] = set()

    def bind_case(self, case_id: str, case_commands: Dict[str, Any]) -> None:
        self.bound_case_id = case_id
        self.bound_case_commands = case_commands

    def setup(self, case_id: str, commands: Dict[str, Any] | Iterable[Dict[str, Any]]) -> None:
        self._execute_commands(case_id, "SQL 前置铺数", commands, "setup")

    def extract_runtime(self, case_id: str, commands: Dict[str, Any] | Iterable[Dict[str, Any]]) -> None:
        if self._is_stage_completed(case_id, "runtime_extract"):
            with allure.step(f"跳过已尝试 SQL 运行期抽取：{case_id}"):
                return
        # 运行期抽取可能包含长等待；失败后 teardown 只负责清理，不得重复抽取和等待。
        self._mark_stage_completed(case_id, "runtime_extract")
        self._execute_commands(case_id, "SQL 运行期抽取", commands, "runtime_extract")

    def cleanup(self, case_id: str, commands: Dict[str, Any] | Iterable[Dict[str, Any]]) -> None:
        self._execute_commands(case_id, "SQL 后置清理", commands, "cleanup")

    def final_verify(self, case_id: str, commands: Dict[str, Any] | Iterable[Dict[str, Any]]) -> None:
        self._execute_commands(case_id, "SQL 最终验证", commands, "final_verify")

    def run_bound_stage(self, stage_key: str) -> None:
        if not self.bound_case_id or self.bound_case_commands is None:
            raise ValueError("SQL 执行器未绑定当前用例")
        stage_names = {
            "setup": "SQL 前置铺数",
            "runtime_extract": "SQL 运行期抽取",
            "cleanup": "SQL 后置清理",
            "final_verify": "SQL 最终验证",
        }
        stage_name = stage_names.get(stage_key)
        if not stage_name:
            raise ValueError(f"不支持的 SQL 阶段：{stage_key}")
        if stage_key == "runtime_extract":
            self.extract_runtime(self.bound_case_id, self.bound_case_commands)
            return
        self._execute_commands(self.bound_case_id, stage_name, self.bound_case_commands, stage_key)

    def _is_stage_completed(self, case_id: str, stage_key: str) -> bool:
        return (case_id, stage_key) in self.completed_stages

    def _mark_stage_completed(self, case_id: str, stage_key: str) -> None:
        self.completed_stages.add((case_id, stage_key))

    def assert_query(self, case_id: str, rule: Dict[str, Any]) -> None:
        query = rule.get("query") or rule.get("sql")
        if not query:
            raise ValueError(f"数据库断言缺少 query/sql：{case_id}")
        SqlSafetyValidator.validate_select_sql(case_id, query)
        params = self._merged_params({}, rule)
        engine = self._select_engine(rule, query)
        with allure.step(f"SQL 数据库断言：{case_id}/{rule.get('step_id', rule.get('query_id', 'db_assertion'))}"):
            with engine.connect() as connection:
                rows = [dict(row) for row in connection.execute(text(query), params).mappings().all()]
            self._assert_query_rows(case_id, rule, rows)
            self._extract_rows_to_runtime(rule, rows)

    def _execute_commands(self, case_id: str, stage_name: str, payload: Dict[str, Any] | Iterable[Dict[str, Any]], stage_key: str) -> None:
        command_list, case_context = self._stage_payload(payload, stage_key)
        # 没有 SQL 命令时直接返回，支持纯 API 用例复用同一 fixture。
        if not command_list:
            return
        with allure.step(f"{stage_name}：{case_id}"):
            cleanup_errors: List[Exception] = []
            for command in command_list:
                missing_command_vars = self._missing_command_skip_vars(command)
                if missing_command_vars:
                    with allure.step(f"跳过可选 SQL 命令：{command.get('command_id', case_id)}"):
                        allure.attach(
                            "未产生可选副作用变量：" + ", ".join(missing_command_vars),
                            name="SQL 命令跳过原因",
                            attachment_type=allure.attachment_type.TEXT,
                        )
                    continue
                try:
                    self._execute_command(case_id, stage_name, command, case_context)
                except Exception as error:
                    if stage_key != "cleanup":
                        raise
                    cleanup_errors.append(error)
            if cleanup_errors:
                details = "；".join(str(error) for error in cleanup_errors)
                raise AssertionError(
                    f"SQL 后置清理存在 {len(cleanup_errors)} 个失败命令：{case_id}；{details}"
                ) from cleanup_errors[0]

    def _execute_command(self, case_id: str, stage_name: str, command: Dict[str, Any], case_context: Dict[str, Any]) -> None:
        sql = command.get("sql")
        if not sql:
            if command.get("queries"):
                self._execute_runtime_queries(case_id, command, case_context)
                return
            raise ValueError(f"{stage_name}命令缺少 sql：{case_id}")

        params = self._merged_params(case_context, command)
        operation = SqlSafetyValidator.detect_operation(sql)
        if operation == "select":
            self._execute_select_command(case_id, command, sql, params)
            return

        SqlSafetyValidator.validate_command(case_id, stage_name, command, params)
        engine = self._select_engine(command, sql, case_context)
        with engine.begin() as connection:
            boundary = SqlSafetyValidator.capture_mutation_boundary(connection, case_id, stage_name, command, params)
            result = connection.execute(text(sql), params)
            self._assert_mutation_effect(case_id, stage_name, command, result.rowcount)
            SqlSafetyValidator.validate_mutation_boundary_after(connection, case_id, stage_name, boundary, params)
            self._verify_expected_effect(connection, case_id, command, params)
            self._extract_setup_identity(connection, command, params)

    def _execute_select_command(self, case_id: str, command: Dict[str, Any], sql: str, params: Dict[str, Any]) -> None:
        SqlSafetyValidator.validate_select_sql(case_id, sql)
        engine = self._select_engine(command, sql)
        with engine.connect() as connection:
            rows = [dict(row) for row in connection.execute(text(sql), params).mappings().all()]
        self._assert_query_rows(case_id, command, rows)
        self._extract_secret_outputs(command, rows)
        self._extract_rows_to_runtime(command, rows)

    def _execute_runtime_queries(self, case_id: str, command: Dict[str, Any], case_context: Dict[str, Any]) -> None:
        params = self._merged_params(case_context, command, params_key="params_source")
        queries = command.get("queries") or {}
        if not isinstance(queries, dict) or not queries:
            raise ValueError(f"运行期抽取命令必须提供 queries：{case_id}")
        expected_effect = command.get("expected_effect") or {}
        poll_config = command.get("poll_until_expected")
        wait_seconds = command.get("wait_seconds_before_queries", 0)
        if poll_config and wait_seconds:
            raise ValueError(f"SQL 运行期抽取不能同时配置固定等待和有界轮询：{case_id}")
        if poll_config:
            values = self._poll_runtime_queries_until_expected(
                case_id, command, case_context, params, queries, expected_effect, poll_config
            )
            self._publish_runtime_query_values(values)
            return
        if wait_seconds:
            wait_seconds = int(self._resolve_value(wait_seconds))
            if wait_seconds < 0:
                raise ValueError(f"SQL 运行期抽取等待秒数不能小于 0：{case_id}")
            with allure.step(f"SQL 运行期抽取前等待异步窗口：{wait_seconds} 秒"):
                time_module.sleep(wait_seconds)
        values = self._collect_runtime_query_values(case_id, command, case_context, params, queries, expected_effect)
        self._publish_runtime_query_values(values)

    def _poll_runtime_queries_until_expected(
        self,
        case_id: str,
        command: Dict[str, Any],
        case_context: Dict[str, Any],
        params: Dict[str, Any],
        queries: Dict[str, str],
        expected_effect: Dict[str, Any],
        poll_config: Any,
    ) -> Dict[str, Any]:
        if not isinstance(poll_config, dict):
            raise TypeError(f"poll_until_expected 必须是对象：{case_id}")
        timeout_seconds = int(self._resolve_value(poll_config.get("timeout_seconds", 0)))
        interval_seconds = int(self._resolve_value(poll_config.get("interval_seconds", 0)))
        if timeout_seconds < 0:
            raise ValueError(f"SQL 有界轮询超时秒数不能小于 0：{case_id}")
        if interval_seconds <= 0:
            raise ValueError(f"SQL 有界轮询间隔秒数必须大于 0：{case_id}")

        deadline = time_module.monotonic() + timeout_seconds
        attempt = 0
        with allure.step(f"SQL 运行期有界轮询：最多 {timeout_seconds} 秒，每 {interval_seconds} 秒一次"):
            while True:
                attempt += 1
                try:
                    values = self._collect_runtime_query_values(
                        case_id, command, case_context, params, queries, expected_effect
                    )
                    allure.attach(
                        str(attempt),
                        name="SQL 轮询命中次数",
                        attachment_type=allure.attachment_type.TEXT,
                    )
                    return values
                except AssertionError as error:
                    remaining_seconds = deadline - time_module.monotonic()
                    if remaining_seconds <= 0:
                        raise AssertionError(
                            f"SQL 有界轮询超时：{case_id}，尝试 {attempt} 次，最后结果：{error}"
                        ) from error
                    time_module.sleep(min(interval_seconds, remaining_seconds))

    def _collect_runtime_query_values(
        self,
        case_id: str,
        command: Dict[str, Any],
        case_context: Dict[str, Any],
        params: Dict[str, Any],
        queries: Dict[str, str],
        expected_effect: Dict[str, Any],
    ) -> Dict[str, Any]:
        values: Dict[str, Any] = {}
        for variable_name, sql in queries.items():
            SqlSafetyValidator.validate_select_sql(case_id, sql)
            engine = self._select_engine(command, sql, case_context)
            with engine.connect() as connection:
                rows = [dict(row) for row in connection.execute(text(sql), params).mappings().all()]
            expected_count = expected_effect.get(f"{variable_name}_row_count", expected_effect.get("every_query_row_count"))
            optional_query_names = set(command.get("optional_query_names") or [])
            if variable_name in optional_query_names and not rows:
                continue
            if expected_count is None and variable_name.endswith("_id"):
                expected_count = expected_effect.get(f"{variable_name[:-3]}_row_count")
            if expected_count is not None and len(rows) != expected_count:
                raise AssertionError(f"运行期抽取行数不符合预期：{case_id}/{variable_name}，实际 {len(rows)}，期望 {expected_count}")
            if not rows:
                raise AssertionError(f"运行期抽取未查询到数据：{case_id}/{variable_name}")
            first_row = rows[0]
            value = first_row.get(variable_name)
            if value is None and len(first_row) == 1:
                value = next(iter(first_row.values()))
            if value is None:
                raise AssertionError(f"运行期抽取结果缺少字段：{case_id}/{variable_name}")
            expected_value = expected_effect.get(variable_name)
            if expected_value is not None:
                resolved_expected = self._resolve_value(expected_value)
                if not self._values_equal(value, resolved_expected):
                    raise AssertionError(f"运行期抽取字段不符合预期：{case_id}/{variable_name}，实际 {value}，期望 {resolved_expected}")
            values[variable_name] = value
        return values

    def _publish_runtime_query_values(self, values: Dict[str, Any]) -> None:
        for variable_name, value in values.items():
            publish_runtime_value(self.runtime_context, variable_name, value)

    def _resolve_value(self, value: Any) -> Any:
        return resolve_runtime_value(value, self.runtime_context)

    def _missing_command_skip_vars(self, command: Dict[str, Any]) -> List[str]:
        variable_names = command.get("skip_if_missing_runtime_vars") or []
        if isinstance(variable_names, str):
            variable_names = [variable_names]
        if not isinstance(variable_names, list):
            raise TypeError("skip_if_missing_runtime_vars 必须是字符串或字符串列表")
        return [
            str(variable_name)
            for variable_name in variable_names
            if self.runtime_context.get(str(variable_name)) in (None, "")
        ]

    def _values_equal(self, actual_value: Any, expected_value: Any) -> bool:
        if actual_value == expected_value:
            return True
        if not self._is_temporal_comparison(actual_value, expected_value):
            return False
        return bool(
            self._temporal_comparison_values(actual_value)
            & self._temporal_comparison_values(expected_value)
        )

    @classmethod
    def _is_temporal_comparison(cls, actual_value: Any, expected_value: Any) -> bool:
        return cls._is_temporal_value(actual_value) or cls._is_temporal_value(expected_value)

    @staticmethod
    def _is_temporal_value(value: Any) -> bool:
        return isinstance(value, (datetime, date, time))

    @classmethod
    def _temporal_comparison_values(cls, value: Any) -> Set[str]:
        parsed_value = cls._parse_temporal_value(value)
        if parsed_value is None:
            return {str(value).strip() if isinstance(value, str) else str(value)}
        if isinstance(parsed_value, datetime):
            return cls._datetime_text_values(parsed_value)
        if isinstance(parsed_value, date):
            return {parsed_value.isoformat(), str(parsed_value)}
        return cls._time_text_values(parsed_value)

    @staticmethod
    def _parse_temporal_value(value: Any) -> datetime | date | time | None:
        if isinstance(value, (datetime, date, time)):
            return value
        if not isinstance(value, str):
            return None
        text_value = value.strip()
        if not text_value:
            return None
        normalized_text = text_value[:-1] + "+00:00" if text_value.endswith("Z") else text_value
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized_text):
            return date.fromisoformat(normalized_text)
        for parser in (datetime.fromisoformat, date.fromisoformat, time.fromisoformat):
            try:
                return parser(normalized_text)
            except ValueError:
                continue
        return None

    @staticmethod
    def _datetime_text_values(value: datetime) -> Set[str]:
        values = {str(value), value.isoformat(sep=" "), value.isoformat()}
        if value.microsecond == 0:
            values.add(value.strftime("%Y-%m-%d %H:%M:%S"))
            values.add(value.strftime("%Y-%m-%dT%H:%M:%S"))
        return values

    @staticmethod
    def _time_text_values(value: time) -> Set[str]:
        values = {str(value), value.isoformat()}
        if value.microsecond == 0:
            values.add(value.strftime("%H:%M:%S"))
        return values

    def _merged_params(
        self,
        case_context: Dict[str, Any],
        command: Dict[str, Any],
        params_key: str = "params",
    ) -> Dict[str, Any]:
        case_params = self._resolve_value(case_context.get("params") or {})
        command_params = self._resolve_value(command.get(params_key) or command.get("params") or {})
        merged = {**case_params, **command_params}
        for param_name in merged:
            self._validate_variable_name(param_name, "SQL 参数名")
        return merged

    def _stage_payload(
        self,
        payload: Dict[str, Any] | Iterable[Dict[str, Any]],
        stage_key: str,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        if isinstance(payload, dict):
            return list(payload.get(stage_key) or []), payload
        return list(payload), {}

    def _select_engine(
        self,
        command: Dict[str, Any],
        sql: str,
        case_context: Optional[Dict[str, Any]] = None,
    ) -> Engine:
        alias = command.get("database_alias") or command.get("database")
        if not alias and case_context:
            alias = case_context.get("database_alias")
        if not alias:
            alias = SqlSafetyValidator.extract_database_alias(sql)
        if alias and alias in self.engines:
            return self.engines[alias]
        if alias and "default" in self.engines and len(self.engines) == 1:
            return self.engines["default"]
        if not alias and len(self.engines) == 1:
            return next(iter(self.engines.values()))
        raise ValueError(f"无法选择数据库连接 alias：{alias or '未声明'}")

    def _assert_mutation_effect(self, case_id: str, stage_name: str, command: Dict[str, Any], rowcount: int) -> None:
        expected_effect = command.get("expected_effect") or {}
        if "affected_rows" in expected_effect and rowcount != expected_effect["affected_rows"]:
            raise AssertionError(
                f"{stage_name}影响行数不符合预期：{case_id}，实际 {rowcount}，期望 {expected_effect['affected_rows']}"
            )
        if "affected_rows_min" in expected_effect and rowcount < expected_effect["affected_rows_min"]:
            raise AssertionError(
                f"{stage_name}影响行数低于预期：{case_id}，实际 {rowcount}，最小 {expected_effect['affected_rows_min']}"
            )
        if "affected_rows_max" in expected_effect and rowcount > expected_effect["affected_rows_max"]:
            raise AssertionError(f"{stage_name}影响行数超过上限：{case_id}")

    def _verify_expected_effect(self, connection: Any, case_id: str, command: Dict[str, Any], params: Dict[str, Any]) -> None:
        expected_effect = command.get("expected_effect") or {}
        verification_query = expected_effect.get("verification_query")
        if not verification_query:
            return
        SqlSafetyValidator.validate_select_sql(case_id, verification_query)
        rows = [dict(row) for row in connection.execute(text(verification_query), params).mappings().all()]
        self._assert_expected_fields(case_id, rows, expected_effect)

    def _extract_setup_identity(self, connection: Any, command: Dict[str, Any], params: Dict[str, Any]) -> None:
        identity = command.get("setup_identity") or {}
        value_ref = identity.get("value_ref")
        verification_query = (command.get("expected_effect") or {}).get("verification_query")
        if not value_ref or not value_ref.startswith("runtime_context.") or not verification_query:
            return
        rows = [dict(row) for row in connection.execute(text(verification_query), params).mappings().all()]
        if not rows or "id" not in rows[0]:
            raise AssertionError(f"SQL 前置铺数未能抽取 setup_identity：{command.get('command_id')}")
        publish_runtime_value(self.runtime_context, value_ref.split(".", 1)[1], rows[0]["id"])

    def _assert_query_rows(self, case_id: str, rule: Dict[str, Any], rows: List[Dict[str, Any]]) -> None:
        expected = rule.get("expected") or {}
        expected_count = rule.get("expected_count") or rule.get("expected_row_count")
        expected_effect = rule.get("expected_effect") or {}
        if expected_count is None:
            expected_count = expected_effect.get("row_count")
        if expected_count is not None and len(rows) != expected_count:
            raise AssertionError(f"SQL 查询行数不符合预期：{case_id}，实际 {len(rows)}，期望 {expected_count}")
        if expected or rule.get("expected_row"):
            self._assert_expected_fields(case_id, rows, {**expected, **(rule.get("expected_row") or {})})
        else:
            self._assert_expected_fields(case_id, rows, expected_effect)

    def _assert_expected_fields(self, case_id: str, rows: List[Dict[str, Any]], expected_map: Dict[str, Any]) -> None:
        expected_fields = {
            key[len("expected_"):]: value
            for key, value in expected_map.items()
            if key.startswith("expected_") and key not in {"expected_count", "expected_row_count"}
        }
        direct_fields = {
            key: value
            for key, value in expected_map.items()
            if not key.startswith("expected_")
            and key not in {"affected_rows", "affected_rows_min", "verification_query", "row_count"}
        }
        expected_fields.update(direct_fields)
        if not expected_fields:
            return
        if not rows:
            raise AssertionError(f"SQL 查询未返回可断言数据：{case_id}")
        first_row = rows[0]
        for field_name, expected_value in expected_fields.items():
            normalized_field_name = field_name.split(".")[-1]
            if normalized_field_name not in first_row:
                raise AssertionError(f"SQL 查询结果缺少字段：{case_id}/{normalized_field_name}")
            resolved_expected = self._resolve_value(expected_value)
            actual_value = first_row[normalized_field_name]
            if not self._values_equal(actual_value, resolved_expected):
                raise AssertionError(
                    f"SQL 查询字段不符合预期：{case_id}/{normalized_field_name}，实际 {actual_value}，期望 {resolved_expected}"
                )

    def _extract_rows_to_runtime(self, rule: Dict[str, Any], rows: List[Dict[str, Any]]) -> None:
        extract_names = rule.get("extract_to_runtime_context") or []
        if not extract_names:
            return
        if not rows:
            raise AssertionError(f"SQL 抽取没有查询到数据：{rule.get('step_id', rule.get('query_id', 'db_assertion'))}")
        for name in extract_names:
            value = self._extract_named_value(name, rows)
            publish_runtime_value(self.runtime_context, name, value)

    def _extract_secret_outputs(self, rule: Dict[str, Any], rows: List[Dict[str, Any]]) -> None:
        output_variables = rule.get("output_variables") or {}
        if not output_variables:
            return
        if not rows:
            raise AssertionError(f"SQL secret 输出没有查询到数据：{rule.get('command_id', 'sql_secret_select')}")
        secret_context = self.runtime_context.setdefault("secret_context", {})
        for name, policy in output_variables.items():
            if not isinstance(policy, dict) or policy.get("never_persist_plaintext") is not True:
                raise ValueError(f"secret 输出必须声明 never_persist_plaintext：{name}")
            if name not in rows[0]:
                raise AssertionError(f"SQL secret 输出缺少字段：{name}")
            secret_context[name] = rows[0][name]

    @staticmethod
    def _extract_named_value(name: str, rows: List[Dict[str, Any]]) -> Any:
        field_name = name.split(".")[-1]
        if field_name in rows[0]:
            return rows[0][field_name]
        if field_name.endswith("_id") and "id" in rows[0]:
            return rows[0]["id"]
        if len(rows) == 2 and field_name.startswith("dialer_before_"):
            source_field = field_name.replace("dialer_before_", "")
            return rows[0][source_field]
        if len(rows) == 2 and field_name.startswith("picker_before_"):
            source_field = field_name.replace("picker_before_", "")
            return rows[1][source_field]
        if len(rows[0]) == 1:
            return next(iter(rows[0].values()))
        raise AssertionError(f"SQL 抽取结果缺少字段：{name}")

    @staticmethod
    def _validate_variable_name(variable_name: str, scene: str) -> None:
        if not isinstance(variable_name, str) or not variable_name.isidentifier() or keyword.iskeyword(variable_name):
            raise ValueError(f"{scene}变量名必须符合 Python 标识符规则且不能是关键字：{variable_name}")


class CaseSqlCommandLoader:
    """按用例 ID 读取 SQL 命令清单。"""

    REQUIRED_QUALITY_CHECKS = (
        "table_structure_verified",
        "knowledge_graph_verified",
        "ownership_boundary_verified",
        "cleanup_scope_verified",
        "id_cleanup_verified",
        "insert_exit_gate_verified",
        "delete_exit_gate_verified",
        "api_insufficiency_verified",
        "seed_scope_guard_verified",
        "dangerous_sql_rejected",
        "sql_syntax_verified",
        "sql_logic_verified",
        "runtime_validation_verified",
    )
    SETUP_QUALITY_CHECKS = (
        "historical_shape_reference_verified",
    )

    @staticmethod
    def get_case_commands(sql_commands: Dict[str, Any], case_id: str, require_runtime: bool = True) -> Dict[str, Any]:
        # 运行期默认要求 SQL 生成门禁和运行预检都已通过；静态校验可显式关闭运行预检要求。
        allowed_tables = CaseSqlCommandLoader.validate_generation_gate(sql_commands, require_runtime=require_runtime)
        cases = sql_commands.get("cases") or {}
        case_commands = cases.get(case_id)
        if case_commands is None:
            raise KeyError(f"SQL 命令文件中不存在用例：{case_id}")
        commands = {
            "setup": case_commands.get("setup") or [],
            "runtime_extract": case_commands.get("runtime_extract") or [],
            "cleanup": case_commands.get("cleanup") or [],
            "final_verify": case_commands.get("final_verify") or [],
            "params": case_commands.get("params") or {},
            "database_alias": case_commands.get("database_alias"),
            "database_aliases": case_commands.get("database_aliases") or [],
            "source_refs": case_commands.get("source_refs") or [],
            "target_tables": case_commands.get("target_tables") or [],
            "failure_path_cleanup": case_commands.get("failure_path_cleanup") or {},
        }
        CaseSqlCommandLoader.validate_case_tables(case_id, commands, allowed_tables)
        return commands

    @classmethod
    def validate_generation_gate(cls, sql_commands: Dict[str, Any], require_runtime: bool = False) -> Set[str]:
        gate = sql_commands.get("sql_generation_gate") or {}
        if gate.get("status") != "passed" or gate.get("passed") is not True:
            raise ValueError(f"SQL 生成准出门禁未通过：{gate.get('reason', '未提供原因')}")

        quality_checks = gate.get("quality_checks") or {}
        if not isinstance(quality_checks, dict):
            raise ValueError("SQL 生成准出门禁 quality_checks 必须是对象")

        required_checks = [
            name
            for name in cls.REQUIRED_QUALITY_CHECKS
            if require_runtime or name != "runtime_validation_verified"
        ]
        if cls._has_mutating_setup_commands(sql_commands):
            required_checks.extend(cls.SETUP_QUALITY_CHECKS)
        missing_checks = [name for name in required_checks if name not in quality_checks]
        failed_checks = [name for name in required_checks if quality_checks.get(name) is not True]
        # 缺少任何质量门禁字段都不能进入 SQL 执行。
        if missing_checks:
            raise ValueError(f"SQL 质量校验缺少必填项：{', '.join(missing_checks)}")
        if failed_checks:
            raise ValueError(f"SQL 质量校验未通过：{', '.join(failed_checks)}")

        allowed_tables = gate.get("allowed_tables") or []
        if not isinstance(allowed_tables, list) or not allowed_tables:
            raise ValueError("SQL 生成准出门禁必须提供 allowed_tables")
        return set(allowed_tables)

    @staticmethod
    def _has_mutating_setup_commands(sql_commands: Dict[str, Any]) -> bool:
        cases = sql_commands.get("cases") or {}
        if not isinstance(cases, dict):
            return False
        for case_commands in cases.values():
            for command in (case_commands or {}).get("setup") or []:
                normalized_sql = str(command.get("sql") or "").strip().lower()
                if re.match(r"^(insert|update)\b", normalized_sql):
                    return True
        return False

    @staticmethod
    def validate_case_tables(case_id: str, commands: Dict[str, Any], allowed_tables: Set[str]) -> None:
        for stage_key in ("setup", "runtime_extract", "cleanup", "final_verify"):
            stage_commands = commands.get(stage_key) or []
            for command in stage_commands:
                target_tables = set(command.get("target_tables") or ([command["table"]] if command.get("table") else []))
                if not target_tables and command.get("queries"):
                    continue
                if not target_tables and SqlSafetyValidator.detect_operation(command.get("sql", "")) == "select":
                    continue
                if not target_tables:
                    raise ValueError(f"SQL 命令缺少目标表清单：{case_id}")
                extra_tables = target_tables - allowed_tables
                if extra_tables:
                    raise ValueError(f"SQL 命令包含未准出的目标表：{case_id}，{', '.join(sorted(extra_tables))}")
                # 比对声明目标表和 SQL 实际目标表，防止产物声明与执行不一致。
                sql = command.get("sql", "")
                if not sql:
                    continue
                sql_tables = SqlSafetyValidator.extract_target_tables(sql)
                if sql_tables and sql_tables != target_tables:
                    raise ValueError(
                        f"SQL 真实目标表与声明不一致：{case_id}，"
                        f"声明 {', '.join(sorted(target_tables))}，"
                        f"实际 {', '.join(sorted(sql_tables))}"
                    )


class SqlSafetyValidator:
    """执行 SQL 前进行安全边界校验。"""

    DANGEROUS_KEYWORDS = ("drop", "truncate", "alter", "create", "grant", "revoke", "replace")
    SETUP_ALLOWED_OPERATIONS = {"insert", "update", "select"}
    EXTRACT_ALLOWED_OPERATIONS = {"select"}
    CLEANUP_ALLOWED_OPERATIONS = {"delete", "update"}

    @classmethod
    def validate_command(cls, case_id: str, stage_name: str, command: Dict[str, Any], params: Dict[str, Any]) -> None:
        sql = command.get("sql", "")
        normalized_sql = cls._normalize_sql(sql)
        operation = cls._operation(normalized_sql)
        cls._validate_metadata(case_id, stage_name, command, operation)
        cls._validate_expected_effect(case_id, command)
        cls._validate_statement_shape(case_id, normalized_sql)
        cls._validate_operation(case_id, stage_name, operation)
        cls._validate_scope(case_id, operation, normalized_sql, command, params)

    @classmethod
    def capture_mutation_boundary(cls, connection: Any, case_id: str, stage_name: str, command: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        operation = cls.detect_operation(command.get("sql", ""))
        if operation not in {"insert", "delete"} or "id" not in params:
            return {}
        target_table = cls._single_target_table_or_none(command)
        if not target_table:
            return {}
        expected_rows = (command.get("expected_effect") or {}).get("affected_rows")
        if expected_rows is None:
            return {}
        before_count = cls._count_by_id(connection, target_table, params)
        if operation == "insert" and before_count != 0:
            raise AssertionError(f"{stage_name}新增前已存在相同 id 数据：{case_id}，表：{target_table}，id：{params['id']}")
        if operation == "delete" and before_count != expected_rows:
            raise AssertionError(
                f"{stage_name}删除前命中行数不符合准出门禁：{case_id}，"
                f"表：{target_table}，实际：{before_count}，期望：{expected_rows}"
            )
        return {
            "operation": operation,
            "target_table": target_table,
            "before_count": before_count,
            "expected_rows": expected_rows,
        }

    @classmethod
    def validate_mutation_boundary_after(cls, connection: Any, case_id: str, stage_name: str, boundary: Dict[str, Any], params: Dict[str, Any]) -> None:
        if not boundary:
            return
        after_count = cls._count_by_id(connection, boundary["target_table"], params)
        operation = boundary["operation"]
        expected_rows = boundary["expected_rows"]
        if operation == "insert" and after_count != expected_rows:
            raise AssertionError(
                f"{stage_name}新增后数据行数不符合准出门禁：{case_id}，"
                f"表：{boundary['target_table']}，实际：{after_count}，期望：{expected_rows}"
            )
        if operation == "delete" and after_count != boundary["before_count"] - expected_rows:
            raise AssertionError(
                f"{stage_name}删除后数据行数不符合准出门禁：{case_id}，"
                f"表：{boundary['target_table']}，实际：{after_count}，"
                f"期望：{boundary['before_count'] - expected_rows}"
            )

    @classmethod
    def extract_target_tables(cls, sql: str) -> Set[str]:
        normalized_sql = cls._normalize_sql(sql)
        operation = cls._operation(normalized_sql)
        patterns = {
            "insert": r"^insert\s+into\s+((?:`[^`]+`|[a-zA-Z_][\w-]*)(?:\.(?:`[^`]+`|[a-zA-Z_][\w-]*))?)\b",
            "update": r"^update\s+((?:`[^`]+`|[a-zA-Z_][\w-]*)(?:\.(?:`[^`]+`|[a-zA-Z_][\w-]*))?)\b",
            "delete": r"^delete\s+from\s+((?:`[^`]+`|[a-zA-Z_][\w-]*)(?:\.(?:`[^`]+`|[a-zA-Z_][\w-]*))?)\b",
        }
        if operation == "select":
            return set()
        pattern = patterns.get(operation)
        if pattern is None:
            raise ValueError("无法识别 SQL 目标表")
        match = re.search(pattern, normalized_sql)
        if not match:
            raise ValueError("无法识别 SQL 目标表")
        return {match.group(1).split(".")[-1].replace("`", "")}

    @classmethod
    def detect_operation(cls, sql: str) -> str:
        return cls._operation(cls._normalize_sql(sql))

    @classmethod
    def validate_select_sql(cls, case_id: str, sql: str) -> None:
        normalized_sql = cls._normalize_sql(sql)
        cls._validate_statement_shape(case_id, normalized_sql)
        if cls._operation(normalized_sql) != "select":
            raise ValueError(f"只允许执行 SELECT 查询：{case_id}")

    @staticmethod
    def extract_database_alias(sql: str) -> Optional[str]:
        match = re.search(r"`([^`]+)`\.", sql)
        if match:
            return match.group(1)
        return None

    @classmethod
    def _validate_metadata(cls, case_id: str, stage_name: str, command: Dict[str, Any], operation: str) -> None:
        if not command.get("source_evidence") and not command.get("source_refs") and not command.get("command_id"):
            raise ValueError(f"SQL 命令缺少来源证据：{case_id}")
        target_tables = command.get("target_tables") or ([command["table"]] if command.get("table") else [])
        if not isinstance(target_tables, list) or not target_tables:
            raise ValueError(f"SQL 命令缺少目标表清单：{case_id}")
        if "后置清理" in stage_name and not command.get("cleanup_identity") and command.get("action_type") != "sql_restore":
            raise ValueError(f"SQL 后置清理缺少 cleanup_identity：{case_id}")
        command_params = command.get("params") or {}
        for param_name in command_params:
            cls._validate_python_identifier(case_id, param_name, "SQL 参数名")
        ownership = command.get("ownership") or {}
        ownership_keys = ownership.get("keys")
        if "后置清理" in stage_name and command.get("action_type") != "sql_restore":
            if not isinstance(ownership_keys, list) or not ownership_keys:
                raise ValueError(f"SQL 命令缺少测试数据归属键：{case_id}")
        if "前置铺数" in stage_name and operation in {"insert", "update"}:
            cls._validate_historical_shape_reference(case_id, command)

    @staticmethod
    def _validate_historical_shape_reference(case_id: str, command: Dict[str, Any]) -> None:
        historical_shape_reference = command.get("historical_shape_reference")
        if not isinstance(historical_shape_reference, dict):
            raise ValueError(f"SQL 前置铺数缺少历史形态引用证据：{case_id}")
        if historical_shape_reference.get("status") != "passed":
            raise ValueError(f"SQL 前置铺数历史形态引用证据未通过：{case_id}")
        for field_name in ("source_ref", "sampled_table", "sample_scope", "privacy_status"):
            if not historical_shape_reference.get(field_name):
                raise ValueError(f"SQL 前置铺数历史形态引用证据缺少字段 {field_name}：{case_id}")
        sample_count = historical_shape_reference.get("sample_count")
        if not isinstance(sample_count, int) or sample_count <= 0:
            raise ValueError(f"SQL 前置铺数历史形态引用证据 sample_count 必须为正整数：{case_id}")
        verified_fields = historical_shape_reference.get("verified_fields")
        if not isinstance(verified_fields, list) or not verified_fields:
            raise ValueError(f"SQL 前置铺数历史形态引用证据缺少 verified_fields：{case_id}")
        if historical_shape_reference.get("privacy_status") != "sampled_shape_only_redacted":
            raise ValueError(f"SQL 前置铺数历史形态引用证据未脱敏：{case_id}")

    @classmethod
    def _validate_statement_shape(cls, case_id: str, normalized_sql: str) -> None:
        sql_without_tail = normalized_sql[:-1] if normalized_sql.endswith(";") else normalized_sql
        if ";" in sql_without_tail:
            raise ValueError(f"禁止单条命令包含多条 SQL：{case_id}")
        if any(re.search(rf"\b{keyword}\b", normalized_sql) for keyword in cls.DANGEROUS_KEYWORDS):
            raise ValueError(f"禁止执行危险 SQL：{case_id}")

    @staticmethod
    def _validate_python_identifier(case_id: str, name: str, scene: str) -> None:
        if not isinstance(name, str) or not name.isidentifier() or keyword.iskeyword(name):
            raise ValueError(f"{scene}必须符合 Python 标识符规则且不能是关键字：{case_id}，{name}")

    @staticmethod
    def _validate_expected_effect(case_id: str, command: Dict[str, Any]) -> None:
        expected_effect = command.get("expected_effect") or {}
        if not any(key in expected_effect for key in ("affected_rows", "affected_rows_min")):
            raise ValueError(f"写 SQL 命令必须声明 expected_effect.affected_rows 或 affected_rows_min：{case_id}")
        if "affected_rows" not in expected_effect and "affected_rows_max" not in expected_effect:
            raise ValueError(f"写 SQL 必须声明精确 affected_rows 或 affected_rows_max 上限：{case_id}")
        for key in ("affected_rows", "affected_rows_min", "affected_rows_max"):
            if key not in expected_effect:
                continue
            affected_rows = expected_effect[key]
            if type(affected_rows) is not int or affected_rows < 0:
                raise ValueError(f"expected_effect.{key} 必须是非负整数：{case_id}")
        if expected_effect.get("affected_rows_min", 0) > expected_effect.get("affected_rows_max", expected_effect.get("affected_rows", 0)):
            raise ValueError(f"SQL 影响行数下限不能大于上限：{case_id}")

    @classmethod
    def _validate_operation(cls, case_id: str, stage_name: str, operation: str) -> None:
        if "前置铺数" in stage_name and operation not in cls.SETUP_ALLOWED_OPERATIONS:
            raise ValueError(f"SQL 前置铺数仅允许 SELECT/INSERT/UPDATE：{case_id}")
        if "运行期抽取" in stage_name and operation not in cls.EXTRACT_ALLOWED_OPERATIONS:
            raise ValueError(f"SQL 运行期抽取仅允许 SELECT：{case_id}")
        if "后置清理" in stage_name and operation not in cls.CLEANUP_ALLOWED_OPERATIONS:
            raise ValueError(f"SQL 后置清理仅允许 DELETE/UPDATE：{case_id}")

    @classmethod
    def _validate_scope(cls, case_id: str, operation: str, normalized_sql: str, command: Dict[str, Any], params: Dict[str, Any]) -> None:
        if operation in {"delete", "update"} and not re.search(r"\bwhere\b", normalized_sql):
            raise ValueError(f"DELETE/UPDATE 必须包含 WHERE 条件：{case_id}")
        if re.search(r"\bwhere\s+1\s*=\s*1\b", normalized_sql) or re.search(r"\bor\s+1\s*=\s*1\b", normalized_sql):
            raise ValueError(f"禁止使用无边界 WHERE 条件：{case_id}")
        if re.search(r"\blike\s+['\"]%['\"]", normalized_sql):
            raise ValueError(f"禁止使用全量 LIKE 条件：{case_id}")
        cls._validate_like_params(case_id, normalized_sql, params)
        if operation in {"delete", "update"}:
            cls._validate_where_uses_bound_param(case_id, normalized_sql, set(params.keys()))
            validate_ownership_sql(command["sql"], command, params)

    @staticmethod
    def _single_target_table_or_none(command: Dict[str, Any]) -> Optional[str]:
        target_tables = command.get("target_tables") or ([command["table"]] if command.get("table") else [])
        if len(target_tables) != 1:
            return None
        target_table = target_tables[0]
        if not isinstance(target_table, str) or not re.match(r"^[a-zA-Z_]\w*$", target_table):
            return None
        return target_table

    @staticmethod
    def _count_by_id(connection: Any, target_table: str, params: Dict[str, Any]) -> int:
        result = connection.execute(text(f"SELECT COUNT(*) FROM {target_table} WHERE id = :id"), {"id": params["id"]})
        return int(result.scalar_one())

    @staticmethod
    def _validate_like_params(case_id: str, normalized_sql: str, params: Dict[str, Any]) -> None:
        like_param_names = re.findall(r"\blike\s+:([a-zA-Z_]\w*)\b", normalized_sql)
        for param_name in like_param_names:
            param_value = params.get(param_name)
            if isinstance(param_value, str) and "%" in param_value:
                raise ValueError(f"禁止使用模糊 LIKE 参数清理数据：{case_id}")

    @staticmethod
    def _validate_where_uses_bound_param(case_id: str, normalized_sql: str, param_keys: Set[str]) -> None:
        where_match = re.search(r"\bwhere\b(.+?);?$", normalized_sql)
        if not where_match:
            raise ValueError(f"DELETE/UPDATE 必须包含 WHERE 条件：{case_id}")
        where_clause = where_match.group(1)
        matched_params = [key for key in param_keys if re.search(rf":{re.escape(key)}\b", where_clause)]
        if not matched_params:
            raise ValueError(f"DELETE/UPDATE 的 WHERE 必须使用绑定参数限定范围：{case_id}")

    @staticmethod
    def _normalize_sql(sql: str) -> str:
        return re.sub(r"\s+", " ", sql.strip().lower())

    @staticmethod
    def _operation(normalized_sql: str) -> str:
        match = re.match(r"^([a-z]+)\b", normalized_sql)
        if not match:
            raise ValueError("无法识别 SQL 操作类型")
        return match.group(1)
