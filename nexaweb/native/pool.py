"""
NexaWeb Native Connection Pool
==============================

High-performance connection pooling.
This is a Python stub that can be replaced with a native implementation.

The native implementation would use:
- Lock-free data structures
- Efficient connection state tracking
- Optimized memory allocation
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, Optional, TypeVar, Union
from contextlib import asynccontextmanager


T = TypeVar("T")


@dataclass
class PoolStats:
    """
    Pool statistics.
    
    Attributes:
        total: Total connections created
        active: Currently in-use connections
        idle: Available connections
        waiting: Requests waiting for connection
        hits: Cache hits
        misses: Cache misses
    """
    
    total: int = 0
    active: int = 0
    idle: int = 0
    waiting: int = 0
    hits: int = 0
    misses: int = 0
    timeouts: int = 0
    errors: int = 0


@dataclass
class PooledConnection(Generic[T]):
    """
    Pooled connection wrapper.
    
    Attributes:
        connection: Actual connection object
        created_at: Creation timestamp
        last_used_at: Last use timestamp
        use_count: Number of times used
    """
    
    connection: T
    created_at: float = field(default_factory=time.time)
    last_used_at: float = field(default_factory=time.time)
    use_count: int = 0
    
    def touch(self) -> None:
        """Update last used timestamp."""
        self.last_used_at = time.time()
        self.use_count += 1
    
    @property
    def age(self) -> float:
        """Get connection age in seconds."""
        return time.time() - self.created_at
    
    @property
    def idle_time(self) -> float:
        """Get idle time in seconds."""
        return time.time() - self.last_used_at


class NativePool(Generic[T]):
    """
    High-performance async connection pool.
    
    This Python implementation provides the same API as the
    native C++ version but with pure Python performance.
    
    Example:
        async def create_connection():
            return await asyncpg.connect(...)
        
        pool = NativePool(
            create=create_connection,
            min_size=5,
            max_size=20,
        )
        
        async with pool.acquire() as conn:
            result = await conn.fetch("SELECT * FROM users")
    
    Native implementation would provide:
        - Lock-free connection management
        - Better memory efficiency
        - Lower latency acquisition
    """
    
    def __init__(
        self,
        create: Callable[[], Union[T, Any]],
        close: Optional[Callable[[T], Union[None, Any]]] = None,
        validate: Optional[Callable[[T], Union[bool, Any]]] = None,
        min_size: int = 1,
        max_size: int = 10,
        max_idle_time: float = 300.0,  # 5 minutes
        max_lifetime: float = 3600.0,  # 1 hour
        acquire_timeout: float = 10.0,
    ):
        """
        Initialize pool.
        
        Args:
            create: Factory function to create connections
            close: Function to close connections
            validate: Function to validate connections
            min_size: Minimum pool size
            max_size: Maximum pool size
            max_idle_time: Max time connection can be idle
            max_lifetime: Max lifetime of connection
            acquire_timeout: Timeout for acquiring connection
        """
        self._create = create
        self._close = close
        self._validate = validate
        
        self._min_size = min_size
        self._max_size = max_size
        self._max_idle_time = max_idle_time
        self._max_lifetime = max_lifetime
        self._acquire_timeout = acquire_timeout
        
        # Pool state
        self._pool: deque[PooledConnection[T]] = deque()
        self._in_use: int = 0
        self._total: int = 0
        
        # Synchronization
        self._lock = asyncio.Lock()
        self._available = asyncio.Condition()
        
        # Stats
        self._stats = PoolStats()
        
        # State
        self._closed = False
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize pool with minimum connections."""
        if self._initialized:
            return
        
        async with self._lock:
            for _ in range(self._min_size):
                try:
                    conn = await self._create_connection()
                    self._pool.append(conn)
                except Exception:
                    pass
            
            self._initialized = True
    
    async def _create_connection(self) -> PooledConnection[T]:
        """Create new pooled connection."""
        result = self._create()
        
        if asyncio.iscoroutine(result):
            connection = await result
        else:
            connection = result
        
        self._total += 1
        self._stats.total += 1
        
        return PooledConnection(connection=connection)
    
    async def _close_connection(self, pooled: PooledConnection[T]) -> None:
        """Close pooled connection."""
        self._total -= 1
        
        if self._close:
            result = self._close(pooled.connection)
            if asyncio.iscoroutine(result):
                await result
    
    async def _validate_connection(self, pooled: PooledConnection[T]) -> bool:
        """Validate pooled connection."""
        # Check lifetime
        if pooled.age > self._max_lifetime:
            return False
        
        # Check idle time
        if pooled.idle_time > self._max_idle_time:
            return False
        
        # Custom validation
        if self._validate:
            result = self._validate(pooled.connection)
            if asyncio.iscoroutine(result):
                return await result
            return result
        
        return True
    
    @asynccontextmanager
    async def acquire(self):
        """
        Acquire connection from pool.
        
        Yields:
            Connection object
            
        Raises:
            TimeoutError: If acquisition times out
            RuntimeError: If pool is closed
        """
        if self._closed:
            raise RuntimeError("Pool is closed")
        
        if not self._initialized:
            await self.initialize()
        
        pooled = await self._acquire()
        
        try:
            yield pooled.connection
        finally:
            await self._release(pooled)
    
    async def _acquire(self) -> PooledConnection[T]:
        """Internal acquire implementation."""
        deadline = time.time() + self._acquire_timeout
        
        async with self._available:
            while True:
                # Try to get from pool
                while self._pool:
                    pooled = self._pool.popleft()
                    
                    if await self._validate_connection(pooled):
                        pooled.touch()
                        self._in_use += 1
                        self._stats.hits += 1
                        return pooled
                    else:
                        # Invalid connection, close it
                        await self._close_connection(pooled)
                
                # Can we create new connection?
                if self._total < self._max_size:
                    try:
                        pooled = await self._create_connection()
                        pooled.touch()
                        self._in_use += 1
                        self._stats.misses += 1
                        return pooled
                    except Exception as e:
                        self._stats.errors += 1
                        raise
                
                # Wait for available connection
                self._stats.waiting += 1
                
                timeout = deadline - time.time()
                if timeout <= 0:
                    self._stats.timeouts += 1
                    raise TimeoutError("Connection pool acquire timeout")
                
                try:
                    await asyncio.wait_for(
                        self._available.wait(),
                        timeout=timeout,
                    )
                finally:
                    self._stats.waiting -= 1
    
    async def _release(self, pooled: PooledConnection[T]) -> None:
        """Release connection back to pool."""
        async with self._available:
            self._in_use -= 1
            
            if not self._closed and await self._validate_connection(pooled):
                self._pool.append(pooled)
            else:
                await self._close_connection(pooled)
            
            self._available.notify()
    
    async def close(self) -> None:
        """Close pool and all connections."""
        async with self._lock:
            self._closed = True
            
            # Close all idle connections
            while self._pool:
                pooled = self._pool.popleft()
                await self._close_connection(pooled)
    
    def stats(self) -> PoolStats:
        """Get pool statistics."""
        self._stats.active = self._in_use
        self._stats.idle = len(self._pool)
        return self._stats
    
    @property
    def size(self) -> int:
        """Current pool size."""
        return len(self._pool) + self._in_use
    
    @property
    def available(self) -> int:
        """Number of available connections."""
        return len(self._pool)
    
    @property
    def in_use(self) -> int:
        """Number of in-use connections."""
        return self._in_use
    
    def __len__(self) -> int:
        return self.size


class SyncNativePool(Generic[T]):
    """
    Synchronous version of NativePool.
    
    For use in synchronous contexts.
    """
    
    def __init__(
        self,
        create: Callable[[], T],
        close: Optional[Callable[[T], None]] = None,
        validate: Optional[Callable[[T], bool]] = None,
        min_size: int = 1,
        max_size: int = 10,
        max_idle_time: float = 300.0,
        max_lifetime: float = 3600.0,
        acquire_timeout: float = 10.0,
    ):
        """Initialize synchronous pool."""
        self._create = create
        self._close = close
        self._validate = validate
        
        self._min_size = min_size
        self._max_size = max_size
        self._max_idle_time = max_idle_time
        self._max_lifetime = max_lifetime
        self._acquire_timeout = acquire_timeout
        
        self._pool: deque[PooledConnection[T]] = deque()
        self._in_use: int = 0
        self._total: int = 0
        
        self._lock = threading.Lock()
        self._available = threading.Condition(self._lock)
        
        self._stats = PoolStats()
        self._closed = False
    
    def initialize(self) -> None:
        """Initialize pool."""
        with self._lock:
            for _ in range(self._min_size):
                try:
                    conn = PooledConnection(connection=self._create())
                    self._pool.append(conn)
                    self._total += 1
                    self._stats.total += 1
                except Exception:
                    pass
    
    def acquire(self) -> T:
        """Acquire connection."""
        deadline = time.time() + self._acquire_timeout
        
        with self._available:
            while True:
                # Try pool
                while self._pool:
                    pooled = self._pool.popleft()
                    
                    if self._is_valid(pooled):
                        pooled.touch()
                        self._in_use += 1
                        self._stats.hits += 1
                        return pooled.connection
                    else:
                        self._close_conn(pooled)
                
                # Create new
                if self._total < self._max_size:
                    connection = self._create()
                    self._total += 1
                    self._stats.total += 1
                    self._stats.misses += 1
                    self._in_use += 1
                    return connection
                
                # Wait
                timeout = deadline - time.time()
                if timeout <= 0:
                    self._stats.timeouts += 1
                    raise TimeoutError("Pool acquire timeout")
                
                self._stats.waiting += 1
                self._available.wait(timeout)
                self._stats.waiting -= 1
    
    def release(self, connection: T) -> None:
        """Release connection."""
        with self._available:
            self._in_use -= 1
            
            pooled = PooledConnection(connection=connection)
            
            if not self._closed and self._is_valid(pooled):
                self._pool.append(pooled)
            else:
                self._close_conn(pooled)
            
            self._available.notify()
    
    def _is_valid(self, pooled: PooledConnection[T]) -> bool:
        """Check if connection is valid."""
        if pooled.age > self._max_lifetime:
            return False
        if pooled.idle_time > self._max_idle_time:
            return False
        if self._validate:
            return self._validate(pooled.connection)
        return True
    
    def _close_conn(self, pooled: PooledConnection[T]) -> None:
        """Close connection."""
        self._total -= 1
        if self._close:
            self._close(pooled.connection)
    
    def close(self) -> None:
        """Close pool."""
        with self._lock:
            self._closed = True
            while self._pool:
                pooled = self._pool.popleft()
                self._close_conn(pooled)


# Native implementation placeholder
"""
// C++ Native Implementation (pool.cpp)

#include <deque>
#include <mutex>
#include <condition_variable>
#include <atomic>
#include <chrono>

namespace nexaweb {

template<typename T>
struct PooledConnection {
    T* connection;
    std::chrono::steady_clock::time_point created_at;
    std::chrono::steady_clock::time_point last_used_at;
    std::atomic<uint32_t> use_count{0};
};

template<typename T>
class NativePool {
public:
    using CreateFunc = std::function<T*()>;
    using CloseFunc = std::function<void(T*)>;
    using ValidateFunc = std::function<bool(T*)>;
    
    NativePool(CreateFunc create, CloseFunc close, ValidateFunc validate,
               size_t min_size, size_t max_size);
    
    // Lock-free acquire attempt
    PooledConnection<T>* try_acquire();
    
    // Blocking acquire with timeout
    PooledConnection<T>* acquire(std::chrono::milliseconds timeout);
    
    // Release back to pool
    void release(PooledConnection<T>* conn);
    
    void close();
    
private:
    std::deque<PooledConnection<T>*> pool_;
    std::mutex mutex_;
    std::condition_variable available_;
    
    std::atomic<size_t> total_{0};
    std::atomic<size_t> in_use_{0};
    
    CreateFunc create_;
    CloseFunc close_;
    ValidateFunc validate_;
};

}  // namespace nexaweb
"""
