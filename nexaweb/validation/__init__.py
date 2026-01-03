"""
NexaWeb Validation System
=========================

Comprehensive validation for request data, forms, and models.

Features:
- Rule-based validation
- Custom validators
- Nested data validation
- Error message formatting
- Form validation helpers
"""

from nexaweb.validation.validator import (
    Validator,
    ValidationError,
    ValidationResult,
    validate,
    validate_or_fail,
)
from nexaweb.validation.rules import (
    Rule,
    Required,
    Email,
    Url,
    Min,
    Max,
    MinLength,
    MaxLength,
    Length,
    Regex,
    In,
    NotIn,
    Numeric,
    Integer,
    Alpha,
    AlphaNumeric,
    Date,
    DateTime,
    Before,
    After,
    Confirmed,
    Same,
    Different,
    Unique,
    Exists,
    File,
    Image,
    Mimes,
    MaxFileSize,
    UUID,
    JSON,
    Array,
    Boolean,
    Nullable,
)
from nexaweb.validation.form import (
    FormValidator,
    FormField,
    Form,
)

__all__ = [
    # Core
    "Validator",
    "ValidationError",
    "ValidationResult",
    "validate",
    "validate_or_fail",
    # Rules
    "Rule",
    "Required",
    "Email",
    "Url",
    "Min",
    "Max",
    "MinLength",
    "MaxLength",
    "Length",
    "Regex",
    "In",
    "NotIn",
    "Numeric",
    "Integer",
    "Alpha",
    "AlphaNumeric",
    "Date",
    "DateTime",
    "Before",
    "After",
    "Confirmed",
    "Same",
    "Different",
    "Unique",
    "Exists",
    "File",
    "Image",
    "Mimes",
    "MaxFileSize",
    "UUID",
    "JSON",
    "Array",
    "Boolean",
    "Nullable",
    # Form
    "FormValidator",
    "FormField",
    "Form",
]
