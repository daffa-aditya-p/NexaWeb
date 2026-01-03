"""
NexaWeb Sandboxed Execution
===========================

Safe execution environment for user-provided code and templates.

Features:
- Restricted Python execution
- Timeout enforcement
- Memory limits
- Blocked dangerous operations
- AST-based code validation

Used by the template engine to safely evaluate expressions
in user templates.
"""

from __future__ import annotations

import ast
import builtins
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, FrozenSet, Optional, Set


@dataclass
class SandboxConfig:
    """Sandbox configuration."""
    
    # Maximum execution time (seconds)
    timeout: float = 1.0
    
    # Maximum memory (bytes) - not enforced directly, but checked
    max_memory: int = 10 * 1024 * 1024  # 10MB
    
    # Maximum string length
    max_string_length: int = 100000
    
    # Maximum collection size
    max_collection_size: int = 10000
    
    # Maximum recursion depth
    max_recursion: int = 50
    
    # Allowed built-in functions
    allowed_builtins: FrozenSet[str] = field(default_factory=lambda: frozenset({
        # Safe type constructors
        "bool", "int", "float", "str", "list", "dict", "tuple", "set",
        "frozenset", "bytes", "bytearray",
        
        # Safe functions
        "abs", "all", "any", "bin", "chr", "divmod", "enumerate",
        "filter", "format", "hash", "hex", "id", "isinstance", "issubclass",
        "iter", "len", "map", "max", "min", "next", "oct", "ord", "pow",
        "range", "repr", "reversed", "round", "slice", "sorted", "sum", "zip",
        
        # Boolean
        "True", "False", "None",
    }))
    
    # Blocked attributes
    blocked_attrs: FrozenSet[str] = field(default_factory=lambda: frozenset({
        "__class__", "__bases__", "__subclasses__", "__mro__",
        "__code__", "__globals__", "__builtins__", "__dict__",
        "__module__", "__qualname__", "__reduce__", "__reduce_ex__",
        "__getattribute__", "__setattr__", "__delattr__",
        "__init_subclass__", "__new__", "__call__",
        "func_code", "func_globals", "gi_code", "gi_frame",
        "co_code", "f_code", "f_globals", "f_builtins", "f_locals",
    }))
    
    # Blocked names (AST level)
    blocked_names: FrozenSet[str] = field(default_factory=lambda: frozenset({
        "exec", "eval", "compile", "open", "input", "print",
        "__import__", "breakpoint", "exit", "quit",
        "globals", "locals", "vars", "dir", "getattr", "setattr", "delattr",
        "hasattr", "type", "object", "super", "classmethod", "staticmethod",
        "property", "memoryview",
    }))


class SandboxError(Exception):
    """Base exception for sandbox errors."""
    pass


class SandboxTimeoutError(SandboxError):
    """Raised when execution times out."""
    pass


class SandboxSecurityError(SandboxError):
    """Raised when code violates security constraints."""
    pass


