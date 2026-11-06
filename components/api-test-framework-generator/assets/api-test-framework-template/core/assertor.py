# 断言封装层，集中维护状态码、JSON 路径和必填字段校验规则。
from typing import Any, Iterable


class Assertor:
    """统一封装接口断言能力。"""

    @staticmethod
    def normalize_assertion_rules(rules: Any, value_key: str) -> list[dict[str, Any]]:
        """统一兼容列表规则和 JSONPath 到期望值的映射格式。"""

        if rules is None:
            return []
        if isinstance(rules, dict):
            return [{"path": str(path), value_key: value} for path, value in rules.items()]
        if not isinstance(rules, list):
            raise TypeError("断言规则必须是列表或 JSONPath 映射")
        normalized: list[dict[str, Any]] = []
        for index, rule in enumerate(rules, start=1):
            if not isinstance(rule, dict) or not isinstance(rule.get("path"), str):
                raise TypeError(f"第 {index} 条断言规则必须包含字符串 path")
            if value_key not in rule:
                raise ValueError(f"第 {index} 条断言规则缺少 {value_key}")
            normalized.append({"path": rule["path"], value_key: rule[value_key]})
        return normalized

    @staticmethod
    def status_code(response: Any, expected_status: int) -> None:
        # 状态码是接口最基础的准出断言，失败时直接暴露实际和期望值。
        assert response.status_code == expected_status, (
            f"状态码不匹配，实际：{response.status_code}，期望：{expected_status}"
        )

    @staticmethod
    def json_path_equal(payload: Any, path: str, expected_value: Any) -> None:
        # 先统一解析 JSON 路径，再比较值，便于所有用例复用同一套错误信息。
        actual_value = Assertor._get_json_path(payload, path)
        assert actual_value == expected_value, (
            f"JSON 路径 {path} 不匹配，实际：{actual_value}，期望：{expected_value}"
        )

    @staticmethod
    def required_fields(payload: Any, fields: Iterable[str]) -> None:
        # 必填字段只校验可访问性，字段值规则由更具体的断言承担。
        for field in fields:
            Assertor._get_json_path(payload, field)

    @staticmethod
    def array_length_equal(payload: Any, path: str, expected_length: int) -> None:
        # 数组长度用于验证列表型业务结果，避免只校验字段存在导致断言过弱。
        actual_value = Assertor._get_json_path(payload, path)
        assert isinstance(actual_value, list), f"JSON 路径 {path} 不是数组，实际类型：{type(actual_value).__name__}"
        assert len(actual_value) == expected_length, (
            f"JSON 路径 {path} 数组长度不匹配，实际：{len(actual_value)}，期望：{expected_length}"
        )

    @staticmethod
    def string_min_length(payload: Any, path: str, min_length: int) -> None:
        # 字符串最小长度用于验证生成文案、描述等非空业务字段。
        actual_value = Assertor._get_json_path(payload, path)
        assert isinstance(actual_value, str), f"JSON 路径 {path} 不是字符串，实际类型：{type(actual_value).__name__}"
        assert len(actual_value) >= min_length, (
            f"JSON 路径 {path} 字符串长度不足，实际：{len(actual_value)}，最小期望：{min_length}"
        )

    @staticmethod
    def _get_json_path(payload: Any, path: str) -> Any:
        if path == "$":
            return payload
        normalized_path = Assertor._normalize_json_path(path)
        if not normalized_path:
            raise AssertionError("JSON 路径不能为空")
        current = payload
        # 支持点分路径和 items[0] 数组下标，保持断言路径与变量提取路径一致。
        for part in normalized_path.split("."):
            current = Assertor._resolve_part(current, part, path)
        return current

    @staticmethod
    def _normalize_json_path(path: str) -> str:
        # 接受标准 JSONPath 根符号，避免把 $ 当成普通字段名。
        if path.startswith("$."):
            return path[2:]
        return path

    @staticmethod
    def _resolve_part(current: Any, part: str, full_path: str) -> Any:
        try:
            if "[" in part and part.endswith("]"):
                key, index_text = part[:-1].split("[", 1)
                if key:
                    if not isinstance(current, dict) or key not in current:
                        raise KeyError(key)
                    current = current[key]
                return current[int(index_text)]
            if isinstance(current, dict) and part in current:
                return current[part]
        except (IndexError, KeyError, TypeError, ValueError) as error:
            raise AssertionError(f"JSON 路径不存在：{full_path}") from error
        raise AssertionError(f"JSON 路径不存在：{full_path}")
