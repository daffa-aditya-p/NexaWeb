"""
NexaWeb Route Guards
====================

Authorization guards for protecting routes.

Features:
- Authentication guards
- Role-based access control
- Permission-based access control
- Composable guards
- Decorator support
"""

from __future__ import annotations

import functools
from abc import ABC, abstractmethod
from typing import Any, Callable, List, Optional, Set, Union

from nexaweb.auth.authenticator import User


class GuardError(Exception):
    """Base guard error."""
    pass


class UnauthorizedError(GuardError):
    """User is not authenticated."""
    
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(message)
        self.status_code = 401


class ForbiddenError(GuardError):
    """User is not authorized."""
    
    def __init__(self, message: str = "Access denied") -> None:
        super().__init__(message)
        self.status_code = 403


class Guard(ABC):
    """
    Abstract base guard.
    
    Guards determine if a user can access a route.
    Implement `can_access` to create custom guards.
    """
    
    @abstractmethod
    async def can_access(
        self,
        user: Optional[User],
        request: Any,
    ) -> bool:
        """
        Check if user can access the route.
        
        Args:
            user: Current user (None if not authenticated)
            request: Request object
            
        Returns:
            True if access is allowed
        """
        ...
        
    async def __call__(
        self,
        user: Optional[User],
        request: Any,
    ) -> bool:
        """Allow guard to be called directly."""
        return await self.can_access(user, request)
        
    def get_error(self) -> GuardError:
        """Get error to raise when guard fails."""
        return ForbiddenError()
        
    def __and__(self, other: Guard) -> CompositeGuard:
        """Combine guards with AND logic."""
        return CompositeGuard([self, other], mode="and")
        
    def __or__(self, other: Guard) -> CompositeGuard:
        """Combine guards with OR logic."""
        return CompositeGuard([self, other], mode="or")


class AuthGuard(Guard):
    """
    Guard that requires authentication.
    
    Fails if user is not logged in.
    
    Example:
        @app.route("/dashboard", guards=[AuthGuard()])
        async def dashboard(request):
            return "Welcome!"
    """
    
    def __init__(self, message: str = "Authentication required") -> None:
        self.message = message
        
    async def can_access(
        self,
        user: Optional[User],
        request: Any,
    ) -> bool:
        """Check if user is authenticated."""
        return user is not None and user.is_active
        
    def get_error(self) -> GuardError:
        return UnauthorizedError(self.message)


class GuestGuard(Guard):
    """
    Guard that requires NO authentication.
    
    Fails if user IS logged in.
    Useful for login/register pages.
    
    Example:
        @app.route("/login", guards=[GuestGuard()])
        async def login(request):
            return "Login form"
    """
    
    def __init__(
        self,
        redirect_to: Optional[str] = None,
        message: str = "Already authenticated",
    ) -> None:
        self.redirect_to = redirect_to
        self.message = message
        
    async def can_access(
        self,
        user: Optional[User],
        request: Any,
    ) -> bool:
        """Check if user is NOT authenticated."""
        return user is None
        
    def get_error(self) -> GuardError:
        return ForbiddenError(self.message)


class RoleGuard(Guard):
    """
    Guard that requires specific roles.
    
    Supports:
    - Single role
    - Multiple roles (any match)
    - All roles required
    
    Example:
        @app.route("/admin", guards=[RoleGuard("admin")])
        async def admin_panel(request):
            return "Admin panel"
            
        @app.route("/manage", guards=[RoleGuard(["admin", "manager"])])
        async def manage(request):
            return "Management"
    """
    
    def __init__(
        self,
        roles: Union[str, List[str]],
        require_all: bool = False,
        message: str = "Insufficient role",
    ) -> None:
        """
        Initialize role guard.
        
        Args:
            roles: Required role(s)
            require_all: If True, user must have ALL roles
            message: Error message on failure
        """
        if isinstance(roles, str):
            self.roles = {roles}
        else:
            self.roles = set(roles)
            
        self.require_all = require_all
        self.message = message
        
    async def can_access(
        self,
        user: Optional[User],
        request: Any,
    ) -> bool:
        """Check if user has required role(s)."""
        if user is None:
            return False
            
        if self.require_all:
            return self.roles.issubset(user.roles)
        else:
            return bool(self.roles & user.roles)
            
    def get_error(self) -> GuardError:
        return ForbiddenError(self.message)


