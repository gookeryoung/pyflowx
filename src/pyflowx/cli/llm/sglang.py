"""使用 SGLang 运行本地模型."""

import argparse
from pathlib import Path

import pyflowx as px
from pyflowx.conditions import BuiltinConditions, Constants


def main():
    parser = argparse.ArgumentParser(description="启动 SGLang 服务")
    parser.add_argument("--model", default="~/.models/Qwen2.5-Coder-32B-Instruct-AWQ", help="模型路径")
    parser.add_argument("--port", type=int, default=8000, help="服务端口")
    parser.add_argument("--ctx-len", type=int, default=28672, help="最大上下文长度")
    parser.add_argument("--mem", type=float, default=0.75, help="显存占比 (0-1)")
    parser.add_argument("--host", default="0.0.0.0", help="主机地址")
    parser.add_argument("--log-level", default="info", help="日志级别")
    args = parser.parse_args()

    if not args.model:
        parser.error("model is required")

    model_dir = Path(args.model).expanduser()
    if not model_dir.exists():
        parser.error(f"Model directory {model_dir} does not exist.")

    graph = px.Graph.from_specs([
        px.TaskSpec(
            name="download",
            cmd=[
                "uv",
                "install",
                "sglang[all]",
            ],
            conditions=(BuiltinConditions.NOT(BuiltinConditions.HAS_INSTALLED("sglang")),),
            verbose=True,
        ),
        px.TaskSpec(
            name="run",
            cmd=[
                "python" if Constants.IS_WINDOWS else "python3",
                "-m",
                "sglang.launch_server",
                "--model-path",
                str(model_dir),
                "--host",
                str(args.host),
                "--port",
                "8000",
                "--mem-fraction-static",
                str(args.mem),
                "--context-length",
                "32768",
                "--tool-call-parser",
                "qwen",
                "--log-level",
                str(args.log_level),
            ],
            verbose=True,
        ),
    ])

    px.run(graph, strategy="sequential", verbose=True)
