"""
NexaWeb ORM Database Connection
===============================

Database connection and pool management.

Features:
- Async connection pool
- Multiple database support (SQLite, PostgreSQL, MySQL)
- Transaction support
- Query logging
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional, Type
from urllib.parse import parse_qs, urlparse


logger = logging.getLogger(__name__)


class DatabaseDriver(Enum):
    """Supported database drivers."""
    
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"


@dataclass
class DatabaseConfig:
    """
    Database configuration.
    
    Can be initialized from a URL or individual parameters.
    
    Example:
        # From URL
        config = DatabaseConfig.from_url("sqlite:///./app.db")
        config = DatabaseConfig.from_url("postgresql://user:pass@localhost/mydb")
        
        # From parameters
        config = DatabaseConfig(
            driver=DatabaseDriver.POSTGRESQL,
            host="localhost",
            port=5432,
            database="mydb",
            username="user",
            password="pass",
        )
    """
    
    driver: DatabaseDriver = DatabaseDriver.SQLITE
    host: str = "localhost"
    port: int = 0
    database: str = ""
    username: str = ""
    password: str = ""
    
    # Connection pool settings
    min_size: int = 1
    max_size: int = 10
    
    # Connection settings
    connect_timeout: int = 30
    command_timeout: int = 60
    
    # SQLite specific
    sqlite_path: str = ""
    
    # SSL settings
    ssl: bool = False
    ssl_cert: Optional[str] = None
    ssl_key: Optional[str] = None
    ssl_ca: Optional[str] = None
    
    # Extra options
    options: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_url(cls, url: str) -> DatabaseConfig:
        """
        Create config from database URL.
        
        Formats:
        - sqlite:///path/to/db.sqlite
        - postgresql://user:pass@host:port/database
        - mysql://user:pass@host:port/database
        """
        parsed = urlparse(url)
        
        driver_map = {
            "sqlite": DatabaseDriver.SQLITE,
            "sqlite3": DatabaseDriver.SQLITE,
            "postgresql": DatabaseDriver.POSTGRESQL,
            "postgres": DatabaseDriver.POSTGRESQL,
            "mysql": DatabaseDriver.MYSQL,
            "mariadb": DatabaseDriver.MYSQL,
        }
        
        driver = driver_map.get(parsed.scheme)
        if not driver:
            raise ValueError(f"Unsupported database driver: {parsed.scheme}")
            
        config = cls(driver=driver)
        
        if driver == DatabaseDriver.SQLITE:
            # SQLite path is in netloc + path
            path = parsed.netloc + parsed.path
            if path.startswith("//"):
                path = path[2:]
            config.sqlite_path = path
            config.database = path
        else:
            config.host = parsed.hostname or "localhost"
            config.port = parsed.port or (5432 if driver == DatabaseDriver.POSTGRESQL else 3306)
            config.database = parsed.path.lstrip("/")
            config.username = parsed.username or ""
            config.password = parsed.password or ""
            
            # Parse query options
            if parsed.query:
                options = parse_qs(parsed.query)
                for key, values in options.items():
                    config.options[key] = values[0] if len(values) == 1 else values
                    
        return config
        
    def get_dsn(self) -> str:
        """Get DSN string for database connection."""
        if self.driver == DatabaseDriver.SQLITE:
            return f"sqlite:///{self.sqlite_path}"
        elif self.driver == DatabaseDriver.POSTGRESQL:
            auth = f"{self.username}:{self.password}@" if self.username else ""
            return f"postgresql://{auth}{self.host}:{self.port}/{self.database}"
        elif self.driver == DatabaseDriver.MYSQL:
            auth = f"{self.username}:{self.password}@" if self.username else ""
            return f"mysql://{auth}{self.host}:{self.port}/{self.database}"
        return ""


@dataclass
class QueryResult:
    """Result of a query execution."""
    
    rows: List[Dict[str, Any]] = field(default_factory=list)
    rowcount: int = 0
    lastrowid: Optional[int] = None
    
    def __iter__(self):
        return iter(self.rows)
        
    def __len__(self):
        return len(self.rows)


class Connection(ABC):
    """
    Abstract database connection.
    
    Implement for specific database drivers.
    """
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection."""
        ...
        
    @abstractmethod
    async def close(self) -> None:
        """Close connection."""
        ...
        
    @abstractmethod
    async def execute(
        self,
        query: str,
        params: List[Any] = None,
    ) -> QueryResult:
        """Execute a query."""
        ...
        
    @abstractmethod
    async def fetch_one(
        self,
        query: str,
        params: List[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fetch single row."""
        ...
        
    @abstractmethod
    async def fetch_all(
        self,
        query: str,
        params: List[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch all rows."""
        ...
        
    @abstractmethod
    async def begin(self) -> None:
        """Begin transaction."""
        ...
        
    @abstractmethod
    async def commit(self) -> None:
        """Commit transaction."""
        ...
        
    @abstractmethod
    async def rollback(self) -> None:
        """Rollback transaction."""
        ...
        
    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[Connection]:
        """Transaction context manager."""
        await self.begin()
        try:
            yield self
            await self.commit()
        except Exception:
            await self.rollback()
            raise


class SQLiteConnection(Connection):
    """
    SQLite database connection.
    
    Uses aiosqlite for async support.
    """
    
    def __init__(self, config: DatabaseConfig) -> None:
        self.config = config
        self._conn = None
        
    async def connect(self) -> None:
        """Connect to SQLite database."""
        try:
            import aiosqlite
            self._conn = await aiosqlite.connect(
                self.config.sqlite_path,
                timeout=self.config.connect_timeout,
            )
            self._conn.row_factory = aiosqlite.Row
        except ImportError:
            raise ImportError("aiosqlite is required for SQLite support")
            
    async def close(self) -> None:
        """Close connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None
            
    async def execute(
        self,
        query: str,
        params: List[Any] = None,
    ) -> QueryResult:
        """Execute query."""
        params = params or []
        logger.debug(f"SQL: {query} | Params: {params}")
        
        cursor = await self._conn.execute(query, params)
        await self._conn.commit()
        
        return QueryResult(
            rowcount=cursor.rowcount,
            lastrowid=cursor.lastrowid,
        )
        
    async def fetch_one(
        self,
        query: str,
        params: List[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fetch single row."""
        params = params or []
        logger.debug(f"SQL: {query} | Params: {params}")
        
        cursor = await self._conn.execute(query, params)
        row = await cursor.fetchone()
        
        if row:
            return dict(row)
        return None
        
    async def fetch_all(
        self,
        query: str,
        params: List[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch all rows."""
        params = params or []
        logger.debug(f"SQL: {query} | Params: {params}")
        
        cursor = await self._conn.execute(query, params)
        rows = await cursor.fetchall()
        
        return [dict(row) for row in rows]
        
    async def begin(self) -> None:
        """Begin transaction."""
        await self._conn.execute("BEGIN")
        
    async def commit(self) -> None:
        """Commit transaction."""
        await self._conn.commit()
        
    async def rollback(self) -> None:
        """Rollback transaction."""
        await self._conn.rollback()


class PostgreSQLConnection(Connection):
    """
    PostgreSQL database connection.
    
    Uses asyncpg for async support.
    """
    
    def __init__(self, config: DatabaseConfig) -> None:
        self.config = config
        self._conn = None
        self._in_transaction = False
        
    async def connect(self) -> None:
        """Connect to PostgreSQL database."""
        try:
            import asyncpg
            
            self._conn = await asyncpg.connect(
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.username,
                password=self.config.password,
                timeout=self.config.connect_timeout,
                ssl=self.config.ssl,
            )
        except ImportError:
            raise ImportError("asyncpg is required for PostgreSQL support")
            
    async def close(self) -> None:
        """Close connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None
            
    async def execute(
        self,
        query: str,
        params: List[Any] = None,
    ) -> QueryResult:
        """Execute query."""
        params = params or []
        # Convert ? to $1, $2, etc for asyncpg
        query = self._convert_placeholders(query)
        
        logger.debug(f"SQL: {query} | Params: {params}")
        
        result = await self._conn.execute(query, *params)
        
        # Parse result string like "INSERT 0 1"
        parts = result.split()
        rowcount = int(parts[-1]) if parts else 0
        
        return QueryResult(rowcount=rowcount)
        
    async def fetch_one(
        self,
        query: str,
        params: List[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fetch single row."""
        params = params or []
        query = self._convert_placeholders(query)
        
        logger.debug(f"SQL: {query} | Params: {params}")
        
        row = await self._conn.fetchrow(query, *params)
        
        if row:
            return dict(row)
        return None
        
    async def fetch_all(
        self,
        query: str,
        params: List[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch all rows."""
        params = params or []
        query = self._convert_placeholders(query)
        
        logger.debug(f"SQL: {query} | Params: {params}")
        
        rows = await self._conn.fetch(query, *params)
        
        return [dict(row) for row in rows]
        
    async def begin(self) -> None:
        """Begin transaction."""
        await self._conn.execute("BEGIN")
        self._in_transaction = True
        
    async def commit(self) -> None:
        """Commit transaction."""
        await self._conn.execute("COMMIT")
        self._in_transaction = False
        
    async def rollback(self) -> None:
        """Rollback transaction."""
        await self._conn.execute("ROLLBACK")
        self._in_transaction = False
        
    def _convert_placeholders(self, query: str) -> str:
        """Convert ? placeholders to $1, $2, etc."""
        result = []
        idx = 1
        i = 0
        
        while i < len(query):
            if query[i] == "?":
                result.append(f"${idx}")
                idx += 1
            else:
                result.append(query[i])
            i += 1
            
        return "".join(result)


class MySQLConnection(Connection):
    """
    MySQL database connection.
    
    Uses aiomysql for async support.
    """
    
    def __init__(self, config: DatabaseConfig) -> None:
        self.config = config
        self._conn = None
        
    async def connect(self) -> None:
        """Connect to MySQL database."""
        try:
            import aiomysql
            
            self._conn = await aiomysql.connect(
                host=self.config.host,
                port=self.config.port,
                db=self.config.database,
                user=self.config.username,
                password=self.config.password,
                connect_timeout=self.config.connect_timeout,
            )
        except ImportError:
            raise ImportError("aiomysql is required for MySQL support")
            
    async def close(self) -> None:
        """Close connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            
    async def execute(
        self,
        query: str,
        params: List[Any] = None,
    ) -> QueryResult:
        """Execute query."""
        params = params or []
        # Convert ? to %s for MySQL
        query = query.replace("?", "%s")
        
        logger.debug(f"SQL: {query} | Params: {params}")
        
        async with self._conn.cursor() as cursor:
            await cursor.execute(query, params)
            await self._conn.commit()
            
            return QueryResult(
                rowcount=cursor.rowcount,
                lastrowid=cursor.lastrowid,
            )
            
    async def fetch_one(
        self,
        query: str,
        params: List[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fetch single row."""
        params = params or []
        query = query.replace("?", "%s")
        
        logger.debug(f"SQL: {query} | Params: {params}")
        
        import aiomysql
        async with self._conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(query, params)
            row = await cursor.fetchone()
            return row
            
    async def fetch_all(
        self,
        query: str,
        params: List[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch all rows."""
        params = params or []
        query = query.replace("?", "%s")
        
        logger.debug(f"SQL: {query} | Params: {params}")
        
        import aiomysql
        async with self._conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(query, params)
            rows = await cursor.fetchall()
            return list(rows)
            
    async def begin(self) -> None:
        """Begin transaction."""
        await self._conn.begin()
        
    async def commit(self) -> None:
        """Commit transaction."""
        await self._conn.commit()
        
    async def rollback(self) -> None:
        """Rollback transaction."""
        await self._conn.rollback()


class ConnectionPool:
    """
    Async database connection pool.
    
    Manages a pool of database connections for reuse.
    
    Example:
        pool = ConnectionPool(config)
        await pool.connect()
        
        async with pool.acquire() as conn:
            await conn.execute("SELECT * FROM users")
            
        await pool.close()
    """
    
    def __init__(self, config: DatabaseConfig) -> None:
        self.config = config
        self._pool: List[Connection] = []
        self._available: asyncio.Queue = asyncio.Queue()
        self._lock = asyncio.Lock()
        self._closed = False
        
    async def connect(self) -> None:
        """Initialize connection pool."""
        for _ in range(self.config.min_size):
            conn = await self._create_connection()
            self._pool.append(conn)
            await self._available.put(conn)
            
    async def close(self) -> None:
        """Close all connections."""
        self._closed = True
        
        for conn in self._pool:
            await conn.close()
            
        self._pool.clear()
        
    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[Connection]:
        """
        Acquire connection from pool.
        
        Returns connection to pool when done.
        """
        conn = await self._get_connection()
        try:
            yield conn
        finally:
            await self._return_connection(conn)
            
    async def _get_connection(self) -> Connection:
        """Get available connection."""
        if self._closed:
            raise RuntimeError("Pool is closed")
            
        try:
            # Try to get from available queue
            return self._available.get_nowait()
        except asyncio.QueueEmpty:
            pass
            
        # Create new connection if under max
        async with self._lock:
            if len(self._pool) < self.config.max_size:
                conn = await self._create_connection()
                self._pool.append(conn)
                return conn
                
        # Wait for available connection
        return await self._available.get()
        
    async def _return_connection(self, conn: Connection) -> None:
        """Return connection to pool."""
        if not self._closed:
            await self._available.put(conn)
            
    async def _create_connection(self) -> Connection:
        """Create new connection based on driver."""
        conn_class = {
            DatabaseDriver.SQLITE: SQLiteConnection,
            DatabaseDriver.POSTGRESQL: PostgreSQLConnection,
            DatabaseDriver.MYSQL: MySQLConnection,
        }.get(self.config.driver)
        
        if not conn_class:
            raise ValueError(f"Unsupported driver: {self.config.driver}")
            
        conn = conn_class(self.config)
        await conn.connect()
        return conn


class Database:
    """
    Main database interface.
    
    Provides high-level database operations with connection pooling.
    
    Example:
        db = Database("sqlite:///app.db")
        await db.connect()
        
        # Direct queries
        users = await db.fetch_all("SELECT * FROM users")
        
        # With model
        User.use(db)
        users = await User.all()
        
        await db.close()
    """
    
    def __init__(
        self,
        url: Optional[str] = None,
        config: Optional[DatabaseConfig] = None,
    ) -> None:
        """
        Initialize database.
        
        Args:
            url: Database URL
            config: Database configuration
        """
        if url:
            self.config = DatabaseConfig.from_url(url)
        elif config:
            self.config = config
        else:
            raise ValueError("url or config required")
            
        self._pool: Optional[ConnectionPool] = None
        self._single_conn: Optional[Connection] = None
        
    async def connect(self) -> None:
        """Connect to database."""
        if self.config.max_size > 1:
            self._pool = ConnectionPool(self.config)
            await self._pool.connect()
        else:
            self._single_conn = await self._create_connection()
            await self._single_conn.connect()
            
    async def close(self) -> None:
        """Close database connections."""
        if self._pool:
            await self._pool.close()
        elif self._single_conn:
            await self._single_conn.close()
            
    async def _create_connection(self) -> Connection:
        """Create single connection."""
        conn_class = {
            DatabaseDriver.SQLITE: SQLiteConnection,
            DatabaseDriver.POSTGRESQL: PostgreSQLConnection,
            DatabaseDriver.MYSQL: MySQLConnection,
        }.get(self.config.driver)
        
        if not conn_class:
            raise ValueError(f"Unsupported driver: {self.config.driver}")
            
        return conn_class(self.config)
        
    @asynccontextmanager
    async def connection(self) -> AsyncIterator[Connection]:
        """Get database connection."""
        if self._pool:
            async with self._pool.acquire() as conn:
                yield conn
        elif self._single_conn:
            yield self._single_conn
        else:
            raise RuntimeError("Database not connected")
            
    async def execute(
        self,
        query: str,
        params: List[Any] = None,
    ) -> QueryResult:
        """Execute query."""
        async with self.connection() as conn:
            return await conn.execute(query, params)
            
    async def fetch_one(
        self,
        query: str,
        params: List[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fetch single row."""
        async with self.connection() as conn:
            return await conn.fetch_one(query, params)
            
    async def fetch_all(
        self,
        query: str,
        params: List[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch all rows."""
        async with self.connection() as conn:
            return await conn.fetch_all(query, params)
            
    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[Connection]:
        """Transaction context."""
        async with self.connection() as conn:
            async with conn.transaction():
                yield conn
