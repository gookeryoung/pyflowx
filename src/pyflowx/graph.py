"""DAG construction, validation, layering and visualisation.

Uses :mod:`graphlib` from the standard library (3.9+) or
:mod:`graphlib_backport` (3.8) for topological sorting. The graph is
built incrementally and validated eagerly so that misconfiguration fails
fast — at construction time, not at execution time.
"""

from __future__ import annotations

import sys
from typing import Dict, Iterable, List, Mapping, Sequence, Set, Tuple

from .errors import CycleError, DuplicateTaskError, MissingDependencyError
from .task import TaskSpec

# graphlib lives in the stdlib since 3.9; fall back to the backport on 3.8.
if sys.version_info >= (3, 9):
    import graphlib

    _TopologicalSorter = graphlib.TopologicalSorter
else:  # pragma: no cover - exercised only on 3.8
    import graphlib  # type: ignore[no-redef]

    _TopologicalSorter = graphlib.TopologicalSorter


class Graph:
    """An immutable-after-validation directed acyclic graph of tasks.

    The graph is built by adding :class:`~pyflowx.task.TaskSpec` instances.
    Each ``add`` performs eager validation (duplicate names, missing
    dependencies), and :meth:`validate` / :meth:`layers` perform full DAG
    validation (cycle detection) and topological layering.

    The graph holds only the *configuration*; runtime state lives in
    :class:`~pyflowx.report.RunReport`. This makes a graph safely
    re-runnable and shareable across threads.
    """

    def __init__(self) -> None:
        self._specs: Dict[str, TaskSpec[object]] = {}
        # Map task -> its direct dependencies (predecessors).
        self._deps: Dict[str, Tuple[str, ...]] = {}

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #
    def add(self, spec: TaskSpec[object]) -> "Graph":
        """Register a task spec with eager validation.

        Returns ``self`` so calls can be chained, but the recommended
        entry point is :meth:`from_specs` which validates the whole batch
        together (allowing forward references in a single call).
        """
        self._specs[spec.name] = spec
        self._deps[spec.name] = spec.depends_on
        # Eagerly check duplicates and missing deps for the incremental API.
        self._validate_references()
        return self

    @classmethod
    def from_specs(cls, specs: Iterable[TaskSpec[object]]) -> "Graph":
        """Build a graph from an iterable of task specs.

        All specs are collected first, then validated together. This means
        a task may reference a dependency that appears *later* in the
        iterable — order does not matter, mirroring how a declarative
        config file reads.
        """
        graph = cls()
        for spec in specs:
            if spec.name in graph._specs:
                raise DuplicateTaskError(spec.name)
            graph._specs[spec.name] = spec
            graph._deps[spec.name] = spec.depends_on
        graph._validate_references()
        graph.validate()
        return graph

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #
    def _validate_references(self) -> None:
        """Ensure every dependency name exists in the graph."""
        for name, deps in self._deps.items():
            for dep in deps:
                if dep not in self._specs:
                    raise MissingDependencyError(name, dep)

    def validate(self) -> None:
        """Run full DAG validation.

        Raises :class:`~pyflowx.errors.CycleError` if a cycle exists.
        Dependency existence is checked by :meth:`_validate_references`.
        """
        self._validate_references()
        sorter = _TopologicalSorter(self._deps)
        try:
            # prepare() raises CycleError on cycles; we don't need the
            # static_order() result here, just the validation side effect.
            sorter.prepare()
        except graphlib.CycleError as exc:
            # exc.args[1] is the list of nodes forming the cycle.
            cycle: Sequence[str] = exc.args[1] if len(exc.args) > 1 else []
            raise CycleError(list(cycle)) from exc

    # ------------------------------------------------------------------ #
    # Introspection
    # ------------------------------------------------------------------ #
    @property
    def names(self) -> List[str]:
        """All registered task names (insertion order)."""
        return list(self._specs.keys())

    def spec(self, name: str) -> TaskSpec[object]:
        """Return the spec for ``name``; ``KeyError`` if absent."""
        return self._specs[name]

    def dependencies(self, name: str) -> Tuple[str, ...]:
        """Direct predecessors of ``name``."""
        return self._deps[name]

    def all_specs(self) -> Mapping[str, TaskSpec[object]]:
        """Read-only view of name -> spec."""
        return self._specs

    def layers(self) -> List[List[str]]:
        """Group tasks into parallel-executable layers (Kahn's algorithm).

        Tasks within the same layer have no mutual dependencies and may
        run concurrently. Layers are returned in execution order.

        Raises :class:`~pyflowx.errors.CycleError` if the graph is cyclic.
        """
        self.validate()
        sorter = _TopologicalSorter(self._deps)
        result: List[List[str]] = []
        # ``get_ready`` + ``done`` gives us one layer at a time, which is
        # exactly the parallel-execution grouping we need.
        sorter.prepare()
        while sorter.is_active():
            ready = list(sorter.get_ready())
            # Sort for deterministic, reproducible execution plans.
            ready.sort()
            result.append(ready)
            for node in ready:
                sorter.done(node)
        return result

    # ------------------------------------------------------------------ #
    # Subgraph / tag filtering
    # ------------------------------------------------------------------ #
    def subgraph(self, tags: Iterable[str]) -> "Graph":
        """Return a new graph containing only tasks matching any tag.

        Dependencies are pruned to keep only edges between retained tasks;
        edges to dropped tasks are removed (the retained task no longer
        waits for them). Use this to run a slice of a large DAG for
        debugging.
        """
        wanted: Set[str] = set(tags)
        kept: List[TaskSpec[object]] = []
        for spec in self._specs.values():
            if wanted & set(spec.tags):
                pruned_deps = tuple(
                    d for d in spec.depends_on if d in self._specs and (wanted & set(self._specs[d].tags))
                )
                kept.append(
                    TaskSpec(
                        name=spec.name,
                        fn=spec.fn,
                        depends_on=pruned_deps,
                        args=spec.args,
                        kwargs=spec.kwargs,
                        retries=spec.retries,
                        timeout=spec.timeout,
                        tags=spec.tags,
                    )
                )
        return Graph.from_specs(kept)

    def subgraph_by_names(self, names: Iterable[str]) -> "Graph":
        """Return a new graph restricted to ``names`` (with pruned edges)."""
        wanted: Set[str] = set(names)
        for n in wanted:
            if n not in self._specs:
                raise KeyError(f"Unknown task name: {n!r}")
        kept: List[TaskSpec[object]] = []
        for spec in self._specs.values():
            if spec.name in wanted:
                pruned_deps = tuple(d for d in spec.depends_on if d in wanted)
                kept.append(
                    TaskSpec(
                        name=spec.name,
                        fn=spec.fn,
                        depends_on=pruned_deps,
                        args=spec.args,
                        kwargs=spec.kwargs,
                        retries=spec.retries,
                        timeout=spec.timeout,
                        tags=spec.tags,
                    )
                )
        return Graph.from_specs(kept)

    # ------------------------------------------------------------------ #
    # Visualisation
    # ------------------------------------------------------------------ #
    def to_mermaid(self, orientation: str = "TD") -> str:
        """Render the DAG as a Mermaid ``graph`` definition string.

        No external dependencies; the output can be pasted into Markdown,
        rendered by VS Code's Mermaid previewer, or saved to a file.
        """
        valid = {"TD", "TB", "BT", "LR", "RL"}
        orientation = orientation.upper()
        if orientation not in valid:
            raise ValueError(f"Invalid orientation {orientation!r}; expected one of {sorted(valid)}.")
        lines: List[str] = [f"graph {orientation}"]
        for name in self._specs:
            lines.append(f'    {name}["{name}"]')
        for name, deps in self._deps.items():
            for dep in deps:
                lines.append(f"    {dep} --> {name}")
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------ #
    # Debug
    # ------------------------------------------------------------------ #
    def describe(self) -> str:
        """Human-readable multi-line summary for debugging."""
        out: List[str] = [f"Graph(tasks={len(self._specs)})"]
        for layer_idx, layer in enumerate(self.layers(), 1):
            out.append(f"  Layer {layer_idx}: {layer}")
        return "\n".join(out)

    def __repr__(self) -> str:
        return f"Graph(tasks={len(self._specs)})"

    def __len__(self) -> int:
        return len(self._specs)

    def __contains__(self, name: object) -> bool:
        return name in self._specs
