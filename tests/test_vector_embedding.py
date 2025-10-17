"""
Test vector embedding fixes: database schema, singleton pattern, and vector operations
"""
import pytest
from sqlalchemy import text


class TestVectorEmbedding:
    """Test suite for vector embedding functionality"""

    def test_database_schema_vector_type(self):
        """Test that embedding column uses vector type (not double precision[])"""
        from data.database.database import PostgresDatabase
        from common.config.configs import Configs

        configs = Configs()
        db = PostgresDatabase(configs.postgres.url)

        with db.get_session() as session:
            result = session.execute(text("""
                SELECT udt_name
                FROM information_schema.columns
                WHERE table_name = 'nuclei_templates' AND column_name = 'embedding'
            """))
            row = result.fetchone()

            assert row is not None, "Embedding column not found"
            assert row[0] == 'vector', f"Expected 'vector' type, got '{row[0]}'"

    def test_singleton_embedding_model(self):
        """Test that embedding model is singleton (same instance)"""
        from data.embeddings import get_embedding_model

        model1 = get_embedding_model()
        model2 = get_embedding_model()

        assert model1 is model2, "Embedding models should be the same instance"

    def test_vector_cast_in_query(self):
        """Test that vector casting works in SQL queries"""
        from data.database.database import PostgresDatabase
        from common.config.configs import Configs
        from data.embeddings import get_embedding_model

        configs = Configs()
        db = PostgresDatabase(configs.postgres.url)
        embedding_model = get_embedding_model()

        # Generate test embedding
        test_embedding = embedding_model.encode("test")
        if hasattr(test_embedding, 'tolist'):
            test_embedding = test_embedding.tolist()

        embedding_str = '[' + ','.join(str(float(x)) for x in test_embedding) + ']'

        # Test CAST syntax works
        with db.get_session() as session:
            query = text("""
                SELECT CAST(:qvec AS vector) <=> CAST(:qvec AS vector) as distance
            """)
            result = session.execute(query, {"qvec": embedding_str})
            row = result.fetchone()

            # Distance to itself should be ~0
            assert row[0] < 0.0001, f"Distance should be ~0, got {row[0]}"

    def test_hybrid_search_execution(self):
        """Test that hybrid search executes without errors"""
        from app.services.nuclei_template import NucleiTemplateService

        service = NucleiTemplateService()

        # Should not raise exception (even if table is empty)
        results = service._retrieve_similar_templates("SQL injection", k=3)

        assert isinstance(results, (list, str)), "Results should be list or string"
