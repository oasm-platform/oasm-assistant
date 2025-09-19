##https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/text-embeddings


from typing import List, Optional
from .base_model import APIBaseEmbedding
from common.config.settings import Settings

class GoogleEmbedding(APIBaseEmbedding):
    """Google Cloud AI Platform embedding model wrapper"""
    
    def __init__(
        self,
        settings: Settings = None,
        name: str = None,
        apiKey: str = None,
    ):
        # Use settings if provided, otherwise create new Settings
        self.settings = settings or Settings()
        config = self.settings.google_embedding

        # Override config with explicit parameters
        self.name = name or config.model_name
        self.apiKey = apiKey or config.api_key

        super().__init__(name=self.name, apiKey=self.apiKey)

        if not self.apiKey:
            raise ValueError("Google API key must not be None")

        try:
            from google.cloud import aiplatform
            from vertexai.language_models import TextEmbeddingModel
            self.TextEmbeddingModel = TextEmbeddingModel
        except ImportError:
            raise ImportError(
                "Required packages not installed. Run:\n"
                "pip install google-cloud-aiplatform"
            )

        try:
            # Initialize client
            aiplatform.init(api_key=self.apiKey)
            self.client = self.TextEmbeddingModel.from_pretrained(self.name)
        except Exception as e:
            raise ValueError(f"Failed to initialize Google client: {str(e)}")

    def encode(self, docs: List[str]) -> List[List[float]]:
        """Generate embeddings for input texts
        
        Args:
            docs: List of input texts
            
        Returns:
            List of embedding vectors
            
        Raises:
            ValueError: If API call fails
        """
        try:
            embeddings = self.client.get_embeddings(docs)
            return [embedding.values for embedding in embeddings]
        except Exception as e:
            raise ValueError(f"Google embedding generation failed: {str(e)}")

    @property 
    def dim(self) -> int:
        """Get embedding dimension"""
        # Default dimensions for Google models
        dims = {
            "textembedding-gecko": 768,
            "textembedding-gecko-multilingual": 768,
            "textembedding-gecko@001": 768,
            "textembedding-gecko@002": 768,
            "textembedding-gecko@003": 768
        }
        return dims.get(self.name, 768)
