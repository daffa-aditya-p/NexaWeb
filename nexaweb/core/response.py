"""
NexaWeb Response Objects
========================

HTTP response abstractions with support for:
- Multiple content types (HTML, JSON, text, binary)
- Response streaming
- Cookie management
- Header manipulation
- Template rendering
- File downloads
- Redirects

All response classes implement the ASGI send interface for
direct integration with ASGI servers.
"""

from __future__ import annotations

import json
import mimetypes
from dataclasses import dataclass, field
from http import HTTPStatus
from http.cookies import SimpleCookie
from pathlib import Path
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Coroutine,
    Dict,
    Iterator,
    List,
    Optional,
    Union,
)

try:
    import orjson
    
    def _json_dumps(obj: Any) -> bytes:
        return orjson.dumps(obj)
except ImportError:
    def _json_dumps(obj: Any) -> bytes:
        return json.dumps(obj, ensure_ascii=False).encode("utf-8")


# Standard HTTP status messages
HTTP_STATUS_PHRASES = {s.value: s.phrase for s in HTTPStatus}


@dataclass
class Cookie:
    """HTTP Cookie with all standard attributes."""
    name: str
    value: str
    max_age: Optional[int] = None
    expires: Optional[str] = None
    path: str = "/"
    domain: Optional[str] = None
    secure: bool = False
    httponly: bool = True
    samesite: str = "Lax"
    
    def to_header(self) -> str:
        """Generate Set-Cookie header value."""
        parts = [f"{self.name}={self.value}"]
        
        if self.max_age is not None:
            parts.append(f"Max-Age={self.max_age}")
        if self.expires:
            parts.append(f"Expires={self.expires}")
        if self.path:
            parts.append(f"Path={self.path}")
        if self.domain:
            parts.append(f"Domain={self.domain}")
        if self.secure:
            parts.append("Secure")
        if self.httponly:
            parts.append("HttpOnly")
        if self.samesite:
            parts.append(f"SameSite={self.samesite}")
            
        return "; ".join(parts)


