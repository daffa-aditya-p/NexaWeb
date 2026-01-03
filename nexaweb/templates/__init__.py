"""
NexaWeb Project Templates
=========================

Starter templates for new NexaWeb projects.
"""

from __future__ import annotations

from nexaweb.templates.base import (
    ProjectTemplate,
    TemplateFile,
    TemplateRegistry,
)
from nexaweb.templates.minimal import MinimalTemplate
from nexaweb.templates.standard import StandardTemplate
from nexaweb.templates.api import APITemplate

__all__ = [
    "ProjectTemplate",
    "TemplateFile",
    "TemplateRegistry",
    "MinimalTemplate",
    "StandardTemplate",
    "APITemplate",
]
