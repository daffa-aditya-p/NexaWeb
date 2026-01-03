"""
NexaWeb XSS Protection
======================

Cross-Site Scripting prevention through:
- HTML sanitization
- JavaScript escaping
- Context-aware encoding
- Content Security Policy helpers

All user input should be sanitized before rendering in HTML context.
The PYXM template engine automatically escapes expressions by default.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

try:
    import bleach
    HAS_BLEACH = True
except ImportError:
    HAS_BLEACH = False


@dataclass
class XSSConfig:
    """XSS protection configuration."""
    
    # Allowed HTML tags
    allowed_tags: Set[str] = field(default_factory=lambda: {
        "a", "abbr", "acronym", "b", "blockquote", "br", "code",
        "div", "em", "h1", "h2", "h3", "h4", "h5", "h6", "hr",
        "i", "img", "li", "ol", "p", "pre", "span", "strong",
        "sub", "sup", "table", "tbody", "td", "th", "thead", "tr",
        "u", "ul",
    })
    
    # Allowed attributes per tag
    allowed_attributes: Dict[str, Set[str]] = field(default_factory=lambda: {
        "*": {"class", "id", "title", "style"},
        "a": {"href", "rel", "target"},
        "img": {"src", "alt", "width", "height"},
        "table": {"border", "cellpadding", "cellspacing"},
    })
    
    # Allowed URL schemes
    allowed_protocols: Set[str] = field(default_factory=lambda: {
        "http", "https", "mailto", "tel",
    })
    
    # Strip or escape disallowed content
    strip_disallowed: bool = True
    
    # Allow data: URLs for images
    allow_data_urls: bool = False


class XSSProtection:
    """
    XSS Protection implementation.
    
    Provides multiple levels of protection:
    1. HTML entity encoding (default, fastest)
    2. HTML sanitization (allows safe HTML)
    3. JavaScript escaping
    4. URL sanitization
    
    Example:
        xss = XSSProtection()
        
        # Encode all HTML
        safe = xss.escape("<script>alert('xss')</script>")
        # "&lt;script&gt;alert('xss')&lt;/script&gt;"
        
        # Sanitize allowing safe tags
        safe = xss.sanitize("<b>Bold</b><script>bad</script>")
        # "<b>Bold</b>"
    """
    
    def __init__(self, config: Optional[XSSConfig] = None) -> None:
        """Initialize XSS protection."""
        self.config = config or XSSConfig()
        
    def escape(self, text: str) -> str:
        """
        Escape HTML entities.
        
        Converts all HTML special characters to entities.
        This is the safest option when HTML is not needed.
        
        Args:
            text: Text to escape
            
        Returns:
            HTML-escaped text
        """
        if not text:
            return ""
        return html.escape(str(text), quote=True)
        
    def sanitize(self, html_content: str) -> str:
        """
        Sanitize HTML, keeping safe tags.
        
        Removes dangerous tags and attributes while preserving
        allowed HTML structure.
        
        Args:
            html_content: HTML to sanitize
            
        Returns:
            Sanitized HTML
        """
        if not html_content:
            return ""
            
        if HAS_BLEACH:
            return self._sanitize_with_bleach(html_content)
        return self._sanitize_simple(html_content)
        
    def _sanitize_with_bleach(self, html_content: str) -> str:
        """Sanitize using bleach library."""
        # Convert allowed_attributes to bleach format
        attrs = {}
        for tag, tag_attrs in self.config.allowed_attributes.items():
            attrs[tag] = list(tag_attrs)
            
        return bleach.clean(
            html_content,
            tags=list(self.config.allowed_tags),
            attributes=attrs,
            protocols=list(self.config.allowed_protocols),
            strip=self.config.strip_disallowed,
        )
        
    def _sanitize_simple(self, html_content: str) -> str:
        """Simple sanitization without bleach."""
        # Remove script tags completely
        html_content = re.sub(
            r'<script[^>]*>.*?</script>',
            '',
            html_content,
            flags=re.DOTALL | re.IGNORECASE
        )
        
        # Remove style tags
        html_content = re.sub(
            r'<style[^>]*>.*?</style>',
            '',
            html_content,
            flags=re.DOTALL | re.IGNORECASE
        )
        
        # Remove event handlers
        html_content = re.sub(
            r'\s+on\w+\s*=\s*["\'][^"\']*["\']',
            '',
            html_content,
            flags=re.IGNORECASE
        )
        
        # Remove javascript: URLs
        html_content = re.sub(
            r'href\s*=\s*["\']?\s*javascript:[^"\'>\s]*',
            'href="#"',
            html_content,
            flags=re.IGNORECASE
        )
        
        # Remove data: URLs (unless allowed)
        if not self.config.allow_data_urls:
            html_content = re.sub(
                r'src\s*=\s*["\']?\s*data:[^"\'>\s]*',
                'src=""',
                html_content,
                flags=re.IGNORECASE
            )
            
        return html_content
        
    def escape_js(self, text: str) -> str:
        """
        Escape text for use in JavaScript strings.
        
        Args:
            text: Text to escape
            
        Returns:
            JavaScript-safe string
        """
        if not text:
            return ""
            
        # Escape special characters
        replacements = {
            "\\": "\\\\",
            "'": "\\'",
            '"': '\\"',
            "\n": "\\n",
            "\r": "\\r",
            "\t": "\\t",
            "<": "\\x3c",
            ">": "\\x3e",
            "&": "\\x26",
            "\u2028": "\\u2028",  # Line separator
            "\u2029": "\\u2029",  # Paragraph separator
        }
        
        result = str(text)
        for char, escaped in replacements.items():
            result = result.replace(char, escaped)
            
        return result
        
    def escape_url(self, url: str) -> str:
        """
        Escape and validate URL.
        
        Args:
            url: URL to escape
            
        Returns:
            Safe URL or '#' if invalid
        """
        if not url:
            return ""
            
        from urllib.parse import urlparse, quote
        
        try:
            parsed = urlparse(url)
            
            # Check scheme
            if parsed.scheme and parsed.scheme.lower() not in self.config.allowed_protocols:
                return "#"
                
            # Re-encode path
            safe_path = quote(parsed.path, safe="/")
            
            # Rebuild URL
            result = ""
            if parsed.scheme:
                result += f"{parsed.scheme}://"
            if parsed.netloc:
                result += parsed.netloc
            result += safe_path
            if parsed.query:
                result += f"?{parsed.query}"
            if parsed.fragment:
                result += f"#{parsed.fragment}"
                
            return result
            
        except Exception:
            return "#"
            
    def escape_css(self, css: str) -> str:
        """
        Escape CSS value.
        
        Args:
            css: CSS value to escape
            
        Returns:
            CSS-safe value
        """
        if not css:
            return ""
            
        # Remove potentially dangerous CSS
        dangerous_patterns = [
            r'expression\s*\(',
            r'url\s*\(\s*["\']?\s*javascript:',
            r'behavior\s*:',
            r'-moz-binding\s*:',
        ]
        
        result = str(css)
        for pattern in dangerous_patterns:
            result = re.sub(pattern, '', result, flags=re.IGNORECASE)
            
        return result
        
    def escape_attribute(self, name: str, value: str) -> str:
        """
        Escape attribute value for safe HTML insertion.
        
        Args:
            name: Attribute name
            value: Attribute value
            
        Returns:
            Escaped attribute string
        """
        name = name.lower()
        
        # Handle special attributes
        if name in ("href", "src", "action", "formaction"):
            value = self.escape_url(value)
        elif name == "style":
            value = self.escape_css(value)
        elif name.startswith("on"):
            # Don't allow event handlers
            return ""
        else:
            value = self.escape(value)
            
        return f'{name}="{value}"'


# Global instance
_xss = XSSProtection()


def get_xss_protection() -> XSSProtection:
    """Get global XSS protection instance."""
    return _xss


def sanitize_html(html_content: str) -> str:
    """Sanitize HTML content (global function)."""
    return _xss.sanitize(html_content)


def escape_js(text: str) -> str:
    """Escape for JavaScript (global function)."""
    return _xss.escape_js(text)


def escape_html(text: str) -> str:
    """Escape HTML entities (global function)."""
    return _xss.escape(text)


def escape_url(url: str) -> str:
    """Escape URL (global function)."""
    return _xss.escape_url(url)


def escape_css(css: str) -> str:
    """Escape CSS (global function)."""
    return _xss.escape_css(css)


class ContentSecurityPolicy:
    """
    Content Security Policy header builder.
    
    Helps construct CSP headers for additional XSS protection.
    
    Example:
        csp = ContentSecurityPolicy()
        csp.default_src("'self'")
        csp.script_src("'self'", "https://cdn.example.com")
        csp.style_src("'self'", "'unsafe-inline'")
        
        header_value = csp.build()
    """
    
    def __init__(self) -> None:
        self._directives: Dict[str, List[str]] = {}
        
    def _add_directive(self, name: str, *values: str) -> "ContentSecurityPolicy":
        """Add values to a directive."""
        if name not in self._directives:
            self._directives[name] = []
        self._directives[name].extend(values)
        return self
        
    def default_src(self, *values: str) -> "ContentSecurityPolicy":
        """Set default-src directive."""
        return self._add_directive("default-src", *values)
        
    def script_src(self, *values: str) -> "ContentSecurityPolicy":
        """Set script-src directive."""
        return self._add_directive("script-src", *values)
        
    def style_src(self, *values: str) -> "ContentSecurityPolicy":
        """Set style-src directive."""
        return self._add_directive("style-src", *values)
        
    def img_src(self, *values: str) -> "ContentSecurityPolicy":
        """Set img-src directive."""
        return self._add_directive("img-src", *values)
        
    def font_src(self, *values: str) -> "ContentSecurityPolicy":
        """Set font-src directive."""
        return self._add_directive("font-src", *values)
        
    def connect_src(self, *values: str) -> "ContentSecurityPolicy":
        """Set connect-src directive."""
        return self._add_directive("connect-src", *values)
        
    def frame_src(self, *values: str) -> "ContentSecurityPolicy":
        """Set frame-src directive."""
        return self._add_directive("frame-src", *values)
        
    def object_src(self, *values: str) -> "ContentSecurityPolicy":
        """Set object-src directive."""
        return self._add_directive("object-src", *values)
        
    def base_uri(self, *values: str) -> "ContentSecurityPolicy":
        """Set base-uri directive."""
        return self._add_directive("base-uri", *values)
        
    def form_action(self, *values: str) -> "ContentSecurityPolicy":
        """Set form-action directive."""
        return self._add_directive("form-action", *values)
        
    def frame_ancestors(self, *values: str) -> "ContentSecurityPolicy":
        """Set frame-ancestors directive."""
        return self._add_directive("frame-ancestors", *values)
        
    def report_uri(self, uri: str) -> "ContentSecurityPolicy":
        """Set report-uri directive."""
        return self._add_directive("report-uri", uri)
        
    def build(self) -> str:
        """Build CSP header value."""
        parts = []
        for directive, values in self._directives.items():
            parts.append(f"{directive} {' '.join(values)}")
        return "; ".join(parts)
        
    def to_header(self) -> tuple:
        """Get header tuple for response."""
        return ("Content-Security-Policy", self.build())


def default_csp() -> ContentSecurityPolicy:
    """Create a secure default CSP."""
    return (
        ContentSecurityPolicy()
        .default_src("'self'")
        .script_src("'self'")
        .style_src("'self'", "'unsafe-inline'")
        .img_src("'self'", "data:", "https:")
        .font_src("'self'", "https:")
        .connect_src("'self'")
        .frame_ancestors("'self'")
        .base_uri("'self'")
        .form_action("'self'")
    )
