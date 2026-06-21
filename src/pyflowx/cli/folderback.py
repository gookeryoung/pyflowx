"""文件夹备份工具.

备份文件和文件夹为 zip 文件,
自动删除超过最大数量的旧备份文件.
"""

from __future__ import annotations

import time
import zipfile
from pathlib import Path

import pyflowx as px

# ============================================================================
# 辅助函数
# ============================================================================


def remove_dump(src: Path, dst: Path, max_zip: int) -> None:
    """递归删除旧的备份 zip 文件."""
    zip_paths = [filepath for filepath in dst.rglob("*.zip") if src.stem in str(filepath)]
    zip_files = sorted(zip_paths, key=lambda fn: str(fn)[-19:-4])
    if len(zip_files) > max_zip:
        zip_files[0].unlink()
        remove_dump(src, dst, max_zip)


def zip_target(src: Path, dst: Path, max_zip: int) -> None:
    """将单个文件或文件夹压缩为 zip 文件."""
    files = [str(_) for _ in src.rglob("*")]
    timestamp = time.strftime("_%Y%m%d_%H%M%S")
    target_path = dst / (src.stem + timestamp + ".zip")

    with zipfile.ZipFile(target_path, "w") as zip_file:
        for file in files:
            zip_file.write(file, arcname=file.replace(str(src.parent), ""))

    remove_dump(src, dst, max_zip)
    print(f"备份完成: {target_path}")


def backup_folder(src: str, dst: str, max_zip: int = 5) -> None:
    """备份文件夹.

    Parameters
    ----------
    src : str
        源文件夹路径
    dst : str
        目标文件夹路径
    max_zip : int
        最大备份数量
    """
    src_path = Path(src)
    dst_path = Path(dst)

    if not src_path.exists():
        print(f"源文件夹不存在: {src_path}")
        return

    if not dst_path.exists():
        dst_path.mkdir(parents=True, exist_ok=True)
        print(f"创建目标文件夹: {dst_path}")

    zip_target(src_path, dst_path, max_zip)


# ============================================================================
# TaskSpec 定义
# ============================================================================

folderback_default: px.TaskSpec = px.TaskSpec(
    "folderback_default",
    fn=lambda: backup_folder(".", "./backup", 5),
)


# ============================================================================
# CLI Runner
# ============================================================================


def main() -> None:
    """文件夹备份工具主函数."""
    runner = px.CliRunner(
        strategy="thread",
        description="FolderBack - 文件夹备份工具",
        graphs={
            # 备份当前目录到 ./backup
            "b": px.Graph.from_specs([folderback_default]),
        },
    )
    runner.run_cli()
