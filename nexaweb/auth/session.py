"""
NexaWeb Session Management
==========================

Session handling with multiple backend support.

Features:
- Multiple storage backends (memory, file, cookie)
- Session regeneration for security
- Flash messages
- Lazy loading
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Set

# Try to import encryption library
try:
    from cryptography.fernet import Fernet
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False


@dataclass
class SessionConfig:
    """Session configuration."""
    
    # Session cookie name
    cookie_name: str = "nexaweb_session"
    
    # Session lifetime (seconds)
    lifetime: int = 7200  # 2 hours
    
    # Expire session on browser close
    expire_on_close: bool = False
    
    # Cookie path
    path: str = "/"
    
    # Cookie domain
    domain: Optional[str] = None
    
    # Secure cookie (HTTPS only)
    secure: bool = True
    
    # HTTP only cookie
    http_only: bool = True
    
    # Same site policy
    same_site: str = "lax"
    
    # Session ID length (bytes)
    id_length: int = 32
    
    # Encryption key (for cookie backend)
    encryption_key: Optional[bytes] = None


class SessionBackend(ABC):
    """
    Abstract session backend.
    
    Implement this to store sessions in any storage system.
    """
    
    @abstractmethod
    async def read(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Read session data."""
        ...
        
    @abstractmethod
    async def write(
        self,
        session_id: str,
        data: Dict[str, Any],
        lifetime: int,
    ) -> None:
        """Write session data."""
        ...
        
    @abstractmethod
    async def destroy(self, session_id: str) -> None:
        """Destroy session."""
        ...
        
    @abstractmethod
    async def gc(self) -> int:
        """Garbage collect expired sessions. Returns count."""
        ...


