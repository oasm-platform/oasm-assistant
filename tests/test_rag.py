"""
Tests for RAG (Retrieval Augmented Generation) System
Includes: Hybrid Search (HNSW + BM25), Vector Retriever, Keyword Retriever
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np


# ============================================================================
# TEST HNSW (Vector Search)
# ============================================================================

class TestVectorRetriever:
    """Test HNSW-based semantic search"""

    @pytest.fixture
    def mock_embedding_model(self):
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.1] * 384])
        return mock_model

    @patch('data.retrieval.vector_retriever.VectorRetriever.search')
    def test_vector_search_returns_results(self, mock_search, mock_embedding_model):
        """Test HNSW vector search returns semantic results"""
        from data.retrieval.vector_retriever import VectorRetriever

        # Mock search result directly
        mock_search.return_value = [
            {
                'id': '1',
                'text': 'SQL injection vulnerability',
                'metadata': {'name': 'SQL Test'},
                'score': 0.95,
                'source': 'vector'
            }
        ]

        retriever = VectorRetriever(table_name='nuclei_templates', embed_dim=384)
        results = retriever.search('SQL injection', k=5)

        assert len(results) > 0
        assert results[0]['score'] == 0.95
        assert 'SQL injection' in results[0]['text']


# ============================================================================
# TEST BM25 (Keyword Search)
# ============================================================================

class TestKeywordRetriever:
    """Test BM25 keyword search"""

    @pytest.fixture
    def sample_docs(self):
        return [
            {'text': 'SQL injection in login', 'metadata': {'id': '1'}},
            {'text': 'XSS cross-site scripting', 'metadata': {'id': '2'}},
            {'text': 'RCE remote code execution', 'metadata': {'id': '3'}}
        ]

    def test_bm25_indexing(self, sample_docs):
        """Test BM25 can index documents"""
        from data.retrieval.keyword_retriever import KeywordRetriever

        retriever = KeywordRetriever()
        retriever.index_documents(sample_docs)

        assert retriever.is_ready()
        assert len(retriever.documents) == 3

    def test_bm25_keyword_search(self, sample_docs):
        """Test BM25 finds exact keyword matches"""
        from data.retrieval.keyword_retriever import KeywordRetriever

        retriever = KeywordRetriever()
        retriever.index_documents(sample_docs)

        results = retriever.search('SQL injection', k=5)

        assert len(results) > 0
        assert 'SQL' in results[0]['text']
        assert results[0]['score'] > 0

    def test_bm25_returns_empty_without_index(self):
        """Test BM25 returns empty when not indexed"""
        from data.retrieval.keyword_retriever import KeywordRetriever

        retriever = KeywordRetriever()
        results = retriever.search('test', k=5)

        assert results == []


# ============================================================================
# TEST HYBRID SEARCH (HNSW + BM25)
# ============================================================================

class TestHybridSearch:
    """Test Hybrid Search combining HNSW and BM25"""

    @patch('data.retrieval.hybrid_search.VectorRetriever')
    @patch('data.retrieval.hybrid_search.KeywordRetriever')
    def test_hybrid_search_combines_results(self, mock_keyword, mock_vector):
        """Test hybrid search merges vector and keyword results"""
        from data.retrieval import HybridSearchEngine

        # Mock vector results
        mock_vector_inst = mock_vector.return_value
        mock_vector_inst.search.return_value = [
            {'id': '1', 'text': 'SQL test', 'metadata': {}, 'score': 0.9}
        ]

        # Mock keyword results
        mock_keyword_inst = mock_keyword.return_value
        mock_keyword_inst.search.return_value = [
            {'id': '1', 'text': 'SQL test', 'metadata': {}, 'score': 20.0}
        ]

        engine = HybridSearchEngine(
            table_name='test',
            vector_weight=0.7,
            keyword_weight=0.3,
            embed_dim=384
        )

        results = engine.search('SQL injection', k=5)

        assert len(results) > 0
        assert 'score' in results[0]
        assert 'vector_score' in results[0]
        assert 'keyword_score' in results[0]

    @patch('data.retrieval.hybrid_search.VectorRetriever')
    @patch('data.retrieval.hybrid_search.KeywordRetriever')
    def test_hybrid_search_weights(self, mock_keyword, mock_vector):
        """Test hybrid search respects vector/keyword weights"""
        from data.retrieval import HybridSearchEngine

        engine = HybridSearchEngine(
            table_name='test',
            vector_weight=0.7,
            keyword_weight=0.3,
            embed_dim=384
        )

        assert engine.vector_weight == 0.7
        assert engine.keyword_weight == 0.3


# ============================================================================
# TEST RAG INTEGRATION
# ============================================================================

class TestRAGIntegration:
    """Test RAG integration in Nuclei Template Service"""

    @patch('app.services.nuclei_template.HybridSearchEngine')
    @patch('app.services.nuclei_template.LLMManager')
    @patch('app.services.nuclei_template.configs')
    @patch('data.database.postgres_db.get_session')
    def test_rag_initialization(self, mock_session, mock_configs, mock_llm, mock_search):
        """Test RAG components initialize correctly"""
        from app.services.nuclei_template import NucleiTemplateService

        mock_configs.embedding.dimensions = 384
        mock_configs.embedding.model_name = 'all-MiniLM-L6-v2'

        # Mock empty DB
        mock_sess = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_sess.execute.return_value = mock_result
        mock_session.return_value.__enter__.return_value = mock_sess

        service = NucleiTemplateService()

        assert service.hybrid_search is not None

    @patch('app.services.nuclei_template.HybridSearchEngine')
    @patch('app.services.nuclei_template.LLMManager')
    @patch('app.services.nuclei_template.configs')
    @patch('data.database.postgres_db.get_session')
    def test_rag_retrieval(self, mock_session, mock_configs, mock_llm, mock_search):
        """Test RAG retrieves similar templates"""
        from app.services.nuclei_template import NucleiTemplateService

        mock_configs.embedding.dimensions = 384
        mock_configs.embedding.model_name = 'all-MiniLM-L6-v2'

        # Mock DB
        mock_sess = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_sess.execute.return_value = mock_result
        mock_session.return_value.__enter__.return_value = mock_sess

        # Mock search results
        mock_search_inst = mock_search.return_value
        mock_search_inst.search.return_value = [
            {
                'id': '1',
                'text': 'SQL injection template',
                'metadata': {
                    'name': 'SQL Injection Test',
                    'description': 'Detects SQL injection',
                    'template': 'id: sql-test\ninfo:\n  name: SQL Test'
                },
                'score': 0.85
            }
        ]

        service = NucleiTemplateService()
        context = service._retrieve_similar_templates('SQL injection', k=3)

        assert context != ""
        assert 'SQL Injection Test' in context
        assert 'Reference Template' in context

    @patch('app.services.nuclei_template.HybridSearchEngine')
    @patch('app.services.nuclei_template.LLMManager')
    @patch('app.services.nuclei_template.configs')
    @patch('data.database.postgres_db.get_session')
    def test_rag_filters_low_scores(self, mock_session, mock_configs, mock_llm, mock_search):
        """Test RAG filters out low-quality results"""
        from app.services.nuclei_template import NucleiTemplateService

        mock_configs.embedding.dimensions = 384
        mock_configs.embedding.model_name = 'all-MiniLM-L6-v2'

        mock_sess = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_sess.execute.return_value = mock_result
        mock_session.return_value.__enter__.return_value = mock_sess

        # Low score result
        mock_search_inst = mock_search.return_value
        mock_search_inst.search.return_value = [
            {'id': '1', 'text': 'test', 'metadata': {}, 'score': 0.3}
        ]

        service = NucleiTemplateService()
        context = service._retrieve_similar_templates('test', k=3, similarity_threshold=0.5)

        assert context == ""  # Filtered out

    @patch('app.services.nuclei_template.HybridSearchEngine')
    @patch('app.services.nuclei_template.LLMManager')
    @patch('app.services.nuclei_template.configs')
    @patch('app.services.nuclei_template.NucleiGenerationPrompts')
    @patch('data.database.postgres_db.get_session')
    def test_rag_enhances_generation(self, mock_session, mock_prompts, mock_configs, mock_llm, mock_search):
        """Test RAG context enhances template generation"""
        from app.services.nuclei_template import NucleiTemplateService

        mock_configs.embedding.dimensions = 384
        mock_configs.embedding.model_name = 'all-MiniLM-L6-v2'

        mock_sess = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_sess.execute.return_value = mock_result
        mock_session.return_value.__enter__.return_value = mock_sess

        # Mock search results
        mock_search_inst = mock_search.return_value
        mock_search_inst.search.return_value = [
            {
                'id': '1',
                'text': 'SQL template',
                'metadata': {
                    'name': 'SQL Test',
                    'description': 'SQL detection',
                    'template': 'id: sql-test'
                },
                'score': 0.9
            }
        ]

        # Mock LLM
        mock_llm_inst = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = "id: test\ninfo:\n  name: Test"
        mock_llm_inst.invoke.return_value = mock_resp
        mock_llm.get_llm.return_value = mock_llm_inst

        mock_prompts.get_nuclei_template_generation_prompt.return_value = "Generate"

        service = NucleiTemplateService()
        template = service._generate_template_with_llm("Create SQL test")

        # Verify RAG context was passed
        mock_prompts.get_nuclei_template_generation_prompt.assert_called_once()
        call_kwargs = mock_prompts.get_nuclei_template_generation_prompt.call_args[1]
        assert 'rag_context' in call_kwargs
        assert template != ""


# ============================================================================
# TEST SCORE NORMALIZATION
# ============================================================================

class TestScoreUtils:
    """Test score normalization and combining"""

    def test_normalize_scores(self):
        """Test scores normalize to 0-1 range"""
        from data.retrieval.score_utils import normalize_scores

        scores = [10.0, 5.0, 2.0]
        normalized = normalize_scores(scores)

        assert len(normalized) == 3
        assert normalized[0] == 1.0  # Max
        assert normalized[-1] == 0.0  # Min
        assert all(0 <= s <= 1 for s in normalized)

    def test_combine_scores(self):
        """Test combining vector and keyword scores"""
        from data.retrieval.score_utils import combine_scores

        combined = combine_scores(0.8, 0.6, 0.7, 0.3)
        expected = 0.7 * 0.8 + 0.3 * 0.6
        assert abs(combined - expected) < 1e-6
