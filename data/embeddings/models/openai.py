import os
from typing import List
from .base_model import APIBaseEmbedding
from openai import OpenAI  # dùng OpenAI client mới
from dotenv import load_dotenv

load_dotenv()

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
            self.client = OpenAI(
                base_url=self.baseUrl, api_key=self.apiKey, organization=self.orgId
            )
        except Exception as e:
            raise ValueError(
                f"OpenAI API client failed to initialize. Error: {e}"
            ) from e

    # ---- public API ----
    def encode(self, docs: List[str]) -> List[List[float]]:
        try:
            resp = self.client.embeddings.create(
                input=docs,
                model=self.name,
                dimensions=self.dimensions,
            )
            return [d.embedding for d in resp.data]
        except Exception as e:
            raise ValueError(f"Failed to get embeddings. Error details: {e}") from e

    # ---- helpers ----
    @staticmethod
    def _default_dim(model_name: str) -> int:
        """Map model -> default dim nếu user không chỉ định."""
        if "large" in model_name:
            return 3072
        if "small" in model_name:
            return 1536
        # fallback
        return 1536

    @property
    def dim(self) -> int:
        return self.dimensions
