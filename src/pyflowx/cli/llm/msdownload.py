"""Download from ModelScopeHub."""

import argparse
from pathlib import Path
from typing import Literal, get_args

import pyflowx as px

DownloadType = Literal["model", "dataset", "space"]


def main():
    parser = argparse.ArgumentParser(description="Download a model from ModelScopeHub.")
    parser.add_argument("name", help="Target name.")
    parser.add_argument("--type", "-t", nargs="?", default="model", choices=get_args(DownloadType), help="Target type.")
    parser.add_argument("--dir", default=None, help="Download directory.")
    args = parser.parse_args()

    if not args.name:
        parser.error("name is required")

    download_dir: Path = Path(args.dir) if args.dir else Path.home() / ".models" / args.name.split("/")[-1]
    download_dir.mkdir(parents=True, exist_ok=True)

    graph = px.Graph.from_specs([
        px.TaskSpec(
            name="download",
            cmd=[
                "uvx",
                "modelscope",
                "download",
                f"--{args.type}",
                args.name,
                "--local_dir",
                str(download_dir),
            ],
            verbose=True,
        ),
    ])

    px.run(graph, strategy="thread", verbose=True)
