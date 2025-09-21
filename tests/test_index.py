from data.indexing.document_indexer import DocumentIndexer
from data.indexing.vector_store import ChromaVectorStore

def test_add_and_search_document():
    indexer = DocumentIndexer(collection_name="test_collection", chunk_size=100, chunk_overlap=20)
    
    content = "This is a test document about AI and machine learning. " * 10
    metadata = {"source": "test_source"}
    
    chunk_ids = indexer.index_document(content=content, metadata=metadata)
    print(f"Indexed chunk IDs: {chunk_ids}")
    assert len(chunk_ids) > 0, "No chunks were created during indexing!"
    
    query = "machine learning"
    results = indexer.search(query=query, k=3)
    print(f"Search results: {results}")
    assert len(results) > 0, "No search results found!"
    assert all("document" in result for result in results), "Search results should contain documents!"

test_add_and_search_document()