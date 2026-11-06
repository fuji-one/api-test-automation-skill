# 运行依赖检查层，避免依赖缺失时进入 pytest 收集或真实执行。
import importlib
import re
from dataclasses import dataclass
from importlib import metadata
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class RequiredDependency:
    package_name: str
    import_name: str
    min_version: Optional[str] = None


class DependencyChecker:
    """运行测试前检查框架依赖是否满足要求。"""

    BASE_DEPENDENCIES = (
        RequiredDependency("pytest", "pytest", "8.0.0"),
        RequiredDependency("requests", "requests", "2.31.0"),
        RequiredDependency("PyYAML", "yaml", "6.0.0"),
        RequiredDependency("allure-pytest", "allure", "2.13.0"),
    )
    DATABASE_DEPENDENCIES = (
        RequiredDependency("SQLAlchemy", "sqlalchemy", "2.0.0"),
        RequiredDependency("sqlglot", "sqlglot", "28.10.1"),
    )
    DATABASE_RUNTIME_DEPENDENCIES = (
        RequiredDependency("SQLAlchemy", "sqlalchemy", "2.0.0"),
        RequiredDependency("PyMySQL", "pymysql", "1.1.0"),
        RequiredDependency("sqlglot", "sqlglot", "28.10.1"),
    )

    @classmethod
    def check_required(cls) -> None:
        cls.check_dependencies(cls.BASE_DEPENDENCIES)

    @classmethod
    def check_database_required(cls) -> None:
        cls.check_dependencies(cls.DATABASE_DEPENDENCIES)

    @classmethod
    def check_database_runtime_required(cls) -> None:
        cls.check_dependencies(cls.DATABASE_RUNTIME_DEPENDENCIES)

    @classmethod
    def check_crypto_required(cls) -> None:
        cls.check_dependencies((RequiredDependency("cryptography", "cryptography", "46.0.7"),))

    @classmethod
    def check_dependencies(cls, dependencies: Tuple[RequiredDependency, ...]) -> None:
        missing_messages: List[str] = []
        # 每个依赖都独立检查，最后一次性输出完整缺失清单。
        for dependency in dependencies:
            message = cls._check_dependency(dependency)
            if message:
                missing_messages.append(message)
        if missing_messages:
            detail = "\n".join(f"- {message}" for message in missing_messages)
            raise RuntimeError(
                "接口自动化框架依赖检查未通过：\n"
                f"{detail}\n"
                "请先执行：python3 -m pip install -r requirements.txt"
            )

    @classmethod
    def _check_dependency(cls, dependency: RequiredDependency) -> Optional[str]:
        try:
            importlib.import_module(dependency.import_name)
        except ImportError:
            return f"缺少依赖：{dependency.package_name}"

        try:
            installed_version = metadata.version(dependency.package_name)
        except metadata.PackageNotFoundError:
            return f"无法读取依赖版本：{dependency.package_name}"

        # 版本过低也视为不可运行，避免运行中触发兼容性问题。
        if dependency.min_version and cls._version_lt(installed_version, dependency.min_version):
            return (
                f"依赖版本过低：{dependency.package_name} "
                f"当前版本 {installed_version}，最低版本 {dependency.min_version}"
            )
        return None

    @staticmethod
    def _version_lt(installed_version: str, min_version: str) -> bool:
        return DependencyChecker._version_tuple(installed_version) < DependencyChecker._version_tuple(min_version)

    @staticmethod
    def _version_tuple(version: str) -> Tuple[int, ...]:
        parts = re.findall(r"\d+", version)
        return tuple(int(part) for part in parts[:3])
