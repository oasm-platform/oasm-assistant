"""
Scheduler service for syncing Nuclei templates from GitHub repository
"""
import os
import shutil
import threading
import time
import git
import yaml
from datetime import datetime
from typing import Optional
from pathlib import Path

from common.logger import logger
from common.config import configs
from data.database import postgres_db
from data.database.models import NucleiTemplates
from data.embeddings import embeddings_manager
from sqlalchemy import delete, text


class NucleiTemplatesScheduler:
    """Scheduler for periodic Nuclei templates synchronization"""

    def __init__(self):
        """Initialize the scheduler"""
        self.repo_url = configs.scheduler.nuclei_templates_repo_url
        self.clone_dir = configs.scheduler.nuclei_templates_clone_dir
        self.sync_time = configs.scheduler.nuclei_templates_sync_time
        self.running = False
        self.thread: Optional[threading.Thread] = None

        # Use shared singleton embedding model
        self.embeddings_manager = embeddings_manager

        # Ensure TSV column and index exist for hybrid search
        self._ensure_tsv_column()

        logger.info(f"NucleiTemplatesScheduler initialized with sync time: {self.sync_time}")

    def _ensure_tsv_column(self):
        """Ensure tsv column and index exist for full-text search"""
        try:
            with postgres_db.get_session() as session:
                # Check if tsv column exists
                check_column = text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'nuclei_templates'
                    AND column_name = 'tsv'
                """)
                result = session.execute(check_column).fetchone()

                if not result:
                    logger.info("Creating tsv column for full-text search...")

                    # Add tsv column
                    session.execute(text("""
                        ALTER TABLE nuclei_templates
                        ADD COLUMN tsv tsvector
                        GENERATED ALWAYS AS (
                            setweight(to_tsvector('english', COALESCE(name, '')), 'A') ||
                            setweight(to_tsvector('english', COALESCE(description, '')), 'B')
                        ) STORED
                    """))

                    # Create GIN index
                    session.execute(text("""
                        CREATE INDEX IF NOT EXISTS nuclei_templates_tsv_idx
                        ON nuclei_templates USING GIN (tsv)
                    """))

                    session.commit()
                    logger.info("TSV column and index created successfully")
                else:
                    logger.debug("TSV column already exists")

        except Exception as e:
            logger.warning(f"Could not ensure TSV column (may already exist): {e}")

    def _clone_or_pull_repo(self) -> bool:
        """
        Clone or pull the latest Nuclei templates repository

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if os.path.exists(self.clone_dir):
                # Pull latest changes
                logger.info(f"Pulling latest changes from {self.repo_url}")
                repo = git.Repo(self.clone_dir)
                origin = repo.remotes.origin
                origin.pull()
                logger.info("Successfully pulled latest changes")
            else:
                # Clone repository
                logger.info(f"Cloning repository from {self.repo_url}")
                git.Repo.clone_from(self.repo_url, self.clone_dir, depth=1)
                logger.info("Successfully cloned repository")

            return True
        except Exception as e:
            logger.error(f"Failed to clone/pull repository: {e}")
            return False

    def _parse_template_file(self, file_path: Path) -> Optional[dict]:
        """
        Parse a Nuclei template file

        Args:
            file_path: Path to the template file

        Returns:
            dict: Parsed template data or None if failed
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                template_data = yaml.safe_load(f)

            if not template_data or not isinstance(template_data, dict):
                return None

            # Extract basic info
            template_id = template_data.get('id', '')
            info = template_data.get('info', {})
            name = info.get('name', '')
            description = info.get('description', '')

            # Extract metadata for better embedding
            tags = info.get('tags', [])
            severity = info.get('severity', '')
            author = info.get('author', '')
            reference = info.get('reference', [])
            classification = info.get('classification', {})

            # Extract technical details
            cve_id = classification.get('cve-id', '')
            cwe_id = classification.get('cwe-id', '')
            cvss_metrics = classification.get('cvss-metrics', '')

            # Read raw template content
            with open(file_path, 'r', encoding='utf-8') as f:
                template_content = f.read()

            if not template_id or not name:
                return None

            return {
                'name': name,
                'description': description or name,
                'template': template_content,
                'metadata': {
                    'tags': tags if isinstance(tags, list) else [],
                    'severity': severity,
                    'author': author,
                    'cve_id': cve_id,
                    'cwe_id': cwe_id,
                    'cvss_metrics': cvss_metrics,
                    'reference': reference if isinstance(reference, list) else []
                }
            }
        except Exception as e:
            logger.debug(f"Failed to parse template {file_path}: {e}")
            return None

    def _clean_text(self, text: str) -> str:
        """
        Clean text to remove NUL characters and other problematic characters

        Args:
            text: Input text

        Returns:
            Cleaned text safe for PostgreSQL
        """
        if not text:
            return ""
        # Remove NUL characters that PostgreSQL doesn't accept
        return text.replace('\x00', '').replace('\u0000', '')

    def _extract_template_keywords(self, template_content: str) -> str:
        """
        Extract key technical terms from template for better semantic matching

        Args:
            template_content: Raw YAML template content

        Returns:
            Space-separated keywords extracted from template
        """
        import re

        keywords = []

        try:
            # Extract paths (common indicators of what's being tested)
            paths = re.findall(r'path:\s*\n\s*-\s*["\']?([^"\']+)["\']?', template_content)
            for path in paths[:3]:  # Limit to first 3 paths
                # Extract meaningful parts (remove {{BaseURL}} etc)
                clean_path = re.sub(r'\{\{.*?\}\}', '', path).strip('/')
                if clean_path:
                    keywords.append(clean_path)

            # Extract matcher words (what patterns it looks for)
            words = re.findall(r'words?:\s*\n\s*-\s*["\']?([^"\']+)["\']?', template_content)
            keywords.extend(words[:5])  # Limit to first 5 words

            # Extract common vulnerability patterns
            vuln_patterns = re.findall(r'\b(SQL|XSS|SSRF|LFI|RFI|XXE|CSRF|RCE|injection|bypass|disclosure)\b',
                                      template_content, re.IGNORECASE)
            keywords.extend(set(vuln_patterns[:5]))  # Unique patterns, max 5

            # Return as space-separated string, limit total length
            keyword_str = ' '.join(keywords)
            return keyword_str[:200] if keyword_str else ""  # Limit to 200 chars

        except Exception:
            # Silently fail - keyword extraction is optional
            return ""

    def _clear_database(self):
        """Clear all existing Nuclei templates from database"""
        try:
            with postgres_db.get_session() as session:
                session.execute(delete(NucleiTemplates))
                session.commit()
                logger.info("Cleared all existing Nuclei templates from database")
        except Exception as e:
            logger.error(f"Failed to clear database: {e}")
            raise

    def _sync_templates_to_database(self) -> int:
        """
        Sync templates from cloned repository to database

        Returns:
            int: Number of templates synced
        """
        count = 0
        skipped = 0
        failed = 0
        templates_dir = Path(self.clone_dir)

        # Find all .yaml files
        yaml_files = list(templates_dir.rglob("*.yaml")) + list(templates_dir.rglob("*.yml"))
        logger.info(f"Found {len(yaml_files)} template files")

        batch_size = 50
        batch_data = []

        for idx, yaml_file in enumerate(yaml_files):
            try:
                # Parse template
                template_data = self._parse_template_file(yaml_file)
                if not template_data:
                    skipped += 1
                    if skipped <= 5:  # Log first 5 skips
                        logger.warning(f"Skipped template (no id/name): {yaml_file}")
                    continue

                # Clean text to remove NUL characters
                name = self._clean_text(template_data['name'])
                description = self._clean_text(template_data['description'])
                template_content = self._clean_text(template_data['template'])
                metadata = template_data.get('metadata', {})

                # Create RICH embedding text with comprehensive metadata for better RAG matching
                tags_str = ', '.join(metadata.get('tags', [])) if metadata.get('tags') else ''
                severity = metadata.get('severity', '')
                author = metadata.get('author', '')
                cve_id = metadata.get('cve_id', '')
                cwe_id = metadata.get('cwe_id', '')

                # Extract technical keywords from template content for better semantic search
                # This helps match user queries about specific vulnerabilities, endpoints, etc.
                template_keywords = self._extract_template_keywords(template_content)

                # Build COMPREHENSIVE embedding text with weighted importance
                # Name and description get highest priority (mentioned multiple times)
                embedding_parts = [
                    f"Template: {name}",  # Primary identifier
                    f"Purpose: {description}",  # What it detects
                    name,  # Repeat for emphasis
                    description,  # Repeat for emphasis
                ]

                # Add metadata context
                if tags_str:
                    embedding_parts.append(f"Tags: {tags_str}")
                    embedding_parts.append(tags_str)  # Repeat tags for importance
                if severity:
                    embedding_parts.append(f"Severity: {severity}")
                if cve_id:
                    embedding_parts.append(f"CVE Identifier: {cve_id}")
                    embedding_parts.append(cve_id)  # CVE IDs are important search terms
                if cwe_id:
                    embedding_parts.append(f"CWE Category: {cwe_id}")

                # Add extracted keywords (paths, matchers, etc.)
                if template_keywords:
                    embedding_parts.append(f"Detection patterns: {template_keywords}")

                text_to_embed = ' '.join(filter(None, embedding_parts))  # Remove empty strings

                # Use encode() which returns List[List[float]], take first element
                embedding = self.embeddings_manager.get_embedding().encode([text_to_embed])[0]

                # Prepare data
                batch_data.append({
                    'name': name[:255],  # Limit to 255 chars
                    'description': description,
                    'template': template_content,
                    'embedding': embedding
                })

                # Batch insert
                if len(batch_data) >= batch_size:
                    self._insert_batch(batch_data)
                    count += len(batch_data)
                    batch_data = []
                    # Update progress on same line (overwrites previous)
                    progress_pct = (idx + 1) / len(yaml_files) * 100
                    print(f"\rProgress: {progress_pct:.1f}% | Synced: {count}/{len(yaml_files)} templates    ", end='', flush=True)

            except Exception as e:
                failed += 1
                if failed <= 5:  # Log first 5 failures with full error
                    logger.error(f"Failed to process template {yaml_file}: {e}", exc_info=True)
                elif failed == 6:
                    logger.warning(f"Too many errors, suppressing further error logs...")
                continue

        # Insert remaining templates
        if batch_data:
            self._insert_batch(batch_data)
            count += len(batch_data)

        # Clear the progress line and log final result
        print()  # New line after progress bar
        logger.info(f"Successfully synced {count} templates to database (skipped: {skipped}, failed: {failed})")
        return count

    def _insert_batch(self, batch_data: list):
        """Insert a batch of templates to database"""
        try:
            with postgres_db.get_session() as session:
                for data in batch_data:
                    template = NucleiTemplates(**data)
                    session.add(template)
                session.commit()
        except Exception as e:
            # Log error once but don't raise to continue with other batches
            logger.error(f"Failed to insert batch of {len(batch_data)} templates: {str(e)[:100]}")
            # Rollback the failed batch
            try:
                session.rollback()
            except:
                pass

    def sync_templates(self):
        """Execute the full sync process"""
        try:
            logger.info("Starting Nuclei templates synchronization...")
            start_time = time.time()

            # Step 1: Clone or pull repository
            if not self._clone_or_pull_repo():
                logger.error("Failed to clone/pull repository, aborting sync")
                return

            # Step 2: Clear existing data
            self._clear_database()

            # Step 3: Sync templates to database
            count = self._sync_templates_to_database()

            elapsed_time = time.time() - start_time
            logger.info(f"Nuclei templates sync completed: {count} templates in {elapsed_time:.2f}s")

            # Cleanup cloned directory to save space (optional)
            # shutil.rmtree(self.clone_dir, ignore_errors=True)

        except Exception as e:
            logger.error(f"Error during Nuclei templates sync: {e}")

    def _should_run_sync(self) -> bool:
        """Check if it's time to run the sync based on configured time"""
        try:
            now = datetime.now()
            sync_hour, sync_minute = map(int, self.sync_time.split(':'))

            return now.hour == sync_hour and now.minute == sync_minute
        except Exception as e:
            logger.error(f"Error checking sync time: {e}")
            return False

    def _scheduler_loop(self):
        """Main scheduler loop"""
        logger.info("Nuclei templates scheduler started")
        last_sync_date = None

        while self.running:
            try:
                if self._should_run_sync():
                    current_date = datetime.now().date()

                    # Only sync once per day
                    if last_sync_date != current_date:
                        logger.info("Scheduled sync time reached, starting sync...")
                        self.sync_templates()
                        last_sync_date = current_date

                # Sleep for 60 seconds before next check
                time.sleep(60)

            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                time.sleep(60)

        logger.info("Nuclei templates scheduler stopped")

    def start(self):
        """Start the scheduler"""
        if self.running:
            logger.warning("Scheduler is already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.thread.start()
        logger.info("Nuclei templates scheduler thread started")

    def stop(self):
        """Stop the scheduler"""
        if not self.running:
            logger.warning("Scheduler is not running")
            return

        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Nuclei templates scheduler stopped")


# Global scheduler instance
_scheduler_instance: Optional[NucleiTemplatesScheduler] = None


def get_scheduler() -> NucleiTemplatesScheduler:
    """Get or create the global scheduler instance"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = NucleiTemplatesScheduler()
    return _scheduler_instance
