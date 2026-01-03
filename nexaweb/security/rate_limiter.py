"""
NexaWeb Rate Limiter
====================

Request rate limiting for API protection and abuse prevention.

Features:
- Multiple algorithms (Token Bucket, Sliding Window, Fixed Window)
- In-memory and Redis backends
- Per-IP, per-user, per-endpoint limiting
- Customizable response handling
- Burst allowance

Example:
    # Global rate limit
    app.use(RateLimitMiddleware(requests=100, window=60))
    
    # Per-route rate limit
    @app.get("/api/expensive")
    @rate_limit(requests=10, window=60)
    async def expensive_operation(request):
        ...
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import wraps
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Optional,
    Tuple,
)

from nexaweb.core.middleware import Middleware

if TYPE_CHECKING:
    from nexaweb.core.request import Request
    from nexaweb.core.response import Response


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    
    # Maximum requests allowed
    requests: int = 100
    
    # Time window in seconds
    window: int = 60
    
    # Burst allowance (extra requests allowed)
    burst: int = 10
    
    # Key function to identify clients
    key_func: Optional[Callable[["Request"], str]] = None
    
    # Response status on limit exceeded
    status_code: int = 429
    
    # Response message
    message: str = "Rate limit exceeded. Please try again later."
    
    # Headers to include in response
    include_headers: bool = True
    
    # Header names
    header_limit: str = "X-RateLimit-Limit"
    header_remaining: str = "X-RateLimit-Remaining"
    header_reset: str = "X-RateLimit-Reset"


@dataclass
class RateLimitResult:
    """Result of rate limit check."""
    allowed: bool
    remaining: int
    reset_at: float
    limit: int


class RateLimitBackend(ABC):
    """Abstract backend for rate limit storage."""
    
    @abstractmethod
    async def check(
        self,
        key: str,
        limit: int,
        window: int,
        burst: int,
    ) -> RateLimitResult:
        """Check if request is allowed."""
        pass
        
    @abstractmethod
    async def reset(self, key: str) -> None:
        """Reset rate limit for key."""
        pass


class InMemoryBackend(RateLimitBackend):
    """
    In-memory rate limit backend.
    
    Uses sliding window algorithm for accurate rate limiting.
    Suitable for single-instance deployments.
    """
    
    def __init__(self) -> None:
        self._buckets: Dict[str, list] = {}
        self._lock = asyncio.Lock()
        
    async def check(
        self,
        key: str,
        limit: int,
        window: int,
        burst: int,
    ) -> RateLimitResult:
        """Check rate limit using sliding window."""
        async with self._lock:
            now = time.time()
            window_start = now - window
            
            # Get or create bucket
            if key not in self._buckets:
                self._buckets[key] = []
                
            bucket = self._buckets[key]
            
            # Remove expired timestamps
            bucket[:] = [ts for ts in bucket if ts > window_start]
            
            # Calculate remaining
            current_count = len(bucket)
            effective_limit = limit + burst
            remaining = effective_limit - current_count
            
            # Check if allowed
            if current_count < effective_limit:
                bucket.append(now)
                allowed = True
                remaining -= 1
            else:
                allowed = False
                
            # Calculate reset time
            if bucket:
                reset_at = bucket[0] + window
            else:
                reset_at = now + window
                
            return RateLimitResult(
                allowed=allowed,
                remaining=max(0, remaining),
                reset_at=reset_at,
                limit=limit,
            )
            
    async def reset(self, key: str) -> None:
        """Reset rate limit for key."""
        async with self._lock:
            if key in self._buckets:
                del self._buckets[key]
                
    async def cleanup(self) -> None:
        """Remove expired entries."""
        async with self._lock:
            now = time.time()
            expired_keys = []
            
            for key, bucket in self._buckets.items():
                # Remove entries older than 1 hour
                if not bucket or bucket[-1] < now - 3600:
                    expired_keys.append(key)
                    
            for key in expired_keys:
                del self._buckets[key]


class TokenBucketBackend(RateLimitBackend):
    """
    Token bucket rate limit backend.
    
    Allows burst traffic while maintaining average rate.
    """
    
    def __init__(self) -> None:
        self._buckets: Dict[str, Tuple[float, float]] = {}  # key -> (tokens, last_update)
        self._lock = asyncio.Lock()
        
    async def check(
        self,
        key: str,
        limit: int,
        window: int,
        burst: int,
    ) -> RateLimitResult:
        """Check rate limit using token bucket."""
        async with self._lock:
            now = time.time()
            
            # Calculate refill rate (tokens per second)
            refill_rate = limit / window
            max_tokens = limit + burst
            
            # Get or create bucket
            if key not in self._buckets:
                tokens = max_tokens
                last_update = now
            else:
                tokens, last_update = self._buckets[key]
                
                # Add tokens based on time elapsed
                elapsed = now - last_update
                tokens = min(max_tokens, tokens + elapsed * refill_rate)
                
            # Check if request is allowed
            if tokens >= 1:
                tokens -= 1
                allowed = True
            else:
                allowed = False
                
            # Update bucket
            self._buckets[key] = (tokens, now)
            
            # Calculate reset time (time until full)
            tokens_needed = max_tokens - tokens
            reset_at = now + (tokens_needed / refill_rate)
            
            return RateLimitResult(
                allowed=allowed,
                remaining=int(tokens),
                reset_at=reset_at,
                limit=limit,
            )
            
    async def reset(self, key: str) -> None:
        """Reset rate limit for key."""
        async with self._lock:
            if key in self._buckets:
                del self._buckets[key]


class RateLimiter:
    """
    Rate limiter with configurable backend.
    
    Example:
        limiter = RateLimiter(requests=100, window=60)
        
        async def handle_request(request):
            result = await limiter.check(request)
            if not result.allowed:
                return rate_limit_response()
            # Process request...
    """
    
    def __init__(
        self,
        requests: int = 100,
        window: int = 60,
        burst: int = 10,
        backend: Optional[RateLimitBackend] = None,
        key_func: Optional[Callable[["Request"], str]] = None,
    ) -> None:
        """
        Initialize rate limiter.
        
        Args:
            requests: Maximum requests per window
            window: Time window in seconds
            burst: Extra burst allowance
            backend: Storage backend
            key_func: Function to extract client key
        """
        self.requests = requests
        self.window = window
        self.burst = burst
        self.backend = backend or InMemoryBackend()
        self.key_func = key_func or self._default_key_func
        
    def _default_key_func(self, request: "Request") -> str:
        """Default key function using client IP."""
        return f"rate_limit:{request.client_ip}"
        
    async def check(self, request: "Request") -> RateLimitResult:
        """Check if request is allowed."""
        key = self.key_func(request)
        return await self.backend.check(
            key=key,
            limit=self.requests,
            window=self.window,
            burst=self.burst,
        )
        
    async def reset(self, request: "Request") -> None:
        """Reset rate limit for request."""
        key = self.key_func(request)
        await self.backend.reset(key)


class RateLimitMiddleware(Middleware):
    """
    Rate limiting middleware.
    
    Applies rate limits to all requests or specific paths.
    
    Example:
        app.use(RateLimitMiddleware(
            requests=100,
            window=60,
            exempt_paths=["/health", "/metrics"]
        ))
    """
    
    def __init__(
        self,
        requests: int = 100,
        window: int = 60,
        burst: int = 10,
        backend: Optional[RateLimitBackend] = None,
        key_func: Optional[Callable[["Request"], str]] = None,
        exempt_paths: Optional[list] = None,
        config: Optional[RateLimitConfig] = None,
    ) -> None:
        """Initialize rate limit middleware."""
        self.config = config or RateLimitConfig(
            requests=requests,
            window=window,
            burst=burst,
            key_func=key_func,
        )
        
        self.limiter = RateLimiter(
            requests=self.config.requests,
            window=self.config.window,
            burst=self.config.burst,
            backend=backend,
            key_func=self.config.key_func,
        )
        
        self.exempt_paths = exempt_paths or []
        
    async def before(self, request: "Request") -> Optional["Response"]:
        """Check rate limit before processing."""
        from nexaweb.core.response import JSONResponse
        
        # Check exempt paths
        for path in self.exempt_paths:
            if request.path.startswith(path):
                return None
                
        # Check rate limit
        result = await self.limiter.check(request)
        
        # Store result for response headers
        request.state["rate_limit"] = result
        
        if not result.allowed:
            response = JSONResponse(
                {"error": self.config.message},
                status_code=self.config.status_code,
            )
            
            if self.config.include_headers:
                self._add_headers(response, result)
                
            return response
            
        return None
        
    async def after(
        self,
        request: "Request",
        response: "Response",
    ) -> "Response":
        """Add rate limit headers to response."""
        if self.config.include_headers:
            result = request.state.get("rate_limit")
            if result:
                self._add_headers(response, result)
                
        return response
        
    def _add_headers(self, response: "Response", result: RateLimitResult) -> None:
        """Add rate limit headers to response."""
        response.headers[self.config.header_limit] = str(result.limit)
        response.headers[self.config.header_remaining] = str(result.remaining)
        response.headers[self.config.header_reset] = str(int(result.reset_at))


def rate_limit(
    requests: int = 10,
    window: int = 60,
    burst: int = 2,
    key_func: Optional[Callable] = None,
) -> Callable:
    """
    Rate limit decorator for individual routes.
    
    Example:
        @app.post("/api/submit")
        @rate_limit(requests=5, window=60)
        async def submit(request):
            ...
    """
    _limiter = RateLimiter(
        requests=requests,
        window=window,
        burst=burst,
        key_func=key_func,
    )
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(request: "Request", *args, **kwargs):
            from nexaweb.core.response import JSONResponse
            
            result = await _limiter.check(request)
            
            if not result.allowed:
                return JSONResponse(
                    {"error": "Rate limit exceeded"},
                    status_code=429,
                )
                
            response = await func(request, *args, **kwargs)
            return response
            
        return wrapper
    return decorator


# Specialized rate limiters

class LoginRateLimiter(RateLimiter):
    """
    Rate limiter for login endpoints.
    
    More aggressive limiting on failed attempts.
    """
    
    def __init__(
        self,
        requests: int = 5,
        window: int = 300,  # 5 minutes
        lockout_threshold: int = 10,
        lockout_duration: int = 900,  # 15 minutes
    ) -> None:
        super().__init__(requests=requests, window=window)
        self.lockout_threshold = lockout_threshold
        self.lockout_duration = lockout_duration
        self._failed_attempts: Dict[str, list] = {}
        
    async def record_failure(self, request: "Request") -> None:
        """Record failed login attempt."""
        key = self.key_func(request)
        now = time.time()
        
        if key not in self._failed_attempts:
            self._failed_attempts[key] = []
            
        self._failed_attempts[key].append(now)
        
        # Clean old attempts
        window_start = now - self.lockout_duration
        self._failed_attempts[key] = [
            t for t in self._failed_attempts[key] if t > window_start
        ]
        
    async def is_locked_out(self, request: "Request") -> bool:
        """Check if client is locked out."""
        key = self.key_func(request)
        
        if key not in self._failed_attempts:
            return False
            
        now = time.time()
        window_start = now - self.lockout_duration
        recent_failures = [
            t for t in self._failed_attempts[key] if t > window_start
        ]
        
        return len(recent_failures) >= self.lockout_threshold
        
    async def clear_failures(self, request: "Request") -> None:
        """Clear failed attempts on successful login."""
        key = self.key_func(request)
        if key in self._failed_attempts:
            del self._failed_attempts[key]


class APIRateLimiter(RateLimiter):
    """
    Rate limiter for API endpoints with tier support.
    
    Supports different rate limits based on API key tier.
    """
    
    def __init__(
        self,
        tiers: Optional[Dict[str, int]] = None,
        default_limit: int = 100,
        window: int = 60,
    ) -> None:
        super().__init__(requests=default_limit, window=window)
        
        self.tiers = tiers or {
            "free": 100,
            "basic": 1000,
            "pro": 10000,
            "enterprise": 100000,
        }
        
    def _get_tier(self, request: "Request") -> str:
        """Get API tier from request."""
        # Override to implement tier detection
        return request.headers.get("x-api-tier", "free").lower()
        
    async def check(self, request: "Request") -> RateLimitResult:
        """Check rate limit with tier support."""
        tier = self._get_tier(request)
        limit = self.tiers.get(tier, self.requests)
        
        key = f"{self.key_func(request)}:{tier}"
        
        return await self.backend.check(
            key=key,
            limit=limit,
            window=self.window,
            burst=self.burst,
        )
