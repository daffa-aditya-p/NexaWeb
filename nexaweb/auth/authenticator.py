"""
NexaWeb Authenticator
=====================

Core authentication system with pluggable strategies.

Features:
- Multiple hash strategies (bcrypt, argon2, plain)
- Pluggable user providers
- Remember me tokens
- Login throttling support
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol, Set


@dataclass
class User:
    """
    Base user model.
    
    Applications should extend this or create their own
    user class with additional fields.
    """
    
    id: Any
    email: str
    password_hash: str
    name: str = ""
    roles: Set[str] = field(default_factory=set)
    permissions: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    created_at: Optional[float] = None
    updated_at: Optional[float] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if isinstance(self.roles, (list, tuple)):
            self.roles = set(self.roles)
        if isinstance(self.permissions, (list, tuple)):
            self.permissions = set(self.permissions)
            
    def has_role(self, role: str) -> bool:
        """Check if user has a role."""
        return role in self.roles
        
    def has_permission(self, permission: str) -> bool:
        """Check if user has a permission."""
        return permission in self.permissions
        
    def has_any_role(self, roles: List[str]) -> bool:
        """Check if user has any of the given roles."""
        return bool(self.roles & set(roles))
        
    def has_all_roles(self, roles: List[str]) -> bool:
        """Check if user has all given roles."""
        return set(roles).issubset(self.roles)
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (for JWT claims etc.)."""
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "roles": list(self.roles),
            "permissions": list(self.permissions),
        }


class UserProvider(Protocol):
    """
    Protocol for user providers.
    
    Implement this to load users from any data source.
    """
    
    async def find_by_id(self, user_id: Any) -> Optional[User]:
        """Find user by ID."""
        ...
        
    async def find_by_email(self, email: str) -> Optional[User]:
        """Find user by email."""
        ...
        
    async def find_by_credentials(
        self,
        email: str,
        password: str,
    ) -> Optional[User]:
        """Find user by credentials."""
        ...
        
    async def find_by_remember_token(self, token: str) -> Optional[User]:
        """Find user by remember token."""
        ...
        
    async def update_remember_token(
        self,
        user: User,
        token: Optional[str],
    ) -> None:
        """Update user's remember token."""
        ...


class MemoryUserProvider:
    """
    In-memory user provider for testing.
    """
    
    def __init__(self, hash_strategy: Optional[HashStrategy] = None) -> None:
        self.users: Dict[Any, User] = {}
        self.email_index: Dict[str, Any] = {}
        self.remember_tokens: Dict[str, Any] = {}
        self.hash_strategy = hash_strategy or PlainHashStrategy()
        
    def add_user(self, user: User) -> None:
        """Add user to store."""
        self.users[user.id] = user
        self.email_index[user.email.lower()] = user.id
        
    def create_user(
        self,
        email: str,
        password: str,
        **kwargs,
    ) -> User:
        """Create and add a new user."""
        user_id = kwargs.pop("id", len(self.users) + 1)
        password_hash = self.hash_strategy.hash(password)
        
        user = User(
            id=user_id,
            email=email,
            password_hash=password_hash,
            **kwargs,
        )
        self.add_user(user)
        return user
        
    async def find_by_id(self, user_id: Any) -> Optional[User]:
        """Find user by ID."""
        return self.users.get(user_id)
        
    async def find_by_email(self, email: str) -> Optional[User]:
        """Find user by email."""
        user_id = self.email_index.get(email.lower())
        if user_id is not None:
            return self.users.get(user_id)
        return None
        
    async def find_by_credentials(
        self,
        email: str,
        password: str,
    ) -> Optional[User]:
        """Find user by credentials."""
        user = await self.find_by_email(email)
        if user and self.hash_strategy.verify(password, user.password_hash):
            return user
        return None
        
    async def find_by_remember_token(self, token: str) -> Optional[User]:
        """Find user by remember token."""
        user_id = self.remember_tokens.get(token)
        if user_id is not None:
            return self.users.get(user_id)
        return None
        
    async def update_remember_token(
        self,
        user: User,
        token: Optional[str],
    ) -> None:
        """Update user's remember token."""
        # Remove old token
        old_tokens = [t for t, uid in self.remember_tokens.items() if uid == user.id]
        for t in old_tokens:
            del self.remember_tokens[t]
            
        # Set new token
        if token:
            self.remember_tokens[token] = user.id


class HashStrategy(ABC):
    """
    Abstract hash strategy for passwords.
    """
    
    @abstractmethod
    def hash(self, password: str) -> str:
        """Hash a password."""
        ...
        
    @abstractmethod
    def verify(self, password: str, hash: str) -> bool:
        """Verify password against hash."""
        ...
        
    @abstractmethod
    def needs_rehash(self, hash: str) -> bool:
        """Check if hash needs to be rehashed."""
        ...


