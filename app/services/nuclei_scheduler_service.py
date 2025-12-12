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
        Clone or pull the latest Nuclei templates repository with retry logic
        and HTTP/2 error handling

        Returns:
            bool: True if successful, False otherwise
        """
        max_retries = 3
        retry_delay = 5  # seconds
        
        for attempt in range(max_retries):
            try:
                if os.path.exists(self.clone_dir):
                    # Pull latest changes
                    logger.info(f"Pulling latest changes from {self.repo_url} (attempt {attempt + 1}/{max_retries})")
                    repo = git.Repo(self.clone_dir)
                    
                    # Configure Git to handle HTTP/2 issues
                    with repo.config_writer() as git_config:
                        # Increase buffer size to handle large repositories
                        git_config.set_value('http', 'postBuffer', '524288000')  # 500MB
                        # Allow fallback to HTTP/1.1 if HTTP/2 fails
                        git_config.set_value('http', 'version', 'HTTP/1.1')
                        # Increase timeout
                        git_config.set_value('http', 'lowSpeedLimit', '1000')
                        git_config.set_value('http', 'lowSpeedTime', '60')
                    
                    # Perform pull with verbose output
                    origin = repo.remotes.origin
                    origin.pull(verbose=True)
                    logger.info("Successfully pulled latest changes")
                else:
                    # Clone repository
                    logger.info(f"Cloning repository from {self.repo_url} (attempt {attempt + 1}/{max_retries})")
                    
                    # Clone with shallow depth to reduce data transfer
                    repo = git.Repo.clone_from(
                        self.repo_url,
                        self.clone_dir,
                        depth=1
                    )
                    
                    # Configure Git after cloning to handle HTTP/2 issues
                    with repo.config_writer() as git_config:
                        # Increase buffer size to handle large repositories
                        git_config.set_value('http', 'postBuffer', '524288000')  # 500MB
                        # Allow fallback to HTTP/1.1 if HTTP/2 fails
                        git_config.set_value('http', 'version', 'HTTP/1.1')
                        # Increase timeout
                        git_config.set_value('http', 'lowSpeedLimit', '1000')
                        git_config.set_value('http', 'lowSpeedTime', '60')
                    
                    logger.info("Successfully cloned repository")

                return True
                
            except git.exc.GitCommandError as e:
                logger.warning(f"Git command failed (attempt {attempt + 1}/{max_retries}): {e}")
                
                # Check if it's an HTTP/2 related error
                if 'HTTP/2 stream' in str(e) or 'RPC failed' in str(e) or 'early EOF' in str(e):
                    if attempt < max_retries - 1:
                        logger.info(f"HTTP/2 error detected, retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        
                        # If pull failed, try to reset and pull again
                        if os.path.exists(self.clone_dir):
                            try:
                                logger.info("Attempting to reset repository and retry...")
                                repo = git.Repo(self.clone_dir)
                                repo.git.reset('--hard', 'HEAD')
                                repo.git.clean('-fdx')
                            except Exception as reset_error:
                                logger.warning(f"Failed to reset repository: {reset_error}")
                                # If reset fails, remove and try fresh clone
                                logger.info("Removing corrupted repository for fresh clone...")
                                shutil.rmtree(self.clone_dir, ignore_errors=True)
                        continue
                    else:
                        logger.error(f"Failed after {max_retries} attempts due to HTTP/2 errors")
                        return False
                else:
                    # Non-HTTP/2 error, don't retry
                    logger.error(f"Git command failed with non-retryable error: {e}")
                    return False
                    
            except Exception as e:
                logger.error(f"Unexpected error during clone/pull: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                return False
        
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

                # Generate embedding using LangChain's embed_query method
                embedding = self.embeddings_manager.embed_query(text_to_embed)

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
            
            # Check if current time is at or past the sync time
            # This prevents missing the sync window due to 60-second check interval
            current_minutes = now.hour * 60 + now.minute
            sync_minutes = sync_hour * 60 + sync_minute
            
            return current_minutes >= sync_minutes
        except Exception as e:
            logger.error(f"Error checking sync time: {e}")
            return False

    def _scheduler_loop(self):
        """Main scheduler loop"""
        logger.info("Nuclei templates scheduler started")
        last_sync_date = None

        while self.running:
            try:
                current_date = datetime.now().date()
                current_time = datetime.now().strftime("%H:%M:%S")
                
                if self._should_run_sync():
                    # Only sync once per day
                    if last_sync_date != current_date:
                        logger.info(f"Scheduled sync time reached at {current_time}, starting sync...")
                        self.sync_templates()
                        last_sync_date = current_date
                    else:
                        logger.debug(f"Sync already completed today ({current_date}), skipping...")
                else:
                    logger.debug(f"Current time {current_time} has not reached sync time {self.sync_time} yet")

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
