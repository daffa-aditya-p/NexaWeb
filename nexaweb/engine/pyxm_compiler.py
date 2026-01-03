"""
NexaWeb PYXM Compiler
=====================

Compiles PYXM AST into optimized render functions. The compiler performs:
- Static analysis for optimization opportunities
- Code generation for dynamic content
- Event handler binding
- Attribute binding compilation
- Component instantiation

Output:
    The compiler produces CompiledTemplate objects containing:
    - render(): Async function that produces HTML
    - bindings: Extracted binding information
    - events: Event handler mappings
    - static_html: Pre-rendered static portions

Optimizations:
    1. Static Hoisting: Pre-render static subtrees
    2. Expression Caching: Cache repeated expressions
    3. Loop Unrolling: Optimize small static loops
    4. String Interning: Deduplicate string literals
"""

from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass, field
from html import escape as html_escape
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple

from nexaweb.engine.pyxm_parser import NodeType, PyxmAST, PyxmNode


@dataclass
class CompiledExpression:
    """Compiled Python expression."""
    source: str
    code: Any  # Compiled code object
    dependencies: Set[str]  # Variable dependencies
    is_safe: bool  # Whether output should be escaped


@dataclass
class CompiledTemplate:
    """
    Compiled template ready for rendering.
    
    Contains the render function and metadata about the template.
    """
    name: str
    source_hash: str
    render_code: str
    render_func: Callable[..., Coroutine[Any, Any, str]]
    static_parts: Dict[str, str]
    expressions: List[CompiledExpression]
    bindings: Dict[str, str]
    events: Dict[str, str]
    components: List[str]
    is_async: bool
    
    async def render(self, context: Dict[str, Any] = None) -> str:
        """Render template with given context."""
        context = context or {}
        return await self.render_func(context)
        
    def render_sync(self, context: Dict[str, Any] = None) -> str:
        """Synchronous render (for simple templates)."""
        import asyncio
        context = context or {}
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            
        return loop.run_until_complete(self.render_func(context))


class CompilerContext:
    """Compilation context for tracking state."""
    
    def __init__(self) -> None:
        self.indent_level = 0
        self.output_parts: List[str] = []
        self.static_parts: Dict[str, str] = {}
        self.expressions: List[CompiledExpression] = []
        self.temp_var_counter = 0
        self.loop_depth = 0
        self.seen_expressions: Dict[str, str] = {}  # Expression -> temp var
        
    def indent(self) -> str:
        """Get current indentation."""
        return "    " * self.indent_level
        
    def emit(self, code: str) -> None:
        """Emit a line of code."""
        self.output_parts.append(f"{self.indent()}{code}")
        
    def new_temp_var(self, prefix: str = "_t") -> str:
        """Generate a new temporary variable name."""
        self.temp_var_counter += 1
        return f"{prefix}{self.temp_var_counter}"
        
    def enter_scope(self) -> None:
        """Enter a new scope (increase indent)."""
        self.indent_level += 1
        
    def exit_scope(self) -> None:
        """Exit scope (decrease indent)."""
        self.indent_level -= 1
        
    def get_code(self) -> str:
        """Get generated code."""
        return "\n".join(self.output_parts)


