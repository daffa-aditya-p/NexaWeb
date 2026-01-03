"""
NexaWeb Standard Template
=========================

Standard project template with full structure.
"""

from __future__ import annotations

from typing import List

from nexaweb.templates.base import ProjectTemplate, TemplateFile, TemplateDirectory


# =============================================================================
# Template Content
# =============================================================================

APP_PY = '''"""
{{ project_name }} Application
"""

from nexaweb import Application
from config import DEBUG
from routes import register_routes


def create_app() -> Application:
    """Create application instance."""
    app = Application(debug=DEBUG)
    
    # Register routes
    register_routes(app)
    
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=DEBUG)
'''


CONFIG_PY = '''"""
Application Configuration
"""

import os
from pathlib import Path


# Base directory
BASE_DIR = Path(__file__).parent

# Application
APP_NAME = os.getenv("APP_NAME", "{{ project_name }}")
APP_ENV = os.getenv("APP_ENV", "development")
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")

# Server
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

# Database
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/database.db")

# Paths
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Session
SESSION_SECRET = SECRET_KEY
SESSION_LIFETIME = 120  # minutes

# Security
CSRF_ENABLED = True
RATE_LIMIT = "100/minute"
'''


ROUTES_PY = '''"""
Application Routes
"""

from nexaweb import Application
from nexaweb.core import Request, Response
from app.controllers.home import HomeController


def register_routes(app: Application) -> None:
    """Register all application routes."""
    
    # Home routes
    home = HomeController()
    
    @app.get("/")
    async def index(request: Request) -> Response:
        return await home.index(request)
    
    @app.get("/about")
    async def about(request: Request) -> Response:
        return await home.about(request)
    
    # API routes
    @app.get("/api/health")
    async def health(request: Request) -> Response:
        return Response.json({"status": "ok", "app": "{{ project_name }}"})
'''


HOME_CONTROLLER = '''"""
Home Controller
"""

from nexaweb.core import Request, Response
from config import APP_NAME


class HomeController:
    """Home page controller."""
    
    async def index(self, request: Request) -> Response:
        """Home page."""
        return Response.html(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{APP_NAME}</title>
            <link rel="stylesheet" href="/static/css/style.css">
        </head>
        <body>
            <main class="container">
                <h1>Welcome to {APP_NAME}</h1>
                <p>Your NexaWeb application is running!</p>
                <nav>
                    <a href="/">Home</a>
                    <a href="/about">About</a>
                </nav>
            </main>
            <script src="/static/js/app.js"></script>
        </body>
        </html>
        """)
    
    async def about(self, request: Request) -> Response:
        """About page."""
        return Response.html(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>About - {APP_NAME}</title>
            <link rel="stylesheet" href="/static/css/style.css">
        </head>
        <body>
            <main class="container">
                <h1>About</h1>
                <p>This is a NexaWeb application.</p>
                <a href="/">← Back to Home</a>
            </main>
        </body>
        </html>
        """)
'''


STYLE_CSS = '''/* {{ project_name }} Styles */

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: system-ui, -apple-system, sans-serif;
    line-height: 1.6;
    color: #333;
    background: #f5f5f5;
}

.container {
    max-width: 800px;
    margin: 0 auto;
    padding: 2rem;
}

h1 {
    color: #2c3e50;
    margin-bottom: 1rem;
}

p {
    margin-bottom: 1rem;
}

nav {
    margin-top: 2rem;
}

nav a {
    color: #3498db;
    text-decoration: none;
    margin-right: 1rem;
}

nav a:hover {
    text-decoration: underline;
}

a {
    color: #3498db;
}
'''


APP_JS = '''// {{ project_name }} JavaScript

document.addEventListener("DOMContentLoaded", () => {
    console.log("{{ project_name }} loaded!");
});
'''


ENV_EXAMPLE = '''# {{ project_name }} Environment Configuration

# Application
APP_NAME="{{ project_name }}"
APP_ENV=development
DEBUG=true
SECRET_KEY=your-secret-key-here

# Server
HOST=127.0.0.1
PORT=8000

# Database
DATABASE_URL=sqlite:///database.db
'''


PYPROJECT_TOML = '''[project]
name = "{{ project_slug }}"
version = "0.1.0"
description = "{{ project_name }}"
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


GITIGNORE = '''# Python
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
.eggs/
dist/
build/

# Virtual environment
venv/
.venv/

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

# OS
.DS_Store
Thumbs.db
'''


README_MD = '''# {{ project_name }}

A NexaWeb web application.

## Getting Started

### Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\\Scripts\\activate on Windows

# Install dependencies
pip install -e .

# Copy environment file
cp .env.example .env
```

### Development

```bash
# Run development server
python app.py

# Or with uvicorn directly
uvicorn app:app --reload
```

Visit http://127.0.0.1:8000

### Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

## Project Structure

```
{{ project_slug }}/
├── app.py              # Application entry point
├── config.py           # Configuration
├── routes.py           # Route definitions
├── app/
│   ├── controllers/    # Request handlers
│   ├── models/         # Database models
│   └── middleware/     # Custom middleware
├── templates/          # HTML templates
├── static/
│   ├── css/           # Stylesheets
│   └── js/            # JavaScript
├── tests/              # Test files
└── migrations/         # Database migrations
```

## Documentation

See https://nexaweb.dev for full documentation.
'''


TEST_APP_PY = '''"""
Application Tests
"""

import pytest
from httpx import AsyncClient
from app import app


@pytest.fixture
async def client():
    """Create test client."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_index(client):
    """Test index page."""
    response = await client.get("/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health(client):
    """Test health endpoint."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
'''


class StandardTemplate(ProjectTemplate):
    """
    Standard project template.
    
    Creates a full-featured NexaWeb application with:
    - Controllers
    - Static files
    - Templates
    - Tests
    - Configuration
    """
    
    name = "standard"
    description = "Standard web application"
    version = "1.0.0"
    
    def get_files(self) -> List[TemplateFile]:
        """Get template files."""
        return [
            # Root files
            TemplateFile("app.py", APP_PY),
            TemplateFile("config.py", CONFIG_PY),
            TemplateFile("routes.py", ROUTES_PY),
            TemplateFile("pyproject.toml", PYPROJECT_TOML),
            TemplateFile(".gitignore", GITIGNORE),
            TemplateFile(".env.example", ENV_EXAMPLE),
            TemplateFile("README.md", README_MD),
            
            # App files
            TemplateFile("app/__init__.py", '"""Application package."""\n'),
            TemplateFile("app/controllers/__init__.py", '"""Controllers package."""\n'),
            TemplateFile("app/controllers/home.py", HOME_CONTROLLER),
            TemplateFile("app/models/__init__.py", '"""Models package."""\n'),
            TemplateFile("app/middleware/__init__.py", '"""Middleware package."""\n'),
            
            # Static files
            TemplateFile("static/css/style.css", STYLE_CSS),
            TemplateFile("static/js/app.js", APP_JS),
            
            # Tests
            TemplateFile("tests/__init__.py", '"""Tests package."""\n'),
            TemplateFile("tests/test_app.py", TEST_APP_PY),
        ]
    
    def get_directories(self) -> List[TemplateDirectory]:
        """Get template directories."""
        return [
            TemplateDirectory("app/services"),
            TemplateDirectory("templates"),
            TemplateDirectory("templates/layouts"),
            TemplateDirectory("templates/components"),
            TemplateDirectory("static/images"),
            TemplateDirectory("migrations"),
            TemplateDirectory("storage/logs"),
        ]
