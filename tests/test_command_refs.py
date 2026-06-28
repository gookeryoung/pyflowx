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
            aliases={
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
            aliases={
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
            aliases={
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
            aliases={
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
            aliases={
                    "cmd1": px.Graph.from_specs(["cmd1", task1]),
                },
            )

    def test_invalid_command_reference_error(self) -> None:
        """Should raise error for invalid command reference."""
        task1 = px.TaskSpec("task1", cmd=["echo", "1"])

        with pytest.raises(ValueError, match="引用的命令 'invalid' 不存在"):
            px.CliRunner(
                strategy="sequential",
            aliases={
                    "cmd1": px.Graph.from_specs(["invalid", task1]),
                },
            )

    def test_invalid_task_reference_error(self) -> None:
        """Should raise error for invalid task reference."""
        task1 = px.TaskSpec("task1", cmd=["echo", "1"])

        with pytest.raises(ValueError, match="任务 'invalid' 不存在于命令 'cmd1' 中"):
            px.CliRunner(
                strategy="sequential",
            aliases={
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
            aliases={
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
            aliases={
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
            aliases={
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

    def test_execution_order_multiple_original_tasks(self) -> None:
        """Should execute multiple original TaskSpecs in correct order."""
        task1 = px.TaskSpec("task1", cmd=["echo", "1"])
        task2 = px.TaskSpec("task2", cmd=["echo", "2"])
        task3 = px.TaskSpec("task3", cmd=["echo", "3"])
        task4 = px.TaskSpec("task4", cmd=["echo", "4"])
        task5 = px.TaskSpec("task5", cmd=["echo", "5"])

        runner = px.CliRunner(
            strategy="sequential",
            aliases={
                "cmd1": px.Graph.from_specs([task1]),
                "cmd2": px.Graph.from_specs([task2]),
                "all": px.Graph.from_specs(["cmd1", "cmd2", task3, task4, task5]),
            },
        )

        # Check execution order through layers
        layers = runner.graphs["all"].layers()

        # Layer 1: task1 (cmd1)
        assert "task1" in layers[0]

        # Layer 2: task2 (cmd2)
        assert "task2" in layers[1]

        # Layer 3: task3 (first original TaskSpec)
        assert "task3" in layers[2]

        # Layer 4: task4 (second original TaskSpec)
        assert "task4" in layers[3]

        # Layer 5: task5 (third original TaskSpec)
        assert "task5" in layers[4]

        # Verify total layers
        assert len(layers) == 5

    def test_execution_order_with_internal_dependencies(self) -> None:
        """Should preserve internal dependencies within referenced commands."""
        task1 = px.TaskSpec("task1", cmd=["echo", "1"])
        task2 = px.TaskSpec("task2", cmd=["echo", "2"], depends_on=("task1",))
        task3 = px.TaskSpec("task3", cmd=["echo", "3"])
        task4 = px.TaskSpec("task4", cmd=["echo", "4"])

        runner = px.CliRunner(
            strategy="sequential",
            aliases={
                "cmd1": px.Graph.from_specs([task1, task2]),
                "cmd2": px.Graph.from_specs([task3]),
                "all": px.Graph.from_specs(["cmd1", "cmd2", task4]),
            },
        )

        # Check execution order through layers
        layers = runner.graphs["all"].layers()

        # Layer 1: task1
        assert "task1" in layers[0]

        # Layer 2: task2 (depends on task1)
        assert "task2" in layers[1]

        # Layer 3: task3 (cmd2, depends on task2)
        assert "task3" in layers[2]

        # Layer 4: task4 (original TaskSpec, depends on task3)
        assert "task4" in layers[3]

        # Verify total layers
        assert len(layers) == 4

    def test_execution_order_pymake_bump_scenario(self) -> None:
        """Should execute pymake bump command in correct order."""
        # Simulate pymake bump scenario
        git_clean = px.TaskSpec("git_clean", cmd=["echo", "clean"])
        typecheck = px.TaskSpec("typecheck", cmd=["echo", "typecheck"])
        lint = px.TaskSpec("lint", cmd=["echo", "lint"])
        format_task = px.TaskSpec("format", cmd=["echo", "format"], depends_on=("lint",))
        git_add_all = px.TaskSpec("git_add_all", cmd=["echo", "git add -A"])
        bump = px.TaskSpec("bumpversion", cmd=["echo", "bumpversion -t"])

        runner = px.CliRunner(
            strategy="sequential",
            aliases={
                "c": px.Graph.from_specs([git_clean]),
                "tc": px.Graph.from_specs([typecheck, "lint"]),
                "lint": px.Graph.from_specs([lint, format_task]),
                "bump": px.Graph.from_specs(["c", "tc", git_add_all, bump]),
            },
        )

        # Check execution order through layers
        layers = runner.graphs["bump"].layers()

        # Layer 1: git_clean (c)
        assert "git_clean" in layers[0]

        # Layer 2: lint (tc.lint, depends on git_clean)
        assert "lint" in layers[1]

        # Layer 3: format (tc.lint.format, depends on lint)
        assert "format" in layers[2]

        # Layer 4: typecheck (tc.typecheck, depends on format)
        assert "typecheck" in layers[3]

        # Layer 5: git_add_all (original TaskSpec, depends on typecheck)
        assert "git_add_all" in layers[4]

        # Layer 6: bumpversion (original TaskSpec, depends on git_add_all)
        assert "bumpversion" in layers[5]

        # Verify total layers
        assert len(layers) == 6

    def test_execution_order_only_references(self) -> None:
        """Should execute only references without original TaskSpecs."""
        task1 = px.TaskSpec("task1", cmd=["echo", "1"])
        task2 = px.TaskSpec("task2", cmd=["echo", "2"])
        task3 = px.TaskSpec("task3", cmd=["echo", "3"])

        runner = px.CliRunner(
            strategy="sequential",
            aliases={
                "cmd1": px.Graph.from_specs([task1]),
                "cmd2": px.Graph.from_specs([task2]),
                "cmd3": px.Graph.from_specs([task3]),
                "all": px.Graph.from_specs(["cmd1", "cmd2", "cmd3"]),
            },
        )

        # Check execution order through layers
        layers = runner.graphs["all"].layers()

        # Layer 1: task1 (cmd1)
        assert "task1" in layers[0]

        # Layer 2: task2 (cmd2, depends on task1)
        assert "task2" in layers[1]

        # Layer 3: task3 (cmd3, depends on task2)
        assert "task3" in layers[2]

        # Verify total layers
        assert len(layers) == 3

    def test_execution_order_only_original_tasks(self) -> None:
        """Should execute only original TaskSpecs without references."""
        task1 = px.TaskSpec("task1", cmd=["echo", "1"])
        task2 = px.TaskSpec("task2", cmd=["echo", "2"])
        task3 = px.TaskSpec("task3", cmd=["echo", "3"])

        runner = px.CliRunner(
            strategy="sequential",
            aliases={
                "all": px.Graph.from_specs([task1, task2, task3]),
            },
        )

        # Check execution order through layers
        layers = runner.graphs["all"].layers()

        # All tasks should be in layer 1 (no dependencies)
        assert "task1" in layers[0]
        assert "task2" in layers[0]
        assert "task3" in layers[0]

        # Verify total layers
        assert len(layers) == 1

    def test_execution_order_single_reference(self) -> None:
        """Should execute single reference correctly."""
        task1 = px.TaskSpec("task1", cmd=["echo", "1"])
        task2 = px.TaskSpec("task2", cmd=["echo", "2"])

        runner = px.CliRunner(
            strategy="sequential",
            aliases={
                "cmd1": px.Graph.from_specs([task1, task2]),
                "all": px.Graph.from_specs(["cmd1"]),
            },
        )

        # Check execution order through layers
        layers = runner.graphs["all"].layers()

        # Should have the same structure as cmd1
        assert "task1" in layers[0]
        assert "task2" in layers[0]

        # Verify total layers
        assert len(layers) == 1

    def test_execution_order_deep_nesting(self) -> None:
        """Should execute deeply nested references correctly."""
        task1 = px.TaskSpec("task1", cmd=["echo", "1"])
        task2 = px.TaskSpec("task2", cmd=["echo", "2"])
        task3 = px.TaskSpec("task3", cmd=["echo", "3"])
        task4 = px.TaskSpec("task4", cmd=["echo", "4"])
        task5 = px.TaskSpec("task5", cmd=["echo", "5"])

        runner = px.CliRunner(
            strategy="sequential",
            aliases={
                "cmd1": px.Graph.from_specs([task1]),
                "cmd2": px.Graph.from_specs(["cmd1", task2]),
                "cmd3": px.Graph.from_specs(["cmd2", task3]),
                "cmd4": px.Graph.from_specs(["cmd3", task4]),
                "cmd5": px.Graph.from_specs(["cmd4", task5]),
            },
        )

        # Check execution order through layers
        layers = runner.graphs["cmd5"].layers()

        # Should execute in order: task1 -> task2 -> task3 -> task4 -> task5
        assert "task1" in layers[0]
        assert "task2" in layers[1]
        assert "task3" in layers[2]
        assert "task4" in layers[3]
        assert "task5" in layers[4]

        # Verify total layers
        assert len(layers) == 5

    def test_execution_order_with_parallel_tasks_in_reference(self) -> None:
        """Should handle parallel tasks within referenced commands."""
        task1 = px.TaskSpec("task1", cmd=["echo", "1"])
        task2 = px.TaskSpec("task2", cmd=["echo", "2"])
        task3 = px.TaskSpec("task3", cmd=["echo", "3"])
        task4 = px.TaskSpec("task4", cmd=["echo", "4"])

        runner = px.CliRunner(
            strategy="sequential",
            aliases={
                "cmd1": px.Graph.from_specs([task1, task2]),  # Parallel tasks
                "cmd2": px.Graph.from_specs([task3, task4]),  # Parallel tasks
                "all": px.Graph.from_specs(["cmd1", "cmd2"]),
            },
        )

        # Check execution order through layers
        layers = runner.graphs["all"].layers()

        # Layer 1: task1 and task2 (cmd1, parallel)
        assert "task1" in layers[0]
        assert "task2" in layers[0]

        # Layer 2: task3 and task4 (cmd2, depends on cmd1's last task)
        # Note: Both task3 and task4 should depend on the last task of cmd1
        assert "task3" in layers[1]
        assert "task4" in layers[1]

        # Verify total layers
        assert len(layers) == 2

    def test_execution_order_complex_mixed_scenario(self) -> None:
        """Should handle complex mixed scenario with references and TaskSpecs."""
        # Create a complex scenario
        clean = px.TaskSpec("clean", cmd=["echo", "clean"])
        build1 = px.TaskSpec("build1", cmd=["echo", "build1"])
        build2 = px.TaskSpec("build2", cmd=["echo", "build2"], depends_on=("build1",))
        test1 = px.TaskSpec("test1", cmd=["echo", "test1"])
        test2 = px.TaskSpec("test2", cmd=["echo", "test2"])
        package = px.TaskSpec("package", cmd=["echo", "package"])
        deploy = px.TaskSpec("deploy", cmd=["echo", "deploy"])

        runner = px.CliRunner(
            strategy="sequential",
            aliases={
                "clean": px.Graph.from_specs([clean]),
                "build": px.Graph.from_specs([build1, build2]),
                "test": px.Graph.from_specs([test1, test2]),
                "release": px.Graph.from_specs(["clean", "build", "test", package, deploy]),
            },
        )

        # Check execution order through layers
        layers = runner.graphs["release"].layers()

        # Layer 1: clean
        assert "clean" in layers[0]

        # Layer 2: build1 (depends on clean)
        assert "build1" in layers[1]

        # Layer 3: build2 (depends on build1)
        assert "build2" in layers[2]

        # Layer 4: test1 and test2 (depends on build2)
        assert "test1" in layers[3]
        assert "test2" in layers[3]

        # Layer 5: package (depends on test1/test2)
        assert "package" in layers[4]

        # Layer 6: deploy (depends on package)
        assert "deploy" in layers[5]

        # Verify total layers
        assert len(layers) == 6