class MemorySessionBackend(SessionBackend):
    """
    In-memory session backend.
    
    Suitable for development and single-process applications.
    Sessions are lost on restart.
    """
    
    def __init__(self) -> None:
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._expires: Dict[str, float] = {}
        
    async def read(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Read session data."""
        # Check expiration
        if session_id in self._expires:
            if time.time() > self._expires[session_id]:
                await self.destroy(session_id)
                return None
                
        return self._sessions.get(session_id)
        
    async def write(
        self,
        session_id: str,
        data: Dict[str, Any],
        lifetime: int,
    ) -> None:
        """Write session data."""
        self._sessions[session_id] = data
        self._expires[session_id] = time.time() + lifetime
        
    async def destroy(self, session_id: str) -> None:
        """Destroy session."""
        self._sessions.pop(session_id, None)
        self._expires.pop(session_id, None)
        
    async def gc(self) -> int:
        """Garbage collect expired sessions."""
        now = time.time()
        expired = [
            sid for sid, exp in self._expires.items()
            if now > exp
        ]
        
        for sid in expired:
            await self.destroy(sid)
            
        return len(expired)


class FileSessionBackend(SessionBackend):
    """
    File-based session backend.
    
    Stores sessions as JSON files.
    Suitable for small to medium applications.
    """
    
    def __init__(self, path: str = "/tmp/nexaweb_sessions") -> None:
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        
    def _get_path(self, session_id: str) -> Path:
        """Get path for session file."""
        # Hash session ID for filename
        filename = hashlib.sha256(session_id.encode()).hexdigest()
        return self.path / f"{filename}.json"
        
    async def read(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Read session data."""
        path = self._get_path(session_id)
        
        if not path.exists():
            return None
            
        try:
            with open(path, "r") as f:
                data = json.load(f)
                
            # Check expiration
            if time.time() > data.get("_expires", 0):
                await self.destroy(session_id)
                return None
                
            return data.get("data", {})
            
        except (json.JSONDecodeError, OSError):
            return None
            
    async def write(
        self,
        session_id: str,
        data: Dict[str, Any],
        lifetime: int,
    ) -> None:
        """Write session data."""
        path = self._get_path(session_id)
        
        session_data = {
            "data": data,
            "_expires": time.time() + lifetime,
            "_created": time.time(),
        }
        
        with open(path, "w") as f:
            json.dump(session_data, f)
            
    async def destroy(self, session_id: str) -> None:
        """Destroy session."""
        path = self._get_path(session_id)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
            
    async def gc(self) -> int:
        """Garbage collect expired sessions."""
        count = 0
        now = time.time()
        
        try:
            for path in self.path.glob("*.json"):
                try:
                    with open(path, "r") as f:
                        data = json.load(f)
                        
                    if now > data.get("_expires", 0):
                        path.unlink()
                        count += 1
                        
                except (json.JSONDecodeError, OSError):
                    # Remove invalid files
                    try:
                        path.unlink()
                        count += 1
                    except OSError:
                        pass
                        
        except OSError:
            pass
            
        return count


class CookieSessionBackend(SessionBackend):
    """
    Cookie-based session backend.
    
    Stores session data in encrypted cookies.
    No server-side storage required.
    
    Warning: Cookie size is limited (~4KB).
    Use for small session data only.
    """
    
    def __init__(self, secret_key: bytes) -> None:
        """
        Initialize with encryption key.
        
        Args:
            secret_key: 32-byte encryption key
        """
        if not HAS_CRYPTOGRAPHY:
            raise ImportError("cryptography is required for CookieSessionBackend")
            
        # Derive key for Fernet
        import base64
        key = base64.urlsafe_b64encode(
            hashlib.sha256(secret_key).digest()
        )
        self._fernet = Fernet(key)
        
        # In-memory cache for current request
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._encrypted: Dict[str, bytes] = {}
        
    async def read(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Read session data from cache."""
        return self._cache.get(session_id)
        
    async def write(
        self,
        session_id: str,
        data: Dict[str, Any],
        lifetime: int,
    ) -> None:
        """Write session data to cache."""
        self._cache[session_id] = data
        
        # Encrypt for cookie
        payload = json.dumps({
            "data": data,
            "expires": time.time() + lifetime,
        }).encode()
        
        self._encrypted[session_id] = self._fernet.encrypt(payload)
        
    async def destroy(self, session_id: str) -> None:
        """Destroy session."""
        self._cache.pop(session_id, None)
        self._encrypted.pop(session_id, None)
        
    async def gc(self) -> int:
        """Cookie backend doesn't need GC."""
        return 0
        
    def decrypt_cookie(self, encrypted: bytes) -> Optional[Dict[str, Any]]:
        """Decrypt session cookie."""
        try:
            payload = self._fernet.decrypt(encrypted)
            data = json.loads(payload)
            
            # Check expiration
            if time.time() > data.get("expires", 0):
                return None
                
            return data.get("data", {})
            
        except Exception:
            return None
            
    def get_encrypted(self, session_id: str) -> Optional[bytes]:
        """Get encrypted session data for cookie."""
        return self._encrypted.get(session_id)


class Session:
    """
    Session object for storing user data.
    
    Provides dict-like access to session data with
    additional features like flash messages.
    
    Example:
        session["user_id"] = 123
        session.flash("message", "Welcome!")
        
        # In next request
        messages = session.get_flash("message")  # ["Welcome!"]
    """
    
    def __init__(
        self,
        session_id: str,
        data: Optional[Dict[str, Any]] = None,
        is_new: bool = False,
    ) -> None:
        self._id = session_id
        self._data = data or {}
        self._is_new = is_new
        self._modified = False
        self._regenerated = False
        
    @property
    def id(self) -> str:
        """Get session ID."""
        return self._id
        
    @property
    def is_new(self) -> bool:
        """Check if session is new."""
        return self._is_new
        
    @property
    def is_modified(self) -> bool:
        """Check if session was modified."""
        return self._modified
        
    def __getitem__(self, key: str) -> Any:
        """Get session value."""
        return self._data[key]
        
    def __setitem__(self, key: str, value: Any) -> None:
        """Set session value."""
        self._data[key] = value
        self._modified = True
        
    def __delitem__(self, key: str) -> None:
        """Delete session value."""
        del self._data[key]
        self._modified = True
        
    def __contains__(self, key: str) -> bool:
        """Check if key exists."""
        return key in self._data
        
    def __iter__(self) -> Iterator[str]:
        """Iterate over keys."""
        return iter(self._data)
        
    def __len__(self) -> int:
        """Get number of items."""
        return len(self._data)
        
    def get(self, key: str, default: Any = None) -> Any:
        """Get session value with default."""
        return self._data.get(key, default)
        
    def set(self, key: str, value: Any) -> None:
        """Set session value."""
        self[key] = value
        
    def pop(self, key: str, default: Any = None) -> Any:
        """Pop session value."""
        self._modified = True
        return self._data.pop(key, default)
        
    def clear(self) -> None:
        """Clear all session data."""
        self._data.clear()
        self._modified = True
        
    def items(self):
        """Get session items."""
        return self._data.items()
        
    def keys(self):
        """Get session keys."""
        return self._data.keys()
        
    def values(self):
        """Get session values."""
        return self._data.values()
        
    def flash(self, key: str, value: Any) -> None:
        """
        Add flash message.
        
        Flash messages are available only in the next request.
        """
        flash_key = f"_flash_{key}"
        if flash_key not in self._data:
            self._data[flash_key] = []
        self._data[flash_key].append(value)
        self._modified = True
        
    def get_flash(self, key: str) -> list:
        """
        Get and clear flash messages.
        """
        flash_key = f"_flash_{key}"
        messages = self._data.pop(flash_key, [])
        if messages:
            self._modified = True
        return messages
        
    def has_flash(self, key: str) -> bool:
        """Check if flash messages exist."""
        return f"_flash_{key}" in self._data
        
    def regenerate(self, new_id: str) -> None:
        """
        Regenerate session ID (for security).
        
        Call after login to prevent session fixation.
        """
        self._id = new_id
        self._regenerated = True
        self._modified = True
        
    def to_dict(self) -> Dict[str, Any]:
        """Get session data as dict."""
        return dict(self._data)
        
    def age(self) -> Optional[float]:
        """Get session age in seconds."""
        created = self._data.get("_created")
        if created:
            return time.time() - created
        return None


class SessionManager:
    """
    Session manager for handling session lifecycle.
    
    Manages session creation, loading, saving, and cleanup.
    
    Example:
        manager = SessionManager()
        
        # Load or create session
        session = await manager.start(request)
        
        # Use session
        session["user_id"] = 123
        
        # Save session
        await manager.save(session, response)
    """
    
    def __init__(
        self,
        backend: Optional[SessionBackend] = None,
        config: Optional[SessionConfig] = None,
    ) -> None:
        """
        Initialize session manager.
        
        Args:
            backend: Storage backend
            config: Session configuration
        """
        self.backend = backend or MemorySessionBackend()
        self.config = config or SessionConfig()
        
    async def start(self, request: Any) -> Session:
        """
        Start or resume session.
        
        Args:
            request: Request object with cookies
            
        Returns:
            Session object
        """
        # Get session ID from cookie
        session_id = self._get_session_id(request)
        
        if session_id:
            # Try to load existing session
            data = await self.backend.read(session_id)
            if data is not None:
                return Session(session_id, data, is_new=False)
                
        # Create new session
        session_id = self._generate_id()
        data = {"_created": time.time()}
        
        return Session(session_id, data, is_new=True)
        
    async def save(self, session: Session, response: Any) -> None:
        """
        Save session and set cookie.
        
        Args:
            session: Session to save
            response: Response object for setting cookie
        """
        if not session.is_modified:
            return
            
        # Save to backend
        await self.backend.write(
            session.id,
            session.to_dict(),
            self.config.lifetime,
        )
        
        # Set cookie
        self._set_cookie(response, session.id)
        
    async def destroy(self, session: Session, response: Any) -> None:
        """
        Destroy session and clear cookie.
        """
        await self.backend.destroy(session.id)
        self._clear_cookie(response)
        
    async def regenerate(self, session: Session) -> str:
        """
        Regenerate session ID.
        
        Use after login to prevent session fixation attacks.
        
        Returns:
            New session ID
        """
        old_id = session.id
        new_id = self._generate_id()
        
        # Migrate data
        await self.backend.destroy(old_id)
        session.regenerate(new_id)
        
        return new_id
        
    async def gc(self) -> int:
        """
        Run garbage collection on expired sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        return await self.backend.gc()
        
    def _generate_id(self) -> str:
        """Generate secure session ID."""
        return secrets.token_urlsafe(self.config.id_length)
        
    def _get_session_id(self, request: Any) -> Optional[str]:
        """Extract session ID from request."""
        # Try to get from cookies
        cookies = getattr(request, "cookies", {})
        return cookies.get(self.config.cookie_name)
        
    def _set_cookie(self, response: Any, session_id: str) -> None:
        """Set session cookie on response."""
        cookie_options = {
            "max_age": None if self.config.expire_on_close else self.config.lifetime,
            "path": self.config.path,
            "secure": self.config.secure,
            "httponly": self.config.http_only,
            "samesite": self.config.same_site,
        }
        
        if self.config.domain:
            cookie_options["domain"] = self.config.domain
            
        if hasattr(response, "set_cookie"):
            response.set_cookie(
                self.config.cookie_name,
                session_id,
                **cookie_options,
            )
            
    def _clear_cookie(self, response: Any) -> None:
        """Clear session cookie."""
        if hasattr(response, "delete_cookie"):
            response.delete_cookie(
                self.config.cookie_name,
                path=self.config.path,
            )
        elif hasattr(response, "set_cookie"):
            response.set_cookie(
                self.config.cookie_name,
                "",
                max_age=0,
                path=self.config.path,
            )


# Session middleware helper
class SessionMiddleware:
    """
    Middleware for automatic session handling.
    
    Loads session at request start and saves at response end.
    """
    
    def __init__(
        self,
        manager: Optional[SessionManager] = None,
    ) -> None:
        self.manager = manager or SessionManager()
        
    async def __call__(self, request: Any, call_next: Any) -> Any:
        """Process request with session."""
        # Load session
        session = await self.manager.start(request)
        request.session = session
        
        # Process request
        response = await call_next(request)
        
        # Save session
        await self.manager.save(session, response)
        
        return response
