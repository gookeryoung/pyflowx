import pyflowx as px


def main() -> None:
    """主函数."""
    # 使用更安全的分步执行方式，便于调试和捕获错误
    graph = px.Graph.from_specs([
        px.TaskSpec("download", cmd="curl -sSL https://linuxmirrors.cn/main.sh -o /tmp/linuxmirrors.sh", verbose=True),
        px.TaskSpec("install", cmd="sudo bash /tmp/linuxmirrors.sh", verbose=True, depends_on=("download",)),
    ])
    px.run(graph, strategy="thread")
