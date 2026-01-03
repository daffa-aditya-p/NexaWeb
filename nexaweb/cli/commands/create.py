"""
NexaWeb CLI Create Command
==========================

Create new NexaWeb projects.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional


# Project templates
TEMPLATES: Dict[str, Dict] = {
    "minimal": {
        "description": "Minimal project structure",
        "files": [
            "app.py",
            "routes.py",
        ],
        "directories": [
            "static",
            "templates",
        ],
    },
    "standard": {
        "description": "Standard web application",
        "files": [
            "app.py",
            "config.py",
            "routes.py",
        ],
        "directories": [
            "app",
            "app/controllers",
            "app/models",
            "app/middleware",
            "static",
            "static/css",
            "static/js",
            "templates",
            "templates/layouts",
            "templates/components",
            "tests",
            "migrations",
        ],
    },
    "full": {
        "description": "Full-featured application",
        "files": [
            "app.py",
            "config.py",
            "routes.py",
        ],
        "directories": [
            "app",
            "app/controllers",
            "app/models",
            "app/middleware",
            "app/guards",
            "app/validators",
            "app/services",
            "static",
            "static/css",
            "static/js",
            "static/images",
            "templates",
            "templates/layouts",
            "templates/components",
            "templates/emails",
            "tests",
            "tests/unit",
            "tests/integration",
            "migrations",
            "storage",
            "storage/logs",
            "storage/cache",
        ],
    },
}


def create_project(
    name: str,
    template: str = "standard",
    install_deps: bool = True,
) -> int:
    """
    Create a new NexaWeb project.
    
    Args:
        name: Project name
        template: Template type
        install_deps: Whether to install dependencies
        
    Returns:
        Exit code
    """
    project_dir = Path.cwd() / name
    
    if project_dir.exists():
        print(f"Error: Directory '{name}' already exists", file=sys.stderr)
        return 1
    
    print(f"Creating NexaWeb project '{name}' with {template} template...")
    
    # Create directories
    template_config = TEMPLATES[template]
    
    project_dir.mkdir(parents=True)
    
    for directory in template_config["directories"]:
        (project_dir / directory).mkdir(parents=True, exist_ok=True)
        # Add .gitkeep to empty directories
        gitkeep = project_dir / directory / ".gitkeep"
        gitkeep.touch()
    
    # Create files
    _create_app_file(project_dir, template)
    _create_config_file(project_dir, template)
    _create_routes_file(project_dir, template)
    _create_pyproject_file(project_dir, name)
    _create_gitignore(project_dir)
    _create_env_file(project_dir)
    _create_readme(project_dir, name)
    
    # Create additional template-specific files
    if template in ("standard", "full"):
        _create_controller_base(project_dir)
        _create_model_base(project_dir)
    
    if template == "full":
        _create_docker_files(project_dir, name)
    
    print(f"  Created project structure")
    
    # Install dependencies
    if install_deps:
        print("  Installing dependencies...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", "."],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"Warning: Failed to install dependencies: {result.stderr}")
    
    print()
    print(f"✓ Project '{name}' created successfully!")
    print()
    print("Next steps:")
    print(f"  cd {name}")
    print("  nexaweb serve")
    print()
    
    return 0


def _create_app_file(project_dir: Path, template: str) -> None:
    """Create main app.py file."""
    content = '''"""
NexaWeb Application
"""

from nexaweb import Application
from routes import register_routes


def create_app() -> Application:
    """Create application instance."""
    app = Application()
    
    # Register routes
    register_routes(app)
    
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
'''
    (project_dir / "app.py").write_text(content)


def _create_config_file(project_dir: Path, template: str) -> None:
    """Create config.py file."""
    content = '''"""
Application Configuration
"""

import os
from pathlib import Path


# Base directory
BASE_DIR = Path(__file__).parent


# Application settings
APP_NAME = os.getenv("APP_NAME", "NexaWeb App")
APP_ENV = os.getenv("APP_ENV", "development")
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")


# Server settings
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))


# Database settings
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/database.db")


# Template settings
TEMPLATE_DIR = BASE_DIR / "templates"


# Static files
STATIC_DIR = BASE_DIR / "static"
STATIC_URL = "/static"


# Session settings
SESSION_DRIVER = os.getenv("SESSION_DRIVER", "memory")
SESSION_LIFETIME = int(os.getenv("SESSION_LIFETIME", "120"))  # minutes


# Security
CSRF_ENABLED = True
RATE_LIMIT = os.getenv("RATE_LIMIT", "100/minute")
'''
    (project_dir / "config.py").write_text(content)


def _create_routes_file(project_dir: Path, template: str) -> None:
    """Create routes.py file."""
    content = '''"""