class PlainHashStrategy(HashStrategy):
    """
    Plain text hash strategy (for testing only!).
    
    DO NOT USE IN PRODUCTION!
    """
    
    def hash(self, password: str) -> str:
        """Hash password with SHA-256."""
        return hashlib.sha256(password.encode()).hexdigest()
        
    def verify(self, password: str, hash: str) -> bool:
        """Verify password."""
        return hmac.compare_digest(self.hash(password), hash)
        
    def needs_rehash(self, hash: str) -> bool:
        """Plain hash never needs rehash."""
        return False


class BcryptHashStrategy(HashStrategy):
    """
    Bcrypt hash strategy.
    
    Requires: pip install bcrypt
    """
    
    def __init__(self, rounds: int = 12) -> None:
        self.rounds = rounds
        
        try:
            import bcrypt
            self._bcrypt = bcrypt
        except ImportError:
            self._bcrypt = None
            
    def hash(self, password: str) -> str:
        """Hash password with bcrypt."""
        if self._bcrypt is None:
            raise ImportError("bcrypt is required for BcryptHashStrategy")
            
        salt = self._bcrypt.gensalt(rounds=self.rounds)
        return self._bcrypt.hashpw(password.encode(), salt).decode()
        
    def verify(self, password: str, hash: str) -> bool:
        """Verify password."""
        if self._bcrypt is None:
            raise ImportError("bcrypt is required for BcryptHashStrategy")
            
        try:
            return self._bcrypt.checkpw(password.encode(), hash.encode())
        except ValueError:
            return False
            
    def needs_rehash(self, hash: str) -> bool:
        """Check if hash needs rehash (different rounds)."""
        if self._bcrypt is None:
            return False
            
        try:
            # Parse rounds from hash
            parts = hash.split("$")
            if len(parts) >= 4:
                current_rounds = int(parts[2])
                return current_rounds != self.rounds
        except (ValueError, IndexError):
            pass
        return False


class Argon2HashStrategy(HashStrategy):
    """
    Argon2 hash strategy (recommended).
    
    Requires: pip install argon2-cffi
    """
    
    def __init__(
        self,
        time_cost: int = 3,
        memory_cost: int = 65536,
        parallelism: int = 4,
    ) -> None:
        self.time_cost = time_cost
        self.memory_cost = memory_cost
        self.parallelism = parallelism
        
        try:
            from argon2 import PasswordHasher
            from argon2.exceptions import VerifyMismatchError
            
            self._hasher = PasswordHasher(
                time_cost=time_cost,
                memory_cost=memory_cost,
                parallelism=parallelism,
            )
            self._mismatch_error = VerifyMismatchError
        except ImportError:
            self._hasher = None
            self._mismatch_error = Exception
            
    def hash(self, password: str) -> str:
        """Hash password with Argon2."""
        if self._hasher is None:
            raise ImportError("argon2-cffi is required for Argon2HashStrategy")
            
        return self._hasher.hash(password)
        
    def verify(self, password: str, hash: str) -> bool:
        """Verify password."""
        if self._hasher is None:
            raise ImportError("argon2-cffi is required for Argon2HashStrategy")
            
        try:
            self._hasher.verify(hash, password)
            return True
        except self._mismatch_error:
            return False
        except Exception:
            return False
            
    def needs_rehash(self, hash: str) -> bool:
        """Check if hash needs rehash."""
        if self._hasher is None:
            return False
            
        try:
            return self._hasher.check_needs_rehash(hash)
        except Exception:
            return False


class AuthStatus(Enum):
    """Authentication result status."""
    
    SUCCESS = "success"
    INVALID_CREDENTIALS = "invalid_credentials"
    USER_NOT_FOUND = "user_not_found"
    USER_INACTIVE = "user_inactive"
    ACCOUNT_LOCKED = "account_locked"
    TWO_FACTOR_REQUIRED = "two_factor_required"


@dataclass
class AuthResult:
    """
    Result of authentication attempt.
    """
    
    status: AuthStatus
    user: Optional[User] = None
    message: str = ""
    remember_token: Optional[str] = None
    requires_2fa: bool = False
    
    @property
    def success(self) -> bool:
        """Check if authentication was successful."""
        return self.status == AuthStatus.SUCCESS
        
    @property
    def failed(self) -> bool:
        """Check if authentication failed."""
        return self.status != AuthStatus.SUCCESS