class PermissionGuard(Guard):
    """
    Guard that requires specific permissions.
    
    Similar to RoleGuard but for fine-grained permissions.
    
    Example:
        @app.route("/posts", methods=["POST"], guards=[PermissionGuard("posts.create")])
        async def create_post(request):
            return "Created"
            
        @app.route("/posts/<id>", methods=["DELETE"], guards=[PermissionGuard("posts.delete")])
        async def delete_post(request, id):
            return "Deleted"
    """
    
    def __init__(
        self,
        permissions: Union[str, List[str]],
        require_all: bool = False,
        message: str = "Insufficient permissions",
    ) -> None:
        """
        Initialize permission guard.
        
        Args:
            permissions: Required permission(s)
            require_all: If True, user must have ALL permissions
            message: Error message on failure
        """
        if isinstance(permissions, str):
            self.permissions = {permissions}
        else:
            self.permissions = set(permissions)
            
        self.require_all = require_all
        self.message = message
        
    async def can_access(
        self,
        user: Optional[User],
        request: Any,
    ) -> bool:
        """Check if user has required permission(s)."""
        if user is None:
            return False
            
        if self.require_all:
            return self.permissions.issubset(user.permissions)
        else:
            return bool(self.permissions & user.permissions)
            
    def get_error(self) -> GuardError:
        return ForbiddenError(self.message)


class CompositeGuard(Guard):
    """
    Guard that combines multiple guards.
    
    Supports AND and OR composition.
    
    Example:
        # User must be admin OR have special permission
        guard = RoleGuard("admin") | PermissionGuard("special_access")
        
        # User must be authenticated AND have role
        guard = AuthGuard() & RoleGuard("member")
    """
    
    def __init__(
        self,
        guards: List[Guard],
        mode: str = "and",
    ) -> None:
        """
        Initialize composite guard.
        
        Args:
            guards: List of guards to combine
            mode: "and" (all must pass) or "or" (any can pass)
        """
        self.guards = guards
        self.mode = mode
        self._failed_guard: Optional[Guard] = None
        
    async def can_access(
        self,
        user: Optional[User],
        request: Any,
    ) -> bool:
        """Check all guards according to mode."""
        self._failed_guard = None
        
        if self.mode == "and":
            for guard in self.guards:
                if not await guard.can_access(user, request):
                    self._failed_guard = guard
                    return False
            return True
        else:  # or
            for guard in self.guards:
                if await guard.can_access(user, request):
                    return True
                self._failed_guard = guard
            return False
            
    def get_error(self) -> GuardError:
        """Get error from failed guard."""
        if self._failed_guard:
            return self._failed_guard.get_error()
        return ForbiddenError()


class CallbackGuard(Guard):
    """
    Guard that uses a callback function.
    
    For simple, one-off authorization checks.
    
    Example:
        async def is_owner(user, request):
            post_id = request.path_params.get("id")
            post = await get_post(post_id)
            return post.author_id == user.id
            
        @app.route("/posts/<id>/edit", guards=[CallbackGuard(is_owner)])
        async def edit_post(request, id):
            return "Edit form"
    """
    
    def __init__(
        self,
        callback: Callable,
        message: str = "Access denied",
    ) -> None:
        """
        Initialize callback guard.
        
        Args:
            callback: Function(user, request) -> bool
            message: Error message on failure
        """
        self.callback = callback
        self.message = message
        
    async def can_access(
        self,
        user: Optional[User],
        request: Any,
    ) -> bool:
        """Call the callback function."""
        if user is None:
            return False
            
        result = self.callback(user, request)
        
        # Handle async callbacks
        if hasattr(result, "__await__"):
            return await result
        return result
        
    def get_error(self) -> GuardError:
        return ForbiddenError(self.message)


