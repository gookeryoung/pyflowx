"""Run report: typed, queryable result of a single :func:`pyflowx.run`.

The report is the single source of truth after execution. It exposes
per-task results via ``report["name"]`` (typed as ``Any`` because the
mapping is heterogeneous), summary statistics, and a flag indicating
whether the whole run succeeded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Mapping, Optional

from .task import TaskResult, TaskStatus


@dataclass
class RunReport:
    """Aggregated outcome of a workflow run.

    Attributes
    ----------
    results:
        Mapping of task name -> :class:`TaskResult`. Insertion order
        matches the order tasks finished.
    success:
        ``True`` iff every non-skipped task ended in ``SUCCESS``.
    """

    results: Dict[str, TaskResult[object]] = field(default_factory=dict)
    success: bool = True

    # ---- typed access ------------------------------------------------- #
    def __getitem__(self, name: str) -> Any:
        """Return the *value* of task ``name`` (not the TaskResult).

        Raises ``KeyError`` if the task was not part of the run. Returns
        ``None`` for tasks that did not reach SUCCESS.
        """
        return self.results[name].value

    def result_of(self, name: str) -> TaskResult[object]:
        """Return the full :class:`TaskResult` for ``name``."""
        return self.results[name]

    def __contains__(self, name: object) -> bool:
        return name in self.results

    def __iter__(self) -> Iterator[str]:
        return iter(self.results)

    def __len__(self) -> int:
        return len(self.results)

    # ---- summary ------------------------------------------------------ #
    def summary(self) -> Dict[str, Any]:
        """Compact statistics dict for logging / dashboards."""
        counts: Dict[str, int] = {}
        total_duration = 0.0
        for r in self.results.values():
            counts[r.status.value] = counts.get(r.status.value, 0) + 1
            if r.duration is not None:
                total_duration += r.duration
        return {
            "success": self.success,
            "total_tasks": len(self.results),
            "by_status": counts,
            "total_duration_seconds": round(total_duration, 6),
        }

    def failed_tasks(self) -> List[str]:
        """Names of tasks that ended in FAILED status."""
        return [name for name, r in self.results.items() if r.status == TaskStatus.FAILED]

    def describe(self) -> str:
        """Human-readable multi-line report for debugging."""
        lines: List[str] = [f"RunReport(success={self.success})"]
        for name, r in self.results.items():
            dur = f"{r.duration:.3f}s" if r.duration is not None else "-"
            err = f" error={r.error!r}" if r.error else ""
            lines.append(f"  {name}: {r.status.value} ({dur} attempts={r.attempts}){err}")
        return "\n".join(lines)
