from typing import List
from .base import APIBaseEmbedding
from common.config import EmbeddingConfigs
import google.generativeai as genai


class GoogleEmbedding(APIBaseEmbedding):
    """Google embedding model wrapper"""

    def __init__(
        self,
        embedding_settings: EmbeddingConfigs,
    ):
        # Initialize parent class (sets self.embedding_settings, self.api_key, etc.)
        super().__init__(embedding_settings)

        if not self.api_key:
            raise ValueError("Google API key must not be None")

        try:
            genai.configure(api_key=self.api_key)
            self.client = genai
        except ImportError:
            raise ImportError(
                "Required packages not installed. Run:\n"
                "pip install google-generativeai"
            )
        except Exception as e:
            raise ValueError(f"Failed to initialize Google client: {str(e)}")

    def encode(self, docs: List[str]) -> List[List[float]]:
        """Generate embeddings for input texts"""
        try:
            embeddings = []
            for doc in docs:
                result = self.client.embed_content(
                    model=self.embedding_settings.model_name,
                    content=doc
                )
                embeddings.append(result['embedding'])
            return embeddings
        except Exception as e:
            raise ValueError(f"Google embedding generation failed: {str(e)}")

    @property 
    def dim(self) -> int:
        """Get embedding dimension"""
        return self.embedding_settings.dimensions or 768