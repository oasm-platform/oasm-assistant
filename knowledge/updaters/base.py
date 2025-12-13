"""
Base abstract class for all knowledge base updaters using AsyncIO
"""
import asyncio
from abc import ABC, abstractmethod
from typing import Optional
from common.logger import logger

class BaseUpdater(ABC):
    """
    Abstract base class that handles asyncio tasks and lifecycle management.
    """

    def __init__(self, name: str, interval_seconds: int = 60):
        """
        Initialize the base updater
        
        Args:
            name: Name of the updater (for logging)
            interval_seconds: How often to run the check loop (default 60s)
        """
        self.name = name
        self.interval_seconds = interval_seconds
        self.running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the updater loop as an asyncio task"""
        if self.running:
            logger.warning(f"{self.name} is already running")
            return

        self.running = True
        # Schedule the loop in the event loop
        self._task = asyncio.create_task(self._run_loop())
        logger.debug(f"{self.name} started (AsyncIO)")

    async def stop(self):
        """Stop the updater loop"""
        if not self.running:
            return

        self.running = False
        if self._task:
            logger.info(f"Stopping {self.name}...")
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass # Task cancellation is expected
        logger.info(f"{self.name} stopped")

    async def _run_loop(self):
        """Internal async loop"""
        logger.debug(f"{self.name} loop running (interval: {self.interval_seconds}s)")
        
        while self.running:
            try:
                # Call the concrete implementation
                # We await it because it might perform async I/O
                await self.update_logic()
                
            except asyncio.CancelledError:
                # Loop was cancelled, exit gracefully
                break
            except Exception as e:
                logger.error(f"Error in {self.name} loop: {e}")
            
            # Async sleep
            try:
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break

    @abstractmethod
    async def update_logic(self):
        """
        Concrete classes must implement this async method.
        """
        pass
