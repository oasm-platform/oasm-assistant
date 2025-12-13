"""
Central auto-updater service for managing all knowledge base updaters
"""
import asyncio
from typing import List, Optional
from common.logger import logger
from .nuclei_updater import NucleiTemplatesUpdater

class KnowledgeBaseUpdater:
    """Central manager for all knowledge base updaters"""
    
    def __init__(self):
        # Register all updaters here
        self.updaters = [
            NucleiTemplatesUpdater()
        ]
        self.running = False
        logger.info(f"KnowledgeBaseUpdater initialized with {len(self.updaters)} updaters")

    async def start(self):
        """Start all registered updaters"""
        if self.running:
            logger.warning("KnowledgeBaseUpdater is already running")
            return
            
        logger.info("Starting Knowledge Base Updaters (AsyncIO)...")
        for updater in self.updaters:
            try:
                # Call async start
                await updater.start()
            except Exception as e:
                logger.error(f"Failed to start updater {updater.__class__.__name__}: {e}")
        
        self.running = True

    async def stop(self):
        """Stop all registered updaters"""
        if not self.running:
            return
            
        logger.info("Stopping Knowledge Base Updaters...")
        for updater in self.updaters:
            try:
                # Call async stop
                await updater.stop()
            except Exception as e:
                logger.error(f"Failed to stop updater {updater.__class__.__name__}: {e}")
        
        self.running = False

# Global singleton instance
_kb_updater_instance: Optional[KnowledgeBaseUpdater] = None

def get_kb_updater() -> KnowledgeBaseUpdater:
    """Get or create the global KnowledgeBaseUpdater instance"""
    global _kb_updater_instance
    if _kb_updater_instance is None:
        _kb_updater_instance = KnowledgeBaseUpdater()
    return _kb_updater_instance
