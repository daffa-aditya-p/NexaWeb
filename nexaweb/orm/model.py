"""
NexaWeb ORM Model
=================

Active Record style model base class.

Features:
- Declarative field definitions
- Automatic table inference
- CRUD operations
- Relationships
- Soft deletes
- Timestamps
"""

from __future__ import annotations

import json
import re
from abc import ABC
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)

T = TypeVar("T", bound="Model")


class FieldType(Enum):
    """Database field types."""
    
    INTEGER = "INTEGER"
    BIGINT = "BIGINT"
    SMALLINT = "SMALLINT"
    STRING = "VARCHAR"
    TEXT = "TEXT"
    BOOLEAN = "BOOLEAN"
    FLOAT = "FLOAT"
    DOUBLE = "DOUBLE"
    DECIMAL = "DECIMAL"
    DATE = "DATE"
    DATETIME = "DATETIME"
    TIMESTAMP = "TIMESTAMP"
    TIME = "TIME"
    JSON = "JSON"
    BLOB = "BLOB"
    UUID = "UUID"


@dataclass
class Field:
    """
    Base field definition.
    
    Defines schema and validation for a model field.
    """
    
    field_type: FieldType = FieldType.STRING
    
    # Constraints
    primary_key: bool = False
    nullable: bool = True
    unique: bool = False
    index: bool = False
    
    # Default value
    default: Any = None
    default_factory: Optional[Callable[[], Any]] = None
    
    # Column definition
    column_name: Optional[str] = None
    max_length: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None
    
    # Validation
    validators: List[Callable] = field(default_factory=list)
    
    # Metadata
    name: str = ""
    model: Optional[Type[Model]] = None
    
    def __set_name__(self, owner: Type[Model], name: str) -> None:
        """Called when field is assigned to a class."""
        self.name = name
        self.model = owner
        if self.column_name is None:
            self.column_name = name
            
    def __get__(self, obj: Optional[Model], objtype: Type[Model] = None) -> Any:
        """Get field value from model instance."""
        if obj is None:
            return self
        return obj._data.get(self.name, self.get_default())
        
    def __set__(self, obj: Model, value: Any) -> None:
        """Set field value on model instance."""
        validated = self.validate(value)
        obj._data[self.name] = validated
        obj._dirty.add(self.name)
        
    def get_default(self) -> Any:
        """Get default value."""
        if self.default_factory:
            return self.default_factory()
        return self.default
        
    def validate(self, value: Any) -> Any:
        """Validate and convert value."""
        if value is None:
            if not self.nullable and not self.primary_key:
                raise ValueError(f"Field '{self.name}' cannot be null")
            return None
            
        # Run validators
        for validator in self.validators:
            value = validator(value)
            
        return self.to_python(value)
        
    def to_python(self, value: Any) -> Any:
        """Convert database value to Python value."""
        return value
        
    def to_database(self, value: Any) -> Any:
        """Convert Python value to database value."""
        return value
        
    def get_column_definition(self) -> str:
        """Get SQL column definition."""
        parts = [self.field_type.value]
        
        if self.max_length:
            parts[-1] = f"{parts[-1]}({self.max_length})"
        elif self.precision:
            if self.scale:
                parts[-1] = f"{parts[-1]}({self.precision},{self.scale})"
            else:
                parts[-1] = f"{parts[-1]}({self.precision})"
                
        if self.primary_key:
            parts.append("PRIMARY KEY")
        if not self.nullable and not self.primary_key:
            parts.append("NOT NULL")
        if self.unique:
            parts.append("UNIQUE")
        if self.default is not None and not callable(self.default):
            parts.append(f"DEFAULT {self._format_default()}")
            
        return " ".join(parts)
        
    def _format_default(self) -> str:
        """Format default value for SQL."""
        if isinstance(self.default, str):
            return f"'{self.default}'"
        if isinstance(self.default, bool):
            return "1" if self.default else "0"
        return str(self.default)


