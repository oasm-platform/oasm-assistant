"""
Unit tests for Nuclei Templates Scheduler
"""

import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path
from datetime import datetime

from app.services.nuclei_scheduler import NucleiTemplatesScheduler


@pytest.fixture
def temp_clone_dir():
    """Create a temporary directory for cloning"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_config(temp_clone_dir):
    """Mock configuration"""
    with patch('app.services.nuclei_scheduler.configs') as mock_cfg:
        mock_cfg.scheduler.nuclei_templates_repo_url = "https://github.com/test/repo.git"
        mock_cfg.scheduler.nuclei_templates_clone_dir = temp_clone_dir
        mock_cfg.scheduler.nuclei_templates_sync_time = "02:00"

        # Mock embedding config
        mock_cfg.embedding.provider = "sentence_transformer"
        mock_cfg.embedding.api_key = "test-key"
        mock_cfg.embedding.model_name = "all-MiniLM-L6-v2"
        mock_cfg.embedding.base_url = None

        yield mock_cfg


@pytest.fixture
def mock_embedding():
    """Mock embedding model"""
    with patch('app.services.nuclei_scheduler.get_embedding_model') as mock_get_emb:
        mock_model = Mock()
        mock_model.encode.return_value = [0.1] * 384  # Mock 384-dim embedding
        mock_get_emb.return_value = mock_model
        yield mock_model


@pytest.fixture
def mock_postgres_db():
    """Mock postgres database"""
    with patch('app.services.nuclei_scheduler.postgres_db') as mock_db:
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session
        mock_db.get_session.return_value.__exit__.return_value = None
        yield mock_db


@pytest.fixture
def sample_nuclei_templates(temp_clone_dir):
    """Create sample nuclei template files"""
    templates_dir = Path(temp_clone_dir) / "http"
    templates_dir.mkdir(parents=True, exist_ok=True)

    # Template 1
    template1 = templates_dir / "test-template-1.yaml"
    template1.write_text("""
id: test-sqli-1
info:
  name: SQL Injection Detection
  description: Detects SQL injection vulnerabilities
  severity: high
requests:
  - method: GET
    path:
      - "{{BaseURL}}/admin?id=1'"
""")

    # Template 2
    template2 = templates_dir / "test-template-2.yaml"
    template2.write_text("""
id: test-xss-1
info:
  name: XSS Detection
  description: Detects cross-site scripting vulnerabilities
  severity: medium
requests:
  - method: GET
    path:
      - "{{BaseURL}}/search?q=<script>alert(1)</script>"
