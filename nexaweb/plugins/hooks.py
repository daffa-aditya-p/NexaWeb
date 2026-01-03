"""
NexaWeb Plugin Hooks
====================

Event hooks and extension points.
"""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    TypeVar,
    Union,
)
from enum import Enum, auto


T = TypeVar("T")
HookCallback = Callable[..., Union[Any, Awaitable[Any]]]


class HookPriority(Enum):
    """Hook execution priority."""
    
    HIGHEST = 0
    HIGH = 25
    NORMAL = 50
    LOW = 75
    LOWEST = 100


@dataclass
class HookHandler:
    """
    Registered hook handler.
    
    Attributes:
        callback: Handler function
        priority: Execution priority
        once: Execute only once
        filter: Filter function for conditional execution
    """
    
    callback: HookCallback
    priority: int = HookPriority.NORMAL.value
    once: bool = False
    filter: Optional[Callable[..., bool]] = None
    _executed: bool = field(default=False, repr=False)
    
    @property
    def is_async(self) -> bool:
        """Check if callback is async."""
        return asyncio.iscoroutinefunction(self.callback)
    
    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the handler."""
        if self.once and self._executed:
            return None
        
        # Check filter
        if self.filter and not self.filter(*args, **kwargs):
            return None
        
        self._executed = True
        
        if self.is_async:
            return await self.callback(*args, **kwargs)
        else:
            return self.callback(*args, **kwargs)


class Hook(Generic[T]):
    """
    Type-safe hook for specific event types.
    
    Example:
        # Define hook
        on_request: Hook[Request] = Hook("request")
        
        # Add handler
        @on_request.handler
        async def log_request(request: Request):
            print(f"Request: {request.path}")
        
        # Trigger
        await on_request.trigger(request)
    """
    
    def __init__(
        self,
        name: str,
        description: str = "",
    ):
        """
        Initialize hook.
        
        Args:
            name: Hook name
            description: Hook description
        """
        self.name = name
        self.description = description
        self._handlers: List[HookHandler] = []
    
    def add(
        self,
        callback: HookCallback,
        priority: int = HookPriority.NORMAL.value,
        once: bool = False,
        filter: Optional[Callable[..., bool]] = None,
    ) -> "Hook[T]":
        """
        Add handler to hook.
        
        Args:
            callback: Handler function
            priority: Execution priority
            once: Execute only once
            filter: Filter function
            
        Returns:
            Self for chaining
        """
        handler = HookHandler(
            callback=callback,
            priority=priority,
            once=once,
            filter=filter,
        )
        
        self._handlers.append(handler)
        self._handlers.sort(key=lambda h: h.priority)
        
        return self
    
    def handler(
        self,
        priority: int = HookPriority.NORMAL.value,
        once: bool = False,
    ) -> Callable[[HookCallback], HookCallback]:
        """
        Decorator to add handler.
        
        Args:
            priority: Execution priority
            once: Execute only once
            
        Returns:
            Decorator function
        """
        def decorator(func: HookCallback) -> HookCallback:
            self.add(func, priority, once)
            return func
        return decorator
    
    def remove(self, callback: HookCallback) -> bool:
        """
        Remove handler from hook.
        
        Args:
            callback: Handler to remove
            
        Returns:
            True if removed
        """
        for handler in self._handlers:
            if handler.callback == callback:
                self._handlers.remove(handler)
                return True
        return False
    
    def clear(self) -> None:
        """Remove all handlers."""
        self._handlers.clear()
    
    async def trigger(self, *args: Any, **kwargs: Any) -> List[Any]:
        """
        Trigger hook and execute all handlers.
        
        Args:
            *args: Arguments to pass to handlers
            **kwargs: Keyword arguments to pass to handlers
            
        Returns:
            List of handler return values
        """
        results = []
        
        for handler in self._handlers:
            try:
                result = await handler.execute(*args, **kwargs)
                results.append(result)
            except Exception as e:
                # Log error but continue with other handlers
                results.append(e)
        
        # Clean up once handlers
        self._handlers = [
            h for h in self._handlers
            if not (h.once and h._executed)
        ]
        
        return results
    
    async def trigger_until(
        self,
        condition: Callable[[Any], bool],
        *args: Any,
        **kwargs: Any,
    ) -> Optional[Any]:
        """
        Trigger until condition is met.
        
        Args:
            condition: Function that returns True to stop
            *args: Arguments to pass
            **kwargs: Keyword arguments
            
        Returns:
            First result that meets condition
        """
        for handler in self._handlers:
            try:
                result = await handler.execute(*args, **kwargs)
                if condition(result):
                    return result
            except Exception:
                continue
        
        return None
    
    def __len__(self) -> int:
        return len(self._handlers)
    
    def __repr__(self) -> str:
        return f"<Hook {self.name!r} handlers={len(self._handlers)}>"


class HookRegistry:
    """
    Registry for managing hooks.
    
    Example:
        registry = HookRegistry()
        
        # Register hook
        registry.register("request.before", "Before request processing")
        
        # Add handler
        registry.on("request.before", my_handler)
        
        # Trigger
        await registry.trigger("request.before", request)
    """
    
    def __init__(self):
        """Initialize registry."""
        self._hooks: Dict[str, Hook] = {}
    
    def register(
        self,
        name: str,
        description: str = "",
    ) -> Hook:
        """
        Register a new hook.
        
        Args:
            name: Hook name
            description: Hook description
            
        Returns:
            Created hook
        """
        if name in self._hooks:
            return self._hooks[name]
        
        hook = Hook(name, description)
        self._hooks[name] = hook
        
        return hook
    
    def get(self, name: str) -> Optional[Hook]:
        """
        Get hook by name.
        
        Args:
            name: Hook name
            
        Returns:
            Hook if found
        """
        return self._hooks.get(name)
    
    def has(self, name: str) -> bool:
        """Check if hook exists."""
        return name in self._hooks
    
    def on(
        self,
        name: str,
        callback: HookCallback,
        priority: int = HookPriority.NORMAL.value,
        once: bool = False,
    ) -> None:
        """
        Add handler to hook.
        
        Args:
            name: Hook name
            callback: Handler function
            priority: Execution priority
            once: Execute only once
        """
        hook = self._hooks.get(name)
        
        if not hook:
            hook = self.register(name)
        
        hook.add(callback, priority, once)
    
    def off(self, name: str, callback: HookCallback) -> bool:
        """
        Remove handler from hook.
        
        Args:
            name: Hook name
            callback: Handler to remove
            
        Returns:
            True if removed
        """
        hook = self._hooks.get(name)
        
        if hook:
            return hook.remove(callback)
        
        return False
    
    async def trigger(
        self,
        name: str,
        *args: Any,
        **kwargs: Any,
    ) -> List[Any]:
        """
        Trigger hook.
        
        Args:
            name: Hook name
            *args: Arguments
            **kwargs: Keyword arguments
            
        Returns:
            List of results
        """
        hook = self._hooks.get(name)
        
        if hook:
            return await hook.trigger(*args, **kwargs)
        
        return []
    
    def list_hooks(self) -> List[str]:
        """Get list of registered hook names."""
        return list(self._hooks.keys())
    
    def clear(self, name: Optional[str] = None) -> None:
        """
        Clear hooks.
        
        Args:
            name: Hook name to clear (or all if None)
        """
        if name:
            hook = self._hooks.get(name)
            if hook:
                hook.clear()
        else:
            for hook in self._hooks.values():
                hook.clear()


class EventEmitter:
    """
    Event emitter for pub/sub pattern.
    
    Example:
        emitter = EventEmitter()
        
        @emitter.on("user.created")
        async def handle_user_created(user):
            print(f"User created: {user.name}")
        
        await emitter.emit("user.created", user)
    """
    
    def __init__(self):
        """Initialize emitter."""
        self._listeners: Dict[str, List[HookHandler]] = {}
        self._max_listeners = 100
    
    @property
    def max_listeners(self) -> int:
        """Get maximum listeners per event."""
        return self._max_listeners
    
    @max_listeners.setter
    def max_listeners(self, value: int) -> None:
        """Set maximum listeners per event."""
        self._max_listeners = value
    
    def on(
        self,
        event: str,
        callback: Optional[HookCallback] = None,
        priority: int = HookPriority.NORMAL.value,
    ) -> Union[None, Callable[[HookCallback], HookCallback]]:
        """
        Add event listener.
        
        Can be used as decorator or method.
        
        Args:
            event: Event name
            callback: Handler function (optional for decorator)
            priority: Execution priority
            
        Returns:
            None or decorator
        """
        def add_listener(func: HookCallback) -> HookCallback:
            if event not in self._listeners:
                self._listeners[event] = []
            
            if len(self._listeners[event]) >= self._max_listeners:
                raise RuntimeError(
                    f"Max listeners ({self._max_listeners}) reached for event '{event}'"
                )
            
            handler = HookHandler(callback=func, priority=priority)
            self._listeners[event].append(handler)
            self._listeners[event].sort(key=lambda h: h.priority)
            
            return func
        
        if callback:
            add_listener(callback)
            return None
        
        return add_listener
    
    def once(
        self,
        event: str,
        callback: Optional[HookCallback] = None,
        priority: int = HookPriority.NORMAL.value,
    ) -> Union[None, Callable[[HookCallback], HookCallback]]:
        """
        Add one-time event listener.
        
        Args:
            event: Event name
            callback: Handler function
            priority: Execution priority
            
        Returns:
            None or decorator
        """
        def add_listener(func: HookCallback) -> HookCallback:
            if event not in self._listeners:
                self._listeners[event] = []
            
            handler = HookHandler(callback=func, priority=priority, once=True)
            self._listeners[event].append(handler)
            self._listeners[event].sort(key=lambda h: h.priority)
            
            return func
        
        if callback:
            add_listener(callback)
            return None
        
        return add_listener
    
    def off(self, event: str, callback: Optional[HookCallback] = None) -> None:
        """
        Remove event listener(s).
        
        Args:
            event: Event name
            callback: Specific callback to remove (or all if None)
        """
        if event not in self._listeners:
            return
        
        if callback:
            self._listeners[event] = [
                h for h in self._listeners[event]
                if h.callback != callback
            ]
        else:
            self._listeners[event] = []
    
    async def emit(self, event: str, *args: Any, **kwargs: Any) -> List[Any]:
        """
        Emit event to all listeners.
        
        Args:
            event: Event name
            *args: Arguments
            **kwargs: Keyword arguments
            
        Returns:
            List of results
        """
        listeners = self._listeners.get(event, [])
        results = []
        
        for handler in listeners:
            try:
                result = await handler.execute(*args, **kwargs)
                results.append(result)
            except Exception as e:
                results.append(e)
        
        # Clean up once handlers
        self._listeners[event] = [
            h for h in listeners
            if not (h.once and h._executed)
        ]
        
        # Also emit to wildcard listeners
        if event != "*":
            wildcard_results = await self.emit("*", event, *args, **kwargs)
            results.extend(wildcard_results)
        
        return results
    
    def listeners(self, event: str) -> List[HookCallback]:
        """
        Get listeners for event.
        
        Args:
            event: Event name
            
        Returns:
            List of callbacks
        """
        return [h.callback for h in self._listeners.get(event, [])]
    
    def listener_count(self, event: str) -> int:
        """
        Get listener count for event.
        
        Args:
            event: Event name
            
        Returns:
            Number of listeners
        """
        return len(self._listeners.get(event, []))
    
    def events(self) -> List[str]:
        """Get list of events with listeners."""
        return list(self._listeners.keys())
    
    def remove_all_listeners(self, event: Optional[str] = None) -> None:
        """
        Remove all listeners.
        
        Args:
            event: Specific event (or all if None)
        """
        if event:
            self._listeners.pop(event, None)
        else:
            self._listeners.clear()


# Pre-defined framework hooks
class FrameworkHooks:
    """Pre-defined framework hook names."""
    
    # Application lifecycle
    APP_STARTING = "app.starting"
    APP_STARTED = "app.started"
    APP_STOPPING = "app.stopping"
    APP_STOPPED = "app.stopped"
    
    # Request lifecycle
    REQUEST_RECEIVED = "request.received"
    REQUEST_HANDLING = "request.handling"
    REQUEST_HANDLED = "request.handled"
    
    # Response lifecycle
    RESPONSE_PREPARING = "response.preparing"
    RESPONSE_SENDING = "response.sending"
    RESPONSE_SENT = "response.sent"
    
    # Routing
    ROUTE_MATCHED = "route.matched"
    ROUTE_NOT_FOUND = "route.not_found"
    
    # Errors
    ERROR_OCCURRED = "error.occurred"
    ERROR_HANDLED = "error.handled"
    
    # Database
    DB_CONNECTING = "db.connecting"
    DB_CONNECTED = "db.connected"
    DB_QUERY = "db.query"
    
    # Auth
    AUTH_ATTEMPTING = "auth.attempting"
    AUTH_SUCCEEDED = "auth.succeeded"
    AUTH_FAILED = "auth.failed"
    AUTH_LOGOUT = "auth.logout"
    
    # Templates
    TEMPLATE_RENDERING = "template.rendering"
    TEMPLATE_RENDERED = "template.rendered"
