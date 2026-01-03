"""
NexaWeb Native Core Package
===========================

Native C++ extensions for performance-critical operations.
These are stub implementations that can be replaced with
native modules for better performance.
"""

from __future__ import annotations

from nexaweb.native.router import NativeRouter, RouteMatch
from nexaweb.native.parser import NativeParser, Token, TokenType
from nexaweb.native.pool import NativePool, PooledConnection

__all__ = [
    # Router
    "NativeRouter",
    "RouteMatch",
    # Parser
    "NativeParser",
    "Token",
    "TokenType",
    # Pool
    "NativePool",
    "PooledConnection",
]

# Flag to check if native extensions are available
NATIVE_AVAILABLE = False

try:
    # Try to import compiled native module
    from nexaweb._native import (
        native_router,
        native_parser,
        native_pool,
    )
    NATIVE_AVAILABLE = True
except ImportError:
    pass