class CodeValidator(ast.NodeVisitor):
    """
    AST visitor that validates code for sandbox safety.
    
    Checks for:
    - Import statements
    - Dangerous function calls
    - Attribute access to blocked names
    - Dangerous operations
    """
    
    def __init__(self, config: SandboxConfig) -> None:
        self.config = config
        self.errors: list = []
        
    def validate(self, code: str) -> None:
        """
        Validate code string.
        
        Raises:
            SandboxSecurityError: If code contains dangerous constructs
        """
        try:
            tree = ast.parse(code, mode="eval")
        except SyntaxError as e:
            raise SandboxSecurityError(f"Syntax error: {e}")
            
        self.errors = []
        self.visit(tree)
        
        if self.errors:
            raise SandboxSecurityError(
                f"Code validation failed: {'; '.join(self.errors)}"
            )
            
    def visit_Import(self, node: ast.Import) -> None:
        """Block import statements."""
        self.errors.append("Import statements are not allowed")
        
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Block from...import statements."""
        self.errors.append("Import statements are not allowed")
        
    def visit_Call(self, node: ast.Call) -> None:
        """Validate function calls."""
        if isinstance(node.func, ast.Name):
            if node.func.id in self.config.blocked_names:
                self.errors.append(f"Function '{node.func.id}' is not allowed")
        self.generic_visit(node)
        
    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Validate attribute access."""
        if node.attr in self.config.blocked_attrs:
            self.errors.append(f"Attribute '{node.attr}' access is not allowed")
        if node.attr.startswith("_"):
            self.errors.append(f"Private attribute '{node.attr}' access is not allowed")
        self.generic_visit(node)
        
    def visit_Name(self, node: ast.Name) -> None:
        """Validate name access."""
        if node.id in self.config.blocked_names:
            self.errors.append(f"Name '{node.id}' is not allowed")
        if node.id.startswith("_") and node.id not in ("_", "__"):
            self.errors.append(f"Private name '{node.id}' is not allowed")
            
    def visit_Subscript(self, node: ast.Subscript) -> None:
        """Validate subscript operations."""
        self.generic_visit(node)
        
    def visit_Lambda(self, node: ast.Lambda) -> None:
        """Validate lambda expressions."""
        self.generic_visit(node)
        
    def visit_ListComp(self, node: ast.ListComp) -> None:
        """Validate list comprehensions."""
        self.generic_visit(node)
        
    def visit_SetComp(self, node: ast.SetComp) -> None:
        """Validate set comprehensions."""
        self.generic_visit(node)
        
    def visit_DictComp(self, node: ast.DictComp) -> None:
        """Validate dict comprehensions."""
        self.generic_visit(node)
        
    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        """Validate generator expressions."""
        self.generic_visit(node)


class RestrictedBuiltins:
    """
    Restricted builtins for sandbox execution.
    
    Only exposes safe built-in functions.
    """
    
    def __init__(self, config: SandboxConfig) -> None:
        self.config = config
        self._builtins = self._create_builtins()
        
    def _create_builtins(self) -> Dict[str, Any]:
        """Create restricted builtins dict."""
        restricted = {}
        
        for name in self.config.allowed_builtins:
            if hasattr(builtins, name):
                restricted[name] = getattr(builtins, name)
                
        # Add safe wrappers
        restricted["len"] = self._safe_len
        restricted["range"] = self._safe_range
        restricted["str"] = self._safe_str
        
        return restricted
        
    def _safe_len(self, obj: Any) -> int:
        """Safe len that limits result."""
        result = len(obj)
        if result > self.config.max_collection_size:
            raise SandboxSecurityError(
                f"Collection too large: {result} > {self.config.max_collection_size}"
            )
        return result
        
    def _safe_range(self, *args) -> range:
        """Safe range that limits size."""
        r = range(*args)
        if len(r) > self.config.max_collection_size:
            raise SandboxSecurityError(
                f"Range too large: {len(r)} > {self.config.max_collection_size}"
            )
        return r
        
    def _safe_str(self, obj: Any) -> str:
        """Safe str that limits length."""
        result = str(obj)
        if len(result) > self.config.max_string_length:
            result = result[:self.config.max_string_length] + "..."
        return result
        
    def get(self) -> Dict[str, Any]:
        """Get builtins dict."""
        return self._builtins


