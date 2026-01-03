"""
NexaWeb Application Core
========================

The central orchestrator of the NexaWeb framework. NexaApp manages:
- Application lifecycle (boot, run, shutdown)
- Service container and dependency injection
- Plugin registration and initialization
- Configuration loading
- Middleware pipeline construction
- Route registration
- Event dispatching

Architecture:
    NexaApp follows a service-oriented architecture where all components
    are registered as services and resolved through dependency injection.
    This allows for maximum flexibility and testability.

Example:
    from nexaweb import NexaApp
    
    app = NexaApp()
    
    @app.get("/")
    async def home(request):
        return {"message": "Welcome to NexaWeb"}
    
    if __name__ == "__main__":
        app.run()
"""

from __future__ import annotations

import asyncio
import signal
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
)

from nexaweb.core.config import Config
from nexaweb.core.middleware import MiddlewareStack
from nexaweb.core.pipeline import Pipeline
from nexaweb.core.router import Router
from nexaweb.utils.env import EnvLoader
from nexaweb.utils.logger import Logger, LogLevel

if TYPE_CHECKING:
    from nexaweb.core.request import Request
    from nexaweb.core.response import Response
    from nexaweb.plugins.manager import PluginManager

T = TypeVar("T")


@dataclass
class AppState:
    """Application runtime state container."""
    
    is_running: bool = False
    is_debug: bool = False
    startup_time: float = 0.0
    request_count: int = 0
    active_connections: int = 0
    services: Dict[str, Any] = field(default_factory=dict)
    

class ServiceContainer:
    """
    Lightweight Dependency Injection Container.
    
    Manages service registration, resolution, and lifecycle.
    Supports singleton, transient, and scoped lifetimes.
    """
    
    def __init__(self) -> None:
        self._singletons: Dict[str, Any] = {}
        self._factories: Dict[str, Callable[..., Any]] = {}
        self._aliases: Dict[str, str] = {}
        
    def singleton(self, name: str, factory: Callable[..., T]) -> None:
        """Register a singleton service."""
        self._factories[name] = factory
        
    def register(self, name: str, factory: Callable[..., T]) -> None:
        """Register a transient service (new instance each resolution)."""
        self._factories[name] = factory
        
    def alias(self, alias: str, target: str) -> None:
        """Create an alias for a service."""
        self._aliases[alias] = target
        
    def resolve(self, name: str) -> Any:
        """Resolve a service by name."""
        resolved_name = self._aliases.get(name, name)
        
        if resolved_name in self._singletons:
            return self._singletons[resolved_name]
            
        if resolved_name not in self._factories:
            raise KeyError(f"Service '{name}' not registered")
            
        instance = self._factories[resolved_name]()
        
        # Cache singleton
        if name in self._factories and resolved_name in self._factories:
            self._singletons[resolved_name] = instance
            
        return instance
    
    def has(self, name: str) -> bool:
        """Check if a service is registered."""
        resolved_name = self._aliases.get(name, name)
        return resolved_name in self._factories or resolved_name in self._singletons


