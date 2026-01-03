"""
NexaWeb ORM Query Builder
=========================

Fluent query builder for constructing SQL queries.

Features:
- Chainable query methods
- WHERE, JOIN, ORDER BY, GROUP BY
- Aggregations
- Subqueries
- Raw expressions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)

T = TypeVar("T")


class Operator(Enum):
    """SQL comparison operators."""
    
    EQ = "="
    NE = "!="
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="
    LIKE = "LIKE"
    NOT_LIKE = "NOT LIKE"
    IN = "IN"
    NOT_IN = "NOT IN"
    IS = "IS"
    IS_NOT = "IS NOT"
    BETWEEN = "BETWEEN"
    NOT_BETWEEN = "NOT BETWEEN"


class JoinType(Enum):
    """SQL join types."""
    
    INNER = "INNER JOIN"
    LEFT = "LEFT JOIN"
    RIGHT = "RIGHT JOIN"
    OUTER = "FULL OUTER JOIN"
    CROSS = "CROSS JOIN"


class OrderDirection(Enum):
    """Sort direction."""
    
    ASC = "ASC"
    DESC = "DESC"


@dataclass
class Expression:
    """
    Raw SQL expression.
    
    Used for complex expressions that can't be built
    with the query builder.
    
    Example:
        query.select(Expression("COUNT(*) as count"))
        query.where(Expression("LOWER(name)"), "john")
    """
    
    sql: str
    bindings: List[Any] = field(default_factory=list)
    
    def __str__(self) -> str:
        return self.sql


class F:
    """
    Field reference for expressions.
    
    Use to reference other fields in expressions.
    
    Example:
        query.where("views", ">", F("likes") * 2)
        query.update(views=F("views") + 1)
    """
    
    def __init__(self, name: str) -> None:
        self.name = name
        self._operations: List[Tuple[str, Any]] = []
        
    def __add__(self, other: Any) -> F:
        new = F(self.name)
        new._operations = self._operations + [("+", other)]
        return new
        
    def __sub__(self, other: Any) -> F:
        new = F(self.name)
        new._operations = self._operations + [("-", other)]
        return new
        
    def __mul__(self, other: Any) -> F:
        new = F(self.name)
        new._operations = self._operations + [("*", other)]
        return new
        
    def __truediv__(self, other: Any) -> F:
        new = F(self.name)
        new._operations = self._operations + [("/", other)]
        return new
        
    def to_sql(self) -> Tuple[str, List[Any]]:
        """Convert to SQL expression."""
        sql = self.name
        bindings = []
        
        for op, value in self._operations:
            if isinstance(value, F):
                val_sql, val_bindings = value.to_sql()
                sql = f"({sql} {op} {val_sql})"
                bindings.extend(val_bindings)
            else:
                sql = f"({sql} {op} ?)"
                bindings.append(value)
                
        return sql, bindings


@dataclass
class Q:
    """
    Complex query condition builder.
    
    Allows building complex WHERE clauses with AND/OR logic.
    
    Example:
        # (status = 'active' AND role = 'admin') OR is_superuser = true
        query.where(
            Q(status="active", role="admin") | Q(is_superuser=True)
        )
    """
    
    conditions: Dict[str, Any] = field(default_factory=dict)
    _children: List[Tuple[str, Q]] = field(default_factory=list)
    
    def __init__(self, **kwargs) -> None:
        self.conditions = kwargs
        self._children = []
        
    def __and__(self, other: Q) -> Q:
        new = Q()
        new._children = [("AND", self), ("AND", other)]
        return new
        
    def __or__(self, other: Q) -> Q:
        new = Q()
        new._children = [("OR", self), ("OR", other)]
        return new
        
    def __invert__(self) -> Q:
        # NOT
        new = Q()
        new._children = [("NOT", self)]
        return new
        
    def to_sql(self) -> Tuple[str, List[Any]]:
        """Convert to SQL WHERE clause."""
        if self._children:
            parts = []
            bindings = []
            
            for i, (connector, child) in enumerate(self._children):
                child_sql, child_bindings = child.to_sql()
                
                if connector == "NOT":
                    parts.append(f"NOT ({child_sql})")
                elif i == 0:
                    parts.append(f"({child_sql})")
                else:
                    parts.append(f"{connector} ({child_sql})")
                    
                bindings.extend(child_bindings)
                
            return " ".join(parts), bindings
        else:
            parts = []
            bindings = []
            
            for key, value in self.conditions.items():
                if value is None:
                    parts.append(f"{key} IS NULL")
                elif isinstance(value, (list, tuple)):
                    placeholders = ", ".join("?" for _ in value)
                    parts.append(f"{key} IN ({placeholders})")
                    bindings.extend(value)
                else:
                    parts.append(f"{key} = ?")
                    bindings.append(value)
                    
            return " AND ".join(parts), bindings


@dataclass
class WhereClause:
    """WHERE clause component."""
    
    column: str
    operator: Operator
    value: Any
    connector: str = "AND"
    is_raw: bool = False


@dataclass
class JoinClause:
    """JOIN clause component."""
    
    table: str
    type: JoinType
    on_left: str
    on_right: str


@dataclass
class OrderClause:
    """ORDER BY clause component."""
    
    column: str
    direction: OrderDirection


class QueryBuilder(Generic[T]):
    """
    Fluent SQL query builder.
    
    Provides a chainable interface for building complex queries.
    
    Example:
        users = await User.query() \\
            .select("id", "name", "email") \\
            .where("is_active", True) \\
            .where("role", "IN", ["admin", "manager"]) \\
            .order_by("created_at", "DESC") \\
            .limit(10) \\
            .get()
    """
    
    def __init__(self, model: Type[T]) -> None:
        """Initialize query builder."""
        self.model = model
        self._table = model.__table_name__
        
        # Query components
        self._selects: List[str] = []
        self._distinct = False
        self._wheres: List[WhereClause] = []
        self._joins: List[JoinClause] = []
        self._orders: List[OrderClause] = []
        self._groups: List[str] = []
        self._havings: List[WhereClause] = []
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None
        self._with_relations: List[str] = []
        
    def select(self, *columns: str) -> QueryBuilder[T]:
        """
        Specify columns to select.
        
        Args:
            *columns: Column names or expressions
            
        Example:
            query.select("id", "name")
            query.select("*")
        """
        self._selects.extend(columns)
        return self
        
    def select_raw(self, expression: str) -> QueryBuilder[T]:
        """Select with raw expression."""
        self._selects.append(expression)
        return self
        
    def distinct(self) -> QueryBuilder[T]:
        """Add DISTINCT to query."""
        self._distinct = True
        return self
        
    def where(
        self,
        column: Union[str, Q],
        operator: Any = None,
        value: Any = None,
    ) -> QueryBuilder[T]:
        """
        Add WHERE clause.
        
        Args:
            column: Column name, or Q object for complex conditions
            operator: Comparison operator (defaults to "=")
            value: Value to compare
            
        Examples:
            query.where("name", "John")
            query.where("age", ">", 18)
            query.where("status", "IN", ["active", "pending"])
            query.where(Q(role="admin") | Q(is_superuser=True))
        """
        if isinstance(column, Q):
            # Complex condition
            self._wheres.append(WhereClause(
                column="",
                operator=Operator.EQ,
                value=column,
                is_raw=True,
            ))
            return self
            
        # Handle shorthand: where("name", "John") -> where("name", "=", "John")
        if value is None and operator is not None:
            value = operator
            operator = "="
            
        # Parse operator
        op_map = {
            "=": Operator.EQ,
            "!=": Operator.NE,
            "<>": Operator.NE,
            "<": Operator.LT,
            "<=": Operator.LE,
            ">": Operator.GT,
            ">=": Operator.GE,
            "LIKE": Operator.LIKE,
            "like": Operator.LIKE,
            "NOT LIKE": Operator.NOT_LIKE,
            "IN": Operator.IN,
            "in": Operator.IN,
            "NOT IN": Operator.NOT_IN,
            "BETWEEN": Operator.BETWEEN,
        }
        
        op = op_map.get(operator, Operator.EQ)
        
        self._wheres.append(WhereClause(
            column=column,
            operator=op,
            value=value,
        ))
        
        return self
        
    def or_where(
        self,
        column: str,
        operator: Any = None,
        value: Any = None,
    ) -> QueryBuilder[T]:
        """Add OR WHERE clause."""
        if value is None and operator is not None:
            value = operator
            operator = "="
            
        op_map = {
            "=": Operator.EQ,
            "!=": Operator.NE,
            "<": Operator.LT,
            "<=": Operator.LE,
            ">": Operator.GT,
            ">=": Operator.GE,
        }
        
        op = op_map.get(operator, Operator.EQ)
        
        self._wheres.append(WhereClause(
            column=column,
            operator=op,
            value=value,
            connector="OR",
        ))
        
        return self
        
    def where_null(self, column: str) -> QueryBuilder[T]:
        """Add WHERE column IS NULL."""
        self._wheres.append(WhereClause(
            column=column,
            operator=Operator.IS,
            value=None,
        ))
        return self
        
    def where_not_null(self, column: str) -> QueryBuilder[T]:
        """Add WHERE column IS NOT NULL."""
        self._wheres.append(WhereClause(
            column=column,
            operator=Operator.IS_NOT,
            value=None,
        ))
        return self
        
    def where_in(self, column: str, values: List[Any]) -> QueryBuilder[T]:
        """Add WHERE column IN (values)."""
        self._wheres.append(WhereClause(
            column=column,
            operator=Operator.IN,
            value=values,
        ))
        return self
        
    def where_not_in(self, column: str, values: List[Any]) -> QueryBuilder[T]:
        """Add WHERE column NOT IN (values)."""
        self._wheres.append(WhereClause(
            column=column,
            operator=Operator.NOT_IN,
            value=values,
        ))
        return self
        
    def where_between(
        self,
        column: str,
        low: Any,
        high: Any,
    ) -> QueryBuilder[T]:
        """Add WHERE column BETWEEN low AND high."""
        self._wheres.append(WhereClause(
            column=column,
            operator=Operator.BETWEEN,
            value=(low, high),
        ))
        return self
        
    def where_raw(self, sql: str, bindings: List[Any] = None) -> QueryBuilder[T]:
        """Add raw WHERE clause."""
        self._wheres.append(WhereClause(
            column=sql,
            operator=Operator.EQ,
            value=bindings or [],
            is_raw=True,
        ))
        return self
        
    def join(
        self,
        table: str,
        left: str,
        right: str,
        join_type: str = "INNER",
    ) -> QueryBuilder[T]:
        """
        Add JOIN clause.
        
        Args:
            table: Table to join
            left: Left column (from main table)
            right: Right column (from joined table)
            join_type: Type of join (INNER, LEFT, RIGHT, OUTER)
            
        Example:
            query.join("posts", "users.id", "posts.user_id")
        """
        type_map = {
            "INNER": JoinType.INNER,
            "LEFT": JoinType.LEFT,
            "RIGHT": JoinType.RIGHT,
            "OUTER": JoinType.OUTER,
            "CROSS": JoinType.CROSS,
        }
        
        self._joins.append(JoinClause(
            table=table,
            type=type_map.get(join_type.upper(), JoinType.INNER),
            on_left=left,
            on_right=right,
        ))
        
        return self
        
    def left_join(self, table: str, left: str, right: str) -> QueryBuilder[T]:
        """Add LEFT JOIN."""
        return self.join(table, left, right, "LEFT")
        
    def right_join(self, table: str, left: str, right: str) -> QueryBuilder[T]:
        """Add RIGHT JOIN."""
        return self.join(table, left, right, "RIGHT")
        
    def order_by(
        self,
        column: str,
        direction: str = "ASC",
    ) -> QueryBuilder[T]:
        """
        Add ORDER BY clause.
        
        Args:
            column: Column to sort by
            direction: ASC or DESC
            
        Example:
            query.order_by("created_at", "DESC")
        """
        dir_enum = OrderDirection.DESC if direction.upper() == "DESC" else OrderDirection.ASC
        
        self._orders.append(OrderClause(
            column=column,
            direction=dir_enum,
        ))
        
        return self
        
    def latest(self, column: str = "created_at") -> QueryBuilder[T]:
        """Order by column DESC."""
        return self.order_by(column, "DESC")
        
    def oldest(self, column: str = "created_at") -> QueryBuilder[T]:
        """Order by column ASC."""
        return self.order_by(column, "ASC")
        
    def group_by(self, *columns: str) -> QueryBuilder[T]:
        """Add GROUP BY clause."""
        self._groups.extend(columns)
        return self
        
    def having(
        self,
        column: str,
        operator: Any = None,
        value: Any = None,
    ) -> QueryBuilder[T]:
        """Add HAVING clause."""
        if value is None and operator is not None:
            value = operator
            operator = "="
            
        op_map = {
            "=": Operator.EQ,
            "!=": Operator.NE,
            "<": Operator.LT,
            "<=": Operator.LE,
            ">": Operator.GT,
            ">=": Operator.GE,
        }
        
        op = op_map.get(operator, Operator.EQ)
        
        self._havings.append(WhereClause(
            column=column,
            operator=op,
            value=value,
        ))
        
        return self
        
    def limit(self, count: int) -> QueryBuilder[T]:
        """Limit number of results."""
        self._limit = count
        return self
        
    def offset(self, count: int) -> QueryBuilder[T]:
        """Skip first N results."""
        self._offset = count
        return self
        
    def take(self, count: int) -> QueryBuilder[T]:
        """Alias for limit()."""
        return self.limit(count)
        
    def skip(self, count: int) -> QueryBuilder[T]:
        """Alias for offset()."""
        return self.offset(count)
        
    def with_relations(self, *relations: str) -> QueryBuilder[T]:
        """Eager load relationships."""
        self._with_relations.extend(relations)
        return self
        
    # Execution methods
    
    def to_sql(self) -> Tuple[str, List[Any]]:
        """
        Build SQL query string.
        
        Returns:
            Tuple of (sql_string, bindings)
        """
        bindings: List[Any] = []
        parts = []
        
        # SELECT
        select_clause = ", ".join(self._selects) if self._selects else "*"
        if self._distinct:
            select_clause = f"DISTINCT {select_clause}"
        parts.append(f"SELECT {select_clause}")
        
        # FROM
        parts.append(f"FROM {self._table}")
        
        # JOIN
        for join in self._joins:
            parts.append(
                f"{join.type.value} {join.table} ON {join.on_left} = {join.on_right}"
            )
            
        # WHERE
        if self._wheres:
            where_parts = []
            
            for i, clause in enumerate(self._wheres):
                if clause.is_raw:
                    if isinstance(clause.value, Q):
                        q_sql, q_bindings = clause.value.to_sql()
                        where_parts.append(q_sql)
                        bindings.extend(q_bindings)
                    elif isinstance(clause.value, list):
                        where_parts.append(clause.column)
                        bindings.extend(clause.value)
                    else:
                        where_parts.append(clause.column)
                    continue
                    
                connector = "" if i == 0 else f"{clause.connector} "
                
                if clause.operator == Operator.IN:
                    placeholders = ", ".join("?" for _ in clause.value)
                    where_parts.append(
                        f"{connector}{clause.column} IN ({placeholders})"
                    )
                    bindings.extend(clause.value)
                elif clause.operator == Operator.NOT_IN:
                    placeholders = ", ".join("?" for _ in clause.value)
                    where_parts.append(
                        f"{connector}{clause.column} NOT IN ({placeholders})"
                    )
                    bindings.extend(clause.value)
                elif clause.operator == Operator.BETWEEN:
                    where_parts.append(
                        f"{connector}{clause.column} BETWEEN ? AND ?"
                    )
                    bindings.extend(clause.value)
                elif clause.operator == Operator.IS:
                    where_parts.append(
                        f"{connector}{clause.column} IS NULL"
                    )
                elif clause.operator == Operator.IS_NOT:
                    where_parts.append(
                        f"{connector}{clause.column} IS NOT NULL"
                    )
                else:
                    where_parts.append(
                        f"{connector}{clause.column} {clause.operator.value} ?"
                    )
                    bindings.append(clause.value)
                    
            parts.append(f"WHERE {' '.join(where_parts)}")
            
        # GROUP BY
        if self._groups:
            parts.append(f"GROUP BY {', '.join(self._groups)}")
            
        # HAVING
        if self._havings:
            having_parts = []
            
            for i, clause in enumerate(self._havings):
                connector = "" if i == 0 else "AND "
                having_parts.append(
                    f"{connector}{clause.column} {clause.operator.value} ?"
                )
                bindings.append(clause.value)
                
            parts.append(f"HAVING {' '.join(having_parts)}")
            
        # ORDER BY
        if self._orders:
            order_parts = [
                f"{o.column} {o.direction.value}" for o in self._orders
            ]
            parts.append(f"ORDER BY {', '.join(order_parts)}")
            
        # LIMIT
        if self._limit is not None:
            parts.append(f"LIMIT {self._limit}")
            
        # OFFSET
        if self._offset is not None:
            parts.append(f"OFFSET {self._offset}")
            
        return " ".join(parts), bindings
        
    async def get(self) -> List[T]:
        """Execute query and return results."""
        if not self.model._database:
            raise RuntimeError("No database connection")
            
        sql, bindings = self.to_sql()
        rows = await self.model._database.fetch_all(sql, bindings)
        
        return [self.model.from_row(dict(row)) for row in rows]
        
    async def first(self) -> Optional[T]:
        """Get first result."""
        self._limit = 1
        results = await self.get()
        return results[0] if results else None
        
    async def first_or_fail(self) -> T:
        """Get first result or raise."""
        result = await self.first()
        if result is None:
            raise ValueError(f"No {self.model.__name__} found")
        return result
        
    async def count(self) -> int:
        """Count matching records."""
        if not self.model._database:
            raise RuntimeError("No database connection")
            
        # Build count query
        self._selects = ["COUNT(*) as count"]
        self._orders = []
        self._limit = None
        self._offset = None
        
        sql, bindings = self.to_sql()
        row = await self.model._database.fetch_one(sql, bindings)
        
        return row["count"] if row else 0
        
    async def exists(self) -> bool:
        """Check if any records match."""
        return await self.count() > 0
        
    async def delete(self) -> int:
        """Delete matching records."""
        if not self.model._database:
            raise RuntimeError("No database connection")
            
        # Build DELETE query
        bindings: List[Any] = []
        parts = [f"DELETE FROM {self._table}"]
        
        if self._wheres:
            where_sql, where_bindings = self._build_where()
            parts.append(f"WHERE {where_sql}")
            bindings.extend(where_bindings)
            
        sql = " ".join(parts)
        result = await self.model._database.execute(sql, bindings)
        
        return result.rowcount
        
    async def update(self, **values) -> int:
        """Update matching records."""
        if not self.model._database:
            raise RuntimeError("No database connection")
            
        # Build UPDATE query
        bindings: List[Any] = []
        parts = [f"UPDATE {self._table}"]
        
        # SET clause
        set_parts = []
        for key, value in values.items():
            if isinstance(value, F):
                f_sql, f_bindings = value.to_sql()
                set_parts.append(f"{key} = {f_sql}")
                bindings.extend(f_bindings)
            else:
                set_parts.append(f"{key} = ?")
                bindings.append(value)
                
        parts.append(f"SET {', '.join(set_parts)}")
        
        # WHERE
        if self._wheres:
            where_sql, where_bindings = self._build_where()
            parts.append(f"WHERE {where_sql}")
            bindings.extend(where_bindings)
            
        sql = " ".join(parts)
        result = await self.model._database.execute(sql, bindings)
        
        return result.rowcount
        
    def _build_where(self) -> Tuple[str, List[Any]]:
        """Build WHERE clause for UPDATE/DELETE."""
        parts = []
        bindings = []
        
        for i, clause in enumerate(self._wheres):
            connector = "" if i == 0 else f"{clause.connector} "
            
            if clause.operator == Operator.IN:
                placeholders = ", ".join("?" for _ in clause.value)
                parts.append(f"{connector}{clause.column} IN ({placeholders})")
                bindings.extend(clause.value)
            elif clause.operator == Operator.IS:
                parts.append(f"{connector}{clause.column} IS NULL")
            elif clause.operator == Operator.IS_NOT:
                parts.append(f"{connector}{clause.column} IS NOT NULL")
            else:
                parts.append(f"{connector}{clause.column} {clause.operator.value} ?")
                bindings.append(clause.value)
                
        return " ".join(parts), bindings


# Alias
Query = QueryBuilder
