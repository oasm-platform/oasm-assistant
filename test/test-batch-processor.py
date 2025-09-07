from data.embeddings.processing.batch_processor import BatchProcessor

# 1. Tạo file test
test_file = "test_input.txt"
with open(test_file, "w", encoding="utf-8") as f:
    f.write("Đây là một đoạn text thử nghiệm để test pipeline DocumentProcessor.")

# 2. Chạy processor
processor = BatchProcessor(chunk_size=50, overlap=10)
chunks = processor.process_file(test_file)

# 3. In ra kết quả
for c in chunks:
    print("--- CHUNK ---")
    print("Text:", c.text)
    print("Meta:", c.metadata)
    print("Chunk ID:", c.chunk_id)
