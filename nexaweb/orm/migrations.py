"""
NexaWeb ORM Migrations
======================

Database schema migrations system.

Features:
- Schema builder (Blueprint)
- Migration runner
- Up/down migrations
- Batch execution
"""

from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type

from nexaweb.orm.connection import Database, DatabaseDriver
from nexaweb.orm.model import FieldType


@dataclass
class Column:
    """Column definition for migrations."""
    
    name: str
    type: FieldType
    length: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None
    nullable: bool = True
    default: Any = None
    primary_key: bool = False
    auto_increment: bool = False
    unique: bool = False
    index: bool = False
    unsigned: bool = False
    references: Optional[str] = None
    on_delete: str = "CASCADE"
    on_update: str = "CASCADE"
    
    def to_sql(self, driver: DatabaseDriver) -> str:
        """Generate SQL column definition."""
        parts = [self.name]
        
        # Type with length
        type_str = self.type.value
        if self.length:
            type_str = f"{type_str}({self.length})"
        elif self.precision:
            if self.scale:
                type_str = f"{type_str}({self.precision},{self.scale})"
            else:
                type_str = f"{type_str}({self.precision})"
                
        parts.append(type_str)
        
        # Constraints
        if self.unsigned and driver == DatabaseDriver.MYSQL:
            parts.append("UNSIGNED")
            
        if self.primary_key:
            parts.append("PRIMARY KEY")
            if self.auto_increment:
                if driver == DatabaseDriver.SQLITE:
                    parts[-1] = "PRIMARY KEY AUTOINCREMENT"
                elif driver == DatabaseDriver.POSTGRESQL:
                    parts[1] = "SERIAL"
                else:
                    parts.append("AUTO_INCREMENT")
                    
        if not self.nullable and not self.primary_key:
            parts.append("NOT NULL")
            
        if self.unique and not self.primary_key:
            parts.append("UNIQUE")
            
        if self.default is not None:
            parts.append(f"DEFAULT {self._format_default()}")
            
        if self.references:
            parts.append(
                f"REFERENCES {self.references} ON DELETE {self.on_delete} ON UPDATE {self.on_update}"
            )
            
        return " ".join(parts)
        
    def _format_default(self) -> str:
        """Format default value."""
        if isinstance(self.default, str):
            return f"'{self.default}'"
        if isinstance(self.default, bool):
            return "1" if self.default else "0"
        if self.default is None:
            return "NULL"
        return str(self.default)


