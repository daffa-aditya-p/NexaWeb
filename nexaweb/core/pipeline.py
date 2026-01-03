"""
NexaWeb Request Pipeline
========================

Orchestrates the flow of requests through the middleware stack
and route handlers. Implements the middleware "onion" pattern
with optimized async execution.

The pipeline:
1. Receives an incoming request
2. Passes through middleware stack (before hooks)
3. Dispatches to route handler
4. Passes response through middleware stack (after hooks)
5. Returns final response

Performance optimizations:
- Pre-compiled middleware chain
- Minimal object allocation
- Efficient async task management
"""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    List,
)

if TYPE_CHECKING:
    from nexaweb.core.middleware import Middleware
    from nexaweb.core.request import Request
    from nexaweb.core.response import Response


class Pipeline:
    """
    Request processing pipeline.
    
    Creates a chain of middleware that wraps the final handler,
    allowing each middleware to process the request and response.
    
    Example:
        pipeline = Pipeline([
            LoggingMiddleware(),
            AuthMiddleware(),
            CORSMiddleware(),
        ])
        
        response = await pipeline.run(request, handler)
    """
    
    __slots__ = ("_middleware", "_chain")
    
    def __init__(self, middleware: List["Middleware"]) -> None:
        """
        Initialize pipeline with middleware stack.
        
        Args:
            middleware: List of middleware instances in execution order
        """
        self._middleware = middleware
        self._chain: Callable[
            ["Request"],
            Coroutine[Any, Any, "Response"],
        ] | None = None
        
    def _build_chain(
        self,
        handler: Callable[["Request"], Coroutine[Any, Any, "Response"]],
    ) -> Callable[["Request"], Coroutine[Any, Any, "Response"]]:
        """
        Build the middleware chain around the handler.
        
        Creates a nested function call structure:
            middleware1(middleware2(middleware3(handler)))
        
        Each middleware wraps the next in the chain.
        """
        # Start with the final handler
        chain = handler
        
        # Wrap in middleware from inside out (reverse order)
        for middleware in reversed(self._middleware):
            chain = self._wrap_middleware(middleware, chain)
            
        return chain
        
    def _wrap_middleware(
        self,
        middleware: "Middleware",
        next_handler: Callable[["Request"], Coroutine[Any, Any, "Response"]],
    ) -> Callable[["Request"], Coroutine[Any, Any, "Response"]]:
        """
        Create a wrapper that calls middleware with the next handler.
        """
        async def wrapped(request: "Request") -> "Response":
            return await middleware(request, next_handler)
        return wrapped
        
    async def run(
        self,
        request: "Request",
        handler: Callable[["Request"], Coroutine[Any, Any, "Response"]],
    ) -> "Response":
        """
        Run the request through the pipeline.
        
        Args:
            request: Incoming request
            handler: Final route handler
            
        Returns:
            Response from handler/middleware
        """
        chain = self._build_chain(handler)
        return await chain(request)


class PipelineBuilder:
    """
    Fluent builder for creating pipelines.
    
    Example:
        pipeline = (
            PipelineBuilder()
            .use(LoggingMiddleware())
            .use(AuthMiddleware())
            .use(handler=route_handler)
            .build()
        )
    """
    
    def __init__(self) -> None:
        self._middleware: List["Middleware"] = []
        self._handler: Callable | None = None
        
    def use(self, middleware: "Middleware") -> "PipelineBuilder":
        """Add middleware to the pipeline."""
        self._middleware.append(middleware)
        return self
        
    def handler(
        self,
        handler: Callable[["Request"], Coroutine[Any, Any, "Response"]],
    ) -> "PipelineBuilder":
        """Set the final handler."""
        self._handler = handler
        return self
        
    def build(self) -> Pipeline:
        """Build the pipeline."""
        return Pipeline(self._middleware)
        
    async def run(self, request: "Request") -> "Response":
        """Build and run the pipeline."""
        if self._handler is None:
            raise ValueError("No handler set")
            
        pipeline = self.build()
        return await pipeline.run(request, self._handler)


class ConditionalPipeline:
    """
    Pipeline that conditionally applies middleware based on request.
    
    Example:
        pipeline = ConditionalPipeline()
        pipeline.when(
            lambda r: r.path.startswith("/api"),
            [AuthMiddleware(), RateLimitMiddleware()]
        )
        pipeline.when(
            lambda r: r.path.startswith("/admin"),
            [AdminAuthMiddleware()]
        )
    """
    
    def __init__(self) -> None:
        self._conditions: List[tuple] = []
        self._default_middleware: List["Middleware"] = []
        
    def when(
        self,
        condition: Callable[["Request"], bool],
        middleware: List["Middleware"],
    ) -> "ConditionalPipeline":
        """
        Add conditional middleware.
        
        Args:
            condition: Function that takes request and returns bool
            middleware: Middleware to apply if condition is true
        """
        self._conditions.append((condition, middleware))
        return self
        
    def default(self, middleware: List["Middleware"]) -> "ConditionalPipeline":
        """Set default middleware applied to all requests."""
        self._default_middleware = middleware
        return self
        
    def get_middleware_for(self, request: "Request") -> List["Middleware"]:
        """Get applicable middleware for a request."""
        middleware = list(self._default_middleware)
        
        for condition, cond_middleware in self._conditions:
            if condition(request):
                middleware.extend(cond_middleware)
                
        return middleware
        
    async def run(
        self,
        request: "Request",
        handler: Callable[["Request"], Coroutine[Any, Any, "Response"]],
    ) -> "Response":
        """Run request through conditional pipeline."""
        middleware = self.get_middleware_for(request)
        pipeline = Pipeline(middleware)
        return await pipeline.run(request, handler)