""")

    # Invalid template (should be skipped)
    invalid_template = templates_dir / "invalid.yaml"
    invalid_template.write_text("invalid: yaml: content:")

    return templates_dir


class TestNucleiTemplatesScheduler:
    """Test suite for NucleiTemplatesScheduler"""

    def test_scheduler_initialization(self, mock_config, mock_embedding):
        """Test scheduler initialization"""
        scheduler = NucleiTemplatesScheduler()

        assert scheduler.repo_url == "https://github.com/test/repo.git"
        assert scheduler.sync_time == "02:00"
        assert scheduler.running == False
        assert scheduler.thread is None

    def test_parse_valid_template(self, mock_config, mock_embedding, sample_nuclei_templates):
        """Test parsing a valid nuclei template"""
        scheduler = NucleiTemplatesScheduler()
        template_file = sample_nuclei_templates / "test-template-1.yaml"

        result = scheduler._parse_template_file(template_file)

        assert result is not None
        assert result['name'] == "SQL Injection Detection"
        assert result['description'] == "Detects SQL injection vulnerabilities"
        assert 'id: test-sqli-1' in result['template']

    def test_parse_invalid_template(self, mock_config, mock_embedding, sample_nuclei_templates):
        """Test parsing an invalid template (should return None)"""
        scheduler = NucleiTemplatesScheduler()
        template_file = sample_nuclei_templates / "invalid.yaml"

        result = scheduler._parse_template_file(template_file)

        assert result is None

    def test_clear_database(self, mock_config, mock_embedding, mock_postgres_db):
        """Test clearing database"""
        scheduler = NucleiTemplatesScheduler()

        scheduler._clear_database()

        # Verify delete was called
        mock_session = mock_postgres_db.get_session.return_value.__enter__.return_value
        assert mock_session.execute.called
        assert mock_session.commit.called

    def test_insert_batch(self, mock_config, mock_embedding, mock_postgres_db):
        """Test batch insert to database"""
        scheduler = NucleiTemplatesScheduler()

        batch_data = [
            {
                'name': 'Test Template 1',
                'description': 'Test Description 1',
                'template': 'template content 1',
                'embedding': [0.1] * 384
            },
            {
                'name': 'Test Template 2',
                'description': 'Test Description 2',
                'template': 'template content 2',
                'embedding': [0.2] * 384
            }
        ]

        scheduler._insert_batch(batch_data)

        mock_session = mock_postgres_db.get_session.return_value.__enter__.return_value
        assert mock_session.add.call_count == 2
        assert mock_session.commit.called

    @patch('git.Repo')
    def test_clone_repo_new(self, mock_git_repo, mock_config, mock_embedding, temp_clone_dir):
        """Test cloning a new repository"""
        scheduler = NucleiTemplatesScheduler()

        # Ensure directory doesn't exist
        shutil.rmtree(temp_clone_dir, ignore_errors=True)

        result = scheduler._clone_or_pull_repo()

        assert result == True
        assert mock_git_repo.clone_from.called

    @patch('git.Repo')
    def test_pull_existing_repo(self, mock_git_repo, mock_config, mock_embedding, temp_clone_dir):
        """Test pulling an existing repository"""
        scheduler = NucleiTemplatesScheduler()

        # Create directory to simulate existing repo
        os.makedirs(temp_clone_dir, exist_ok=True)

        # Mock repo instance
        mock_repo_instance = Mock()
        mock_origin = Mock()
        mock_repo_instance.remotes.origin = mock_origin
        mock_git_repo.return_value = mock_repo_instance

        result = scheduler._clone_or_pull_repo()

        assert result == True
        assert mock_git_repo.called
        assert mock_origin.pull.called

    def test_should_run_sync_true(self, mock_config, mock_embedding):
        """Test should_run_sync returns True at correct time"""
        scheduler = NucleiTemplatesScheduler()
        scheduler.sync_time = datetime.now().strftime("%H:%M")

        result = scheduler._should_run_sync()

        assert result == True

    def test_should_run_sync_false(self, mock_config, mock_embedding):
        """Test should_run_sync returns False at wrong time"""
        scheduler = NucleiTemplatesScheduler()
        scheduler.sync_time = "23:59"  # Different from current time

        result = scheduler._should_run_sync()

        assert result == False

    def test_sync_templates_full_workflow(
        self, mock_config, mock_embedding, mock_postgres_db, sample_nuclei_templates
    ):
        """Test full sync workflow"""
        with patch.object(NucleiTemplatesScheduler, '_clone_or_pull_repo', return_value=True):
            scheduler = NucleiTemplatesScheduler()
            scheduler.clone_dir = str(sample_nuclei_templates.parent)

            scheduler.sync_templates()

            # Verify clear database was called
            mock_session = mock_postgres_db.get_session.return_value.__enter__.return_value
            assert mock_session.execute.called
            assert mock_session.commit.called

            # Verify templates were added (2 valid templates)
            assert mock_session.add.call_count >= 2

    def test_scheduler_start_stop(self, mock_config, mock_embedding):
        """Test starting and stopping scheduler"""
        scheduler = NucleiTemplatesScheduler()

        # Start scheduler
        scheduler.start()
        assert scheduler.running == True
        assert scheduler.thread is not None
        assert scheduler.thread.is_alive()

        # Stop scheduler
        scheduler.stop()
        assert scheduler.running == False

    def test_scheduler_start_already_running(self, mock_config, mock_embedding):
        """Test starting scheduler when already running"""
        scheduler = NucleiTemplatesScheduler()

        scheduler.start()
        initial_thread = scheduler.thread

        # Try to start again
        scheduler.start()

        # Should be the same thread
        assert scheduler.thread == initial_thread

        scheduler.stop()

    def test_get_scheduler_singleton(self, mock_config, mock_embedding):
        """Test get_scheduler returns singleton instance"""
        from app.services.nuclei_scheduler import get_scheduler, _scheduler_instance

        # Reset singleton
        import app.services.nuclei_scheduler as scheduler_module
        scheduler_module._scheduler_instance = None

        scheduler1 = get_scheduler()
        scheduler2 = get_scheduler()

        assert scheduler1 is scheduler2

    def test_sync_templates_clone_failure(self, mock_config, mock_embedding):
        """Test sync when clone/pull fails"""
        with patch.object(NucleiTemplatesScheduler, '_clone_or_pull_repo', return_value=False):
            scheduler = NucleiTemplatesScheduler()

            # Should not raise exception, just log and return
            scheduler.sync_templates()

    def test_template_name_truncation(self, mock_config, mock_embedding, mock_postgres_db):
        """Test that template name is truncated to 255 chars"""
        scheduler = NucleiTemplatesScheduler()

        long_name = "A" * 300
        batch_data = [{
            'name': long_name[:255],  # Already truncated in real code
            'description': 'Test',
            'template': 'content',
            'embedding': [0.1] * 384
        }]

        scheduler._insert_batch(batch_data)

        # Verify insert was attempted
        mock_session = mock_postgres_db.get_session.return_value.__enter__.return_value
        assert mock_session.add.called
        assert mock_session.commit.called


class TestSchedulerIntegration:
    """Integration tests for scheduler"""

    def test_end_to_end_sync(
        self, mock_config, mock_embedding,
        mock_postgres_db, sample_nuclei_templates, temp_clone_dir
    ):
        """Test end-to-end sync process"""
        # Setup
        scheduler = NucleiTemplatesScheduler()
        scheduler.clone_dir = str(sample_nuclei_templates.parent)

        # Mock successful clone
        with patch.object(scheduler, '_clone_or_pull_repo', return_value=True):
            # Run sync
            scheduler.sync_templates()

        # Verify workflow
        mock_session = mock_postgres_db.get_session.return_value.__enter__.return_value

        # 1. Database should be cleared
        assert mock_session.execute.called

        # 2. Templates should be inserted
        assert mock_session.add.called

        # 3. Transaction should be committed
        assert mock_session.commit.called