class Blueprint:
    """
    Table schema builder.
    
    Provides fluent interface for defining table schema.
    
    Example:
        def up(schema):
            with schema.create("users") as table:
                table.id()
                table.string("name", 100)
                table.string("email").unique()
                table.boolean("is_active").default(True)
                table.timestamps()
    """
    
    def __init__(self, table: str) -> None:
        self.table = table
        self.columns: List[Column] = []
        self.indexes: List[Dict[str, Any]] = []
        self.foreign_keys: List[Dict[str, Any]] = []
        self.primary_key: Optional[List[str]] = None
        
        # Current column being defined
        self._current: Optional[Column] = None
        
    def _add_column(self, column: Column) -> Blueprint:
        """Add column and set as current."""
        self.columns.append(column)
        self._current = column
        return self
        
    # Column types
    
    def id(self, name: str = "id") -> Blueprint:
        """Add auto-incrementing primary key."""
        return self._add_column(Column(
            name=name,
            type=FieldType.INTEGER,
            primary_key=True,
            auto_increment=True,
            nullable=False,
        ))
        
    def big_increments(self, name: str) -> Blueprint:
        """Add auto-incrementing big integer."""
        return self._add_column(Column(
            name=name,
            type=FieldType.BIGINT,
            primary_key=True,
            auto_increment=True,
            nullable=False,
        ))
        
    def integer(self, name: str) -> Blueprint:
        """Add integer column."""
        return self._add_column(Column(
            name=name,
            type=FieldType.INTEGER,
        ))
        
    def big_integer(self, name: str) -> Blueprint:
        """Add big integer column."""
        return self._add_column(Column(
            name=name,
            type=FieldType.BIGINT,
        ))
        
    def small_integer(self, name: str) -> Blueprint:
        """Add small integer column."""
        return self._add_column(Column(
            name=name,
            type=FieldType.SMALLINT,
        ))
        
    def string(self, name: str, length: int = 255) -> Blueprint:
        """Add varchar column."""
        return self._add_column(Column(
            name=name,
            type=FieldType.STRING,
            length=length,
        ))
        
    def text(self, name: str) -> Blueprint:
        """Add text column."""
        return self._add_column(Column(
            name=name,
            type=FieldType.TEXT,
        ))
        
    def boolean(self, name: str) -> Blueprint:
        """Add boolean column."""
        return self._add_column(Column(
            name=name,
            type=FieldType.BOOLEAN,
            nullable=False,
        ))
        
    def float(self, name: str) -> Blueprint:
        """Add float column."""
        return self._add_column(Column(
            name=name,
            type=FieldType.FLOAT,
        ))
        
    def double(self, name: str) -> Blueprint:
        """Add double column."""
        return self._add_column(Column(
            name=name,
            type=FieldType.DOUBLE,
        ))
        
    def decimal(
        self,
        name: str,
        precision: int = 10,
        scale: int = 2,
    ) -> Blueprint:
        """Add decimal column."""
        return self._add_column(Column(
            name=name,
            type=FieldType.DECIMAL,
            precision=precision,
            scale=scale,
        ))
        
    def date(self, name: str) -> Blueprint:
        """Add date column."""
        return self._add_column(Column(
            name=name,
            type=FieldType.DATE,
        ))
        
    def datetime(self, name: str) -> Blueprint:
        """Add datetime column."""
        return self._add_column(Column(
            name=name,
            type=FieldType.DATETIME,
        ))
        
    def timestamp(self, name: str) -> Blueprint:
        """Add timestamp column."""
        return self._add_column(Column(
            name=name,
            type=FieldType.TIMESTAMP,
        ))
        
    def timestamps(self) -> Blueprint:
        """Add created_at and updated_at columns."""
        self.datetime("created_at").nullable()
        self.datetime("updated_at").nullable()
        return self
        
    def soft_deletes(self) -> Blueprint:
        """Add deleted_at column for soft deletes."""
        return self.datetime("deleted_at").nullable()
        
    def json(self, name: str) -> Blueprint:
        """Add JSON column."""
        return self._add_column(Column(
            name=name,
            type=FieldType.JSON,
        ))
        
    def binary(self, name: str) -> Blueprint:
        """Add binary/blob column."""
        return self._add_column(Column(
            name=name,
            type=FieldType.BLOB,
        ))
        
    def uuid(self, name: str) -> Blueprint:
        """Add UUID column."""
        return self._add_column(Column(
            name=name,
            type=FieldType.UUID,
        ))
        
    # Foreign key
    
    def foreign_id(self, name: str) -> Blueprint:
        """Add foreign key column."""
        return self.integer(name).unsigned()
        
    def foreign(self, column: str) -> ForeignKeyBuilder:
        """Define foreign key constraint."""
        return ForeignKeyBuilder(self, column)
        
    # Modifiers (apply to current column)
    
    def nullable(self) -> Blueprint:
        """Make current column nullable."""
        if self._current:
            self._current.nullable = True
        return self
        
    def not_nullable(self) -> Blueprint:
        """Make current column not nullable."""
        if self._current:
            self._current.nullable = False
        return self
        
    def default(self, value: Any) -> Blueprint:
        """Set default value for current column."""
        if self._current:
            self._current.default = value
        return self
        
    def unique(self) -> Blueprint:
        """Make current column unique."""
        if self._current:
            self._current.unique = True
        return self
        
    def unsigned(self) -> Blueprint:
        """Make current column unsigned."""
        if self._current:
            self._current.unsigned = True
        return self
        
    def primary(self) -> Blueprint:
        """Make current column primary key."""
        if self._current:
            self._current.primary_key = True
        return self
        
    def index(self, name: Optional[str] = None) -> Blueprint:
        """Add index on current column."""
        if self._current:
            self.indexes.append({
                "columns": [self._current.name],
                "name": name or f"idx_{self.table}_{self._current.name}",
                "unique": False,
            })
        return self
        
    def references(self, table_column: str) -> Blueprint:
        """Set foreign key reference."""
        if self._current:
            self._current.references = table_column
        return self
        
    def on_delete(self, action: str) -> Blueprint:
        """Set ON DELETE action."""
        if self._current:
            self._current.on_delete = action
        return self
        
    def on_update(self, action: str) -> Blueprint:
        """Set ON UPDATE action."""
        if self._current:
            self._current.on_update = action
        return self
        
    # Composite indexes
    
    def add_index(
        self,
        columns: List[str],
        name: Optional[str] = None,
        unique: bool = False,
    ) -> Blueprint:
        """Add composite index."""
        cols_str = "_".join(columns)
        self.indexes.append({
            "columns": columns,
            "name": name or f"idx_{self.table}_{cols_str}",
            "unique": unique,
        })
        return self
        
    def add_unique(
        self,
        columns: List[str],
        name: Optional[str] = None,
    ) -> Blueprint:
        """Add unique composite index."""
        return self.add_index(columns, name, unique=True)
        
    def add_primary(self, columns: List[str]) -> Blueprint:
        """Set composite primary key."""
        self.primary_key = columns
        return self
        
    def to_sql(self, driver: DatabaseDriver) -> List[str]:
        """Generate SQL statements."""
        statements = []
        
        # CREATE TABLE
        column_defs = [col.to_sql(driver) for col in self.columns]
        
        # Add composite primary key
        if self.primary_key:
            column_defs.append(
                f"PRIMARY KEY ({', '.join(self.primary_key)})"
            )
            
        create_sql = f"CREATE TABLE {self.table} (\n  {',\n  '.join(column_defs)}\n)"
        statements.append(create_sql)
        
        # CREATE INDEX
        for idx in self.indexes:
            unique = "UNIQUE " if idx["unique"] else ""
            columns = ", ".join(idx["columns"])
            statements.append(
                f"CREATE {unique}INDEX {idx['name']} ON {self.table} ({columns})"
            )
            
        return statements


