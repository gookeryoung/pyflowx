"""Tests for cli.clearscreen module."""

from __future__ import annotations

from unittest.mock import patch

import pyflowx as px
from pyflowx.cli.system import clearscreen


# ---------------------------------------------------------------------- #
# main function
# ---------------------------------------------------------------------- #
class TestMain:
    """Test main function."""

    def test_main_creates_graph_and_runs(self) -> None:
        """main() should create a Graph and run it."""
        with patch.object(px, "run") as mock_run:
            clearscreen.main()
            assert mock_run.called
