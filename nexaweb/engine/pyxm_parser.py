"""
NexaWeb PYXM Parser
===================

The PYXM (Python XML Markup) parser is the foundation of NexaWeb's template
system. It parses .pyxm files into an Abstract Syntax Tree (AST) that can
be analyzed, optimized, and compiled.

PYXM Format:
    PYXM extends HTML with Python expressions and control structures:
    
    - {{ expression }}: Output expression result
    - {% if condition %}...{% endif %}: Conditionals
    - {% for item in items %}...{% endfor %}: Loops
    - {% component Name %}...{% endcomponent %}: Components
    - @event="handler": Event binding
    - :attr="expression": Dynamic attributes
    - #ref="name": Element references
    - <py>...</py>: Server-side Python blocks

Example .pyxm:
    <py>
        from nexaweb import State
        count = State(0)
        
        def increment():
            count.value += 1
    </py>
    
    <div class="counter">
        <h1>Count: {{ count }}</h1>
        <button @click="increment">+1</button>
        
        {% if count > 10 %}
            <p class="warning">Count is high!</p>
        {% endif %}
        
        <ul>
            {% for i in range(count) %}
                <li>Item {{ i + 1 }}</li>
            {% endfor %}
        </ul>
    </div>

Parser Architecture:
    1. Lexer: Tokenize input into meaningful tokens
    2. Parser: Build AST from tokens
    3. Analyzer: Validate and annotate AST
    4. Optimizer: Apply optimizations to AST
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Pattern, Tuple, Union
from html.parser import HTMLParser
from html import escape as html_escape


class TokenType(Enum):
    """Token types for PYXM lexer."""
    # Basic tokens
    TEXT = auto()
    WHITESPACE = auto()
    NEWLINE = auto()
    
    # HTML tokens
    TAG_OPEN = auto()          # <
    TAG_CLOSE = auto()         # >
    TAG_SELF_CLOSE = auto()    # />
    TAG_END_OPEN = auto()      # </
    TAG_NAME = auto()          # div, span, etc.
    ATTR_NAME = auto()         # class, id, etc.
    ATTR_VALUE = auto()        # "value"
    ATTR_EQUALS = auto()       # =
    
    # Expression tokens
    EXPR_OPEN = auto()         # {{
    EXPR_CLOSE = auto()        # }}
    EXPR_CONTENT = auto()      # Python expression
    
    # Statement tokens
    STMT_OPEN = auto()         # {%
    STMT_CLOSE = auto()        # %}
    STMT_CONTENT = auto()      # if, for, etc.
    
    # Comment tokens
    COMMENT_OPEN = auto()      # {#
    COMMENT_CLOSE = auto()     # #}
    COMMENT_CONTENT = auto()
    
    # Special tokens
    PY_BLOCK_OPEN = auto()     # <py>
    PY_BLOCK_CLOSE = auto()    # </py>
    PY_CONTENT = auto()        # Python code
    
    # Binding tokens
    EVENT_BIND = auto()        # @click, @submit
    ATTR_BIND = auto()         # :class, :style
    REF_BIND = auto()          # #ref
    
    EOF = auto()


@dataclass
class Token:
    """Represents a lexer token."""
    type: TokenType
    value: str
    line: int
    column: int
    
    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, {self.line}:{self.column})"


class NodeType(Enum):
    """AST node types."""
    ROOT = auto()
    ELEMENT = auto()
    TEXT = auto()
    EXPRESSION = auto()
    IF = auto()
    ELIF = auto()
    ELSE = auto()
    FOR = auto()
    COMPONENT = auto()
    SLOT = auto()
    BLOCK = auto()
    PYTHON = auto()
    COMMENT = auto()
    FRAGMENT = auto()
    RAW = auto()


@dataclass
class PyxmNode:
    """
    AST Node for PYXM templates.
    
    Represents any element in the PYXM template tree:
    - HTML elements
    - Text content
    - Expressions
    - Control structures
    - Components
    """
    type: NodeType
    tag: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    bindings: Dict[str, str] = field(default_factory=dict)  # :attr bindings
    events: Dict[str, str] = field(default_factory=dict)    # @event bindings
    refs: List[str] = field(default_factory=list)           # #ref bindings
    children: List["PyxmNode"] = field(default_factory=list)
    content: Optional[str] = None
    condition: Optional[str] = None  # For if/elif
    iterator: Optional[str] = None   # For for loops (item in items)
    line: int = 0
    column: int = 0
    is_self_closing: bool = False
    is_static: bool = False  # Can be pre-rendered
    
    def add_child(self, child: "PyxmNode") -> None:
        """Add a child node."""
        self.children.append(child)
        
    def find_by_tag(self, tag: str) -> List["PyxmNode"]:
        """Find all descendant nodes with given tag."""
        results = []
        if self.tag == tag:
            results.append(self)
        for child in self.children:
            results.extend(child.find_by_tag(tag))
        return results
        
    def find_by_type(self, node_type: NodeType) -> List["PyxmNode"]:
        """Find all descendant nodes with given type."""
        results = []
        if self.type == node_type:
            results.append(self)
        for child in self.children:
            results.extend(child.find_by_type(node_type))
        return results
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert node to dictionary representation."""
        return {
            "type": self.type.name,
            "tag": self.tag,
            "attributes": self.attributes,
            "bindings": self.bindings,
            "events": self.events,
            "content": self.content,
            "condition": self.condition,
            "iterator": self.iterator,
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class PyxmAST:
    """
    Complete AST for a PYXM template.
    
    Contains:
    - Root node tree
    - Python code blocks
    - Metadata (imports, dependencies)
    - Component definitions
    """
    root: PyxmNode
    python_blocks: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    components: Dict[str, PyxmNode] = field(default_factory=dict)
    slots: Dict[str, PyxmNode] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_expressions(self) -> List[PyxmNode]:
        """Get all expression nodes."""
        return self.root.find_by_type(NodeType.EXPRESSION)
        
    def get_components(self) -> List[PyxmNode]:
        """Get all component nodes."""
        return self.root.find_by_type(NodeType.COMPONENT)
        
    def has_dynamic_content(self) -> bool:
        """Check if template has any dynamic content."""
        return bool(
            self.get_expressions() or
            self.root.find_by_type(NodeType.IF) or
            self.root.find_by_type(NodeType.FOR) or
            any(node.bindings for node in self._all_nodes())
        )
        
    def _all_nodes(self) -> List[PyxmNode]:
        """Get all nodes in tree."""
        nodes = []
        def collect(node: PyxmNode):
            nodes.append(node)
            for child in node.children:
                collect(child)
        collect(self.root)
        return nodes


class PyxmLexer:
    """
    Tokenizer for PYXM templates.
    
    Converts raw PYXM source into a stream of tokens for parsing.
    """
    
    # Regular expressions for token matching
    PATTERNS = {
        "expr_open": re.compile(r"\{\{"),
        "expr_close": re.compile(r"\}\}"),
        "stmt_open": re.compile(r"\{%"),
        "stmt_close": re.compile(r"%\}"),
        "comment_open": re.compile(r"\{#"),
        "comment_close": re.compile(r"#\}"),
        "py_open": re.compile(r"<py\s*>", re.IGNORECASE),
        "py_close": re.compile(r"</py\s*>", re.IGNORECASE),
        "tag_end_open": re.compile(r"</"),
        "tag_self_close": re.compile(r"/>"),
        "tag_open": re.compile(r"<"),
        "tag_close": re.compile(r">"),
        "whitespace": re.compile(r"\s+"),
        "tag_name": re.compile(r"[a-zA-Z_][a-zA-Z0-9_-]*"),
        "attr_equals": re.compile(r"="),
        "attr_value_double": re.compile(r'"[^"]*"'),
        "attr_value_single": re.compile(r"'[^']*'"),
        "event_bind": re.compile(r"@([a-zA-Z][a-zA-Z0-9_]*)"),
        "attr_bind": re.compile(r":([a-zA-Z][a-zA-Z0-9_-]*)"),
        "ref_bind": re.compile(r"#([a-zA-Z][a-zA-Z0-9_]*)"),
    }
    
    def __init__(self, source: str) -> None:
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []
        
    def tokenize(self) -> List[Token]:
        """Tokenize the entire source."""
        while self.pos < len(self.source):
            self._next_token()
        self.tokens.append(Token(TokenType.EOF, "", self.line, self.column))
        return self.tokens
        
    def _next_token(self) -> None:
        """Extract next token from source."""
        # Check for special sequences first
        if self._match_pattern("expr_open"):
            self._tokenize_expression()
        elif self._match_pattern("stmt_open"):
            self._tokenize_statement()
        elif self._match_pattern("comment_open"):
            self._tokenize_comment()
        elif self._match_pattern("py_open"):
            self._tokenize_python_block()
        elif self._match_pattern("tag_end_open"):
            self._add_token(TokenType.TAG_END_OPEN, "</")
            self._tokenize_tag()
        elif self._match_pattern("tag_open"):
            self._add_token(TokenType.TAG_OPEN, "<")
            self._tokenize_tag()
        else:
            self._tokenize_text()
            
    def _match_pattern(self, name: str) -> bool:
        """Check if pattern matches at current position."""
        pattern = self.PATTERNS[name]
        match = pattern.match(self.source, self.pos)
        return match is not None
        
    def _consume_pattern(self, name: str) -> Optional[str]:
        """Consume pattern if it matches, return matched text."""
        pattern = self.PATTERNS[name]
        match = pattern.match(self.source, self.pos)
        if match:
            text = match.group()
            self._advance(len(text))
            return text
        return None
        
    def _advance(self, count: int = 1) -> None:
        """Advance position in source."""
        for _ in range(count):
            if self.pos < len(self.source):
                if self.source[self.pos] == "\n":
                    self.line += 1
                    self.column = 1
                else:
                    self.column += 1
                self.pos += 1
                
    def _add_token(self, type: TokenType, value: str) -> None:
        """Add token to list."""
        self.tokens.append(Token(type, value, self.line, self.column))
        
    def _tokenize_expression(self) -> None:
        """Tokenize {{ expression }}."""
        self._add_token(TokenType.EXPR_OPEN, "{{")
        self._advance(2)
        
        # Find closing }}
        content_start = self.pos
        depth = 1
        while self.pos < len(self.source) and depth > 0:
            if self.source[self.pos:self.pos+2] == "{{":
                depth += 1
                self._advance(2)
            elif self.source[self.pos:self.pos+2] == "}}":
                depth -= 1
                if depth > 0:
                    self._advance(2)
            else:
                self._advance()
                
        content = self.source[content_start:self.pos].strip()
        self._add_token(TokenType.EXPR_CONTENT, content)
        
        self._add_token(TokenType.EXPR_CLOSE, "}}")
        self._advance(2)
        
    def _tokenize_statement(self) -> None:
        """Tokenize {% statement %}."""
        self._add_token(TokenType.STMT_OPEN, "{%")
        self._advance(2)
        
        # Find closing %}
        content_start = self.pos
        while self.pos < len(self.source):
            if self.source[self.pos:self.pos+2] == "%}":
                break
            self._advance()
            
        content = self.source[content_start:self.pos].strip()
        self._add_token(TokenType.STMT_CONTENT, content)
        
        self._add_token(TokenType.STMT_CLOSE, "%}")
        self._advance(2)
        
    def _tokenize_comment(self) -> None:
        """Tokenize {# comment #}."""
        self._add_token(TokenType.COMMENT_OPEN, "{#")
        self._advance(2)
        
        content_start = self.pos
        while self.pos < len(self.source):
            if self.source[self.pos:self.pos+2] == "#}":
                break
            self._advance()
            
        content = self.source[content_start:self.pos]
        self._add_token(TokenType.COMMENT_CONTENT, content)
        
        self._add_token(TokenType.COMMENT_CLOSE, "#}")
        self._advance(2)
        
    def _tokenize_python_block(self) -> None:
        """Tokenize <py>...</py> block."""
        match = self.PATTERNS["py_open"].match(self.source, self.pos)
        if match:
            self._add_token(TokenType.PY_BLOCK_OPEN, match.group())
            self._advance(len(match.group()))
            
        # Find closing </py>
        content_start = self.pos
        while self.pos < len(self.source):
            if self.PATTERNS["py_close"].match(self.source, self.pos):
                break
            self._advance()
            
        content = self.source[content_start:self.pos]
        self._add_token(TokenType.PY_CONTENT, content)
        
        match = self.PATTERNS["py_close"].match(self.source, self.pos)
        if match:
            self._add_token(TokenType.PY_BLOCK_CLOSE, match.group())
            self._advance(len(match.group()))
            
    def _tokenize_tag(self) -> None:
        """Tokenize HTML tag."""
        # Skip whitespace
        self._consume_pattern("whitespace")
        
        # Tag name
        name = self._consume_pattern("tag_name")
        if name:
            self._add_token(TokenType.TAG_NAME, name)
            
        # Attributes
        while self.pos < len(self.source):
            self._consume_pattern("whitespace")
            
            # Check for tag close
            if self._match_pattern("tag_self_close"):
                self._add_token(TokenType.TAG_SELF_CLOSE, "/>")
                self._advance(2)
                return
            if self._match_pattern("tag_close"):
                self._add_token(TokenType.TAG_CLOSE, ">")
                self._advance()
                return
                
            # Event binding @event
            event_match = self.PATTERNS["event_bind"].match(self.source, self.pos)
            if event_match:
                self._add_token(TokenType.EVENT_BIND, event_match.group(1))
                self._advance(len(event_match.group()))
                self._tokenize_attr_value()
                continue
                
            # Attribute binding :attr
            bind_match = self.PATTERNS["attr_bind"].match(self.source, self.pos)
            if bind_match:
                self._add_token(TokenType.ATTR_BIND, bind_match.group(1))
                self._advance(len(bind_match.group()))
                self._tokenize_attr_value()
                continue
                
            # Ref binding #ref
            ref_match = self.PATTERNS["ref_bind"].match(self.source, self.pos)
            if ref_match:
                self._add_token(TokenType.REF_BIND, ref_match.group(1))
                self._advance(len(ref_match.group()))
                continue
                
            # Regular attribute
            attr_name = self._consume_pattern("tag_name")
            if attr_name:
                self._add_token(TokenType.ATTR_NAME, attr_name)
                self._consume_pattern("whitespace")
                
                if self._match_pattern("attr_equals"):
                    self._add_token(TokenType.ATTR_EQUALS, "=")
                    self._advance()
                    self._tokenize_attr_value()
            else:
                break
                
    def _tokenize_attr_value(self) -> None:
        """Tokenize attribute value."""
        self._consume_pattern("whitespace")
        
        # Double quoted
        value = self._consume_pattern("attr_value_double")
        if value:
            self._add_token(TokenType.ATTR_VALUE, value[1:-1])
            return
            
        # Single quoted
        value = self._consume_pattern("attr_value_single")
        if value:
            self._add_token(TokenType.ATTR_VALUE, value[1:-1])
            return
            
    def _tokenize_text(self) -> None:
        """Tokenize plain text content."""
        start = self.pos
        while self.pos < len(self.source):
            c = self.source[self.pos]
            # Stop at special sequences
            if c == "<" or self.source[self.pos:self.pos+2] in ("{{", "{%", "{#"):
                break
            self._advance()
            
        if self.pos > start:
            text = self.source[start:self.pos]
            self._add_token(TokenType.TEXT, text)


class PyxmParser:
    """
    Parser for PYXM templates.
    
    Converts token stream into AST for further processing.
    
    Example:
        parser = PyxmParser()
        ast = parser.parse(source)
        print(ast.root)
    """
    
    # Self-closing HTML tags
    VOID_ELEMENTS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr"
    }
    
    def __init__(self) -> None:
        self.tokens: List[Token] = []
        self.pos = 0
        self.ast: Optional[PyxmAST] = None
        
    def parse(self, source: str) -> PyxmAST:
        """
        Parse PYXM source into AST.
        
        Args:
            source: PYXM template source code
            
        Returns:
            PyxmAST with parsed template
        """
        # Tokenize
        lexer = PyxmLexer(source)
        self.tokens = lexer.tokenize()
        self.pos = 0
        
        # Build AST
        root = PyxmNode(type=NodeType.ROOT)
        python_blocks: List[str] = []
        
        while not self._is_at_end():
            node = self._parse_node()
            if node:
                if node.type == NodeType.PYTHON:
                    python_blocks.append(node.content or "")
                else:
                    root.add_child(node)
                    
        self.ast = PyxmAST(root=root, python_blocks=python_blocks)
        self._analyze_ast()
        
        return self.ast
        
    def _current(self) -> Token:
        """Get current token."""
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return Token(TokenType.EOF, "", 0, 0)
        
    def _peek(self, offset: int = 1) -> Token:
        """Peek at token at offset."""
        pos = self.pos + offset
        if pos < len(self.tokens):
            return self.tokens[pos]
        return Token(TokenType.EOF, "", 0, 0)
        
    def _advance(self) -> Token:
        """Advance to next token and return current."""
        token = self._current()
        self.pos += 1
        return token
        
    def _is_at_end(self) -> bool:
        """Check if at end of tokens."""
        return self._current().type == TokenType.EOF
        
    def _expect(self, type: TokenType) -> Token:
        """Expect specific token type."""
        if self._current().type != type:
            raise SyntaxError(
                f"Expected {type.name}, got {self._current().type.name} "
                f"at line {self._current().line}:{self._current().column}"
            )
        return self._advance()
        
    def _parse_node(self) -> Optional[PyxmNode]:
        """Parse a single node."""
        token = self._current()
        
        if token.type == TokenType.TEXT:
            return self._parse_text()
        elif token.type == TokenType.EXPR_OPEN:
            return self._parse_expression()
        elif token.type == TokenType.STMT_OPEN:
            return self._parse_statement()
        elif token.type == TokenType.COMMENT_OPEN:
            return self._parse_comment()
        elif token.type == TokenType.PY_BLOCK_OPEN:
            return self._parse_python_block()
        elif token.type == TokenType.TAG_OPEN:
            return self._parse_element()
        elif token.type == TokenType.TAG_END_OPEN:
            # End tag - handled by element parser
            return None
        else:
            self._advance()
            return None
            
    def _parse_text(self) -> PyxmNode:
        """Parse text content."""
        token = self._advance()
        return PyxmNode(
            type=NodeType.TEXT,
            content=token.value,
            line=token.line,
            column=token.column,
            is_static=True,
        )
        
    def _parse_expression(self) -> PyxmNode:
        """Parse {{ expression }}."""
        self._expect(TokenType.EXPR_OPEN)
        content_token = self._expect(TokenType.EXPR_CONTENT)
        self._expect(TokenType.EXPR_CLOSE)
        
        return PyxmNode(
            type=NodeType.EXPRESSION,
            content=content_token.value,
            line=content_token.line,
            column=content_token.column,
        )
        
    def _parse_statement(self) -> Optional[PyxmNode]:
        """Parse {% statement %}."""
        self._expect(TokenType.STMT_OPEN)
        content_token = self._expect(TokenType.STMT_CONTENT)
        self._expect(TokenType.STMT_CLOSE)
        
        content = content_token.value.strip()
        
        # Parse different statement types
        if content.startswith("if "):
            return self._parse_if_block(content[3:].strip())
        elif content.startswith("for "):
            return self._parse_for_block(content[4:].strip())
        elif content.startswith("component "):
            return self._parse_component_block(content[10:].strip())
        elif content.startswith("block "):
            return self._parse_block_block(content[6:].strip())
        elif content.startswith("slot"):
            return self._parse_slot_block(content)
        elif content.startswith("raw"):
            return self._parse_raw_block()
        elif content in ("endif", "endfor", "endcomponent", "endblock", "endraw", "else", "elif"):
            # These are handled by their parent parsers
            self.pos -= 3  # Rewind to re-read the statement
            return None
        else:
            # Unknown statement
            return PyxmNode(
                type=NodeType.COMMENT,
                content=f"Unknown statement: {content}",
                line=content_token.line,
            )
            
    def _parse_if_block(self, condition: str) -> PyxmNode:
        """Parse {% if %}...{% endif %} block."""
        node = PyxmNode(
            type=NodeType.IF,
            condition=condition,
        )
        
        # Parse children until endif, else, or elif
        while not self._is_at_end():
            if self._is_end_tag("endif"):
                self._consume_end_tag("endif")
                break
            elif self._is_end_tag("else"):
                self._consume_end_tag("else")
                else_node = PyxmNode(type=NodeType.ELSE)
                self._parse_children_until(else_node, ["endif"])
                node.add_child(else_node)
                self._consume_end_tag("endif")
                break
            elif self._is_elif():
                # Parse elif as nested if
                elif_condition = self._consume_elif()
                elif_node = self._parse_if_block(elif_condition)
                elif_node.type = NodeType.ELIF
                node.add_child(elif_node)
                break
            else:
                child = self._parse_node()
                if child:
                    node.add_child(child)
                    
        return node
        
    def _parse_for_block(self, iterator: str) -> PyxmNode:
        """Parse {% for %}...{% endfor %} block."""
        node = PyxmNode(
            type=NodeType.FOR,
            iterator=iterator,
        )
        
        self._parse_children_until(node, ["endfor"])
        self._consume_end_tag("endfor")
        
        return node
        
    def _parse_component_block(self, name: str) -> PyxmNode:
        """Parse {% component %}...{% endcomponent %} block."""
        node = PyxmNode(
            type=NodeType.COMPONENT,
            tag=name,
        )
        
        self._parse_children_until(node, ["endcomponent"])
        self._consume_end_tag("endcomponent")
        
        return node
        
    def _parse_block_block(self, name: str) -> PyxmNode:
        """Parse {% block %}...{% endblock %} block."""
        node = PyxmNode(
            type=NodeType.BLOCK,
            tag=name,
        )
        
        self._parse_children_until(node, ["endblock"])
        self._consume_end_tag("endblock")
        
        return node
        
    def _parse_slot_block(self, content: str) -> PyxmNode:
        """Parse {% slot %}."""
        parts = content.split()
        name = parts[1] if len(parts) > 1 else "default"
        
        return PyxmNode(
            type=NodeType.SLOT,
            tag=name,
        )
        
    def _parse_raw_block(self) -> PyxmNode:
        """Parse {% raw %}...{% endraw %} - outputs content as-is."""
        node = PyxmNode(type=NodeType.RAW)
        
        # Collect raw content
        content_parts = []
        while not self._is_at_end():
            if self._is_end_tag("endraw"):
                self._consume_end_tag("endraw")
                break
            token = self._advance()
            content_parts.append(token.value)
            
        node.content = "".join(content_parts)
        return node
        
    def _parse_children_until(self, node: PyxmNode, end_tags: List[str]) -> None:
        """Parse children until one of the end tags is reached."""
        while not self._is_at_end():
            if any(self._is_end_tag(tag) for tag in end_tags):
                break
            child = self._parse_node()
            if child:
                node.add_child(child)
                
    def _is_end_tag(self, name: str) -> bool:
        """Check if current position is an end tag."""
        if self._current().type != TokenType.STMT_OPEN:
            return False
        if self._peek().type != TokenType.STMT_CONTENT:
            return False
        return self._peek().value.strip() == name
        
    def _is_elif(self) -> bool:
        """Check if current position is elif."""
        if self._current().type != TokenType.STMT_OPEN:
            return False
        if self._peek().type != TokenType.STMT_CONTENT:
            return False
        return self._peek().value.strip().startswith("elif ")
        
    def _consume_elif(self) -> str:
        """Consume elif and return condition."""
        self._expect(TokenType.STMT_OPEN)
        content = self._expect(TokenType.STMT_CONTENT).value.strip()
        self._expect(TokenType.STMT_CLOSE)
        return content[5:].strip()  # Remove "elif "
        
    def _consume_end_tag(self, name: str) -> None:
        """Consume end tag."""
        self._expect(TokenType.STMT_OPEN)
        content = self._expect(TokenType.STMT_CONTENT)
        if content.value.strip() != name:
            raise SyntaxError(f"Expected {name}, got {content.value}")
        self._expect(TokenType.STMT_CLOSE)
        
    def _parse_comment(self) -> PyxmNode:
        """Parse {# comment #}."""
        self._expect(TokenType.COMMENT_OPEN)
        content_token = self._expect(TokenType.COMMENT_CONTENT)
        self._expect(TokenType.COMMENT_CLOSE)
        
        return PyxmNode(
            type=NodeType.COMMENT,
            content=content_token.value,
            line=content_token.line,
        )
        
    def _parse_python_block(self) -> PyxmNode:
        """Parse <py>...</py> block."""
        self._expect(TokenType.PY_BLOCK_OPEN)
        content_token = self._expect(TokenType.PY_CONTENT)
        self._expect(TokenType.PY_BLOCK_CLOSE)
        
        return PyxmNode(
            type=NodeType.PYTHON,
            content=content_token.value,
            line=content_token.line,
        )
        
    def _parse_element(self) -> PyxmNode:
        """Parse HTML element."""
        self._expect(TokenType.TAG_OPEN)
        
        # Get tag name
        tag_token = self._expect(TokenType.TAG_NAME)
        tag_name = tag_token.value.lower()
        
        node = PyxmNode(
            type=NodeType.ELEMENT,
            tag=tag_name,
            line=tag_token.line,
            column=tag_token.column,
        )
        
        # Parse attributes
        while self._current().type not in (TokenType.TAG_CLOSE, TokenType.TAG_SELF_CLOSE, TokenType.EOF):
            if self._current().type == TokenType.ATTR_NAME:
                self._parse_attribute(node)
            elif self._current().type == TokenType.EVENT_BIND:
                self._parse_event_binding(node)
            elif self._current().type == TokenType.ATTR_BIND:
                self._parse_attr_binding(node)
            elif self._current().type == TokenType.REF_BIND:
                self._parse_ref_binding(node)
            else:
                break
                
        # Check for self-closing
        if self._current().type == TokenType.TAG_SELF_CLOSE:
            self._advance()
            node.is_self_closing = True
            return node
            
        self._expect(TokenType.TAG_CLOSE)
        
        # Void elements are self-closing
        if tag_name in self.VOID_ELEMENTS:
            node.is_self_closing = True
            return node
            
        # Parse children until closing tag
        while not self._is_at_end():
            if self._current().type == TokenType.TAG_END_OPEN:
                # Verify matching tag
                self._advance()
                close_tag = self._expect(TokenType.TAG_NAME)
                self._expect(TokenType.TAG_CLOSE)
                
                if close_tag.value.lower() != tag_name:
                    raise SyntaxError(
                        f"Mismatched tags: expected </{tag_name}>, "
                        f"got </{close_tag.value}>"
                    )
                break
            else:
                child = self._parse_node()
                if child:
                    node.add_child(child)
                    
        # Check if static
        node.is_static = self._is_static_node(node)
        
        return node
        
    def _parse_attribute(self, node: PyxmNode) -> None:
        """Parse regular attribute."""
        name = self._advance().value
        
        if self._current().type == TokenType.ATTR_EQUALS:
            self._advance()
            if self._current().type == TokenType.ATTR_VALUE:
                value = self._advance().value
                node.attributes[name] = value
            else:
                node.attributes[name] = True
        else:
            node.attributes[name] = True
            
    def _parse_event_binding(self, node: PyxmNode) -> None:
        """Parse @event binding."""
        event_name = self._advance().value
        
        if self._current().type == TokenType.ATTR_EQUALS:
            self._advance()
            if self._current().type == TokenType.ATTR_VALUE:
                handler = self._advance().value
                node.events[event_name] = handler
                
    def _parse_attr_binding(self, node: PyxmNode) -> None:
        """Parse :attr binding."""
        attr_name = self._advance().value
        
        if self._current().type == TokenType.ATTR_EQUALS:
            self._advance()
            if self._current().type == TokenType.ATTR_VALUE:
                expression = self._advance().value
                node.bindings[attr_name] = expression
                
    def _parse_ref_binding(self, node: PyxmNode) -> None:
        """Parse #ref binding."""
        ref_name = self._advance().value
        node.refs.append(ref_name)
        
    def _is_static_node(self, node: PyxmNode) -> bool:
        """Check if node can be pre-rendered."""
        if node.bindings or node.events:
            return False
        for child in node.children:
            if child.type in (NodeType.EXPRESSION, NodeType.IF, NodeType.FOR):
                return False
            if child.type == NodeType.ELEMENT and not child.is_static:
                return False
        return True
        
    def _analyze_ast(self) -> None:
        """Analyze and annotate the AST."""
        if not self.ast:
            return
            
        # Extract imports from Python blocks
        for block in self.ast.python_blocks:
            for line in block.split("\n"):
                line = line.strip()
                if line.startswith("import ") or line.startswith("from "):
                    self.ast.imports.append(line)
                    
        # Extract component definitions
        for node in self.ast.root.find_by_type(NodeType.COMPONENT):
            if node.tag:
                self.ast.components[node.tag] = node
                
        # Extract slot definitions
        for node in self.ast.root.find_by_type(NodeType.SLOT):
            if node.tag:
                self.ast.slots[node.tag] = node
