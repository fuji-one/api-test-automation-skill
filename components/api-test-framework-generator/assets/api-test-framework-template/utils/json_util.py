# JSON 工具层，统一处理 UTF-8 JSON 文件读写。
import json
from pathlib import Path
from typing import Any, Union


class JsonUtil:
    """统一封装 JSON 文件读写能力。"""

    @staticmethod
    def load(path: Union[str, Path]) -> Any:
        file_path = Path(path)
        with file_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    @staticmethod
    def dump(path: Union[str, Path], data: Any) -> None:
        file_path = Path(path)
        with file_path.open("w", encoding="utf-8") as file:
            # ensure_ascii=False 保留中文，方便排查生成数据和校验报告。
            json.dump(data, file, ensure_ascii=False, indent=2)