class ForeignKeyBuilder:
    """Foreign key constraint builder."""
    
    def __init__(self, blueprint: Blueprint, column: str) -> None:
        self.blueprint = blueprint
        self.column = column
        self._ref_table = ""
        self._ref_column = "id"
        self._on_delete = "CASCADE"
        self._on_update = "CASCADE"
        
    def references(self, column: str) -> ForeignKeyBuilder:
        """Set referenced column."""
        self._ref_column = column
        return self
        
    def on(self, table: str) -> ForeignKeyBuilder:
        """Set referenced table."""
        self._ref_table = table
        self.blueprint.foreign_keys.append({
            "column": self.column,
            "ref_table": table,
            "ref_column": self._ref_column,
            "on_delete": self._on_delete,
            "on_update": self._on_update,
        })
        return self
        
    def on_delete(self, action: str) -> ForeignKeyBuilder:
        """Set ON DELETE action."""
        self._on_delete = action
        return self
        
    def on_update(self, action: str) -> ForeignKeyBuilder:
        """Set ON UPDATE action."""
        self._on_update = action
        return self


class Schema:
    """
    Schema builder for migrations.
    
    Provides methods for creating, altering, and dropping tables.
    
    Example:
        async def up(schema: Schema):
            with schema.create("posts") as table:
                table.id()
                table.string("title")
                table.text("content")
                table.foreign_id("user_id")
                table.foreign("user_id").references("id").on("users")
                table.timestamps()
    """
    
    def __init__(self, database: Database) -> None:
        self.database = database
        self._statements: List[str] = []
        
    def create(self, table: str) -> Blueprint:
        """
        Create new table.
        
        Returns Blueprint for defining columns.
        """
        blueprint = Blueprint(table)
        self._statements.extend(
            blueprint.to_sql(self.database.config.driver)
        )
        return blueprint
        
    def drop(self, table: str) -> None:
        """Drop table."""
        self._statements.append(f"DROP TABLE IF EXISTS {table}")
        
    def drop_if_exists(self, table: str) -> None:
        """Drop table if exists."""
        self._statements.append(f"DROP TABLE IF EXISTS {table}")
        
    def rename(self, old_name: str, new_name: str) -> None:
        """Rename table."""
        self._statements.append(
            f"ALTER TABLE {old_name} RENAME TO {new_name}"
        )
        
    def has_table(self, table: str) -> str:
        """Generate check table exists query."""
        driver = self.database.config.driver
        
        if driver == DatabaseDriver.SQLITE:
            return f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
        elif driver == DatabaseDriver.POSTGRESQL:
            return f"SELECT tablename FROM pg_tables WHERE tablename='{table}'"
        else:
            return f"SHOW TABLES LIKE '{table}'"
            
    async def execute(self) -> None:
        """Execute all pending statements."""
        for sql in self._statements:
            await self.database.execute(sql)
        self._statements.clear()


