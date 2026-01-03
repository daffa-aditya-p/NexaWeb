"""
███╗   ██╗███████╗██╗  ██╗ █████╗ ██╗    ██╗███████╗██████╗
████╗  ██║██╔════╝╚██╗██╔╝██╔══██╗██║    ██║██╔════╝██╔══██╗
██╔██╗ ██║█████╗   ╚███╔╝ ███████║██║ █╗ ██║█████╗  ██████╔╝
██║╚██╗██║██╔══╝   ██╔██╗ ██╔══██║██║███╗██║██╔══╝  ██╔══██╗
██║ ╚████║███████╗██╔╝ ██╗██║  ██║╚███╔███╔╝███████╗██████╔╝
╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚══╝╚══╝ ╚══════╝╚═════╝

NexaWeb - Next-Generation Full-Stack Python Framework
======================================================

A high-performance, lightweight, full-stack web framework built with Python
with optional C++ native extensions. Designed to compete with Laravel and React
while being significantly lighter, faster, and more efficient.

Features:
---------
- Full Application Framework (not just API)
- Custom PYXM Template Engine (HTML + Python expressions)
- Native Async Support (ASGI-compatible)
- Security-First Design (CSRF, XSS, Rate Limiting)
- Lightweight ORM with Query Builder
- JWT & Session Authentication
- Flexible Validation System
- Plugin Architecture with Hooks
- CLI Tools for Scaffolding

Quick Start:
    $ pip install nexaweb
    $ nexaweb create myproject
    $ cd myproject
    $ nexaweb serve

Documentation: https://nexaweb.dev
Repository: https://github.com/nexaweb/nexaweb
"""

from __future__ import annotations

__version__ = "1.0.0-alpha.1"
__author__ = "NexaWeb Team"
__license__ = "MIT"

from typing import TYPE_CHECKING

# Core imports (always available)
from nexaweb.core.application import Application
from nexaweb.core.router import Router
from nexaweb.core.request import Request
from nexaweb.core.response import Response
from nexaweb.core.middleware import Middleware
from nexaweb.core.config import Config

# Lazy imports for performance
if TYPE_CHECKING:
    from nexaweb.pyxm import Template, Parser, Compiler
    from nexaweb.security import CSRF, XSS, RateLimiter
    from nexaweb.auth import Authenticator, Session, JWTHandler
    from nexaweb.orm import Model, QueryBuilder, Database
    from nexaweb.validation import Validator, Form
    from nexaweb.plugins import Plugin, PluginManager


def __getattr__(name: str):
    """Lazy loading of optional components for faster startup."""
    _imports = {
        # PYXM Template Engine
        "Template": "nexaweb.pyxm.template",
        "Parser": "nexaweb.pyxm.parser",
        "Compiler": "nexaweb.pyxm.compiler",
        "Reactive": "nexaweb.pyxm.reactive",
        # Security
        "CSRF": "nexaweb.security.csrf",
        "XSS": "nexaweb.security.xss",
        "RateLimiter": "nexaweb.security.rate_limiter",
        "Sanitizer": "nexaweb.security.sanitizer",
        # Auth
        "Authenticator": "nexaweb.auth.authenticator",
        "Session": "nexaweb.auth.session",
        "JWTHandler": "nexaweb.auth.jwt_handler",
        "Guard": "nexaweb.auth.guards",
        # ORM
        "Model": "nexaweb.orm.model",
        "QueryBuilder": "nexaweb.orm.query",
        "Database": "nexaweb.orm.connection",
        "Migration": "nexaweb.orm.migrations",
        # Validation
        "Validator": "nexaweb.validation.validator",
        "Form": "nexaweb.validation.form",
        "Rule": "nexaweb.validation.rules",
        # Plugins
        "Plugin": "nexaweb.plugins.base",
        "PluginManager": "nexaweb.plugins.loader",
        "Hook": "nexaweb.plugins.hooks",
        # Utils
        "Logger": "nexaweb.utils.logger",
        "Env": "nexaweb.utils.env",
    }
    
    if name in _imports:
        import importlib
        module = importlib.import_module(_imports[name])
        return getattr(module, name)
    
    raise AttributeError(f"module 'nexaweb' has no attribute '{name}'")


__all__ = [
    # Metadata
    "__version__",
    "__author__",
    "__license__",
    # Core (always loaded)
    "Application",
    "Router",
    "Request",
    "Response",
    "Middleware",
    "Config",
    # PYXM Template (lazy)
    "Template",
    "Parser",
    "Compiler",
    "Reactive",
    # Security (lazy)
    "CSRF",
    "XSS",
    "RateLimiter",
    "Sanitizer",
    # Auth (lazy)
    "Authenticator",
    "Session",
    "JWTHandler",
    "Guard",
    # ORM (lazy)
    "Model",
    "QueryBuilder",
    "Database",
    "Migration",
    # Validation (lazy)
    "Validator",
    "Form",
    "Rule",
    # Plugins (lazy)
    "Plugin",
    "PluginManager",
    "Hook",
    # Utils (lazy)
    "Logger",
    "Env",
]
