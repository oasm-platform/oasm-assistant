from typing import List
import os
from .base import BaseEmbedding
from sentence_transformers import SentenceTransformer
from common.config.configs import EmbeddingConfigs

class SentenceTransformerEmbedding(BaseEmbedding):
    def __init__(self, embedding_settings: EmbeddingConfigs):
        # Initialize parent class with the correct name
        super().__init__("sentence_transformer")
        self.embedding_settings = embedding_settings
        self.embedding_model = None
        
        # Extract model name without namespace for fallback
        model_name = self.embedding_settings.model_name
        if "/" in model_name:
            # Extract just the model name part (e.g., "all-MiniLM-L6-v2" from "sentence-transformers/all-MiniLM-L6-v2")
            base_model_name = model_name.split("/")[-1]
        else:
            base_model_name = model_name
            
        # Define local path for model as fallback
        local_model_path = os.path.join("models", base_model_name)
        
        try:
            print(f"Loading SentenceTransformer model: {model_name}")
            # Increase timeout and configure retry settings
            self.embedding_model = SentenceTransformer(
                model_name,
                trust_remote_code=True,
                # Try to use local model first if available
                local_files_only=False
            )
            print(f"Successfully loaded model: {model_name}")
        except Exception as e:
            print(f"Failed to load model '{model_name}': {e}")
            # Try loading from local path if it exists
            try:
                if os.path.exists(local_model_path):
                    print(f"Trying local model path: {local_model_path}")
                    self.embedding_model = SentenceTransformer(
                        local_model_path,
                        trust_remote_code=True,
                        local_files_only=True
                    )
                    print("Successfully loaded local model")
                else:
                    # Try fallback to base model name
                    print(f"Trying fallback model: {base_model_name}")
                    self.embedding_model = SentenceTransformer(
                        base_model_name,
                        trust_remote_code=True,
                        local_files_only=False
                    )
                    print("Successfully loaded fallback model")
            except Exception as e2:
                # Final fallback to a basic model that's likely cached
                try:
                    print("Trying final fallback to cached 'all-MiniLM-L6-v2' model")
                    self.embedding_model = SentenceTransformer(
                        "all-MiniLM-L6-v2",
                        trust_remote_code=True,
                        local_files_only=True  # Only use cached/local version
                    )
                    print("Successfully loaded cached fallback model")
                except Exception as e3:
                    raise ValueError(f"Failed to load model from primary source: {model_name}, local path: {local_model_path}, and all fallbacks: {e}, {e2}, {e3}")

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