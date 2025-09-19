import os
from typing import List
from .base_model import APIBaseEmbedding
from mistralai.client import MistralClient
from common.config.settings import Settings

class MistralEmbedding(APIBaseEmbedding):
    def __init__(
            self,
            settings: Settings = None,
            name: str = None,
            dimensions: int = None,
            apiKey: str = None,
        ):
        # Use settings if provided, otherwise create new Settings
        self.settings = settings or Settings()
        config = self.settings.mistral

        # Override config with explicit parameters if provided
        self.name = name or config.model_name
        self.dimensions = dimensions or config.dimensions
        self.apiKey = apiKey or config.api_key

        super().__init__(name=self.name, apiKey=self.apiKey)
        
        if not self.apiKey:
            raise ValueError("The Mistral API key must not be 'None'.")
        
        try:
            self.client = MistralClient(api_key=self.apiKey)
        except Exception as e:
            raise ValueError(
                f"Mistral API client failed to initialize. Error: {e}"
            ) from e

    def encode(self, docs: List[str]):
        try:
            embeds = self.client.embeddings(
                    input=docs,
                    model=self.name,
                )
            embeddings = [embeds_obj.embedding for embeds_obj in embeds.data]
            return embeddings
        except Exception as e:
            raise ValueError(
                f"Failed to get embeddings. Error details: {e}"
            ) from e

    @property
    def dim(self) -> int:
        return self.dimensions