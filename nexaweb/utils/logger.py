"""
NexaWeb Logger
==============

Structured logging with multiple handlers.
"""

from __future__ import annotations

import json
import logging
import sys
import traceback
from datetime import datetime
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field


class LogLevel(IntEnum):
    """Log levels."""
    
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


@dataclass
class LogRecord:
    """
    Structured log record.
    
    Attributes:
        level: Log level
        message: Log message
        timestamp: Record timestamp
        context: Additional context
        exception: Exception info
    """
    
    level: LogLevel
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    context: Dict[str, Any] = field(default_factory=dict)
    exception: Optional[BaseException] = None
    logger_name: str = "nexaweb"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.name,
            "message": self.message,
            "logger": self.logger_name,
        }
        
        if self.context:
            data["context"] = self.context
        
        if self.exception:
            data["exception"] = {
                "type": type(self.exception).__name__,
                "message": str(self.exception),
                "traceback": traceback.format_exception(
                    type(self.exception),
                    self.exception,
                    self.exception.__traceback__,
                ),
            }
        
        return data
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class LogFormatter:
    """Base log formatter."""
    
    def format(self, record: LogRecord) -> str:
        """Format log record."""
        raise NotImplementedError


class TextFormatter(LogFormatter):
    """
    Plain text formatter.
    
    Example output:
        2024-01-15 10:30:45 [INFO] Request received path=/api/users
    """
    
    def __init__(
        self,
        format_string: Optional[str] = None,
        date_format: str = "%Y-%m-%d %H:%M:%S",
        colors: bool = True,
    ):
        """Initialize formatter."""
        self.format_string = format_string or "{timestamp} [{level}] {message}"
        self.date_format = date_format
        self.colors = colors and sys.stdout.isatty()
        
        self._colors = {
            LogLevel.DEBUG: "\033[36m",    # Cyan
            LogLevel.INFO: "\033[32m",     # Green
            LogLevel.WARNING: "\033[33m",  # Yellow
            LogLevel.ERROR: "\033[31m",    # Red
            LogLevel.CRITICAL: "\033[35m", # Magenta
        }
        self._reset = "\033[0m"
    
    def format(self, record: LogRecord) -> str:
        """Format as text."""
        timestamp = record.timestamp.strftime(self.date_format)
        level = record.level.name
        
        # Add color
        if self.colors:
            color = self._colors.get(record.level, "")
            level = f"{color}{level}{self._reset}"
        
        # Build message
        message = record.message
        
        # Add context as key=value pairs
        if record.context:
            context_str = " ".join(
                f"{k}={v}" for k, v in record.context.items()
            )
            message = f"{message} {context_str}"
        
        output = self.format_string.format(
            timestamp=timestamp,
            level=level,
            message=message,
            logger=record.logger_name,
        )
        
        # Add exception
        if record.exception:
            output += "\n" + "".join(
                traceback.format_exception(
                    type(record.exception),
                    record.exception,
                    record.exception.__traceback__,
                )
            )
        
        return output


class JsonFormatter(LogFormatter):
    """
    JSON formatter for structured logging.
    
    Example output:
        {"timestamp": "2024-01-15T10:30:45", "level": "INFO", "message": "Request received"}
    """
    
    def __init__(self, pretty: bool = False):
        """Initialize formatter."""
        self.pretty = pretty
    
    def format(self, record: LogRecord) -> str:
        """Format as JSON."""
        if self.pretty:
            return json.dumps(record.to_dict(), indent=2)
        return record.to_json()


class LogHandler:
    """Base log handler."""
    
    def __init__(
        self,
        formatter: Optional[LogFormatter] = None,
        level: LogLevel = LogLevel.DEBUG,
    ):
        """Initialize handler."""
        self.formatter = formatter or TextFormatter()
        self.level = level
    
    def handle(self, record: LogRecord) -> None:
        """Handle log record."""
        if record.level >= self.level:
            self.emit(record)
    
    def emit(self, record: LogRecord) -> None:
        """Emit formatted record."""
        raise NotImplementedError


class StreamHandler(LogHandler):
    """Stream output handler."""
    
    def __init__(
        self,
        stream: Any = None,
        formatter: Optional[LogFormatter] = None,
        level: LogLevel = LogLevel.DEBUG,
    ):
        """Initialize stream handler."""
        super().__init__(formatter, level)
        self.stream = stream or sys.stderr
    
    def emit(self, record: LogRecord) -> None:
        """Write to stream."""
        message = self.formatter.format(record)
        self.stream.write(message + "\n")
        self.stream.flush()


