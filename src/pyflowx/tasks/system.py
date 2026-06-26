import pyflowx as px


def CLR():
    """清屏."""
    import subprocess

    from pyflowx.conditions import Constants

    return px.TaskSpec(
        "clear_screen", fn=lambda: subprocess.run(["cls"] if Constants.IS_WINDOWS else ["clear"], check=True)
    )


def SETENV(name: str, value: str):
    """设置环境变量."""
    import os

    return px.TaskSpec("set_env", fn=lambda: os.environ.setdefault(name, value))


def WHICH(cmd: str):
    """查找命令路径."""
    import subprocess

    def find_command() -> str | None:
        """查找命令并返回路径, 找不到时返回 None."""
        result = subprocess.run(["which", cmd], capture_output=True, text=True, check=False)

        if result.returncode == 0:
            path = result.stdout.strip()
            print(f"{cmd:<8} -> {path}")
            return path

        print(f"{cmd:<8} -> 未找到命令")
        return None

    return px.TaskSpec(f"which_{cmd}", fn=find_command)
