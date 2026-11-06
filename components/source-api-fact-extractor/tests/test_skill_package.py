from __future__ import annotations

from pathlib import Path
import re


SKILL_ROOT = Path(__file__).resolve().parents[1]


def test_skill_frontmatter_description_is_trigger_only():
    skill_md = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    description = next(line for line in skill_md.splitlines() if line.startswith("description: "))

    assert description.startswith("description: Use when ")


def test_skill_package_has_no_auxiliary_docs_or_unused_templates():
    assert not (SKILL_ROOT / "README.md").exists()
    assert not (SKILL_ROOT / "templates").exists()


def test_skill_commands_use_python3_and_skill_dir_paths():
    skill_md = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert not re.search(r"(^|\n)\s*python\s+", skill_md)
    assert "python3" in skill_md
    assert "<skill_dir>/scripts/scan_source.py" in skill_md
    assert "<skill_dir>/scripts/quality_check_source_facts.py" in skill_md


def test_skill_declares_pytest_dev_dependency():
    pyproject = (SKILL_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "pytest" in pyproject


def test_openai_yaml_short_description_is_descriptive():
    openai_yaml = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
    short_line = next(line for line in openai_yaml.splitlines() if "short_description:" in line)
    short_description = short_line.split(":", 1)[1].strip().strip('"')

    assert 25 <= len(short_description) <= 64


def test_project_unknowns_shape_documents_required_fields():
    skill_md = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    project_unknowns_block = skill_md.split('"project_unknowns": [', 1)[1].split('"apis": [', 1)[0]

    for field in (
        "unknown_id",
        "api_id",
        "description",
        "why_unknown",
        "evidence_or_location",
        "suggested_manual_check",
    ):
        assert f'"{field}"' in project_unknowns_block
