"""Example 1: ETL pipeline (sequential strategy).

Demonstrates the core PyFlowX workflow:
  * Define tasks as plain functions.
  * Declare the DAG with a list of TaskSpec.
  * Parameter names == dependency names → automatic context injection,
    no wrappers needed (contrast with flowweaver's get_task_result boilerplate).
  * dry_run to preview, then execute and read typed results from RunReport.
"""

from __future__ import annotations

import pyflowx as px

# --- task functions: pure, testable, no framework coupling ------------- #


def extract_customers() -> list[dict]:
    return [
        {"id": "C001", "name": "Alice"},
        {"id": "C002", "name": "Bob"},
    ]


def extract_orders() -> list[dict]:
    return [
        {"id": "O001", "customer_id": "C001", "amount": 150.0},
        {"id": "O002", "customer_id": "C002", "amount": 200.5},
    ]


# Parameter names match dependency names → automatic injection.
def transform(
    extract_customers: list[dict],
    extract_orders: list[dict],
) -> list[dict]:
    cmap = {c["id"]: c for c in extract_customers}
    return [
        {**o, "customer_name": cmap[o["customer_id"]]["name"]}
        for o in extract_orders
        if o["customer_id"] in cmap
    ]


def load(transform: list[dict]) -> int:
    print(f"  loaded {len(transform)} records")
    return len(transform)


def main() -> None:
    graph = px.Graph.from_specs(
        [
            px.TaskSpec("extract_customers", extract_customers, tags=("extract",)),
            px.TaskSpec("extract_orders", extract_orders, tags=("extract",)),
            px.TaskSpec(
                "transform",
                transform,
                ("extract_customers", "extract_orders"),
                tags=("transform",),
            ),
            px.TaskSpec("load", load, ("transform",), retries=1, tags=("load",)),
        ]
    )

    print("=== Execution plan ===")
    print(graph.describe())

    print("\n=== Dry run (no execution) ===")
    px.run(graph, strategy="sequential", dry_run=True)

    print("\n=== Sequential execution ===")
    report = px.run(graph, strategy="sequential")
    print(report.describe())
    print(f"\nload result = {report['load']}")
    print(f"summary = {report.summary()}")


if __name__ == "__main__":
    main()
