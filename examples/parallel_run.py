"""Example 2: parallel execution (thread strategy).

Same DAG run with sequential vs. thread strategy to show layer-internal
parallelism. Tasks within a layer run concurrently; layers are barriers.

Layer 1: [fetch_a, fetch_b]   (parallel)
Layer 2: [merge]              (waits for both)
"""

from __future__ import annotations

import time

import pyflowx as px


def fetch_a() -> str:
    time.sleep(0.5)
    return "a"


def fetch_b() -> str:
    time.sleep(0.5)
    return "b"


def merge(fetch_a: str, fetch_b: str) -> str:
    return fetch_a + fetch_b


def main() -> None:
    graph = px.Graph.from_specs(
        [
            px.TaskSpec("fetch_a", fetch_a),
            px.TaskSpec("fetch_b", fetch_b),
            px.TaskSpec("merge", merge, ("fetch_a", "fetch_b")),
        ]
    )

    print("=== Mermaid diagram ===")
    print(graph.to_mermaid("LR"))

    print("\n=== Sequential (expect ~1.0s) ===")
    start = time.time()
    report_seq = px.run(graph, strategy="sequential")
    t_seq = time.time() - start
    print(f"  result={report_seq['merge']}  time={t_seq:.2f}s")

    print("\n=== Threaded (expect ~0.5s) ===")
    start = time.time()
    report_thr = px.run(graph, strategy="thread", max_workers=2)
    t_thr = time.time() - start
    print(f"  result={report_thr['merge']}  time={t_thr:.2f}s")

    print(f"\nspeedup = {t_seq / t_thr:.2f}x")


if __name__ == "__main__":
    main()
