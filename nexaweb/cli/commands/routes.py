"""
NexaWeb CLI Routes Command
==========================

List all registered routes.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Tuple


def list_routes() -> int:
    """
    List all registered routes.
    
    Returns:
        Exit code
    """
    # Find and load app
    app = _load_app()
    
    if not app:
        print("Error: Could not find application", file=sys.stderr)
        return 1
    
    # Get routes from router
    routes = _extract_routes(app)
    
    if not routes:
        print("No routes found")
        return 0
    
    # Print routes
    _print_routes(routes)
    
    return 0


def _load_app():
    """Load application instance."""
    import importlib.util
    
    # Check common locations
    app_files = [
        Path.cwd() / "app.py",
        Path.cwd() / "main.py",
        Path.cwd() / "application.py",
    ]
    
    for app_file in app_files:
        if not app_file.exists():
            continue
            
        try:
            # Add cwd to path
            sys.path.insert(0, str(Path.cwd()))
            
            spec = importlib.util.spec_from_file_location("app", app_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Look for app instance
            for attr_name in ["app", "application", "api"]:
                if hasattr(module, attr_name):
                    return getattr(module, attr_name)
            
            # Look for create_app function
            if hasattr(module, "create_app"):
                return module.create_app()
                
        except Exception as e:
            print(f"Warning: Failed to load {app_file}: {e}", file=sys.stderr)
            continue
    
    return None


def _extract_routes(app) -> List[Tuple[str, str, str, str]]:
    """
    Extract routes from application.
    
    Returns:
        List of (method, path, name, handler) tuples
    """
    routes = []
    
    # Try to get router
    router = getattr(app, "router", None) or getattr(app, "_router", None)
    
    if not router:
        return routes
    
    # Extract from router
    route_map = getattr(router, "routes", None) or getattr(router, "_routes", None)
    
    if not route_map:
        return routes
    
    # Handle different router structures
    if isinstance(route_map, dict):
        for method, paths in route_map.items():
            if isinstance(paths, dict):
                for path, handler_info in paths.items():
                    handler_name = _get_handler_name(handler_info)
                    route_name = _get_route_name(handler_info)
                    routes.append((method.upper(), path, route_name, handler_name))
            elif isinstance(paths, list):
                for route in paths:
                    path = getattr(route, "path", str(route))
                    handler_name = _get_handler_name(route)
                    route_name = _get_route_name(route)
                    routes.append((method.upper(), path, route_name, handler_name))
    elif isinstance(route_map, list):
        for route in route_map:
            method = getattr(route, "method", "GET")
            path = getattr(route, "path", "/")
            handler_name = _get_handler_name(route)
            route_name = _get_route_name(route)
            routes.append((method.upper(), path, route_name, handler_name))
    
    # Sort by path then method
    routes.sort(key=lambda r: (r[1], r[0]))
    
    return routes


def _get_handler_name(handler_info) -> str:
    """Get handler name from route info."""
    if hasattr(handler_info, "handler"):
        handler = handler_info.handler
    elif hasattr(handler_info, "__call__"):
        handler = handler_info
    elif isinstance(handler_info, tuple):
        handler = handler_info[0] if handler_info else None
    else:
        return str(handler_info)
    
    if handler:
        if hasattr(handler, "__name__"):
            return handler.__name__
        elif hasattr(handler, "__class__"):
            return handler.__class__.__name__
    
    return str(handler)


def _get_route_name(handler_info) -> str:
    """Get route name if defined."""
    if hasattr(handler_info, "name"):
        return handler_info.name or ""
    elif isinstance(handler_info, tuple) and len(handler_info) > 1:
        return str(handler_info[1])
    return ""


def _print_routes(routes: List[Tuple[str, str, str, str]]) -> None:
    """Print routes in a formatted table."""
    # Calculate column widths
    method_width = max(len(r[0]) for r in routes)
    path_width = max(len(r[1]) for r in routes)
    name_width = max((len(r[2]) for r in routes if r[2]), default=0)
    
    method_width = max(method_width, 6)
    path_width = max(path_width, 4)
    name_width = max(name_width, 4)
    
    # Print header
    print()
    header = f"{'Method':<{method_width}}  {'Path':<{path_width}}"
    if name_width > 4:
        header += f"  {'Name':<{name_width}}"
    header += "  Handler"
    
    print(header)
    print("-" * len(header))
    
    # Print routes
    for method, path, name, handler in routes:
        # Color methods
        method_display = _colorize_method(method, method_width)
        
        line = f"{method_display}  {path:<{path_width}}"
        if name_width > 4:
            line += f"  {name:<{name_width}}"
        line += f"  {handler}"
        
        print(line)
    
    print()
    print(f"Total: {len(routes)} routes")
    print()


def _colorize_method(method: str, width: int) -> str:
    """Add ANSI colors to HTTP method."""
    colors = {
        "GET": "\033[92m",     # Green
        "POST": "\033[93m",    # Yellow
        "PUT": "\033[94m",     # Blue
        "PATCH": "\033[96m",   # Cyan
        "DELETE": "\033[91m",  # Red
        "HEAD": "\033[95m",    # Magenta
        "OPTIONS": "\033[90m", # Gray
    }
    
    reset = "\033[0m"
    color = colors.get(method, "")
    
    if color and sys.stdout.isatty():
        return f"{color}{method:<{width}}{reset}"
    
    return f"{method:<{width}}"
