"""SSH 密钥部署工具.

类似 ssh-copy-id, 自动将 SSH 公钥部署到远程服务器,
支持密码认证和密钥认证两种方式.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pyflowx as px

# ============================================================================
# 辅助函数
# ============================================================================


def ssh_copy_id(
    hostname: str,
    username: str,
    password: str,
    port: int = 22,
    keypath: str = "~/.ssh/id_rsa.pub",
    timeout: int = 30,
) -> None:
    """将 SSH 公钥部署到远程服务器.

    Parameters
    ----------
    hostname : str
        远程服务器主机名或 IP 地址
    username : str
        远程服务器用户名
    password : str
        远程服务器密码
    port : int
        SSH 端口, 默认 22
    keypath : str
        公钥文件路径, 默认 ~/.ssh/id_rsa.pub
    timeout : int
        SSH 操作超时秒数, 默认 30
    """
    # 读取公钥
    pub_key_path = Path(keypath).expanduser()
    if not pub_key_path.exists():
        print(f"公钥文件不存在: {pub_key_path}")
        sys.exit(1)

    pub_key = pub_key_path.read_text().strip()

    # 构建部署脚本
    script = f"""mkdir -p ~/.ssh && chmod 700 ~/.ssh
cd ~/.ssh && touch authorized_keys && chmod 600 authorized_keys
grep -qF '{pub_key.split()[1]}' authorized_keys 2>/dev/null || echo '{pub_key}' >> authorized_keys"""

    # 使用 sshpass 执行
    try:
        subprocess.run(
            [
                "sshpass",
                "-p",
                password,
                "ssh",
                "-p",
                str(port),
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                "-o",
                f"ConnectTimeout={timeout}",
                f"{username}@{hostname}",
                script,
            ],
            check=True,
            timeout=timeout,
        )
        print(f"SSH 密钥已部署到 {username}@{hostname}:{port}")
    except FileNotFoundError:
        print(f"未找到 sshpass 工具，请手动执行: ssh-copy-id -p {port} {username}@{hostname}")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("SSH 连接超时")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"SSH 执行失败: {e}")
        sys.exit(1)


# ============================================================================
# CLI Runner
# ============================================================================


def main() -> None:
    """SSH 密钥部署工具主函数."""
    parser = argparse.ArgumentParser(
        description="SSHCopyID - SSH 密钥部署工具",
        usage="sshcopyid <hostname> <username> <password> [--port PORT] [--keypath KEYPATH]",
    )
    parser.add_argument("hostname", type=str, help="远程服务器主机名或 IP 地址")
    parser.add_argument("username", type=str, help="远程服务器用户名")
    parser.add_argument("password", type=str, help="远程服务器密码")
    parser.add_argument("--port", type=int, default=22, help="SSH 端口 (默认: 22)")
    parser.add_argument("--keypath", type=str, default="~/.ssh/id_rsa.pub", help="公钥文件路径")
    parser.add_argument("--timeout", type=int, default=30, help="SSH 操作超时秒数 (默认: 30)")
    args = parser.parse_args()

    graph = px.Graph.from_specs([
        px.TaskSpec(
            "ssh_deploy",
            fn=ssh_copy_id,
            args=(args.hostname, args.username, args.password),
            kwargs={"port": args.port, "keypath": args.keypath, "timeout": args.timeout},
        )
    ])
    px.run(graph, strategy="thread")
