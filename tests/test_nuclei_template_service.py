"""
Integration tests for NucleiTemplateService with RAG
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import grpc
from grpc import StatusCode

from app.services.nuclei_template import NucleiTemplateService
from app.protos import assistant_pb2


@pytest.fixture
def mock_llm():
    """Mock LLM manager"""
    with patch('app.services.nuclei_template.llm_manager') as mock_mgr:
        mock_llm_instance = Mock()
        mock_response = Mock()
        mock_response.content = """```yaml
id: test-template
info:
  name: Test Template
  description: Generated test template
  severity: medium
requests:
  - method: GET
    path:
      - "{{BaseURL}}/test"
```"""
        mock_llm_instance.invoke.return_value = mock_response
        mock_mgr.get_llm.return_value = mock_llm_instance
        yield mock_mgr


@pytest.fixture
def mock_vector_store():
    """Mock vector store"""
    with patch('app.services.nuclei_template.PgVectorStore') as mock_vs:
        mock_instance = Mock()
        mock_vs.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_hybrid_retriever():
    """Mock hybrid retriever"""
    with patch('app.services.nuclei_template.HybridRetriever') as mock_hr:
        mock_instance = Mock()

        # Mock successful retrieval
        mock_instance.hybrid_search.return_value = [
            {
                'id': 'template-1',
                'score': 0.95,
                'vec_score': 0.92,
                'text_score': 0.88,
                'metadata': {
                    'title': 'SQL Injection Detection',
                    'content': 'Detects SQL injection vulnerabilities'
                }
            },
            {
                'id': 'template-2',
                'score': 0.87,
                'vec_score': 0.85,
                'text_score': 0.82,
                'metadata': {
                    'title': 'XSS Detection',
                    'content': 'Detects cross-site scripting'
                }
            },
            {
                'id': 'template-3',
                'score': 0.78,
                'vec_score': 0.75,
                'text_score': 0.72,
                'metadata': {
                    'title': 'Command Injection',
                    'content': 'Detects command injection vulnerabilities'
                }
            }
        ]

        mock_hr.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_configs():
    """Mock configs"""
    with patch('app.services.nuclei_template.configs') as mock_cfg:
        mock_cfg.embedding.provider = "openai"
        mock_cfg.embedding.api_key = "test-key"
        mock_cfg.embedding.model_name = "text-embedding-3-small"
        yield mock_cfg


class TestNucleiTemplateService:
    """Test suite for NucleiTemplateService"""

    def test_service_initialization(self, mock_llm, mock_vector_store, mock_hybrid_retriever, mock_configs):
        """Test service initialization"""
        service = NucleiTemplateService()

        assert service.llm_manager is not None
        assert service.vector_store is not None
        assert service.hybrid_retriever is not None

    def test_retrieve_similar_templates_success(
        self, mock_llm, mock_vector_store, mock_hybrid_retriever, mock_configs
    ):
        """Test successful retrieval of similar templates"""
        service = NucleiTemplateService()

        context = service._retrieve_similar_templates("SQL injection detection", k=3)

        assert "Here are some similar Nuclei templates for reference:" in context
        assert "SQL Injection Detection" in context
        assert "XSS Detection" in context
        assert "Command Injection" in context
        assert "0.950" in context  # Check score is included

    def test_retrieve_similar_templates_no_results(
        self, mock_llm, mock_vector_store, mock_hybrid_retriever, mock_configs
    ):
        """Test retrieval when no similar templates found"""
        service = NucleiTemplateService()

        # Mock empty results
        mock_hybrid_retriever.hybrid_search.return_value = []

        context = service._retrieve_similar_templates("test query", k=3)

        assert context == ""

    def test_retrieve_similar_templates_error(
        self, mock_llm, mock_vector_store, mock_hybrid_retriever, mock_configs
    ):
        """Test retrieval when error occurs"""
        service = NucleiTemplateService()

        # Mock error
        mock_hybrid_retriever.hybrid_search.side_effect = Exception("Database error")

        context = service._retrieve_similar_templates("test query", k=3)

        assert context == ""

    def test_generate_template_with_rag(
        self, mock_llm, mock_vector_store, mock_hybrid_retriever, mock_configs
    ):
        """Test template generation with RAG context"""
        service = NucleiTemplateService()

        template = service._generate_template_with_llm("Create SQL injection template")

        # Verify RAG was used
        assert mock_hybrid_retriever.hybrid_search.called

        # Verify LLM was invoked
        assert mock_llm.get_llm.return_value.invoke.called

        # Verify template was cleaned up
        assert not template.startswith("```")
        assert not template.endswith("```")
        assert "id: test-template" in template

    def test_generate_template_without_rag(
        self, mock_llm, mock_vector_store, mock_hybrid_retriever, mock_configs
    ):
        """Test template generation when RAG returns empty"""
        service = NucleiTemplateService()

        # Mock empty RAG results
        mock_hybrid_retriever.hybrid_search.return_value = []

        template = service._generate_template_with_llm("Create test template")

        # Verify template was still generated
        assert "id: test-template" in template

    def test_create_template_grpc_endpoint_success(
        self, mock_llm, mock_vector_store, mock_hybrid_retriever, mock_configs
    ):
        """Test successful gRPC endpoint call"""
        service = NucleiTemplateService()

        request = assistant_pb2.CreateTemplateRequest(
            question="Create a template to detect SQL injection"
        )
        context = Mock()

        response = service.CreateTemplate(request, context)

        assert response.answer
        assert "id: test-template" in response.answer
        assert not context.set_code.called  # No error

    def test_create_template_grpc_empty_question(
        self, mock_llm, mock_vector_store, mock_hybrid_retriever, mock_configs
    ):
        """Test gRPC endpoint with empty question"""
        service = NucleiTemplateService()

        request = assistant_pb2.CreateTemplateRequest(question="   ")
        context = Mock()

        response = service.CreateTemplate(request, context)

        assert response.answer == ""
        context.set_code.assert_called_once_with(grpc.StatusCode.INVALID_ARGUMENT)
        context.set_details.assert_called_once_with("Question is required and cannot be empty")

    def test_create_template_grpc_llm_error(
        self, mock_llm, mock_vector_store, mock_hybrid_retriever, mock_configs
    ):
        """Test gRPC endpoint when LLM fails"""
        service = NucleiTemplateService()

        # Mock LLM error
        mock_llm.get_llm.return_value.invoke.side_effect = Exception("LLM API error")

        request = assistant_pb2.CreateTemplateRequest(
            question="Create test template"
        )
        context = Mock()

        response = service.CreateTemplate(request, context)

        assert "Error generating template" in response.answer
        context.set_code.assert_called_once_with(grpc.StatusCode.INTERNAL)

    def test_template_cleanup_various_formats(
        self, mock_llm, mock_vector_store, mock_hybrid_retriever, mock_configs
    ):
        """Test template cleanup with various markdown formats"""
        service = NucleiTemplateService()

        test_cases = [
            ("```yaml\nid: test\n```", "id: test"),
            ("```\nid: test\n```", "id: test"),
            ("id: test", "id: test"),
            ("```yaml\nid: test", "id: test"),
        ]

        for input_template, expected in test_cases:
            # Mock LLM response
            mock_response = Mock()
            mock_response.content = input_template
            mock_llm.get_llm.return_value.invoke.return_value = mock_response

            result = service._generate_template_with_llm("test")
            assert result.strip() == expected.strip()

    def test_rag_context_formatting(
        self, mock_llm, mock_vector_store, mock_hybrid_retriever, mock_configs
    ):
        """Test RAG context is properly formatted"""
        service = NucleiTemplateService()

        context = service._retrieve_similar_templates("test", k=2)

        # Check formatting
        assert "Here are some similar Nuclei templates for reference:" in context
        assert "1. Template:" in context
        assert "Description:" in context
        assert "Similarity Score:" in context

    def test_hybrid_search_parameters(
        self, mock_llm, mock_vector_store, mock_hybrid_retriever, mock_configs
    ):
        """Test hybrid search is called with correct parameters"""
        service = NucleiTemplateService()

        service._retrieve_similar_templates("test query", k=5)

        mock_hybrid_retriever.hybrid_search.assert_called_once_with(
            table="nuclei_templates",
            qtext="test query",
            k=5,
            id_col="template_id",
            title_col="name",
            content_col="description",
            embedding_col="embedding",
            tsv_col="tsv"
        )


class TestNucleiTemplateServiceIntegration:
    """Integration tests for the full workflow"""

    def test_full_workflow_with_rag(
        self, mock_llm, mock_vector_store, mock_hybrid_retriever, mock_configs
    ):
        """Test complete workflow from gRPC request to response with RAG"""
        service = NucleiTemplateService()

        # Create request
        request = assistant_pb2.CreateTemplateRequest(
            question="Create a nuclei template to detect Apache Struts RCE"
        )
        context = Mock()

        # Execute
        response = service.CreateTemplate(request, context)

        # Verify workflow
        # 1. RAG retrieval was attempted
        assert mock_hybrid_retriever.hybrid_search.called

        # 2. LLM was invoked with enhanced context
        llm_call = mock_llm.get_llm.return_value.invoke.call_args
        assert llm_call is not None

        # 3. Response is valid YAML template
        assert response.answer
        assert "id:" in response.answer
        assert "info:" in response.answer

        # 4. No errors
        assert not context.set_code.called

    def test_degradation_when_rag_fails(
        self, mock_llm, mock_vector_store, mock_hybrid_retriever, mock_configs
    ):
        """Test service still works when RAG fails"""
        service = NucleiTemplateService()

        # Mock RAG failure
        mock_hybrid_retriever.hybrid_search.side_effect = Exception("DB error")

        request = assistant_pb2.CreateTemplateRequest(
            question="Create test template"
        )
        context = Mock()

        # Should still work without RAG
        response = service.CreateTemplate(request, context)

        assert response.answer
        assert "id: test-template" in response.answer
        assert not context.set_code.called

    @patch('app.services.nuclei_template.NucleiGenerationPrompts')
    def test_prompt_enhancement_with_rag(
        self, mock_prompts, mock_llm, mock_vector_store,
        mock_hybrid_retriever, mock_configs
    ):
        """Test that prompt is enhanced with RAG context"""
        service = NucleiTemplateService()

        # Mock prompt generation
        mock_prompts.get_nuclei_template_generation_prompt.return_value = "Enhanced prompt"

        service._generate_template_with_llm("Create SQL injection template")

        # Verify prompt was called with enhanced question
        call_args = mock_prompts.get_nuclei_template_generation_prompt.call_args
        enhanced_question = call_args.kwargs['question']

        # Should contain original question + RAG context
        assert "Create SQL injection template" in enhanced_question
        assert "Here are some similar Nuclei templates for reference:" in enhanced_question
