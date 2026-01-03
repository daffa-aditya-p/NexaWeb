"""
NexaWeb Validator
=================

Core validation engine.

Validates data against rules and returns results
with detailed error messages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

from nexaweb.validation.rules import Nullable, Required, Rule


class ValidationError(Exception):
    """
    Validation failed exception.
    
    Contains all validation errors.
    """
    
    def __init__(
        self,
        message: str = "Validation failed",
        errors: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        super().__init__(message)
        self.errors = errors or {}
        
    def __str__(self) -> str:
        if self.errors:
            error_list = []
            for field_name, messages in self.errors.items():
                for msg in messages:
                    error_list.append(f"  - {field_name}: {msg}")
            return f"Validation failed:\n" + "\n".join(error_list)
        return "Validation failed"
        
    def first(self, field_name: Optional[str] = None) -> Optional[str]:
        """Get first error message."""
        if field_name:
            messages = self.errors.get(field_name, [])
            return messages[0] if messages else None
        else:
            for messages in self.errors.values():
                if messages:
                    return messages[0]
            return None


@dataclass
class ValidationResult:
    """
    Result of validation.
    
    Contains validated data and any errors.
    """
    
    valid: bool
    data: Dict[str, Any] = field(default_factory=dict)
    errors: Dict[str, List[str]] = field(default_factory=dict)
    
    def __bool__(self) -> bool:
        """Allow using result as boolean."""
        return self.valid
        
    def failed(self) -> bool:
        """Check if validation failed."""
        return not self.valid
        
    def has_error(self, field_name: str) -> bool:
        """Check if field has error."""
        return field_name in self.errors
        
    def get_errors(self, field_name: str) -> List[str]:
        """Get errors for field."""
        return self.errors.get(field_name, [])
        
    def first_error(self, field_name: Optional[str] = None) -> Optional[str]:
        """Get first error message."""
        if field_name:
            messages = self.errors.get(field_name, [])
            return messages[0] if messages else None
        else:
            for messages in self.errors.values():
                if messages:
                    return messages[0]
            return None
            
    def all_errors(self) -> List[str]:
        """Get all error messages as flat list."""
        all_msgs = []
        for messages in self.errors.values():
            all_msgs.extend(messages)
        return all_msgs
        
    def raise_if_invalid(self) -> None:
        """Raise ValidationError if invalid."""
        if not self.valid:
            raise ValidationError(errors=self.errors)


# Rule parsing types
RuleSpec = Union[str, Rule, List[Union[str, Rule]], Callable]


class Validator:
    """
    Main validation class.
    
    Validates data against a set of rules.
    
    Example:
        validator = Validator({
            "name": [Required(), MaxLength(100)],
            "email": [Required(), Email()],
            "age": [Integer(), Min(18)],
        })
        
        result = validator.validate({
            "name": "John",
            "email": "john@example.com",
            "age": 25,
        })
        
        if result.valid:
            print("Data is valid!")
        else:
            print(result.errors)
    """
    
    # Built-in rule aliases
    RULE_ALIASES: Dict[str, Callable[..., Rule]] = {}
    
    def __init__(
        self,
        rules: Dict[str, RuleSpec],
        messages: Optional[Dict[str, str]] = None,
        attributes: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Initialize validator.
        
        Args:
            rules: Validation rules per field
            messages: Custom error messages
            attributes: Custom field names for messages
        """
        self.rules = self._parse_rules(rules)
        self.messages = messages or {}
        self.attributes = attributes or {}
        self.database = None  # For async rules
        
    def _parse_rules(
        self,
        rules: Dict[str, RuleSpec],
    ) -> Dict[str, List[Rule]]:
        """Parse rule specifications into Rule objects."""
        parsed = {}
        
        for field_name, rule_spec in rules.items():
            parsed[field_name] = self._parse_rule_spec(rule_spec)
            
        return parsed
        
    def _parse_rule_spec(self, spec: RuleSpec) -> List[Rule]:
        """Parse a single rule specification."""
        if isinstance(spec, Rule):
            return [spec]
            
        if isinstance(spec, list):
            rules = []
            for item in spec:
                rules.extend(self._parse_rule_spec(item))
            return rules
            
        if isinstance(spec, str):
            return self._parse_string_rules(spec)
            
        if callable(spec):
            # Custom validation function
            return [CallableRule(spec)]
            
        return []
        
    def _parse_string_rules(self, rule_string: str) -> List[Rule]:
        """
        Parse pipe-separated rule string.
        
        Example: "required|email|max:255"
        """
        rules = []
        
        for part in rule_string.split("|"):
            part = part.strip()
            if not part:
                continue
                
            # Parse rule name and parameters
            if ":" in part:
                name, params_str = part.split(":", 1)
                params = params_str.split(",")
            else:
                name = part
                params = []
                
            # Look up rule alias
            rule = self._create_rule_from_name(name, params)
            if rule:
                rules.append(rule)
                
        return rules
        
    def _create_rule_from_name(
        self,
        name: str,
        params: List[str],
    ) -> Optional[Rule]:
        """Create rule from name and parameters."""
        from nexaweb.validation.rules import (
            Required, Email, Url, Min, Max, MinLength, MaxLength,
            Regex, In, NotIn, Numeric, Integer, Alpha, AlphaNumeric,
            Date, DateTime, Confirmed, Same, Different, UUID, JSON,
            Array, Boolean, Nullable,
        )
        
        # Built-in rules
        rule_map: Dict[str, Callable[..., Rule]] = {
            "required": lambda: Required(),
            "nullable": lambda: Nullable(),
            "email": lambda: Email(),
            "url": lambda: Url(),
            "min": lambda p: Min(min_value=float(p[0])),
            "max": lambda p: Max(max_value=float(p[0])),
            "min_length": lambda p: MinLength(length=int(p[0])),
            "max_length": lambda p: MaxLength(length=int(p[0])),
            "regex": lambda p: Regex(pattern=p[0]),
            "in": lambda p: In(allowed=p),
            "not_in": lambda p: NotIn(disallowed=p),
            "numeric": lambda: Numeric(),
            "integer": lambda: Integer(),
            "alpha": lambda: Alpha(),
            "alpha_numeric": lambda: AlphaNumeric(),
            "date": lambda: Date(),
            "datetime": lambda: DateTime(),
            "confirmed": lambda: Confirmed(),
            "same": lambda p: Same(other_field=p[0]),
            "different": lambda p: Different(other_field=p[0]),
            "uuid": lambda: UUID(),
            "json": lambda: JSON(),
            "array": lambda: Array(),
            "boolean": lambda: Boolean(),
        }
        
        # Add custom aliases
        rule_map.update(self.RULE_ALIASES)
        
        creator = rule_map.get(name.lower())
        if creator:
            try:
                if params:
                    return creator(params)
                else:
                    return creator()
            except (TypeError, ValueError, IndexError):
                pass
                
        return None
        
    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """
        Validate data synchronously.
        
        Args:
            data: Data to validate
            
        Returns:
            ValidationResult with errors
        """
        errors: Dict[str, List[str]] = {}
        validated: Dict[str, Any] = {}
        
        for field_name, rules in self.rules.items():
            value = self._get_value(data, field_name)
            field_errors = self._validate_field(
                value, field_name, rules, data
            )
            
            if field_errors:
                errors[field_name] = field_errors
            else:
                validated[field_name] = value
                
        return ValidationResult(
            valid=len(errors) == 0,
            data=validated,
            errors=errors,
        )
        
    async def validate_async(self, data: Dict[str, Any]) -> ValidationResult:
        """
        Validate data asynchronously.
        
        Supports database rules like Unique/Exists.
        
        Args:
            data: Data to validate
            
        Returns:
            ValidationResult with errors
        """
        errors: Dict[str, List[str]] = {}
        validated: Dict[str, Any] = {}
        
        for field_name, rules in self.rules.items():
            value = self._get_value(data, field_name)
            field_errors = await self._validate_field_async(
                value, field_name, rules, data
            )
            
            if field_errors:
                errors[field_name] = field_errors
            else:
                validated[field_name] = value
                
        return ValidationResult(
            valid=len(errors) == 0,
            data=validated,
            errors=errors,
        )
        
    def _get_value(self, data: Dict[str, Any], field: str) -> Any:
        """Get value from data, supporting dot notation."""
        if "." not in field:
            return data.get(field)
            
        parts = field.split(".")
        current = data
        
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list) and part.isdigit():
                idx = int(part)
                current = current[idx] if idx < len(current) else None
            else:
                return None
                
        return current
        
    def _validate_field(
        self,
        value: Any,
        field: str,
        rules: List[Rule],
        data: Dict[str, Any],
    ) -> List[str]:
        """Validate single field against rules."""
        errors = []
        
        # Check if nullable
        is_nullable = any(isinstance(r, Nullable) for r in rules)
        is_required = any(isinstance(r, Required) for r in rules)
        
        # Handle null values
        if value is None or (isinstance(value, str) and not value.strip()):
            if is_required:
                req_rule = next(r for r in rules if isinstance(r, Required))
                errors.append(self._get_message(field, req_rule))
            elif is_nullable:
                return []  # Skip remaining rules
            else:
                return []  # Field not present and not required
                
        # Validate against rules
        for rule in rules:
            if isinstance(rule, (Required, Nullable)):
                continue
                
            if not rule.validate(value, field, data):
                errors.append(self._get_message(field, rule))
                
        return errors
        
    async def _validate_field_async(
        self,
        value: Any,
        field: str,
        rules: List[Rule],
        data: Dict[str, Any],
    ) -> List[str]:
        """Validate single field against rules (async)."""
        # Run sync validation first
        errors = self._validate_field(value, field, rules, data)
        
        if errors:
            return errors
            
        # Run async rules
        for rule in rules:
            if hasattr(rule, "validate_async"):
                # Inject database
                if hasattr(rule, "database") and self.database:
                    rule.database = self.database
                    
                if not await rule.validate_async(value, field, data):
                    errors.append(self._get_message(field, rule))
                    
        return errors
        
    def _get_message(self, field: str, rule: Rule) -> str:
        """Get error message for rule."""
        # Check custom messages
        key = f"{field}.{rule.__class__.__name__.lower()}"
        if key in self.messages:
            return self.messages[key]
            
        # Use rule's message
        display_field = self.attributes.get(field, field.replace("_", " "))
        return rule.get_message(display_field)
        
    def with_database(self, database: Any) -> Validator:
        """Set database for async rules."""
        self.database = database
        return self


