# apps/api/agentflow_api/rate_limiter.py
"""
Rate limiting and error handling utilities for AgentFlow.

Implements:
- Exponential backoff with jitter for retries
- Circuit breaker pattern for repeated failures
- OpenAI-specific rate limit handling
- Request throttling
"""

import asyncio
import time
import random
from typing import Callable, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import wraps
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# EXPONENTIAL BACKOFF WITH JITTER
# ============================================================================

@dataclass
class RetryConfig:
    """Configuration for retry logic."""
    max_retries: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    exponential_base: float = 2.0
    jitter: bool = True  # Add randomness to prevent thundering herd


def calculate_backoff(attempt: int, config: RetryConfig) -> float:
    """
    Calculate backoff delay with exponential backoff and optional jitter.
    
    Formula: min(base_delay * (exponential_base ^ attempt), max_delay)
    With jitter: multiply by random factor between 0.5 and 1.5
    """
    delay = min(
        config.base_delay * (config.exponential_base ** attempt),
        config.max_delay
    )
    
    if config.jitter:
        # Add ±50% jitter to prevent thundering herd
        jitter_factor = 0.5 + random.random()  # 0.5 to 1.5
        delay *= jitter_factor
    
    return delay


def retry_with_backoff(
    config: Optional[RetryConfig] = None,
    exceptions: tuple = (Exception,)
):
    """
    Decorator to retry a function with exponential backoff.
    
    Usage:
        @retry_with_backoff(exceptions=(OpenAIError, APIConnectionError))
        async def call_openai_api():
            ...
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    # Check if it's a rate limit error (429)
                    is_rate_limit = (
                        hasattr(e, 'status_code') and e.status_code == 429
                    ) or (
                        '429' in str(e) or 'rate limit' in str(e).lower()
                    )
                    
                    if attempt == config.max_retries:
                        logger.error(
                            f"Failed after {config.max_retries} retries: {e}"
                        )
                        raise
                    
                    delay = calculate_backoff(attempt, config)
                    
                    # For rate limits, respect Retry-After header if available
                    if is_rate_limit and hasattr(e, 'headers'):
                        retry_after = e.headers.get('Retry-After')
                        if retry_after:
                            try:
                                delay = max(delay, float(retry_after))
                            except ValueError:
                                pass
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{config.max_retries} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    
                    await asyncio.sleep(delay)
            
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    is_rate_limit = (
                        hasattr(e, 'status_code') and e.status_code == 429
                    ) or (
                        '429' in str(e) or 'rate limit' in str(e).lower()
                    )
                    
                    if attempt == config.max_retries:
                        logger.error(
                            f"Failed after {config.max_retries} retries: {e}"
                        )
                        raise
                    
                    delay = calculate_backoff(attempt, config)
                    
                    if is_rate_limit and hasattr(e, 'headers'):
                        retry_after = e.headers.get('Retry-After')
                        if retry_after:
                            try:
                                delay = max(delay, float(retry_after))
                            except ValueError:
                                pass
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{config.max_retries} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    
                    time.sleep(delay)
            
            raise last_exception
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# ============================================================================
# CIRCUIT BREAKER
# ============================================================================

@dataclass
class CircuitBreakerState:
    """State of a circuit breaker."""
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    state: str = "closed"  # closed, open, half_open
    success_count: int = 0


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.
    
    States:
    - CLOSED: Normal operation, requests go through
    - OPEN: Too many failures, requests fail fast
    - HALF_OPEN: Testing if service recovered
    
    Usage:
        breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60.0,
            success_threshold=2
        )
        
        result = await breaker.call(my_async_function, arg1, arg2)
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 2,
        name: str = "default"
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.name = name
        self.state = CircuitBreakerState()
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function through the circuit breaker."""
        async with self._lock:
            current_state = self._get_state()
            
            if current_state == "open":
                logger.warning(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Failing fast without calling function."
                )
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is open. "
                    f"Service unavailable."
                )
        
        try:
            # Call the function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Success - record it
            await self._on_success()
            return result
            
        except Exception as e:
            # Failure - record it
            await self._on_failure()
            raise
    
    def _get_state(self) -> str:
        """Determine current state based on failures and time."""
        if self.state.state == "closed":
            return "closed"
        
        if self.state.state == "open":
            # Check if recovery timeout has passed
            if self.state.last_failure_time:
                time_since_failure = (
                    datetime.now() - self.state.last_failure_time
                ).total_seconds()
                
                if time_since_failure >= self.recovery_timeout:
                    # Move to half-open to test recovery
                    self.state.state = "half_open"
                    self.state.success_count = 0
                    logger.info(
                        f"Circuit breaker '{self.name}' moving to HALF_OPEN"
                    )
                    return "half_open"
            
            return "open"
        
        # half_open state
        return "half_open"
    
    async def _on_success(self):
        """Handle successful execution."""
        async with self._lock:
            if self.state.state == "half_open":
                self.state.success_count += 1
                
                if self.state.success_count >= self.success_threshold:
                    # Recovery confirmed - close circuit
                    self.state.state = "closed"
                    self.state.failure_count = 0
                    self.state.success_count = 0
                    logger.info(
                        f"Circuit breaker '{self.name}' CLOSED (recovered)"
                    )
            
            elif self.state.state == "closed":
                # Reset failure count on success
                self.state.failure_count = 0
    
    async def _on_failure(self):
        """Handle failed execution."""
        async with self._lock:
            self.state.failure_count += 1
            self.state.last_failure_time = datetime.now()
            
            if self.state.state == "half_open":
                # Failure during testing - reopen circuit
                self.state.state = "open"
                self.state.success_count = 0
                logger.warning(
                    f"Circuit breaker '{self.name}' reopened (test failed)"
                )
            
            elif self.state.state == "closed":
                if self.state.failure_count >= self.failure_threshold:
                    # Too many failures - open circuit
                    self.state.state = "open"
                    logger.error(
                        f"Circuit breaker '{self.name}' OPENED "
                        f"({self.state.failure_count} failures)"
                    )
    
    def get_status(self) -> dict:
        """Get current circuit breaker status."""
        return {
            "name": self.name,
            "state": self.state.state,
            "failure_count": self.state.failure_count,
            "success_count": self.state.success_count,
            "last_failure": (
                self.state.last_failure_time.isoformat()
                if self.state.last_failure_time else None
            )
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


# ============================================================================
# CONCURRENT REQUEST LIMITER
# ============================================================================

class ConcurrentRequestLimiter:
    """
    Limit number of concurrent operations.
    
    Usage:
        limiter = ConcurrentRequestLimiter(max_concurrent=10)
        
        async with limiter:
            # Your code here
            await some_operation()
    """
    
    def __init__(self, max_concurrent: int = 10, name: str = "default"):
        self.max_concurrent = max_concurrent
        self.name = name
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.current_count = 0
        self._lock = asyncio.Lock()
    
    async def __aenter__(self):
        await self.semaphore.acquire()
        async with self._lock:
            self.current_count += 1
            logger.debug(
                f"Limiter '{self.name}': {self.current_count}/{self.max_concurrent}"
            )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        async with self._lock:
            self.current_count -= 1
        self.semaphore.release()
    
    def get_status(self) -> dict:
        """Get current limiter status."""
        return {
            "name": self.name,
            "current": self.current_count,
            "max": self.max_concurrent,
            "available": self.max_concurrent - self.current_count
        }


# ============================================================================
# GLOBAL INSTANCES (Singleton Pattern)
# ============================================================================

# Circuit breaker for OpenAI API calls
openai_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60.0,
    success_threshold=2,
    name="openai_api"
)

# Concurrent workflow limiter
workflow_limiter = ConcurrentRequestLimiter(
    max_concurrent=10,
    name="workflows"
)

# Concurrent API request limiter (for direct agent endpoints)
api_limiter = ConcurrentRequestLimiter(
    max_concurrent=20,
    name="api_requests"
)
