"""
NexaWeb CSRF Protection
=======================

Cross-Site Request Forgery protection using double-submit cookie pattern
with cryptographically secure tokens.

Features:
- Automatic token generation
- Cookie-based token storage
- Header and form field validation
- Configurable token lifetime
- Per-session token binding

Usage:
    # In middleware
    app.use(CSRFMiddleware())
    
    # In templates
    <form method="POST">
        {{ csrf_field() }}
        ...
    </form>
    
    # In AJAX requests
    fetch('/api/data', {
        headers: {
            'X-CSRF-Token': getCsrfToken()
        }
    })
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from nexaweb.core.middleware import Middleware

if TYPE_CHECKING:
    from nexaweb.core.request import Request
    from nexaweb.core.response import Response


@dataclass
class CSRFConfig:
    """CSRF protection configuration."""
    secret_key: str = ""
    token_name: str = "_csrf_token"
    header_name: str = "X-CSRF-Token"
    cookie_name: str = "csrf_token"
    cookie_path: str = "/"
    cookie_secure: bool = True
    cookie_httponly: bool = True
    cookie_samesite: str = "Strict"
    token_lifetime: int = 3600  # 1 hour
    exempt_methods: tuple = ("GET", "HEAD", "OPTIONS", "TRACE")
    failure_status: int = 403
    failure_message: str = "CSRF token validation failed"


class CSRFProtection:
    """
    CSRF Protection implementation.
    
    Uses the double-submit cookie pattern where:
    1. A token is stored in a cookie
    2. The same token must be submitted with requests
    3. Tokens are cryptographically signed for integrity
    
    Example:
        csrf = CSRFProtection(secret_key="your-secret-key")
        
        # Generate token for a session
        token = csrf.generate_token(session_id)
        
        # Validate incoming token
        if csrf.validate_token(token, session_id):
            # Token is valid
    """
    
    def __init__(
        self,
        secret_key: Optional[str] = None,
        config: Optional[CSRFConfig] = None,
    ) -> None:
        """
        Initialize CSRF protection.
        
        Args:
            secret_key: Secret key for token signing
            config: CSRF configuration
        """
        self.config = config or CSRFConfig()
        
        if secret_key:
            self.config.secret_key = secret_key
        elif not self.config.secret_key:
            # Generate random secret if not provided (not recommended for production)
            self.config.secret_key = secrets.token_hex(32)
            
    def generate_token(self, session_id: str = "") -> str:
        """
        Generate a CSRF token.
        
        Args:
            session_id: Optional session ID to bind token to
            
        Returns:
            Signed CSRF token
        """
        # Create token payload
        timestamp = int(time.time())
        random_bytes = secrets.token_hex(16)
        
        payload = f"{timestamp}.{random_bytes}.{session_id}"
        
        # Sign the payload
        signature = self._sign(payload)
        
        return f"{payload}.{signature}"
        
    def validate_token(
        self,
        token: str,
        session_id: str = "",
    ) -> bool:
        """
        Validate a CSRF token.
        
        Args:
            token: Token to validate
            session_id: Session ID token should be bound to
            
        Returns:
            True if token is valid
        """
        if not token:
            return False
            
        try:
            parts = token.rsplit(".", 1)
            if len(parts) != 2:
                return False
                
            payload, signature = parts
            
            # Verify signature
            expected_signature = self._sign(payload)
            if not hmac.compare_digest(signature, expected_signature):
                return False
                
            # Parse payload
            payload_parts = payload.split(".")
            if len(payload_parts) != 3:
                return False
                
            timestamp, _, token_session = payload_parts
            
            # Check session binding
            if session_id and token_session != session_id:
                return False
                
            # Check expiration
            token_time = int(timestamp)
            if time.time() - token_time > self.config.token_lifetime:
                return False
                
            return True
            
        except (ValueError, IndexError):
            return False
            
    def _sign(self, payload: str) -> str:
        """Sign payload with HMAC-SHA256."""
        key = self.config.secret_key.encode()
        message = payload.encode()
        
        signature = hmac.new(key, message, hashlib.sha256)
        return signature.hexdigest()
        
    def get_token_from_request(self, request: "Request") -> Optional[str]:
        """
        Extract CSRF token from request.
        
        Checks:
        1. Header (X-CSRF-Token)
        2. POST body (_csrf_token)
        3. Query string (_csrf_token)
        """
        # Check header first
        header_token = request.headers.get(self.config.header_name.lower())
        if header_token:
            return header_token
            
        # Check POST body (would need to be parsed)
        if hasattr(request, "_form") and request._form:
            form_token = request._form.get(self.config.token_name)
            if form_token:
                return form_token
                
        # Check query string
        query_token = request.query.get(self.config.token_name)
        if query_token:
            return query_token
            
        return None


class CSRFMiddleware(Middleware):
    """
    CSRF protection middleware.
    
    Automatically validates CSRF tokens on state-changing requests
    and injects tokens into responses.
    
    Example:
        app.use(CSRFMiddleware(secret_key="your-secret-key"))
    """
    
    def __init__(
        self,
        secret_key: Optional[str] = None,
        config: Optional[CSRFConfig] = None,
        exempt_paths: Optional[list] = None,
    ) -> None:
        """
        Initialize CSRF middleware.
        
        Args:
            secret_key: Secret key for token signing
            config: CSRF configuration
            exempt_paths: Paths to exempt from CSRF validation
        """
        self.csrf = CSRFProtection(secret_key, config)
        self.exempt_paths = exempt_paths or []
        
    async def before(self, request: "Request") -> Optional["Response"]:
        """Validate CSRF token on non-safe requests."""
        from nexaweb.core.response import JSONResponse
        
        # Skip safe methods
        if request.method in self.csrf.config.exempt_methods:
            return None
            
        # Skip exempt paths
        for path in self.exempt_paths:
            if request.path.startswith(path):
                return None
                
        # Get session ID if available
        session_id = request.cookies.get("session_id", "")
        
        # Get and validate token
        token = self.csrf.get_token_from_request(request)
        
        if not self.csrf.validate_token(token or "", session_id):
            return JSONResponse(
                {"error": self.csrf.config.failure_message},
                status_code=self.csrf.config.failure_status,
            )
            
        return None
        
    async def after(
        self,
        request: "Request",
        response: "Response",
    ) -> "Response":
        """Inject CSRF token into response."""
        # Generate token for next request
        session_id = request.cookies.get("session_id", "")
        token = self.csrf.generate_token(session_id)
        
        # Store in request for template access
        request.state["csrf_token"] = token
        
        # Set cookie
        response.set_cookie(
            name=self.csrf.config.cookie_name,
            value=token,
            path=self.csrf.config.cookie_path,
            secure=self.csrf.config.cookie_secure,
            httponly=self.csrf.config.cookie_httponly,
            samesite=self.csrf.config.cookie_samesite,
            max_age=self.csrf.config.token_lifetime,
        )
        
        return response


# Global CSRF instance
_csrf: Optional[CSRFProtection] = None


def configure_csrf(secret_key: str, **kwargs) -> CSRFProtection:
    """Configure global CSRF protection."""
    global _csrf
    config = CSRFConfig(secret_key=secret_key, **kwargs)
    _csrf = CSRFProtection(config=config)
    return _csrf


def get_csrf() -> CSRFProtection:
    """Get global CSRF protection instance."""
    global _csrf
    if _csrf is None:
        _csrf = CSRFProtection()
    return _csrf


def csrf_token(session_id: str = "") -> str:
    """Generate CSRF token (template helper)."""
    return get_csrf().generate_token(session_id)


def csrf_protect(token: str, session_id: str = "") -> bool:
    """Validate CSRF token."""
    return get_csrf().validate_token(token, session_id)


def csrf_field(session_id: str = "") -> str:
    """Generate CSRF hidden input field (template helper)."""
    token = csrf_token(session_id)
    name = get_csrf().config.token_name
    return f'<input type="hidden" name="{name}" value="{token}">'


def csrf_meta(session_id: str = "") -> str:
    """Generate CSRF meta tag for JavaScript access."""
    token = csrf_token(session_id)
    return f'<meta name="csrf-token" content="{token}">'
