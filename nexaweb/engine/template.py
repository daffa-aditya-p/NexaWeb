"""
NexaWeb Template Interface
==========================

High-level template API for loading, compiling, and rendering PYXM templates.

Features:
- File-based template loading
- String template compilation
- Template inheritance
- Component registration
- Automatic caching
- Async and sync rendering

Example:
    # Load and render template file
    html = await render_file("templates/home.pyxm", {"title": "Home"})
    
    # Render string template
    html = await render("<h1>{{ title }}</h1>", {"title": "Hello"})
    
    # Using Template class
    template = Template.from_file("templates/base.pyxm")
    html = await template.render({"content": "Page content"})
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from nexaweb.engine.pyxm_parser import PyxmParser, PyxmAST
from nexaweb.engine.pyxm_compiler import (
    PyxmCompiler,
    CompiledTemplate,
    get_template_cache,
)


class TemplateError(Exception):
    """Base exception for template errors."""
    pass


class TemplateNotFoundError(TemplateError):
    """Raised when template file is not found."""
    pass


class TemplateSyntaxError(TemplateError):
    """Raised when template has syntax errors."""
    pass


class TemplateRenderError(TemplateError):
    """Raised when template rendering fails."""
    pass


class Template:
    """
    Template wrapper providing high-level template operations.
    
    Handles parsing, compilation, caching, and rendering of PYXM templates.
    
    Example:
        # From string
        template = Template("<h1>{{ title }}</h1>")
        html = await template.render({"title": "Hello"})
        
        # From file
        template = Template.from_file("templates/page.pyxm")
        html = await template.render({"data": page_data})
        
        # With inheritance
        template = Template.from_file("templates/child.pyxm")
        template.extends("templates/base.pyxm")
        html = await template.render(context)
    """
    
    def __init__(
        self,
        source: str,
        name: str = "template",
        auto_compile: bool = True,
    ) -> None:
        """
        Create template from source string.
        
        Args:
            source: PYXM template source
            name: Template name for identification
            auto_compile: Whether to compile immediately
        """
        self.source = source
        self.name = name
        self._ast: Optional[PyxmAST] = None
        self._compiled: Optional[CompiledTemplate] = None
        self._parent: Optional[Template] = None
        self._components: Dict[str, Template] = {}
        self._blocks: Dict[str, str] = {}
        
        if auto_compile:
            self._compile()
            
    @classmethod
    def from_file(
        cls,
        path: Union[str, Path],
        encoding: str = "utf-8",
    ) -> "Template":
        """
        Load template from file.
        
        Args:
            path: Path to .pyxm file
            encoding: File encoding
            
        Returns:
            Template instance
            
        Raises:
            TemplateNotFoundError: If file doesn't exist
        """
        path = Path(path)
        
        if not path.exists():
            raise TemplateNotFoundError(f"Template not found: {path}")
            
        source = path.read_text(encoding=encoding)
        return cls(source, name=str(path))
        
    @classmethod
    def from_string(cls, source: str, name: str = "string") -> "Template":
        """Create template from string source."""
        return cls(source, name=name)
        
    def _compile(self) -> None:
        """Parse and compile the template."""
        # Check cache first
        cache = get_template_cache()
        cache_key = self._get_cache_key()
        
        cached = cache.get(cache_key)
        if cached:
            self._compiled = cached
            return
            
        # Parse
        try:
            parser = PyxmParser()
            self._ast = parser.parse(self.source)
        except SyntaxError as e:
            raise TemplateSyntaxError(f"Syntax error in {self.name}: {e}")
            
        # Compile
        try:
            compiler = PyxmCompiler()
            self._compiled = compiler.compile(self._ast, self.name)
        except Exception as e:
            raise TemplateSyntaxError(f"Compilation error in {self.name}: {e}")
            
        # Cache
        cache.set(cache_key, self._compiled)
        
    def _get_cache_key(self) -> str:
        """Generate cache key for template."""
        source_hash = hashlib.md5(self.source.encode()).hexdigest()
        return f"{self.name}:{source_hash}"
        
    def extends(self, parent: Union[str, Path, "Template"]) -> "Template":
        """
        Set parent template for inheritance.
        
        Args:
            parent: Parent template (path or Template instance)
            
        Returns:
            Self for chaining
        """
        if isinstance(parent, Template):
            self._parent = parent
        else:
            self._parent = Template.from_file(parent)
        return self
        
    def register_component(
        self,
        name: str,
        component: Union[str, Path, "Template"],
    ) -> "Template":
        """
        Register a component for use in template.
        
        Args:
            name: Component name
            component: Component template (path or Template instance)
            
        Returns:
            Self for chaining
        """
        if isinstance(component, Template):
            self._components[name] = component
        else:
            self._components[name] = Template.from_file(component)
        return self
        
    async def render(self, context: Dict[str, Any] = None) -> str:
        """
        Render template with context.
        
        Args:
            context: Template variables
            
        Returns:
            Rendered HTML string
            
        Raises:
            TemplateRenderError: If rendering fails
        """
        if self._compiled is None:
            self._compile()
            
        context = context or {}
        
        # Add components to context
        if self._components:
            context["_components"] = self._components
            
        # Add blocks to context
        if self._blocks:
            context["_blocks"] = self._blocks
            
        try:
            html = await self._compiled.render(context)
            
            # Handle inheritance
            if self._parent:
                # Extract blocks from rendered content
                # and render parent with blocks
                parent_context = context.copy()
                parent_context["_blocks"] = self._extract_blocks(html)
                html = await self._parent.render(parent_context)
                
            return html
            
        except Exception as e:
            raise TemplateRenderError(f"Render error in {self.name}: {e}")
            
    def render_sync(self, context: Dict[str, Any] = None) -> str:
        """
        Synchronous render (convenience method).
        
        For async contexts, use render() instead.
        """
        import asyncio
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        return loop.run_until_complete(self.render(context))
        
    def _extract_blocks(self, html: str) -> Dict[str, str]:
        """Extract block content from rendered HTML."""
        # Implementation for template inheritance
        # Blocks are marked with data-nexa-block attributes
        import re
        
        blocks = {}
        pattern = r'<div data-nexa-block="(\w+)">(.*?)</div>'
        
        for match in re.finditer(pattern, html, re.DOTALL):
            block_name = match.group(1)
            block_content = match.group(2)
            blocks[block_name] = block_content
            
        return blocks
        
    @property
    def ast(self) -> Optional[PyxmAST]:
        """Get parsed AST."""
        return self._ast
        
    @property
    def compiled(self) -> Optional[CompiledTemplate]:
        """Get compiled template."""
        return self._compiled
        
    def __repr__(self) -> str:
        return f"<Template {self.name}>"


class TemplateLoader:
    """
    Template loader with directory-based lookup.
    
    Manages template directories and provides path resolution
    for template loading.
    
    Example:
        loader = TemplateLoader("templates")
        loader.add_path("shared")
        
        template = loader.load("pages/home.pyxm")
    """
    
    def __init__(self, *paths: Union[str, Path]) -> None:
        """
        Initialize loader with template directories.
        
        Args:
            *paths: Template directory paths
        """
        self.paths: List[Path] = []
        for path in paths:
            self.add_path(path)
            
    def add_path(self, path: Union[str, Path]) -> None:
        """Add template directory."""
        path = Path(path)
        if path.exists() and path not in self.paths:
            self.paths.append(path)
            
    def resolve(self, name: str) -> Optional[Path]:
        """
        Resolve template name to file path.
        
        Args:
            name: Template name (relative path)
            
        Returns:
            Absolute path to template file, or None if not found
        """
        for base in self.paths:
            full_path = base / name
            if full_path.exists():
                return full_path
                
            # Try with .pyxm extension
            if not name.endswith(".pyxm"):
                full_path = base / f"{name}.pyxm"
                if full_path.exists():
                    return full_path
                    
        return None
        
    def load(self, name: str) -> Template:
        """
        Load template by name.
        
        Args:
            name: Template name
            
        Returns:
            Template instance
            
        Raises:
            TemplateNotFoundError: If template not found
        """
        path = self.resolve(name)
        if path is None:
            raise TemplateNotFoundError(
                f"Template '{name}' not found in paths: {self.paths}"
            )
        return Template.from_file(path)
        
    def exists(self, name: str) -> bool:
        """Check if template exists."""
        return self.resolve(name) is not None


class TemplateEnvironment:
    """
    Template environment with global configuration.
    
    Manages template loading, global variables, filters, and components.
    
    Example:
        env = TemplateEnvironment("templates")
        env.globals["site_name"] = "My Site"
        env.filters["markdown"] = markdown_to_html
        
        html = await env.render("home.pyxm", {"page": "Home"})
    """
    
    def __init__(
        self,
        *paths: Union[str, Path],
        auto_reload: bool = False,
    ) -> None:
        """
        Initialize template environment.
        
        Args:
            *paths: Template directory paths
            auto_reload: Whether to auto-reload templates on change
        """
        self.loader = TemplateLoader(*paths)
        self.globals: Dict[str, Any] = {}
        self.filters: Dict[str, Any] = {}
        self.components: Dict[str, Template] = {}
        self.auto_reload = auto_reload
        
    def add_global(self, name: str, value: Any) -> None:
        """Add global template variable."""
        self.globals[name] = value
        
    def add_filter(self, name: str, func: Any) -> None:
        """Add custom filter function."""
        self.filters[name] = func
        
    def register_component(
        self,
        name: str,
        template: Union[str, Template],
    ) -> None:
        """Register global component."""
        if isinstance(template, str):
            template = self.loader.load(template)
        self.components[name] = template
        
    def get_template(self, name: str) -> Template:
        """Get template by name."""
        template = self.loader.load(name)
        
        # Register global components
        for comp_name, comp_template in self.components.items():
            template.register_component(comp_name, comp_template)
            
        return template
        
    async def render(
        self,
        name: str,
        context: Dict[str, Any] = None,
    ) -> str:
        """
        Load and render template.
        
        Args:
            name: Template name
            context: Template variables
            
        Returns:
            Rendered HTML string
        """
        template = self.get_template(name)
        
        # Merge globals with context
        full_context = {**self.globals}
        if context:
            full_context.update(context)
            
        # Add filters
        full_context["_filters"] = {**self.filters}
        
        return await template.render(full_context)
        
    def render_sync(
        self,
        name: str,
        context: Dict[str, Any] = None,
    ) -> str:
        """Synchronous render."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            self.render(name, context)
        )


# Convenience functions

_default_environment: Optional[TemplateEnvironment] = None


def configure(
    *paths: Union[str, Path],
    **kwargs: Any,
) -> TemplateEnvironment:
    """
    Configure default template environment.
    
    Args:
        *paths: Template directory paths
        **kwargs: Additional environment options
        
    Returns:
        Configured TemplateEnvironment
    """
    global _default_environment
    _default_environment = TemplateEnvironment(*paths, **kwargs)
    return _default_environment


def get_environment() -> TemplateEnvironment:
    """Get default template environment."""
    global _default_environment
    if _default_environment is None:
        _default_environment = TemplateEnvironment("templates")
    return _default_environment


async def render(
    source: str,
    context: Dict[str, Any] = None,
) -> str:
    """
    Render template string.
    
    Args:
        source: PYXM template source
        context: Template variables
        
    Returns:
        Rendered HTML string
    """
    template = Template(source)
    return await template.render(context)


async def render_file(
    path: Union[str, Path],
    context: Dict[str, Any] = None,
) -> str:
    """
    Load and render template file.
    
    Args:
        path: Path to template file
        context: Template variables
        
    Returns:
        Rendered HTML string
    """
    template = Template.from_file(path)
    return await template.render(context)