class Response:
    """
    Base HTTP Response class.
    
    Provides the foundation for all response types with:
    - Status code management
    - Header manipulation
    - Cookie handling
    - ASGI send interface
    
    Example:
        # Simple text response
        return Response("Hello, World!")
        
        # With status code
        return Response("Not Found", status_code=404)
        
        # With headers
        response = Response("OK")
        response.headers["X-Custom"] = "value"
        return response
    """
    
    media_type: str = "text/plain"
    charset: str = "utf-8"
    
    def __init__(
        self,
        content: Any = None,
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
        media_type: Optional[str] = None,
    ) -> None:
        self.status_code = status_code
        self.headers: Dict[str, str] = headers or {}
        self._cookies: List[Cookie] = []
        
        if media_type:
            self.media_type = media_type
            
        # Set content
        self.body = self._render_content(content)
        
        # Set Content-Type if not already set
        if "content-type" not in {k.lower() for k in self.headers}:
            content_type = self.media_type
            if self.charset and "text" in content_type:
                content_type += f"; charset={self.charset}"
            self.headers["Content-Type"] = content_type
            
        # Set Content-Length
        if self.body is not None:
            self.headers["Content-Length"] = str(len(self.body))
            
    def _render_content(self, content: Any) -> bytes:
        """Convert content to bytes."""
        if content is None:
            return b""
        if isinstance(content, bytes):
            return content
        if isinstance(content, str):
            return content.encode(self.charset)
        return str(content).encode(self.charset)
        
    def set_cookie(
        self,
        name: str,
        value: str,
        max_age: Optional[int] = None,
        expires: Optional[str] = None,
        path: str = "/",
        domain: Optional[str] = None,
        secure: bool = False,
        httponly: bool = True,
        samesite: str = "Lax",
    ) -> "Response":
        """Set a cookie on the response."""
        cookie = Cookie(
            name=name,
            value=value,
            max_age=max_age,
            expires=expires,
            path=path,
            domain=domain,
            secure=secure,
            httponly=httponly,
            samesite=samesite,
        )
        self._cookies.append(cookie)
        return self
        
    def delete_cookie(
        self,
        name: str,
        path: str = "/",
        domain: Optional[str] = None,
    ) -> "Response":
        """Delete a cookie by setting max_age to 0."""
        return self.set_cookie(
            name=name,
            value="",
            max_age=0,
            path=path,
            domain=domain,
        )
        
    def _get_headers(self) -> List[tuple]:
        """Get headers as list of tuples for ASGI."""
        headers = [(k.lower().encode(), v.encode()) for k, v in self.headers.items()]
        
        # Add cookies
        for cookie in self._cookies:
            headers.append((b"set-cookie", cookie.to_header().encode()))
            
        return headers
        
    async def send(
        self,
        send: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        """Send response via ASGI interface."""
        # Send response start
        await send({
            "type": "http.response.start",
            "status": self.status_code,
            "headers": self._get_headers(),
        })
        
        # Send response body
        await send({
            "type": "http.response.body",
            "body": self.body,
        })
        
    @classmethod
    def error(cls, status_code: int, message: str) -> "Response":
        """Create an error response."""
        return cls(
            content=message,
            status_code=status_code,
            media_type="text/plain",
        )
        
    @property
    def status_phrase(self) -> str:
        """Get HTTP status phrase."""
        return HTTP_STATUS_PHRASES.get(self.status_code, "Unknown")
        
    def __repr__(self) -> str:
        return f"<Response {self.status_code} {self.status_phrase}>"


class HTMLResponse(Response):
    """
    HTML content response.
    
    Example:
        return HTMLResponse("<h1>Hello, World!</h1>")
        
        # From template
        html = template.render(context)
        return HTMLResponse(html)
    """
    
    media_type = "text/html"


class JSONResponse(Response):
    """
    JSON content response.
    
    Uses orjson for fast serialization if available.
    
    Example:
        return JSONResponse({"message": "Hello"})
        return JSONResponse({"error": "Not found"}, status_code=404)
    """
    
    media_type = "application/json"
    
    def __init__(
        self,
        content: Any = None,
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self._json_content = content
        super().__init__(content, status_code, headers)
        
    def _render_content(self, content: Any) -> bytes:
        """Serialize content to JSON bytes."""
        if content is None:
            return b"null"
        return _json_dumps(content)


class PlainTextResponse(Response):
    """Plain text response."""
    
    media_type = "text/plain"


class RedirectResponse(Response):
    """
    HTTP redirect response.
    
    Example:
        return RedirectResponse("/login")
        return RedirectResponse("/dashboard", status_code=301)  # Permanent
    """
    
    def __init__(
        self,
        url: str,
        status_code: int = 302,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        headers = headers or {}
        headers["Location"] = url
        super().__init__(content=None, status_code=status_code, headers=headers)


class FileResponse(Response):
    """
    File download response.
    
    Efficiently streams file content for large files.
    
    Example:
        return FileResponse("/path/to/file.pdf")
        return FileResponse(path, filename="download.pdf")
    """
    
    chunk_size = 64 * 1024  # 64KB chunks
    
    def __init__(
        self,
        path: Union[str, Path],
        filename: Optional[str] = None,
        media_type: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        as_attachment: bool = True,
    ) -> None:
        self.path = Path(path)
        
        if not self.path.exists():
            raise FileNotFoundError(f"File not found: {self.path}")
            
        # Determine filename
        self.filename = filename or self.path.name
        
        # Determine media type
        if media_type is None:
            media_type, _ = mimetypes.guess_type(str(self.path))
            media_type = media_type or "application/octet-stream"
            
        # Build headers
        headers = headers or {}
        
        if as_attachment:
            headers["Content-Disposition"] = f'attachment; filename="{self.filename}"'
        else:
            headers["Content-Disposition"] = f'inline; filename="{self.filename}"'
            
        headers["Content-Length"] = str(self.path.stat().st_size)
        
        super().__init__(content=None, status_code=200, headers=headers, media_type=media_type)
        
    async def send(
        self,
        send: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        """Stream file content."""
        await send({
            "type": "http.response.start",
            "status": self.status_code,
            "headers": self._get_headers(),
        })
        
        # Stream file in chunks
        async with self._open_file() as f:
            while True:
                chunk = await f.read(self.chunk_size)
                if not chunk:
                    break
                await send({
                    "type": "http.response.body",
                    "body": chunk,
                    "more_body": True,
                })
                
        # Final empty body to close
        await send({
            "type": "http.response.body",
            "body": b"",
            "more_body": False,
        })
        
    async def _open_file(self):
        """Open file for async reading."""
        import aiofiles
        return aiofiles.open(self.path, "rb")


class StreamingResponse(Response):
    """
    Streaming response for server-sent events or large content.
    
    Example:
        async def generate():
            for i in range(10):
                yield f"data: {i}\n\n"
                await asyncio.sleep(1)
                
        return StreamingResponse(generate(), media_type="text/event-stream")
    """
    
    def __init__(
        self,
        content: Union[Iterator[bytes], AsyncIterator[bytes]],
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
        media_type: str = "application/octet-stream",
    ) -> None:
        self._stream = content
        self.status_code = status_code
        self.headers = headers or {}
        self.media_type = media_type
        self._cookies: List[Cookie] = []
        self.body = b""
        
        # Set Content-Type
        if "content-type" not in {k.lower() for k in self.headers}:
            self.headers["Content-Type"] = media_type
            
    async def send(
        self,
        send: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        """Stream response content."""
        await send({
            "type": "http.response.start",
            "status": self.status_code,
            "headers": self._get_headers(),
        })
        
        # Check if async iterator
        if hasattr(self._stream, "__anext__"):
            async for chunk in self._stream:
                if isinstance(chunk, str):
                    chunk = chunk.encode("utf-8")
                await send({
                    "type": "http.response.body",
                    "body": chunk,
                    "more_body": True,
                })
        else:
            for chunk in self._stream:
                if isinstance(chunk, str):
                    chunk = chunk.encode("utf-8")
                await send({
                    "type": "http.response.body",
                    "body": chunk,
                    "more_body": True,
                })
                
        await send({
            "type": "http.response.body",
            "body": b"",
            "more_body": False,
        })


class SSEResponse(StreamingResponse):
    """
    Server-Sent Events response.
    
    Example:
        async def events():
            for i in range(10):
                yield {"event": "update", "data": {"count": i}}
                await asyncio.sleep(1)
                
        return SSEResponse(events())
    """
    
    def __init__(
        self,
        content: AsyncIterator[Dict[str, Any]],
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        headers = headers or {}
        headers["Cache-Control"] = "no-cache"
        headers["Connection"] = "keep-alive"
        
        super().__init__(
            content=self._format_sse(content),
            status_code=status_code,
            headers=headers,
            media_type="text/event-stream",
        )
        
    async def _format_sse(
        self,
        content: AsyncIterator[Dict[str, Any]],
    ) -> AsyncIterator[bytes]:
        """Format events as SSE."""
        async for event in content:
            lines = []
            
            if "event" in event:
                lines.append(f"event: {event['event']}")
            if "id" in event:
                lines.append(f"id: {event['id']}")
            if "retry" in event:
                lines.append(f"retry: {event['retry']}")
            if "data" in event:
                data = event["data"]
                if isinstance(data, dict):
                    data = json.dumps(data)
                lines.append(f"data: {data}")
                
            yield ("\n".join(lines) + "\n\n").encode("utf-8")


# Convenience functions
def html(content: str, status_code: int = 200, **kwargs) -> HTMLResponse:
    """Create HTML response."""
    return HTMLResponse(content, status_code, **kwargs)


def json_response(data: Any, status_code: int = 200, **kwargs) -> JSONResponse:
    """Create JSON response."""
    return JSONResponse(data, status_code, **kwargs)


def redirect(url: str, permanent: bool = False, **kwargs) -> RedirectResponse:
    """Create redirect response."""
    status_code = 301 if permanent else 302
    return RedirectResponse(url, status_code, **kwargs)


def file(path: Union[str, Path], **kwargs) -> FileResponse:
    """Create file download response."""
    return FileResponse(path, **kwargs)
