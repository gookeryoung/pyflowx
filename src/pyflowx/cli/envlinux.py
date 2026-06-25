import pyflowx as px


def main() -> None:
    """主函数."""
    graph = px.Graph.from_specs(
        [
            px.TaskSpec(
                "envlinux", cmd=["sudo", "curl", "-sSL", "https://linuxmirrors.cn/main.sh", "|", "bash"], verbose=True
            )
        ]
    )
    px.run(graph, strategy="thread")
