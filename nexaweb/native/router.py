"""
NexaWeb Native Router
=====================

High-performance route matching.
This is a Python stub that can be replaced with a native implementation.

The native implementation would use:
- Radix tree for O(log n) route matching
- Compiled regex patterns
- Memory-efficient parameter extraction
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Pattern, Tuple, Union


@dataclass
class RouteMatch:
    """
    Route match result.
    
    Attributes:
        handler: Matched handler
        params: Extracted parameters
        path: Matched path pattern
        method: HTTP method
    """
    
    handler: Any
    params: Dict[str, str]
    path: str
    method: str
    name: Optional[str] = None
    
    def __bool__(self) -> bool:
        return self.handler is not None


@dataclass
class RouteNode:
    """
    Radix tree node for route matching.
    
    In native implementation, this would be a C++ struct.
    """
    
    segment: str
    handler: Optional[Any] = None
    params: Dict[str, str] = field(default_factory=dict)
    children: Dict[str, "RouteNode"] = field(default_factory=dict)
    param_child: Optional["RouteNode"] = None
    wildcard_child: Optional["RouteNode"] = None
    pattern: Optional[Pattern] = None
    name: Optional[str] = None


class NativeRouter:
    """
    High-performance route matcher.
    
    This Python implementation provides the same API as the
    native C++ version but with pure Python performance.
    
    Example:
        router = NativeRouter()
        
        router.add("GET", "/users", list_users)
        router.add("GET", "/users/{id}", get_user)
        router.add("POST", "/users", create_user)
        
        match = router.match("GET", "/users/123")
        print(match.handler)  # get_user
        print(match.params)   # {"id": "123"}
    
    Native implementation would provide:
        - 10-100x faster route matching
        - Lower memory usage
        - Better cache utilization
    """
    
    # Parameter pattern
    PARAM_PATTERN = re.compile(r"\{(\w+)(?::([^}]+))?\}")
    
    def __init__(self):
        """Initialize router."""
        self._trees: Dict[str, RouteNode] = {}
        self._routes: List[Tuple[str, str, Any, Optional[str]]] = []
        self._compiled = False
    
    def add(
        self,
        method: str,
        path: str,
        handler: Any,
        name: Optional[str] = None,
    ) -> None:
        """
        Add route.
        
        Args:
            method: HTTP method
            path: URL path pattern
            handler: Route handler
            name: Optional route name
        """
        method = method.upper()
        
        # Store route
        self._routes.append((method, path, handler, name))
        
        # Get or create tree for method
        if method not in self._trees:
            self._trees[method] = RouteNode(segment="")
        
        # Insert into radix tree
        self._insert(self._trees[method], path, handler, name)
        
        self._compiled = False
    
    def _insert(
        self,
        node: RouteNode,
        path: str,
        handler: Any,
        name: Optional[str],
    ) -> None:
        """Insert route into radix tree."""
        if not path or path == "/":
            node.handler = handler
            node.name = name
            return
        
        # Remove leading slash
        if path.startswith("/"):
            path = path[1:]
        
        # Split into segments
        segments = path.split("/")
        current = node
        
        for segment in segments:
            # Check for parameter
            param_match = self.PARAM_PATTERN.fullmatch(segment)
            
            if param_match:
                # Parameter segment
                param_name = param_match.group(1)
                param_pattern = param_match.group(2)
                
                if not current.param_child:
                    current.param_child = RouteNode(segment=f":{param_name}")
                    if param_pattern:
                        current.param_child.pattern = re.compile(f"^{param_pattern}$")
                
                current.param_child.params[param_name] = ""
                current = current.param_child
                
            elif segment == "*":
                # Wildcard
                if not current.wildcard_child:
                    current.wildcard_child = RouteNode(segment="*")
                current = current.wildcard_child
                
            else:
                # Static segment
                if segment not in current.children:
                    current.children[segment] = RouteNode(segment=segment)
                current = current.children[segment]
        
        current.handler = handler
        current.name = name
    
    def match(self, method: str, path: str) -> RouteMatch:
        """
        Match path against routes.
        
        Args:
            method: HTTP method
            path: URL path
            
        Returns:
            RouteMatch result
        """
        method = method.upper()
        
        # Get tree for method
        tree = self._trees.get(method)
        
        if not tree:
            return RouteMatch(handler=None, params={}, path="", method=method)
        
        # Remove leading slash and split
        if path.startswith("/"):
            path = path[1:]
        
        segments = path.split("/") if path else []
        
        # Match against tree
        params: Dict[str, str] = {}
        handler, matched_name = self._match_node(tree, segments, params)
        
        if handler:
            return RouteMatch(
                handler=handler,
                params=params,
                path=path,
                method=method,
                name=matched_name,
            )
        
        return RouteMatch(handler=None, params={}, path="", method=method)
    
    def _match_node(
        self,
        node: RouteNode,
        segments: List[str],
        params: Dict[str, str],
    ) -> Tuple[Optional[Any], Optional[str]]:
        """Match segments against node."""
        if not segments:
            return node.handler, node.name
        
        segment = segments[0]
        remaining = segments[1:]
        
        # Try static match first
        if segment in node.children:
            handler, name = self._match_node(node.children[segment], remaining, params)
            if handler:
                return handler, name
        
        # Try parameter match
        if node.param_child:
            # Check pattern if exists
            if node.param_child.pattern:
                if not node.param_child.pattern.match(segment):
                    pass  # Pattern doesn't match, try wildcard
                else:
                    for param_name in node.param_child.params:
                        params[param_name] = segment
                    handler, name = self._match_node(node.param_child, remaining, params)
                    if handler:
                        return handler, name
            else:
                for param_name in node.param_child.params:
                    params[param_name] = segment
                handler, name = self._match_node(node.param_child, remaining, params)
                if handler:
                    return handler, name
        
        # Try wildcard match
        if node.wildcard_child:
            params["*"] = "/".join([segment] + remaining)
            return node.wildcard_child.handler, node.wildcard_child.name
        
        return None, None
    
    def compile(self) -> None:
        """
        Compile routes for optimal matching.
        
        Native implementation would:
        - Build optimized data structures
        - Pre-compile all regex patterns
        - Sort routes by specificity
        """
        # Sort children by length (longer matches first)
        for tree in self._trees.values():
            self._sort_node(tree)
        
        self._compiled = True
    
    def _sort_node(self, node: RouteNode) -> None:
        """Sort node children by priority."""
        if node.children:
            # Sort by segment length (descending) for longest match first
            node.children = dict(
                sorted(
                    node.children.items(),
                    key=lambda x: len(x[0]),
                    reverse=True,
                )
            )
            for child in node.children.values():
                self._sort_node(child)
    
    def routes(self) -> List[Tuple[str, str, Any, Optional[str]]]:
        """Get all registered routes."""
        return self._routes.copy()
    
    def __len__(self) -> int:
        return len(self._routes)


# Native implementation placeholder
# This would be replaced by Cython or pybind11 binding
"""
// C++ Native Implementation (router.cpp)

#include <unordered_map>
#include <vector>
#include <string>
#include <regex>
#include <memory>

namespace nexaweb {

struct RouteMatch {
    void* handler;
    std::unordered_map<std::string, std::string> params;
    std::string path;
    std::string method;
};

struct RouteNode {
    std::string segment;
    void* handler = nullptr;
    std::unordered_map<std::string, std::shared_ptr<RouteNode>> children;
    std::shared_ptr<RouteNode> param_child;
    std::shared_ptr<RouteNode> wildcard_child;
    std::regex pattern;
    std::vector<std::string> param_names;
};

class NativeRouter {
public:
    void add(const std::string& method, const std::string& path, void* handler);
    RouteMatch match(const std::string& method, const std::string& path);
    void compile();
    
private:
    std::unordered_map<std::string, std::shared_ptr<RouteNode>> trees_;
    void insert(std::shared_ptr<RouteNode> node, const std::string& path, void* handler);
    RouteMatch match_node(std::shared_ptr<RouteNode> node, 
                          const std::vector<std::string>& segments,
                          std::unordered_map<std::string, std::string>& params);
};

}  // namespace nexaweb
"""
