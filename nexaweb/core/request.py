"""
NexaWeb Request Object
======================

Encapsulates HTTP request data with lazy parsing for optimal performance.
Request bodies are only parsed when accessed, reducing overhead for
routes that don't need body data.

Features:
- Lazy body parsing (JSON, form data, multipart)
- Typed header access
- Cookie handling
- Query parameter parsing
- Path parameter injection
- File upload handling
- Client info extraction

The Request object is immutable once created to ensure thread safety
and prevent accidental modification during middleware processing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from http.cookies import SimpleCookie
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
    Union,
)
from urllib.parse import parse_qs, unquote

try:
    import orjson
    _json_loads = orjson.loads
except ImportError:
    _json_loads = json.loads

if TYPE_CHECKING:
    from nexaweb.auth.session import Session


@dataclass
class UploadedFile:
    """
    Represents an uploaded file from multipart form data.
    
    Attributes:
        filename: Original filename
        content_type: MIME type
        size: File size in bytes
        content: File content as bytes
    """
    filename: str
    content_type: str
    size: int
    content: bytes
    
    async def save(self, path: str) -> None:
        """Save uploaded file to disk."""
        import aiofiles
        async with aiofiles.open(path, 'wb') as f:
            await f.write(self.content)
            
    def read(self) -> bytes:
        """Read file content."""
        return self.content
        
    def text(self, encoding: str = "utf-8") -> str:
        """Read file content as text."""
        return self.content.decode(encoding)


@dataclass
class QueryParams:
    """
    Query string parameters with type coercion.
    
    Supports:
    - Single values: ?name=value -> params.get("name") = "value"
    - Multiple values: ?tag=a&tag=b -> params.get_list("tag") = ["a", "b"]
    - Type conversion: params.get_int("page", 1)
    """
    _data: Dict[str, List[str]] = field(default_factory=dict)
    
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get single value (first if multiple)."""
        values = self._data.get(key)
        return values[0] if values else default
        
    def get_list(self, key: str) -> List[str]:
        """Get all values for a key."""
        return self._data.get(key, [])
        
    def get_int(self, key: str, default: int = 0) -> int:
        """Get value as integer."""
        value = self.get(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            return default
            
    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get value as float."""
        value = self.get(key)
        if value is None:
            return default
        try:
            return float(value)
        except ValueError:
            return default
            
    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get value as boolean."""
        value = self.get(key)
        if value is None:
            return default
        return value.lower() in ("true", "1", "yes", "on")
        
    def __contains__(self, key: str) -> bool:
        return key in self._data
        
    def keys(self) -> List[str]:
        return list(self._data.keys())
        
    def items(self) -> List[tuple]:
        return [(k, v[0] if len(v) == 1 else v) for k, v in self._data.items()]
        
    def to_dict(self) -> Dict[str, Union[str, List[str]]]:
        """Convert to dictionary (single values unwrapped)."""
        return {k: v[0] if len(v) == 1 else v for k, v in self._data.items()}


class Headers:
    """
    Case-insensitive HTTP headers container.
    
    Example:
        headers["Content-Type"]  # application/json
        headers["content-type"]  # application/json (same)
        headers.get("X-Custom", "default")
    """
    
    def __init__(self, raw_headers: List[tuple]) -> None:
        self._headers: Dict[str, str] = {}
        self._raw: List[tuple] = raw_headers
        
        for key, value in raw_headers:
            # Decode bytes if needed
            if isinstance(key, bytes):
                key = key.decode("latin-1")
            if isinstance(value, bytes):
                value = value.decode("latin-1")
            self._headers[key.lower()] = value
            
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get header value."""
        return self._headers.get(key.lower(), default)
        
    def __getitem__(self, key: str) -> str:
        return self._headers[key.lower()]
        
    def __contains__(self, key: str) -> bool:
        return key.lower() in self._headers
        
    def items(self) -> List[tuple]:
        return list(self._headers.items())
        
    def keys(self) -> List[str]:
        return list(self._headers.keys())
        
    def to_dict(self) -> Dict[str, str]:
        return self._headers.copy()


class Request:
    """
    HTTP Request encapsulation.
    
    Created from ASGI scope and provides convenient access to:
    - Method, path, query string
    - Headers and cookies
    - Body data (JSON, form, multipart)
    - Path parameters (injected by router)
    - Client information
    - Session data
    
    Body data is lazily parsed for performance - the body is only
    read and parsed when explicitly accessed.
    
    Example:
        @app.post("/users")
        async def create_user(request: Request):
            data = await request.json()
            name = data.get("name")
            
            # Access headers
            auth = request.headers.get("Authorization")
            
            # Access query params
            page = request.query.get_int("page", 1)
            
            # Access cookies
            session_id = request.cookies.get("session_id")
    """
    
    __slots__ = (
        "_scope",
        "_receive",
        "_body",
        "_body_consumed",
        "_json",
        "_form",
        "_files",
        "method",
        "path",
        "query_string",
        "query",
        "headers",
        "cookies",
        "params",
        "state",
        "_session",
        "_user",
    )
    
    def __init__(
        self,
        scope: Dict[str, Any],
        receive: Callable[[], Coroutine[Any, Any, Dict[str, Any]]],
    ) -> None:
        self._scope = scope
        self._receive = receive
        self._body: Optional[bytes] = None
        self._body_consumed = False
        self._json: Optional[Any] = None
        self._form: Optional[Dict[str, Any]] = None
        self._files: Optional[Dict[str, UploadedFile]] = None
        
        # Extract basic request info
        self.method: str = scope.get("method", "GET").upper()
        self.path: str = scope.get("path", "/")
        self.query_string: str = scope.get("query_string", b"").decode("utf-8")
        
        # Parse query parameters
        self.query = QueryParams(_data=parse_qs(self.query_string, keep_blank_values=True))
        
        # Parse headers
        self.headers = Headers(scope.get("headers", []))
        
        # Parse cookies
        self.cookies: Dict[str, str] = {}
        cookie_header = self.headers.get("cookie", "")
        if cookie_header:
            cookie = SimpleCookie()
            cookie.load(cookie_header)
            self.cookies = {key: morsel.value for key, morsel in cookie.items()}
            
        # Route parameters (injected by router)
        self.params: Dict[str, Any] = {}
        
        # Request state (for middleware data passing)
        self.state: Dict[str, Any] = {}
        
        # Auth state (lazy loaded)
        self._session: Optional["Session"] = None
        self._user: Optional[Any] = None
        
    @classmethod
    async def from_scope(
        cls,
        scope: Dict[str, Any],
        receive: Callable,
    ) -> "Request":
        """Create Request from ASGI scope."""
        return cls(scope, receive)
        
    async def body(self) -> bytes:
        """
        Read request body.
        
        Can only be called once - subsequent calls return cached body.
        """
        if self._body is not None:
            return self._body
            
        if self._body_consumed:
            raise RuntimeError("Request body already consumed")
            
        chunks: List[bytes] = []
        while True:
            message = await self._receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                if body:
                    chunks.append(body)
                if not message.get("more_body", False):
                    break
            elif message["type"] == "http.disconnect":
                raise RuntimeError("Client disconnected")
                
        self._body = b"".join(chunks)
        self._body_consumed = True
        return self._body
        
    async def text(self, encoding: str = "utf-8") -> str:
        """Read body as text."""
        body = await self.body()
        return body.decode(encoding)
        
    async def json(self) -> Any:
        """
        Parse body as JSON.
        
        Uses orjson for faster parsing if available.
        """
        if self._json is not None:
            return self._json
            
        body = await self.body()
        if not body:
            return None
            
        self._json = _json_loads(body)
        return self._json
        
    async def form(self) -> Dict[str, Any]:
        """
        Parse body as form data.
        
        Supports both application/x-www-form-urlencoded and multipart/form-data.
        """
        if self._form is not None:
            return self._form
            
        content_type = self.headers.get("content-type", "")
        body = await self.body()
        
        if "application/x-www-form-urlencoded" in content_type:
            self._form = dict(parse_qs(body.decode("utf-8"), keep_blank_values=True))
            # Unwrap single values
            self._form = {k: v[0] if len(v) == 1 else v for k, v in self._form.items()}
        elif "multipart/form-data" in content_type:
            self._form, self._files = await self._parse_multipart(body, content_type)
        else:
            self._form = {}
            
        return self._form
        
    async def files(self) -> Dict[str, UploadedFile]:
        """Get uploaded files from multipart form data."""
        if self._files is None:
            await self.form()  # This populates _files
        return self._files or {}
        
    async def _parse_multipart(
        self,
        body: bytes,
        content_type: str,
    ) -> tuple:
        """Parse multipart form data."""
        import re
        
        # Extract boundary
        boundary_match = re.search(r'boundary=([^;\s]+)', content_type)
        if not boundary_match:
            return {}, {}
            
        boundary = boundary_match.group(1).encode()
        
        form_data: Dict[str, Any] = {}
        files: Dict[str, UploadedFile] = {}
        
        # Split by boundary
        parts = body.split(b"--" + boundary)
        
        for part in parts[1:-1]:  # Skip first empty and last closing
            if not part.strip() or part.strip() == b"--":
                continue
                
            # Split headers from content
            try:
                headers_end = part.index(b"\r\n\r\n")
                headers_raw = part[:headers_end].decode("utf-8")
                content = part[headers_end + 4:].rstrip(b"\r\n")
            except ValueError:
                continue
                
            # Parse Content-Disposition
            name_match = re.search(r'name="([^"]+)"', headers_raw)
            filename_match = re.search(r'filename="([^"]+)"', headers_raw)
            content_type_match = re.search(r'Content-Type:\s*([^\r\n]+)', headers_raw, re.I)
            
            if not name_match:
                continue
                
            field_name = name_match.group(1)
            
            if filename_match:
                # File upload
                files[field_name] = UploadedFile(
                    filename=filename_match.group(1),
                    content_type=content_type_match.group(1) if content_type_match else "application/octet-stream",
                    size=len(content),
                    content=content,
                )
            else:
                # Regular field
                form_data[field_name] = content.decode("utf-8")
                
        return form_data, files
        
    @property
    def content_type(self) -> Optional[str]:
        """Get Content-Type header."""
        return self.headers.get("content-type")
        
    @property
    def content_length(self) -> int:
        """Get Content-Length header."""
        length = self.headers.get("content-length", "0")
        try:
            return int(length)
        except ValueError:
            return 0
            
    @property
    def host(self) -> str:
        """Get request host."""
        return self.headers.get("host", "")
        
    @property
    def url(self) -> str:
        """Get full request URL."""
        scheme = self._scope.get("scheme", "http")
        host = self.host
        path = self.path
        query = f"?{self.query_string}" if self.query_string else ""
        return f"{scheme}://{host}{path}{query}"
        
    @property
    def client(self) -> tuple:
        """Get client address (host, port)."""
        return self._scope.get("client", ("", 0))
        
    @property
    def client_ip(self) -> str:
        """Get client IP address."""
        # Check forwarded headers first
        forwarded = self.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
            
        real_ip = self.headers.get("x-real-ip")
        if real_ip:
            return real_ip
            
        return self.client[0]
        
    @property
    def is_ajax(self) -> bool:
        """Check if request is AJAX/XHR."""
        return self.headers.get("x-requested-with", "").lower() == "xmlhttprequest"
        
    @property
    def is_secure(self) -> bool:
        """Check if request is HTTPS."""
        return self._scope.get("scheme", "http") == "https"
        
    @property
    def accepts_json(self) -> bool:
        """Check if client accepts JSON response."""
        accept = self.headers.get("accept", "")
        return "application/json" in accept or "*/*" in accept
        
    @property
    def session(self) -> "Session":
        """Get session object (must be enabled via middleware)."""
        if self._session is None:
            raise RuntimeError("Session not available. Add SessionMiddleware to enable sessions.")
        return self._session
        
    @property
    def user(self) -> Any:
        """Get authenticated user (set by auth middleware)."""
        return self._user
        
    def wants_json(self) -> bool:
        """Check if client expects JSON response."""
        return self.accepts_json or self.is_ajax
        
    def __repr__(self) -> str:
        return f"<Request {self.method} {self.path}>"
