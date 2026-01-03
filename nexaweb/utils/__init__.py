"""
NexaWeb Utils Package
=====================

Utility functions, helpers, and environment management.
"""

from __future__ import annotations

from nexaweb.utils.env import Env, env, load_env
from nexaweb.utils.logger import Logger, LogLevel, get_logger, configure_logging
from nexaweb.utils.helpers import (
    # String helpers
    slugify,
    truncate,
    snake_case,
    camel_case,
    pascal_case,
    kebab_case,
    pluralize,
    singularize,
    # Collection helpers
    get_nested,
    set_nested,
    flatten,
    unique,
    chunk,
    # Time helpers
    now,
    timestamp,
    parse_date,
    format_date,
    time_ago,
    # Other helpers
    retry,
    memoize,
    debounce,
    throttle,
)

__all__ = [
    # Environment
    "Env",
    "env",
    "load_env",
    # Logging
    "Logger",
    "LogLevel",
    "get_logger",
    "configure_logging",
    # String helpers
    "slugify",
    "truncate",
    "snake_case",
    "camel_case",
    "pascal_case",
    "kebab_case",
    "pluralize",
    "singularize",
    # Collection helpers
    "get_nested",
    "set_nested",
    "flatten",
    "unique",
    "chunk",
    # Time helpers
    "now",
    "timestamp",
    "parse_date",
    "format_date",
    "time_ago",
    # Other
    "retry",
    "memoize",
    "debounce",
    "throttle",
]
