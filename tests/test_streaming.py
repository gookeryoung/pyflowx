"""Tests for streaming result passing (iterators between tasks)."""

from __future__ import annotations

from typing import Iterator

import pyflowx as px


def test_generator_passed_as_iterator() -> None:
    """上游返回生成器，下游应能惰性消费."""

    @px.task
    def source() -> Iterator[int]:
        yield from range(5)

    @px.task(depends_on=("source",))
    def consume(source: Iterator[int]) -> int:
        return sum(source)

    graph = px.Graph.from_specs([source, consume])
    report = px.run(graph)
    assert report.success
    assert report["consume"] == 10


def test_large_range_streaming() -> None:
    """大范围迭代器流式传递，避免中间列表."""

    @px.task
    def numbers() -> Iterator[int]:
        yield from range(1000)

    @px.task(depends_on=("numbers",))
    def total(numbers: Iterator[int]) -> int:
        return sum(numbers)

    graph = px.Graph.from_specs([numbers, total])
    report = px.run(graph)
    assert report.success
    assert report["total"] == sum(range(1000))


def test_chain_multiple_streams() -> None:
    """多个流式任务串联."""

    @px.task
    def gen() -> Iterator[int]:
        yield from range(10)

    @px.task(depends_on=("gen",))
    def doubled(gen: Iterator[int]) -> Iterator[int]:
        for x in gen:
            yield x * 2

    @px.task(depends_on=("doubled",))
    def collect(doubled: Iterator[int]) -> list[int]:
        return list(doubled)

    graph = px.Graph.from_specs([gen, doubled, collect])
    report = px.run(graph)
    assert report.success
    assert report["collect"] == [x * 2 for x in range(10)]
