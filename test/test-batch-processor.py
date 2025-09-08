# test_batch_processor.py
from data.embeddings.processing.batch_processor import TextProcessingPipeline

def main():
    # Example Vietnamese text
    sample_text = """
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
 Therefore, compared with traditional databases, vector
 databases (VDBs) have three significant advantages: (1) Vector
 databases possess efficient and accurate vector retrieval
 capabilities. The core function of VDBs is to retrieve relevant
 vectors through vector similarity (distance), and this function
 is also the core of applications such as natural language pro
cessing (NLP), computer vision, and recommendation systems
 [18], [19]. In contrast, traditional databases can only query
 data based on exact matching or predefined conditions, and
 this kind of query method is relatively slow and often does
 not consider the semantic information of the data itself. (2)
 Vector databases support the storage and query of complex
 and unstructured data. VDBs can store and search data with
 high complexity and granularity, such as text, images, audio,
 video, etc. However, traditional databases, such as relational
 databases, are difficult to store this kind of data informa
tion well [20]. (3) Vector databases have high scalability
 and real-time processing capabilities. Traditional databases
 face challenges in effectively handling unstructured data and
 large volumes of real-time datasets [21]. However, VDBs can
 process vector data at large scale and in real time, which
 is crucial for modern data science and artificial intelligence
 applications [22]. By using technologies such as sharding [23],
 partitioning, caching, and replication, VDBs can distribute
 workloads andoptimize resourceutilizationacrossmultiple
 machinesorclusters.Traditionaldatabases,ontheotherhand,
 mayfacescalabilitybottlenecks,latencyissues,orconcurrency
 conflictswhenhandlingbigdata[19].
  RecentsurveysonVDBsprimarilycoverfundamentalcon
ceptsandpracticalapplicationsofVDBsandvectordatabase
 management systems.Somestudies [12], [19], [24] focuson
 theworkflowandtechnicalchallengesofVDBs, includingkey
 aspectssuchasqueryprocessing,optimization,andexecution
 techniques. And someworks [25] explore the critical role
 ofVDBs inmoderngenerativeAI applications andprovide
 anoutlookonthefutureofVDBs.While thesestudieshave
 theirrespectivefocuses, theydonotprovideacomprehensive
 surveyoftheoverallstorageandsearchtechnologiesinVDBs,
 nor deliver a thorough analysis comparing the capabilities
 of existingVDBs. Furthermore, there is limitedexploration
 of howthese systems can integratewith rapidly advancing
 AI technologies, suchas large languagemodels (LLMs), to
 supportmoderndata-intensiveapplications.
 This gap shows the need for a comprehensive survey to
 consolidatecurrentknowledgeanduncoverkeyresearchchal
lengesrelatedtoVDB.Toaddressthis,oursurveymakesthe
 followingcorecontributions:
 •Wesystematicallyreviewstorageandretrievaltechniques
 inVDBs,outliningtheirdesignprinciplesandtechnolog
icalevolution.
 •Weprovide adetailedcomparative analysis of existing
 VDBsolutions, highlighting their strengths, limitations,
 andtypicalapplicationscenarios.
 •Wesynthesizethemainchallenges,recentadvancements,
 andfuturedirectionsforVDBs, includingopenresearch
 problems and trends suchas novel indexing strategies,
 adaptive query optimization, and integrationwith ad
vancedAIcapabilities.
 Thispapercomprehensivelysummarizes the technologies re
lated to vector databases, and systematically tests the per
formance of existing open-source vector databases. It also
 provides anoutlookon thechallenges that vector databases
 will face in the future.Through the summaryof thispaper,
 researchers can deepen their understanding of the field of
 vectordatabases.Figure 1showstheoverallframeworkofthe
 paper,andwealsoconstructaclassificationsystemofstorage
 andsearchtechnologiesforVDBs, asshowninFigure 2

     """
    
    # Initialize and run the pipeline
    pipeline = TextProcessingPipeline(embedding_dim=50)
    result = pipeline.process_text(
        sample_text,
        source_info={"source": "test", "language": "vi"}
    )
    
    # Print results (FULL)
    print("=== Results ===")
    num_chunks = len(result.get("chunks", []))
    num_embeds = len(result.get("embeddings", []))
    print(f"Number of chunks: {num_chunks}")
    print(f"Embedding dimension: {len(result['embeddings'][0]) if num_embeds else 0}")

    # In toàn bộ chunk + text + embedding
    print("\n=== All Chunks & Embeddings ===")
    for i, (chunk, emb) in enumerate(zip(result.get("chunks", []), result.get("embeddings", []))):
        # Lấy text đã xử lý
        text = getattr(chunk, "text", chunk)  # chunk có thể là str hoặc object
        print(f"\n--- Chunk #{i} ---")
        print("Text:")
        print(text)
        print("Embedding:")
        print(emb)

    # Quality metrics (nếu có)
    if result.get("quality_metrics"):
        print("\n=== Quality Metrics ===")
        for k, v in result["quality_metrics"].items():
            try:
                print(f"{k}: {v:.4f}")
            except Exception:
                print(f"{k}: {v}")


if __name__ == "__main__":
    main()