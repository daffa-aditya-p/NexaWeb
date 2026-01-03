"""
NexaWeb Validation Rules
========================

Collection of built-in validation rules.

Each rule implements the Rule interface and can be
composed to create complex validation logic.
"""

from __future__ import annotations

import json
import re
import uuid as uuid_module
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Pattern, Union


class Rule(ABC):
    """
    Abstract validation rule.
    
    Implement `validate` to create custom rules.
    
    Example:
        class IsPositive(Rule):
            message = "The {field} must be positive"
            
            def validate(self, value: Any, field: str, data: dict) -> bool:
                return isinstance(value, (int, float)) and value > 0
    """
    
    message: str = "The {field} is invalid"
    
    @abstractmethod
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        """
        Validate the value.
        
        Args:
            value: Value to validate
            field: Field name
            data: Full data being validated
            
        Returns:
            True if valid, False otherwise
        """
        ...
        
    def get_message(self, field: str, **params) -> str:
        """Get error message with parameters."""
        return self.message.format(field=field, **params)
        
    def __call__(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        """Allow rule to be called directly."""
        return self.validate(value, field, data)


@dataclass
class Required(Rule):
    """Require field to be present and not empty."""
    
    message: str = "The {field} field is required"
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        if value is None:
            return False
        if isinstance(value, str) and not value.strip():
            return False
        if isinstance(value, (list, dict)) and len(value) == 0:
            return False
        return True


@dataclass
class Nullable(Rule):
    """Allow field to be null (stops validation if null)."""
    
    message: str = ""
    stop_on_null: bool = True
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        return True  # Always passes


@dataclass
class Email(Rule):
    """Validate email format."""
    
    message: str = "The {field} must be a valid email address"
    
    _pattern: Pattern = re.compile(
        r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    )
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        if not isinstance(value, str):
            return False
        return bool(self._pattern.match(value))


@dataclass
class Url(Rule):
    """Validate URL format."""
    
    message: str = "The {field} must be a valid URL"
    require_tld: bool = True
    
    _pattern: Pattern = re.compile(
        r"^https?://"
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
        r"localhost|"
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        r"(?::\d+)?"
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        if not isinstance(value, str):
            return False
        return bool(self._pattern.match(value))


@dataclass
class Min(Rule):
    """Minimum value for numbers, length for strings/arrays."""
    
    min_value: Union[int, float]
    message: str = "The {field} must be at least {min}"
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        if isinstance(value, (int, float)):
            return value >= self.min_value
        if isinstance(value, (str, list, dict)):
            return len(value) >= self.min_value
        return False
        
    def get_message(self, field: str, **params) -> str:
        return self.message.format(field=field, min=self.min_value)


@dataclass
class Max(Rule):
    """Maximum value for numbers, length for strings/arrays."""
    
    max_value: Union[int, float]
    message: str = "The {field} must not exceed {max}"
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        if isinstance(value, (int, float)):
            return value <= self.max_value
        if isinstance(value, (str, list, dict)):
            return len(value) <= self.max_value
        return False
        
    def get_message(self, field: str, **params) -> str:
        return self.message.format(field=field, max=self.max_value)


@dataclass
class MinLength(Rule):
    """Minimum string length."""
    
    length: int
    message: str = "The {field} must be at least {length} characters"
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        if not isinstance(value, str):
            return False
        return len(value) >= self.length
        
    def get_message(self, field: str, **params) -> str:
        return self.message.format(field=field, length=self.length)


@dataclass
class MaxLength(Rule):
    """Maximum string length."""
    
    length: int
    message: str = "The {field} must not exceed {length} characters"
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        if not isinstance(value, str):
            return False
        return len(value) <= self.length
        
    def get_message(self, field: str, **params) -> str:
        return self.message.format(field=field, length=self.length)


@dataclass
class Length(Rule):
    """Exact length or range."""
    
    min_length: int
    max_length: Optional[int] = None
    message: str = "The {field} must be between {min} and {max} characters"
    
    def __post_init__(self):
        if self.max_length is None:
            self.max_length = self.min_length
            self.message = "The {field} must be exactly {min} characters"
            
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        if not isinstance(value, str):
            return False
        length = len(value)
        return self.min_length <= length <= self.max_length
        
    def get_message(self, field: str, **params) -> str:
        return self.message.format(
            field=field,
            min=self.min_length,
            max=self.max_length,
        )


@dataclass
class Regex(Rule):
    """Match regular expression."""
    
    pattern: Union[str, Pattern]
    message: str = "The {field} format is invalid"
    
    def __post_init__(self):
        if isinstance(self.pattern, str):
            self.pattern = re.compile(self.pattern)
            
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        if not isinstance(value, str):
            return False
        return bool(self.pattern.match(value))


@dataclass
class In(Rule):
    """Value must be in allowed list."""
    
    allowed: List[Any]
    message: str = "The selected {field} is invalid"
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        return value in self.allowed


@dataclass
class NotIn(Rule):
    """Value must not be in disallowed list."""
    
    disallowed: List[Any]
    message: str = "The selected {field} is invalid"
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        return value not in self.disallowed


@dataclass
class Numeric(Rule):
    """Value must be numeric."""
    
    message: str = "The {field} must be a number"
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        if isinstance(value, (int, float)):
            return True
        if isinstance(value, str):
            try:
                float(value)
                return True
            except ValueError:
                return False
        return False


@dataclass
class Integer(Rule):
    """Value must be an integer."""
    
    message: str = "The {field} must be an integer"
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        if isinstance(value, bool):
            return False
        if isinstance(value, int):
            return True
        if isinstance(value, str):
            try:
                int(value)
                return True
            except ValueError:
                return False
        return False


@dataclass
class Alpha(Rule):
    """Value must contain only letters."""
    
    message: str = "The {field} must only contain letters"
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        if not isinstance(value, str):
            return False
        return value.isalpha()


@dataclass
class AlphaNumeric(Rule):
    """Value must contain only letters and numbers."""
    
    message: str = "The {field} must only contain letters and numbers"
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        if not isinstance(value, str):
            return False
        return value.isalnum()


@dataclass
class Date(Rule):
    """Value must be a valid date."""
    
    format: str = "%Y-%m-%d"
    message: str = "The {field} is not a valid date"
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        if isinstance(value, date):
            return True
        if isinstance(value, str):
            try:
                datetime.strptime(value, self.format)
                return True
            except ValueError:
                return False
        return False


@dataclass
class DateTime(Rule):
    """Value must be a valid datetime."""
    
    format: str = "%Y-%m-%d %H:%M:%S"
    message: str = "The {field} is not a valid datetime"
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        if isinstance(value, datetime):
            return True
        if isinstance(value, str):
            try:
                datetime.strptime(value, self.format)
                return True
            except ValueError:
                return False
        return False


@dataclass
class Before(Rule):
    """Date must be before another date."""
    
    date: Union[str, date, datetime]
    message: str = "The {field} must be before {date}"
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        try:
            if isinstance(value, str):
                value = datetime.strptime(value, "%Y-%m-%d").date()
            if isinstance(self.date, str):
                compare = datetime.strptime(self.date, "%Y-%m-%d").date()
            else:
                compare = self.date
                
            if isinstance(value, datetime):
                value = value.date()
            if isinstance(compare, datetime):
                compare = compare.date()
                
            return value < compare
        except (ValueError, TypeError):
            return False
            
    def get_message(self, field: str, **params) -> str:
        return self.message.format(field=field, date=self.date)


@dataclass
class After(Rule):
    """Date must be after another date."""
    
    date: Union[str, date, datetime]
    message: str = "The {field} must be after {date}"
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        try:
            if isinstance(value, str):
                value = datetime.strptime(value, "%Y-%m-%d").date()
            if isinstance(self.date, str):
                compare = datetime.strptime(self.date, "%Y-%m-%d").date()
            else:
                compare = self.date
                
            if isinstance(value, datetime):
                value = value.date()
            if isinstance(compare, datetime):
                compare = compare.date()
                
            return value > compare
        except (ValueError, TypeError):
            return False
            
    def get_message(self, field: str, **params) -> str:
        return self.message.format(field=field, date=self.date)


@dataclass
class Confirmed(Rule):
    """Value must match {field}_confirmation."""
    
    message: str = "The {field} confirmation does not match"
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        confirmation = data.get(f"{field}_confirmation")
        return value == confirmation


@dataclass
class Same(Rule):
    """Value must match another field."""
    
    other_field: str
    message: str = "The {field} must match {other}"
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        return value == data.get(self.other_field)
        
    def get_message(self, field: str, **params) -> str:
        return self.message.format(field=field, other=self.other_field)


@dataclass
class Different(Rule):
    """Value must be different from another field."""
    
    other_field: str
    message: str = "The {field} must be different from {other}"
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        return value != data.get(self.other_field)
        
    def get_message(self, field: str, **params) -> str:
        return self.message.format(field=field, other=self.other_field)


@dataclass
class Unique(Rule):
    """
    Value must be unique in database.
    
    Requires async validation context.
    """
    
    table: str
    column: Optional[str] = None
    ignore_id: Optional[Any] = None
    message: str = "The {field} has already been taken"
    
    # Database will be injected by validator
    database: Any = None
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        # Synchronous check - always passes
        # Real check is done in async validator
        return True
        
    async def validate_async(
        self,
        value: Any,
        field: str,
        data: Dict[str, Any],
    ) -> bool:
        """Async database validation."""
        if not self.database:
            return True
            
        column = self.column or field
        query = f"SELECT COUNT(*) as count FROM {self.table} WHERE {column} = ?"
        params = [value]
        
        if self.ignore_id:
            query += " AND id != ?"
            params.append(self.ignore_id)
            
        result = await self.database.fetch_one(query, params)
        return result["count"] == 0 if result else True


@dataclass
class Exists(Rule):
    """
    Value must exist in database.
    
    Requires async validation context.
    """
    
    table: str
    column: Optional[str] = None
    message: str = "The selected {field} is invalid"
    
    database: Any = None
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        return True
        
    async def validate_async(
        self,
        value: Any,
        field: str,
        data: Dict[str, Any],
    ) -> bool:
        """Async database validation."""
        if not self.database:
            return True
            
        column = self.column or field
        query = f"SELECT COUNT(*) as count FROM {self.table} WHERE {column} = ?"
        
        result = await self.database.fetch_one(query, [value])
        return result["count"] > 0 if result else False


@dataclass
class File(Rule):
    """Value must be a file upload."""
    
    message: str = "The {field} must be a file"
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        return hasattr(value, "filename") and hasattr(value, "read")


@dataclass
class Image(Rule):
    """Value must be an image file."""
    
    message: str = "The {field} must be an image"
    allowed_types: List[str] = None
    
    def __post_init__(self):
        if self.allowed_types is None:
            self.allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
            
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        if not hasattr(value, "content_type"):
            return False
        return value.content_type in self.allowed_types


@dataclass
class Mimes(Rule):
    """Value must have allowed MIME type."""
    
    allowed: List[str]
    message: str = "The {field} must be a file of type: {types}"
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        if not hasattr(value, "content_type"):
            return False
        return value.content_type in self.allowed
        
    def get_message(self, field: str, **params) -> str:
        return self.message.format(field=field, types=", ".join(self.allowed))


@dataclass
class MaxFileSize(Rule):
    """File must not exceed size limit."""
    
    max_bytes: int
    message: str = "The {field} must not be larger than {size}"
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        if hasattr(value, "size"):
            return value.size <= self.max_bytes
        if hasattr(value, "read"):
            content = value.read()
            value.seek(0)  # Reset file pointer
            return len(content) <= self.max_bytes
        return False
        
    def get_message(self, field: str, **params) -> str:
        # Format size
        size = self.max_bytes
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return self.message.format(field=field, size=f"{size:.1f}{unit}")
            size /= 1024
        return self.message.format(field=field, size=f"{size:.1f}TB")


@dataclass
class UUID(Rule):
    """Value must be a valid UUID."""
    
    message: str = "The {field} must be a valid UUID"
    version: Optional[int] = None
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        try:
            parsed = uuid_module.UUID(str(value))
            if self.version:
                return parsed.version == self.version
            return True
        except (ValueError, AttributeError):
            return False


@dataclass
class JSON(Rule):
    """Value must be valid JSON."""
    
    message: str = "The {field} must be valid JSON"
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        if isinstance(value, (dict, list)):
            return True
        if isinstance(value, str):
            try:
                json.loads(value)
                return True
            except json.JSONDecodeError:
                return False
        return False


@dataclass
class Array(Rule):
    """Value must be an array/list."""
    
    message: str = "The {field} must be an array"
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        return isinstance(value, list)


@dataclass
class Boolean(Rule):
    """Value must be a boolean."""
    
    message: str = "The {field} must be true or false"
    
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        return value in [True, False, 1, 0, "1", "0", "true", "false", "yes", "no"]


# Rule factory functions

def required() -> Required:
    """Create Required rule."""
    return Required()


def email() -> Email:
    """Create Email rule."""
    return Email()


def url() -> Url:
    """Create URL rule."""
    return Url()


def min_value(value: Union[int, float]) -> Min:
    """Create Min rule."""
    return Min(min_value=value)


def max_value(value: Union[int, float]) -> Max:
    """Create Max rule."""
    return Max(max_value=value)


def between(min_val: Union[int, float], max_val: Union[int, float]) -> List[Rule]:
    """Create Min and Max rules."""
    return [Min(min_value=min_val), Max(max_value=max_val)]


def length(min_len: int, max_len: Optional[int] = None) -> Length:
    """Create Length rule."""
    return Length(min_length=min_len, max_length=max_len)


def regex(pattern: str) -> Regex:
    """Create Regex rule."""
    return Regex(pattern=pattern)


def in_list(values: List[Any]) -> In:
    """Create In rule."""
    return In(allowed=values)
