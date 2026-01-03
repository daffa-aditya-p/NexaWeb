"""
NexaWeb Engine Module
=====================

The PYXM template engine - NexaWeb's revolutionary template format
that combines HTML with Python for reactive, high-performance rendering.

Components:
- PYXM Parser: Parses .pyxm files into AST
- PYXM Compiler: Compiles AST to optimized render functions
- Template: High-level template interface
- Reactive: State management and reactivity system
"""

from nexaweb.engine.pyxm_parser import PyxmParser, PyxmNode, PyxmAST
from nexaweb.engine.pyxm_compiler import PyxmCompiler, CompiledTemplate
from nexaweb.engine.template import Template, render, render_file
from nexaweb.engine.reactive import State, Computed, Effect, reactive

__all__ = [
    "PyxmParser",
    "PyxmNode",
    "PyxmAST",
    "PyxmCompiler",
    "CompiledTemplate",
    "Template",
    "render",
    "render_file",
    "State",
    "Computed",
    "Effect",
    "reactive",
]
