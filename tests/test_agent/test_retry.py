"""LLM 重试模块测试"""
import litellm

from voice_assistant.agent.retry import (
    ErrorClass,
    RetryPolicy,
    classify_error,
    compute_delay,
    get_retry_after,
    should_retry,
)


class TestClassifyError:
    def test_rate_limit_error(self):
        exc = litellm.RateLimitError(
            message="rate limited",
            model="gpt-4",
            llm_provider="openai",
        )
        assert classify_error(exc) == ErrorClass.RATE_LIMIT

    def test_timeout_error(self):
        exc = litellm.Timeout(message="timed out", model="gpt-4", llm_provider="openai")
        assert classify_error(exc) == ErrorClass.TIMEOUT

    def test_connection_error(self):
        exc = litellm.APIConnectionError(message="conn failed", model="gpt-4", llm_provider="openai")
        assert classify_error(exc) == ErrorClass.CONNECTION

    def test_api_error(self):
        exc = litellm.APIError(
            message="server error", model="gpt-4", llm_provider="openai", status_code=500
        )
        assert classify_error(exc) == ErrorClass.SERVER_ERROR

    def test_generic_exception(self):
        assert classify_error(RuntimeError("oops")) == ErrorClass.UNKNOWN


class TestShouldRetry:
    def test_retryable_errors(self):
        assert should_retry(ErrorClass.RATE_LIMIT)
        assert should_retry(ErrorClass.TIMEOUT)
        assert should_retry(ErrorClass.CONNECTION)
        assert should_retry(ErrorClass.SERVER_ERROR)

    def test_non_retryable_errors(self):
        assert not should_retry(ErrorClass.CLIENT_ERROR)
        assert not should_retry(ErrorClass.UNKNOWN)


class TestComputeDelay:
    def test_exponential_backoff(self):
        policy = RetryPolicy(base_delay=1.0, backoff_factor=2.0, jitter=0.0, max_delay=30.0)
        assert compute_delay(0, policy, ErrorClass.SERVER_ERROR) == 1.0
        assert compute_delay(1, policy, ErrorClass.SERVER_ERROR) == 2.0
        assert compute_delay(2, policy, ErrorClass.SERVER_ERROR) == 4.0
        assert compute_delay(3, policy, ErrorClass.SERVER_ERROR) == 8.0

    def test_max_delay_cap(self):
        policy = RetryPolicy(base_delay=1.0, backoff_factor=2.0, jitter=0.0, max_delay=5.0)
        assert compute_delay(10, policy, ErrorClass.SERVER_ERROR) == 5.0

    def test_retry_after_overrides(self):
        policy = RetryPolicy(base_delay=1.0, backoff_factor=2.0, jitter=0.0, max_delay=30.0)
        delay = compute_delay(0, policy, ErrorClass.RATE_LIMIT, retry_after=10.0)
        assert delay == 10.0

    def test_retry_after_capped_by_max(self):
        policy = RetryPolicy(base_delay=1.0, backoff_factor=2.0, jitter=0.0, max_delay=5.0)
        delay = compute_delay(0, policy, ErrorClass.RATE_LIMIT, retry_after=60.0)
        assert delay == 5.0

    def test_jitter_adds_variance(self):
        policy = RetryPolicy(base_delay=10.0, backoff_factor=1.0, jitter=0.5, max_delay=30.0)
        delays = [compute_delay(0, policy, ErrorClass.SERVER_ERROR) for _ in range(100)]
        # 有抖动，不应所有值相同
        assert len(set(delays)) > 1
        # 所有延迟在合理范围内
        for d in delays:
            assert 5.0 <= d <= 15.0

    def test_non_rate_limit_ignores_retry_after(self):
        policy = RetryPolicy(base_delay=1.0, backoff_factor=2.0, jitter=0.0, max_delay=30.0)
        delay = compute_delay(0, policy, ErrorClass.SERVER_ERROR, retry_after=10.0)
        # 非限流错误忽略 Retry-After
        assert delay == 1.0


class TestGetRetryAfter:
    def test_no_headers(self):
        assert get_retry_after(RuntimeError("oops")) is None

    def test_with_retry_after_header(self):
        class MockResponse:
            headers = {"retry-after": "5"}

        class MockError(Exception):
            response = MockResponse()

        assert get_retry_after(MockError("test")) == 5.0

    def test_invalid_retry_after(self):
        class MockResponse:
            headers = {"retry-after": "invalid"}

        class MockError(Exception):
            response = MockResponse()

        assert get_retry_after(MockError("test")) is None


class TestRetryPolicy:
    def test_default_values(self):
        from voice_assistant.agent.retry import DEFAULT_RETRY_POLICY
        assert DEFAULT_RETRY_POLICY.max_retries == 3
        assert DEFAULT_RETRY_POLICY.base_delay == 1.0
        assert DEFAULT_RETRY_POLICY.max_delay == 30.0
