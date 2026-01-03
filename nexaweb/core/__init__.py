"""
NexaWeb Core Module
===================

Contains the fundamental building blocks of the NexaWeb framework:
- Application: Main application container and lifecycle manager
- Server: High-performance async HTTP server
- Router: URL routing with pattern matching and middleware support
- Request/Response: HTTP message abstractions
- Middleware: Request/Response processing pipeline
- Config: Configuration management
"""

from nexaweb.core.application import NexaApp
from nexaweb.core.router import Router, route, get, post, put, delete, patch
from nexaweb.core.request import Request
from nexaweb.core.response import Response, HTMLResponse, JSONResponse, RedirectResponse
from nexaweb.core.middleware import Middleware, MiddlewareStack
from nexaweb.core.config import Config

__all__ = [
    "NexaApp",
    "Router",
    "route",
    "get",
    "post",
    "put",
    "delete",
    "patch",
    "Request",
    "Response",
    "HTMLResponse",
    "JSONResponse",
    "RedirectResponse",
    "Middleware",
    "MiddlewareStack",
    "Config",
]
