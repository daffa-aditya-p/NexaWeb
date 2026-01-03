"""
NexaWeb API Template
====================

API-focused project template for RESTful services.
"""

from __future__ import annotations

from typing import List

from nexaweb.templates.base import ProjectTemplate, TemplateFile, TemplateDirectory


# =============================================================================
# Template Content
# =============================================================================

APP_PY = '''"""
{{ project_name }} API
"""

from nexaweb import Application
from nexaweb.core import Request, Response
from config import DEBUG, API_VERSION
from api import register_routes


def create_app() -> Application:
    """Create API application."""
    app = Application(debug=DEBUG)
    
    # CORS middleware
    @app.middleware
    async def cors_middleware(request: Request, call_next):
        response = await call_next(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response
    
    # Register routes
    register_routes(app)
    
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=DEBUG)
'''


CONFIG_PY = '''"""
API Configuration
"""

import os
from pathlib import Path


# Base
BASE_DIR = Path(__file__).parent

# API
API_NAME = os.getenv("API_NAME", "{{ project_name }}")
API_VERSION = os.getenv("API_VERSION", "v1")
API_PREFIX = f"/api/{API_VERSION}"
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

# Auth
SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION = 3600  # 1 hour

# Database
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/database.db")

# Rate limiting
RATE_LIMIT = os.getenv("RATE_LIMIT", "100/minute")

# Pagination
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
'''


API_INIT = '''"""
API Routes
"""

from nexaweb import Application
from api.v1 import health, users


def register_routes(app: Application) -> None:
    """Register all API routes."""
    
    # Health routes
    health.register(app)
    
    # User routes
    users.register(app)
'''


HEALTH_PY = '''"""
Health Check Endpoints
"""

from nexaweb import Application
from nexaweb.core import Request, Response
from config import API_NAME, API_VERSION


def register(app: Application) -> None:
    """Register health routes."""
    
    @app.get("/health")
    async def health_check(request: Request) -> Response:
        """Basic health check."""
        return Response.json({"status": "healthy"})
    
    @app.get("/api/v1/health")
    async def api_health(request: Request) -> Response:
        """API health check with details."""
        return Response.json({
            "status": "healthy",
            "api": API_NAME,
            "version": API_VERSION,
        })
'''


USERS_PY = '''"""
User API Endpoints
"""

from typing import List, Optional
from nexaweb import Application
from nexaweb.core import Request, Response
from config import API_PREFIX


# Mock database
_users = [
    {"id": 1, "name": "Alice", "email": "alice@example.com"},
    {"id": 2, "name": "Bob", "email": "bob@example.com"},
]
_next_id = 3


def register(app: Application) -> None:
    """Register user routes."""
    
    @app.get(f"{API_PREFIX}/users")
    async def list_users(request: Request) -> Response:
        """List all users."""
        # Pagination
        page = int(request.query.get("page", 1))
        per_page = int(request.query.get("per_page", 20))
        
        start = (page - 1) * per_page
        end = start + per_page
        
        return Response.json({
            "data": _users[start:end],
            "meta": {
                "page": page,
                "per_page": per_page,
                "total": len(_users),
            }
        })
    
    @app.get(f"{API_PREFIX}/users/{{id}}")
    async def get_user(request: Request, id: int) -> Response:
        """Get user by ID."""
        user = next((u for u in _users if u["id"] == id), None)
        
        if not user:
            return Response.json(
                {"error": "User not found"},
                status=404,
            )
        
        return Response.json({"data": user})
    
    @app.post(f"{API_PREFIX}/users")
    async def create_user(request: Request) -> Response:
        """Create new user."""
        global _next_id
        
        data = await request.json()
        
        # Validate
        if not data.get("name") or not data.get("email"):
            return Response.json(
                {"error": "Name and email are required"},
                status=400,
            )
        
        # Create user
        user = {
            "id": _next_id,
            "name": data["name"],
            "email": data["email"],
        }
        
        _users.append(user)
        _next_id += 1
        
        return Response.json({"data": user}, status=201)
    
    @app.put(f"{API_PREFIX}/users/{{id}}")
    async def update_user(request: Request, id: int) -> Response:
        """Update user."""
        user = next((u for u in _users if u["id"] == id), None)
        
        if not user:
            return Response.json(
                {"error": "User not found"},
                status=404,
            )
        
        data = await request.json()
        
        if "name" in data:
            user["name"] = data["name"]
        if "email" in data:
            user["email"] = data["email"]
        
        return Response.json({"data": user})
    
    @app.delete(f"{API_PREFIX}/users/{{id}}")
    async def delete_user(request: Request, id: int) -> Response:
        """Delete user."""
        global _users
        
        user = next((u for u in _users if u["id"] == id), None)
        
        if not user:
            return Response.json(
                {"error": "User not found"},
                status=404,
            )
        
        _users = [u for u in _users if u["id"] != id]
        
        return Response.json({"message": "User deleted"})
'''


