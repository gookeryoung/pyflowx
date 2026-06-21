"""文件等级重命名工具.

根据文件等级配置自动重命名文件,
支持多种等级标识和括号格式.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pyflowx as px

# ============================================================================
# 配置
# ============================================================================

LEVELS: dict[str, str] = {
    "0": "",
    "1": "PUB,NOR",
    "2": "INT",
    "3": "CON",
    "4": "CLA",
}

BRACKETS: tuple[str, str] = (" ([_(【-", " )]_）】")


# ============================================================================
# 辅助函数
# ============================================================================


def remove_marks(stem: str, marks: list[str]) -> str:
    """从文件名主干中移除所有标记."""
    left_brackets, right_brackets = BRACKETS
    for mark in marks:
        pos = 0
        while True:
            pos = stem.find(mark, pos)
            if pos == -1:
                break
            b, e = pos - 1, pos + len(mark)
            if b >= 0 and e < len(stem) and stem[b] in left_brackets and stem[e] in right_brackets:
                stem = stem[:b] + stem[e + 1 :]
            else:
                pos = e
    return stem


def process_file_level(filepath: Path, level: int = 0) -> None:
    """处理单个文件的等级标记.

    Parameters
    ----------
    filepath : Path
        文件路径
    level : int
        文件等级 (0-4), 0 用于清除等级
    """
    if not (0 <= level < len(LEVELS)):
        print(f"无效的等级 {level}, 必须在 0 和 {len(LEVELS) - 1} 之间")
        return

    if not filepath.exists():
        print(f"文件不存在: {filepath}")
        return

    filestem = filepath.stem
    original_stem = filestem

    # 移除所有等级标记
    for level_names in LEVELS.values():
        if level_names:
            filestem = remove_marks(filestem, level_names.split(","))

    # 移除数字标记
    for digit in map(str, range(1, 10)):
        filestem = remove_marks(filestem, [digit])

    # 添加等级标记
    if level > 0:
        levelstr = LEVELS.get(str(level), "").split(",")[0]
        if levelstr:
            filestem = f"{filestem}({levelstr})"

    # 重命名文件
    if filestem != original_stem:
        new_path = filepath.with_name(filestem + filepath.suffix)
        filepath.rename(new_path)
        print(f"重命名: {filepath} -> {new_path}")


def process_files_level(targets: list[Path], level: int = 0) -> None:
    """批量处理文件等级标记.

    Parameters
    ----------
    targets : list[Path]
        文件路径列表
    level : int
        文件等级 (0-4)
    """
    for target in targets:
        process_file_level(target, level)


# ============================================================================
# CLI Runner
# ============================================================================


def main() -> None:
    """文件等级重命名工具主函数."""
    parser = argparse.ArgumentParser(
        description="FileLevel - 文件等级重命名工具",
        usage="filelevel <command> [options]",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 设置等级命令
    level_parser = subparsers.add_parser("set", help="设置文件等级")
    level_parser.add_argument("files", nargs="+", help="文件路径")
    level_parser.add_argument("--level", type=int, choices=[0, 1, 2, 3, 4], required=True, help="文件等级 (0-4)")

    args = parser.parse_args()

    if args.command == "set":
        graph = px.Graph.from_specs([
            px.TaskSpec("process_files_level", fn=process_files_level, args=([Path(f) for f in args.files], args.level))
        ])
    else:
        parser.print_help()
        return

    px.run(graph, strategy="thread")
