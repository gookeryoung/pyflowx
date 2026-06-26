import argparse
import os
from pathlib import Path
from typing import Literal, get_args

import pyflowx as px

HFDownloadType = Literal["model", "dataset", "space"]


def setenvs():
    """设置 HuggingFace mirror 环境变量."""
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"


def main():
    parser = argparse.ArgumentParser(description="Download a model from HuggingFace.")
    parser.add_argument("dataset_name", type=str, help="HuggingFace dataset name.")
    parser.add_argument(
        "--type",
        type=str,
        nargs="?",
        default="dataset",
        choices=get_args(HFDownloadType),
        help="HuggingFace dataset type.",
    )
    parser.add_argument("--use-hfd", action="store_true", help="Use HFD tool to download dataset.")
    args = parser.parse_args()

    if not args.dataset_name:
        parser.error("dataset_name is required")

    dataset_name = args.dataset_name

    # 创建下载目录
    download_dir = Path.cwd() / dataset_name
    download_dir.mkdir(parents=True, exist_ok=True)

    if args.use_hfd:
        graph = px.Graph.from_specs([
            px.TaskSpec(name="setenvs", fn=setenvs, verbose=True),
            px.TaskSpec(
                name="download_hfd",
                cmd=["wget", "https://hf-mirror.com/hfd/hfd.sh"],
                depends_on=("setenvs",),
                verbose=True,
            ),
            px.TaskSpec(
                name="chmod_hfd",
                cmd=["chmod", "a+x", "hfd.sh"],
                depends_on=("download_hfd",),
                verbose=True,
            ),
            px.TaskSpec(
                name="run_hfd",
                cmd=["./hfd.sh", dataset_name, args.type],
                depends_on=("chmod_hfd",),
                verbose=True,
            ),
        ])
    else:
        graph = px.Graph.from_specs([
            px.TaskSpec(name="setenvs", fn=setenvs, verbose=True),
            px.TaskSpec(
                name="download",
                cmd=[
                    "uvx",
                    "hf",
                    "download",
                    "--repo-type",
                    args.type,
                    "--force-download",
                    dataset_name,
                    "--local-dir",
                    str(Path.cwd() / dataset_name),
                ],
                depends_on=("setenvs",),
                verbose=True,
            ),
        ])

    px.run(graph, strategy="thread", verbose=True)
