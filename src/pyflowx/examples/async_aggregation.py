"""Example 3: async aggregation with static args and Context injection.

Shows:
  * async task functions executed with strategy="async".
  * static positional args (TaskSpec.args) for parameterised tasks.
  * Context annotation to receive the full upstream result mapping.
  * on_event callback for real-time progress.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

import pyflowx as px


async def fetch_user(uid: int) -> dict:
    await asyncio.sleep(0.2)
    return {"id": uid, "name": f"User{uid}"}


async def fetch_posts(uid: int) -> List[int]:
    await asyncio.sleep(0.2)
    return [uid, uid + 1]


# Context annotation → receives the full mapping of upstream results.
def aggregate(ctx: px.Context) -> Dict[str, Any]:
    return dict(ctx)


def main() -> None:
    graph = px.Graph.from_specs(
        [
            # Static positional args parameterise the same function twice.
            px.TaskSpec("fetch_user", fetch_user, args=(1,)),
            px.TaskSpec("fetch_posts", fetch_posts, args=(1,)),
            px.TaskSpec("aggregate", aggregate, ("fetch_user", "fetch_posts")),
        ]
    )

    print("=== Dry run ===")
    px.run(graph, strategy="async", dry_run=True)

    events: List[px.TaskEvent] = []
    print("\n=== Async execution ===")
    report = px.run(graph, strategy="async", on_event=events.append)

    for ev in events:
        print(f"  event: {ev.task} -> {ev.status.value}")

    print(f"\naggregate = {report['aggregate']}")
    print(report.describe())


if __name__ == "__main__":
    main()
