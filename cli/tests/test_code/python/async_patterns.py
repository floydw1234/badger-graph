"""
Test file demonstrating async/await patterns and async function calls.
"""

import asyncio
from typing import List, Coroutine
from functools import partial

async def fetch_data_async(url: str) -> dict:
    """Simulate async data fetching."""
    await asyncio.sleep(0.1)  # Simulate network delay
    return {"url": url, "data": f"Data from {url}"}

async def process_item(item: int) -> int:
    """Process a single item asynchronously."""
    await asyncio.sleep(0.01)
    return item * 2

async def batch_process(items: List[int]) -> List[int]:
    """Process multiple items concurrently."""
    tasks = [process_item(item) for item in items]
    results = await asyncio.gather(*tasks)
    return results

async def chain_async_operations(value: int) -> int:
    """Chain multiple async operations."""
    result = await fetch_data_async(f"http://example.com/{value}")
    processed = await process_item(value)
    return processed

class AsyncService:
    """Service with async methods."""
    
    async def initialize(self) -> None:
        """Initialize service asynchronously."""
        await asyncio.sleep(0.1)
        self.initialized = True
    
    async def get_data(self, key: str) -> str:
        """Get data asynchronously."""
        await asyncio.sleep(0.05)
        return f"Data for {key}"
    
    async def save_data(self, key: str, value: str) -> bool:
        """Save data asynchronously."""
        await asyncio.sleep(0.05)
        return True

def sync_wrapper(coro: Coroutine):
    """Wrap async function for sync execution."""
    return asyncio.run(coro)

def create_async_task(coro: Coroutine):
    """Create and return async task."""
    return asyncio.create_task(coro)

async def main_async():
    """Main async function."""
    # Direct async calls
    data1 = await fetch_data_async("http://api.example.com/users")
    print(f"Fetched: {data1}")
    
    # Batch processing
    items = [1, 2, 3, 4, 5]
    results = await batch_process(items)
    print(f"Processed: {results}")
    
    # Chained operations
    result = await chain_async_operations(42)
    print(f"Chained result: {result}")
    
    # Async service
    service = AsyncService()
    await service.initialize()
    data = await service.get_data("user:123")
    saved = await service.save_data("user:123", "new_data")
    print(f"Service data: {data}, Saved: {saved}")
    
    # Multiple concurrent operations
    tasks = [
        fetch_data_async("http://api1.com"),
        fetch_data_async("http://api2.com"),
        fetch_data_async("http://api3.com")
    ]
    all_data = await asyncio.gather(*tasks)
    print(f"All data: {all_data}")

def main():
    """Entry point that runs async code."""
    # Run async main
    asyncio.run(main_async())
    
    # Sync wrapper usage
    result = sync_wrapper(fetch_data_async("http://wrapped.com"))
    print(f"Wrapped result: {result}")

if __name__ == "__main__":
    main()

