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

        # Ensure TSV column and index exist for hybrid search
        self._ensure_tsv_column()

        logger.info(f"NucleiTemplatesUpdater initialized with sync time: {self.sync_time}")

    async def update_logic(self):
        """
        Check cron schedule and run sync if needed.
        """
        # Use common utility for cron check
        if is_cron_match(self.sync_time):
            # Create a lock key
            lock_key = "nuclei-scheduler"
            
            # Try to acquire lock via ASYNC redis
            # Expire in 5 minutes (300s) to prevent overlapping runs
            acquired = await redis_client.async_client.set(lock_key, "locked", nx=True, ex=300)
            
            if acquired:
                logger.info(f"Acquired lock {lock_key}, starting sync...")
                
                # Execute heavy blocking task in a separate thread
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self.sync_templates)
            else:
                pass # Silent wait

    def sync_templates(self):
        """Execute the full sync process"""
        try:
            # Step 1: Clone or pull repo using common utility
            success = clone_or_pull_repo(self.repo_url, self.clone_dir)
            if not success:
                logger.error("Failed to clone/pull repository via common utility")
                return

            # Step 2 & 3: Clear DB and Sync
            self._clear_database()
            self._sync_templates_to_database()
            
        except Exception as e:
            logger.error(f"Sync error: {e}")

    def _ensure_tsv_column(self):
        """Ensure tsv column and index exist for full-text search"""
        try:
            with postgres_db.get_session() as session:
                check_column = text("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'nuclei_templates' AND column_name = 'tsv'
                """)
                if not session.execute(check_column).fetchone():
                    logger.info("Creating tsv column for full-text search...")
                    session.execute(text("""
                        ALTER TABLE nuclei_templates
                        ADD COLUMN tsv tsvector
                        GENERATED ALWAYS AS (
                            setweight(to_tsvector('english', COALESCE(name, '')), 'A') ||
                            setweight(to_tsvector('english', COALESCE(description, '')), 'B')
                        ) STORED
                    """))
                    session.execute(text("""
                        CREATE INDEX IF NOT EXISTS nuclei_templates_tsv_idx
                        ON nuclei_templates USING GIN (tsv)
                    """))
                    session.commit()
        except Exception as e:
            logger.warning(f"Could not ensure TSV column: {e}")

    def _parse_template_file(self, file_path: Path) -> Optional[dict]:
        """Parse a Nuclei template file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                template_data = yaml.safe_load(f)

            if not template_data or not isinstance(template_data, dict):
                return None

            info = template_data.get('info', {})
            name = info.get('name', '')
            if not name: return None

            description = info.get('description', '') or name
            
            with open(file_path, 'r', encoding='utf-8') as f:
                template_content = f.read()

            return {
                'name': name,
                'description': description,
                'template': template_content,
                'metadata': info
            }
        except Exception:
            return None

    def _clear_database(self):
        """Clear all existing Nuclei templates from database"""
        try:
            with postgres_db.get_session() as session:
                session.execute(delete(NucleiTemplates))
                session.commit()
        except Exception as e:
            logger.error(f"Failed to clear database: {e}")
            raise

    def _sync_templates_to_database(self) -> int:
        """Sync templates from cloned repository to database"""
        count = 0
        templates_dir = Path(self.clone_dir)
        yaml_files = list(templates_dir.rglob("*.yaml"))
        logger.info(f"Found {len(yaml_files)} template files")

        batch_size = 50
        batch_data = []

        for idx, yaml_file in enumerate(yaml_files):
            try:
                data = self._parse_template_file(yaml_file)
                if not data: continue

                # Basic data cleanup
                clean = lambda t: t.replace('\x00', '') if t and isinstance(t, str) else ""
                name = clean(data['name'])
                desc = clean(data['description'])
                content = clean(data['template'])
                meta = data['metadata']

                # Create Embedding Text
                text_to_embed = f"Template: {name} Purpose: {desc}"
                if 'tags' in meta: text_to_embed += f" Tags: {meta['tags']}"
                
                embedding = self.embeddings_manager.embed_query(text_to_embed)

                batch_data.append({
                    'name': name[:255],
                    'description': desc,
                    'template': content,
                    'embedding': embedding
                })

                if len(batch_data) >= batch_size:
                    self._insert_batch(batch_data)
                    count += len(batch_data)
                    batch_data = []

            except Exception:
                continue

        if batch_data:
            self._insert_batch(batch_data)
            count += len(batch_data)

        logger.info(f"Synced {count} templates")
        return count

    def _insert_batch(self, batch_data: list):
        """Insert batch to DB"""
        try:
            with postgres_db.get_session() as session:
                for data in batch_data:
                    session.add(NucleiTemplates(**data))
                session.commit()
        except:
            pass
