from typing import List
from .base import APIBaseEmbedding

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None

from common.config import EmbeddingConfigs

class OpenAIEmbedding(APIBaseEmbedding):
    def __init__(
        self,
        embedding_settings: EmbeddingConfigs,
    ):
        # Check if the openai library is available
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI library is not available. Please install it with 'pip install openai'")
            
        self.embedding_settings = embedding_settings

        super().__init__(name=self.embedding_settings.model_name, apiKey=self.embedding_settings.api_key)

        if not self.embedding_settings.api_key:
            raise ValueError("The OpenAI API key must not be 'None'.")

        try:
            self.client = openai.OpenAI(api_key=self.embedding_settings.api_key)
        except Exception as e:
            raise ValueError(
                f"OpenAI client failed to initialize. Error: {e}"
            ) from e

    def encode(self, docs: List[str]) -> List[List[float]]:
        # Kiểm tra xem openai có khả dụng không
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI library is not available. Please install it with 'pip install openai'")
            
        try:
            response = self.client.embeddings.create(
                model=self.embedding_settings.model_name,
                input=docs
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            raise ValueError(f"Failed to get embeddings. Error details: {e}") from e

    @staticmethod
    def _default_dim(model_name: str) -> int:
        if "large" in model_name:
            return 3072
        if "small" in model_name:
            return 1536
        return 1536

    @property
    def dim(self) -> int:
        return self.embedding_settings.dimensions or self._default_dim(self.embedding_settings.model_name)