Application Routes
"""

from nexaweb import Application
from nexaweb.core import Request, Response


def register_routes(app: Application) -> None:
    """Register application routes."""
    
    @app.get("/")
    async def index(request: Request) -> Response:
        """Home page."""
        return Response.html("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Welcome to NexaWeb</title>
            <style>
                body {
                    font-family: system-ui, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }
                .container {
                    text-align: center;
                    color: white;
                }
                h1 { font-size: 3em; margin-bottom: 0; }
                p { font-size: 1.2em; opacity: 0.9; }
                a { color: white; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🚀 NexaWeb</h1>
                <p>Your application is ready!</p>
                <p><a href="/api/hello">Try the API</a></p>
            </div>
        </body>
        </html>
        """)
    
    @app.get("/api/hello")
    async def hello(request: Request) -> Response:
        """API hello endpoint."""
        return Response.json({
            "message": "Hello from NexaWeb!",
            "version": "0.1.0",
        })
'''
    (project_dir / "routes.py").write_text(content)


def _create_pyproject_file(project_dir: Path, name: str) -> None:
    """Create pyproject.toml file."""
    content = f'''[project]
name = "{name}"
version = "0.1.0"
description = "A NexaWeb application"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "nexaweb",
    "uvicorn[standard]",
]

[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-asyncio",
    "httpx",
]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"
'''
    (project_dir / "pyproject.toml").write_text(content)


def _create_gitignore(project_dir: Path) -> None:
    """Create .gitignore file."""
    content = '''# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
.venv/
ENV/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Environment
.env
.env.local
.env.*.local

# Database
*.db
*.sqlite3

# Logs
*.log
storage/logs/*
!storage/logs/.gitkeep

# Cache
storage/cache/*
!storage/cache/.gitkeep

# OS
.DS_Store
Thumbs.db
'''
    (project_dir / ".gitignore").write_text(content)


def _create_env_file(project_dir: Path) -> None:
    """Create .env.example file."""
    content = '''# Application
APP_NAME="My NexaWeb App"
APP_ENV=development
DEBUG=true
SECRET_KEY=your-secret-key-here

# Server
HOST=127.0.0.1
PORT=8000

# Database
DATABASE_URL=sqlite:///database.db

# Session
SESSION_DRIVER=memory
SESSION_LIFETIME=120
'''
    (project_dir / ".env.example").write_text(content)


def _create_readme(project_dir: Path, name: str) -> None:
    """Create README.md file."""
    content = f'''# {name}

A web application built with NexaWeb.

## Getting Started

### Installation

```bash
# Install dependencies
pip install -e .

# Copy environment file
cp .env.example .env
```

### Development

```bash
# Start development server
nexaweb serve

# Or using Python
python app.py
```

Visit http://127.0.0.1:8000 in your browser.

### Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

## Project Structure

```
{name}/
├── app.py              # Application entry point
├── config.py           # Configuration
├── routes.py           # Route definitions
├── app/
│   ├── controllers/    # Request handlers
│   ├── models/         # Database models
│   └── middleware/     # Custom middleware
├── templates/          # PYXM templates
├── static/             # Static assets
├── tests/              # Test files
└── migrations/         # Database migrations
```

## Documentation

Visit https://nexaweb.dev for full documentation.
'''
    (project_dir / "README.md").write_text(content)


def _create_controller_base(project_dir: Path) -> None:
    """Create base controller file."""
    content = '''"""
Base Controller
"""

from nexaweb.core import Request, Response


class Controller:
    """Base controller class."""
    
    def __init__(self, request: Request):
        self.request = request
    
    def json(self, data: dict, status: int = 200) -> Response:
        """Return JSON response."""
        return Response.json(data, status=status)
    
    def html(self, content: str, status: int = 200) -> Response:
        """Return HTML response."""
        return Response.html(content, status=status)
    
    def redirect(self, url: str, status: int = 302) -> Response:
        """Return redirect response."""
        return Response.redirect(url, status=status)
'''
    (project_dir / "app" / "controllers" / "__init__.py").write_text(content)


def _create_model_base(project_dir: Path) -> None:
    """Create base model file."""
    content = '''"""
Base Model
"""

from nexaweb.orm import Model, StringField, IntegerField, DateTimeField


class BaseModel(Model):
    """Base model with common fields."""
    
    class Meta:
        abstract = True


# Example model (remove or modify)
class User(BaseModel):
    """User model."""
    
    __tablename__ = "users"
    
    id = IntegerField(primary_key=True)
    name = StringField(max_length=100)
    email = StringField(max_length=255, unique=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
'''
    (project_dir / "app" / "models" / "__init__.py").write_text(content)


def _create_docker_files(project_dir: Path, name: str) -> None:
    """Create Docker files for full template."""
    dockerfile = '''FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Run
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
'''
    (project_dir / "Dockerfile").write_text(dockerfile)
    
    compose = f'''version: "3.8"

services:
  app:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - .:/app
    environment:
      - APP_ENV=development
      - DEBUG=true
    depends_on:
      - db

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: {name}
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

volumes:
  postgres_data:
'''
    (project_dir / "docker-compose.yml").write_text(compose)
