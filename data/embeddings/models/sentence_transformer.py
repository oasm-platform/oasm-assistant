from typing import List
from .base import BaseEmbedding
from sentence_transformers import SentenceTransformer
from common.config import EmbeddingConfigs

class SentenceTransformerEmbedding(BaseEmbedding):
    def __init__(self, embedding_settings: EmbeddingConfigs):  
        # Initialize parent class with the correct name
        super().__init__("sentence_transformer")
        self.embedding_settings = embedding_settings  
        self.embedding_model = None
        try:
            print(f"Loading SentenceTransformer model: {self.embedding_settings.model_name}")
            self.embedding_model = SentenceTransformer(self.embedding_settings.model_name, trust_remote_code=True)
            print(f"Successfully loaded model: {self.embedding_settings.model_name}")
        except Exception as e:
            print(f"Failed to load model '{self.embedding_settings.model_name}': {e}")
            # Try fallback to a known working model
            try:
                print("Trying fallback model: all-MiniLM-L6-v2")
                self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2", trust_remote_code=True)
                print("Successfully loaded fallback model")
            except Exception as e2:
                raise ValueError(f"Failed to load both primary and fallback models: {e}, {e2}")

    def encode(self, docs: List[str]) -> List[List[float]]:
        if self.embedding_model is None:
            raise ValueError("SentenceTransformer model is not properly initialized")
        
        embeddings = self.embedding_model.encode(docs)
        if hasattr(embeddings, 'tolist'):
            return embeddings.tolist()
        else:
            return embeddings.astype(float).tolist()
    
    @property
    def dim(self) -> int:
        return self.embedding_model.get_sentence_embedding_dimension()