#!/usr/bin/env python3
"""根据用户输入判断接口自动化流水线入口。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


SOURCE_SUFFIXES = {".java"}
EXECUTION_TARGET_DEPTHS = {"executable", "framework"}
DATA_MODEL_EXECUTION_MARKER_GROUPS = {
    "表结构": ("表结构", "表名", "字段", "columns", "column"),
    "关系图": ("关系图", "表关系", "父子关系", "relationship", "graph"),
    "铺数顺序": ("铺数顺序", "构造顺序", "setup order", "setup_order"),
    "清理逆序": ("清理逆序", "清理顺序", "cleanup order", "cleanup_order"),
    "归属键": ("归属键", "ownership key", "ownership_key"),
    "清理边界": ("清理边界", "cleanup boundary", "cleanup_boundary"),
}
DATA_MODEL_MISSING_CONTENT_MARKERS = (
    "缺失",
    "未提供",
    "没有",
    "待提供",
    "待补充",
    "待确认",
    "未知",
    "不详",
    "暂无",
    "todo",
    "tbd",
    "unknown",
    "n/a",
    "none",
    "null",
)
EXECUTION_CONFIG_REQUIREMENTS = {
    "环境引用": ("环境", "base_url", "base url", "url", "网关", "域名", "env"),
    "鉴权账号": ("鉴权", "认证", "授权", "账号", "登录", "auth", "account", "login"),
}
EXECUTION_CONFIG_MISSING_PHRASE_MARKERS = (
    "缺失",
    "未提供",
    "没有",
    "不需要",
    "无需",
    "待提供",
    "待补充",
    "待确认",
    "不详",
    "未知",
)
EXECUTION_CONFIG_MISSING_EXACT_MARKERS = {
    "无",
    "暂无",
    "空",
    "none",
    "null",
    "nil",
    "n/a",
    "na",
    "tbd",
    "todo",
    "xxx",
    "待定",
}
EXECUTION_CONFIG_PLACEHOLDER_MARKERS = (
    "example",
    "示例",
    "占位",
    "placeholder",
    "your_",
    "<",
    ">",
)


def readable_markdown(path_text: str | None) -> bool:
    if not path_text:
        return False
    path = Path(path_text)
    if not path.is_file() or path.suffix.lower() != ".md":
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False
    return bool(text.strip()) and "\ufffd" not in text


def readable_text_file(path_text: str | None) -> bool:
    if not path_text:
        return False
    path = Path(path_text)
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False
    return bool(text.strip()) and "\ufffd" not in text


def source_root_ready(path_text: str | None) -> bool:
    if not path_text:
        return False
    root = Path(path_text)
    if not root.is_dir():
        return False
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES:
            return True
    return False


def data_model_ready(path_text: str | None) -> bool:
    return readable_markdown(path_text)


def data_model_section_blocks(text: str, markers: tuple[str, ...]) -> list[str]:
    lines = text.splitlines()
    blocks: list[str] = []
    for index, raw_line in enumerate(lines):
        lowered = raw_line.lower()
        if not any(marker.lower() in lowered for marker in markers):
            continue
        block_lines = [raw_line]
        for nested in lines[index + 1 :]:
            if nested.lstrip().startswith("#"):
                break
            block_lines.append(nested)
        blocks.append("\n".join(block_lines))
    return blocks


def data_model_line_has_confirmed_content(line: str, markers: tuple[str, ...]) -> bool:
    normalized = line.strip().strip("|").strip()
    if not normalized or set(normalized) <= {"-", ":", "|", " "}:
        return False
    for marker in markers:
        normalized = re.sub(re.escape(marker), "", normalized, flags=re.IGNORECASE).strip()
    normalized = normalized.strip("#：:。；;，, ")
    if not normalized:
        return False
    return not any(marker in normalized.lower() for marker in DATA_MODEL_MISSING_CONTENT_MARKERS)


def data_model_group_has_confirmed_content(text: str, markers: tuple[str, ...]) -> bool:
    for block in data_model_section_blocks(text, markers):
        if any(data_model_line_has_confirmed_content(line, markers) for line in block.splitlines()):
            return True
    return False


def execution_data_model_missing_items(path_text: str | None) -> list[str]:
    if not readable_markdown(path_text):
        return ["可读、非空、UTF-8 的数据模型 Markdown"]
    text = Path(path_text).read_text(encoding="utf-8")
    missing_items: list[str] = []
    for name, markers in DATA_MODEL_EXECUTION_MARKER_GROUPS.items():
        if not data_model_group_has_confirmed_content(text, markers):
            missing_items.append(name)
    return missing_items


def split_config_value(line: str, keyword: str) -> str:
    """提取配置项值，用于区分真实配置和缺失占位说明。"""
    separators = ("：", ":", "=", " ")
    keyword_index = line.find(keyword)
    tail = line[keyword_index + len(keyword) :] if keyword_index >= 0 else line
    for separator in separators:
        if separator in tail:
            return tail.split(separator, 1)[1].strip()
    return tail.strip()


def is_missing_config_value(value: str) -> bool:
    normalized = value.strip().strip("'\"").strip()
    if not normalized:
        return True
    if normalized in EXECUTION_CONFIG_MISSING_EXACT_MARKERS:
        return True
    if any(marker in normalized for marker in EXECUTION_CONFIG_MISSING_PHRASE_MARKERS):
        return True
    return any(marker in normalized for marker in EXECUTION_CONFIG_PLACEHOLDER_MARKERS)


def line_denies_requirement(line: str, keyword: str) -> bool:
    """识别整行否定表达，避免把“无环境引用”误判成已提供。"""
    compact = re.sub(r"\s+", "", line)
    keyword_compact = re.sub(r"\s+", "", keyword)
    deny_prefixes = ("无", "没有", "未提供", "缺少", "不需要", "无需")
    deny_suffixes = ("无", "缺失", "未提供", "待提供", "待补充", "待确认", "未知", "不详", "待定")
    if any(f"{prefix}{keyword_compact}" in compact for prefix in deny_prefixes):
        return True
    if any(f"{keyword_compact}{suffix}" in compact for suffix in deny_suffixes):
        return True
    return False


def requirement_has_confirmed_value(text: str, keywords: tuple[str, ...]) -> bool:
    for raw_line in text.splitlines():
        line = raw_line.strip().lower()
        if not line or line.startswith("#"):
            continue
        for keyword in keywords:
            normalized_keyword = keyword.lower()
            if normalized_keyword not in line:
                continue
            if line_denies_requirement(line, normalized_keyword):
                continue
            value = split_config_value(line, normalized_keyword)
            if not is_missing_config_value(value):
                return True
    return False


def execution_config_missing_items(path_text: str | None) -> list[str]:
    if not readable_text_file(path_text):
        return ["可读、非空、UTF-8 的执行配置文件"]
    text = Path(path_text).read_text(encoding="utf-8").lower()
    missing_items: list[str] = []
    for name, keywords in EXECUTION_CONFIG_REQUIREMENTS.items():
        if not requirement_has_confirmed_value(text, keywords):
            missing_items.append(name)
    return missing_items


def decide_route(
    prd: str | None,
    api_doc: str | None,
    system_analysis: str | None,
    source_root: str | None,
    data_model: str | None = None,
    execution_config: str | None = None,
    target_depth: str = "framework",
) -> dict[str, object]:
    prd_ready = readable_markdown(prd)
    api_ready = readable_markdown(api_doc)
    system_analysis_ready = readable_markdown(system_analysis)
    model_ready = data_model_ready(data_model)
    doc_ready = all([prd_ready, api_ready, system_analysis_ready, model_ready])
    source_ready = source_root_ready(source_root)
    missing_config_items = execution_config_missing_items(execution_config)
    missing_execution_model_items = execution_data_model_missing_items(data_model)
    config_ready = not missing_config_items
    needs_execution_input = target_depth in EXECUTION_TARGET_DEPTHS
    missing_doc_entry_items = []
    if not prd_ready:
        missing_doc_entry_items.append("PRD Markdown")
    if not api_ready:
        missing_doc_entry_items.append("API Markdown")
    if not system_analysis_ready:
        missing_doc_entry_items.append("系统分析 Markdown")
    if not model_ready:
        missing_doc_entry_items.append("数据模型 Markdown")
    downstream_missing_inputs = []
    if needs_execution_input and not config_ready:
        downstream_missing_inputs.append(f"执行配置缺失项：{'、'.join(missing_config_items)}")
    if needs_execution_input and model_ready and missing_execution_model_items:
        downstream_missing_inputs.append(
            f"执行级数据模型缺失项：{'、'.join(missing_execution_model_items)}"
        )

    if not doc_ready and not source_ready:
        return {
            "route": "blocked",
            "stage_status": "BLOCKED_MISSING_ENTRY_INPUT",
            "doc_ready": doc_ready,
            "source_ready": source_ready,
            "data_model_ready": model_ready,
            "execution_config_ready": config_ready,
            "missing_doc_entry_items": missing_doc_entry_items,
            "downstream_missing_inputs": downstream_missing_inputs,
            "target_depth": target_depth,
            "reason": "既不满足 PRD/API/系统分析/数据模型四件套文档入口，也不满足源码入口。",
        }

    if doc_ready:
        return {
            "route": "pre-doc-analysis-pipeline",
            "stage_status": "PASSED",
            "doc_ready": True,
            "source_ready": source_ready,
            "data_model_ready": model_ready,
            "execution_config_ready": config_ready,
            "missing_doc_entry_items": [],
            "downstream_missing_inputs": downstream_missing_inputs,
            "target_depth": target_depth,
            "reason": "PRD、API、系统分析、数据模型四个文件均满足入口要求，按规则优先走文档入口。",
        }
    if source_ready:
        if needs_execution_input and not model_ready:
            downstream_missing_inputs.append("执行级/脚本阶段仍需数据模型 Markdown 或源码阶段归一化出的数据模型")
        return {
            "route": "source-api-fact-extractor",
            "stage_status": "PASSED",
            "doc_ready": False,
            "source_ready": True,
            "data_model_ready": model_ready,
            "execution_config_ready": config_ready,
            "missing_doc_entry_items": missing_doc_entry_items,
            "downstream_missing_inputs": downstream_missing_inputs,
            "target_depth": target_depth,
            "reason": "未满足 PRD/API/系统分析/数据模型四件套文档入口，但源码根目录满足源码入口要求。",
        }
    raise RuntimeError("入口路由判断出现未覆盖分支")


def main() -> int:
    parser = argparse.ArgumentParser(description="判断 api-automation-pipeline-suite 入口路由")
    parser.add_argument("--prd", help="PRD Markdown 路径")
    parser.add_argument("--api-doc", help="API Markdown 路径")
    parser.add_argument("--system-analysis", help="系统分析 Markdown 路径")
    parser.add_argument("--source-root", help="Java 后端源码根目录")
    parser.add_argument("--data-model", help="数据模型 Markdown 路径")
    parser.add_argument("--execution-config", help="执行配置文件路径，初始预检只强制包含环境引用和鉴权账号")
    parser.add_argument(
        "--target-depth",
        choices=("design", "executable", "framework"),
        default="framework",
        help="流水线目标深度，默认跑到 pytest+allure 脚本生成",
    )
    args = parser.parse_args()

    result = decide_route(
        args.prd,
        args.api_doc,
        args.system_analysis,
        args.source_root,
        args.data_model,
        args.execution_config,
        args.target_depth,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["route"] == "blocked" else 0


if __name__ == "__main__":
    sys.exit(main())
