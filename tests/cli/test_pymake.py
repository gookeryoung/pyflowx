"""Tests for pymake CLI."""

from pyflowx.cli.pymake import build_graphs, conf, get_maturin_build_command


def test_pymake_config_attributes():
    """Test PymakeConfig has expected attributes."""
    assert hasattr(conf, "PROJECT_ROOT")
    assert hasattr(conf, "BUILD_TOOL")
    assert hasattr(conf, "BUILD_COMMAND")
    assert hasattr(conf, "MATURIN_TOOL")
    assert hasattr(conf, "MATURIN_BUILD_COMMAND")
    assert hasattr(conf, "MATURIN_DEV_COMMAND")
    assert hasattr(conf, "TIMEOUT")


def test_pymake_config_values():
    """Test PymakeConfig values are correct."""
    assert conf.BUILD_TOOL == "uv"
    assert conf.BUILD_COMMAND == ["uv", "build"]
    assert conf.MATURIN_TOOL == "maturin"
    assert conf.TIMEOUT == 600


def test_get_maturin_build_command_basic():
    """Test get_maturin_build_command returns base command."""
    cmd = get_maturin_build_command()
    assert "maturin" in cmd
    assert "build" in cmd
    assert "-r" in cmd


def testbuild_graphs_returns_dict():
    """Test build_graphs returns a dictionary."""
    graphs = build_graphs()
    assert isinstance(graphs, dict)
    assert len(graphs) > 0


def testbuild_graphs_has_expected_commands():
    """Test build_graphs has expected command keys."""
    graphs = build_graphs()
    expected_commands = [
        "b",
        "bc",
        "ba",
        "ic",
        "ip",
        "ia",
        "cp",
        "cc",
        "ca",
        "t",
        "lint",
    ]
    for cmd in expected_commands:
        assert cmd in graphs, f"Expected command '{cmd}' not found in graphs"


def testbuild_graphs_values_are_graphs():
    """Test build_graphs values are Graph instances."""
    import pyflowx as px

    graphs = build_graphs()
    for name, graph in graphs.items():
        assert isinstance(graph, px.Graph), (
            f"Graph for command '{name}' is not a Graph instance"
        )


def test_build_command_graph_structure():
    """Test 'b' command graph has correct structure."""

    graphs = build_graphs()
    graph = graphs["b"]
    assert len(graph.all_specs()) == 1
    spec = graph.spec("uv_build")
    assert spec.cmd == conf.BUILD_COMMAND


def test_build_all_command_graph_structure():
    """Test 'ba' command graph has correct dependencies."""

    graphs = build_graphs()
    graph = graphs["ba"]
    specs = graph.all_specs()
    assert len(specs) == 2
    # Check dependency
    uv_build_spec = graph.spec("uv_build")
    assert "maturin_build" in uv_build_spec.depends_on


def test_maturin_build_command_graph_structure():
    """Test 'bc' command graph has correct structure."""
    graphs = build_graphs()
    graph = graphs["bc"]
    specs = graph.all_specs()
    assert len(specs) == 1
    spec = graph.spec("maturin_build")
    assert spec.cmd == get_maturin_build_command()


def test_install_all_command_graph_structure():
    """Test 'ia' command graph has correct dependencies."""
    graphs = build_graphs()
    graph = graphs["ia"]
    specs = graph.all_specs()
    assert len(specs) == 2
    uv_install_spec = graph.spec("uv_install")
    assert "maturin_dev" in uv_install_spec.depends_on


def test_clean_all_command_graph_structure():
    """Test 'ca' command graph has correct structure."""
    graphs = build_graphs()
    graph = graphs["ca"]
    specs = graph.all_specs()
    assert len(specs) == 2


def test_test_command_graph_structure():
    """Test 't' command graph has correct structure."""
    graphs = build_graphs()
    graph = graphs["t"]
    specs = graph.all_specs()
    assert len(specs) == 1
    spec = graph.spec("pytest")
    assert "pytest" in spec.cmd


def test_lint_command_graph_structure():
    """Test 'lint' command graph has correct structure."""
    graphs = build_graphs()
    graph = graphs["lint"]
    specs = graph.all_specs()
    assert len(specs) == 1
    spec = graph.spec("ruff_check")
    assert "ruff" in spec.cmd


def test_pymake_config_dirs_to_ignore():
    """Test PymakeConfig has correct dirs to ignore."""
    assert ".venv" in conf.DIRS_TO_IGNORE
    assert ".git" in conf.DIRS_TO_IGNORE
    assert ".tox" in conf.DIRS_TO_IGNORE


def test_pymake_config_python_build_dirs():
    """Test PymakeConfig has correct Python build dirs."""
    assert "dist" in conf.PYTHON_BUILD_DIRS
    assert "build" in conf.PYTHON_BUILD_DIRS


def test_maturin_build_options_win7():
    """Test MATURIN_BUILD_OPTIONS_WIN7 has expected options."""
    assert "--target" in conf.MATURIN_BUILD_OPTIONS_WIN7
    assert "x86_64-win7-windows-msvc" in conf.MATURIN_BUILD_OPTIONS_WIN7
    assert "-Zbuild-std" in conf.MATURIN_BUILD_OPTIONS_WIN7


def test_doc_build_command():
    """Test DOC_BUILD_COMMAND has expected structure."""
    assert "sphinx-build" in conf.DOC_BUILD_COMMAND
    assert "-b" in conf.DOC_BUILD_COMMAND
    assert "html" in conf.DOC_BUILD_COMMAND
