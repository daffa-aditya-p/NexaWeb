"""
NexaWeb WebSocket Support
=========================

WebSocket connection handling with:
- Async message sending/receiving
- JSON message support
- Connection lifecycle management
- Room-based broadcasting
"""

from __future__ import annotations

import json
from typing import Any, Callable, Coroutine, Dict, Optional, Union


class WebSocketConnection:
    """
    WebSocket connection wrapper.
    
    Provides a clean interface for WebSocket communication
    within NexaWeb route handlers.
    
    Example:
        @app.websocket("/ws/chat")
        async def chat(ws: WebSocketConnection):
            await ws.accept()
            
            while True:
                data = await ws.receive_json()
                await ws.send_json({"echo": data})
    """
    
    def __init__(
        self,
        scope: Dict[str, Any],
        receive: Callable[[], Coroutine[Any, Any, Dict[str, Any]]],
        send: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        self._scope = scope
        self._receive = receive
        self._send = send
        self._accepted = False
        self._closed = False
        
    @property
    def path(self) -> str:
        """Get WebSocket path."""
        return self._scope.get("path", "/")
        
    @property
    def query_string(self) -> str:
        """Get query string."""
        return self._scope.get("query_string", b"").decode("utf-8")
        
    @property
    def headers(self) -> Dict[str, str]:
        """Get connection headers."""
        return {
            k.decode(): v.decode()
            for k, v in self._scope.get("headers", [])
        }
        
    @property
    def client(self) -> tuple:
        """Get client address."""
        return self._scope.get("client", ("", 0))
        
    async def accept(
        self,
        subprotocol: Optional[str] = None,
    ) -> None:
        """Accept the WebSocket connection."""
        if self._accepted:
            return
            
        message: Dict[str, Any] = {"type": "websocket.accept"}
        if subprotocol:
            message["subprotocol"] = subprotocol
            
        await self._send(message)
        self._accepted = True
        
    async def close(
        self,
        code: int = 1000,
        reason: str = "",
    ) -> None:
        """Close the WebSocket connection."""
        if self._closed:
            return
            
        await self._send({
            "type": "websocket.close",
            "code": code,
            "reason": reason,
        })
        self._closed = True
        
    async def send_text(self, data: str) -> None:
        """Send text message."""
        await self._send({
            "type": "websocket.send",
            "text": data,
        })
        
    async def send_bytes(self, data: bytes) -> None:
        """Send binary message."""
        await self._send({
            "type": "websocket.send",
            "bytes": data,
        })
        
    async def send_json(self, data: Any) -> None:
        """Send JSON message."""
        await self.send_text(json.dumps(data))
        
    async def receive(self) -> Dict[str, Any]:
        """Receive raw WebSocket message."""
        message = await self._receive()
        
        if message["type"] == "websocket.disconnect":
            self._closed = True
            raise WebSocketDisconnect(message.get("code", 1000))
            
        return message
        
    async def receive_text(self) -> str:
        """Receive text message."""
        message = await self.receive()
        return message.get("text", "")
        
    async def receive_bytes(self) -> bytes:
        """Receive binary message."""
        message = await self.receive()
        return message.get("bytes", b"")
        
    async def receive_json(self) -> Any:
        """Receive and parse JSON message."""
        text = await self.receive_text()
        return json.loads(text)
        
    async def __aiter__(self):
        """Iterate over incoming messages."""
        while True:
            try:
                yield await self.receive()
            except WebSocketDisconnect:
                break


class WebSocketDisconnect(Exception):
    """Exception raised when WebSocket disconnects."""
    
    def __init__(self, code: int = 1000) -> None:
        self.code = code
        super().__init__(f"WebSocket disconnected with code {code}")


class WebSocketRoom:
    """
    Manage a group of WebSocket connections.
    
    Useful for chat rooms, live updates, etc.
    
    Example:
        room = WebSocketRoom()
        
        @app.websocket("/ws/chat/{room_id}")
        async def chat(ws: WebSocketConnection, room_id: str):
            await ws.accept()
            room.add(ws)
            
            try:
                async for message in ws:
                    await room.broadcast(message["text"])
            finally:
                room.remove(ws)
    """
    
    def __init__(self) -> None:
        self._connections: set[WebSocketConnection] = set()
        
    def add(self, ws: WebSocketConnection) -> None:
        """Add connection to room."""
        self._connections.add(ws)
        
    def remove(self, ws: WebSocketConnection) -> None:
        """Remove connection from room."""
        self._connections.discard(ws)
        
    async def broadcast(
        self,
        message: Union[str, bytes, Dict],
        exclude: Optional[WebSocketConnection] = None,
    ) -> None:
        """Broadcast message to all connections."""
        for ws in self._connections:
            if ws is exclude or ws._closed:
                continue
                
            try:
                if isinstance(message, dict):
                    await ws.send_json(message)
                elif isinstance(message, bytes):
                    await ws.send_bytes(message)
                else:
                    await ws.send_text(str(message))
            except Exception:
                self.remove(ws)
                
    async def broadcast_json(
        self,
        data: Any,
        exclude: Optional[WebSocketConnection] = None,
    ) -> None:
        """Broadcast JSON to all connections."""
        await self.broadcast(data, exclude)
        
    def __len__(self) -> int:
        return len(self._connections)
        
    def __contains__(self, ws: WebSocketConnection) -> bool:
        return ws in self._connections
