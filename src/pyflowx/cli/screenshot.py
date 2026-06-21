"""截图工具.

跨平台截图工具, 支持全屏截图和区域截图.
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

import pyflowx as px
from pyflowx.conditions import Constants

# ============================================================================
# 辅助函数
# ============================================================================


def get_screenshot_path(filename: str | None = None) -> Path:
    """获取截图保存路径.

    Parameters
    ----------
    filename : str | None
        文件名, 如果为 None 则自动生成

    Returns
    -------
    Path
        截图保存路径
    """
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"

    screenshots_dir = Path.home() / "Pictures" / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    return screenshots_dir / filename


def take_screenshot_full(filename: str | None = None) -> None:
    """全屏截图.

    Parameters
    ----------
    filename : str | None
        文件名
    """
    output_path = get_screenshot_path(filename)

    if Constants.IS_WINDOWS:
        # Windows: 使用 PowerShell 截图
        ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$screen = [System.Windows.Forms.Screen]::PrimaryScreen
$bounds = $screen.Bounds
$bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
$bitmap.Save('{output_path.as_posix()}')
$graphics.Dispose()
$bitmap.Dispose()
"""
        subprocess.run(["powershell", "-Command", ps_script], check=True)
    elif Constants.IS_MACOS:
        # macOS: 使用 screencapture
        subprocess.run(["screencapture", "-x", str(output_path)], check=True)
    else:
        # Linux: 使用 gnome-screenshot 或 scrot
        try:
            subprocess.run(["gnome-screenshot", "-f", str(output_path)], check=True)
        except FileNotFoundError:
            subprocess.run(["scrot", str(output_path)], check=True)

    print(f"截图已保存: {output_path}")


def take_screenshot_area(filename: str | None = None) -> None:
    """区域截图.

    Parameters
    ----------
    filename : str | None
        文件名
    """
    output_path = get_screenshot_path(filename)

    if Constants.IS_WINDOWS:
        # Windows: 使用 PowerShell 截图 (需要用户选择区域)
        ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$form = New-Object System.Windows.Forms.Form
$form.WindowState = 'Maximized'
$form.FormBorderStyle = 'None'
$form.BackColor = [System.Drawing.Color]::FromArgb(1, 0, 0)
$form.Opacity = 0.5
$form.TopMost = $true
$form.Show()
Start-Sleep -Milliseconds 100
$screen = [System.Windows.Forms.Screen]::PrimaryScreen
$bounds = $screen.Bounds
$bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
$form.Close()
$bitmap.Save('{output_path.as_posix()}')
$graphics.Dispose()
$bitmap.Dispose()
"""
        subprocess.run(["powershell", "-Command", ps_script], check=True)
    elif Constants.IS_MACOS:
        # macOS: 使用 screencapture 交互模式
        subprocess.run(["screencapture", "-i", str(output_path)], check=True)
    else:
        # Linux: 使用 gnome-screenshot 交互模式
        try:
            subprocess.run(["gnome-screenshot", "-a", "-f", str(output_path)], check=True)
        except FileNotFoundError:
            subprocess.run(["scrot", "-s", str(output_path)], check=True)

    print(f"截图已保存: {output_path}")


# ============================================================================
# TaskSpec 定义
# ============================================================================

screenshot_full: px.TaskSpec = px.TaskSpec("screenshot_full", fn=take_screenshot_full)
screenshot_area: px.TaskSpec = px.TaskSpec("screenshot_area", fn=take_screenshot_area)


# ============================================================================
# CLI Runner
# ============================================================================


def main() -> None:
    """截图工具主函数."""
    runner = px.CliRunner(
        strategy="thread",
        description="Screenshot - 截图工具",
        graphs={
            # 全屏截图
            "f": px.Graph.from_specs([screenshot_full]),
            # 区域截图
            "a": px.Graph.from_specs([screenshot_area]),
        },
    )
    runner.run_cli()
