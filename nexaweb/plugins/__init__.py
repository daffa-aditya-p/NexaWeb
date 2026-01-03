"""
NexaWeb Plugin System
=====================

Plugin loading, hooks, and extension points.
"""

from __future__ import annotations

from nexaweb.plugins.loader import PluginLoader, PluginManager
from nexaweb.plugins.hooks import Hook, HookRegistry, EventEmitter
from nexaweb.plugins.base import Plugin, PluginMeta, PluginInfo

__all__ = [
    # Loader
    "PluginLoader",
    "PluginManager",
    # Hooks
    "Hook",
    "HookRegistry",
    "EventEmitter",
    # Base
    "Plugin",
    "PluginMeta",
    "PluginInfo",
]
