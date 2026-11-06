from __future__ import annotations

import sys
from pathlib import Path

import pytest


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
SAMPLE_PROJECT = SKILL_ROOT / "examples" / "sample-java-project"

sys.path.insert(0, str(SCRIPTS))


@pytest.fixture()
def facts(tmp_path):
    from scan_source import scan

    return scan(SAMPLE_PROJECT, tmp_path)


@pytest.fixture()
def output_root(tmp_path):
    from scan_source import scan

    scan(SAMPLE_PROJECT, tmp_path)
    return tmp_path
