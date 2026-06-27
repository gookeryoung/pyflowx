"""使用 SGLang 运行本地模型."""

import argparse
from pathlib import Path

import pyflowx as px
from pyflowx.conditions import BuiltinConditions


def main():
    parser = argparse.ArgumentParser(description="Run a local model using SGLang.")
    parser.add_argument("name", help="Model name.")
    parser.add_argument("--dir", default=None, help="Directory of model.")
    args = parser.parse_args()

    if not args.name:
        parser.error("name is required")

    model_dir = Path(args.dir) if args.dir else Path.home() / ".models" / args.name.split("/")[-1]
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
                "uvx",
                "sglang",
                "serve",
                "--model-path",
                str(model_dir),
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
                "--mem-fraction-static",
                "0.88",
                "--context-length",
                "32768",
            ],
            verbose=True,
        ),
    ])

    px.run(graph, verbose=True)
