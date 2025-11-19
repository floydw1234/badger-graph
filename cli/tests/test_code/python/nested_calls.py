"""
Test file demonstrating nested function calls and method chaining.
"""

from functools import reduce
from operator import add, mul
from typing import List, Callable

def square(x: int) -> int:
    """Square a number."""
    return x * x

def double(x: int) -> int:
    """Double a number."""
    return x * 2

def compose(*functions: Callable) -> Callable:
    """Compose multiple functions."""
    def composed(x):
        result = x
        for func in reversed(functions):
            result = func(result)
        return result
    return composed

class DataProcessor:
    """Process data with method chaining."""
    
    def __init__(self, data: List[int]):
        self.data = data
        self.operations = []
    
    def filter(self, predicate: Callable) -> 'DataProcessor':
        """Filter data."""
        self.data = [x for x in self.data if predicate(x)]
        self.operations.append("filter")
        return self
    
    def map(self, func: Callable) -> 'DataProcessor':
        """Map function over data."""
        self.data = [func(x) for x in self.data]
        self.operations.append("map")
        return self
    
    def reduce(self, func: Callable, initial: int = 0) -> int:
        """Reduce data."""
        return reduce(func, self.data, initial)
    
    def get(self) -> List[int]:
        """Get processed data."""
        return self.data

def process_numbers(numbers: List[int]) -> int:
    """Process numbers through multiple transformations."""
    # Deeply nested function calls
    result = reduce(
        add,
        map(
            double,
            filter(
                lambda x: x > 0,
                map(square, numbers)
            )
        ),
        0
    )
    return result

def chain_operations(data: List[int]) -> int:
    """Chain operations using method chaining."""
    processor = DataProcessor(data)
    result = processor \
        .filter(lambda x: x % 2 == 0) \
        .map(square) \
        .map(double) \
        .reduce(add, 0)
    return result

def nested_composition(x: int) -> int:
    """Use function composition."""
    # Compose functions and call
    transform = compose(double, square, double)
    return transform(x)

def call_with_args(func: Callable, *args, **kwargs):
    """Call a function with arguments."""
    return func(*args, **kwargs)

def main():
    """Test nested calls."""
    numbers = [1, 2, 3, 4, 5, -1, -2]
    
    # Nested calls
    result1 = process_numbers(numbers)
    print(f"Nested calls result: {result1}")
    
    # Method chaining
    result2 = chain_operations(numbers)
    print(f"Chained operations result: {result2}")
    
    # Function composition
    result3 = nested_composition(5)
    print(f"Composition result: {result3}")
    
    # Call function through variable
    func_var = square
    result4 = call_with_args(func_var, 7)
    print(f"Indirect call result: {result4}")
    
    # Multiple levels of nesting
    result5 = call_with_args(
        compose,
        double,
        square,
        lambda x: x + 1
    )(10)
    print(f"Deep nesting result: {result5}")

if __name__ == "__main__":
    main()

