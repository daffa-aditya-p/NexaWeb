"""
NexaWeb Security Module
=======================

Comprehensive security features for NexaWeb applications:
- CSRF Protection
- XSS Prevention
- Input Sanitization
- Rate Limiting
- Sandboxed Execution
- SQL Injection Prevention

Security is enabled by default and follows security-first design.
"""

from nexaweb.security.csrf import CSRFProtection, csrf_token, csrf_protect
from nexaweb.security.xss import XSSProtection, sanitize_html, escape_js
from nexaweb.security.sanitizer import Sanitizer, sanitize
from nexaweb.security.rate_limiter import RateLimiter, rate_limit
from nexaweb.security.sandbox import Sandbox, safe_eval

__all__ = [
    "CSRFProtection",
    "csrf_token",
    "csrf_protect",
    "XSSProtection",
    "sanitize_html",
    "escape_js",
    "Sanitizer",
    "sanitize",
    "RateLimiter",
    "rate_limit",
    "Sandbox",
    "safe_eval",
]
