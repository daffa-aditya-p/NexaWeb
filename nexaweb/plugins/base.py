"""
NexaWeb Plugin Base Classes
===========================

Base classes and types for plugins.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type

if TYPE_CHECKING:
    from nexaweb.core import Application


@dataclass
class PluginInfo:
    """
    Plugin metadata information.
    
    Attributes:
        name: Plugin name
        version: Plugin version
        description: Plugin description
        author: Plugin author
        dependencies: Required plugin dependencies
        tags: Plugin tags for categorization
    """
    
    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    dependencies: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    homepage: str = ""
    license: str = ""
    
    def __str__(self) -> str:
        return f"{self.name} v{self.version}"


class PluginMeta(abc.ABCMeta):
    """
    Metaclass for plugins.
    
    Automatically registers plugins and validates plugin info.
    """
    
    _registry: Dict[str, Type["Plugin"]] = {}
    
    def __new__(
        mcs,
        name: str,
        bases: tuple,
        namespace: Dict[str, Any],
    ) -> "PluginMeta":
        cls = super().__new__(mcs, name, bases, namespace)
        
        # Don't register base Plugin class
        if name != "Plugin" and any(
            base.__name__ == "Plugin" for base in bases
        ):
            # Get or create plugin info
            if "info" not in namespace and "Meta" in namespace:
                meta = namespace["Meta"]
                info = PluginInfo(
                    name=getattr(meta, "name", name),
                    version=getattr(meta, "version", "0.1.0"),
                    description=getattr(meta, "description", ""),
                    author=getattr(meta, "author", ""),
                    dependencies=getattr(meta, "dependencies", []),
                    tags=getattr(meta, "tags", []),
                )
                cls.info = info
            elif "info" not in namespace:
                cls.info = PluginInfo(name=name)
            
            # Register plugin
            mcs._registry[cls.info.name] = cls
        
        return cls
    
    @classmethod
    def get_registry(mcs) -> Dict[str, Type["Plugin"]]:
        """Get all registered plugins."""
        return mcs._registry.copy()


class Plugin(metaclass=PluginMeta):
    """
    Base class for all plugins.
    
    Plugins extend NexaWeb's functionality through hooks and
    extension points.
    
    Example:
        class MyPlugin(Plugin):
            class Meta:
                name = "my-plugin"
                version = "1.0.0"
                description = "My awesome plugin"
            
            async def boot(self, app: Application) -> None:
                # Called when plugin boots
                app.on_startup(self.setup)
            
            async def setup(self) -> None:
                print("Plugin setup!")
    """
    
    info: PluginInfo
    
    def __init__(self, app: Optional["Application"] = None):
        """
        Initialize plugin.
        
        Args:
            app: Application instance
        """
        self.app = app
        self._booted = False
        self._enabled = True
    
    @property
    def name(self) -> str:
        """Get plugin name."""
        return self.info.name
    
    @property
    def version(self) -> str:
        """Get plugin version."""
        return self.info.version
    
    @property
    def is_booted(self) -> bool:
        """Check if plugin is booted."""
        return self._booted
    
    @property
    def is_enabled(self) -> bool:
        """Check if plugin is enabled."""
        return self._enabled
    
    def enable(self) -> None:
        """Enable plugin."""
        self._enabled = True
    
    def disable(self) -> None:
        """Disable plugin."""
        self._enabled = False
    
    async def register(self, app: "Application") -> None:
        """
        Register plugin with application.
        
        Called when plugin is first added. Use this to register
        services, middleware, and other components.
        
        Args:
            app: Application instance
        """
        self.app = app
    
    async def boot(self, app: "Application") -> None:
        """
        Boot the plugin.
        
        Called after all plugins are registered. Use this to
        set up routes, hooks, and other functionality that
        depends on other plugins.
        
        Args:
            app: Application instance
        """
        pass
    
    async def shutdown(self) -> None:
        """
        Shutdown the plugin.
        
        Called when application is shutting down. Use this to
        clean up resources.
        """
        pass
    
    def __repr__(self) -> str:
        status = "enabled" if self._enabled else "disabled"
        booted = "booted" if self._booted else "not booted"
        return f"<{self.__class__.__name__} {self.info} ({status}, {booted})>"


class ServiceProvider(Plugin):
    """
    Service provider plugin.
    
    Service providers register services with the application's
    service container.
    
    Example:
        class DatabaseProvider(ServiceProvider):
            class Meta:
                name = "database-provider"
            
            def provides(self) -> List[str]:
                return ["db", "database"]
            
            async def register(self, app: Application) -> None:
                app.container.singleton("db", Database)
    """
    
    def provides(self) -> List[str]:
        """
        Get list of services this provider registers.
        
        Returns:
            List of service names
        """
        return []
    
    def when_needed(self) -> List[str]:
        """
        Get list of services that trigger deferred loading.
        
        Returns:
            List of service names
        """
        return []
    
    @property
    def is_deferred(self) -> bool:
        """Check if provider should be deferred."""
        return len(self.when_needed()) > 0


class MiddlewarePlugin(Plugin):
    """
    Middleware plugin base class.
    
    Automatically registers middleware with the application.
    
    Example:
        class LoggingPlugin(MiddlewarePlugin):
            class Meta:
                name = "logging"
            
            async def handle(self, request, call_next):
                print(f"Request: {request.path}")
                response = await call_next(request)
                print(f"Response: {response.status}")
                return response
    """
    
    # Middleware priority (lower = earlier)
    priority: int = 100
    
    async def boot(self, app: "Application") -> None:
        """Register middleware with application."""
        if hasattr(app, "middleware") and hasattr(self, "handle"):
            app.middleware(self.handle)
    
    async def handle(self, request: Any, call_next: Any) -> Any:
        """
        Handle request.
        
        Args:
            request: Request object
            call_next: Next middleware
            
        Returns:
            Response object
        """
        return await call_next(request)


class RoutePlugin(Plugin):
    """
    Route plugin base class.
    
    Automatically registers routes with the application.
    """
    
    # Route prefix
    prefix: str = ""
    
    async def boot(self, app: "Application") -> None:
        """Register routes with application."""
        await self.register_routes(app)
    
    async def register_routes(self, app: "Application") -> None:
        """
        Register plugin routes.
        
        Override this to add custom routes.
        
        Args:
            app: Application instance
        """
        pass


class CommandPlugin(Plugin):
    """
    CLI command plugin base class.
    
    Registers custom CLI commands.
    """
    
    async def boot(self, app: "Application") -> None:
        """Register commands."""
        commands = self.get_commands()
        # Commands would be registered with CLI system
        for name, handler in commands.items():
            # Register command
            pass
    
    def get_commands(self) -> Dict[str, Any]:
        """
        Get plugin commands.
        
        Returns:
            Dict mapping command names to handlers
        """
        return {}