SCHEMAS_PY = '''"""
API Schemas (Pydantic-style validation)
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class UserCreate:
    """User creation schema."""
    name: str
    email: str


@dataclass  
class UserUpdate:
    """User update schema."""
    name: Optional[str] = None
    email: Optional[str] = None


@dataclass
class UserResponse:
    """User response schema."""
    id: int
    name: str
    email: str
'''


PYPROJECT_TOML = '''[project]
name = "{{ project_slug }}"
version = "0.1.0"
description = "{{ project_name }} API"
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


DOCKERFILE = '''FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s \\
    CMD curl -f http://localhost:8000/health || exit 1

# Run
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
'''


DOCKER_COMPOSE = '''version: "3.8"

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DEBUG=false
      - DATABASE_URL=postgresql://postgres:postgres@db/{{ project_slug }}
    depends_on:
      - db

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: {{ project_slug }}
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
'''


ENV_EXAMPLE = '''# API Configuration
API_NAME="{{ project_name }}"
API_VERSION=v1
DEBUG=true
SECRET_KEY=your-secret-key

# Database
DATABASE_URL=sqlite:///database.db

# Rate limiting
RATE_LIMIT=100/minute
'''


GITIGNORE = '''# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/

# Virtual environment
venv/
.venv/

# IDE
.idea/
.vscode/

# Environment
.env
.env.local

# Database
*.db
*.sqlite3

# Docker
.docker/
'''


README_MD = '''# {{ project_name }} API

RESTful API built with NexaWeb.

## Quick Start

```bash
# Install
pip install -e .

# Run
python app.py
```

API available at http://localhost:8000

## API Endpoints

### Health
- `GET /health` - Basic health check
- `GET /api/v1/health` - Detailed health check

### Users
- `GET /api/v1/users` - List users
- `GET /api/v1/users/{id}` - Get user
- `POST /api/v1/users` - Create user
- `PUT /api/v1/users/{id}` - Update user
- `DELETE /api/v1/users/{id}` - Delete user

## Docker

```bash
docker-compose up -d
```

## Testing

```bash
pip install -e ".[dev]"
pytest
```
'''


TEST_API_PY = '''"""
API Tests
"""

import pytest
from httpx import AsyncClient
from app import app


@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_list_users(client):
    response = await client.get("/api/v1/users")
    assert response.status_code == 200
    assert "data" in response.json()


@pytest.mark.asyncio
async def test_create_user(client):
    response = await client.post("/api/v1/users", json={
        "name": "Test User",
        "email": "test@example.com",
    })
    assert response.status_code == 201
    assert response.json()["data"]["name"] == "Test User"
'''


class APITemplate(ProjectTemplate):
    """
    API-focused project template.
    
    Creates a RESTful API with:
    - Versioned endpoints
    - CORS support
    - Docker configuration
    - OpenAPI-ready structure
    """
    
    name = "api"
    description = "RESTful API application"
    version = "1.0.0"
    
    def get_files(self) -> List[TemplateFile]:
        """Get template files."""
        return [
            # Root files
            TemplateFile("app.py", APP_PY),
            TemplateFile("config.py", CONFIG_PY),
            TemplateFile("pyproject.toml", PYPROJECT_TOML),
            TemplateFile(".gitignore", GITIGNORE),
            TemplateFile(".env.example", ENV_EXAMPLE),
            TemplateFile("README.md", README_MD),
            TemplateFile("Dockerfile", DOCKERFILE),
            TemplateFile("docker-compose.yml", DOCKER_COMPOSE),
            
            # API package
            TemplateFile("api/__init__.py", API_INIT),
            TemplateFile("api/schemas.py", SCHEMAS_PY),
            
            # API v1
            TemplateFile("api/v1/__init__.py", '"""API v1 endpoints."""\n'),
            TemplateFile("api/v1/health.py", HEALTH_PY),
            TemplateFile("api/v1/users.py", USERS_PY),
            
            # Tests
            TemplateFile("tests/__init__.py", '"""Tests."""\n'),
            TemplateFile("tests/test_api.py", TEST_API_PY),
        ]
    
    def get_directories(self) -> List[TemplateDirectory]:
        """Get template directories."""
        return [
            TemplateDirectory("api/v1/middleware"),
            TemplateDirectory("migrations"),
        ]
