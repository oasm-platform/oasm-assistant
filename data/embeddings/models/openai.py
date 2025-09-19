from typing import List
from .base_model import APIBaseEmbedding
from llama_index.embeddings.openai import OpenAIEmbedding as LlamaOpenAIEmbedding
from common.config.settings import Settings

class OpenAIEmbedding(APIBaseEmbedding):
    def __init__(
        self,
        settings: Settings = None,
        name: str = None,
        dimensions: int = None,
        token_limit: int = None,
        baseUrl: str = None,
        apiKey: str = None,
        orgId: str = None,
    ):
        # Use settings if provided, otherwise create new Settings
        self.settings = settings or Settings()
        config = self.settings.openai

        # Override config with explicit parameters if provided
        self.name = name or config.model_name
        self.dimensions = dimensions or config.dimensions
        self.token_limit = token_limit or config.token_limit
        self.apiKey = apiKey or config.api_key
        self.orgId = orgId or config.org_id
        self.baseUrl = baseUrl or config.base_url

        super().__init__(name=self.name, baseUrl=self.baseUrl, apiKey=self.apiKey)

        if not self.apiKey:
            raise ValueError("The OpenAI API key must not be 'None'.")

        # Build client kwargs
        ctor_kwargs = self._build_client_kwargs()
        
        try:
            self.client = LlamaOpenAIEmbedding(**ctor_kwargs)
        except Exception as e:
            raise ValueError(
                f"LlamaIndex OpenAIEmbedding client failed to initialize with {ctor_kwargs}. Error: {e}"
            ) from e

    def encode(self, docs: List[str]) -> List[List[float]]:
        try:
            # Try common APIs across LlamaIndex versions
            if hasattr(self.client, "get_text_embedding_batch"):
                return self.client.get_text_embedding_batch(docs)
            if hasattr(self.client, "get_text_embedding"):
                first = self.client.get_text_embedding(docs[0])
                if isinstance(first, list):
                    rest = [self.client.get_text_embedding(t) for t in docs[1:]]
                    return [first, *rest]
                return [self.client.get_text_embedding(t)["embedding"] for t in docs]
            if hasattr(self.client, "embed"):
                return self.client.embed(texts=docs)
            raise RuntimeError("No compatible embedding method found on client.")
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
        return self.dimensions
