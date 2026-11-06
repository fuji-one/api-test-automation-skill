# 随机数据工具层，生成可重复执行所需的后缀和时间戳。
import random
import string
from datetime import datetime


class RandomUtil:
    """统一封装可重复执行所需的随机数据能力。"""

    @staticmethod
    def suffix(length: int = 8) -> str:
        chars = string.ascii_lowercase + string.digits
        return "".join(random.choice(chars) for _ in range(length))

    @staticmethod
    def timestamp() -> str:
        return datetime.now().strftime("%Y%m%d%H%M%S")
