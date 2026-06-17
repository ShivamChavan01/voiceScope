import pytest
from utils.resilience import CircuitBreaker, with_retry


class TestCircuitBreaker:
    def test_initial_state(self):
        cb = CircuitBreaker()
        assert cb.state == "closed"
        assert cb.failure_count == 0

    def test_record_failure(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        assert cb.failure_count == 1
        assert cb.state == "closed"

    def test_circuit_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"
        assert cb.is_open() is True

    def test_record_success_resets(self):
        cb = CircuitBreaker()
        cb.record_failure()
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.state == "closed"


class TestWithRetry:
    @pytest.mark.asyncio
    async def test_successful_call(self):
        @with_retry(max_retries=2)
        async def success():
            return "ok"

        result = await success()
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        call_count = 0

        @with_retry(max_retries=2, base_delay=0.01)
        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("fail")
            return "ok"

        result = await fail_then_succeed()
        assert result == "ok"
        assert call_count == 2