class Migration(ABC):
    """
    Abstract migration class.
    
    Subclass and implement up() and down() methods.
    
    Example:
        class CreateUsersTable(Migration):
            async def up(self, schema: Schema) -> None:
                with schema.create("users") as table:
                    table.id()
                    table.string("email").unique()
                    table.string("password_hash")
                    table.timestamps()
                    
            async def down(self, schema: Schema) -> None:
                schema.drop("users")
    """
    
    @abstractmethod
    async def up(self, schema: Schema) -> None:
        """Run the migration."""
        ...
        
    @abstractmethod
    async def down(self, schema: Schema) -> None:
        """Reverse the migration."""
        ...


@dataclass
class MigrationRecord:
    """Migration execution record."""
    
    id: int
    migration: str
    batch: int
    executed_at: datetime


class MigrationManager:
    """
    Migration runner.
    
    Manages migration execution, tracking, and rollback.
    
    Example:
        manager = MigrationManager(database, "migrations")
        
        # Run pending migrations
        await manager.migrate()
        
        # Rollback last batch
        await manager.rollback()
        
        # Reset all migrations
        await manager.reset()
    """
    
    def __init__(
        self,
        database: Database,
        migrations_path: str = "migrations",
    ) -> None:
        self.database = database
        self.migrations_path = Path(migrations_path)
        self._migrations: Dict[str, Type[Migration]] = {}
        
    async def setup(self) -> None:
        """Create migrations table if not exists."""
        schema = Schema(self.database)
        
        # Check if table exists
        driver = self.database.config.driver
        
        if driver == DatabaseDriver.SQLITE:
            result = await self.database.fetch_one(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='migrations'"
            )
        else:
            result = await self.database.fetch_one(
                f"SELECT table_name FROM information_schema.tables WHERE table_name='migrations'"
            )
            
        if not result:
            await self.database.execute("""
                CREATE TABLE migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    migration VARCHAR(255) NOT NULL,
                    batch INTEGER NOT NULL,
                    executed_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
    def register(self, name: str, migration_class: Type[Migration]) -> None:
        """Register a migration."""
        self._migrations[name] = migration_class
        
    async def get_ran_migrations(self) -> List[str]:
        """Get list of executed migrations."""
        rows = await self.database.fetch_all(
            "SELECT migration FROM migrations ORDER BY batch, id"
        )
        return [row["migration"] for row in rows]
        
    async def get_last_batch(self) -> int:
        """Get last batch number."""
        result = await self.database.fetch_one(
            "SELECT MAX(batch) as max_batch FROM migrations"
        )
        return result["max_batch"] or 0 if result else 0
        
    async def get_pending_migrations(self) -> List[str]:
        """Get list of pending migrations."""
        ran = await self.get_ran_migrations()
        all_migrations = sorted(self._migrations.keys())
        return [m for m in all_migrations if m not in ran]
        
    async def migrate(self) -> List[str]:
        """
        Run all pending migrations.
        
        Returns list of executed migration names.
        """
        await self.setup()
        
        pending = await self.get_pending_migrations()
        if not pending:
            return []
            
        batch = await self.get_last_batch() + 1
        executed = []
        
        for name in pending:
            migration_class = self._migrations[name]
            migration = migration_class()
            
            schema = Schema(self.database)
            await migration.up(schema)
            await schema.execute()
            
            await self.database.execute(
                "INSERT INTO migrations (migration, batch) VALUES (?, ?)",
                [name, batch],
            )
            
            executed.append(name)
            
        return executed
        
    async def rollback(self, steps: int = 1) -> List[str]:
        """
        Rollback last N batches.
        
        Returns list of rolled back migration names.
        """
        rolled_back = []
        last_batch = await self.get_last_batch()
        
        for _ in range(steps):
            if last_batch < 1:
                break
                
            # Get migrations in this batch
            rows = await self.database.fetch_all(
                "SELECT migration FROM migrations WHERE batch = ? ORDER BY id DESC",
                [last_batch],
            )
            
            for row in rows:
                name = row["migration"]
                if name not in self._migrations:
                    continue
                    
                migration_class = self._migrations[name]
                migration = migration_class()
                
                schema = Schema(self.database)
                await migration.down(schema)
                await schema.execute()
                
                await self.database.execute(
                    "DELETE FROM migrations WHERE migration = ?",
                    [name],
                )
                
                rolled_back.append(name)
                
            last_batch -= 1
            
        return rolled_back
        
    async def reset(self) -> List[str]:
        """
        Rollback all migrations.
        
        Returns list of rolled back migration names.
        """
        total_batches = await self.get_last_batch()
        return await self.rollback(total_batches)
        
    async def refresh(self) -> Tuple[List[str], List[str]]:
        """
        Reset and re-run all migrations.
        
        Returns (rolled_back, executed) tuple.
        """
        rolled_back = await self.reset()
        executed = await self.migrate()
        return rolled_back, executed
        
    async def status(self) -> List[Dict[str, Any]]:
        """
        Get migration status.
        
        Returns list of migration info with ran status.
        """
        ran = set(await self.get_ran_migrations())
        
        status = []
        for name in sorted(self._migrations.keys()):
            status.append({
                "migration": name,
                "ran": name in ran,
            })
            
        return status


def create_migration(name: str, migrations_path: str = "migrations") -> str:
    """
    Create a new migration file.
    
    Returns path to created file.
    """
    path = Path(migrations_path)
    path.mkdir(parents=True, exist_ok=True)
    
    # Generate timestamp
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    
    # Create filename
    filename = f"{timestamp}_{name}.py"
    filepath = path / filename
    
    # Generate content
    class_name = "".join(word.title() for word in name.split("_"))
    
    content = f'''"""
Migration: {name}
Created: {datetime.now().isoformat()}
"""

from nexaweb.orm import Migration, Schema


class {class_name}(Migration):
    """Migration for {name}."""
    
    async def up(self, schema: Schema) -> None:
        """Run the migration."""
        # TODO: Define your migration here
        pass
        
    async def down(self, schema: Schema) -> None:
        """Reverse the migration."""
        # TODO: Define rollback here
        pass
'''
    
    with open(filepath, "w") as f:
        f.write(content)
        
    return str(filepath)