class PyxmCompiler:
    """
    Compiles PYXM AST to executable render functions.
    
    The compiler generates Python async functions that produce HTML
    strings when called with a context dictionary.
    
    Example:
        compiler = PyxmCompiler()
        compiled = compiler.compile(ast)
        html = await compiled.render({"name": "World"})
    """
    
    # HTML tags that should not have closing tags
    VOID_ELEMENTS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr"
    }
    
    # Attributes that should not be escaped
    SAFE_ATTRIBUTES = {"id", "class", "style", "href", "src", "name", "type"}
    
    def __init__(self) -> None:
        self.context: Optional[CompilerContext] = None
        self._builtin_filters = self._create_builtin_filters()
        
    def _create_builtin_filters(self) -> Dict[str, Callable]:
        """Create built-in template filters."""
        return {
            "escape": html_escape,
            "e": html_escape,
            "safe": lambda x: x,
            "upper": str.upper,
            "lower": str.lower,
            "title": str.title,
            "strip": str.strip,
            "length": len,
            "first": lambda x: x[0] if x else None,
            "last": lambda x: x[-1] if x else None,
            "join": lambda x, sep=", ": sep.join(str(i) for i in x),
            "default": lambda x, d="": x if x else d,
            "int": int,
            "float": float,
            "str": str,
            "bool": bool,
            "list": list,
            "dict": dict,
            "json": lambda x: __import__("json").dumps(x),
        }
        
    def compile(
        self,
        ast: PyxmAST,
        name: str = "template",
    ) -> CompiledTemplate:
        """
        Compile PYXM AST to CompiledTemplate.
        
        Args:
            ast: Parsed PYXM AST
            name: Template name for identification
            
        Returns:
            CompiledTemplate ready for rendering
        """
        self.context = CompilerContext()
        
        # Generate source hash
        source_repr = str(ast.root.to_dict())
        source_hash = hashlib.md5(source_repr.encode()).hexdigest()[:12]
        
        # Emit function header
        self.context.emit("async def _render(_ctx):")
        self.context.enter_scope()
        
        # Emit local variable setup
        self.context.emit("_output = []")
        self.context.emit("_append = _output.append")
        self.context.emit("_escape = __builtins_escape__")
        self.context.emit("")
        
        # Emit Python setup blocks
        for block in ast.python_blocks:
            # Execute Python blocks to define functions/variables
            self._emit_python_block(block)
            
        # Emit render code
        self._compile_node(ast.root)
        
        # Emit return
        self.context.emit("")
        self.context.emit("return ''.join(_output)")
        
        self.context.exit_scope()
        
        # Get generated code
        render_code = self.context.get_code()
        
        # Compile render function
        render_func = self._compile_render_function(render_code)
        
        # Collect metadata
        bindings = self._collect_bindings(ast.root)
        events = self._collect_events(ast.root)
        components = list(ast.components.keys())
        
        return CompiledTemplate(
            name=name,
            source_hash=source_hash,
            render_code=render_code,
            render_func=render_func,
            static_parts=self.context.static_parts,
            expressions=self.context.expressions,
            bindings=bindings,
            events=events,
            components=components,
            is_async=True,
        )
        
    def _emit_python_block(self, block: str) -> None:
        """Emit Python block code."""
        lines = block.strip().split("\n")
        for line in lines:
            # Skip empty lines and imports (handled separately)
            stripped = line.strip()
            if not stripped or stripped.startswith("import ") or stripped.startswith("from "):
                continue
            self.context.emit(line)
        self.context.emit("")
        
    def _compile_node(self, node: PyxmNode) -> None:
        """Compile a single AST node."""
        if node.type == NodeType.ROOT:
            for child in node.children:
                self._compile_node(child)
                
        elif node.type == NodeType.TEXT:
            self._compile_text(node)
            
        elif node.type == NodeType.EXPRESSION:
            self._compile_expression(node)
            
        elif node.type == NodeType.ELEMENT:
            self._compile_element(node)
            
        elif node.type == NodeType.IF:
            self._compile_if(node)
            
        elif node.type == NodeType.FOR:
            self._compile_for(node)
            
        elif node.type == NodeType.COMPONENT:
            self._compile_component(node)
            
        elif node.type == NodeType.SLOT:
            self._compile_slot(node)
            
        elif node.type == NodeType.BLOCK:
            self._compile_block(node)
            
        elif node.type == NodeType.RAW:
            self._compile_raw(node)
            
        elif node.type == NodeType.COMMENT:
            # Skip comments in output
            pass
            
    def _compile_text(self, node: PyxmNode) -> None:
        """Compile text node."""
        if node.content:
            # Escape and emit text
            escaped = repr(node.content)
            self.context.emit(f"_append({escaped})")
            
    def _compile_expression(self, node: PyxmNode) -> None:
        """Compile expression {{ expr }}."""
        if not node.content:
            return
            
        expr = node.content.strip()
        
        # Check for filters (expr | filter)
        if "|" in expr:
            expr = self._compile_filters(expr)
            
        # Check if expression should be safe (not escaped)
        is_safe = expr.endswith("|safe") or "safe(" in expr
        
        if is_safe:
            self.context.emit(f"_append(str({expr}))")
        else:
            self.context.emit(f"_append(_escape(str({expr})))")
            
    def _compile_filters(self, expr: str) -> str:
        """Compile filter chain."""
        parts = [p.strip() for p in expr.split("|")]
        result = parts[0]
        
        for filter_expr in parts[1:]:
            # Parse filter with arguments: filter(arg1, arg2)
            if "(" in filter_expr:
                filter_name = filter_expr[:filter_expr.index("(")]
                args = filter_expr[filter_expr.index("("):]
                result = f"_filters['{filter_name}']({result}, {args[1:-1]})"
            else:
                result = f"_filters['{filter_expr}']({result})"
                
        return result
        
    def _compile_element(self, node: PyxmNode) -> None:
        """Compile HTML element."""
        tag = node.tag
        
        # Start tag
        self.context.emit(f"_append('<{tag}')")
        
        # Static attributes
        for name, value in node.attributes.items():
            if value is True:
                self.context.emit(f"_append(' {name}')")
            else:
                escaped_value = html_escape(str(value), quote=True)
                self.context.emit(f"_append(' {name}=\"{escaped_value}\"')")
                
        # Dynamic attribute bindings
        for name, expr in node.bindings.items():
            var = self.context.new_temp_var("_attr")
            self.context.emit(f"{var} = {expr}")
            self.context.emit(f"if {var} is not None:")
            self.context.enter_scope()
            if name == "class" and isinstance(expr, str) and "{" in expr:
                # Class object binding
                self.context.emit(f"_append(' class=\"' + _escape(str({var})) + '\"')")
            elif name == "style" and isinstance(expr, str) and "{" in expr:
                # Style object binding
                self.context.emit(f"_append(' style=\"' + _escape(str({var})) + '\"')")
            else:
                self.context.emit(f"_append(' {name}=\"' + _escape(str({var})) + '\"')")
            self.context.exit_scope()
            
        # Event bindings (for client-side hydration)
        for event, handler in node.events.items():
            # Emit data attribute for client-side binding
            self.context.emit(f"_append(' data-nexa-on-{event}=\"{handler}\"')")
            
        # Refs
        for ref in node.refs:
            self.context.emit(f"_append(' data-nexa-ref=\"{ref}\"')")
            
        # Close start tag
        if node.is_self_closing or tag in self.VOID_ELEMENTS:
            self.context.emit("_append(' />')")
            return
        else:
            self.context.emit("_append('>')")
            
        # Children
        for child in node.children:
            self._compile_node(child)
            
        # End tag
        self.context.emit(f"_append('</{tag}>')")
        
    def _compile_if(self, node: PyxmNode) -> None:
        """Compile if/elif/else block."""
        self.context.emit(f"if {node.condition}:")
        self.context.enter_scope()
        
        # Compile children that are not elif/else
        for child in node.children:
            if child.type == NodeType.ELIF:
                self.context.exit_scope()
                self.context.emit(f"elif {child.condition}:")
                self.context.enter_scope()
                for elif_child in child.children:
                    if elif_child.type not in (NodeType.ELIF, NodeType.ELSE):
                        self._compile_node(elif_child)
            elif child.type == NodeType.ELSE:
                self.context.exit_scope()
                self.context.emit("else:")
                self.context.enter_scope()
                for else_child in child.children:
                    self._compile_node(else_child)
            else:
                self._compile_node(child)
                
        self.context.exit_scope()
        
    def _compile_for(self, node: PyxmNode) -> None:
        """Compile for loop."""
        self.context.loop_depth += 1
        
        # Parse iterator: "item in items" or "key, value in items.items()"
        iterator = node.iterator
        
        self.context.emit(f"for {iterator}:")
        self.context.enter_scope()
        
        # Add loop helper variables
        loop_var = f"_loop{self.context.loop_depth}"
        self.context.emit(f"{loop_var} = {{'index': 0, 'first': True, 'last': False}}")
        
        for child in node.children:
            self._compile_node(child)
            
        # Update loop variable
        self.context.emit(f"{loop_var}['index'] += 1")
        self.context.emit(f"{loop_var}['first'] = False")
        
        self.context.exit_scope()
        self.context.loop_depth -= 1
        
    def _compile_component(self, node: PyxmNode) -> None:
        """Compile component usage."""
        component_name = node.tag
        
        # Check if component exists in context
        self.context.emit(f"if '{component_name}' in _ctx.get('_components', {{}}):")
        self.context.enter_scope()
        
        # Build props from attributes and bindings
        props_var = self.context.new_temp_var("_props")
        self.context.emit(f"{props_var} = {{}}")
        
        for name, value in node.attributes.items():
            self.context.emit(f"{props_var}['{name}'] = {repr(value)}")
            
        for name, expr in node.bindings.items():
            self.context.emit(f"{props_var}['{name}'] = {expr}")
            
        # Render component
        self.context.emit(f"_component = _ctx['_components']['{component_name}']")
        self.context.emit(f"_component_result = await _component.render({props_var})")
        self.context.emit("_append(_component_result)")
        
        self.context.exit_scope()
        
        # Fallback: render children as default content
        self.context.emit("else:")
        self.context.enter_scope()
        for child in node.children:
            self._compile_node(child)
        self.context.exit_scope()
        
    def _compile_slot(self, node: PyxmNode) -> None:
        """Compile slot for component content projection."""
        slot_name = node.tag or "default"
        
        self.context.emit(f"if '{slot_name}' in _ctx.get('_slots', {{}}):")
        self.context.enter_scope()
        self.context.emit(f"_append(_ctx['_slots']['{slot_name}'])")
        self.context.exit_scope()
        
        # Default slot content
        if node.children:
            self.context.emit("else:")
            self.context.enter_scope()
            for child in node.children:
                self._compile_node(child)
            self.context.exit_scope()
            
    def _compile_block(self, node: PyxmNode) -> None:
        """Compile template block for inheritance."""
        block_name = node.tag
        
        # Check if block is overridden
        self.context.emit(f"if '{block_name}' in _ctx.get('_blocks', {{}}):")
        self.context.enter_scope()
        self.context.emit(f"_append(_ctx['_blocks']['{block_name}'])")
        self.context.exit_scope()
        
        self.context.emit("else:")
        self.context.enter_scope()
        for child in node.children:
            self._compile_node(child)
        self.context.exit_scope()
        
    def _compile_raw(self, node: PyxmNode) -> None:
        """Compile raw block (output as-is, no processing)."""
        if node.content:
            self.context.emit(f"_append({repr(node.content)})")
            
    def _compile_render_function(
        self,
        code: str,
    ) -> Callable[..., Coroutine[Any, Any, str]]:
        """Compile render code to executable function."""
        # Build execution namespace
        namespace = {
            "__builtins_escape__": html_escape,
            "_filters": self._builtin_filters,
        }
        
        # Execute code to define function
        exec(code, namespace)
        
        # Get and wrap render function
        raw_render = namespace["_render"]
        
        async def render(context: Dict[str, Any] = None) -> str:
            ctx = context or {}
            return await raw_render(ctx)
            
        return render
        
    def _collect_bindings(self, node: PyxmNode) -> Dict[str, str]:
        """Collect all attribute bindings from AST."""
        bindings = {}
        
        def collect(n: PyxmNode):
            bindings.update(n.bindings)
            for child in n.children:
                collect(child)
                
        collect(node)
        return bindings
        
    def _collect_events(self, node: PyxmNode) -> Dict[str, str]:
        """Collect all event bindings from AST."""
        events = {}
        
        def collect(n: PyxmNode):
            events.update(n.events)
            for child in n.children:
                collect(child)
                
        collect(node)
        return events