@dataclass
class IntegerField(Field):
    """Integer field."""
    
    field_type: FieldType = FieldType.INTEGER
    auto_increment: bool = False
    
    def to_python(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        return int(value)
        
    def get_column_definition(self) -> str:
        base = super().get_column_definition()
        if self.auto_increment:
            base = base.replace("PRIMARY KEY", "PRIMARY KEY AUTOINCREMENT")
        return base


@dataclass
class BigIntegerField(IntegerField):
    """Big integer field."""
    
    field_type: FieldType = FieldType.BIGINT


@dataclass
class StringField(Field):
    """String/VARCHAR field."""
    
    field_type: FieldType = FieldType.STRING
    max_length: Optional[int] = 255
    
    def to_python(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        return str(value)
        
    def validate(self, value: Any) -> Any:
        value = super().validate(value)
        if value and self.max_length and len(value) > self.max_length:
            raise ValueError(
                f"Value exceeds max_length of {self.max_length}"
            )
        return value


@dataclass
class TextField(Field):
    """Text field (unlimited length)."""
    
    field_type: FieldType = FieldType.TEXT
    
    def to_python(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        return str(value)


@dataclass
class BooleanField(Field):
    """Boolean field."""
    
    field_type: FieldType = FieldType.BOOLEAN
    default: bool = False
    nullable: bool = False
    
    def to_python(self, value: Any) -> Optional[bool]:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return bool(value)
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")
        return bool(value)
        
    def to_database(self, value: Any) -> Any:
        if value is None:
            return None
        return 1 if value else 0


@dataclass
class FloatField(Field):
    """Float field."""
    
    field_type: FieldType = FieldType.FLOAT
    
    def to_python(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        return float(value)


@dataclass
class DecimalField(Field):
    """Decimal field with precision."""
    
    field_type: FieldType = FieldType.DECIMAL
    precision: int = 10
    scale: int = 2
    
    def to_python(self, value: Any) -> Any:
        if value is None:
            return None
        from decimal import Decimal
        return Decimal(str(value))


@dataclass
class DateTimeField(Field):
    """DateTime field."""
    
    field_type: FieldType = FieldType.DATETIME
    auto_now: bool = False
    auto_now_add: bool = False
    
    def to_python(self, value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            # Try common formats
            for fmt in [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S.%f",
            ]:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
        raise ValueError(f"Cannot convert {value} to datetime")
        
    def to_database(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return value


@dataclass
class DateField(Field):
    """Date field."""
    
    field_type: FieldType = FieldType.DATE
    
    def to_python(self, value: Any) -> Optional[date]:
        if value is None:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            return datetime.strptime(value, "%Y-%m-%d").date()
        raise ValueError(f"Cannot convert {value} to date")
        
    def to_database(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, date):
            return value.strftime("%Y-%m-%d")
        return value


@dataclass
class JSONField(Field):
    """JSON field."""
    
    field_type: FieldType = FieldType.JSON
    
    def to_python(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            return json.loads(value)
        return value
        
    def to_database(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return value


@dataclass
class ForeignKey(Field):
    """Foreign key field."""
    
    field_type: FieldType = FieldType.INTEGER
    to: Union[str, Type[Model]] = ""
    on_delete: str = "CASCADE"
    on_update: str = "CASCADE"
    related_name: Optional[str] = None
    
    def __post_init__(self):
        super().__post_init__()
        
    def get_column_definition(self) -> str:
        base = super().get_column_definition()
        
        # Get referenced table
        if isinstance(self.to, str):
            ref_table = self.to.lower()
        else:
            ref_table = self.to.__table_name__
            
        return f"{base} REFERENCES {ref_table}(id) ON DELETE {self.on_delete} ON UPDATE {self.on_update}"


@dataclass
class RelationshipInfo:
    """Relationship definition."""
    
    model: Union[str, Type[Model]]
    foreign_key: Optional[str] = None
    back_populates: Optional[str] = None
    lazy: str = "select"  # select, joined, subquery
    uselist: bool = True  # False for one-to-one


def relationship(
    model: Union[str, Type[Model]],
    foreign_key: Optional[str] = None,
    back_populates: Optional[str] = None,
    lazy: str = "select",
    uselist: bool = True,
) -> RelationshipInfo:
    """
    Define a relationship between models.
    
    Example:
        class User(Model):
            name = StringField()
            posts = relationship("Post", back_populates="author")
            
        class Post(Model):
            title = StringField()
            author_id = ForeignKey(User)
            author = relationship(User, foreign_key="author_id", uselist=False)
    """
    return RelationshipInfo(
        model=model,
        foreign_key=foreign_key,
        back_populates=back_populates,
        lazy=lazy,
        uselist=uselist,
    )


class ModelMeta(type):
    """
    Metaclass for Model.
    
    Collects field definitions and sets up table metadata.
    """
    
    def __new__(
        mcs,
        name: str,
        bases: Tuple[type, ...],
        namespace: Dict[str, Any],
    ) -> ModelMeta:
        # Collect fields from class and bases
        fields: Dict[str, Field] = {}
        relationships: Dict[str, RelationshipInfo] = {}
        
        # Get fields from base classes
        for base in reversed(bases):
            if hasattr(base, "_fields"):
                fields.update(base._fields)
            if hasattr(base, "_relationships"):
                relationships.update(base._relationships)
                
        # Get fields from current class
        for key, value in list(namespace.items()):
            if isinstance(value, Field):
                fields[key] = value
            elif isinstance(value, RelationshipInfo):
                relationships[key] = value
                
        # Add to namespace
        namespace["_fields"] = fields
        namespace["_relationships"] = relationships
        
        # Infer table name
        if "__table_name__" not in namespace:
            # Convert CamelCase to snake_case
            table_name = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
            namespace["__table_name__"] = table_name
            
        cls = super().__new__(mcs, name, bases, namespace)
        
        # Set field names and model references
        for field_name, field_obj in fields.items():
            field_obj.name = field_name
            field_obj.model = cls
            
        return cls


class Model(metaclass=ModelMeta):
    """
    Base model class with Active Record pattern.
    
    Example:
        class User(Model):
            __table_name__ = "users"
            
            id = IntegerField(primary_key=True, auto_increment=True)
            name = StringField(max_length=100)
            email = StringField(max_length=255, unique=True)
            is_active = BooleanField(default=True)
            created_at = DateTimeField(auto_now_add=True)
            
        # Create
        user = User(name="John", email="john@example.com")
        await user.save()
        
        # Read
        user = await User.find(1)
        users = await User.where("is_active", True).get()
        
        # Update
        user.name = "Jane"
        await user.save()
        
        # Delete
        await user.delete()
    """
    
    # Class attributes
    __table_name__: ClassVar[str]
    _fields: ClassVar[Dict[str, Field]]
    _relationships: ClassVar[Dict[str, RelationshipInfo]]
    _database: ClassVar[Any] = None
    
    # Instance attributes
    _data: Dict[str, Any]
    _dirty: Set[str]
    _exists: bool
    _loaded_relations: Dict[str, Any]
    
    def __init__(self, **kwargs) -> None:
        """Initialize model with field values."""
        object.__setattr__(self, "_data", {})
        object.__setattr__(self, "_dirty", set())
        object.__setattr__(self, "_exists", False)
        object.__setattr__(self, "_loaded_relations", {})
        
        # Set field values
        for name, field in self._fields.items():
            if name in kwargs:
                setattr(self, name, kwargs[name])
            else:
                # Set default
                default = field.get_default()
                if default is not None:
                    self._data[name] = default
                    
    def __repr__(self) -> str:
        """String representation."""
        pk = self.get_primary_key_value()
        return f"<{self.__class__.__name__} {pk}>"
        
    def __eq__(self, other: Any) -> bool:
        """Check equality by primary key."""
        if not isinstance(other, self.__class__):
            return False
        return self.get_primary_key_value() == other.get_primary_key_value()
        
    def __hash__(self) -> int:
        """Hash by primary key."""
        return hash((self.__class__.__name__, self.get_primary_key_value()))
        
    @classmethod
    def get_primary_key_field(cls) -> Optional[Field]:
        """Get primary key field."""
        for field in cls._fields.values():
            if field.primary_key:
                return field
        return None
        
    def get_primary_key_value(self) -> Any:
        """Get primary key value."""
        pk_field = self.get_primary_key_field()
        if pk_field:
            return self._data.get(pk_field.name)
        return None
        
    @classmethod
    def use(cls, database: Any) -> Type[T]:
        """
        Set database connection for model.
        
        Returns the class for chaining.
        """
        cls._database = database
        return cls
        
    # Query methods
    
    @classmethod
    def query(cls: Type[T]) -> QueryBuilder:
        """Start a query builder."""
        from nexaweb.orm.query import QueryBuilder
        return QueryBuilder(cls)
        
    @classmethod
    def where(
        cls: Type[T],
        column: str,
        operator: Any = None,
        value: Any = None,
    ) -> QueryBuilder:
        """Start query with WHERE clause."""
        return cls.query().where(column, operator, value)
        
    @classmethod
    def where_in(
        cls: Type[T],
        column: str,
        values: List[Any],
    ) -> QueryBuilder:
        """Start query with WHERE IN clause."""
        return cls.query().where_in(column, values)
        
    @classmethod
    def order_by(
        cls: Type[T],
        column: str,
        direction: str = "ASC",
    ) -> QueryBuilder:
        """Start query with ORDER BY."""
        return cls.query().order_by(column, direction)
        
    @classmethod
    async def find(cls: Type[T], pk: Any) -> Optional[T]:
        """Find model by primary key."""
        pk_field = cls.get_primary_key_field()
        if not pk_field:
            raise ValueError("Model has no primary key")
            
        return await cls.where(pk_field.name, pk).first()
        
    @classmethod
    async def find_or_fail(cls: Type[T], pk: Any) -> T:
        """Find model by primary key or raise."""
        result = await cls.find(pk)
        if result is None:
            raise ValueError(f"{cls.__name__} not found: {pk}")
        return result
        
    @classmethod
    async def all(cls: Type[T]) -> List[T]:
        """Get all records."""
        return await cls.query().get()
        
    @classmethod
    async def first(cls: Type[T]) -> Optional[T]:
        """Get first record."""
        return await cls.query().first()
        
    @classmethod
    async def count(cls) -> int:
        """Count all records."""
        return await cls.query().count()
        
    @classmethod
    async def create(cls: Type[T], **kwargs) -> T:
        """Create and save new record."""
        instance = cls(**kwargs)
        await instance.save()
        return instance
        
    # Instance methods
    
    async def save(self) -> bool:
        """
        Save model to database.
        
        Inserts if new, updates if existing.
        """
        if not self._database:
            raise RuntimeError("No database connection")
            
        # Handle auto timestamps
        now = datetime.now()
        for name, field in self._fields.items():
            if isinstance(field, DateTimeField):
                if field.auto_now_add and not self._exists:
                    self._data[name] = now
                    self._dirty.add(name)
                elif field.auto_now:
                    self._data[name] = now
                    self._dirty.add(name)
                    
        if self._exists:
            return await self._update()
        else:
            return await self._insert()
            
    async def _insert(self) -> bool:
        """Insert new record."""
        # Get values for non-auto fields
        columns = []
        values = []
        placeholders = []
        
        for name, field in self._fields.items():
            if isinstance(field, IntegerField) and field.auto_increment:
                continue
            if name in self._data:
                columns.append(field.column_name)
                values.append(field.to_database(self._data[name]))
                placeholders.append("?")
                
        sql = f"INSERT INTO {self.__table_name__} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
        
        result = await self._database.execute(sql, values)
        
        # Get inserted ID
        pk_field = self.get_primary_key_field()
        if pk_field and isinstance(pk_field, IntegerField) and pk_field.auto_increment:
            self._data[pk_field.name] = result.lastrowid
            
        self._exists = True
        self._dirty.clear()
        return True
        
    async def _update(self) -> bool:
        """Update existing record."""
        if not self._dirty:
            return True
            
        pk_field = self.get_primary_key_field()
        if not pk_field:
            raise ValueError("Cannot update without primary key")
            
        # Build SET clause
        sets = []
        values = []
        
        for name in self._dirty:
            if name in self._fields:
                field = self._fields[name]
                sets.append(f"{field.column_name} = ?")
                values.append(field.to_database(self._data[name]))
                
        # Add WHERE
        values.append(self._data[pk_field.name])
        
        sql = f"UPDATE {self.__table_name__} SET {', '.join(sets)} WHERE {pk_field.column_name} = ?"
        
        await self._database.execute(sql, values)
        
        self._dirty.clear()
        return True
        
    async def delete(self) -> bool:
        """Delete record from database."""
        if not self._exists:
            return False
            
        pk_field = self.get_primary_key_field()
        if not pk_field:
            raise ValueError("Cannot delete without primary key")
            
        sql = f"DELETE FROM {self.__table_name__} WHERE {pk_field.column_name} = ?"
        
        await self._database.execute(sql, [self._data[pk_field.name]])
        
        self._exists = False
        return True
        
    async def refresh(self) -> None:
        """Reload model from database."""
        pk = self.get_primary_key_value()
        if pk is None:
            return
            
        fresh = await self.__class__.find(pk)
        if fresh:
            self._data = fresh._data.copy()
            self._dirty.clear()
            self._loaded_relations.clear()
            
    def fill(self, **kwargs) -> Model:
        """Fill model with values."""
        for key, value in kwargs.items():
            if key in self._fields:
                setattr(self, key, value)
        return self
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        result = {}
        for name, field in self._fields.items():
            value = self._data.get(name)
            if value is not None:
                value = field.to_python(value)
            result[name] = value
        return result
        
    @classmethod
    def from_row(cls: Type[T], row: Dict[str, Any]) -> T:
        """Create model instance from database row."""
        instance = cls()
        
        for name, field in cls._fields.items():
            column = field.column_name or name
            if column in row:
                instance._data[name] = field.to_python(row[column])
                
        instance._exists = True
        instance._dirty.clear()
        return instance
