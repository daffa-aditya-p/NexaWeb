"""
NexaWeb Middleware System
=========================

Provides a flexible middleware architecture for request/response processing.
Middleware can:
- Intercept and modify requests before route handling
- Intercept and modify responses after route handling
- Short-circuit request processing
- Add functionality like auth, logging, CORS, etc.

Middleware follows the "onion" model where each middleware wraps the next,
allowing both pre-processing (before) and post-processing (after) of requests.

Architecture:
    Request → Middleware1.before → Middleware2.before → Handler
                                                            ↓
    Response ← Middleware1.after ← Middleware2.after ← Response

Example:
    class LoggingMiddleware(Middleware):
        async def before(self, request: Request) -> Optional[Response]:
            request.state["start_time"] = time.time()
            return None  # Continue processing
            
        async def after(self, request: Request, response: Response) -> Response:
            duration = time.time() - request.state["start_time"]
            logger.info(f"{request.method} {request.path} - {duration:.3f}s")
            return response
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    List,
    Optional,
    Type,
    Union,
)

if TYPE_CHECKING:
    from nexaweb.core.request import Request
    from nexaweb.core.response import Response


class Middleware(ABC):
    """
    Base middleware class.
    
    All middleware must inherit from this class and implement
    at least one of `before()` or `after()` methods.
    
    Lifecycle:
        1. `before()` is called before the route handler
        2. If `before()` returns a Response, processing stops
        3. Route handler is called
        4. `after()` is called with request and response
        5. Final response is returned
        
    Example:
        class AuthMiddleware(Middleware):
            async def before(self, request: Request) -> Optional[Response]:
                if not request.headers.get("Authorization"):
                    return JSONResponse({"error": "Unauthorized"}, 401)
                return None
    """
    
    async def before(self, request: "Request") -> Optional["Response"]:
        """
        Called before request handling.
        
        Args:
            request: Incoming request
            
        Returns:
            None to continue processing, or Response to short-circuit
        """
        return None
        
    async def after(
        self,
        request: "Request",
        response: "Response",
    ) -> "Response":
        """
        Called after request handling.
        
        Args:
            request: Original request
            response: Response from handler
            
        Returns:
            Modified or original response
        """
        return response
        
    async def __call__(
        self,
        request: "Request",
        call_next: Callable[["Request"], Coroutine[Any, Any, "Response"]],
    ) -> "Response":
        """
        Middleware invocation.
        
        This is the standard ASGI-style middleware interface.
        Override this for full control over the middleware flow.
        """
        # Pre-processing
        early_response = await self.before(request)
        if early_response is not None:
            return early_response
            
        # Call next middleware/handler
        response = await call_next(request)
        
        # Post-processing
        return await self.after(request, response)


class FunctionMiddleware(Middleware):
    """
    Middleware wrapper for simple functions.
    
    Allows using functions as middleware without creating a class.
    
    Example:
        @app.use
        async def log_requests(request, call_next):
            start = time.time()
            response = await call_next(request)
            logger.info(f"Request took {time.time() - start:.3f}s")
            return response
    """
    
    def __init__(
        self,
        func: Callable[
            ["Request", Callable[["Request"], Coroutine[Any, Any, "Response"]]],
            Coroutine[Any, Any, "Response"],
        ],
    ) -> None:
        self._func = func
        
    async def __call__(
        self,
        request: "Request",
        call_next: Callable[["Request"], Coroutine[Any, Any, "Response"]],
    ) -> "Response":
        return await self._func(request, call_next)


@dataclass
class MiddlewareEntry:
    """Middleware stack entry with metadata."""
    middleware: Union[Middleware, Type[Middleware]]
    priority: int = 0
    name: Optional[str] = None
    
    def __post_init__(self) -> None:
        if self.name is None:
            if isinstance(self.middleware, type):
                self.name = self.middleware.__name__
            else:
                self.name = type(self.middleware).__name__


class MiddlewareStack:
    """
    Manages the middleware stack for an application.
    
    Features:
    - Priority-based ordering
    - Named middleware for easy removal
    - Support for both class and instance middleware
    - Middleware groups
    
    Example:
        stack = MiddlewareStack()
        stack.add(LoggingMiddleware, priority=100)
        stack.add(AuthMiddleware, priority=50)
        stack.add(CORSMiddleware())  # Instance
        
        # Remove middleware
        stack.remove("AuthMiddleware")
    """
    
    def __init__(self) -> None:
        self._entries: List[MiddlewareEntry] = []
        self._sorted = False
        
    def add(
        self,
        middleware: Union[Middleware, Type[Middleware], Callable],
        *,
        priority: int = 0,
        name: Optional[str] = None,
    ) -> "MiddlewareStack":
        """
        Add middleware to the stack.
        
        Args:
            middleware: Middleware class, instance, or function
            priority: Higher priority runs first (default: 0)
            name: Optional name for removal
            
        Returns:
            Self for chaining
        """
        # Wrap function as middleware
        if callable(middleware) and not isinstance(middleware, (Middleware, type)):
            middleware = FunctionMiddleware(middleware)
            
        entry = MiddlewareEntry(
            middleware=middleware,
            priority=priority,
            name=name,
        )
        
        self._entries.append(entry)
        self._sorted = False
        
        return self
        
    def remove(self, name: str) -> bool:
        """
        Remove middleware by name.
        
        Returns:
            True if middleware was removed, False otherwise
        """
        for i, entry in enumerate(self._entries):
            if entry.name == name:
                del self._entries[i]
                return True
        return False
        
    def clear(self) -> None:
        """Remove all middleware."""
        self._entries.clear()
        self._sorted = False
        
    def _sort(self) -> None:
        """Sort middleware by priority (higher first)."""
        if not self._sorted:
            self._entries.sort(key=lambda e: e.priority, reverse=True)
            self._sorted = True
            
    @property
    def stack(self) -> List[Middleware]:
        """Get sorted middleware instances."""
        self._sort()
        
        instances: List[Middleware] = []
        for entry in self._entries:
            if isinstance(entry.middleware, type):
                # Instantiate class
                instances.append(entry.middleware())
            else:
                instances.append(entry.middleware)
                
        return instances
        
    def __len__(self) -> int:
        return len(self._entries)
        
    def __iter__(self):
        return iter(self.stack)


# Built-in middleware implementations

class CORSMiddleware(Middleware):
    """
    Cross-Origin Resource Sharing (CORS) middleware.
    
    Handles preflight requests and adds CORS headers to responses.
    
    Example:
        app.use(CORSMiddleware(
            allow_origins=["https://example.com"],
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization"],
        ))
    """
    
    def __init__(
        self,
        allow_origins: List[str] = None,
        allow_methods: List[str] = None,
        allow_headers: List[str] = None,
        expose_headers: List[str] = None,
        allow_credentials: bool = False,
        max_age: int = 600,
    ) -> None:
        self.allow_origins = allow_origins or ["*"]
        self.allow_methods = allow_methods or ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
        self.allow_headers = allow_headers or ["*"]
        self.expose_headers = expose_headers or []
        self.allow_credentials = allow_credentials
        self.max_age = max_age
        
    async def __call__(
        self,
        request: "Request",
        call_next: Callable[["Request"], Coroutine[Any, Any, "Response"]],
    ) -> "Response":
        from nexaweb.core.response import Response
        
        origin = request.headers.get("origin", "")
        
        # Handle preflight request
        if request.method == "OPTIONS":
            response = Response(status_code=204)
            self._add_cors_headers(response, origin)
            return response
            
        # Process request
        response = await call_next(request)
        self._add_cors_headers(response, origin)
        
        return response
        
    def _add_cors_headers(self, response: "Response", origin: str) -> None:
        """Add CORS headers to response."""
        # Determine allowed origin
        if "*" in self.allow_origins:
            response.headers["Access-Control-Allow-Origin"] = "*"
        elif origin in self.allow_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            
        if self.allow_credentials:
            response.headers["Access-Control-Allow-Credentials"] = "true"
            
        if self.expose_headers:
            response.headers["Access-Control-Expose-Headers"] = ", ".join(self.expose_headers)
            
        # Preflight headers
        response.headers["Access-Control-Allow-Methods"] = ", ".join(self.allow_methods)
        response.headers["Access-Control-Allow-Headers"] = ", ".join(self.allow_headers)
        response.headers["Access-Control-Max-Age"] = str(self.max_age)


class TrustedHostMiddleware(Middleware):
    """
    Validate Host header to prevent host header attacks.
    
    Example:
        app.use(TrustedHostMiddleware(
            allowed_hosts=["example.com", "*.example.com"]
        ))
    """
    
    def __init__(self, allowed_hosts: List[str]) -> None:
        self.allowed_hosts = allowed_hosts
        self._allow_all = "*" in allowed_hosts
        
    async def before(self, request: "Request") -> Optional["Response"]:
        from nexaweb.core.response import Response
        
        if self._allow_all:
            return None
            
        host = request.headers.get("host", "").split(":")[0]
        
        for pattern in self.allowed_hosts:
            if pattern.startswith("*."):
                # Wildcard subdomain
                if host.endswith(pattern[1:]) or host == pattern[2:]:
                    return None
            elif host == pattern:
                return None
                
        return Response("Invalid host header", status_code=400)


class GZipMiddleware(Middleware):
    """
    Compress responses using gzip.
    
    Example:
        app.use(GZipMiddleware(minimum_size=500))
    """
    
    def __init__(self, minimum_size: int = 500, compression_level: int = 6) -> None:
        self.minimum_size = minimum_size
        self.compression_level = compression_level
        
    async def after(
        self,
        request: "Request",
        response: "Response",
    ) -> "Response":
        import gzip
        
        # Check if compression is appropriate
        if len(response.body) < self.minimum_size:
            return response
            
        accept_encoding = request.headers.get("accept-encoding", "")
        if "gzip" not in accept_encoding:
            return response
            
        # Don't compress if already compressed
        if "content-encoding" in {k.lower() for k in response.headers}:
            return response
            
        # Compress
        compressed = gzip.compress(response.body, compresslevel=self.compression_level)
        
        # Only use if smaller
        if len(compressed) >= len(response.body):
            return response
            
        response.body = compressed
        response.headers["Content-Encoding"] = "gzip"
        response.headers["Content-Length"] = str(len(compressed))
        response.headers["Vary"] = "Accept-Encoding"
        
        return response


class RequestIdMiddleware(Middleware):
    """
    Add unique request ID to each request for tracing.
    
    Example:
        app.use(RequestIdMiddleware())
        
        @app.get("/")
        async def index(request):
            # Access request ID
            request_id = request.state["request_id"]
    """
    
    def __init__(self, header_name: str = "X-Request-ID") -> None:
        self.header_name = header_name
        
    async def before(self, request: "Request") -> Optional["Response"]:
        import uuid
        
        # Use provided ID or generate new one
        request_id = request.headers.get(self.header_name.lower())
        if not request_id:
            request_id = str(uuid.uuid4())
            
        request.state["request_id"] = request_id
        return None
        
    async def after(
        self,
        request: "Request",
        response: "Response",
    ) -> "Response":
        # Add request ID to response
        response.headers[self.header_name] = request.state.get("request_id", "")
        return response
