# SQL 命令校验入口，负责生成静态校验和可选运行预检报告。
import argparse
import sys
from pathlib import Path

from core.dependency_check import DependencyChecker


ROOT_DIR = Path(__file__).parent


def main() -> None:
    DependencyChecker.check_required()
    from core.sql_validator import SqlCommandValidator
    from utils.yaml_util import YamlUtil

    args = parse_args()
    if args.runtime:
        DependencyChecker.check_database_runtime_required()
    else:
        DependencyChecker.check_database_required()
    database_config = load_database_config(YamlUtil, args.env)
    sql_commands_file = database_config.get("sql_commands_file")
    if not sql_commands_file:
        raise ValueError("database.sql_commands_file 不能为空")

    sql_commands_path = ROOT_DIR / sql_commands_file
    validation_path = ROOT_DIR / "data" / "case_sql_validation.yaml"
    sql_commands = YamlUtil.load(sql_commands_path)
    try:
        # 默认先做静态校验：语法、绑定参数、安全边界和清理契约。
        SqlCommandValidator.validate_static(sql_commands)
        runtime_validation = resolve_runtime_validation_status(sql_commands, "pending")
        validation_data = build_validation_data("static_passed", "passed", runtime_validation, sql_commands)
        # 开启 --runtime 时会连接数据库做事务回滚式运行预检。
        if args.runtime:
            SqlCommandValidator.validate_runtime(database_config, sql_commands)
            mark_runtime_validation_passed(sql_commands)
            YamlUtil.dump(sql_commands_path, sql_commands)
            validation_data = build_validation_data("runtime_passed", "passed", "passed", sql_commands)
            YamlUtil.dump(validation_path, validation_data)
            print("SQL 静态校验和运行预检通过")
            return
        YamlUtil.dump(validation_path, validation_data)
        print("SQL 静态校验通过")
    except Exception as error:
        validation_data = build_validation_data("blocked", "failed", "failed" if args.runtime else "pending", sql_commands, str(error))
        YamlUtil.dump(validation_path, validation_data)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="校验每条用例的 SQL 前置铺数和后置清理命令")
    parser.add_argument("--env", required=True, help="指定运行环境：dev/test/prod")
    parser.add_argument("--runtime", action="store_true", help="启用事务回滚式运行预检")
    return parser.parse_args()


def load_database_config(yaml_util: object, env_name: str) -> dict:
    database_config_path = ROOT_DIR / "configs" / "database.yaml"
    all_database_config = yaml_util.load(database_config_path)
    database_config = all_database_config.get(env_name)
    if not isinstance(database_config, dict):
        raise ValueError(f"数据库配置缺少环境节点：{env_name}")
    return database_config


def mark_runtime_validation_passed(sql_commands: dict) -> None:
    gate = sql_commands.setdefault("sql_generation_gate", {})
    quality_checks = gate.setdefault("quality_checks", {})
    quality_checks["runtime_validation_verified"] = True


def resolve_runtime_validation_status(sql_commands: dict, default_status: str) -> str:
    gate = sql_commands.get("sql_generation_gate") or {}
    quality_checks = gate.get("quality_checks") or {}
    if quality_checks.get("db_mcp_runtime_supplement_verified"):
        return "passed_via_db_mcp_supplement"
    if quality_checks.get("runtime_validation_verified"):
        return "passed"
    return default_status


def build_validation_data(status: str, static_validation: str, runtime_validation: str, sql_commands: dict, reason: str = "") -> dict:
    validation = {
        "sql_validation": {
            "status": status,
            "static_validation": static_validation,
            "runtime_validation": runtime_validation,
            "reason": reason,
            "checked_cases": sorted((sql_commands.get("cases") or {}).keys()),
        }
    }
    gate = sql_commands.get("sql_generation_gate") or {}
    supplement_ref = gate.get("runtime_validation_supplement_ref")
    if runtime_validation == "passed_via_db_mcp_supplement" and supplement_ref:
        validation["sql_validation"]["runtime_validation_ref"] = supplement_ref
        validation["sql_validation"]["runtime_validation_boundary"] = gate.get(
            "runtime_validation_boundary",
            "DB MCP 是运行时证据源；pytest 运行时仍通过 database.yaml 环境变量连接数据库。",
        )
    return validation


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
