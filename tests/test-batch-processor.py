# test_batch_processor.py
from data.embeddings.processing.batch_processor import BatchProcessor

def main():
    # Sample text
    text = """VDBs have two core functions: vector storage and vector retrieval. The vector storage function relies on techniques such as
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
 andsearchtechnologiesforVDBs, asshowninFigure 2"""
    
    # Initialize BatchProcessor
    processor = BatchProcessor(embedding_dim=50)
    
    # Process single text
    result = processor.process_single(
        text=text,
        source_info={"source": "test"}
    )
    
    # Print results
    print(f"Metadata: {result.metadata}")
    print(f"Number of chunks: {len(result.chunks)}")
    print(f"First chunk: {result.chunks[0]}")
    print(f"First embedding: {result.embeddings[0][:5]}")  # Print first 5 values of the first embedding
    print(f"Quality metrics: {result.quality_metrics}")

if __name__ == "__main__":
    main()