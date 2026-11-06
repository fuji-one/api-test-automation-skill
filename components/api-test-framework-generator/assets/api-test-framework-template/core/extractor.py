# 变量提取层，按 JSON 路径或正则表达式从响应中提取 token、业务 ID 或链路变量。
import re
from typing import Any


class Extractor:
    """统一封装响应变量提取能力。"""

    @staticmethod
    def extract_json_value(payload: Any, path: str) -> Any:
        current = payload
        parts = [part for part in path.split(".") if part and part != "$"]
        # 按点分路径逐层解析，任何一层缺失都应暴露为提取失败。
        for part in parts:
            current = Extractor._resolve_part(current, part, path)
        return current

    @staticmethod
    def _resolve_part(current: Any, part: str, full_path: str) -> Any:
        # 支持 items[0] 这类数组下标，便于链路变量从列表响应中提取。
        if "[" in part and part.endswith("]"):
            key, index_text = part[:-1].split("[", 1)
            if key:
                current = current[key]
            return current[int(index_text)]
        if isinstance(current, dict) and part in current:
            return current[part]
        raise KeyError(f"无法提取 JSON 路径：{full_path}")

    @staticmethod
    def extract_regex_value(source_text: str, pattern: str, group: int = 1) -> str:
        # 正则提取用于把非标准 JSON 响应、文本响应或响应头依赖传给下游。
        match = re.search(pattern, source_text)
        if not match:
            raise ValueError(f"正则表达式未匹配到内容：{pattern}")
        try:
            return match.group(group)
        except IndexError as error:
            raise ValueError(f"正则表达式分组不存在：{pattern}，group={group}") from error
