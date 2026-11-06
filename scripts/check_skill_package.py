"""离线检查发布包的 Python 语法、YAML 和必要资源。"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'.git', '.venv', '__pycache__', '.audit', '.pytest_cache', 'output', 'dist', 'build'}
COMPONENTS = {
    'pre-doc-analysis-pipeline', 'doc-precheck-coverage', 'test-point-analysis',
    'interface-testcase-design', 'source-api-fact-extractor',
    'interface-testcase-generation', 'executable-interface-case-set',
    'api-test-framework-generator',
}


def check() -> list[str]:
    errors: list[str] = []
    for name in sorted(COMPONENTS):
        if not (ROOT / 'components' / name / 'SKILL.md').is_file():
            errors.append(f'缺少组件：{name}')
    actual = {p.name for p in (ROOT / 'components').iterdir() if p.is_dir()}
    if actual != COMPONENTS:
        errors.append(f'组件集合不一致：{sorted(actual ^ COMPONENTS)}')
    count = 0
    for path in ROOT.rglob('*'):
        if not path.is_file() or EXCLUDED.intersection(path.relative_to(ROOT).parts):
            continue
        if path.suffix not in {'.py', '.md', '.yaml', '.yml', '.json', '.txt'}:
            continue
        count += 1
        label = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding='utf-8')
            if '\ufffd' in text:
                errors.append(f'{label}: 含 Unicode 替换字符')
            if path.suffix == '.py':
                ast.parse(text, filename=label)
            elif path.suffix in {'.yaml', '.yml'}:
                yaml.safe_load(text)
            if path.name == 'SKILL.md':
                match = re.match(r'^---\s*\n(.*?)\n---', text, re.S)
                metadata = yaml.safe_load(match.group(1)) if match else {}
                if not metadata.get('name') or not metadata.get('description'):
                    errors.append(f'{label}: 缺少 skill name/description')
                for resource in re.findall(r'`((?:\.\./)*(?:references|scripts|assets|components)/[^`\s]+)`', text):
                    if any(char in resource for char in '*<>#') or not Path(resource).suffix:
                        continue
                    if not (path.parent / resource).exists():
                        errors.append(f'{label}: 缺少引用资源 {resource}')
        except (UnicodeError, SyntaxError, yaml.YAMLError) as exc:
            errors.append(f'{label}: {exc}')
    print(f'检查了 {count} 个文本文件、{len(COMPONENTS)} 个组件')
    return errors


if __name__ == '__main__':
    problems = check()
    for problem in problems:
        print(problem)
    raise SystemExit(bool(problems))