# Decorator versions

def require_auth(
    message: str = "Authentication required",
) -> Callable:
    """
    Decorator to require authentication.
    
    Example:
        @app.route("/profile")
        @require_auth()
        async def profile(request):
            return f"Hello, {request.user.name}!"
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(request, *args, **kwargs):
            user = getattr(request, "user", None)
            
            if user is None or not getattr(user, "is_active", True):
                raise UnauthorizedError(message)
                
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_role(
    roles: Union[str, List[str]],
    require_all: bool = False,
    message: str = "Insufficient role",
) -> Callable:
    """
    Decorator to require specific role(s).
    
    Example:
        @app.route("/admin")
        @require_role("admin")
        async def admin_panel(request):
            return "Admin panel"
            
        @app.route("/manage")
        @require_role(["admin", "manager"])
        async def manage(request):
            return "Management"
    """
    if isinstance(roles, str):
        required_roles = {roles}
    else:
        required_roles = set(roles)
        
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(request, *args, **kwargs):
            user = getattr(request, "user", None)
            
            if user is None:
                raise UnauthorizedError()
                
            has_access = False
            if require_all:
                has_access = required_roles.issubset(user.roles)
            else:
                has_access = bool(required_roles & user.roles)
                
            if not has_access:
                raise ForbiddenError(message)
                
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_permission(
    permissions: Union[str, List[str]],
    require_all: bool = False,
    message: str = "Insufficient permissions",
) -> Callable:
    """
    Decorator to require specific permission(s).
    
    Example:
        @app.route("/posts", methods=["POST"])
        @require_permission("posts.create")
        async def create_post(request):
            return "Created"
    """
    if isinstance(permissions, str):
        required_permissions = {permissions}
    else:
        required_permissions = set(permissions)
        
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(request, *args, **kwargs):
            user = getattr(request, "user", None)
            
            if user is None:
                raise UnauthorizedError()
                
            has_access = False
            if require_all:
                has_access = required_permissions.issubset(user.permissions)
            else:
                has_access = bool(required_permissions & user.permissions)
                
            if not has_access:
                raise ForbiddenError(message)
                
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator


# Guard middleware

class GuardMiddleware:
    """
    Middleware that enforces guards on routes.
    
    Automatically checks guards defined on routes.
    """
    
    def __init__(
        self,
        get_user: Optional[Callable] = None,
        on_unauthorized: Optional[Callable] = None,
        on_forbidden: Optional[Callable] = None,
    ) -> None:
        """
        Initialize guard middleware.
        
        Args:
            get_user: Function to get current user from request
            on_unauthorized: Handler for unauthorized errors
            on_forbidden: Handler for forbidden errors
        """
        self.get_user = get_user or self._default_get_user
        self.on_unauthorized = on_unauthorized
        self.on_forbidden = on_forbidden
        
    def _default_get_user(self, request: Any) -> Optional[User]:
        """Default user getter."""
        return getattr(request, "user", None)
        
    async def __call__(self, request: Any, call_next: Any) -> Any:
        """Process request through guards."""
        # Get route guards
        route = getattr(request, "route", None)
        guards = getattr(route, "guards", []) if route else []
        
        if not guards:
            return await call_next(request)
            
        # Get current user
        user = self.get_user(request)
        
        # Check guards
        for guard in guards:
            try:
                if not await guard.can_access(user, request):
                    error = guard.get_error()
                    return await self._handle_error(request, error)
            except GuardError as e:
                return await self._handle_error(request, e)
                
        return await call_next(request)
        
    async def _handle_error(
        self,
        request: Any,
        error: GuardError,
    ) -> Any:
        """Handle guard error."""
        if isinstance(error, UnauthorizedError):
            if self.on_unauthorized:
                return await self.on_unauthorized(request, error)
        elif isinstance(error, ForbiddenError):
            if self.on_forbidden:
                return await self.on_forbidden(request, error)
                
        # Re-raise if no handler
        raise error