class FileHandler(LogHandler):
    """File output handler."""
    
    def __init__(
        self,
        path: Union[str, Path],
        formatter: Optional[LogFormatter] = None,
        level: LogLevel = LogLevel.DEBUG,
        max_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
    ):
        """Initialize file handler."""
        super().__init__(formatter or JsonFormatter(), level)
        self.path = Path(path)
        self.max_size = max_size
        self.backup_count = backup_count
        
        # Ensure directory exists
        self.path.parent.mkdir(parents=True, exist_ok=True)
    
    def emit(self, record: LogRecord) -> None:
        """Write to file."""
        # Check rotation
        if self.path.exists() and self.path.stat().st_size > self.max_size:
            self._rotate()
        
        message = self.formatter.format(record)
        
        with open(self.path, "a") as f:
            f.write(message + "\n")
    
    def _rotate(self) -> None:
        """Rotate log files."""
        # Remove oldest backup
        oldest = self.path.with_suffix(f".{self.backup_count}")
        if oldest.exists():
            oldest.unlink()
        
        # Shift existing backups
        for i in range(self.backup_count - 1, 0, -1):
            src = self.path.with_suffix(f".{i}")
            dst = self.path.with_suffix(f".{i + 1}")
            if src.exists():
                src.rename(dst)
        
        # Move current to .1
        if self.path.exists():
            self.path.rename(self.path.with_suffix(".1"))


class Logger:
    """
    Structured logger.
    
    Example:
        logger = Logger("myapp")
        
        logger.info("Request received", path="/api/users", method="GET")
        logger.error("Database error", exception=e)
        
        # With context
        logger = logger.with_context(request_id="abc123")
        logger.info("Processing request")
    """
    
    def __init__(
        self,
        name: str = "nexaweb",
        level: LogLevel = LogLevel.DEBUG,
        handlers: Optional[List[LogHandler]] = None,
    ):
        """
        Initialize logger.
        
        Args:
            name: Logger name
            level: Minimum log level
            handlers: Log handlers
        """
        self.name = name
        self.level = level
        self._handlers = handlers or []
        self._context: Dict[str, Any] = {}
    
    def add_handler(self, handler: LogHandler) -> "Logger":
        """Add log handler."""
        self._handlers.append(handler)
        return self
    
    def remove_handler(self, handler: LogHandler) -> "Logger":
        """Remove log handler."""
        self._handlers.remove(handler)
        return self
    
    def with_context(self, **context: Any) -> "Logger":
        """
        Create logger with additional context.
        
        Args:
            **context: Context key-values
            
        Returns:
            New logger with context
        """
        new_logger = Logger(
            name=self.name,
            level=self.level,
            handlers=self._handlers,
        )
        new_logger._context = {**self._context, **context}
        return new_logger
    
    def _log(
        self,
        level: LogLevel,
        message: str,
        exception: Optional[BaseException] = None,
        **context: Any,
    ) -> None:
        """Internal log method."""
        if level < self.level:
            return
        
        # Merge context
        merged_context = {**self._context, **context}
        
        # Create record
        record = LogRecord(
            level=level,
            message=message,
            context=merged_context,
            exception=exception,
            logger_name=self.name,
        )
        
        # Send to handlers
        for handler in self._handlers:
            try:
                handler.handle(record)
            except Exception:
                pass  # Don't let logging errors break the app
    
    def debug(self, message: str, **context: Any) -> None:
        """Log debug message."""
        self._log(LogLevel.DEBUG, message, **context)
    
    def info(self, message: str, **context: Any) -> None:
        """Log info message."""
        self._log(LogLevel.INFO, message, **context)
    
    def warning(self, message: str, **context: Any) -> None:
        """Log warning message."""
        self._log(LogLevel.WARNING, message, **context)
    
    def error(
        self,
        message: str,
        exception: Optional[BaseException] = None,
        **context: Any,
    ) -> None:
        """Log error message."""
        self._log(LogLevel.ERROR, message, exception, **context)
    
    def critical(
        self,
        message: str,
        exception: Optional[BaseException] = None,
        **context: Any,
    ) -> None:
        """Log critical message."""
        self._log(LogLevel.CRITICAL, message, exception, **context)
    
    def exception(
        self,
        message: str,
        **context: Any,
    ) -> None:
        """Log current exception."""
        import sys
        exc = sys.exc_info()[1]
        self._log(LogLevel.ERROR, message, exc, **context)


# Global logger registry
_loggers: Dict[str, Logger] = {}


def get_logger(
    name: str = "nexaweb",
    level: Optional[LogLevel] = None,
) -> Logger:
    """
    Get or create logger.
    
    Args:
        name: Logger name
        level: Log level
        
    Returns:
        Logger instance
    """
    if name not in _loggers:
        _loggers[name] = Logger(name=name, level=level or LogLevel.DEBUG)
        
        # Add default handler
        _loggers[name].add_handler(StreamHandler())
    
    return _loggers[name]


def configure_logging(
    level: LogLevel = LogLevel.INFO,
    format: str = "text",
    log_file: Optional[str] = None,
    colors: bool = True,
) -> Logger:
    """
    Configure default logging.
    
    Args:
        level: Log level
        format: Output format ("text" or "json")
        log_file: Optional log file path
        colors: Enable colored output
        
    Returns:
        Configured logger
    """
    # Create formatter
    if format == "json":
        formatter = JsonFormatter()
    else:
        formatter = TextFormatter(colors=colors)
    
    # Create handlers
    handlers = [StreamHandler(formatter=formatter, level=level)]
    
    if log_file:
        file_formatter = JsonFormatter() if format == "json" else TextFormatter(colors=False)
        handlers.append(FileHandler(log_file, formatter=file_formatter, level=level))
    
    # Create logger
    logger = Logger(name="nexaweb", level=level, handlers=handlers)
    _loggers["nexaweb"] = logger
    
    return logger
