"""
NexaWeb ORM (Object-Relational Mapping)
=======================================

Lightweight async ORM with:
- Active Record pattern
- Query builder
- Migrations
- Connection pooling
- Multiple database support
"""

from nexaweb.orm.model import (
    Model,
    Field,
    IntegerField,
    StringField,
    TextField,
    BooleanField,
    FloatField,
    DateTimeField,
    DateField,
    JSONField,
    ForeignKey,
    relationship,
)
from nexaweb.orm.query import (
    Query,
    QueryBuilder,
    Expression,
    F,
    Q,
)
from nexaweb.orm.connection import (
    Connection,
    ConnectionPool,
    Database,
    DatabaseConfig,
)
from nexaweb.orm.migrations import (
    Migration,
    MigrationManager,
    Schema,
    Blueprint,
)

__all__ = [
    # Model
    "Model",
    "Field",
    "IntegerField",
    "StringField",
    "TextField",
    "BooleanField",
    "FloatField",
    "DateTimeField",
    "DateField",
    "JSONField",
    "ForeignKey",
    "relationship",
    # Query
    "Query",
    "QueryBuilder",
    "Expression",
    "F",
    "Q",
    # Connection
    "Connection",
    "ConnectionPool",
    "Database",
    "DatabaseConfig",
    # Migrations
    "Migration",
    "MigrationManager",
    "Schema",
    "Blueprint",
]
