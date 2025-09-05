"""
Vector database management
"""
from common.logger import logger
from data.database.chroma_database import ChromaDatabase


class VectorStore:
    def __init__(self, host="localhost", port=8000):
        self.db = ChromaDatabase(host=host, port=port)
        logger.info(f"Initialized VectorStore with host={host}, port={port}")

    def insert_data(self, collection_name: str, documents: list, metadatas: list = None, embeddings: list = None):
        try:
            logger.info(f"Starting data insertion into collection '{collection_name}'")
            logger.debug(f"Documents: {documents}")
            logger.debug(f"Metadata: {metadatas}")
            logger.debug(f"Embeddings: {embeddings}")

            self.db.create_collection(name=collection_name)
            logger.info(f"Collection '{collection_name}' created or already exists.")

            self.db.add_documents(
                collection_name=collection_name,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings
            )
            logger.info(f"Successfully inserted {len(documents)} documents into collection '{collection_name}'.")

        except Exception as e:
            logger.error(f"Failed to insert data into collection '{collection_name}'. Error: {e}")
            raise
