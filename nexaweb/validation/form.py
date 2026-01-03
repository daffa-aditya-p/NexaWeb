"""
NexaWeb Form Validation
=======================

Form helpers and form classes for web forms.

Features:
- Form class definition
- Field types with validation
- CSRF integration
- Request binding
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type, Union

from nexaweb.validation.rules import Required, Rule
from nexaweb.validation.validator import ValidationResult, Validator


@dataclass
class FormField:
    """
    Form field definition.
    
    Defines a field with validation rules and HTML attributes.
    
    Example:
        email = FormField(
            rules=[Required(), Email()],
            label="Email Address",
            placeholder="Enter your email",
        )
    """
    
    rules: List[Rule] = field(default_factory=list)
    label: str = ""
    placeholder: str = ""
    help_text: str = ""
    default: Any = None
    required: bool = False
    disabled: bool = False
    readonly: bool = False
    html_type: str = "text"
    html_attrs: Dict[str, Any] = field(default_factory=dict)
    
    # Current value and error
    value: Any = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.required and not any(isinstance(r, Required) for r in self.rules):
            self.rules.insert(0, Required())
            
    def get_html_attrs(self) -> Dict[str, Any]:
        """Get all HTML attributes."""
        attrs = dict(self.html_attrs)
        
        if self.placeholder:
            attrs["placeholder"] = self.placeholder
        if self.required:
            attrs["required"] = True
        if self.disabled:
            attrs["disabled"] = True
        if self.readonly:
            attrs["readonly"] = True
            
        return attrs
        
    def render_attrs(self) -> str:
        """Render HTML attributes as string."""
        attrs = self.get_html_attrs()
        parts = []
        
        for key, value in attrs.items():
            if value is True:
                parts.append(key)
            elif value is not False and value is not None:
                parts.append(f'{key}="{value}"')
                
        return " ".join(parts)


class FormMeta(type):
    """Metaclass for Form to collect field definitions."""
    
    def __new__(
        mcs,
        name: str,
        bases: tuple,
        namespace: dict,
    ) -> FormMeta:
        # Collect fields
        fields: Dict[str, FormField] = {}
        
        # Get fields from base classes
        for base in bases:
            if hasattr(base, "_fields"):
                fields.update(base._fields)
                
        # Get fields from current class
        for key, value in list(namespace.items()):
            if isinstance(value, FormField):
                if not value.label:
                    value.label = key.replace("_", " ").title()
                fields[key] = value
                
        namespace["_fields"] = fields
        
        return super().__new__(mcs, name, bases, namespace)


class Form(metaclass=FormMeta):
    """
    Base form class.
    
    Define fields as class attributes with FormField instances.
    
    Example:
        class LoginForm(Form):
            email = FormField(
                rules=[Required(), Email()],
                label="Email",
            )
            password = FormField(
                rules=[Required(), MinLength(8)],
                label="Password",
                html_type="password",
            )
            remember = FormField(
                html_type="checkbox",
                label="Remember me",
            )
            
        # Usage
        form = LoginForm()
        
        if request.method == "POST":
            form.bind(request.form)
            
            if form.validate():
                email = form.data["email"]
                password = form.data["password"]
    """
    
    _fields: Dict[str, FormField]
    
    def __init__(
        self,
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        """
        Initialize form.
        
        Args:
            data: Initial data to bind
            **kwargs: Additional field values
        """
        self._data: Dict[str, Any] = {}
        self._errors: Dict[str, List[str]] = {}
        self._validated = False
        
        # Create field copies
        self.fields: Dict[str, FormField] = {}
        for name, field_def in self._fields.items():
            field = FormField(
                rules=list(field_def.rules),
                label=field_def.label,
                placeholder=field_def.placeholder,
                help_text=field_def.help_text,
                default=field_def.default,
                required=field_def.required,
                disabled=field_def.disabled,
                readonly=field_def.readonly,
                html_type=field_def.html_type,
                html_attrs=dict(field_def.html_attrs),
            )
            self.fields[name] = field
            
        # Bind initial data
        if data:
            self.bind(data)
        if kwargs:
            self.bind(kwargs)
            
    def bind(self, data: Dict[str, Any]) -> Form:
        """
        Bind data to form.
        
        Args:
            data: Data dictionary
            
        Returns:
            Self for chaining
        """
        for name, field in self.fields.items():
            if name in data:
                field.value = data[name]
                self._data[name] = data[name]
            elif field.default is not None:
                field.value = field.default
                self._data[name] = field.default
                
        self._validated = False
        return self
        
    def validate(self) -> bool:
        """
        Validate form data.
        
        Returns:
            True if valid
        """
        # Build validation rules
        rules = {}
        for name, field in self.fields.items():
            if field.rules:
                rules[name] = field.rules
                
        # Validate
        validator = Validator(rules)
        result = validator.validate(self._data)
        
        # Store errors
        self._errors = result.errors
        self._validated = True
        
        # Update field errors
        for name, field in self.fields.items():
            errors = self._errors.get(name, [])
            field.error = errors[0] if errors else None
            
        return result.valid
        
    @property
    def is_valid(self) -> bool:
        """Check if form is valid (requires validate() call)."""
        if not self._validated:
            return self.validate()
        return len(self._errors) == 0
        
    @property
    def errors(self) -> Dict[str, List[str]]:
        """Get all validation errors."""
        return self._errors
        
    @property
    def data(self) -> Dict[str, Any]:
        """Get form data."""
        return self._data
        
    def __getitem__(self, name: str) -> Any:
        """Get field value."""
        return self._data.get(name)
        
    def __setitem__(self, name: str, value: Any) -> None:
        """Set field value."""
        self._data[name] = value
        if name in self.fields:
            self.fields[name].value = value
            
    def __contains__(self, name: str) -> bool:
        """Check if field exists."""
        return name in self.fields
        
    def get(self, name: str, default: Any = None) -> Any:
        """Get field value with default."""
        return self._data.get(name, default)
        
    def has_error(self, name: str) -> bool:
        """Check if field has error."""
        return name in self._errors
        
    def get_error(self, name: str) -> Optional[str]:
        """Get first error for field."""
        errors = self._errors.get(name, [])
        return errors[0] if errors else None


class FormValidator:
    """
    Form-based validator.
    
    Alternative to Form class for simpler use cases.
    
    Example:
        validator = FormValidator()
        
        validator.field("email") \\
            .required() \\
            .email() \\
            .label("Email Address")
            
        validator.field("password") \\
            .required() \\
            .min_length(8) \\
            .label("Password")
            
        result = validator.validate(data)
    """
    
    def __init__(self) -> None:
        self._fields: Dict[str, FieldBuilder] = {}
        self._messages: Dict[str, str] = {}
        self._attributes: Dict[str, str] = {}
        
    def field(self, name: str) -> FieldBuilder:
        """
        Define a field.
        
        Returns FieldBuilder for chaining rules.
        """
        builder = FieldBuilder(name, self)
        self._fields[name] = builder
        return builder
        
    def message(self, key: str, message: str) -> FormValidator:
        """Set custom error message."""
        self._messages[key] = message
        return self
        
    def attribute(self, field: str, label: str) -> FormValidator:
        """Set field display name."""
        self._attributes[field] = label
        return self
        
    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate data."""
        rules = {}
        for name, builder in self._fields.items():
            rules[name] = builder._rules
            if builder._label:
                self._attributes[name] = builder._label
                
        validator = Validator(rules, self._messages, self._attributes)
        return validator.validate(data)
        
    async def validate_async(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate data asynchronously."""
        rules = {}
        for name, builder in self._fields.items():
            rules[name] = builder._rules
            if builder._label:
                self._attributes[name] = builder._label
                
        validator = Validator(rules, self._messages, self._attributes)
        return await validator.validate_async(data)


class FieldBuilder:
    """Builder for field validation rules."""
    
    def __init__(self, name: str, form: FormValidator) -> None:
        self.name = name
        self.form = form
        self._rules: List[Rule] = []
        self._label: Optional[str] = None
        
    def rule(self, rule: Rule) -> FieldBuilder:
        """Add custom rule."""
        self._rules.append(rule)
        return self
        
    def label(self, label: str) -> FieldBuilder:
        """Set field label."""
        self._label = label
        return self
        
    def required(self) -> FieldBuilder:
        """Add required rule."""
        from nexaweb.validation.rules import Required
        self._rules.append(Required())
        return self
        
    def nullable(self) -> FieldBuilder:
        """Allow null values."""
        from nexaweb.validation.rules import Nullable
        self._rules.append(Nullable())
        return self
        
    def email(self) -> FieldBuilder:
        """Add email rule."""
        from nexaweb.validation.rules import Email
        self._rules.append(Email())
        return self
        
    def url(self) -> FieldBuilder:
        """Add URL rule."""
        from nexaweb.validation.rules import Url
        self._rules.append(Url())
        return self
        
    def min(self, value: Union[int, float]) -> FieldBuilder:
        """Add min value rule."""
        from nexaweb.validation.rules import Min
        self._rules.append(Min(min_value=value))
        return self
        
    def max(self, value: Union[int, float]) -> FieldBuilder:
        """Add max value rule."""
        from nexaweb.validation.rules import Max
        self._rules.append(Max(max_value=value))
        return self
        
    def min_length(self, length: int) -> FieldBuilder:
        """Add min length rule."""
        from nexaweb.validation.rules import MinLength
        self._rules.append(MinLength(length=length))
        return self
        
    def max_length(self, length: int) -> FieldBuilder:
        """Add max length rule."""
        from nexaweb.validation.rules import MaxLength
        self._rules.append(MaxLength(length=length))
        return self
        
    def regex(self, pattern: str) -> FieldBuilder:
        """Add regex rule."""
        from nexaweb.validation.rules import Regex
        self._rules.append(Regex(pattern=pattern))
        return self
        
    def in_list(self, values: List[Any]) -> FieldBuilder:
        """Add in-list rule."""
        from nexaweb.validation.rules import In
        self._rules.append(In(allowed=values))
        return self
        
    def not_in(self, values: List[Any]) -> FieldBuilder:
        """Add not-in-list rule."""
        from nexaweb.validation.rules import NotIn
        self._rules.append(NotIn(disallowed=values))
        return self
        
    def numeric(self) -> FieldBuilder:
        """Add numeric rule."""
        from nexaweb.validation.rules import Numeric
        self._rules.append(Numeric())
        return self
        
    def integer(self) -> FieldBuilder:
        """Add integer rule."""
        from nexaweb.validation.rules import Integer
        self._rules.append(Integer())
        return self
        
    def alpha(self) -> FieldBuilder:
        """Add alpha rule."""
        from nexaweb.validation.rules import Alpha
        self._rules.append(Alpha())
        return self
        
    def alpha_numeric(self) -> FieldBuilder:
        """Add alphanumeric rule."""
        from nexaweb.validation.rules import AlphaNumeric
        self._rules.append(AlphaNumeric())
        return self
        
    def date(self, format: str = "%Y-%m-%d") -> FieldBuilder:
        """Add date rule."""
        from nexaweb.validation.rules import Date
        self._rules.append(Date(format=format))
        return self
        
    def datetime(self, format: str = "%Y-%m-%d %H:%M:%S") -> FieldBuilder:
        """Add datetime rule."""
        from nexaweb.validation.rules import DateTime
        self._rules.append(DateTime(format=format))
        return self
        
    def confirmed(self) -> FieldBuilder:
        """Add confirmed rule."""
        from nexaweb.validation.rules import Confirmed
        self._rules.append(Confirmed())
        return self
        
    def same(self, other_field: str) -> FieldBuilder:
        """Add same rule."""
        from nexaweb.validation.rules import Same
        self._rules.append(Same(other_field=other_field))
        return self
        
    def different(self, other_field: str) -> FieldBuilder:
        """Add different rule."""
        from nexaweb.validation.rules import Different
        self._rules.append(Different(other_field=other_field))
        return self
        
    def uuid(self) -> FieldBuilder:
        """Add UUID rule."""
        from nexaweb.validation.rules import UUID
        self._rules.append(UUID())
        return self
        
    def json(self) -> FieldBuilder:
        """Add JSON rule."""
        from nexaweb.validation.rules import JSON
        self._rules.append(JSON())
        return self
        
    def array(self) -> FieldBuilder:
        """Add array rule."""
        from nexaweb.validation.rules import Array
        self._rules.append(Array())
        return self
        
    def boolean(self) -> FieldBuilder:
        """Add boolean rule."""
        from nexaweb.validation.rules import Boolean
        self._rules.append(Boolean())
        return self
        
    def unique(self, table: str, column: Optional[str] = None) -> FieldBuilder:
        """Add unique rule."""
        from nexaweb.validation.rules import Unique
        self._rules.append(Unique(table=table, column=column))
        return self
        
    def exists(self, table: str, column: Optional[str] = None) -> FieldBuilder:
        """Add exists rule."""
        from nexaweb.validation.rules import Exists
        self._rules.append(Exists(table=table, column=column))
        return self
