"""
NexaWeb Minimal Template
========================

Minimal project template for small applications.
"""

from __future__ import annotations

from typing import List

from nexaweb.templates.base import ProjectTemplate, TemplateFile, TemplateDirectory


# Template content
APP_PY = '''"""
{{ project_name }}
"""

from nexaweb import Application
from nexaweb.core import Request, Response


app = Application()


@app.get("/")
async def index(request: Request) -> Response:
    """Home page."""
    return Response.html("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{{ project_name }}</title>
        <style>
            body {
                font-family: system-ui, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 2rem;
            }
        </style>
    </head>
    <body>
        <h1>Welcome to {{ project_name }}</h1>
        <p>Your NexaWeb app is running!</p>
    </body>
    </html>
    """)


@app.get("/api/health")
async def health(request: Request) -> Response:
    """Health check endpoint."""
    return Response.json({"status": "ok"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
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

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"
'''


GITIGNORE = '''# Python
__pycache__/
*.py[cod]
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

# Environment
.env
.env.local
'''


README_MD = '''# {{ project_name }}

A minimal NexaWeb application.

## Quick Start

```bash
# Install dependencies
pip install -e .

# Run development server
python app.py
```

Visit http://127.0.0.1:8000
'''


class MinimalTemplate(ProjectTemplate):
    """
    Minimal project template.
    
    Creates a simple single-file NexaWeb application.
    """
    
    name = "minimal"
    description = "Minimal single-file application"
    version = "1.0.0"
    
    def get_files(self) -> List[TemplateFile]:
        """Get template files."""
        return [
            TemplateFile("app.py", APP_PY),
            TemplateFile("pyproject.toml", PYPROJECT_TOML),
            TemplateFile(".gitignore", GITIGNORE),
            TemplateFile("README.md", README_MD),
        ]
    
    def get_directories(self) -> List[TemplateDirectory]:
        """Get template directories."""
        return [
            TemplateDirectory("static"),
            TemplateDirectory("templates"),
        ]
