"""
NexaWeb Template Base Classes
=============================

Base classes for project templates.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type


@dataclass
class TemplateFile:
    """
    Template file definition.
    
    Attributes:
        path: Relative file path
        content: File content (string or callable)
        executable: Whether file should be executable
        condition: Optional condition function
    """
    
    path: str
    content: str | Callable[..., str]
    executable: bool = False
    condition: Optional[Callable[..., bool]] = None
    
    def render(self, context: Dict[str, Any]) -> str:
        """Render file content with context."""
        if callable(self.content):
            return self.content(context)
        
        # Simple template substitution
        content = self.content
        for key, value in context.items():
            content = content.replace(f"{{{{ {key} }}}}", str(value))
            content = content.replace(f"{{{{{key}}}}}", str(value))
        
        return content
    
    def should_create(self, context: Dict[str, Any]) -> bool:
        """Check if file should be created."""
        if self.condition is None:
            return True
        return self.condition(context)


@dataclass
class TemplateDirectory:
    """
    Template directory definition.
    
    Attributes:
        path: Relative directory path
        gitkeep: Create .gitkeep file
        condition: Optional condition function
    """
    
    path: str
    gitkeep: bool = True
    condition: Optional[Callable[..., bool]] = None
    
    def should_create(self, context: Dict[str, Any]) -> bool:
        """Check if directory should be created."""
        if self.condition is None:
            return True
        return self.condition(context)


class ProjectTemplate(ABC):
    """
    Base class for project templates.
    
    Example:
        class MyTemplate(ProjectTemplate):
            name = "my-template"
            description = "My custom template"
            
            def get_files(self) -> List[TemplateFile]:
                return [
                    TemplateFile("app.py", APP_PY_CONTENT),
                    TemplateFile("config.py", CONFIG_PY_CONTENT),
                ]
    """
    
    name: str = "base"
    description: str = "Base template"
    version: str = "1.0.0"
    
    # Template options
    options: Dict[str, Dict[str, Any]] = {}
    
    def __init__(self, **options: Any):
        """
        Initialize template.
        
        Args:
            **options: Template options
        """
        self.template_options = options
    
    @abstractmethod
    def get_files(self) -> List[TemplateFile]:
        """
        Get template files.
        
        Returns:
            List of template files
        """
        pass
    
    def get_directories(self) -> List[TemplateDirectory]:
        """
        Get template directories.
        
        Returns:
            List of template directories
        """
        return []
    
    def get_context(self, project_name: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Get template context.
        
        Args:
            project_name: Project name
            **kwargs: Additional context
            
        Returns:
            Template context dict
        """
        return {
            "project_name": project_name,
            "project_slug": project_name.lower().replace(" ", "-"),
            "template_name": self.name,
            "template_version": self.version,
            **self.template_options,
            **kwargs,
        }
    
    def create(
        self,
        target: Path,
        project_name: str,
        **kwargs: Any,
    ) -> List[Path]:
        """
        Create project from template.
        
        Args:
            target: Target directory
            project_name: Project name
            **kwargs: Additional context
            
        Returns:
            List of created files
        """
        context = self.get_context(project_name, **kwargs)
        created_files: List[Path] = []
        
        # Create target directory
        target.mkdir(parents=True, exist_ok=True)
        
        # Create directories
        for directory in self.get_directories():
            if directory.should_create(context):
                dir_path = target / directory.path
                dir_path.mkdir(parents=True, exist_ok=True)
                
                if directory.gitkeep:
                    gitkeep = dir_path / ".gitkeep"
                    gitkeep.touch()
                    created_files.append(gitkeep)
        
        # Create files
        for template_file in self.get_files():
            if template_file.should_create(context):
                file_path = target / template_file.path
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                content = template_file.render(context)
                file_path.write_text(content)
                
                if template_file.executable:
                    file_path.chmod(0o755)
                
                created_files.append(file_path)
        
        # Post-creation hook
        self.post_create(target, context)
        
        return created_files
    
    def post_create(
        self,
        target: Path,
        context: Dict[str, Any],
    ) -> None:
        """
        Post-creation hook.
        
        Override to perform additional setup after files are created.
        
        Args:
            target: Target directory
            context: Template context
        """
        pass


class TemplateRegistry:
    """
    Registry for project templates.
    
    Example:
        registry = TemplateRegistry()
        registry.register(MinimalTemplate)
        registry.register(StandardTemplate)
        
        template = registry.get("standard")
        template.create(Path("myproject"), "My Project")
    """
    
    def __init__(self):
        """Initialize registry."""
        self._templates: Dict[str, Type[ProjectTemplate]] = {}
    
    def register(
        self,
        template_class: Type[ProjectTemplate],
    ) -> None:
        """
        Register a template.
        
        Args:
            template_class: Template class to register
        """
        self._templates[template_class.name] = template_class
    
    def unregister(self, name: str) -> None:
        """
        Unregister a template.
        
        Args:
            name: Template name
        """
        self._templates.pop(name, None)
    
    def get(
        self,
        name: str,
        **options: Any,
    ) -> Optional[ProjectTemplate]:
        """
        Get template instance.
        
        Args:
            name: Template name
            **options: Template options
            
        Returns:
            Template instance or None
        """
        template_class = self._templates.get(name)
        
        if template_class:
            return template_class(**options)
        
        return None
    
    def list(self) -> List[Dict[str, str]]:
        """
        List available templates.
        
        Returns:
            List of template info dicts
        """
        return [
            {
                "name": cls.name,
                "description": cls.description,
                "version": cls.version,
            }
            for cls in self._templates.values()
        ]
    
    def __contains__(self, name: str) -> bool:
        return name in self._templates


# Global registry
_registry = TemplateRegistry()


def get_registry() -> TemplateRegistry:
    """Get global template registry."""
    return _registry
