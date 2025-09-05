import os
from typing import List
from .base_model import APIBaseEmbedding
from llama_index.embeddings.openai import OpenAIEmbedding as LlamaOpenAIEmbedding

class OpenAIEmbedding(APIBaseEmbedding):
    def __init__(
        self,
        name: str = "text-embedding-3-small",
        dimensions: int | None = None,
        token_limit: int = 8192,
        baseUrl: str | None = None,
        apiKey: str | None = None,
        orgId: str | None = None,
    ):
        super().__init__(name=name, baseUrl=baseUrl, apiKey=apiKey)
        self.name = name
        self.dimensions = dimensions or self._default_dim(name)
        self.token_limit = token_limit

        self.apiKey = apiKey or os.getenv("OPENAI_API_KEY")
        self.orgId = orgId or os.getenv("OPENAI_ORG_ID")
        self.baseUrl = baseUrl or os.getenv("OPENAI_BASE_URL")

        if not self.apiKey:
            raise ValueError("The OpenAI API key must not be 'None'.")

        try:
            self.client = LlamaOpenAIEmbedding(
                api_key=self.apiKey,
                model=self.name,
                organization=self.orgId,
                base_url=self.baseUrl,
            )
        except Exception as e:
            raise ValueError(
                f"LlamaIndex OpenAIEmbedding client failed to initialize. Error: {e}"
            ) from e

    def encode(self, docs: List[str]) -> List[List[float]]:
        try:
            embeddings = self.client.get_text_embedding(docs)
            return embeddings
        except Exception as e:
            raise ValueError(f"Failed to get embeddings. Error details: {e}") from e

    @staticmethod
    def _default_dim(model_name: str) -> int:
        """Map model -> default dim nếu user không chỉ định."""
        if "large" in model_name:
            return 3072
        if "small" in model_name:
            return 1536
        return 1536

    @property
    def dim(self) -> int:
        return self.dimensions
