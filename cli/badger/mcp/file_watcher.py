"""File watcher for monitoring workspace changes."""

import asyncio
import logging
from pathlib import Path
from typing import Callable, Optional, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

logger = logging.getLogger(__name__)


class FileWatcherHandler(FileSystemEventHandler):
    """Handler for file system events with debouncing."""
    
    def __init__(
        self,
        workspace_path: Path,
        callback: Callable[[Set[Path]], None],
        debounce_seconds: float = 10.0,
        event_loop: Optional[asyncio.AbstractEventLoop] = None
    ):
        """Initialize file watcher handler.
        
        Args:
            workspace_path: Path to workspace root (only files in this directory are watched)
            callback: Async callback function that receives set of changed file paths
            debounce_seconds: Delay in seconds before triggering callback (default: 10.0)
            event_loop: Event loop to schedule callbacks on (required for async callbacks)
        """
        self.workspace_path = workspace_path.resolve()
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self.event_loop = event_loop
        
        # Track pending file changes
        self.pending_changes: Set[Path] = set()
        self.debounce_task: Optional[asyncio.Task] = None
        self.debounce_timer: Optional[asyncio.TimerHandle] = None
        
        # Source file extensions to watch
        self.source_extensions = {'.py', '.c', '.h', '.cpp', '.hpp', '.cc', '.cxx', '.hxx'}
    
    def _is_source_file(self, file_path: Path) -> bool:
        """Check if file is a source file we should watch."""
        return file_path.suffix.lower() in self.source_extensions
    
    def _is_in_workspace(self, file_path: Path) -> bool:
        """Check if file is within the workspace directory."""
        try:
            resolved = file_path.resolve()
            return resolved.is_relative_to(self.workspace_path)
        except (ValueError, RuntimeError):
            return False
    
    def _schedule_callback(self):
        """Schedule the debounced callback."""
        if not self.event_loop:
            logger.warning("No event loop provided, cannot schedule async callback")
            return
        
        # Cancel existing task if any
        if self.debounce_task and not self.debounce_task.done():
            self.debounce_task.cancel()
        
        # Schedule new callback after debounce delay
        async def debounced_callback():
            try:
                await asyncio.sleep(self.debounce_seconds)
                if self.pending_changes:
                    changes = self.pending_changes.copy()
                    self.pending_changes.clear()
                    logger.info(f"File changes detected: {len(changes)} files changed")
                    await self.callback(changes)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error in file watcher callback: {e}", exc_info=True)
        
        # Schedule on the event loop (may be called from watchdog thread)
        self.debounce_task = asyncio.run_coroutine_threadsafe(
            debounced_callback(),
            self.event_loop
        )
    
    def on_modified(self, event: FileSystemEvent):
        """Handle file modification events."""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        if self._is_source_file(file_path) and self._is_in_workspace(file_path):
            self.pending_changes.add(file_path)
            logger.debug(f"File modified: {file_path}")
            self._schedule_callback()
    
    def on_created(self, event: FileSystemEvent):
        """Handle file creation events."""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        if self._is_source_file(file_path) and self._is_in_workspace(file_path):
            self.pending_changes.add(file_path)
            logger.debug(f"File created: {file_path}")
            self._schedule_callback()
    
    def on_deleted(self, event: FileSystemEvent):
        """Handle file deletion events."""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        if self._is_source_file(file_path) and self._is_in_workspace(file_path):
            self.pending_changes.add(file_path)
            logger.debug(f"File deleted: {file_path}")
            self._schedule_callback()


class FileWatcher:
    """File watcher for monitoring workspace file changes."""
    
    def __init__(
        self,
        workspace_path: Path,
        callback: Callable[[Set[Path]], None],
        debounce_seconds: float = 10.0,
        event_loop: Optional[asyncio.AbstractEventLoop] = None
    ):
        """Initialize file watcher.
        
        Args:
            workspace_path: Path to workspace root to watch
            callback: Async callback function that receives set of changed file paths
            debounce_seconds: Delay in seconds before triggering callback (default: 10.0)
            event_loop: Event loop to schedule callbacks on (required for async callbacks)
        """
        self.workspace_path = workspace_path.resolve()
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self.event_loop = event_loop
        
        self.observer: Optional[Observer] = None
        self.handler: Optional[FileWatcherHandler] = None
    
    def start(self):
        """Start watching for file changes."""
        if self.observer and self.observer.is_alive():
            logger.warning("File watcher already running")
            return
        
        self.handler = FileWatcherHandler(
            self.workspace_path,
            self.callback,
            self.debounce_seconds,
            event_loop=self.event_loop
        )
        
        self.observer = Observer()
        self.observer.schedule(
            self.handler,
            str(self.workspace_path),
            recursive=True
        )
        self.observer.start()
        logger.info(f"File watcher started for workspace: {self.workspace_path}")
    
    def stop(self):
        """Stop watching for file changes."""
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5.0)
            logger.info("File watcher stopped")
    
    def is_running(self) -> bool:
        """Check if watcher is running."""
        return self.observer is not None and self.observer.is_alive()

