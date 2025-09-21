import sys, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] 
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from data.embeddings.processing.chunk_processor import SentenceChunker, Chunk, SentenceChunkerConfig, WhitespaceTokenizer
from data.embeddings.processing.text_preprocessor import TextPreprocessor, TextPreprocessorConfig
from data.embeddings.processing.batch_processor import BatchEmbedder, BatchEmbedConfig
RAW = """
Abstract—Vector databases (VDBs) have emerged to manage
 high-dimensional data that exceed the capabilities of traditional
 database management systems, and are now tightly integrated
 with large language models as well as widely applied in modern
 artificial intelligence systems. Although relatively few studies
 describe existing or introduce new vector database architectures,
 the core technologies underlying VDBs, such as approximate
 nearest neighbor search, have been extensively studied and are
 well documented in the literature. In this work, we present a
 comprehensive review of the relevant algorithms to provide a
 general understanding of this booming research area. Specifically,
 we first provide a review of storage and retrieval techniques in
 VDBs, with detailed design principles and technological evolution.
 Then, we conduct an in-depth comparison of several advanced
 VDBsolutions with their strengths, limitations, and typical appli
cation scenarios. Finally, we also outline emerging opportunities
 for coupling VDBs with large language models, including open
 research problems and trends, such as novel indexing strategies.
 This survey aims to serve as a practical resource, enabling
 readers to quickly gain an overall understanding of the current
 knowledge landscape in this rapidly developing area.
 Index Terms—Vector Database, Retrieval, Storage, Large Lan
guage Models.
 I. INTRODUCTION
 Vectors, particularly those in high-dimensional spaces, are
 mathematical representations of data, encoding the semantic
 and contextual information of entities such as text, images,
 audio, and video [1], [2]. These vectors are generally gen
erated through some related machine learning models, and
 the generated vectors are usually high-dimensional and can
 be used for similarity comparison. The step of converting
 original unstructured data into vectors is the foundation of
 many artificial intelligence (AI) applications (including large
 language models (LLMs) [3], question-answering systems
 [4], [5], image recognition [6], recommendation systems [7],
 [8], etc.). However, in terms of managing and retrieving
 high-dimensional vector data, traditional databases designed
 for handling structured data are often inadequate. Vector
 databases, on the other hand, provide a specialized solution
 to these challenges.
 Vector Databases (VDBs) are tools specifically designed to
 efficiently store and manage high-dimensional vectors. Specif
ically, VDBs store information as high-dimensional vectors,
 which are mathematical representations of data features or
 ∗ Equal contribution. † Corresponding author.
 This paper was produced by the IEEE Publication Technology Group. They
 are in Piscataway, NJ.
 Manuscript received April 19, 2021; revised August 16, 2021.
 attributes [9]. Depending on the complexity and granularity of
 the underlying data, the dimensions of these high-dimensional
 vectors usually range from dozens to thousands. Unlike tra
ditional relational databases, VDBs provide efficient mecha
nisms for large-scale storage, management, and search of high
dimensional vectors [10]–[12]. These mechanisms bring vari
ous efficient functions to VDBs, such as supporting semantic
 similarity search, efficiently managing large-scale data, and
 providing low-latency responses. These functions make VDBs
 increasingly integrated into AI-based applications.
 VDBshave two core functions: vector storage and vector re
trieval. The vector storage function relies on techniques such as
 quantization, compression, and distributed storage mechanisms
 to improve efficiency and scalability. The retrieval function
 of VDBs relies on specialized indexing techniques, including
 tree-based methods, hashing methods [13], graph-based mod
els, and quantization-based techniques [14]. These indexing
 techniques optimize high-dimensional similarity search by
 reducing computational cost and improving search perfor
mance. In addition, hardware acceleration and cloud-based
 technologies have further enhanced the capabilities of VDBs,
 making them suitable for large-scale and real-time applications
 [15]–[17].
"""

def main():
    # 1. Preprocess
    tp = TextPreprocessor(TextPreprocessorConfig())
    clean = tp.preprocess(RAW)

    # 2. Chunk
    chunker = SentenceChunker(SentenceChunkerConfig(max_tokens=40, overlap_tokens=8), tokenizer=WhitespaceTokenizer())
    chunks = chunker.chunk(clean)

    texts = [ch.text for ch in chunks]

    print("=== CLEANED TEXT ===")
    print(clean)
    print()

    print("=== CHUNKS ===")
    for i, ch in enumerate(chunks, 1):
        print(f"[{i}] tokens={ch.n_tokens} idx=({ch.start_index},{ch.end_index})")
        print(ch.text)
        print("-" * 60)

    # 3. Embed
    cfg = BatchEmbedConfig(
        provider="sentence_transformer",
        batch_size=8,
        out_jsonl="output_vectors.jsonl",
        include_text_in_jsonl=True,
        provider_kwargs={
            "model_name": "all-MiniLM-L6-v2",  
        }
    )

    embedder = BatchEmbedder(cfg)
    vectors, dim = embedder.run(texts)

    print(f"✅ Embedded {len(vectors)} chunks | dimension = {dim}")

if __name__ == "__main__":
    main()