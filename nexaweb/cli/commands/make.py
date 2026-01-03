"""
NexaWeb CLI Make Command
========================

Generate components (controllers, models, migrations, etc).
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Callable


def make_component(component_type: str, name: str) -> int:
    """
    Generate a component.
    
    Args:
        component_type: Type of component
        name: Component name
        
    Returns:
        Exit code
    """
    generators: Dict[str, Callable] = {
        "controller": make_controller,
        "model": make_model,
        "migration": make_migration,
        "middleware": make_middleware,
        "guard": make_guard,
    }
    
    generator = generators.get(component_type)
    
    if not generator:
        print(f"Unknown component type: {component_type}", file=sys.stderr)
        return 1
    
    return generator(name)


def make_controller(name: str) -> int:
    """Generate a controller."""
    controllers_dir = _get_dir("app/controllers")
    
    # Format name
    class_name = _to_class_name(name)
    file_name = _to_file_name(name)
    
    if not class_name.endswith("Controller"):
        class_name = f"{class_name}Controller"
    
    content = f'''"""
{class_name}
{"=" * len(class_name)}

Controller for {name.replace("_", " ").title()}.
"""

from nexaweb.core import Request, Response


class {class_name}:
    """Handle {name.replace("_", " ")} requests."""
    
    async def index(self, request: Request) -> Response:
        """List all items."""
        return Response.json({{"message": "List {name}"}})
    
    async def show(self, request: Request, id: int) -> Response:
        """Show single item."""
        return Response.json({{"message": f"Show {name} {{id}}"}})
    
    async def create(self, request: Request) -> Response:
        """Create new item."""
        data = await request.json()
        return Response.json({{"message": "Created", "data": data}}, status=201)
    
    async def update(self, request: Request, id: int) -> Response:
        """Update item."""
        data = await request.json()
        return Response.json({{"message": f"Updated {name} {{id}}", "data": data}})
    
    async def delete(self, request: Request, id: int) -> Response:
        """Delete item."""
        return Response.json({{"message": f"Deleted {name} {{id}}"}})
'''
    
    output_file = controllers_dir / f"{file_name}_controller.py"
    output_file.write_text(content)
    
    print(f"✓ Created controller: {output_file}")
    return 0


def make_model(name: str) -> int:
    """Generate a model."""
    models_dir = _get_dir("app/models")
    
    # Format name
    class_name = _to_class_name(name)
    file_name = _to_file_name(name)
    table_name = _to_table_name(name)
    
    content = f'''"""
{class_name} Model
{"=" * (len(class_name) + 6)}

Database model for {name.replace("_", " ").title()}.
"""

from nexaweb.orm import (
    Model,
    IntegerField,
    StringField,
    TextField,
    BooleanField,
    DateTimeField,
)


class {class_name}(Model):
    """
    {class_name} model.
    
    Attributes:
        id: Primary key
        name: Item name
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    
    __tablename__ = "{table_name}"
    
    id = IntegerField(primary_key=True)
    name = StringField(max_length=255)
    description = TextField(nullable=True)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    
    def __repr__(self) -> str:
        return f"<{class_name} id={{self.id}} name={{self.name!r}}>"
'''
    
    output_file = models_dir / f"{file_name}.py"
    output_file.write_text(content)
    
    print(f"✓ Created model: {output_file}")
    return 0


def make_migration(name: str) -> int:
    """Generate a migration."""
    from nexaweb.cli.commands.migrate import create_migration
    return create_migration(name)


def make_middleware(name: str) -> int:
    """Generate middleware."""
    middleware_dir = _get_dir("app/middleware")
    
    # Format name
    class_name = _to_class_name(name)
    file_name = _to_file_name(name)
    
    if not class_name.endswith("Middleware"):
        class_name = f"{class_name}Middleware"
    
    content = f'''"""
{class_name}
{"=" * len(class_name)}

Custom middleware for {name.replace("_", " ").title()}.
"""

from typing import Callable, Awaitable
from nexaweb.core import Request, Response, Middleware


class {class_name}(Middleware):
    """
    {name.replace("_", " ").title()} middleware.
    
    Processes requests before they reach route handlers
    and responses before they're sent to clients.
    """
    
    async def __call__(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process the request."""
        # Before request processing
        # Add your pre-processing logic here
        
        # Call next middleware/handler
        response = await call_next(request)
        
        # After request processing
        # Add your post-processing logic here
        
        return response
'''
    
    output_file = middleware_dir / f"{file_name}_middleware.py"
    output_file.write_text(content)
    
    print(f"✓ Created middleware: {output_file}")
    return 0


def make_guard(name: str) -> int:
    """Generate a guard."""
    guards_dir = _get_dir("app/guards")
    
    # Format name
    class_name = _to_class_name(name)
    file_name = _to_file_name(name)
    
    if not class_name.endswith("Guard"):
        class_name = f"{class_name}Guard"
    
    content = f'''"""
{class_name}
{"=" * len(class_name)}

Authorization guard for {name.replace("_", " ").title()}.
"""

from nexaweb.core import Request
from nexaweb.auth import Guard


class {class_name}(Guard):
    """
    {name.replace("_", " ").title()} authorization guard.
    
    Determines if a request should be allowed to proceed.
    """
    
    async def can_activate(self, request: Request) -> bool:
        """
        Check if the request can proceed.
        
        Args:
            request: The incoming request
            
        Returns:
            True if allowed, False otherwise
        """
        # Add your authorization logic here
        # Example: Check if user has specific permission
        
        user = getattr(request, "user", None)
        
        if not user:
            return False
        
        # Add custom checks
        return True
    
    def get_error_message(self) -> str:
        """Get error message when guard fails."""
        return "Access denied: {name.replace('_', ' ').title()} check failed"
'''
    
    output_file = guards_dir / f"{file_name}_guard.py"
    output_file.write_text(content)
    
    print(f"✓ Created guard: {output_file}")
    return 0


def _get_dir(relative_path: str) -> Path:
    """Get or create directory."""
    directory = Path.cwd() / relative_path
    directory.mkdir(parents=True, exist_ok=True)
    
    # Ensure __init__.py exists
    init_file = directory / "__init__.py"
    if not init_file.exists():
        init_file.write_text('"""Package."""\n')
    
    return directory


def _to_class_name(name: str) -> str:
    """Convert to PascalCase class name."""
    words = name.replace("-", "_").split("_")
    return "".join(word.capitalize() for word in words)


def _to_file_name(name: str) -> str:
    """Convert to snake_case file name."""
    return name.lower().replace("-", "_").replace(" ", "_")


def _to_table_name(name: str) -> str:
    """Convert to plural table name."""
    file_name = _to_file_name(name)
    
    # Simple pluralization
    if file_name.endswith("y"):
        return file_name[:-1] + "ies"
    elif file_name.endswith(("s", "x", "ch", "sh")):
        return file_name + "es"
    else:
        return file_name + "s"
