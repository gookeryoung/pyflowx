import time

import pytest
from pytest_mock import MockerFixture

from pyflowx.utils import _perf_metrics, perf_timer


@pytest.fixture(autouse=True)
def reset_perf_metrics():
    """重置性能指标."""
    _perf_metrics.clear()


class TestPerformanceTimer:
    def test_perf_timer(self):

        @perf_timer()
        def test_func():
            time.sleep(0.1)

        test_func()

        assert _perf_metrics["test_func"] is not None
        assert _perf_metrics["test_func"]["count"] == 1
        assert _perf_metrics["test_func"]["total_time"] >= 0.1

    def test_perf_timer_report(self, mocker: MockerFixture):
        mock_log = mocker.patch("logging.info")

        @perf_timer(report=True, unit="ms", precision=3)
        def test_func():
            time.sleep(0.1)

        test_func()

        assert _perf_metrics["test_func"] is not None
        assert _perf_metrics["test_func"]["count"] == 1
        assert _perf_metrics["test_func"]["total_time"] >= 0.1

        assert mock_log.call_count == 1

    def test_generate_report(self, mocker: MockerFixture, caplog: pytest.LogCaptureFixture):
        mock_log = mocker.patch("logging.info")

        from pyflowx.utils import _generate_report

        @perf_timer(report=True, unit="ms", precision=3)
        def test_func():
            time.sleep(0.1)

        @perf_timer(report=True, unit="ms", precision=3)
        def test_func2():
            time.sleep(0.2)

        test_func()
        test_func2()

        _generate_report("ms", 3)

        assert mock_log.call_count == 3
        assert _perf_metrics["test_func"]["count"] == 1
        assert _perf_metrics["test_func"]["total_time"] >= 0.1
        assert _perf_metrics["test_func2"]["count"] == 1
        assert _perf_metrics["test_func2"]["total_time"] >= 0.2
