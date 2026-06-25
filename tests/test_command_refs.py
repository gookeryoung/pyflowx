"""Tests for command reference feature in CliRunner."""

from __future__ import annotations

import pytest

import pyflowx as px


class TestCommandReferences:
    """Test string references in Graph.from_specs."""

    def test_simple_command_reference(self) -> None:
        """Should expand simple command reference."""
        build_task = px.TaskSpec("build", cmd=["echo", "building"])
        test_task = px.TaskSpec("test", cmd=["echo", "testing"])

        runner = px.CliRunner(
            strategy="sequential",
            graphs={
                "build": px.Graph.from_specs([build_task]),
                "test": px.Graph.from_specs([test_task]),
                "all": px.Graph.from_specs([build_task, "test"]),
            },
        )

        # Check that 'all' command has both tasks
        all_tasks = list(runner.graphs["all"].all_specs().keys())
        assert "build" in all_tasks
        assert "test" in all_tasks
        assert len(all_tasks) == 2

    def test_multiple_command_references(self) -> None:
        """Should expand multiple command references."""
        task1 = px.TaskSpec("task1", cmd=["echo", "1"])
        task2 = px.TaskSpec("task2", cmd=["echo", "2"])
        task3 = px.TaskSpec("task3", cmd=["echo", "3"])

        runner = px.CliRunner(
            strategy="sequential",
            graphs={
                "cmd1": px.Graph.from_specs([task1]),
                "cmd2": px.Graph.from_specs([task2]),
                "cmd3": px.Graph.from_specs([task3]),
                "all": px.Graph.from_specs(["cmd1", "cmd2", "cmd3"]),
            },
        )

        # Check that 'all' command has all tasks
        all_tasks = list(runner.graphs["all"].all_specs().keys())
        assert set(all_tasks) == {"task1", "task2", "task3"}

    def test_specific_task_reference(self) -> None:
        """Should expand specific task reference."""
        lint_task = px.TaskSpec("lint", cmd=["echo", "linting"])
        format_task = px.TaskSpec("format", cmd=["echo", "formatting"])

        runner = px.CliRunner(
            strategy="sequential",
            graphs={
                "lint": px.Graph.from_specs([lint_task, format_task]),
                "quick": px.Graph.from_specs(["lint.lint"]),
            },
        )

        # Check that 'quick' command only has lint task
        quick_tasks = list(runner.graphs["quick"].all_specs().keys())
        assert quick_tasks == ["lint"]

    def test_nested_command_reference(self) -> None:
        """Should expand nested command references."""
        task1 = px.TaskSpec("task1", cmd=["echo", "1"])
        task2 = px.TaskSpec("task2", cmd=["echo", "2"])
        task3 = px.TaskSpec("task3", cmd=["echo", "3"])

        runner = px.CliRunner(
            strategy="sequential",
            graphs={
                "cmd1": px.Graph.from_specs([task1]),
                "cmd2": px.Graph.from_specs(["cmd1", task2]),
                "cmd3": px.Graph.from_specs(["cmd2", task3]),
            },
        )

        # Check that 'cmd3' has all tasks
        cmd3_tasks = list(runner.graphs["cmd3"].all_specs().keys())
        assert set(cmd3_tasks) == {"task1", "task2", "task3"}

    def test_circular_reference_error(self) -> None:
        """Should raise error for circular references."""
        task1 = px.TaskSpec("task1", cmd=["echo", "1"])

        with pytest.raises(ValueError, match="循环引用"):
            px.CliRunner(
                strategy="sequential",
                graphs={
                    "cmd1": px.Graph.from_specs(["cmd1", task1]),
                },
            )

    def test_invalid_command_reference_error(self) -> None:
        """Should raise error for invalid command reference."""
        task1 = px.TaskSpec("task1", cmd=["echo", "1"])

        with pytest.raises(ValueError, match="引用的命令 'invalid' 不存在"):
            px.CliRunner(
                strategy="sequential",
                graphs={
                    "cmd1": px.Graph.from_specs(["invalid", task1]),
                },
            )

    def test_invalid_task_reference_error(self) -> None:
        """Should raise error for invalid task reference."""
        task1 = px.TaskSpec("task1", cmd=["echo", "1"])

        with pytest.raises(ValueError, match="任务 'invalid' 不存在于命令 'cmd1' 中"):
            px.CliRunner(
                strategy="sequential",
                graphs={
                    "cmd1": px.Graph.from_specs([task1]),
                    "cmd2": px.Graph.from_specs(["cmd1.invalid"]),
                },
            )

    def test_reference_preserves_dependencies(self) -> None:
        """Should preserve dependencies when expanding references."""
        task1 = px.TaskSpec("task1", cmd=["echo", "1"])
        task2 = px.TaskSpec("task2", cmd=["echo", "2"], depends_on=("task1",))

        runner = px.CliRunner(
            strategy="sequential",
            graphs={
                "cmd1": px.Graph.from_specs([task1, task2]),
                "cmd2": px.Graph.from_specs(["cmd1"]),
            },
        )

        # Check that dependencies are preserved
        cmd2_deps = runner.graphs["cmd2"].deps
        assert cmd2_deps["task2"] == ("task1",)

    def test_mixed_references_and_tasks(self) -> None:
        """Should handle mixed references and direct tasks."""
        task1 = px.TaskSpec("task1", cmd=["echo", "1"])
        task2 = px.TaskSpec("task2", cmd=["echo", "2"])
        task3 = px.TaskSpec("task3", cmd=["echo", "3"])

        runner = px.CliRunner(
            strategy="sequential",
            graphs={
                "cmd1": px.Graph.from_specs([task1, task2]),
                "cmd2": px.Graph.from_specs(["cmd1", task3]),
            },
        )

        # Check that 'cmd2' has all tasks
        cmd2_tasks = list(runner.graphs["cmd2"].all_specs().keys())
        assert set(cmd2_tasks) == {"task1", "task2", "task3"}

    def test_execution_order_with_references(self) -> None:
        """Should execute references in correct order."""
        task1 = px.TaskSpec("task1", cmd=["echo", "step1"])
        task2 = px.TaskSpec("task2", cmd=["echo", "step2"])
        task3 = px.TaskSpec("task3", cmd=["echo", "step3"])
        task4 = px.TaskSpec("task4", cmd=["echo", "step4"])
        task5 = px.TaskSpec("task5", cmd=["echo", "step5"])

        runner = px.CliRunner(
            strategy="sequential",
            graphs={
                "cmd1": px.Graph.from_specs([task1]),
                "cmd2": px.Graph.from_specs([task2, task3]),
                "cmd3": px.Graph.from_specs([task4]),
                "ordered": px.Graph.from_specs(["cmd1", "cmd2", "cmd3", task5]),
            },
        )

        # Check execution order through layers
        layers = runner.graphs["ordered"].layers()

        # Layer 1 should have task1 (cmd1)
        assert "task1" in layers[0]

        # Layer 2 should have task2 and task3 (cmd2)
        assert "task2" in layers[1]
        assert "task3" in layers[1]

        # Layer 3 should have task4 (cmd3)
        assert "task4" in layers[2]

        # Layer 4 should have task5 (original task)
        assert "task5" in layers[3]

        # Verify total layers
        assert len(layers) == 4
