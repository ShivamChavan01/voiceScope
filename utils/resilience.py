import asyncio
import time
from functools import wraps
from typing import Callable, Any
from utils.logger import logger


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "closed"

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(f"[CircuitBreaker] state=open failures={self.failure_count}")

    def record_success(self):
        self.failure_count = 0
        self.state = "closed"

    def is_open(self) -> bool:
        if self.state == "open":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
                logger.info("[CircuitBreaker] state=half-open")
                return False
            return True
        return False


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(base_delay * (exponential_base**attempt), max_delay)
                        logger.warning(
                            f"[Retry] attempt={attempt + 1} delay={delay:.1f}s error={e}"
                        )
                        await asyncio.sleep(delay)
            raise last_exception

        return wrapper

    return decorator
