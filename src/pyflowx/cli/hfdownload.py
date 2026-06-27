import argparse
from pathlib import Path
from typing import Literal, get_args

import pyflowx as px
from pyflowx.tasks.system import setenv

HFDownloadType = Literal["model", "dataset", "space"]


def main():
    parser = argparse.ArgumentParser(description="Download a model from HuggingFace.")
    parser.add_argument("name", help="Target name.")
    parser.add_argument(
        "--type", "-t", nargs="?", default="model", choices=get_args(HFDownloadType), help="Target type."
    )
    parser.add_argument("--dir", default=None, help="Download directory.")
    args = parser.parse_args()

    if not args.name:
        parser.error("name is required")

    target_name = args.name

    # 创建下载目录
    if args.dir:
        download_dir = Path(args.dir)
    else:
        download_dir = Path.home() / ".models" / target_name.split("/")[-1]
    download_dir.mkdir(parents=True, exist_ok=True)

    graph = px.Graph.from_specs([
        setenv("HF_ENDPOINT", "https://hf-mirror.com"),
        px.TaskSpec(
            name="download",
            cmd=[
                "uvx",
                "modelscope",
                "download",
                f"--{args.type}",
                target_name,
                "--local_dir",
                str(download_dir),
            ],
            depends_on=("setenv_hf_endpoint",),
            verbose=True,
        ),
    ])

    px.run(graph, strategy="thread", verbose=True)
