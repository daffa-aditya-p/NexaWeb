"""
NexaWeb CLI
===========

Command-line interface for NexaWeb framework.

Commands:
- create: Create new project or component
- serve: Run development server
- build: Build for production
- migrate: Run database migrations
"""

from nexaweb.cli.main import main, cli

__all__ = ["main", "cli"]
