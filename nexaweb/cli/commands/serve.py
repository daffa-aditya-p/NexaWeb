"""
NexaWeb CLI Serve Command
=========================

Run development server.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional


def run_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = True,
    workers: int = 1,
) -> int:
    """
    Run development server.
    
    Args:
        host: Host to bind to
        port: Port to bind to
        reload: Enable auto-reload
        workers: Number of workers
        
    Returns:
        Exit code
    """
    # Check for app file
    app_file = _find_app_file()
    
    if not app_file:
        print("Error: Could not find app.py or application entry point", file=sys.stderr)
        print("Make sure you're in a NexaWeb project directory", file=sys.stderr)
        return 1
    
    # Try to import uvicorn
    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is not installed", file=sys.stderr)
        print("Install it with: pip install uvicorn[standard]", file=sys.stderr)
        return 1
    
    print(f"Starting NexaWeb development server...")
    print(f"  URL: http://{host}:{port}")
    print(f"  Reload: {'enabled' if reload else 'disabled'}")
    print()
    
    # Determine app string
    app_string = _get_app_string(app_file)
    
    # Run server
    config = uvicorn.Config(
        app_string,
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,
        log_level="info",
    )
    
    server = uvicorn.Server(config)
    
    try:
        server.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
    
    return 0


def _find_app_file() -> Optional[Path]:
    """Find application entry point."""
    cwd = Path.cwd()
    
    # Check common locations
    candidates = [
        cwd / "app.py",
        cwd / "main.py",
        cwd / "application.py",
        cwd / "src" / "app.py",
        cwd / "src" / "main.py",
    ]
    
    for candidate in candidates:
        if candidate.exists():
            return candidate
    
    return None


def _get_app_string(app_file: Path) -> str:
    """Get uvicorn app string from file."""
    module_name = app_file.stem
    
    # Read file to find app variable
    content = app_file.read_text()
    
    # Look for common app variable names
    app_names = ["app", "application", "api", "server"]
    
    for name in app_names:
        # Check for assignment
        if f"{name} = " in content or f"{name}=" in content:
            return f"{module_name}:{name}"
    
    # Check for create_app function
    if "create_app" in content:
        return f"{module_name}:create_app"
    
    # Default
    return f"{module_name}:app"
