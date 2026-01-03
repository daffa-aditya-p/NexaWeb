"""
NexaWeb Plugin Loader
=====================

Plugin discovery, loading, and management.
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Type,
    Union,
)

from nexaweb.plugins.base import Plugin, PluginInfo, PluginMeta
from nexaweb.plugins.hooks import HookRegistry, EventEmitter, FrameworkHooks

if TYPE_CHECKING:
    from nexaweb.core import Application


class PluginError(Exception):
    """Plugin-related error."""
    pass


class PluginNotFoundError(PluginError):
    """Plugin not found."""
    pass


class PluginDependencyError(PluginError):
    """Plugin dependency error."""
    pass


@dataclass
class LoadedPlugin:
    """
    Loaded plugin instance.
    
    Attributes:
        plugin: Plugin instance
        info: Plugin metadata
        path: Source path
        enabled: Whether enabled
    """
    
    plugin: Plugin
    info: PluginInfo
    path: Optional[Path] = None
    enabled: bool = True
    
    @property
    def name(self) -> str:
        return self.info.name
    
    @property
    def version(self) -> str:
        return self.info.version


class PluginLoader:
    """
    Plugin discovery and loading.
    
    Example:
        loader = PluginLoader()
        
        # Load from directory
        plugins = loader.load_from_directory("plugins/")
        
        # Load specific plugin
        plugin = loader.load("my_plugin")
        
        # Load from entry points
        plugins = loader.load_entry_points("nexaweb.plugins")
    """
    
    def __init__(
        self,
        search_paths: Optional[List[Path]] = None,
    ):
        """
        Initialize loader.
        
        Args:
            search_paths: Additional plugin search paths
        """
        self.search_paths = search_paths or []
        self._loaded: Dict[str, LoadedPlugin] = {}
    
    def load(
        self,
        name: str,
        path: Optional[Path] = None,
    ) -> LoadedPlugin:
        """
        Load a plugin by name.
        
        Args:
            name: Plugin name or module path
            path: Optional explicit path
            
        Returns:
            Loaded plugin
            
        Raises:
            PluginNotFoundError: If plugin not found
        """
        # Check if already loaded
        if name in self._loaded:
            return self._loaded[name]
        
        # Try to load module
        module = self._load_module(name, path)
        
        if not module:
            raise PluginNotFoundError(f"Plugin not found: {name}")
        
        # Find plugin class
        plugin_class = self._find_plugin_class(module)
        
        if not plugin_class:
            raise PluginNotFoundError(f"No Plugin class found in: {name}")
        
        # Create instance
        plugin = plugin_class()
        loaded = LoadedPlugin(
            plugin=plugin,
            info=plugin.info,
            path=path,
        )
        
        self._loaded[plugin.info.name] = loaded
        
        return loaded
    
    def load_from_directory(
        self,
        directory: Union[str, Path],
        recursive: bool = False,
    ) -> List[LoadedPlugin]:
        """
        Load all plugins from directory.
        
        Args:
            directory: Plugin directory
            recursive: Search subdirectories
            
        Returns:
            List of loaded plugins
        """
        directory = Path(directory)
        
        if not directory.exists():
            return []
        
        plugins = []
        
        # Find Python files
        pattern = "**/*.py" if recursive else "*.py"
        
        for file in directory.glob(pattern):
            if file.name.startswith("_"):
                continue
            
            try:
                loaded = self.load(file.stem, file)
                plugins.append(loaded)
            except (PluginNotFoundError, PluginError):
                continue
        
        return plugins
    
    def load_entry_points(
        self,
        group: str = "nexaweb.plugins",
    ) -> List[LoadedPlugin]:
        """
        Load plugins from entry points.
        
        Args:
            group: Entry point group name
            
        Returns:
            List of loaded plugins
        """
        plugins = []
        
        try:
            if sys.version_info >= (3, 10):
                from importlib.metadata import entry_points
                eps = entry_points(group=group)
            else:
                from importlib.metadata import entry_points
                eps = entry_points().get(group, [])
            
            for ep in eps:
                try:
                    plugin_class = ep.load()
                    
                    if inspect.isclass(plugin_class) and issubclass(plugin_class, Plugin):
                        plugin = plugin_class()
                        loaded = LoadedPlugin(
                            plugin=plugin,
                            info=plugin.info,
                        )
                        self._loaded[plugin.info.name] = loaded
                        plugins.append(loaded)
                        
                except Exception:
                    continue
                    
        except ImportError:
            pass
        
        return plugins
    
    def _load_module(
        self,
        name: str,
        path: Optional[Path] = None,
    ) -> Optional[Any]:
        """Load Python module."""
        # Try explicit path first
        if path and path.exists():
            spec = importlib.util.spec_from_file_location(name, path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[name] = module
                spec.loader.exec_module(module)
                return module
        
        # Try import
        try:
            return importlib.import_module(name)
        except ImportError:
            pass
        
        # Search paths
        for search_path in self.search_paths:
            candidate = search_path / f"{name}.py"
            if candidate.exists():
                return self._load_module(name, candidate)
            
            # Check package
            candidate = search_path / name / "__init__.py"
            if candidate.exists():
                return self._load_module(name, candidate.parent)
        
        return None
    
    def _find_plugin_class(self, module: Any) -> Optional[Type[Plugin]]:
        """Find Plugin subclass in module."""
        for name in dir(module):
            obj = getattr(module, name)
            
            if (
                inspect.isclass(obj) and
                issubclass(obj, Plugin) and
                obj is not Plugin and
                not name.startswith("_")
            ):
                return obj
        
        return None
    
    def get_loaded(self, name: str) -> Optional[LoadedPlugin]:
        """Get loaded plugin by name."""
        return self._loaded.get(name)
    
    def list_loaded(self) -> List[LoadedPlugin]:
        """Get all loaded plugins."""
        return list(self._loaded.values())
    
    def unload(self, name: str) -> bool:
        """
        Unload a plugin.
        
        Args:
            name: Plugin name
            
        Returns:
            True if unloaded
        """
        if name in self._loaded:
            del self._loaded[name]
            return True
        return False


class PluginManager:
    """
    Plugin lifecycle manager.
    
    Manages plugin registration, booting, and shutdown.
    
    Example:
        manager = PluginManager(app)
        
        # Register plugins
        manager.register(MyPlugin())
        manager.register(AnotherPlugin())
        
        # Boot all plugins
        await manager.boot()
        
        # Shutdown
        await manager.shutdown()
    """
    
    def __init__(
        self,
        app: Optional["Application"] = None,
    ):
        """
        Initialize manager.
        
        Args:
            app: Application instance
        """
        self.app = app
        self.loader = PluginLoader()
        self.hooks = HookRegistry()
        self.events = EventEmitter()
        
        self._plugins: Dict[str, Plugin] = {}
        self._boot_order: List[str] = []
        self._booted = False
        
        # Register framework hooks
        self._register_framework_hooks()
    
    def _register_framework_hooks(self) -> None:
        """Register pre-defined framework hooks."""
        for attr in dir(FrameworkHooks):
            if not attr.startswith("_"):
                hook_name = getattr(FrameworkHooks, attr)
                self.hooks.register(hook_name)
    
    def register(
        self,
        plugin: Union[Plugin, Type[Plugin], str],
        **config: Any,
    ) -> Plugin:
        """
        Register a plugin.
        
        Args:
            plugin: Plugin instance, class, or name
            **config: Plugin configuration
            
        Returns:
            Registered plugin instance
        """
        # Load if string
        if isinstance(plugin, str):
            loaded = self.loader.load(plugin)
            plugin = loaded.plugin
        
        # Instantiate if class
        elif isinstance(plugin, type):
            plugin = plugin()
        
        # Check dependencies
        self._check_dependencies(plugin)
        
        # Register
        self._plugins[plugin.info.name] = plugin
        
        return plugin
    
    def _check_dependencies(self, plugin: Plugin) -> None:
        """Check plugin dependencies."""
        for dep in plugin.info.dependencies:
            if dep not in self._plugins and dep not in PluginMeta.get_registry():
                raise PluginDependencyError(
                    f"Plugin '{plugin.info.name}' requires '{dep}' which is not available"
                )
    
    def _resolve_boot_order(self) -> List[str]:
        """Resolve plugin boot order based on dependencies."""
        order: List[str] = []
        visited: Set[str] = set()
        
        def visit(name: str, ancestors: Set[str]) -> None:
            if name in visited:
                return
            
            if name in ancestors:
                raise PluginDependencyError(f"Circular dependency detected: {name}")
            
            plugin = self._plugins.get(name)
            if not plugin:
                return
            
            ancestors.add(name)
            
            for dep in plugin.info.dependencies:
                if dep in self._plugins:
                    visit(dep, ancestors.copy())
            
            visited.add(name)
            order.append(name)
        
        for name in self._plugins:
            visit(name, set())
        
        return order
    
    async def boot(self) -> None:
        """Boot all registered plugins."""
        if self._booted:
            return
        
        # Resolve boot order
        self._boot_order = self._resolve_boot_order()
        
        # Emit starting event
        await self.hooks.trigger(FrameworkHooks.APP_STARTING)
        
        # Register plugins
        for name in self._boot_order:
            plugin = self._plugins[name]
            if self.app:
                await plugin.register(self.app)
        
        # Boot plugins
        for name in self._boot_order:
            plugin = self._plugins[name]
            if self.app:
                await plugin.boot(self.app)
            plugin._booted = True
        
        self._booted = True
        
        # Emit started event
        await self.hooks.trigger(FrameworkHooks.APP_STARTED)
    
    async def shutdown(self) -> None:
        """Shutdown all plugins in reverse order."""
        if not self._booted:
            return
        
        # Emit stopping event
        await self.hooks.trigger(FrameworkHooks.APP_STOPPING)
        
        # Shutdown in reverse order
        for name in reversed(self._boot_order):
            plugin = self._plugins[name]
            try:
                await plugin.shutdown()
            except Exception:
                pass  # Log error but continue
        
        self._booted = False
        
        # Emit stopped event
        await self.hooks.trigger(FrameworkHooks.APP_STOPPED)
    
    def get(self, name: str) -> Optional[Plugin]:
        """
        Get plugin by name.
        
        Args:
            name: Plugin name
            
        Returns:
            Plugin if found
        """
        return self._plugins.get(name)
    
    def has(self, name: str) -> bool:
        """Check if plugin is registered."""
        return name in self._plugins
    
    def enable(self, name: str) -> bool:
        """Enable a plugin."""
        plugin = self._plugins.get(name)
        if plugin:
            plugin.enable()
            return True
        return False
    
    def disable(self, name: str) -> bool:
        """Disable a plugin."""
        plugin = self._plugins.get(name)
        if plugin:
            plugin.disable()
            return True
        return False
    
    def list_plugins(self) -> List[PluginInfo]:
        """Get list of registered plugins."""
        return [p.info for p in self._plugins.values()]
    
    def __contains__(self, name: str) -> bool:
        return name in self._plugins
    
    def __iter__(self):
        return iter(self._plugins.values())
    
    def __len__(self) -> int:
        return len(self._plugins)


# Convenience decorator for creating plugins
def plugin(
    name: Optional[str] = None,
    version: str = "0.1.0",
    description: str = "",
    dependencies: Optional[List[str]] = None,
) -> Callable[[Type], Type[Plugin]]:
    """
    Decorator to create a plugin from a class.
    
    Example:
        @plugin(name="my-plugin", version="1.0.0")
        class MyPlugin:
            async def boot(self, app):
                print("Booting!")
    """
    def decorator(cls: Type) -> Type[Plugin]:
        # Create Meta class
        class Meta:
            pass
        
        Meta.name = name or cls.__name__.lower().replace("plugin", "")
        Meta.version = version
        Meta.description = description or cls.__doc__ or ""
        Meta.dependencies = dependencies or []
        
        # Create new class inheriting from Plugin
        new_cls = type(
            cls.__name__,
            (Plugin,),
            {
                **{k: v for k, v in cls.__dict__.items() if not k.startswith("__")},
                "Meta": Meta,
            },
        )
        
        return new_cls
    
    return decorator