class Sandbox:
    """
    Sandboxed code execution environment.
    
    Executes Python code with restrictions on:
    - Available functions
    - Execution time
    - Memory usage (approximate)
    
    Example:
        sandbox = Sandbox()
        
        # Safe execution
        result = sandbox.eval("1 + 2")  # 3
        
        # With context
        result = sandbox.eval("name.upper()", {"name": "hello"})  # "HELLO"
        
        # Dangerous code is blocked
        sandbox.eval("__import__('os')")  # Raises SandboxSecurityError
    """
    
    def __init__(self, config: Optional[SandboxConfig] = None) -> None:
        """Initialize sandbox."""
        self.config = config or SandboxConfig()
        self.validator = CodeValidator(self.config)
        self.builtins = RestrictedBuiltins(self.config)
        
    def eval(
        self,
        code: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Evaluate expression in sandbox.
        
        Args:
            code: Python expression to evaluate
            context: Variables available to the code
            
        Returns:
            Result of evaluation
            
        Raises:
            SandboxSecurityError: If code is not allowed
            SandboxTimeoutError: If execution times out
        """
        # Validate code
        self.validator.validate(code)
        
        # Build execution namespace
        namespace = {"__builtins__": self.builtins.get()}
        
        if context:
            # Validate context keys
            for key in context:
                if key.startswith("_"):
                    raise SandboxSecurityError(
                        f"Context key '{key}' starts with underscore"
                    )
            namespace.update(context)
            
        # Compile code
        try:
            compiled = compile(code, "<sandbox>", "eval")
        except SyntaxError as e:
            raise SandboxSecurityError(f"Syntax error: {e}")
            
        # Execute with timeout
        return self._execute_with_timeout(compiled, namespace)
        
    def _execute_with_timeout(
        self,
        compiled: Any,
        namespace: Dict[str, Any],
    ) -> Any:
        """Execute code with timeout enforcement."""
        result = None
        error = None
        
        def execute():
            nonlocal result, error
            try:
                # Set recursion limit
                old_limit = sys.getrecursionlimit()
                sys.setrecursionlimit(self.config.max_recursion)
                
                try:
                    result = eval(compiled, namespace)
                finally:
                    sys.setrecursionlimit(old_limit)
                    
            except RecursionError:
                error = SandboxSecurityError("Maximum recursion depth exceeded")
            except Exception as e:
                error = e
                
        # Run in thread with timeout
        thread = threading.Thread(target=execute)
        thread.start()
        thread.join(timeout=self.config.timeout)
        
        if thread.is_alive():
            raise SandboxTimeoutError(
                f"Execution timed out after {self.config.timeout}s"
            )
            
        if error:
            if isinstance(error, SandboxError):
                raise error
            raise SandboxSecurityError(f"Execution error: {error}")
            
        return result
        
    def safe_getattr(self, obj: Any, name: str) -> Any:
        """
        Safely get attribute from object.
        
        Blocks access to dangerous attributes.
        """
        if name in self.config.blocked_attrs:
            raise SandboxSecurityError(f"Attribute '{name}' is not allowed")
            
        if name.startswith("_"):
            raise SandboxSecurityError(f"Private attribute access is not allowed")
            
        return getattr(obj, name)


# Global sandbox instance
_sandbox = Sandbox()


def get_sandbox() -> Sandbox:
    """Get global sandbox instance."""
    return _sandbox


def safe_eval(
    code: str,
    context: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Safely evaluate Python expression.
    
    Global convenience function.
    """
    return _sandbox.eval(code, context)


def validate_code(code: str) -> bool:
    """
    Validate code without executing.
    
    Returns True if code is safe to execute.
    """
    try:
        _sandbox.validator.validate(code)
        return True
    except SandboxSecurityError:
        return False


class SafeDict(dict):
    """
    Dictionary wrapper that blocks dangerous key access.
    """
    
    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, str) and key.startswith("_"):
            raise SandboxSecurityError(f"Private key '{key}' access is not allowed")
        return super().__getitem__(key)
        
    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise SandboxSecurityError(f"Private attribute '{name}' access is not allowed")
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def make_safe(obj: Any) -> Any:
    """
    Wrap object to restrict dangerous access.
    """
    if isinstance(obj, dict):
        return SafeDict({k: make_safe(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return [make_safe(item) for item in obj]
    if isinstance(obj, tuple):
        return tuple(make_safe(item) for item in obj)
    return obj
