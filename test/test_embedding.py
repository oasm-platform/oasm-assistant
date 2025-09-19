from data.embeddings.embeddings import Embeddings
from data.embeddings.models.base_model import EmbeddingConfig
from common.config.settings import Settings

# Initialize settings
settings = Settings()

# Create embedding client
cli = Embeddings.create_embedding(
    "sentence_transformer",
    config=EmbeddingConfig(name="sentence-transformers/all-MiniLM-L6-v2"),
    settings=settings
)

# Generate vectors
texts = ["Xin chào", "Hello world"]
vecs = cli.encode(texts)
print(len(vecs), len(vecs[0]))
