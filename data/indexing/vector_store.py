"""
Vector database management
"""
from data.database.chroma_database import ChromaDatabase

class VectorStore:

    def __init__(self, host="localhost", port=8000):

        self.db = ChromaDatabase(host=host, port=port)

    def insert_data(self, collection_name: str, documents: list, metadatas: list = None, embeddings: list = None):
        self.db.create_collection(name=collection_name)
        self.db.add_documents(
            collection_name=collection_name,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings
        )
        print(f"Inserted {len(documents)} documents into collection '{collection_name}'.")
