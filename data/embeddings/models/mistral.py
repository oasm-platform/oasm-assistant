from typing import List
from .base import APIBaseEmbedding
from mistralai.client import MistralClient
from common.config import EmbeddingConfigs

class MistralEmbedding(APIBaseEmbedding):
    def __init__(
            self,
            embedding_settings: EmbeddingConfigs,
        ):
        # Initialize parent class (sets self.embedding_settings, self.api_key, etc.)
        super().__init__(embedding_settings)

        if not self.api_key:
            raise ValueError("The Mistral API key must not be 'None'.")
        
        try:
            self.client = MistralClient(api_key=self.api_key)
        except Exception as e:
            raise ValueError(
                f"Mistral API client failed to initialize. Error: {e}"
            ) from e

    def encode(self, docs: List[str]) -> List[List[float]]:
        try:
            embeds = self.client.embeddings(
                    input=docs,
                    model=self.embedding_settings.model_name,
                )
            embeddings = [embeds_obj.embedding for embeds_obj in embeds.data]
            return embeddings
        except Exception as e:
            raise ValueError(
                f"Failed to get embeddings. Error details: {e}"
            ) from e

    @property
    def dim(self) -> int:
        return self.embedding_settings.dimensions or 1024