import os, inspect
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

        # --- Build kwargs robustly based on the constructor signature ---
        sig = inspect.signature(LlamaOpenAIEmbedding.__init__)
        params = sig.parameters

        def pick(*names, value=None):
            for n in names:
                if n in params:
                    return n, value
            return None

        ctor_kwargs = {}
        for cand in [
            pick("apiKey", "api_key", value=self.apiKey),
            pick("model_name", "model", value=self.name),
            pick("organization", "org_id", "orgId", value=self.orgId),
            pick("base_url", "api_base", "apiBase", value=self.baseUrl),
        ]:
            if cand and cand[1] is not None:
                ctor_kwargs[cand[0]] = cand[1]

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
                # một số bản chỉ nhận str -> lặp qua
                first = self.client.get_text_embedding(docs[0])
                if isinstance(first, list):
                    rest = [self.client.get_text_embedding(t) for t in docs[1:]]
                    return [first, *rest]
                # fallback: có bản trả dict
                return [self.client.get_text_embedding(t)["embedding"] for t in docs]
            if hasattr(self.client, "embed"):
                # đôi khi API là .embed(texts=[...])
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
