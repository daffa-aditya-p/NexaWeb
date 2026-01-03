"""
NexaWeb Configuration Management
================================

Centralized configuration system with support for:
- Multiple configuration sources (files, env, runtime)
- Hierarchical configuration with dot notation
- Type-safe access with defaults
- Environment-specific overrides
- Configuration caching

Configuration Loading Priority (highest to lowest):
1. Runtime overrides
2. Environment variables (NEXAWEB_*)
3. .env file
4. config/{env}.py (environment-specific)
5. config/app.py (base configuration)
6. Default values

Example:
    # config/app.py
    config = {
        "app": {
            "name": "MyApp",
            "debug": False,
        },
        "database": {
            "host": "localhost",
            "port": 5432,
        }
    }
    
    # Access configuration
    app_name = config.get("app.name")
    db_host = config.get("database.host", "127.0.0.1")
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

T = TypeVar("T")


@dataclass
class ConfigSource:
    """Represents a configuration source with priority."""
    name: str
    data: Dict[str, Any]
    priority: int = 0


class Config:
    """
    Application configuration container.
    
    Provides hierarchical configuration access with type coercion
    and default values. Configuration values can be nested using
    dot notation.
    
    Example:
        config = Config()
        config.set("app.name", "MyApp")
        config.set("app.debug", True)
        
        name = config.get("app.name")  # "MyApp"
        debug = config.get("app.debug", False)  # True
        missing = config.get("app.missing", "default")  # "default"
    """
    
    def __init__(self) -> None:
        self._sources: List[ConfigSource] = []
        self._cache: Dict[str, Any] = {}
        self._merged: Dict[str, Any] = {}
        self._dirty = True
        
    async def load_from_path(self, config_path: Path) -> None:
        """
        Load configuration from a directory.
        
        Loads:
        - app.py (base configuration)
        - {NEXAWEB_ENV}.py (environment-specific)
        """
        if not config_path.exists():
            return
            
        # Load base config
        base_config = config_path / "app.py"
        if base_config.exists():
            data = self._load_python_config(base_config)
            self.add_source("app", data, priority=10)
            
        # Load environment-specific config
        env = os.getenv("NEXAWEB_ENV", "development")
        env_config = config_path / f"{env}.py"
        if env_config.exists():
            data = self._load_python_config(env_config)
            self.add_source(f"env:{env}", data, priority=20)
            
        # Load from environment variables
        self._load_env_overrides()
        
    def _load_python_config(self, path: Path) -> Dict[str, Any]:
        """Load configuration from Python file."""
        spec = importlib.util.spec_from_file_location("config", path)
        if spec is None or spec.loader is None:
            return {}
            
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Look for 'config' dict or all uppercase variables
        if hasattr(module, "config"):
            return module.config
            
        return {
            key: value
            for key, value in vars(module).items()
            if not key.startswith("_")
        }
        
    def _load_env_overrides(self) -> None:
        """Load overrides from NEXAWEB_* environment variables."""
        overrides: Dict[str, Any] = {}
        prefix = "NEXAWEB_"
        
        for key, value in os.environ.items():
            if key.startswith(prefix):
                # Convert NEXAWEB_APP_DEBUG to app.debug
                config_key = key[len(prefix):].lower().replace("_", ".")
                overrides[config_key] = self._parse_env_value(value)
                
        if overrides:
            self.add_source("env_vars", self._unflatten(overrides), priority=100)
            
    def _parse_env_value(self, value: str) -> Any:
        """Parse environment variable value to appropriate type."""
        # Boolean
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
            return False
            
        # Integer
        try:
            return int(value)
        except ValueError:
            pass
            
        # Float
        try:
            return float(value)
        except ValueError:
            pass
            
        # JSON (for complex values)
        if value.startswith(("{", "[")):
            import json
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass
                
        return value
        
    def _unflatten(self, flat: Dict[str, Any]) -> Dict[str, Any]:
        """Convert flat dot-notation keys to nested dict."""
        result: Dict[str, Any] = {}
        
        for key, value in flat.items():
            parts = key.split(".")
            current = result
            
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
                
            current[parts[-1]] = value
            
        return result
        
    def add_source(
        self,
        name: str,
        data: Dict[str, Any],
        priority: int = 0,
    ) -> None:
        """Add a configuration source."""
        source = ConfigSource(name=name, data=data, priority=priority)
        self._sources.append(source)
        self._dirty = True
        
    def _merge(self) -> None:
        """Merge all sources into single configuration."""
        if not self._dirty:
            return
            
        # Sort by priority (lower first, so higher overrides)
        sorted_sources = sorted(self._sources, key=lambda s: s.priority)
        
        self._merged = {}
        for source in sorted_sources:
            self._deep_merge(self._merged, source.data)
            
        self._dirty = False
        self._cache.clear()
        
    def _deep_merge(self, base: Dict, override: Dict) -> None:
        """Deep merge override into base."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
                
    def get(
        self,
        key: str,
        default: T = None,
    ) -> Union[Any, T]:
        """
        Get configuration value using dot notation.
        
        Args:
            key: Configuration key (e.g., "app.debug")
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        # Check cache
        if key in self._cache:
            return self._cache[key]
            
        self._merge()
        
        # Navigate to key
        parts = key.split(".")
        current = self._merged
        
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                return default
            current = current[part]
            
        # Cache and return
        self._cache[key] = current
        return current
        
    def get_int(self, key: str, default: int = 0) -> int:
        """Get configuration value as integer."""
        value = self.get(key, default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
            
    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get configuration value as float."""
        value = self.get(key, default)
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
            
    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get configuration value as boolean."""
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "yes", "1")
        return bool(value)
        
    def get_list(self, key: str, default: Optional[List] = None) -> List:
        """Get configuration value as list."""
        value = self.get(key, default)
        if value is None:
            return default or []
        if isinstance(value, list):
            return value
        return [value]
        
    def set(self, key: str, value: Any) -> None:
        """
        Set a runtime configuration value.
        
        Runtime values have the highest priority.
        """
        # Add to runtime source
        runtime_source = None
        for source in self._sources:
            if source.name == "runtime":
                runtime_source = source
                break
                
        if runtime_source is None:
            runtime_source = ConfigSource(name="runtime", data={}, priority=1000)
            self._sources.append(runtime_source)
            
        # Set value using dot notation
        parts = key.split(".")
        current = runtime_source.data
        
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
            
        current[parts[-1]] = value
        self._dirty = True
        
        # Update cache
        self._cache[key] = value
        
    def has(self, key: str) -> bool:
        """Check if configuration key exists."""
        return self.get(key) is not None
        
    def all(self) -> Dict[str, Any]:
        """Get all configuration as dict."""
        self._merge()
        return self._merged.copy()
        
    def section(self, prefix: str) -> Dict[str, Any]:
        """Get all values under a prefix."""
        self._merge()
        
        parts = prefix.split(".")
        current = self._merged
        
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                return {}
            current = current[part]
            
        if isinstance(current, dict):
            return current.copy()
        return {}
        
    def __getitem__(self, key: str) -> Any:
        """Allow dict-like access."""
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value
        
    def __setitem__(self, key: str, value: Any) -> None:
        """Allow dict-like setting."""
        self.set(key, value)
        
    def __contains__(self, key: str) -> bool:
        """Check if key exists."""
        return self.has(key)


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def config(key: str, default: Any = None) -> Any:
    """Shortcut function for configuration access."""
    return get_config().get(key, default)
