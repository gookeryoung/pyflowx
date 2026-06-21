"""文件夹压缩工具.

压缩目录下的所有文件/文件夹为 zip 文件,
默认压缩当前目录下的所有子文件夹.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pyflowx as px

# ============================================================================
# 配置
# ============================================================================

IGNORE_DIRS: list[str] = [".git", ".idea", ".vscode", "__pycache__"]
IGNORE_FILES: list[str] = [".gitignore"]
IGNORE: list[str] = [*IGNORE_DIRS, *IGNORE_FILES]
IGNORE_EXT: list[str] = [".zip", ".rar", ".7z", ".tar", ".gz"]


# ============================================================================
# 辅助函数
# ============================================================================


def archive_folder(folder: Path) -> None:
    """压缩单个文件夹."""
    shutil.make_archive(
        str(folder.with_name(folder.name)),
        format="zip",
        base_dir=folder,
    )
    print(f"压缩完成: {folder.name}.zip")


def zip_folders(cwd: str = ".") -> None:
    """压缩目录下的所有文件夹.

    Parameters
    ----------
    cwd : str
        工作目录
    """
    cwd_path = Path(cwd)
    if not cwd_path.exists():
        print(f"目录不存在: {cwd_path}")
        return

    dirs: list[Path] = [
        e for e in cwd_path.iterdir() if e.is_dir() and e.name not in IGNORE_DIRS and e.suffix not in IGNORE_EXT
    ]

    for dir_path in dirs:
        archive_folder(dir_path)


# ============================================================================
# TaskSpec 定义
# ============================================================================

folderzip_default: px.TaskSpec = px.TaskSpec("folderzip_default", fn=lambda: zip_folders("."))


# ============================================================================
# CLI Runner
# ============================================================================


def main() -> None:
    """文件夹压缩工具主函数."""
    runner = px.CliRunner(
        strategy="thread",
        description="FolderZip - 文件夹压缩工具",
        graphs={
            # 压缩当前目录下的所有文件夹
            "z": px.Graph.from_specs([folderzip_default]),
        },
    )
    runner.run_cli()
