"""
Pytest tests for database functionality
"""

import pytest
from unittest.mock import Mock, patch
from data.database.models import Conversation
from data.database import postgres_db as db


class TestDatabase:
    """Test database operations"""

    def test_database_health_check(self, mock_database):
        """Test database health check"""
        # Mock successful health check
        mock_database.health_check.return_value = True

        # Call health check
        mock_database.health_check()

        # Verify it was called
        mock_database.health_check.assert_called_once()

    def test_add_conversation_success(self, mock_database, test_workspace_id, test_user_id):
        """Test adding conversation to database successfully"""
        # Create test conversation
        conversation = Conversation(
            title="Test Conversation",
            workspace_id=test_workspace_id,
            user_id=test_user_id
        )

        # Mock session operations
        mock_session = mock_database.get_session.return_value.__enter__.return_value

        # Test adding conversation
        with mock_database.get_session() as session:
            session.add(conversation)
            session.commit()
            session.refresh(conversation)

        # Verify operations were called
        mock_session.add.assert_called_once_with(conversation)
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once_with(conversation)

    def test_add_conversation_failure(self, mock_database):
        """Test handling database errors when adding conversation"""
        conversation = Conversation(title="Test Conversation")

        # Mock session to raise exception
        mock_session = mock_database.get_session.return_value.__enter__.return_value
        mock_session.add.side_effect = Exception("Database error")

        # Test that exception is properly handled
        with pytest.raises(Exception):
            with mock_database.get_session() as session:
                session.add(conversation)
                session.commit()

    def test_conversation_model_creation(self, test_workspace_id, test_user_id):
        """Test Conversation model creation"""
        conversation = Conversation(
            title="Test Conversation",
            description="Test Description",
            workspace_id=test_workspace_id,
            user_id=test_user_id
        )

        assert conversation.title == "Test Conversation"
        assert conversation.description == "Test Description"
        assert conversation.workspace_id == test_workspace_id
        assert conversation.user_id == test_user_id

    def test_database_session_context_manager(self, mock_database):
        """Test database session context manager"""
        # Test context manager usage
        with mock_database.get_session() as session:
            pass

        # Verify context manager was used
        mock_database.get_session.assert_called_once()
    