"""
NexaWeb CLI Migrate Command
===========================

Database migration commands.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional


async def run_migration(
    action: str = "run",
    steps: int = 1,
) -> int:
    """
    Run database migrations.
    
    Args:
        action: Migration action (run, rollback, reset, refresh, status)
        steps: Number of batches for rollback
        
    Returns:
        Exit code
    """
    # Find migrations directory
    migrations_dir = _find_migrations_dir()
    
    if not migrations_dir:
        print("Error: Could not find migrations directory", file=sys.stderr)
        print("Create a 'migrations' directory in your project", file=sys.stderr)
        return 1
    
    print(f"Running migration: {action}")
    
    try:
        # Import ORM components
        from nexaweb.orm import MigrationManager, Database
        
        # Get database connection
        db = await _get_database()
        
        if not db:
            print("Error: Could not connect to database", file=sys.stderr)
            return 1
        
        # Create migration manager
        manager = MigrationManager(db, str(migrations_dir))
        
        # Execute action
        if action == "run":
            await manager.migrate()
            print("✓ Migrations completed")
        
        elif action == "rollback":
            await manager.rollback(steps)
            print(f"✓ Rolled back {steps} batch(es)")
        
        elif action == "reset":
            await manager.reset()
            print("✓ All migrations reset")
        
        elif action == "refresh":
            await manager.refresh()
            print("✓ Database refreshed")
        
        elif action == "status":
            status = await manager.status()
            _print_status(status)
        
        else:
            print(f"Unknown action: {action}", file=sys.stderr)
            return 1
        
    except ImportError as e:
        print(f"Error: Missing required package: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Migration error: {e}", file=sys.stderr)
        return 1
    
    return 0


def _find_migrations_dir() -> Optional[Path]:
    """Find migrations directory."""
    cwd = Path.cwd()
    
    candidates = [
        cwd / "migrations",
        cwd / "database" / "migrations",
        cwd / "db" / "migrations",
    ]
    
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate
    
    return None


async def _get_database():
    """Get database connection from config."""
    import os
    
    # Try to load config
    config_file = Path.cwd() / "config.py"
    
    database_url = None
    
    if config_file.exists():
        import importlib.util
        
        spec = importlib.util.spec_from_file_location("config", config_file)
        config = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config)
        
        database_url = getattr(config, "DATABASE_URL", None)
    
    if not database_url:
        database_url = os.getenv("DATABASE_URL", "sqlite:///database.db")
    
    from nexaweb.orm import Database
    
    db = Database(database_url)
    await db.connect()
    
    return db


def _print_status(status: dict) -> None:
    """Print migration status."""
    print()
    print("Migration Status")
    print("=" * 50)
    
    ran = status.get("ran", [])
    pending = status.get("pending", [])
    
    if ran:
        print("\nRan:")
        for migration in ran:
            print(f"  ✓ {migration}")
    
    if pending:
        print("\nPending:")
        for migration in pending:
            print(f"  ○ {migration}")
    
    if not ran and not pending:
        print("No migrations found")
    
    print()


def create_migration(name: str) -> int:
    """
    Create a new migration file.
    
    Args:
        name: Migration name
        
    Returns:
        Exit code
    """
    from datetime import datetime
    
    migrations_dir = _find_migrations_dir()
    
    if not migrations_dir:
        migrations_dir = Path.cwd() / "migrations"
        migrations_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate timestamp
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    
    # Generate filename
    safe_name = name.lower().replace(" ", "_").replace("-", "_")
    filename = f"{timestamp}_{safe_name}.py"
    
    # Generate content
    class_name = "".join(word.capitalize() for word in safe_name.split("_"))
    
    content = f'''"""
Migration: {name}
Created: {datetime.now().isoformat()}
"""

from nexaweb.orm import Migration, Schema, Blueprint


class {class_name}Migration(Migration):
    """Migration for {name}."""
    
    async def up(self, schema: Schema) -> None:
        """Run the migration."""
        async with schema.create("table_name") as table:
            table.id()
            table.string("name")
            table.timestamps()
    
    async def down(self, schema: Schema) -> None:
        """Reverse the migration."""
        await schema.drop("table_name")
'''
    
    migration_file = migrations_dir / filename
    migration_file.write_text(content)
    
    print(f"✓ Created migration: {filename}")
    
    return 0
