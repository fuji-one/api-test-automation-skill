# 前置数据管理层，按用例声明的规则执行 API 铺数、变量提取和数据清理。
import keyword
import re
from typing import Any, Dict, Iterable, List

import allure

from core.assertor import Assertor
from core.extractor import Extractor


class DataRuleExecutor:
    """统一封装用例前置铺数和执行后清理。"""

    def __init__(
        self,
        api_client: Any,
        runtime_context: Dict[str, Any],
        auth_contexts: Dict[str, Dict[str, Any]] | None = None,
    ) -> None:
        self.api_client = api_client
        self.runtime_context = runtime_context
        self.auth_contexts = auth_contexts or {}

    # 执行用例前置铺数规则，返回响应列表供必要时扩展检查。
    def setup(self, rules: Iterable[Dict[str, Any]]) -> List[Any]:
        responses = []
        for rule in rules:
            responses.append(self._execute_rule(rule, "前置铺数"))
        return responses

    # 执行用例后置清理规则，避免测试数据污染后续用例。
    def cleanup(self, rules: Iterable[Dict[str, Any]]) -> List[Any]:
        responses = []
        cleanup_errors: list[tuple[str, Exception]] = []
        for rule in rules:
            # 仅当规则显式声明依赖本轮运行变量时，允许在变量尚未产生的失败路径跳过。
            if self._missing_cleanup_runtime_vars(rule):
                continue
            try:
                responses.append(self._execute_rule(rule, "数据清理"))
            except Exception as error:
                cleanup_errors.append((str(rule.get("name") or rule.get("path") or "未命名清理"), error))
        if cleanup_errors:
            details = "；".join(f"{name}={error}" for name, error in cleanup_errors)
            raise AssertionError(f"API 后置清理存在 {len(cleanup_errors)} 个失败规则：{details}") from cleanup_errors[0][1]
        return responses

    def _missing_cleanup_runtime_vars(self, rule: Dict[str, Any]) -> List[str]:
        variable_names = rule.get("skip_if_missing_runtime_vars") or []
        if isinstance(variable_names, str):
            variable_names = [variable_names]
        if not isinstance(variable_names, list):
            raise TypeError("skip_if_missing_runtime_vars 必须是字符串或字符串列表")
        for variable_name in variable_names:
            self._validate_variable_name(variable_name, "清理跳过条件")
        return [name for name in variable_names if name not in self.runtime_context]

    def _execute_rule(self, rule: Dict[str, Any], stage_name: str) -> Any:
        rule_type = rule.get("type")
        # 当前模板只执行来源明确的 API 铺数/清理规则，其他类型必须由上游补齐实现。
        if rule_type != "api":
            raise ValueError(f"{stage_name}仅支持来源明确的 api 规则，当前类型：{rule_type}")

        # method/path/expected_status 是执行规则最小闭环，缺任一项都不能安全执行。
        method = rule.get("method")
        path = rule.get("path")
        expected_status = rule.get("expected_status")
        if not method or not path or expected_status is None:
            raise ValueError(f"{stage_name}规则必须包含 method、path 和 expected_status")

        with allure.step(f"{stage_name}：{rule.get('name', path)}"):
            # 请求参数先解析变量占位符，再交给统一 client 发起请求。
            resolved_headers = self._resolve_value(rule.get("headers") or {})
            resolved_params = self._resolve_value(rule.get("params") or {})
            resolved_json = self._resolve_value(rule.get("json") or {})
            resolved_path = self._resolve_text(path)
            if stage_name == "数据清理":
                self._validate_cleanup_identity(rule, resolved_path, resolved_params, resolved_json)
            previous_auth_context = getattr(self.api_client, "auth_context", {"enabled": False})
            self._select_rule_auth_context(rule, stage_name)
            try:
                response = self.api_client.request(
                    method=method,
                    path=resolved_path,
                    module=rule.get("module"),
                    headers=resolved_headers,
                    params=resolved_params,
                    json=resolved_json,
                )
                Assertor.status_code(response, expected_status)
            finally:
                self.api_client.set_auth_context(previous_auth_context)
            # 铺数或清理接口返回的变量会进入 runtime_context，供后续请求注入。
            self._extract_variables(response, rule.get("extract") or {})
            return response

    def _select_rule_auth_context(self, rule: Dict[str, Any], stage_name: str) -> None:
        session_role = rule.get("session_role")
        if not session_role:
            return
        if session_role == "none":
            self.api_client.set_auth_context({"enabled": False})
            return
        if session_role not in self.auth_contexts:
            raise ValueError(f"{stage_name}规则声明了未配置的 session_role：{session_role}")
        self.api_client.set_auth_context(self.auth_contexts[session_role])

    def _validate_cleanup_identity(self, rule: Dict[str, Any], path: str, params: Dict[str, Any], json_body: Dict[str, Any]) -> None:
        cleanup_identity = rule.get("cleanup_identity") or {}
        if cleanup_identity.get("field") != "id":
            raise ValueError("API 清理规则必须声明 cleanup_identity.field 为 id")
        value_ref = cleanup_identity.get("value_ref")
        if not value_ref:
            raise ValueError("API 清理规则必须声明 id 清理值来源")
        cleanup_id = self._read_cleanup_id(value_ref, path, params, json_body)
        if cleanup_id in (None, ""):
            raise ValueError(f"API 清理规则未能解析到有效 id：{value_ref}")

    def _read_cleanup_id(self, value_ref: str, path: str, params: Dict[str, Any], json_body: Dict[str, Any]) -> Any:
        if value_ref == "params.id":
            return params.get("id")
        if value_ref == "json.id":
            return json_body.get("id")
        if value_ref == "runtime_context.id":
            return self.runtime_context.get("id")
        if value_ref == "path.id":
            return self.runtime_context.get("id")
        raise ValueError(f"不支持的 id 清理值来源：{value_ref}")

    def _extract_variables(self, response: Any, extract_rules: Dict[str, str]) -> None:
        if not extract_rules:
            return
        json_rules, regex_rules = self._split_extract_rules(extract_rules)
        # 提取结果写入 runtime_context，后续步骤通过 ${变量名} 注入。
        if json_rules:
            payload = response.json()
            for variable_name, json_path in json_rules.items():
                self._validate_variable_name(variable_name, "变量提取")
                self.runtime_context[variable_name] = Extractor.extract_json_value(payload, json_path)
        for variable_name, regex_rule in regex_rules.items():
            self._validate_variable_name(variable_name, "正则变量提取")
            source_text = self._read_regex_source(response, regex_rule.get("source", "body"))
            self.runtime_context[variable_name] = Extractor.extract_regex_value(
                source_text,
                regex_rule["pattern"],
                int(regex_rule.get("group", 1)),
            )

    def _split_extract_rules(self, extract_rules: Dict[str, Any]) -> tuple[Dict[str, str], Dict[str, Dict[str, Any]]]:
        # 兼容旧格式 {变量名: json_path}，新格式则显式区分 json/regex。
        if "json" not in extract_rules and "regex" not in extract_rules:
            return extract_rules, {}
        json_rules = extract_rules.get("json") or {}
        regex_rules = {}
        for variable_name, regex_rule in (extract_rules.get("regex") or {}).items():
            if isinstance(regex_rule, str):
                regex_rules[variable_name] = {"pattern": regex_rule, "source": "body", "group": 1}
                continue
            if not isinstance(regex_rule, dict) or not regex_rule.get("pattern"):
                raise ValueError(f"正则依赖规则必须包含 pattern：{variable_name}")
            regex_rules[variable_name] = regex_rule
        return json_rules, regex_rules

    def _read_regex_source(self, response: Any, source: str) -> str:
        if source in ("body", "text"):
            return response.text
        if source.startswith("header."):
            header_name = source.split(".", 1)[1]
            return str(response.headers.get(header_name, ""))
        if source.startswith("json."):
            payload = response.json()
            return str(Extractor.extract_json_value(payload, source.split(".", 1)[1]))
        raise ValueError(f"不支持的正则依赖来源：{source}")

    def _resolve_value(self, value: Any) -> Any:
        # 递归解析嵌套结构，保证 header、query、body 中的变量都能被替换。
        if isinstance(value, dict):
            return {key: self._resolve_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._resolve_value(item) for item in value]
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            variable_name = value[2:-1]
            self._validate_variable_name(variable_name, "变量注入")
            # 变量缺失时立即失败，避免把未替换占位符发送到真实接口。
            if variable_name not in self.runtime_context:
                raise KeyError(f"变量未定义，无法注入：{variable_name}")
            return self.runtime_context[variable_name]
        return value

    def _resolve_text(self, text: str) -> str:
        # 路径中的 ${变量名} 也必须解析，常用于按 id 调用清理接口。
        def replace(match: re.Match[str]) -> str:
            variable_name = match.group(1)
            self._validate_variable_name(variable_name, "路径变量注入")
            if variable_name not in self.runtime_context:
                raise KeyError(f"变量未定义，无法注入路径：{variable_name}")
            return str(self.runtime_context[variable_name])

        return re.sub(r"\$\{([^}]+)\}", replace, text)

    @staticmethod
    def _validate_variable_name(variable_name: str, scene: str) -> None:
        if not isinstance(variable_name, str) or not variable_name.isidentifier() or keyword.iskeyword(variable_name):
            raise ValueError(f"{scene}变量名必须符合 Python 标识符规则且不能是关键字：{variable_name}")
