from data.embeddings.embeddings import Embeddings
from data.embeddings.models.base_model import EmbeddingConfig


cli = Embeddings.create_embedding(
    "sentence_transformer",
    config=EmbeddingConfig(name="sentence-transformers/all-MiniLM-L6-v2"),
)

# 2. Sinh vector
texts = ["Xin chào", "Hello world"]
vecs = cli.encode(["hello world", "xin chào"])
print(len(vecs), len(vecs[0])) 
