from data.retrieval.context_retriever import ContextRetriever

def main():
    retriever = ContextRetriever(collection_name="test_collection")

    documents = [
        {"content": "Artificial intelligence is transforming the world.", "metadata": {"source": "doc1"}},
        {"content": "Machine learning is a subset of AI.", "metadata": {"source": "doc2"}},
        {"content": "Deep learning is a powerful technique in AI.", "metadata": {"source": "doc3"}},
    ]
    retriever.add_documents(documents)

    query = "What is AI?"
    results = retriever.retrieve(query=query, top_k=2)

    for result in results:
        print(f"Content: {result['content']}, Score: {result['score']}")

if __name__ == "__main__":
    main()