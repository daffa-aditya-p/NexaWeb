"""
NexaWeb CLI Build Command
=========================

Build project for production.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set


def build_project(
    output_dir: str = "dist",
    minify: bool = False,
) -> int:
    """
    Build project for production.
    
    Args:
        output_dir: Output directory
        minify: Whether to minify assets
        
    Returns:
        Exit code
    """
    cwd = Path.cwd()
    output = cwd / output_dir
    
    print("Building NexaWeb project for production...")
    
    # Clean output directory
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    
    # Copy Python files
    print("  Copying source files...")
    _copy_source_files(cwd, output)
    
    # Process static files
    print("  Processing static assets...")
    assets_manifest = _process_static_files(cwd, output, minify)
    
    # Process templates
    print("  Processing templates...")
    _process_templates(cwd, output, assets_manifest)
    
    # Create production config
    print("  Creating production config...")
    _create_production_config(output)
    
    # Generate manifest
    print("  Generating build manifest...")
    _generate_manifest(output, assets_manifest)
    
    print()
    print(f"✓ Build complete! Output: {output_dir}/")
    print()
    print("To run in production:")
    print(f"  cd {output_dir}")
    print("  uvicorn app:app --host 0.0.0.0 --port 8000")
    print()
    
    return 0


def _copy_source_files(source: Path, dest: Path) -> None:
    """Copy Python source files."""
    exclude_patterns = {
        "__pycache__",
        ".git",
        ".env",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        ".pytest_cache",
        "*.pyc",
        ".coverage",
        "htmlcov",
    }
    
    for item in source.iterdir():
        if item.name in exclude_patterns:
            continue
        if item.name.startswith("."):
            continue
            
        if item.is_file() and item.suffix in (".py", ".toml", ".txt", ".md"):
            shutil.copy2(item, dest / item.name)
        elif item.is_dir() and item.name not in ("static", "templates", "tests"):
            # Copy Python packages
            if (item / "__init__.py").exists() or item.name in ("app", "src"):
                shutil.copytree(
                    item,
                    dest / item.name,
                    ignore=shutil.ignore_patterns(*exclude_patterns),
                )


def _process_static_files(
    source: Path,
    dest: Path,
    minify: bool,
) -> Dict[str, str]:
    """
    Process static files with optional minification.
    
    Returns manifest mapping original names to hashed names.
    """
    static_dir = source / "static"
    if not static_dir.exists():
        return {}
    
    output_static = dest / "static"
    output_static.mkdir(parents=True)
    
    manifest: Dict[str, str] = {}
    
    for file in static_dir.rglob("*"):
        if file.is_dir():
            continue
            
        # Calculate relative path
        rel_path = file.relative_to(static_dir)
        
        # Read content
        content = file.read_bytes()
        
        # Minify if enabled
        if minify:
            content = _minify_asset(file, content)
        
        # Calculate hash
        content_hash = hashlib.md5(content).hexdigest()[:8]
        
        # Create hashed filename
        stem = file.stem
        suffix = file.suffix
        hashed_name = f"{stem}.{content_hash}{suffix}"
        
        # Determine output path
        output_subdir = output_static / rel_path.parent
        output_subdir.mkdir(parents=True, exist_ok=True)
        output_file = output_subdir / hashed_name
        
        # Write file
        output_file.write_bytes(content)
        
        # Record in manifest
        original_url = f"/static/{rel_path}"
        hashed_url = f"/static/{rel_path.parent / hashed_name}"
        manifest[original_url] = hashed_url
    
    return manifest


def _minify_asset(file: Path, content: bytes) -> bytes:
    """Minify asset content."""
    if file.suffix == ".css":
        return _minify_css(content.decode()).encode()
    elif file.suffix == ".js":
        return _minify_js(content.decode()).encode()
    return content


def _minify_css(content: str) -> str:
    """Basic CSS minification."""
    # Remove comments
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    # Remove whitespace
    content = re.sub(r"\s+", " ", content)
    # Remove spaces around special chars
    content = re.sub(r"\s*([{};:,>+~])\s*", r"\1", content)
    # Remove trailing semicolons
    content = re.sub(r";}", "}", content)
    return content.strip()


def _minify_js(content: str) -> str:
    """Basic JS minification (very simple)."""
    # Remove single-line comments (but not URLs)
    content = re.sub(r"(?<!:)//.*$", "", content, flags=re.MULTILINE)
    # Remove multi-line comments
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    # Collapse whitespace
    content = re.sub(r"\s+", " ", content)
    return content.strip()


def _process_templates(
    source: Path,
    dest: Path,
    manifest: Dict[str, str],
) -> None:
    """Process templates and update asset references."""
    templates_dir = source / "templates"
    if not templates_dir.exists():
        return
    
    output_templates = dest / "templates"
    
    shutil.copytree(templates_dir, output_templates)
    
    # Update asset references in templates
    for template in output_templates.rglob("*"):
        if template.is_dir():
            continue
        if template.suffix not in (".html", ".pyxm", ".jinja", ".j2"):
            continue
            
        content = template.read_text()
        
        # Replace asset references
        for original, hashed in manifest.items():
            content = content.replace(original, hashed)
        
        template.write_text(content)


def _create_production_config(output: Path) -> None:
    """Create production configuration."""
    config_file = output / "config.py"
    
    if not config_file.exists():
        return
    
    content = config_file.read_text()
    
    # Update production defaults
    replacements = [
        ('DEBUG = os.getenv("DEBUG", "true")', 'DEBUG = os.getenv("DEBUG", "false")'),
        ('APP_ENV = os.getenv("APP_ENV", "development")', 'APP_ENV = os.getenv("APP_ENV", "production")'),
    ]
    
    for old, new in replacements:
        content = content.replace(old, new)
    
    config_file.write_text(content)


def _generate_manifest(output: Path, assets: Dict[str, str]) -> None:
    """Generate build manifest."""
    import json
    from datetime import datetime
    
    manifest = {
        "build_time": datetime.utcnow().isoformat(),
        "assets": assets,
    }
    
    manifest_file = output / "build-manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2))
