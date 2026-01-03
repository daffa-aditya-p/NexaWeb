"""
NexaWeb CLI Shell Command
=========================

Interactive Python shell with app context.
"""

from __future__ import annotations

import code
import sys
from pathlib import Path
from typing import Any, Dict


def start_shell() -> int:
    """
    Start interactive shell.
    
    Returns:
        Exit code
    """
    print("NexaWeb Interactive Shell")
    print("=" * 40)
    
    # Prepare context
    context = _prepare_context()
    
    # Print available objects
    print("\nAvailable objects:")
    for name, obj in sorted(context.items()):
        obj_type = type(obj).__name__
        print(f"  {name}: {obj_type}")
    
    print()
    
    # Try IPython first
    try:
        from IPython import embed
        embed(user_ns=context, colors="neutral")
        return 0
    except ImportError:
        pass
    
    # Fall back to standard REPL
    try:
        import readline
        import rlcompleter
        readline.set_completer(rlcompleter.Completer(context).complete)
        readline.parse_and_bind("tab: complete")
    except ImportError:
        pass
    
    # Start interactive console
    console = code.InteractiveConsole(context)
    console.interact(banner="", exitmsg="Goodbye!")
    
    return 0


def _prepare_context() -> Dict[str, Any]:
    """Prepare shell context with useful objects."""
    context: Dict[str, Any] = {}
    
    # Add cwd to path
    sys.path.insert(0, str(Path.cwd()))
    
    # Import core framework
    try:
        import nexaweb
        context["nexaweb"] = nexaweb
        
        from nexaweb.core import Application, Request, Response, Router
        context["Application"] = Application
        context["Request"] = Request
        context["Response"] = Response
        context["Router"] = Router
    except ImportError as e:
        print(f"Warning: Could not import nexaweb: {e}")
    
    # Import ORM
    try:
        from nexaweb.orm import Model, Database, QueryBuilder
        context["Model"] = Model
        context["Database"] = Database
        context["QueryBuilder"] = QueryBuilder
    except ImportError:
        pass
    
    # Import auth
    try:
        from nexaweb.auth import Authenticator, Session
        context["Authenticator"] = Authenticator
        context["Session"] = Session
    except ImportError:
        pass
    
    # Import validation
    try:
        from nexaweb.validation import Validator, ValidationResult
        context["Validator"] = Validator
        context["ValidationResult"] = ValidationResult
    except ImportError:
        pass
    
    # Load app
    app = _load_app()
    if app:
        context["app"] = app
    
    # Load models from project
    models = _load_models()
    context.update(models)
    
    # Async helpers
    import asyncio
    context["asyncio"] = asyncio
    
    def run_async(coro):
        """Helper to run async code in shell."""
        return asyncio.get_event_loop().run_until_complete(coro)
    
    context["run_async"] = run_async
    context["await_"] = run_async  # Alias
    
    return context


def _load_app():
    """Load application instance."""
    import importlib.util
    
    app_files = [
        Path.cwd() / "app.py",
        Path.cwd() / "main.py",
    ]
    
    for app_file in app_files:
        if not app_file.exists():
            continue
            
        try:
            spec = importlib.util.spec_from_file_location("app", app_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            for attr_name in ["app", "application", "api"]:
                if hasattr(module, attr_name):
                    return getattr(module, attr_name)
            
            if hasattr(module, "create_app"):
                return module.create_app()
                
        except Exception:
            continue
    
    return None


def _load_models() -> Dict[str, Any]:
    """Load models from project."""
    models = {}
    
    models_dir = Path.cwd() / "app" / "models"
    
    if not models_dir.exists():
        return models
    
    import importlib.util
    
    for model_file in models_dir.glob("*.py"):
        if model_file.name.startswith("_"):
            continue
            
        try:
            module_name = f"app.models.{model_file.stem}"
            spec = importlib.util.spec_from_file_location(module_name, model_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Look for Model subclasses
            for name in dir(module):
                obj = getattr(module, name)
                if isinstance(obj, type) and name != "Model":
                    # Check if it's a model
                    if hasattr(obj, "__tablename__"):
                        models[name] = obj
                        
        except Exception:
            continue
    
    return models
