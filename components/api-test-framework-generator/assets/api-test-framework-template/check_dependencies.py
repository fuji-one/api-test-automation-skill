# 依赖检查入口，运行测试前先确认 pytest、requests、allure、YAML 和可选加密依赖可用。
import sys
from pathlib import Path

from core.dependency_check import DependencyChecker


ROOT_DIR = Path(__file__).parent


def main() -> None:
    try:
        DependencyChecker.check_required()
        if transport_crypto_enabled():
            DependencyChecker.check_crypto_required()
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
    print("依赖检查通过")


def transport_crypto_enabled() -> bool:
    from utils.yaml_util import YamlUtil

    for config_path in (ROOT_DIR / "configs").glob("*.yaml"):
        if config_path.name == "database.yaml":
            continue
        config = YamlUtil.load(config_path)
        if ((config.get("transport_encryption") or {}).get("enabled")):
            return True
    return False


if __name__ == "__main__":
    main()
