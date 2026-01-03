"""
NexaWeb Input Sanitizer
=======================

Comprehensive input sanitization for:
- String sanitization
- Numeric validation
- Email validation
- File upload validation
- SQL parameter escaping

Provides defense-in-depth by sanitizing all user input
before processing or storage.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Union


@dataclass
class SanitizerConfig:
    """Sanitizer configuration."""
    
    # Maximum string length
    max_string_length: int = 10000
    
    # Allowed characters (regex pattern)
    allowed_chars: str = r"[\w\s\-_.,!?@#$%^&*()+=\[\]{}|\\:;\"'<>/`~]"
    
    # Strip null bytes
    strip_null_bytes: bool = True
    
    # Normalize unicode
    normalize_unicode: bool = True
    
    # Unicode normalization form
    unicode_form: str = "NFKC"
    
    # Strip control characters
    strip_control_chars: bool = True
    
    # Trim whitespace
    trim_whitespace: bool = True
    
    # Collapse multiple whitespace
    collapse_whitespace: bool = True


class Sanitizer:
    """
    Input sanitizer for cleaning and validating user input.
    
    Example:
        sanitizer = Sanitizer()
        
        # Clean string input
        clean_name = sanitizer.string(user_input)
        
        # Validate email
        email = sanitizer.email(email_input)
        if email is None:
            raise ValueError("Invalid email")
            
        # Clean and validate integer
        age = sanitizer.integer(age_input, min_val=0, max_val=150)
    """
    
    # Common patterns
    EMAIL_PATTERN = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    
    URL_PATTERN = re.compile(
        r'^https?://[^\s<>"{}|\\^`\[\]]+$'
    )
    
    SLUG_PATTERN = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
    
    USERNAME_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]{2,30}$')
    
    PHONE_PATTERN = re.compile(r'^\+?[\d\s\-()]{7,20}$')
    
    # Control characters to strip
    CONTROL_CHARS = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
    
    def __init__(self, config: Optional[SanitizerConfig] = None) -> None:
        """Initialize sanitizer."""
        self.config = config or SanitizerConfig()
        
    def string(
        self,
        value: Any,
        max_length: Optional[int] = None,
        strip: bool = True,
        normalize: bool = True,
    ) -> str:
        """
        Sanitize string input.
        
        Args:
            value: Input value
            max_length: Maximum allowed length
            strip: Whether to strip whitespace
            normalize: Whether to normalize unicode
            
        Returns:
            Sanitized string
        """
        if value is None:
            return ""
            
        # Convert to string
        result = str(value)
        
        # Strip null bytes
        if self.config.strip_null_bytes:
            result = result.replace("\x00", "")
            
        # Strip control characters
        if self.config.strip_control_chars:
            result = self.CONTROL_CHARS.sub("", result)
            
        # Normalize unicode
        if normalize and self.config.normalize_unicode:
            result = unicodedata.normalize(self.config.unicode_form, result)
            
        # Trim whitespace
        if strip and self.config.trim_whitespace:
            result = result.strip()
            
        # Collapse whitespace
        if self.config.collapse_whitespace:
            result = re.sub(r'\s+', ' ', result)
            
        # Enforce max length
        max_len = max_length or self.config.max_string_length
        if len(result) > max_len:
            result = result[:max_len]
            
        return result
        
    def integer(
        self,
        value: Any,
        default: int = 0,
        min_val: Optional[int] = None,
        max_val: Optional[int] = None,
    ) -> int:
        """
        Sanitize and validate integer input.
        
        Args:
            value: Input value
            default: Default if invalid
            min_val: Minimum allowed value
            max_val: Maximum allowed value
            
        Returns:
            Validated integer
        """
        try:
            result = int(value)
            
            if min_val is not None and result < min_val:
                result = min_val
            if max_val is not None and result > max_val:
                result = max_val
                
            return result
            
        except (TypeError, ValueError):
            return default
            
    def float_num(
        self,
        value: Any,
        default: float = 0.0,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None,
        precision: Optional[int] = None,
    ) -> float:
        """
        Sanitize and validate float input.
        
        Args:
            value: Input value
            default: Default if invalid
            min_val: Minimum allowed value
            max_val: Maximum allowed value
            precision: Decimal places to round to
            
        Returns:
            Validated float
        """
        try:
            result = float(value)
            
            # Check for infinity/nan
            if not (-1e308 < result < 1e308):
                return default
                
            if min_val is not None and result < min_val:
                result = min_val
            if max_val is not None and result > max_val:
                result = max_val
                
            if precision is not None:
                result = round(result, precision)
                
            return result
            
        except (TypeError, ValueError):
            return default
            
    def boolean(
        self,
        value: Any,
        default: bool = False,
    ) -> bool:
        """
        Sanitize boolean input.
        
        Args:
            value: Input value
            default: Default if ambiguous
            
        Returns:
            Boolean value
        """
        if isinstance(value, bool):
            return value
            
        if isinstance(value, str):
            lower = value.lower().strip()
            if lower in ("true", "yes", "1", "on", "enabled"):
                return True
            if lower in ("false", "no", "0", "off", "disabled"):
                return False
                
        if isinstance(value, (int, float)):
            return bool(value)
            
        return default
        
    def email(
        self,
        value: Any,
        allow_empty: bool = False,
    ) -> Optional[str]:
        """
        Sanitize and validate email address.
        
        Args:
            value: Input value
            allow_empty: Whether empty is valid
            
        Returns:
            Valid email or None
        """
        if value is None or value == "":
            return "" if allow_empty else None
            
        email = self.string(value).lower()
        
        if not self.EMAIL_PATTERN.match(email):
            return None
            
        # Additional validation
        if ".." in email:
            return None
        if email.startswith(".") or email.endswith("."):
            return None
            
        return email
        
    def url(
        self,
        value: Any,
        require_https: bool = False,
        allow_empty: bool = False,
    ) -> Optional[str]:
        """
        Sanitize and validate URL.
        
        Args:
            value: Input value
            require_https: Whether to require HTTPS
            allow_empty: Whether empty is valid
            
        Returns:
            Valid URL or None
        """
        if value is None or value == "":
            return "" if allow_empty else None
            
        url = self.string(value)
        
        if require_https and not url.startswith("https://"):
            return None
            
        if not self.URL_PATTERN.match(url):
            return None
            
        return url
        
    def slug(
        self,
        value: Any,
        allow_empty: bool = False,
    ) -> Optional[str]:
        """
        Sanitize and validate URL slug.
        
        Args:
            value: Input value
            allow_empty: Whether empty is valid
            
        Returns:
            Valid slug or None
        """
        if value is None or value == "":
            return "" if allow_empty else None
            
        slug = self.string(value).lower()
        
        if not self.SLUG_PATTERN.match(slug):
            return None
            
        return slug
        
    def username(
        self,
        value: Any,
    ) -> Optional[str]:
        """
        Sanitize and validate username.
        
        Args:
            value: Input value
            
        Returns:
            Valid username or None
        """
        if value is None or value == "":
            return None
            
        username = self.string(value)
        
        if not self.USERNAME_PATTERN.match(username):
            return None
            
        return username
        
    def phone(
        self,
        value: Any,
        allow_empty: bool = False,
    ) -> Optional[str]:
        """
        Sanitize and validate phone number.
        
        Args:
            value: Input value
            allow_empty: Whether empty is valid
            
        Returns:
            Valid phone or None
        """
        if value is None or value == "":
            return "" if allow_empty else None
            
        # Remove common formatting
        phone = re.sub(r'[\s\-().]', '', str(value))
        
        # Validate format
        if not re.match(r'^\+?\d{7,15}$', phone):
            return None
            
        return phone
        
    def filename(
        self,
        value: Any,
        allowed_extensions: Optional[Set[str]] = None,
    ) -> Optional[str]:
        """
        Sanitize and validate filename.
        
        Args:
            value: Input value
            allowed_extensions: Set of allowed extensions
            
        Returns:
            Safe filename or None
        """
        if value is None or value == "":
            return None
            
        filename = self.string(value)
        
        # Remove directory traversal
        filename = filename.replace("..", "")
        filename = filename.replace("/", "")
        filename = filename.replace("\\", "")
        
        # Remove dangerous characters
        filename = re.sub(r'[<>:"|?*\x00-\x1f]', '', filename)
        
        if not filename:
            return None
            
        # Check extension
        if allowed_extensions:
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            if ext not in allowed_extensions:
                return None
                
        return filename
        
    def array(
        self,
        value: Any,
        item_sanitizer: Optional[Callable] = None,
        max_items: int = 1000,
    ) -> List[Any]:
        """
        Sanitize array/list input.
        
        Args:
            value: Input value
            item_sanitizer: Function to sanitize each item
            max_items: Maximum number of items
            
        Returns:
            Sanitized list
        """
        if value is None:
            return []
            
        if isinstance(value, str):
            # Try to parse as comma-separated
            items = [v.strip() for v in value.split(",")]
        elif isinstance(value, (list, tuple)):
            items = list(value)
        else:
            items = [value]
            
        # Limit items
        items = items[:max_items]
        
        # Sanitize items
        if item_sanitizer:
            items = [item_sanitizer(item) for item in items]
            
        return items
        
    def dict_input(
        self,
        value: Any,
        allowed_keys: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """
        Sanitize dictionary input.
        
        Args:
            value: Input value
            allowed_keys: Set of allowed keys
            
        Returns:
            Sanitized dictionary
        """
        if not isinstance(value, dict):
            return {}
            
        result = {}
        for key, val in value.items():
            # Sanitize key
            clean_key = self.string(str(key), max_length=100)
            
            if not clean_key:
                continue
                
            # Check allowed keys
            if allowed_keys and clean_key not in allowed_keys:
                continue
                
            result[clean_key] = val
            
        return result
        
    def sql_identifier(self, value: str) -> Optional[str]:
        """
        Sanitize SQL identifier (table/column name).
        
        Args:
            value: Input value
            
        Returns:
            Safe identifier or None
        """
        if not value:
            return None
            
        # Only allow alphanumeric and underscore
        clean = re.sub(r'[^a-zA-Z0-9_]', '', value)
        
        # Must start with letter or underscore
        if not re.match(r'^[a-zA-Z_]', clean):
            return None
            
        # Limit length
        return clean[:64]


# Global sanitizer instance
_sanitizer = Sanitizer()


def sanitize(value: Any, **kwargs) -> str:
    """Sanitize string input (global function)."""
    return _sanitizer.string(value, **kwargs)


def sanitize_int(value: Any, **kwargs) -> int:
    """Sanitize integer input (global function)."""
    return _sanitizer.integer(value, **kwargs)


def sanitize_float(value: Any, **kwargs) -> float:
    """Sanitize float input (global function)."""
    return _sanitizer.float_num(value, **kwargs)


def sanitize_email(value: Any, **kwargs) -> Optional[str]:
    """Sanitize email input (global function)."""
    return _sanitizer.email(value, **kwargs)


def sanitize_url(value: Any, **kwargs) -> Optional[str]:
    """Sanitize URL input (global function)."""
    return _sanitizer.url(value, **kwargs)


def get_sanitizer() -> Sanitizer:
    """Get global sanitizer instance."""
    return _sanitizer
