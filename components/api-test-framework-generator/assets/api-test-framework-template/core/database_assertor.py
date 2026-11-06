# 数据库断言层，通过 pytest fixture 提供的数据库实例执行落库查询断言。
import keyword
import re
from typing import Any, Dict, Iterable, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine


class DatabaseAssertor:
    """基于数据库 fixture 查询落库结果，并使用 assert 校验行数和字段。"""

    def __init__(self, engine: Engine, runtime_context: Dict[str, Any], marker_rules: Optional[Iterable[Dict[str, Any]]] = None) -> None:
        self.engine = engine
        self.runtime_context = runtime_context
        self.marker_rules = list(marker_rules or [])

    def assert_marker_rules(self) -> None:
        for rule in self.marker_rules:
            self.assert_persistence(rule)

    def assert_persistence(self, rule: Dict[str, Any]) -> None:
        # 先统一解析规则中的运行期变量，确保 params 和 expected_fields 使用同一套上下文。
        resolved_rule = self._resolve_value(rule)
        assertion_id = resolved_rule.get("assertion_id") or resolved_rule.get("name") or "database_assertion"
        sql = resolved_rule.get("sql")
        if not sql:
            raise ValueError(f"数据库断言缺少 sql：{assertion_id}")
        self._validate_select_sql(assertion_id, sql)
        params = resolved_rule.get("params") or {}
        with self.engine.connect() as connection:
            rows = [dict(row) for row in connection.execute(text(sql), params).mappings().all()]
        self._assert_row_count(assertion_id, rows, resolved_rule)
        self._assert_fields(assertion_id, rows, resolved_rule)

    def _resolve_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._resolve_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._resolve_value(item) for item in value]
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            variable_name = value[2:-1]
            self._validate_variable_name(variable_name, "数据库断言变量注入")
            if variable_name not in self.runtime_context:
                raise KeyError(f"数据库断言变量未定义，无法注入：{variable_name}")
            return self.runtime_context[variable_name]
        return value

    @staticmethod
    def _validate_variable_name(variable_name: str, scene: str) -> None:
        if not isinstance(variable_name, str) or not variable_name.isidentifier() or keyword.iskeyword(variable_name):
            raise ValueError(f"{scene}变量名必须符合 Python 标识符规则且不能是关键字：{variable_name}")

    @staticmethod
    def _validate_select_sql(assertion_id: str, sql: str) -> None:
        normalized_sql = re.sub(r"\s+", " ", sql.strip().lower())
        if not normalized_sql.startswith("select "):
            raise ValueError(f"数据库断言只允许 SELECT 查询：{assertion_id}")
        sql_without_tail = normalized_sql[:-1] if normalized_sql.endswith(";") else normalized_sql
        if ";" in sql_without_tail:
            raise ValueError(f"数据库断言禁止单条规则包含多条 SQL：{assertion_id}")

    @staticmethod
    def _assert_row_count(assertion_id: str, rows: list[Dict[str, Any]], rule: Dict[str, Any]) -> None:
        expected_row_count = rule.get("expected_row_count")
        if expected_row_count is None:
            return
        actual_row_count = len(rows)
        assert actual_row_count == expected_row_count, (
            f"落库行数不匹配：{assertion_id}，实际：{actual_row_count}，期望：{expected_row_count}"
        )

    @staticmethod
    def _assert_fields(assertion_id: str, rows: list[Dict[str, Any]], rule: Dict[str, Any]) -> None:
        expected_fields = rule.get("expected_fields") or {}
        if not expected_fields:
            return
        assert rows, f"落库字段断言没有查询到数据：{assertion_id}"
        first_row = rows[0]
        for field_name, expected_value in expected_fields.items():
            assert field_name in first_row, f"落库字段不存在：{assertion_id}/{field_name}"
            actual_value = first_row[field_name]
            assert actual_value == expected_value, (
                f"落库字段不匹配：{assertion_id}/{field_name}，实际：{actual_value}，期望：{expected_value}"
            )
