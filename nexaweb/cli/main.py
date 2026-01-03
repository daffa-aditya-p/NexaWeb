"""
NexaWeb CLI Main Module
=======================

Main CLI entry point with all commands.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Version
__version__ = "0.1.0"


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        prog="nexaweb",
        description="NexaWeb Framework CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  nexaweb create myapp           Create a new NexaWeb project
  nexaweb serve                  Run development server
  nexaweb build                  Build for production
  nexaweb migrate                Run database migrations
  nexaweb make:controller users  Create a new controller
        """,
    )
    
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"NexaWeb {__version__}",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Create command
    create_parser = subparsers.add_parser(
        "create",
        help="Create a new NexaWeb project",
    )
    create_parser.add_argument(
        "name",
        help="Project name",
    )
    create_parser.add_argument(
        "--template",
        choices=["minimal", "standard", "full"],
        default="standard",
        help="Project template",
    )
    create_parser.add_argument(
        "--no-install",
        action="store_true",
        help="Skip dependency installation",
    )
    
    # Serve command
    serve_parser = subparsers.add_parser(
        "serve",
        help="Run development server",
    )
    serve_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to",
    )
    serve_parser.add_argument(
        "--reload",
        action="store_true",
        default=True,
        help="Enable auto-reload",
    )
    serve_parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes",
    )
    
    # Build command
    build_parser = subparsers.add_parser(
        "build",
        help="Build for production",
    )
    build_parser.add_argument(
        "--minify",
        action="store_true",
        help="Minify assets",
    )
    build_parser.add_argument(
        "--output",
        default="dist",
        help="Output directory",
    )
    
    # Migrate commands
    migrate_parser = subparsers.add_parser(
        "migrate",
        help="Run database migrations",
    )
    migrate_parser.add_argument(
        "action",
        nargs="?",
        default="run",
        choices=["run", "rollback", "reset", "refresh", "status"],
        help="Migration action",
    )
    migrate_parser.add_argument(
        "--steps",
        type=int,
        default=1,
        help="Number of batches to rollback",
    )
    
    # Make commands
    make_parser = subparsers.add_parser(
        "make",
        help="Generate components",
    )
    make_parser.add_argument(
        "type",
        choices=["controller", "model", "migration", "middleware", "guard"],
        help="Component type to generate",
    )
    make_parser.add_argument(
        "name",
        help="Component name",
    )
    
    # Routes command
    subparsers.add_parser(
        "routes",
        help="List all routes",
    )
    
    # Shell command
    subparsers.add_parser(
        "shell",
        help="Start interactive shell",
    )
    
    return parser


def cli(args: Optional[List[str]] = None) -> int:
    """
    Main CLI entry point.
    
    Args:
        args: Command line arguments (uses sys.argv if None)
        
    Returns:
        Exit code
    """
    parser = create_parser()
    parsed = parser.parse_args(args)
    
    if not parsed.command:
        parser.print_help()
        return 0
        
    # Route to command handler
    handlers = {
        "create": handle_create,
        "serve": handle_serve,
        "build": handle_build,
        "migrate": handle_migrate,
        "make": handle_make,
        "routes": handle_routes,
        "shell": handle_shell,
    }
    
    handler = handlers.get(parsed.command)
    if handler:
        try:
            return handler(parsed)
        except KeyboardInterrupt:
            print("\nAborted.")
            return 130
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    else:
        parser.print_help()
        return 1


def handle_create(args: argparse.Namespace) -> int:
    """Handle create command."""
    from nexaweb.cli.commands.create import create_project
    return create_project(args.name, args.template, not args.no_install)


def handle_serve(args: argparse.Namespace) -> int:
    """Handle serve command."""
    from nexaweb.cli.commands.serve import run_server
    return run_server(args.host, args.port, args.reload, args.workers)


def handle_build(args: argparse.Namespace) -> int:
    """Handle build command."""
    from nexaweb.cli.commands.build import build_project
    return build_project(args.output, args.minify)


def handle_migrate(args: argparse.Namespace) -> int:
    """Handle migrate command."""
    from nexaweb.cli.commands.migrate import run_migration
    return asyncio.run(run_migration(args.action, args.steps))


def handle_make(args: argparse.Namespace) -> int:
    """Handle make command."""
    from nexaweb.cli.commands.make import make_component
    return make_component(args.type, args.name)


def handle_routes(args: argparse.Namespace) -> int:
    """Handle routes command."""
    from nexaweb.cli.commands.routes import list_routes
    return list_routes()


def handle_shell(args: argparse.Namespace) -> int:
    """Handle shell command."""
    from nexaweb.cli.commands.shell import start_shell
    return start_shell()


def main() -> None:
    """Main entry point."""
    sys.exit(cli())


if __name__ == "__main__":
    main()
