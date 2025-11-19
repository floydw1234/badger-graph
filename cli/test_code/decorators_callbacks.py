"""
Test file demonstrating decorators, callbacks, and higher-order functions.
"""

from functools import wraps
from typing import Callable, Any
import time

# Decorator that modifies function behavior
def timing_decorator(func: Callable) -> Callable:
    """Decorator to time function execution."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"{func.__name__} took {end - start:.4f} seconds")
        return result
    return wrapper

# Decorator with arguments
def retry(max_attempts: int = 3):
    """Decorator factory for retry logic."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    print(f"Attempt {attempt + 1} failed: {e}")
            return None
        return wrapper
    return decorator

# Class decorator
def register_handler(handler_type: str):
    """Register a handler function."""
    handlers = {}
    def decorator(func: Callable):
        handlers[handler_type] = func
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        wrapper.handlers = handlers
        return wrapper
    return decorator

@timing_decorator
def compute_factorial(n: int) -> int:
    """Compute factorial with timing."""
    if n <= 1:
        return 1
    return n * compute_factorial(n - 1)

@retry(max_attempts=3)
def risky_operation(value: int) -> int:
    """Operation that might fail."""
    if value < 0:
        raise ValueError("Value must be positive")
    return value * 2

@register_handler("user_created")
def handle_user_created(user_id: int) -> None:
    """Handle user creation event."""
    print(f"User {user_id} was created")

def apply_callback(data: list, callback: Callable) -> list:
    """Apply callback to each item in data."""
    return [callback(item) for item in data]

def create_multiplier(factor: int) -> Callable:
    """Create a multiplier function."""
    def multiply(x: int) -> int:
        return x * factor
    return multiply

def chain_callbacks(*callbacks: Callable) -> Callable:
    """Chain multiple callbacks together."""
    def chained(x: Any) -> Any:
        result = x
        for callback in callbacks:
            result = callback(result)
        return result
    return chained

class EventEmitter:
    """Simple event emitter with callbacks."""
    
    def __init__(self):
        self.listeners = {}
    
    def on(self, event: str, callback: Callable) -> None:
        """Register event listener."""
        if event not in self.listeners:
            self.listeners[event] = []
        self.listeners[event].append(callback)
    
    def emit(self, event: str, *args, **kwargs) -> None:
        """Emit event and call all listeners."""
        if event in self.listeners:
            for callback in self.listeners[event]:
                callback(*args, **kwargs)

def main():
    """Test decorators and callbacks."""
    # Decorated function calls
    result1 = compute_factorial(5)
    print(f"Factorial result: {result1}")
    
    # Retry decorator
    try:
        result2 = risky_operation(10)
        print(f"Risky operation result: {result2}")
    except ValueError as e:
        print(f"Error: {e}")
    
    # Callback usage
    numbers = [1, 2, 3, 4, 5]
    doubled = apply_callback(numbers, lambda x: x * 2)
    print(f"Doubled: {doubled}")
    
    # Higher-order function
    triple = create_multiplier(3)
    tripled = apply_callback(numbers, triple)
    print(f"Tripled: {tripled}")
    
    # Chained callbacks
    transform = chain_callbacks(
        lambda x: x + 1,
        lambda x: x * 2,
        lambda x: x - 1
    )
    transformed = apply_callback(numbers, transform)
    print(f"Transformed: {transformed}")
    
    # Event emitter with callbacks
    emitter = EventEmitter()
    emitter.on("test", lambda x: print(f"Event received: {x}"))
    emitter.on("test", lambda x: print(f"Another listener: {x}"))
    emitter.emit("test", "Hello World")
    
    # Handler decorator
    handle_user_created(123)

if __name__ == "__main__":
    main()