class TemplateCache:
    """
    LRU cache for compiled templates.
    
    Caches compiled templates to avoid re-parsing and re-compiling
    on every render.
    """
    
    def __init__(self, max_size: int = 100) -> None:
        self.max_size = max_size
        self._cache: Dict[str, CompiledTemplate] = {}
        self._access_order: List[str] = []
        
    def get(self, key: str) -> Optional[CompiledTemplate]:
        """Get compiled template from cache."""
        if key in self._cache:
            # Update access order
            self._access_order.remove(key)
            self._access_order.append(key)
            return self._cache[key]
        return None
        
    def set(self, key: str, template: CompiledTemplate) -> None:
        """Add compiled template to cache."""
        if key in self._cache:
            self._access_order.remove(key)
        elif len(self._cache) >= self.max_size:
            # Evict least recently used
            oldest = self._access_order.pop(0)
            del self._cache[oldest]
            
        self._cache[key] = template
        self._access_order.append(key)
        
    def clear(self) -> None:
        """Clear all cached templates."""
        self._cache.clear()
        self._access_order.clear()
        
    def __contains__(self, key: str) -> bool:
        return key in self._cache
        
    def __len__(self) -> int:
        return len(self._cache)


# Global template cache
_template_cache = TemplateCache()


def get_template_cache() -> TemplateCache:
    """Get global template cache."""
    return _template_cache
