import sys
import os

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from data.embeddings.embeddings import Embeddings

# Create embedding client
cli = Embeddings.create_embedding(
    "sentence_transformer",
    model_name="sentence-transformers/all-MiniLM-L6-v2",
)

# Generate vectors
texts = ["Xin chào", "Hello world"]
vecs = cli.encode(texts)
print(len(vecs), len(vecs[0]))