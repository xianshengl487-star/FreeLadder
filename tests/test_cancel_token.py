# path: tests/test_cancel_token.py
"""CancelToken 单元测试"""

import threading
import time

import pytest

from freeladder.core.cancel_token import CancelToken


class TestCancelToken:
    def test_init_not_cancelled(self):
        token = CancelToken()
        assert token.cancelled is False

    def test_cancel_sets_flag(self):
        token = CancelToken()
        token.cancel()
        assert token.cancelled is True

    def test_double_cancel(self):
        token = CancelToken()
        token.cancel()
        token.cancel()
        assert token.cancelled is True

    def test_raise_if_cancelled_when_not(self):
        token = CancelToken()
        token.raise_if_cancelled()  # Should not raise

    def test_raise_if_cancelled_when_cancelled(self):
        token = CancelToken()
        token.cancel()
        with pytest.raises(CancelToken.CancelledError):
            token.raise_if_cancelled()

    def test_wait_returns_immediately_when_cancelled(self):
        token = CancelToken()
        token.cancel()
        result = token.wait(timeout=1.0)
        assert result is True

    def test_wait_timeout(self):
        token = CancelToken()
        result = token.wait(timeout=0.05)
        assert result is False
        assert token.cancelled is False

    def test_wait_in_thread(self):
        token = CancelToken()

        def cancel_after():
            time.sleep(0.05)
            token.cancel()

        t = threading.Thread(target=cancel_after)
        t.start()
        result = token.wait(timeout=2.0)
        t.join()
        assert result is True
        assert token.cancelled is True

    def test_cancelled_error_is_exception(self):
        assert issubclass(CancelToken.CancelledError, Exception)
