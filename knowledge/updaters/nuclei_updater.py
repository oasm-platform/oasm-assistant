"""
Updater service for syncing Nuclei templates from GitHub repository
"""
import yaml
import asyncio
from datetime import datetime
from typing import Optional
from pathlib import Path

from .base import BaseUpdater

from common.logger import logger
from common.config import configs
from common.utils.git import clone_or_pull_repo
from common.utils.cron import is_cron_match
from data.database import postgres_db
from data.database.models import NucleiTemplates
from data.embeddings import embeddings_manager
from data.redis import redis_client
from sqlalchemy import delete, text


class NucleiTemplatesUpdater(BaseUpdater):
    """Updater for periodic Nuclei templates synchronization"""


    def __init__(self):
        """Initialize the updater"""
        # Initialize BaseUpdater with name and 60s interval
        super().__init__(name="NucleiTemplatesUpdater", interval_seconds=60)
        
        self.repo_url = configs.scheduler.nuclei_templates_repo_url
        self.clone_dir = configs.scheduler.nuclei_templates_clone_dir
        self.sync_time = configs.scheduler.nuclei_templates_sync_time

        # Use shared singleton embedding model
        self.embeddings_manager = embeddings_manager
        
        # Flag to track if we've performed the startup check
        self._startup_check_done = False

    async def _ensure_tsv_column(self):
        """Ensure tsv column and index exist for full-text search"""
        try:
            async with postgres_db.get_session() as session:
                check_column = text("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'nuclei_templates' AND column_name = 'tsv'
                """)
                result = await session.execute(check_column)
                if not result.fetchone():
                    logger.info("Creating tsv column for full-text search...")
                    await session.execute(text("""
                        ALTER TABLE nuclei_templates
                        ADD COLUMN tsv tsvector
                        GENERATED ALWAYS AS (
                            setweight(to_tsvector('english', COALESCE(name, '')), 'A') ||
                            setweight(to_tsvector('english', COALESCE(description, '')), 'B')
                        ) STORED
                    """))
                    await session.execute(text("""
                        CREATE INDEX IF NOT EXISTS nuclei_templates_tsv_idx
                        ON nuclei_templates USING GIN (tsv)
                    """))
                    await session.commit()
        except Exception as e:
            logger.warning(f"Could not ensure TSV column: {e}")

    async def _has_templates(self) -> bool:
        """Check if any templates exist in the database"""
        try:
            from sqlalchemy import select
            async with postgres_db.get_session() as session:
                result = await session.execute(select(NucleiTemplates).limit(1))
                return result.scalars().first() is not None
        except Exception as e:
            logger.error(f"Error checking template existence: {e}")
            return False

    async def sync_templates(self):
        """Execute the full sync process"""
        try:
            self.embeddings_manager = embeddings_manager # Reload to ensure init

            # Step 1: Clone or pull repo 
            # (Run Git operations in thread pool to avoid blocking async loop)
            loop = asyncio.get_running_loop()
            success = await loop.run_in_executor(
                None, 
                clone_or_pull_repo, 
                self.repo_url, 
                self.clone_dir
            )
            
            if not success:
                logger.error("Failed to clone/pull repository")
                return

            # Step 2 & 3: Clear DB and Sync
            await self._clear_database()
            await self._sync_templates_to_database()
            
        except Exception as e:
            logger.error(f"Sync error: {e}", exc_info=True)

    async def _clear_database(self):
        """Clear all existing Nuclei templates from database"""
        try:
            async with postgres_db.get_session() as session:
                await session.execute(delete(NucleiTemplates))
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to clear database: {e}")
            raise

    async def _sync_templates_to_database(self) -> int:
        """Sync templates from cloned repository to database"""
        count = 0
        templates_dir = Path(self.clone_dir)
        yaml_files = list(templates_dir.rglob("*.yaml"))
        logger.info(f"Found {len(yaml_files)} template files")

        batch_size = 50
        batch_data = []

        # We can still run CPU bound parsing in sync, effectively blocking slightly 
        # but better than overhead of 12000 tasks.
        # Alternatively, yield to loop occasionally.
        
        for idx, yaml_file in enumerate(yaml_files):
            try:
                # 1. Parse (Sync CPU)
                data = self._parse_template_file(yaml_file)
                if not data: continue

                # Basic data cleanup
                clean = lambda t: t.replace('\x00', '') if t and isinstance(t, str) else ""
                name = clean(data['name'])
                desc = clean(data['description'])
                content = clean(data['template'])
                meta = data['metadata']

                # 2. Embedding (Async)
                text_to_embed = f"Template: {name} Purpose: {desc}"
                if 'tags' in meta: text_to_embed += f" Tags: {meta['tags']}"
                
                # Use async embedding generation
                embedding = await self.embeddings_manager.generate_embedding_async(text_to_embed)

                batch_data.append({
                    'name': name[:255],
                    'description': desc,
                    'template': content,
                    'embedding': embedding
                })

                if len(batch_data) >= batch_size:
                    await self._insert_batch(batch_data)
                    count += len(batch_data)
                    batch_data = []
                    
                    # Yield to event loop every batch to keep heartbeat alive
                    await asyncio.sleep(0.01)

            except Exception:
                continue

        if batch_data:
            await self._insert_batch(batch_data)
            count += len(batch_data)

        logger.info(f"Synced {count} templates")
        return count

    async def _insert_batch(self, batch_data: list):
        """Insert batch to DB"""
        try:
            async with postgres_db.get_session() as session:
                for data in batch_data:
                    session.add(NucleiTemplates(**data))
                await session.commit()
        except:
            pass

    async def update_logic(self):
        """
        Check cron schedule and run sync if needed.
        Also check for initial empty DB on startup.
        """
        # Ensure Schema on first run
        if not self._startup_check_done:
             await self._ensure_tsv_column()

        needs_sync = False
        sync_reason = ""

        # 1. Startup Check: If DB is empty, sync immediately
        if not self._startup_check_done:
            self._startup_check_done = True 
            
            has_templates = await self._has_templates()
            
            if not has_templates:
                logger.info("Startup check: Database is empty. Scheduling immediate sync.")
                needs_sync = True
                sync_reason = "Startup (Empty Database)"

        # 2. Cron Check
        if not needs_sync and is_cron_match(self.sync_time):
            needs_sync = True
            sync_reason = "Cron Schedule"

        if needs_sync:
            lock_key = "nuclei-scheduler"
            
            # Try to acquire lock via ASYNC redis
            acquired = await redis_client.async_client.set(lock_key, "locked", nx=True, ex=600)
            
            if acquired:
                logger.info(f"Acquired lock {lock_key}, starting sync (Reason: {sync_reason})...")
                # Run ASYNC sync
                await self.sync_templates()
            else:
                pass

