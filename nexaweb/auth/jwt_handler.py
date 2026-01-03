"""
NexaWeb JWT Handler
===================

JSON Web Token handling for stateless authentication.

Features:
- Access and refresh token pairs
- Token validation and refresh
- Custom claims support
- Multiple algorithm support
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union


class JWTAlgorithm(Enum):
    """Supported JWT algorithms."""
    
    HS256 = "HS256"
    HS384 = "HS384"
    HS512 = "HS512"


# Try to import PyJWT
try:
    import jwt as pyjwt
    HAS_PYJWT = True
except ImportError:
    pyjwt = None
    HAS_PYJWT = False


class JWTError(Exception):
    """Base JWT error."""
    pass


class TokenExpiredError(JWTError):
    """Token has expired."""
    pass


class InvalidTokenError(JWTError):
    """Token is invalid."""
    pass


class InvalidSignatureError(JWTError):
    """Token signature is invalid."""
    pass


@dataclass
class JWTConfig:
    """JWT configuration."""
    
    # Secret key for signing
    secret_key: str = ""
    
    # Algorithm
    algorithm: JWTAlgorithm = JWTAlgorithm.HS256
    
    # Access token lifetime (seconds)
    access_lifetime: int = 3600  # 1 hour
    
    # Refresh token lifetime (seconds)
    refresh_lifetime: int = 604800  # 7 days
    
    # Token issuer
    issuer: Optional[str] = None
    
    # Token audience
    audience: Optional[str] = None
    
    # Leeway for expiration check (seconds)
    leeway: int = 0
    
    # Required claims
    required_claims: Set[str] = field(default_factory=lambda: {"exp", "iat"})
    
    # Additional headers
    headers: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenPair:
    """Access and refresh token pair."""
    
    access_token: str
    refresh_token: str
    access_expires: float
    refresh_expires: float
    token_type: str = "Bearer"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_in": int(self.access_expires - time.time()),
        }


class JWTHandler:
    """
    JWT token handler for stateless authentication.
    
    Supports both native implementation and PyJWT library.
    
    Example:
        handler = JWTHandler(JWTConfig(secret_key="your-secret-key"))
        
        # Create tokens
        tokens = handler.create_tokens({"user_id": 123, "roles": ["admin"]})
        
        # Validate token
        payload = handler.decode(tokens.access_token)
        
        # Refresh tokens
        new_tokens = handler.refresh(tokens.refresh_token)
    """
    
    def __init__(self, config: JWTConfig) -> None:
        """
        Initialize JWT handler.
        
        Args:
            config: JWT configuration
        """
        self.config = config
        
        if not config.secret_key:
            raise ValueError("secret_key is required")
            
    def create_tokens(
        self,
        claims: Dict[str, Any],
        access_lifetime: Optional[int] = None,
        refresh_lifetime: Optional[int] = None,
    ) -> TokenPair:
        """
        Create access and refresh token pair.
        
        Args:
            claims: Custom claims to include
            access_lifetime: Override access token lifetime
            refresh_lifetime: Override refresh token lifetime
            
        Returns:
            TokenPair with access and refresh tokens
        """
        now = time.time()
        
        access_exp = now + (access_lifetime or self.config.access_lifetime)
        refresh_exp = now + (refresh_lifetime or self.config.refresh_lifetime)
        
        # Access token claims
        access_claims = {
            **claims,
            "iat": int(now),
            "exp": int(access_exp),
            "type": "access",
        }
        
        # Refresh token claims
        refresh_claims = {
            "sub": claims.get("sub", claims.get("user_id")),
            "iat": int(now),
            "exp": int(refresh_exp),
            "type": "refresh",
        }
        
        # Add issuer/audience if configured
        if self.config.issuer:
            access_claims["iss"] = self.config.issuer
            refresh_claims["iss"] = self.config.issuer
            
        if self.config.audience:
            access_claims["aud"] = self.config.audience
            refresh_claims["aud"] = self.config.audience
            
        # Create tokens
        access_token = self.encode(access_claims)
        refresh_token = self.encode(refresh_claims)
        
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires=access_exp,
            refresh_expires=refresh_exp,
        )
        
    def create_access_token(
        self,
        claims: Dict[str, Any],
        lifetime: Optional[int] = None,
    ) -> str:
        """
        Create single access token.
        
        Args:
            claims: Token claims
            lifetime: Token lifetime in seconds
            
        Returns:
            Encoded JWT token
        """
        now = time.time()
        exp = now + (lifetime or self.config.access_lifetime)
        
        token_claims = {
            **claims,
            "iat": int(now),
            "exp": int(exp),
            "type": "access",
        }
        
        if self.config.issuer:
            token_claims["iss"] = self.config.issuer
            
        if self.config.audience:
            token_claims["aud"] = self.config.audience
            
        return self.encode(token_claims)
        
    def encode(self, claims: Dict[str, Any]) -> str:
        """
        Encode claims to JWT token.
        
        Args:
            claims: Token claims
            
        Returns:
            Encoded JWT string
        """
        if HAS_PYJWT:
            return pyjwt.encode(
                claims,
                self.config.secret_key,
                algorithm=self.config.algorithm.value,
                headers=self.config.headers or None,
            )
        else:
            return self._native_encode(claims)
            
    def decode(
        self,
        token: str,
        verify: bool = True,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Decode and validate JWT token.
        
        Args:
            token: JWT token string
            verify: Whether to verify signature and claims
            options: Additional validation options
            
        Returns:
            Decoded claims
            
        Raises:
            TokenExpiredError: If token is expired
            InvalidTokenError: If token is invalid
        """
        if HAS_PYJWT:
            return self._pyjwt_decode(token, verify, options)
        else:
            return self._native_decode(token, verify)
            
    def refresh(
        self,
        refresh_token: str,
        claims: Optional[Dict[str, Any]] = None,
    ) -> TokenPair:
        """
        Refresh token pair using refresh token.
        
        Args:
            refresh_token: Valid refresh token
            claims: Optional new claims (otherwise uses original)
            
        Returns:
            New token pair
            
        Raises:
            TokenExpiredError: If refresh token is expired
            InvalidTokenError: If refresh token is invalid
        """
        # Decode and validate refresh token
        payload = self.decode(refresh_token)
        
        # Verify it's a refresh token
        if payload.get("type") != "refresh":
            raise InvalidTokenError("Not a refresh token")
            
        # Get subject
        sub = payload.get("sub")
        if not sub:
            raise InvalidTokenError("Missing subject in refresh token")
            
        # Build new claims
        new_claims = claims or {}
        new_claims["sub"] = sub
        
        # Create new token pair
        return self.create_tokens(new_claims)
        
    def validate(self, token: str) -> bool:
        """
        Validate token without decoding.
        
        Returns:
            True if token is valid, False otherwise
        """
        try:
            self.decode(token)
            return True
        except JWTError:
            return False
            
    def get_unverified_header(self, token: str) -> Dict[str, Any]:
        """Get token header without verification."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                raise InvalidTokenError("Invalid token format")
                
            header_b64 = parts[0]
            header_json = self._base64_decode(header_b64)
            return json.loads(header_json)
            
        except Exception as e:
            raise InvalidTokenError(f"Cannot decode header: {e}")
            
    def get_unverified_claims(self, token: str) -> Dict[str, Any]:
        """Get token claims without verification."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                raise InvalidTokenError("Invalid token format")
                
            payload_b64 = parts[1]
            payload_json = self._base64_decode(payload_b64)
            return json.loads(payload_json)
            
        except Exception as e:
            raise InvalidTokenError(f"Cannot decode claims: {e}")
            
    # Native implementation (fallback)
    
    def _native_encode(self, claims: Dict[str, Any]) -> str:
        """Native JWT encoding."""
        # Header
        header = {
            "alg": self.config.algorithm.value,
            "typ": "JWT",
            **self.config.headers,
        }
        
        # Encode header and payload
        header_b64 = self._base64_encode(json.dumps(header))
        payload_b64 = self._base64_encode(json.dumps(claims))
        
        # Create signature
        message = f"{header_b64}.{payload_b64}"
        signature = self._create_signature(message)
        signature_b64 = self._base64_encode(signature)
        
        return f"{header_b64}.{payload_b64}.{signature_b64}"
        
    def _native_decode(
        self,
        token: str,
        verify: bool = True,
    ) -> Dict[str, Any]:
        """Native JWT decoding."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                raise InvalidTokenError("Invalid token format")
                
            header_b64, payload_b64, signature_b64 = parts
            
            # Decode header
            header = json.loads(self._base64_decode(header_b64))
            
            # Verify algorithm
            if header.get("alg") != self.config.algorithm.value:
                raise InvalidTokenError(
                    f"Algorithm mismatch: expected {self.config.algorithm.value}"
                )
                
            # Decode payload
            payload = json.loads(self._base64_decode(payload_b64))
            
            if verify:
                # Verify signature
                message = f"{header_b64}.{payload_b64}"
                expected_signature = self._create_signature(message)
                actual_signature = self._base64_decode(signature_b64)
                
                if not hmac.compare_digest(expected_signature, actual_signature):
                    raise InvalidSignatureError("Invalid signature")
                    
                # Verify expiration
                exp = payload.get("exp")
                if exp:
                    if time.time() > exp + self.config.leeway:
                        raise TokenExpiredError("Token has expired")
                        
                # Verify not before
                nbf = payload.get("nbf")
                if nbf:
                    if time.time() < nbf - self.config.leeway:
                        raise InvalidTokenError("Token not yet valid")
                        
                # Verify issuer
                if self.config.issuer:
                    if payload.get("iss") != self.config.issuer:
                        raise InvalidTokenError("Invalid issuer")
                        
                # Verify audience
                if self.config.audience:
                    aud = payload.get("aud")
                    if isinstance(aud, list):
                        if self.config.audience not in aud:
                            raise InvalidTokenError("Invalid audience")
                    elif aud != self.config.audience:
                        raise InvalidTokenError("Invalid audience")
                        
            return payload
            
        except JWTError:
            raise
        except json.JSONDecodeError:
            raise InvalidTokenError("Invalid token payload")
        except Exception as e:
            raise InvalidTokenError(f"Token decode failed: {e}")
            
    def _pyjwt_decode(
        self,
        token: str,
        verify: bool,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """PyJWT decode wrapper."""
        try:
            decode_options = options or {}
            
            if not verify:
                decode_options["verify_signature"] = False
                
            kwargs = {
                "jwt": token,
                "key": self.config.secret_key,
                "algorithms": [self.config.algorithm.value],
                "options": decode_options,
            }
            
            if self.config.issuer:
                kwargs["issuer"] = self.config.issuer
                
            if self.config.audience:
                kwargs["audience"] = self.config.audience
                
            if self.config.leeway:
                kwargs["leeway"] = self.config.leeway
                
            return pyjwt.decode(**kwargs)
            
        except pyjwt.ExpiredSignatureError:
            raise TokenExpiredError("Token has expired")
        except pyjwt.InvalidTokenError as e:
            raise InvalidTokenError(str(e))
            
    def _create_signature(self, message: str) -> bytes:
        """Create HMAC signature."""
        key = self.config.secret_key.encode()
        message_bytes = message.encode()
        
        if self.config.algorithm == JWTAlgorithm.HS256:
            return hmac.new(key, message_bytes, hashlib.sha256).digest()
        elif self.config.algorithm == JWTAlgorithm.HS384:
            return hmac.new(key, message_bytes, hashlib.sha384).digest()
        elif self.config.algorithm == JWTAlgorithm.HS512:
            return hmac.new(key, message_bytes, hashlib.sha512).digest()
        else:
            raise ValueError(f"Unsupported algorithm: {self.config.algorithm}")
            
    def _base64_encode(self, data: Union[str, bytes]) -> str:
        """Base64 URL-safe encode."""
        if isinstance(data, str):
            data = data.encode()
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()
        
    def _base64_decode(self, data: str) -> bytes:
        """Base64 URL-safe decode."""
        # Add padding if needed
        padding = 4 - len(data) % 4
        if padding != 4:
            data += "=" * padding
        return base64.urlsafe_b64decode(data)


# Helper functions

def create_jwt_handler(
    secret_key: str,
    algorithm: str = "HS256",
    access_lifetime: int = 3600,
    refresh_lifetime: int = 604800,
    **kwargs,
) -> JWTHandler:
    """
    Create JWT handler with common defaults.
    
    Args:
        secret_key: Secret key for signing
        algorithm: Algorithm name (HS256, HS384, HS512)
        access_lifetime: Access token lifetime in seconds
        refresh_lifetime: Refresh token lifetime in seconds
        **kwargs: Additional config options
        
    Returns:
        Configured JWTHandler
    """
    config = JWTConfig(
        secret_key=secret_key,
        algorithm=JWTAlgorithm(algorithm),
        access_lifetime=access_lifetime,
        refresh_lifetime=refresh_lifetime,
        **kwargs,
    )
    return JWTHandler(config)