class Authenticator:
    """
    Main authentication service.
    
    Handles user authentication with support for:
    - Multiple user providers
    - Password hashing strategies
    - Remember me tokens
    - Login events
    
    Example:
        provider = MemoryUserProvider()
        provider.create_user("admin@example.com", "secret", roles={"admin"})
        
        auth = Authenticator(provider)
        
        result = await auth.attempt("admin@example.com", "secret")
        if result.success:
            user = result.user
            print(f"Welcome, {user.name}!")
    """
    
    def __init__(
        self,
        provider: UserProvider,
        hash_strategy: Optional[HashStrategy] = None,
    ) -> None:
        """
        Initialize authenticator.
        
        Args:
            provider: User provider implementation
            hash_strategy: Password hash strategy
        """
        self.provider = provider
        self.hash_strategy = hash_strategy or PlainHashStrategy()
        
        # Event handlers
        self._on_login: List[Callable] = []
        self._on_logout: List[Callable] = []
        self._on_failed: List[Callable] = []
        
        # Current user (request-scoped)
        self._current_user: Optional[User] = None
        
    @property
    def user(self) -> Optional[User]:
        """Get current authenticated user."""
        return self._current_user
        
    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self._current_user is not None
        
    async def attempt(
        self,
        email: str,
        password: str,
        remember: bool = False,
    ) -> AuthResult:
        """
        Attempt to authenticate user.
        
        Args:
            email: User email
            password: Plain text password
            remember: Whether to create remember token
            
        Returns:
            AuthResult with status and user if successful
        """
        # Find user
        user = await self.provider.find_by_email(email)
        
        if user is None:
            result = AuthResult(
                status=AuthStatus.USER_NOT_FOUND,
                message="User not found",
            )
            await self._fire_failed(email, result)
            return result
            
        # Check if active
        if not user.is_active:
            result = AuthResult(
                status=AuthStatus.USER_INACTIVE,
                message="User account is inactive",
            )
            await self._fire_failed(email, result)
            return result
            
        # Verify password
        if not self.hash_strategy.verify(password, user.password_hash):
            result = AuthResult(
                status=AuthStatus.INVALID_CREDENTIALS,
                message="Invalid password",
            )
            await self._fire_failed(email, result)
            return result
            
        # Check if password needs rehash
        if self.hash_strategy.needs_rehash(user.password_hash):
            user.password_hash = self.hash_strategy.hash(password)
            
        # Create remember token if requested
        remember_token = None
        if remember:
            remember_token = self._generate_remember_token()
            await self.provider.update_remember_token(user, remember_token)
            
        # Set current user
        self._current_user = user
        
        # Create result
        result = AuthResult(
            status=AuthStatus.SUCCESS,
            user=user,
            message="Authentication successful",
            remember_token=remember_token,
        )
        
        # Fire login event
        await self._fire_login(user, remember)
        
        return result
        
    async def login(self, user: User) -> None:
        """
        Log in user directly (without credentials).
        
        Useful for OAuth, passwordless login, etc.
        """
        self._current_user = user
        await self._fire_login(user, False)
        
    async def logout(self) -> None:
        """Log out current user."""
        if self._current_user:
            user = self._current_user
            await self.provider.update_remember_token(user, None)
            self._current_user = None
            await self._fire_logout(user)
            
    async def validate_remember_token(self, token: str) -> Optional[User]:
        """
        Validate remember token and return user.
        """
        user = await self.provider.find_by_remember_token(token)
        if user and user.is_active:
            self._current_user = user
            return user
        return None
        
    async def validate_session(self, user_id: Any) -> Optional[User]:
        """
        Validate session by loading user.
        """
        user = await self.provider.find_by_id(user_id)
        if user and user.is_active:
            self._current_user = user
            return user
        return None
        
    def on_login(self, callback: Callable) -> None:
        """Register login event handler."""
        self._on_login.append(callback)
        
    def on_logout(self, callback: Callable) -> None:
        """Register logout event handler."""
        self._on_logout.append(callback)
        
    def on_failed(self, callback: Callable) -> None:
        """Register failed login event handler."""
        self._on_failed.append(callback)
        
    def _generate_remember_token(self) -> str:
        """Generate secure remember token."""
        return secrets.token_urlsafe(32)
        
    async def _fire_login(self, user: User, remember: bool) -> None:
        """Fire login event."""
        for callback in self._on_login:
            try:
                result = callback(user, remember)
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                pass
                
    async def _fire_logout(self, user: User) -> None:
        """Fire logout event."""
        for callback in self._on_logout:
            try:
                result = callback(user)
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                pass
                
    async def _fire_failed(self, email: str, result: AuthResult) -> None:
        """Fire failed login event."""
        for callback in self._on_failed:
            try:
                result = callback(email, result)
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                pass
