"""文件日期处理工具.

自动检测文件名的日期前缀,
并根据文件的实际创建或修改时间重命名文件.
"""

from __future__ import annotations

import argparse
import re
import time
from pathlib import Path

import pyflowx as px

# ============================================================================
# 配置
# ============================================================================

DATE_PATTERN = re.compile(r"(20|19)\d{2}[-_#.~]?((0[1-9])|(1[012]))[-_#.~]?((0[1-9])|([12]\d)|(3[01]))[-_#.~]?")
SEP = "_"


# ============================================================================
# 辅助函数
# ============================================================================


def get_file_timestamp(filepath: Path) -> str:
    """获取文件时间戳."""
    modified_time = filepath.stat().st_mtime
    created_time = filepath.stat().st_ctime
    return time.strftime("%Y%m%d", time.localtime(max((modified_time, created_time))))


def remove_date_prefix(filepath: Path) -> Path:
    """移除文件日期前缀."""
    stem = filepath.stem
    new_stem = DATE_PATTERN.sub("", stem)
    if new_stem != stem:
        new_path = filepath.with_name(new_stem + filepath.suffix)
        filepath.rename(new_path)
        return new_path
    return filepath


def add_date_prefix(filepath: Path) -> Path:
    """添加文件日期前缀."""
    timestamp = get_file_timestamp(filepath)
    stem = filepath.stem
    new_stem = f"{timestamp}{SEP}{stem}"
    new_path = filepath.with_name(new_stem + filepath.suffix)
    if new_path != filepath:
        filepath.rename(new_path)
        return new_path
    return filepath


def process_file_date(filepath: Path, clear: bool = False) -> None:
    """处理单个文件的日期前缀.

    Parameters
    ----------
    filepath : Path
        文件路径
    clear : bool
        是否清除日期前缀
    """
    if clear:
        remove_date_prefix(filepath)
    else:
        # 先移除旧日期前缀，再添加新日期前缀
        new_path = remove_date_prefix(filepath)
        add_date_prefix(new_path)


def process_files_date(targets: list[Path], clear: bool = False) -> None:
    """批量处理文件日期前缀.

    Parameters
    ----------
    targets : list[Path]
        文件路径列表
    clear : bool
        是否清除日期前缀
    """
    for target in targets:
        if target.exists() and not target.name.startswith("."):
            process_file_date(target, clear)


# ============================================================================
# CLI Runner
# ============================================================================


def main() -> None:
    """文件日期处理工具主函数."""
    parser = argparse.ArgumentParser(
        description="FileDate - 文件日期处理工具",
        usage="filedate <command> [options]",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 添加日期前缀命令
    add_parser = subparsers.add_parser("add", help="添加日期前缀")
    add_parser.add_argument("files", nargs="+", help="文件路径")

    # 清除日期前缀命令
    clear_parser = subparsers.add_parser("clear", help="清除日期前缀")
    clear_parser.add_argument("files", nargs="+", help="文件路径")

    args = parser.parse_args()

    if args.command == "add":
        graph = px.Graph.from_specs([
            px.TaskSpec(
                "process_files_date",
                fn=process_files_date,
                args=([Path(f) for f in args.files],),
                kwargs={"clear": False},
            )
        ])
    elif args.command == "clear":
        graph = px.Graph.from_specs([
            px.TaskSpec(
                "process_files_date",
                fn=process_files_date,
                args=([Path(f) for f in args.files],),
                kwargs={"clear": True},
            )
        ])
    else:
        parser.print_help()
        return

    px.run(graph, strategy="thread")
