"""发布包独立性及跨平台源码证据回归测试。"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_package_has_all_required_resources():
    package = load('suite_package_check', ROOT / 'scripts/check_skill_package.py')
    assert package.check() == []


def test_source_quality_accepts_legacy_windows_evidence():
    scripts = ROOT / 'components/source-api-fact-extractor/scripts'
    sys.path.insert(0, str(scripts))
    try:
        quality = load('suite_quality_portability', scripts / 'quality_check_source_facts.py')
        evidence = r'src\main\java\Example.java:12 | Example.create'
        parsed = quality.parse_evidence(evidence)
        assert parsed and parsed['path'] == 'src/main/java/Example.java'
        entries = quality.actual_source_entries([
            {'entry': {'source_evidence': evidence}}
        ])
        assert ('src/main/java/Example.java', 'Example', 'create') in entries
    finally:
        sys.path.remove(str(scripts))
