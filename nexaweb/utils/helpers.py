"""
NexaWeb Helpers
===============

Collection of utility functions.
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import re
import time
from datetime import datetime, timedelta
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    TypeVar,
    Union,
)


T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


# =============================================================================
# String Helpers
# =============================================================================

def slugify(text: str, separator: str = "-") -> str:
    """
    Convert text to URL-safe slug.
    
    Args:
        text: Input text
        separator: Word separator
        
    Returns:
        Slugified text
        
    Example:
        >>> slugify("Hello World!")
        'hello-world'
    """
    # Convert to lowercase
    text = text.lower()
    
    # Remove accents (basic)
    replacements = {
        "à": "a", "á": "a", "â": "a", "ã": "a", "ä": "a", "å": "a",
        "è": "e", "é": "e", "ê": "e", "ë": "e",
        "ì": "i", "í": "i", "î": "i", "ï": "i",
        "ò": "o", "ó": "o", "ô": "o", "õ": "o", "ö": "o",
        "ù": "u", "ú": "u", "û": "u", "ü": "u",
        "ñ": "n", "ç": "c",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    # Replace non-alphanumeric with separator
    text = re.sub(r"[^a-z0-9]+", separator, text)
    
    # Remove leading/trailing separators
    text = text.strip(separator)
    
    # Remove duplicate separators
    text = re.sub(f"{separator}+", separator, text)
    
    return text


def truncate(
    text: str,
    length: int,
    suffix: str = "...",
    word_boundary: bool = True,
) -> str:
    """
    Truncate text to specified length.
    
    Args:
        text: Input text
        length: Maximum length
        suffix: Truncation indicator
        word_boundary: Break at word boundary
        
    Returns:
        Truncated text
    """
    if len(text) <= length:
        return text
    
    # Account for suffix length
    target_length = length - len(suffix)
    
    if word_boundary:
        # Find last space before target length
        truncated = text[:target_length]
        last_space = truncated.rfind(" ")
        
        if last_space > 0:
            truncated = truncated[:last_space]
        
        return truncated.rstrip() + suffix
    
    return text[:target_length] + suffix


def snake_case(text: str) -> str:
    """
    Convert text to snake_case.
    
    Example:
        >>> snake_case("HelloWorld")
        'hello_world'
    """
    # Insert underscore before uppercase letters
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", text)
    text = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", text)
    
    # Replace spaces and hyphens
    text = re.sub(r"[-\s]+", "_", text)
    
    return text.lower()


def camel_case(text: str) -> str:
    """
    Convert text to camelCase.
    
    Example:
        >>> camel_case("hello_world")
        'helloWorld'
    """
    # Split on non-alphanumeric
    parts = re.split(r"[_\-\s]+", text)
    
    if not parts:
        return ""
    
    # First part lowercase, rest capitalized
    return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])


def pascal_case(text: str) -> str:
    """
    Convert text to PascalCase.
    
    Example:
        >>> pascal_case("hello_world")
        'HelloWorld'
    """
    # Split on non-alphanumeric
    parts = re.split(r"[_\-\s]+", text)
    return "".join(p.capitalize() for p in parts)


def kebab_case(text: str) -> str:
    """
    Convert text to kebab-case.
    
    Example:
        >>> kebab_case("HelloWorld")
        'hello-world'
    """
    return snake_case(text).replace("_", "-")


def pluralize(word: str) -> str:
    """
    Simple English pluralization.
    
    Example:
        >>> pluralize("user")
        'users'
        >>> pluralize("category")
        'categories'
    """
    # Special cases
    irregulars = {
        "person": "people",
        "child": "children",
        "man": "men",
        "woman": "women",
        "foot": "feet",
        "tooth": "teeth",
        "mouse": "mice",
    }
    
    lower = word.lower()
    if lower in irregulars:
        return irregulars[lower]
    
    # Rules
    if word.endswith(("s", "x", "z", "ch", "sh")):
        return word + "es"
    elif word.endswith("y") and not word[-2:-1] in "aeiou":
        return word[:-1] + "ies"
    elif word.endswith("f"):
        return word[:-1] + "ves"
    elif word.endswith("fe"):
        return word[:-2] + "ves"
    else:
        return word + "s"


def singularize(word: str) -> str:
    """
    Simple English singularization.
    
    Example:
        >>> singularize("users")
        'user'
    """
    # Irregular plurals
    irregulars = {
        "people": "person",
        "children": "child",
        "men": "man",
        "women": "woman",
        "feet": "foot",
        "teeth": "tooth",
        "mice": "mouse",
    }
    
    lower = word.lower()
    if lower in irregulars:
        return irregulars[lower]
    
    # Rules
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    elif word.endswith("ves"):
        return word[:-3] + "f"
    elif word.endswith("es") and word[-4:-2] in ("ch", "sh", "ss", "zz"):
        return word[:-2]
    elif word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    
    return word


# =============================================================================
# Collection Helpers
# =============================================================================

def get_nested(
    obj: Union[Dict, List, Any],
    path: str,
    default: Any = None,
    separator: str = ".",
) -> Any:
    """
    Get nested value from dict/list using dot notation.
    
    Args:
        obj: Source object
        path: Dot-separated path
        default: Default if not found
        separator: Path separator
        
    Returns:
        Value at path or default
        
    Example:
        >>> get_nested({"a": {"b": 1}}, "a.b")
        1
    """
    keys = path.split(separator)
    current = obj
    
    for key in keys:
        try:
            if isinstance(current, dict):
                current = current[key]
            elif isinstance(current, (list, tuple)) and key.isdigit():
                current = current[int(key)]
            else:
                return default
        except (KeyError, IndexError, TypeError):
            return default
    
    return current


def set_nested(
    obj: Dict,
    path: str,
    value: Any,
    separator: str = ".",
) -> Dict:
    """
    Set nested value in dict using dot notation.
    
    Args:
        obj: Target dict
        path: Dot-separated path
        value: Value to set
        separator: Path separator
        
    Returns:
        Modified dict
        
    Example:
        >>> set_nested({}, "a.b.c", 1)
        {'a': {'b': {'c': 1}}}
    """
    keys = path.split(separator)
    current = obj
    
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    
    current[keys[-1]] = value
    return obj


def flatten(
    items: Iterable,
    depth: int = -1,
) -> List:
    """
    Flatten nested iterables.
    
    Args:
        items: Nested iterable
        depth: Max depth (-1 for unlimited)
        
    Returns:
        Flattened list
        
    Example:
        >>> flatten([[1, [2]], [3]])
        [1, 2, 3]
    """
    result = []
    
    for item in items:
        if (
            isinstance(item, (list, tuple)) and
            depth != 0
        ):
            result.extend(flatten(item, depth - 1 if depth > 0 else -1))
        else:
            result.append(item)
    
    return result


def unique(
    items: Iterable[T],
    key: Optional[Callable[[T], Any]] = None,
) -> List[T]:
    """
    Get unique items preserving order.
    
    Args:
        items: Input iterable
        key: Optional key function
        
    Returns:
        List of unique items
        
    Example:
        >>> unique([1, 2, 1, 3, 2])
        [1, 2, 3]
    """
    seen = set()
    result = []
    
    for item in items:
        k = key(item) if key else item
        if k not in seen:
            seen.add(k)
            result.append(item)
    
    return result


def chunk(
    items: List[T],
    size: int,
) -> List[List[T]]:
    """
    Split list into chunks.
    
    Args:
        items: Input list
        size: Chunk size
        
    Returns:
        List of chunks
        
    Example:
        >>> chunk([1, 2, 3, 4, 5], 2)
        [[1, 2], [3, 4], [5]]
    """
    return [items[i:i + size] for i in range(0, len(items), size)]


# =============================================================================
# Time Helpers
# =============================================================================

def now() -> datetime:
    """Get current UTC datetime."""
    return datetime.utcnow()


def timestamp() -> float:
    """Get current Unix timestamp."""
    return time.time()


def parse_date(
    text: str,
    formats: Optional[List[str]] = None,
) -> Optional[datetime]:
    """
    Parse date string.
    
    Args:
        text: Date string
        formats: List of formats to try
        
    Returns:
        Parsed datetime or None
    """
    if not formats:
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
        ]
    
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    
    return None


def format_date(
    dt: datetime,
    format: str = "%Y-%m-%d %H:%M:%S",
) -> str:
    """Format datetime to string."""
    return dt.strftime(format)


def time_ago(
    dt: datetime,
    now: Optional[datetime] = None,
) -> str:
    """
    Get human-readable relative time.
    
    Args:
        dt: Datetime to compare
        now: Current time (defaults to now)
        
    Returns:
        Relative time string
        
    Example:
        >>> time_ago(datetime.now() - timedelta(hours=2))
        '2 hours ago'
    """
    if now is None:
        now = datetime.utcnow()
    
    diff = now - dt
    seconds = diff.total_seconds()
    
    if seconds < 0:
        return "in the future"
    
    intervals = [
        (60, "second", "seconds"),
        (60, "minute", "minutes"),
        (24, "hour", "hours"),
        (30, "day", "days"),
        (12, "month", "months"),
        (None, "year", "years"),
    ]
    
    value = seconds
    unit = "seconds"
    unit_plural = "seconds"
    
    for divisor, singular, plural in intervals:
        if divisor is None or value < divisor:
            break
        value /= divisor
        unit = singular
        unit_plural = plural
    
    value = int(value)
    
    if value == 0:
        return "just now"
    elif value == 1:
        return f"1 {unit} ago"
    else:
        return f"{value} {unit_plural} ago"


# =============================================================================
# Function Helpers
# =============================================================================

def retry(
    attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Callable[[F], F]:
    """
    Retry decorator with exponential backoff.
    
    Args:
        attempts: Max retry attempts
        delay: Initial delay in seconds
        backoff: Backoff multiplier
        exceptions: Exceptions to catch
        
    Returns:
        Decorator
        
    Example:
        @retry(attempts=3, delay=1.0)
        async def fetch_data():
            ...
    """
    def decorator(func: F) -> F:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                current_delay = delay
                last_exception = None
                
                for attempt in range(attempts):
                    try:
                        return await func(*args, **kwargs)
                    except exceptions as e:
                        last_exception = e
                        if attempt < attempts - 1:
                            await asyncio.sleep(current_delay)
                            current_delay *= backoff
                
                raise last_exception
            
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                current_delay = delay
                last_exception = None
                
                for attempt in range(attempts):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        last_exception = e
                        if attempt < attempts - 1:
                            time.sleep(current_delay)
                            current_delay *= backoff
                
                raise last_exception
            
            return sync_wrapper
    
    return decorator


def memoize(
    maxsize: int = 128,
    ttl: Optional[float] = None,
) -> Callable[[F], F]:
    """
    Memoization decorator with optional TTL.
    
    Args:
        maxsize: Maximum cache size
        ttl: Time-to-live in seconds
        
    Returns:
        Decorator
    """
    def decorator(func: F) -> F:
        cache: Dict[str, tuple] = {}
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key
            key = str((args, tuple(sorted(kwargs.items()))))
            
            # Check cache
            if key in cache:
                value, timestamp = cache[key]
                if ttl is None or time.time() - timestamp < ttl:
                    return value
            
            # Call function
            result = func(*args, **kwargs)
            
            # Store in cache
            cache[key] = (result, time.time())
            
            # Evict if over maxsize
            if len(cache) > maxsize:
                oldest_key = min(cache, key=lambda k: cache[k][1])
                del cache[oldest_key]
            
            return result
        
        wrapper.cache = cache
        wrapper.clear = lambda: cache.clear()
        
        return wrapper
    
    return decorator


def debounce(
    wait: float,
) -> Callable[[F], F]:
    """
    Debounce decorator (delay execution until after wait period).
    
    Args:
        wait: Wait time in seconds
        
    Returns:
        Decorator
    """
    def decorator(func: F) -> F:
        timer = None
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal timer
            
            if timer:
                timer.cancel()
            
            def call():
                func(*args, **kwargs)
            
            timer = asyncio.get_event_loop().call_later(wait, call)
        
        return wrapper
    
    return decorator


def throttle(
    limit: float,
) -> Callable[[F], F]:
    """
    Throttle decorator (limit execution frequency).
    
    Args:
        limit: Minimum time between calls in seconds
        
    Returns:
        Decorator
    """
    def decorator(func: F) -> F:
        last_call = [0.0]
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_call[0]
            
            if elapsed < limit:
                return None
            
            last_call[0] = time.time()
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator
