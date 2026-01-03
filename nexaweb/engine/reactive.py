"""
NexaWeb Reactive System
=======================

State management and reactivity for NexaWeb applications.
Provides reactive primitives that automatically track dependencies
and trigger updates when values change.

Features:
- State: Reactive state container
- Computed: Derived values with automatic caching
- Effect: Side effects that run when dependencies change
- Watch: Observe state changes

This is the server-side reactivity system. For client-side reactivity,
NexaWeb generates minimal JavaScript that hydrates server-rendered HTML.

Example:
    from nexaweb.engine.reactive import State, Computed, Effect
    
    count = State(0)
    doubled = Computed(lambda: count.value * 2)
    
    @Effect
    def log_changes():
        print(f"Count: {count.value}, Doubled: {doubled.value}")
    
    count.value = 5  # Triggers effect: "Count: 5, Doubled: 10"
"""

from __future__ import annotations

import asyncio
import weakref
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    TypeVar,
    Union,
)

T = TypeVar("T")


# Global tracking context
_current_effect: Optional["Effect"] = None
_batch_depth: int = 0
_pending_effects: Set["Effect"] = set()


def _get_current_effect() -> Optional["Effect"]:
    """Get the currently running effect for dependency tracking."""
    return _current_effect


def _set_current_effect(effect: Optional["Effect"]) -> None:
    """Set the currently running effect."""
    global _current_effect
    _current_effect = effect


class State(Generic[T]):
    """
    Reactive state container.
    
    Wraps a value and tracks dependencies. When the value changes,
    all dependent computeds and effects are notified.
    
    Example:
        name = State("World")
        print(name.value)  # "World"
        
        name.value = "NexaWeb"  # Triggers updates
    """
    
    __slots__ = ("_value", "_subscribers", "_name")
    
    def __init__(self, initial: T, name: str = "") -> None:
        """
        Create reactive state.
        
        Args:
            initial: Initial value
            name: Optional name for debugging
        """
        self._value = initial
        self._subscribers: Set[weakref.ref] = set()
        self._name = name
        
    @property
    def value(self) -> T:
        """Get current value, tracking as dependency."""
        effect = _get_current_effect()
        if effect is not None:
            self._track(effect)
        return self._value
        
    @value.setter
    def value(self, new_value: T) -> None:
        """Set value and trigger updates."""
        if self._value != new_value:
            self._value = new_value
            self._trigger()
            
    def _track(self, effect: "Effect") -> None:
        """Track effect as subscriber."""
        self._subscribers.add(weakref.ref(effect))
        effect._dependencies.add(self)
        
    def _trigger(self) -> None:
        """Notify all subscribers of change."""
        global _batch_depth, _pending_effects
        
        # Clean up dead refs and get live effects
        live_effects: List[Effect] = []
        dead_refs: List[weakref.ref] = []
        
        for ref in self._subscribers:
            effect = ref()
            if effect is not None:
                live_effects.append(effect)
            else:
                dead_refs.append(ref)
                
        # Remove dead refs
        for ref in dead_refs:
            self._subscribers.discard(ref)
            
        # Schedule or run effects
        if _batch_depth > 0:
            _pending_effects.update(live_effects)
        else:
            for effect in live_effects:
                effect._run()
                
    def peek(self) -> T:
        """Get value without tracking dependency."""
        return self._value
        
    def update(self, fn: Callable[[T], T]) -> None:
        """Update value using function."""
        self.value = fn(self._value)
        
    def __repr__(self) -> str:
        name = f" {self._name}" if self._name else ""
        return f"<State{name}: {self._value!r}>"


class Computed(Generic[T]):
    """
    Computed value that derives from reactive state.
    
    Automatically recalculates when dependencies change.
    Results are cached until dependencies change.
    
    Example:
        count = State(5)
        doubled = Computed(lambda: count.value * 2)
        
        print(doubled.value)  # 10
        count.value = 10
        print(doubled.value)  # 20
    """
    
    __slots__ = ("_fn", "_value", "_dirty", "_dependencies", "_name")
    
    def __init__(
        self,
        fn: Callable[[], T],
        name: str = "",
    ) -> None:
        """
        Create computed value.
        
        Args:
            fn: Function that computes the value
            name: Optional name for debugging
        """
        self._fn = fn
        self._value: Optional[T] = None
        self._dirty = True
        self._dependencies: Set[State] = set()
        self._name = name
        
    @property
    def value(self) -> T:
        """Get computed value, recalculating if dirty."""
        if self._dirty:
            self._compute()
        return self._value  # type: ignore
        
    def _compute(self) -> None:
        """Recalculate the computed value."""
        # Clear old dependencies
        self._dependencies.clear()
        
        # Track this computed as current effect
        old_effect = _get_current_effect()
        
        # Create a temporary effect for tracking
        class ComputedEffect:
            _dependencies: Set[State] = set()
            
        temp_effect = ComputedEffect()
        _set_current_effect(temp_effect)  # type: ignore
        
        try:
            self._value = self._fn()
            self._dirty = False
            
            # Copy tracked dependencies
            self._dependencies = temp_effect._dependencies.copy()
            
        finally:
            _set_current_effect(old_effect)
            
    def _invalidate(self) -> None:
        """Mark computed as dirty."""
        self._dirty = True
        
    def __repr__(self) -> str:
        name = f" {self._name}" if self._name else ""
        return f"<Computed{name}: {self._value!r}>"


class Effect:
    """
    Side effect that runs when dependencies change.
    
    Effects automatically track which reactive values they read
    and re-run when any of those values change.
    
    Example:
        count = State(0)
        
        @Effect
        def log_count():
            print(f"Count is: {count.value}")
        
        count.value = 5  # Prints: "Count is: 5"
    """
    
    __slots__ = ("_fn", "_dependencies", "_active", "_name")
    
    def __init__(
        self,
        fn: Callable[[], Any],
        name: str = "",
    ) -> None:
        """
        Create effect.
        
        Args:
            fn: Effect function
            name: Optional name for debugging
        """
        self._fn = fn
        self._dependencies: Set[State] = set()
        self._active = True
        self._name = name
        
        # Run immediately to collect dependencies
        self._run()
        
    def _run(self) -> None:
        """Execute the effect."""
        if not self._active:
            return
            
        # Clear old dependencies
        for dep in self._dependencies:
            dep._subscribers.discard(weakref.ref(self))
        self._dependencies.clear()
        
        # Track dependencies during execution
        old_effect = _get_current_effect()
        _set_current_effect(self)
        
        try:
            self._fn()
        finally:
            _set_current_effect(old_effect)
            
    def stop(self) -> None:
        """Stop the effect from running."""
        self._active = False
        for dep in self._dependencies:
            dep._subscribers.discard(weakref.ref(self))
        self._dependencies.clear()
        
    def __repr__(self) -> str:
        name = f" {self._name}" if self._name else ""
        status = "active" if self._active else "stopped"
        return f"<Effect{name} ({status})>"


def effect(fn: Callable[[], Any]) -> Effect:
    """
    Decorator to create an effect.
    
    Example:
        @effect
        def auto_save():
            save_to_disk(document.value)
    """
    return Effect(fn)


class Watch:
    """
    Watch a specific reactive value for changes.
    
    Unlike Effect, Watch only observes specific values
    and receives both old and new values in callback.
    
    Example:
        count = State(0)
        
        @Watch(count)
        def on_count_change(new_val, old_val):
            print(f"Count changed from {old_val} to {new_val}")
    """
    
    def __init__(
        self,
        source: Union[State, Computed],
        callback: Optional[Callable[[Any, Any], Any]] = None,
        immediate: bool = False,
    ) -> None:
        """
        Create watcher.
        
        Args:
            source: Reactive value to watch
            callback: Function called on change
            immediate: Whether to call callback immediately
        """
        self._source = source
        self._callback = callback
        self._old_value = source.peek() if isinstance(source, State) else source.value
        
        if immediate and callback:
            callback(self._old_value, None)
            
    def __call__(self, fn: Callable[[Any, Any], Any]) -> "Watch":
        """Use as decorator."""
        self._callback = fn
        
        # Create effect to watch for changes
        @effect
        def watcher():
            new_value = self._source.value
            if new_value != self._old_value:
                if self._callback:
                    self._callback(new_value, self._old_value)
                self._old_value = new_value
                
        return self


def batch(fn: Callable[[], Any]) -> Any:
    """
    Batch multiple state updates into single update cycle.
    
    Prevents effects from running multiple times when
    updating multiple related state values.
    
    Example:
        @batch
        def update_user():
            name.value = "John"
            age.value = 30
            email.value = "john@example.com"
        # Effects only run once after all updates
    """
    global _batch_depth, _pending_effects
    
    _batch_depth += 1
    try:
        result = fn()
    finally:
        _batch_depth -= 1
        
        if _batch_depth == 0:
            # Run all pending effects
            effects = _pending_effects.copy()
            _pending_effects.clear()
            
            for eff in effects:
                eff._run()
                
    return result


def reactive(obj: Dict[str, Any]) -> Dict[str, State]:
    """
    Create reactive object from dictionary.
    
    Converts all values to State objects.
    
    Example:
        user = reactive({
            "name": "John",
            "age": 30,
        })
        
        print(user["name"].value)  # "John"
        user["age"].value = 31
    """
    return {key: State(value, name=key) for key, value in obj.items()}


@dataclass
class Store:
    """
    Centralized state store with actions.
    
    Provides Redux-like state management with:
    - Centralized state
    - Actions to modify state
    - Computed getters
    - Subscription to changes
    
    Example:
        store = Store(
            state={"count": 0},
            getters={
                "doubled": lambda s: s["count"].value * 2,
            },
            actions={
                "increment": lambda s: s["count"].update(lambda x: x + 1),
            },
        )
        
        store.dispatch("increment")
        print(store.get("doubled"))  # 2
    """
    
    state: Dict[str, State] = field(default_factory=dict)
    getters: Dict[str, Callable] = field(default_factory=dict)
    actions: Dict[str, Callable] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        # Convert state dict to reactive
        if not all(isinstance(v, State) for v in self.state.values()):
            self.state = reactive(self.state)
            
    def get(self, key: str) -> Any:
        """Get state value or getter result."""
        if key in self.getters:
            return self.getters[key](self.state)
        if key in self.state:
            return self.state[key].value
        raise KeyError(f"Unknown key: {key}")
        
    def dispatch(self, action: str, *args: Any, **kwargs: Any) -> Any:
        """Dispatch an action."""
        if action not in self.actions:
            raise KeyError(f"Unknown action: {action}")
        return self.actions[action](self.state, *args, **kwargs)
        
    def subscribe(self, key: str, callback: Callable[[Any, Any], Any]) -> Watch:
        """Subscribe to state changes."""
        if key not in self.state:
            raise KeyError(f"Unknown state key: {key}")
        return Watch(self.state[key], callback)


class AsyncState(State[T]):
    """
    Async-aware state that can handle async updates.
    
    Example:
        data = AsyncState(None)
        
        async def fetch_data():
            result = await api.fetch()
            await data.set_async(result)
    """
    
    async def set_async(self, value: T) -> None:
        """Set value asynchronously."""
        self.value = value
        
    async def update_async(self, fn: Callable[[T], T]) -> None:
        """Update value asynchronously."""
        new_value = fn(self._value)
        if asyncio.iscoroutine(new_value):
            new_value = await new_value
        self.value = new_value