class CallableRule(Rule):
    """Rule wrapper for callable validators."""
    
    message = "The {field} is invalid"
    
    def __init__(self, func: Callable) -> None:
        self.func = func
        
    def validate(self, value: Any, field: str, data: Dict[str, Any]) -> bool:
        try:
            result = self.func(value, field, data)
            return bool(result)
        except Exception:
            return False


# Convenience functions

def validate(
    data: Dict[str, Any],
    rules: Dict[str, RuleSpec],
    messages: Optional[Dict[str, str]] = None,
) -> ValidationResult:
    """
    Validate data with rules.
    
    Convenience function that creates Validator and validates.
    
    Example:
        result = validate(
            {"email": "test@example.com"},
            {"email": [Required(), Email()]},
        )
    """
    validator = Validator(rules, messages)
    return validator.validate(data)


def validate_or_fail(
    data: Dict[str, Any],
    rules: Dict[str, RuleSpec],
    messages: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Validate data and raise on failure.
    
    Returns validated data if successful.
    Raises ValidationError if validation fails.
    
    Example:
        try:
            data = validate_or_fail(
                request.form,
                {"email": "required|email"},
            )
        except ValidationError as e:
            return {"errors": e.errors}
    """
    result = validate(data, rules, messages)
    
    if not result.valid:
        raise ValidationError(errors=result.errors)
        
    return result.data
