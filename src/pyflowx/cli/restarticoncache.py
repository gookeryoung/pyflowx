from __future__ import annotations

import pyflowx as px
from pyflowx.tasks.system import reset_icon_cache


def main() -> None:
    """重启图标缓存工具主函数."""
    graph = px.Graph.from_specs(reset_icon_cache())
    px.run(graph, strategy="thread")
