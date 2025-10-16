"""
Pytest configuration and fixtures for OASM Assistant tests
"""

import pytest
import sys
import os
import uuid
from unittest.mock import Mock, patch

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

@pytest.fixture(scope="session")
def project_root_path():
    """Return the project root path"""
    return project_root

@pytest.fixture
def mock_database():
    """Mock database for testing"""
    with patch('data.database.postgres_db') as mock_db:
        mock_session = Mock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session
        mock_db.get_session.return_value.__exit__.return_value = None
        yield mock_db

@pytest.fixture
def test_workspace_id():
    """Generate a test workspace ID"""
    return str(uuid.uuid4())

@pytest.fixture
def test_user_id():
    """Generate a test user ID"""
    return str(uuid.uuid4())

@pytest.fixture
def test_conversation_id():
    """Generate a test conversation ID"""
    return str(uuid.uuid4())

@pytest.fixture
def test_message_id():
    """Generate a test message ID"""
    return str(uuid.uuid4())

@pytest.fixture
def sample_vectors():
    """Sample vectors for testing"""
    return [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0]
    ]

@pytest.fixture
def sample_texts():
    """Sample texts for testing"""
    return [
        "This is a sample document about artificial intelligence",
        "Machine learning is a subset of AI that focuses on algorithms",
        "Natural language processing helps computers understand human language",
        "Computer vision enables machines to interpret visual information",
        "Deep learning uses neural networks with multiple layers"
    ]

@pytest.fixture
def sample_documents():
    """Sample documents for testing retrieval"""
    return [
        {"content": "Artificial intelligence is transforming the world.", "metadata": {"source": "doc1"}},
        {"content": "Machine learning is a subset of AI.", "metadata": {"source": "doc2"}},
        {"content": "Deep learning is a powerful technique in AI.", "metadata": {"source": "doc3"}},
    ]

@pytest.fixture
def mock_embedding_model():
    """Mock embedding model for testing"""
    with patch('data.embeddings.embeddings.Embeddings.create_embedding') as mock_create:
        mock_model = Mock()
        mock_model.encode.return_value = [[0.1, 0.2, 0.3, 0.4]] * 5  # Mock embeddings
        mock_model.embed_query.return_value = [0.1, 0.2, 0.3, 0.4]
        mock_create.return_value = mock_model
        yield mock_model

@pytest.fixture
def mock_security_coordinator():
    """Mock SecurityCoordinator for testing"""
    with patch('agents.workflows.security_coordinator.SecurityCoordinator') as mock_coordinator:
        mock_instance = Mock()
        mock_instance.process_message_question.return_value = "Test security analysis response"
        mock_coordinator.return_value = mock_instance
        yield mock_instance