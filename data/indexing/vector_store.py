"""
Vector database management with optimized connection handling
"""
from typing import List, Dict, Any, Optional
from common.logger import logger
from data.database.chroma_database import ChromaDatabase


class VectorStore:
    _instance = None
    _db = None
    
    def __new__(cls, host: str = "localhost", port: int = 8000, 
               persist_directory: Optional[str] = None):
        if cls._instance is None:
            cls._instance = super(VectorStore, cls).__new__(cls)
            cls._db = ChromaDatabase(host=host, port=port, persist_directory=persist_directory)
            logger.info(f"Initialized VectorStore with host={host}, port={port}")
        return cls._instance
    
    def __init__(self, host: str = "localhost", port: int = 8000, 
                persist_directory: Optional[str] = None):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        self.db = self._db
    
    def insert_batch(self, collection_name: str, documents: List[str], 
                    metadatas: Optional[List[Dict[str, Any]]] = None, 
                    embeddings: Optional[List[List[float]]] = None,
                    batch_size: int = 100) -> bool:
        """
        Chèn dữ liệu vào collection theo batch để tối ưu hiệu năng
        
        Args:
            collection_name: Tên collection
            documents: Danh sách văn bản cần lưu trữ
            metadatas: Danh sách metadata tương ứng
            embeddings: Danh sách embeddings tương ứng (nếu có)
            batch_size: Kích thước mỗi batch
            
        Returns:
            bool: True nếu thành công, False nếu thất bại
        """
        try:
            if not documents:
                logger.warning("No documents provided for insertion")
                return False
                
            # Tạo collection nếu chưa tồn tại
            self.db.create_collection(name=collection_name)
            
            # Xử lý chèn theo batch
            total_docs = len(documents)
            success_count = 0
            
            for i in range(0, total_docs, batch_size):
                batch_end = min(i + batch_size, total_docs)
                batch_docs = documents[i:batch_end]
                batch_metas = metadatas[i:batch_end] if metadatas else None
                batch_embs = embeddings[i:batch_end] if embeddings else None
                
                try:
                    self.db.add_documents(
                        collection_name=collection_name,
                        documents=batch_docs,
                        metadatas=batch_metas,
                        embeddings=batch_embs
                    )
                    success_count += len(batch_docs)
                    logger.debug(f"Inserted batch {i//batch_size + 1}: {len(batch_docs)} documents")
                    
                except Exception as e:
                    logger.error(f"Error inserting batch {i//batch_size + 1}: {str(e)}")
                    # Có thể thêm logic retry ở đây nếu cần
                    continue
            
            logger.info(f"Successfully inserted {success_count}/{total_docs} documents into '{collection_name}'")
            return success_count == total_docs
            
        except Exception as e:
            logger.error(f"Failed to insert data into collection '{collection_name}'. Error: {e}")
            return False
    
    def get_collection_info(self, collection_name: str) -> Optional[Dict[str, Any]]:
        """Lấy thông tin về collection"""
        try:
            return self.db.get_collection_info(collection_name)
        except Exception as e:
            logger.error(f"Error getting collection info for '{collection_name}': {e}")
            return None
    
    def delete_collection(self, collection_name: str) -> bool:
        """Xóa collection"""
        try:
            self.db.delete_collection(collection_name)
            logger.info(f"Successfully deleted collection '{collection_name}'")
            return True
        except Exception as e:
            logger.error(f"Error deleting collection '{collection_name}': {e}")
            return False
    
    def list_collections(self) -> List[str]:
        """Liệt kê tất cả collections"""
        try:
            return self.db.list_collections()
        except Exception as e:
            logger.error(f"Error listing collections: {e}")
            return []

    insert_data = insert_batch
