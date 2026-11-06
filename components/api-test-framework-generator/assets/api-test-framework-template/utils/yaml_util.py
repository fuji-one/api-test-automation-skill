# YAML 工具层，统一处理 UTF-8 YAML 文件读写。
from pathlib import Path
from typing import Any, Union

import yaml


class YamlUtil:
    """统一封装 YAML 文件读写能力。"""

    @staticmethod
    def load(path: Union[str, Path]) -> Any:
        file_path = Path(path)
        with file_path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)
        # 空 YAML 会导致后续字段判断失真，读取阶段直接失败。
        if data is None:
            raise ValueError(f"YAML 文件内容不能为空：{file_path}")
        return data

    @staticmethod
    def dump(path: Union[str, Path], data: Any) -> None:
        file_path = Path(path)
        with file_path.open("w", encoding="utf-8") as file:
            yaml.safe_dump(data, file, allow_unicode=True, sort_keys=False)
