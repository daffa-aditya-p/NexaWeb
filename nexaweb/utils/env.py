"""
NexaWeb Environment Management
==============================

Environment variable loading and management.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar, Union, overload


T = TypeVar("T")


class Env:
    """
    Environment variable manager.
    
    Loads environment variables from .env files and provides
    typed access with defaults and validation.
    
    Example:
        # Load from .env file
        env = Env()
        env.load()
        
        # Get values with type conversion
        debug = env.bool("DEBUG", default=False)
        port = env.int("PORT", default=8000)
        hosts = env.list("ALLOWED_HOSTS", default=["localhost"])
        
        # Required values
        secret = env.str("SECRET_KEY", required=True)
    """
    
    def __init__(
        self,
        env_file: Optional[Union[str, Path]] = None,
        override: bool = False,
    ):
        """
        Initialize environment manager.
        
        Args:
            env_file: Path to .env file
            override: Override existing environment variables
        """
        self._env_file = Path(env_file) if env_file else None
        self._override = override
        self._cache: Dict[str, str] = {}
        self._loaded = False
    
    def load(
        self,
        env_file: Optional[Union[str, Path]] = None,
        override: Optional[bool] = None,
    ) -> "Env":
        """
        Load environment from file.
        
        Args:
            env_file: Path to .env file (optional)
            override: Override existing variables
            
        Returns:
            Self for chaining
        """
        path = Path(env_file) if env_file else self._env_file
        should_override = override if override is not None else self._override
        
        # Find .env file
        if not path:
            path = self._find_env_file()
        
        if path and path.exists():
            self._load_file(path, should_override)
        
        self._loaded = True
        return self
    
    def _find_env_file(self) -> Optional[Path]:
        """Find .env file in current directory or parents."""
        cwd = Path.cwd()
        
        # Check current directory and parents
        for directory in [cwd] + list(cwd.parents)[:3]:
            env_file = directory / ".env"
            if env_file.exists():
                return env_file
            
            # Also check for environment-specific files
            env_name = os.getenv("APP_ENV", "development")
            specific_file = directory / f".env.{env_name}"
            if specific_file.exists():
                return specific_file
        
        return None
    
    def _load_file(self, path: Path, override: bool) -> None:
        """Load environment variables from file."""
        content = path.read_text()
        
        for line in content.splitlines():
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue
            
            # Handle export prefix
            if line.startswith("export "):
                line = line[7:]
            
            # Parse key=value
            if "=" not in line:
                continue
            
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            
            # Remove quotes
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            
            # Handle escape sequences in double-quoted strings
            if value.startswith('"'):
                value = value.encode().decode("unicode_escape")
            
            # Expand variables
            value = self._expand_variables(value)
            
            # Set in cache
            self._cache[key] = value
            
            # Set in environment if not exists or override
            if override or key not in os.environ:
                os.environ[key] = value
    
    def _expand_variables(self, value: str) -> str:
        """Expand environment variables in value."""
        import re
        
        def replace(match):
            var_name = match.group(1) or match.group(2)
            return os.getenv(var_name, self._cache.get(var_name, ""))
        
        # Match ${VAR} or $VAR
        pattern = r"\$\{([^}]+)\}|\$(\w+)"
        return re.sub(pattern, replace, value)
    
    def get(
        self,
        key: str,
        default: Optional[str] = None,
        required: bool = False,
    ) -> Optional[str]:
        """
        Get environment variable.
        
        Args:
            key: Variable name
            default: Default value
            required: Raise error if not found
            
        Returns:
            Variable value
            
        Raises:
            KeyError: If required and not found
        """
        value = os.getenv(key, self._cache.get(key, default))
        
        if value is None and required:
            raise KeyError(f"Required environment variable '{key}' is not set")
        
        return value
    
    def str(
        self,
        key: str,
        default: Optional[str] = None,
        required: bool = False,
    ) -> Optional[str]:
        """Get string value."""
        return self.get(key, default, required)
    
    def int(
        self,
        key: str,
        default: Optional[int] = None,
        required: bool = False,
    ) -> Optional[int]:
        """Get integer value."""
        value = self.get(key, required=required)
        
        if value is None:
            return default
        
        try:
            return int(value)
        except ValueError:
            if default is not None:
                return default
            raise ValueError(f"Environment variable '{key}' is not a valid integer")
    
    def float(
        self,
        key: str,
        default: Optional[float] = None,
        required: bool = False,
    ) -> Optional[float]:
        """Get float value."""
        value = self.get(key, required=required)
        
        if value is None:
            return default
        
        try:
            return float(value)
        except ValueError:
            if default is not None:
                return default
            raise ValueError(f"Environment variable '{key}' is not a valid float")
    
    def bool(
        self,
        key: str,
        default: Optional[bool] = None,
        required: bool = False,
    ) -> Optional[bool]:
        """Get boolean value."""
        value = self.get(key, required=required)
        
        if value is None:
            return default
        
        # Truthy values
        if value.lower() in ("true", "1", "yes", "on", "enabled"):
            return True
        
        # Falsy values
        if value.lower() in ("false", "0", "no", "off", "disabled", ""):
            return False
        
        if default is not None:
            return default
        
        raise ValueError(f"Environment variable '{key}' is not a valid boolean")
    
    def list(
        self,
        key: str,
        default: Optional[List[str]] = None,
        separator: str = ",",
        required: bool = False,
    ) -> Optional[List[str]]:
        """Get list value (comma-separated by default)."""
        value = self.get(key, required=required)
        
        if value is None:
            return default
        
        if not value:
            return []
        
        return [item.strip() for item in value.split(separator)]
    
    def dict(
        self,
        prefix: str,
    ) -> Dict[str, str]:
        """
        Get all variables with prefix as dict.
        
        Args:
            prefix: Variable prefix (e.g., "DB_")
            
        Returns:
            Dict of matching variables with prefix removed
        """
        result = {}
        
        for key, value in os.environ.items():
            if key.startswith(prefix):
                result_key = key[len(prefix):].lower()
                result[result_key] = value
        
        return result
    
    def set(self, key: str, value: str) -> None:
        """Set environment variable."""
        os.environ[key] = value
        self._cache[key] = value
    
    def unset(self, key: str) -> None:
        """Unset environment variable."""
        os.environ.pop(key, None)
        self._cache.pop(key, None)
    
    def __getitem__(self, key: str) -> Optional[str]:
        return self.get(key)
    
    def __setitem__(self, key: str, value: str) -> None:
        self.set(key, value)
    
    def __contains__(self, key: str) -> bool:
        return key in os.environ or key in self._cache


# Global instance
_env: Optional[Env] = None


def env(
    key: str,
    default: Any = None,
    required: bool = False,
) -> Any:
    """
    Get environment variable using global instance.
    
    Args:
        key: Variable name
        default: Default value
        required: Raise if not found
        
    Returns:
        Variable value
    """
    global _env
    
    if _env is None:
        _env = Env()
        _env.load()
    
    return _env.get(key, default, required)


def load_env(
    env_file: Optional[Union[str, Path]] = None,
    override: bool = False,
) -> Env:
    """
    Load environment from file.
    
    Args:
        env_file: Path to .env file
        override: Override existing variables
        
    Returns:
        Env instance
    """
    global _env
    
    _env = Env(env_file, override)
    _env.load()
    
    return _env