class NexaApp:
    """
    NexaWeb Application Container.
    
    The main entry point for building NexaWeb applications. Provides:
    - ASGI-compatible interface for production servers
    - Built-in development server with hot reload
    - Plugin system integration
    - Service container for dependency injection
    - Middleware pipeline management
    - Route registration shortcuts
    
    Attributes:
        config: Application configuration
        router: URL router
        middleware: Middleware stack
        container: Service container
        state: Runtime state
        
    Example:
        app = NexaApp(debug=True)
        
        @app.get("/users/{id}")
        async def get_user(request, id: int):
            user = await User.find(id)
            return user.to_dict()
            
        @app.post("/users")
        async def create_user(request):
            data = await request.json()
            user = await User.create(**data)
            return user.to_dict(), 201
    """
    
    def __init__(
        self,
        name: str = "nexaweb",
        debug: bool = False,
        config_path: Optional[Path] = None,
        base_path: Optional[Path] = None,
    ) -> None:
        self.name = name
        self.base_path = base_path or Path.cwd()
        self.config_path = config_path or self.base_path / "config"
        
        # Core components
        self.config = Config()
        self.router = Router()
        self.middleware = MiddlewareStack()
        self.container = ServiceContainer()
        self.state = AppState(is_debug=debug)
        self.logger = Logger(name, level=LogLevel.DEBUG if debug else LogLevel.INFO)
        
        # Lifecycle hooks
        self._on_startup: List[Callable[[], Coroutine[Any, Any, None]]] = []
        self._on_shutdown: List[Callable[[], Coroutine[Any, Any, None]]] = []
        
        # Plugin manager (lazy loaded)
        self._plugin_manager: Optional[PluginManager] = None
        
        # Initialize core services
        self._register_core_services()
        
    def _register_core_services(self) -> None:
        """Register framework core services."""
        self.container.singleton("config", lambda: self.config)
        self.container.singleton("router", lambda: self.router)
        self.container.singleton("logger", lambda: self.logger)
        self.container.singleton("app", lambda: self)
        
    async def _load_environment(self) -> None:
        """Load environment variables from .env file."""
        env_path = self.base_path / ".env"
        if env_path.exists():
            EnvLoader.load(env_path)
            self.logger.debug(f"Loaded environment from {env_path}")
            
    async def _load_configuration(self) -> None:
        """Load application configuration."""
        await self.config.load_from_path(self.config_path)
        self.state.is_debug = self.config.get("app.debug", self.state.is_debug)
        self.logger.debug("Configuration loaded")
        
    async def _boot_plugins(self) -> None:
        """Initialize and boot registered plugins."""
        from nexaweb.plugins.manager import PluginManager
        
        self._plugin_manager = PluginManager(self)
        await self._plugin_manager.boot_all()
        self.logger.debug("Plugins booted")
        
    async def _execute_startup_hooks(self) -> None:
        """Execute all registered startup hooks."""
        for hook in self._on_startup:
            await hook()
            
    async def _execute_shutdown_hooks(self) -> None:
        """Execute all registered shutdown hooks."""
        for hook in self._on_shutdown:
            await hook()
            
    @asynccontextmanager
    async def lifespan(self):
        """
        Application lifespan context manager.
        
        Handles startup and shutdown sequences for ASGI servers.
        """
        import time
        
        start_time = time.perf_counter()
        
        try:
            # Boot sequence
            await self._load_environment()
            await self._load_configuration()
            await self._boot_plugins()
            await self._execute_startup_hooks()
            
            self.state.is_running = True
            self.state.startup_time = time.perf_counter() - start_time
            
            self.logger.info(
                f"🚀 NexaWeb started in {self.state.startup_time:.3f}s",
                extra={"startup_time": self.state.startup_time}
            )
            
            yield
            
        finally:
            # Shutdown sequence
            self.state.is_running = False
            await self._execute_shutdown_hooks()
            self.logger.info("👋 NexaWeb shutdown complete")
            
    async def __call__(
        self,
        scope: Dict[str, Any],
        receive: Callable[[], Coroutine[Any, Any, Dict[str, Any]]],
        send: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        """
        ASGI application interface.
        
        This method is called by ASGI servers (uvicorn, hypercorn, etc.)
        for each incoming request.
        """
        if scope["type"] == "lifespan":
            await self._handle_lifespan(scope, receive, send)
        elif scope["type"] == "http":
            await self._handle_http(scope, receive, send)
        elif scope["type"] == "websocket":
            await self._handle_websocket(scope, receive, send)
        else:
            raise ValueError(f"Unknown scope type: {scope['type']}")
            
    async def _handle_lifespan(
        self,
        scope: Dict[str, Any],
        receive: Callable,
        send: Callable,
    ) -> None:
        """Handle ASGI lifespan events."""
        async with self.lifespan():
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
                    
    async def _handle_http(
        self,
        scope: Dict[str, Any],
        receive: Callable,
        send: Callable,
    ) -> None:
        """Handle HTTP requests through the middleware pipeline."""
        from nexaweb.core.request import Request
        from nexaweb.core.response import Response
        
        self.state.request_count += 1
        self.state.active_connections += 1
        
        try:
            # Build request object
            request = await Request.from_scope(scope, receive)
            
            # Run through middleware pipeline
            pipeline = Pipeline(self.middleware.stack)
            response = await pipeline.run(request, self._dispatch_route)
            
            # Send response
            await response.send(send)
            
        except Exception as e:
            self.logger.exception("Request handling error", exc_info=e)
            error_response = Response.error(500, str(e) if self.state.is_debug else "Internal Server Error")
            await error_response.send(send)
            
        finally:
            self.state.active_connections -= 1
            
    async def _handle_websocket(
        self,
        scope: Dict[str, Any],
        receive: Callable,
        send: Callable,
    ) -> None:
        """Handle WebSocket connections."""
        # WebSocket handling implementation
        from nexaweb.core.websocket import WebSocketConnection
        
        ws = WebSocketConnection(scope, receive, send)
        route = self.router.match_websocket(scope["path"])
        
        if route:
            await route.handler(ws)
        else:
            await ws.close(code=4004, reason="Not Found")
            
    async def _dispatch_route(self, request: "Request") -> "Response":
        """Dispatch request to the matched route handler."""
        from nexaweb.core.response import Response, JSONResponse
        
        match = self.router.match(request.method, request.path)
        
        if not match:
            return Response.error(404, "Not Found")
            
        route, params = match
        request.params = params
        
        # Execute route handler
        try:
            result = await route.handler(request, **params)
            
            # Convert result to Response
            if isinstance(result, Response):
                return result
            elif isinstance(result, dict):
                return JSONResponse(result)
            elif isinstance(result, tuple):
                body, status = result
                if isinstance(body, dict):
                    return JSONResponse(body, status_code=status)
                return Response(body, status_code=status)
            else:
                return Response(str(result))
                
        except Exception as e:
            self.logger.exception(f"Route handler error: {route.path}", exc_info=e)
            raise
            
    # Route registration shortcuts
    def route(
        self,
        path: str,
        methods: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Callable:
        """Register a route with multiple methods."""
        return self.router.route(path, methods, **kwargs)
        
    def get(self, path: str, **kwargs: Any) -> Callable:
        """Register a GET route."""
        return self.router.get(path, **kwargs)
        
    def post(self, path: str, **kwargs: Any) -> Callable:
        """Register a POST route."""
        return self.router.post(path, **kwargs)
        
    def put(self, path: str, **kwargs: Any) -> Callable:
        """Register a PUT route."""
        return self.router.put(path, **kwargs)
        
    def patch(self, path: str, **kwargs: Any) -> Callable:
        """Register a PATCH route."""
        return self.router.patch(path, **kwargs)
        
    def delete(self, path: str, **kwargs: Any) -> Callable:
        """Register a DELETE route."""
        return self.router.delete(path, **kwargs)
        
    def websocket(self, path: str, **kwargs: Any) -> Callable:
        """Register a WebSocket route."""
        return self.router.websocket(path, **kwargs)
        
    def use(self, middleware: Union[Type["Middleware"], "Middleware"]) -> "NexaApp":
        """Add middleware to the stack."""
        self.middleware.add(middleware)
        return self
        
    def on_startup(self, func: Callable[[], Coroutine[Any, Any, None]]) -> Callable:
        """Register a startup hook."""
        self._on_startup.append(func)
        return func
        
    def on_shutdown(self, func: Callable[[], Coroutine[Any, Any, None]]) -> Callable:
        """Register a shutdown hook."""
        self._on_shutdown.append(func)
        return func
        
    def include_router(self, router: Router, prefix: str = "") -> None:
        """Include routes from another router with optional prefix."""
        self.router.include(router, prefix)
        
    def run(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        reload: bool = False,
        workers: int = 1,
        log_level: str = "info",
    ) -> None:
        """
        Run the application using the built-in server.
        
        For production, use an ASGI server directly:
            uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
        """
        import uvicorn
        
        uvicorn.run(
            self,
            host=host,
            port=port,
            reload=reload,
            workers=workers,
            log_level=log_level,
            lifespan="on",
        )
        
    def serve(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        reload: bool = True,
    ) -> None:
        """Alias for run() with development defaults."""
        self.run(host=host, port=port, reload=reload)


def create_app(
    name: str = "nexaweb",
    debug: bool = False,
    **kwargs: Any,
) -> NexaApp:
    """
    Factory function for creating NexaApp instances.
    
    Useful for application factories and testing.
    """
    return NexaApp(name=name, debug=debug, **kwargs)
