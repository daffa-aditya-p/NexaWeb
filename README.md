# 🚀 NexaWeb

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-1.0.0--alpha.1-orange.svg)](https://github.com/nexaweb/nexaweb)

**Next-Generation Full-Stack Python Web Framework**

A high-performance, lightweight, full-stack web framework designed to compete with Laravel and React while being significantly lighter, faster, and more efficient.

---

## ✨ Features

- 🏗️ **Full Application Framework** - Not just an API framework, but a complete solution
- 📝 **PYXM Template Engine** - Custom HTML + Python expression templates
- ⚡ **Native Async Support** - ASGI-compatible for high concurrency
- 🔒 **Security-First Design** - Built-in CSRF, XSS protection, rate limiting
- 🗄️ **Lightweight ORM** - Active Record pattern with query builder
- 🔐 **Authentication** - JWT tokens, sessions, role-based guards
- ✅ **Validation System** - 30+ built-in rules with form support
- 🔌 **Plugin Architecture** - Extensible hooks and extension points
- 🛠️ **CLI Tools** - Project scaffolding and management
- 🚀 **Optional C++ Core** - Native extensions for performance-critical code

---

## 📦 Installation

```bash
pip install nexaweb
```

Or install from source:

```bash
git clone https://github.com/nexaweb/nexaweb.git
cd nexaweb
pip install -e .
```

---

## 🚀 Quick Start

### Create a New Project

```bash
nexaweb create myapp
cd myapp
nexaweb serve
```

### Minimal Example

```python
from nexaweb import Application, Request, Response

app = Application()

@app.get("/")
async def index(request: Request) -> Response:
    return Response.html("<h1>Hello, NexaWeb!</h1>")

@app.get("/api/users")
async def users(request: Request) -> Response:
    return Response.json({"users": ["Alice", "Bob"]})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", reload=True)
```

---

## 📚 Framework Components

### Core (`nexaweb.core`)
- **Application** - ASGI application with middleware support
- **Router** - High-performance route matching with parameters
- **Request/Response** - Full HTTP request/response handling
- **Middleware** - Composable middleware pipeline
- **WebSocket** - Real-time bidirectional communication
- **Config** - Flexible configuration management

### PYXM Template Engine (`nexaweb.pyxm`)
Custom template format combining HTML with Python expressions:

```html
<!-- templates/index.pyxm -->
<html>
<head><title>{{ title }}</title></head>
<body>
    <h1>{{ greeting }}</h1>
    {% for user in users %}
        <p>{{ user.name }} - {{ user.email }}</p>
    {% endfor %}
</body>
</html>
```

### Security (`nexaweb.security`)
- **CSRF Protection** - Double-submit cookie pattern
- **XSS Prevention** - Content sanitization
- **Rate Limiting** - Token bucket algorithm
- **Sandboxed Execution** - Safe template evaluation

### Authentication (`nexaweb.auth`)
```python
from nexaweb.auth import Authenticator, JWTHandler

# JWT Authentication
jwt = JWTHandler(secret="your-secret")
tokens = jwt.create_tokens({"user_id": 123})

# Session-based Auth
auth = Authenticator(user_provider)
user = await auth.attempt(email, password)
```

### ORM (`nexaweb.orm`)
```python
from nexaweb.orm import Model, StringField, IntegerField

class User(Model):
    __tablename__ = "users"
    
    id = IntegerField(primary_key=True)
    name = StringField(max_length=100)
    email = StringField(max_length=255, unique=True)

# Query Builder
users = await User.query() \
    .where("active", True) \
    .order_by("name") \
    .limit(10) \
    .all()
```

### Validation (`nexaweb.validation`)
```python
from nexaweb.validation import Validator

data = {"email": "user@example.com", "age": 25}
rules = {
    "email": "required|email",
    "age": "required|integer|min:18",
}

result = await Validator.validate(data, rules)
```

### CLI Tools (`nexaweb.cli`)
```bash
nexaweb create myapp       # Create new project
nexaweb serve              # Run development server
nexaweb build              # Build for production
nexaweb migrate            # Run database migrations
nexaweb make controller    # Generate components
nexaweb routes             # List all routes
nexaweb shell              # Interactive shell
```

### Plugin System (`nexaweb.plugins`)
```python
from nexaweb.plugins import Plugin

class MyPlugin(Plugin):
    class Meta:
        name = "my-plugin"
        version = "1.0.0"
    
    async def boot(self, app):
        @app.get("/plugin-route")
        async def plugin_route(request):
            return Response.json({"plugin": "active"})
```

---

## 🏗️ Project Structure

```
myapp/
├── app.py              # Application entry point
├── config.py           # Configuration
├── routes.py           # Route definitions
├── app/
│   ├── controllers/    # Request handlers
│   ├── models/         # Database models
│   ├── middleware/     # Custom middleware
│   └── services/       # Business logic
├── templates/          # PYXM templates
├── static/             # Static assets
├── tests/              # Test files
└── migrations/         # Database migrations
```

---

## 📖 Documentation

- [Getting Started](https://nexaweb.dev/docs/getting-started)
- [Routing](https://nexaweb.dev/docs/routing)
- [Templates](https://nexaweb.dev/docs/templates)
- [Database](https://nexaweb.dev/docs/database)
- [Authentication](https://nexaweb.dev/docs/auth)
- [Validation](https://nexaweb.dev/docs/validation)
- [Plugins](https://nexaweb.dev/docs/plugins)
- [Deployment](https://nexaweb.dev/docs/deployment)

---

## 📤 Publishing to PyPI

Tutorial lengkap untuk upload NexaWeb ke PyPI:

### 1. Persiapan Akun PyPI

```bash
# 1. Buat akun di https://pypi.org/account/register/
# 2. Buat API Token di https://pypi.org/manage/account/token/
#    - Pilih scope "Entire account" (untuk upload pertama)
#    - Simpan token dengan baik (hanya ditampilkan sekali!)
```

### 2. Install Build Tools

```bash
pip install --upgrade pip build twine
```

### 3. Build Package

```bash
# Build source distribution dan wheel
python -m build

# Akan menghasilkan:
# dist/
# ├── nexaweb-1.0.0a1-py3-none-any.whl
# └── nexaweb-1.0.0a1.tar.gz
```

### 4. Test di TestPyPI (Opsional tapi Disarankan)

```bash
# Upload ke TestPyPI dulu untuk testing
twine upload --repository testpypi dist/*

# Username: __token__
# Password: [paste TestPyPI API token]

# Test install dari TestPyPI
pip install --index-url https://test.pypi.org/simple/ nexaweb
```

### 5. Upload ke PyPI (Production)

```bash
# Upload ke PyPI production
twine upload dist/*

# Username: __token__
# Password: [paste PyPI API token]
```

### 6. Setup `.pypirc` (Opsional)

Buat file `~/.pypirc` agar tidak perlu input token setiap upload:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-xxxxxxxxxxxxxxxxxxxx

[testpypi]
username = __token__
password = pypi-xxxxxxxxxxxxxxxxxxxx
```

Lalu upload cukup dengan:
```bash
twine upload dist/*
```

### 7. Verifikasi Upload

```bash
# Cek di browser
# https://pypi.org/project/nexaweb/

# Test install
pip install nexaweb

# Verifikasi
python -c "import nexaweb; print(nexaweb.__version__)"
```

### 8. Update Version (untuk rilis berikutnya)

Edit `pyproject.toml`:
```toml
[project]
version = "1.0.0-alpha.2"  # Ubah versi
```

Lalu ulangi langkah 3-5.

### 📋 Checklist Sebelum Upload

- [ ] Update version di `pyproject.toml`
- [ ] Update `README.md` jika ada perubahan
- [ ] Pastikan semua tests pass
- [ ] Review dependencies di `pyproject.toml`
- [ ] Hapus folder `dist/` lama: `rm -rf dist/`
- [ ] Build ulang: `python -m build`
- [ ] Test di TestPyPI dulu (opsional)

### 🔧 Troubleshooting

**Error: Package already exists**
```bash
# Hapus versi lama di dist/ dan build ulang dengan versi baru
rm -rf dist/ && python -m build
```

**Error: Invalid API token**
```bash
# Pastikan format token benar
# Username: __token__
# Password: pypi-xxx... (termasuk prefix "pypi-")
```

**Error: Missing metadata**
```bash
# Pastikan README.md dan pyproject.toml lengkap
# Verifikasi dengan: twine check dist/*
```

---

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md).

```bash
# Development setup
git clone https://github.com/daffa-aditya-p/NexaWeb.git
cd nexaweb
pip install -e ".[dev]"
pytest
```

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

Built with inspiration from Laravel, FastAPI, Django, and React.

---

<p align="center">
  Made with ❤️ by the NexaWeb Team
</p>
