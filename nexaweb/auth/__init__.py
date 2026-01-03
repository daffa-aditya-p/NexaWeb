"""
NexaWeb Authentication & Session Management
============================================

Complete auth system with:
- Multiple authentication strategies
- Session management with multiple backends
- JWT token handling
- Route guards and permissions
"""

from nexaweb.auth.authenticator import (
    Authenticator,
    AuthResult,
    User,
    UserProvider,
    MemoryUserProvider,
    HashStrategy,
    BcryptHashStrategy,
    Argon2HashStrategy,
    PlainHashStrategy,
)
from nexaweb.auth.session import (
    Session,
    SessionManager,
    SessionBackend,
    MemorySessionBackend,
    FileSessionBackend,
    CookieSessionBackend,
)
from nexaweb.auth.jwt_handler import (
    JWTHandler,
    JWTConfig,
    TokenPair,
    JWTError,
    TokenExpiredError,
    InvalidTokenError,
)
from nexaweb.auth.guards import (
    Guard,
    AuthGuard,
    RoleGuard,
    PermissionGuard,
    GuestGuard,
    CompositeGuard,
    require_auth,
    require_role,
    require_permission,
)

__all__ = [
    # Authenticator
    "Authenticator",
    "AuthResult",
    "User",
    "UserProvider",
    "MemoryUserProvider",
    "HashStrategy",
    "BcryptHashStrategy",
    "Argon2HashStrategy",
    "PlainHashStrategy",
    # Session
    "Session",
    "SessionManager",
    "SessionBackend",
    "MemorySessionBackend",
    "FileSessionBackend",
    "CookieSessionBackend",
    # JWT
    "JWTHandler",
    "JWTConfig",
    "TokenPair",
    "JWTError",
    "TokenExpiredError",
    "InvalidTokenError",
    # Guards
    "Guard",
    "AuthGuard",
    "RoleGuard",
    "PermissionGuard",
    "GuestGuard",
    "CompositeGuard",
    "require_auth",
    "require_role",
    "require_permission",
]
