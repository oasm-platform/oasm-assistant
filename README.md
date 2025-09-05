# ⚔️ OASM Assistant

An AI-powered cybersecurity assistant that leverages advanced agent architectures for threat monitoring, attack prevention, and web security protection.

## Overview

OASM Assistant is a sophisticated multi-agent system designed to enhance cybersecurity operations through intelligent automation and knowledge retrieval. The system combines multiple AI agents with comprehensive threat intelligence databases to provide real-time security analysis and recommendations.

## Key Features

### 🤖 Multi-Agent Architecture

- **Specialized Agents**: Dedicated agents for threat detection, vulnerability scanning, network reconnaissance, and incident response
- **Agent Orchestration**: Coordinated workflows with intelligent handoffs between agents
- **Swarm Intelligence**: Collective decision-making through agent collaboration
- **Agent Debate**: Multi-perspective analysis for complex security scenarios

### 🧠 Advanced AI Capabilities

- **ReAct Pattern**: Reasoning and Acting for structured problem-solving
- **Chain of Thought**: Step-by-step logical reasoning for complex analysis
- **Reflex Agents**: Immediate response to critical security events
- **Learning Loop**: Continuous improvement through feedback and evaluation

### 📚 Comprehensive Knowledge Base

- **RAG (Retrieval Augmented Generation)**: Enhanced responses using domain-specific knowledge
- **PDF Document Processing**: Automated extraction from security standards, compliance documents, and threat intelligence reports
- **Nuclei Template Integration**: Direct integration with Project Discovery's vulnerability templates
- **Web Search Capabilities**: Real-time threat intelligence gathering

### 🔍 Security Tool Integration

- **Nmap Agent**: Network discovery and security auditing
- **Subfinder Agent**: Subdomain discovery and enumeration
- **Nuclei Agent**: Vulnerability scanning with customizable templates
- **Amass Agent**: In-depth attack surface mapping and external asset discovery

### 🔍 Web Search Capabilities

- **Multi-Engine Search**: Support for DuckDuckGo, Google, Bing, Tavily, and SerpApi
- **Search Coordination**: Intelligent orchestration across multiple search engines
- **Result Processing**: Cleaning, deduplication, and formatting of search results
- **Source Validation**: Credibility checking for search result sources
- **Knowledge Extraction**: Structured information extraction from search results

### 🗄️ Data Management

- **LlamaIndex**: Advanced document indexing and retrieval
- **Vector Storage**: Semantic search across security knowledge
- **PostgreSQL**: Structured storage for scan results and threat data
- **Real-time Processing**: Live data ingestion and analysis

## Architecture Components

### Agent Types

- **Threat Detection Agent**: Identifies and analyzes security threats
- **Vulnerability Scan Agent**: Manages vulnerability assessment workflows
- **Network Reconnaissance Agent**: Performs network discovery and mapping
- **Web Security Agent**: Focuses on web application security
- **Report Generation Agent**: Creates comprehensive security reports
- **Coordination Agent**: Orchestrates multi-agent workflows

### Core Systems

- **Environment**: Context-aware security landscape monitoring
- **Perception**: Multi-source threat intelligence gathering
- **Memory**: Long-term and short-term knowledge retention
- **Planning**: Strategic and tactical security planning
- **Evaluation**: Continuous performance assessment and optimization

### Technology Stack

- **LangChain & LangGraph**: Agent coordination and workflow management
- **LlamaIndex**: Document processing and knowledge retrieval
- **PostgreSQL**: Primary data storage
- **ChromaDB/Qdrant**: Vector database for semantic search
- **FastAPI**: REST API interface
- **Docker**: Containerized deployment

## Use Cases

### Threat Intelligence

- Automated threat hunting and analysis
- Real-time vulnerability assessment
- Security trend identification
- Attack pattern recognition

### Incident Response

- Automated incident detection and classification
- Response workflow orchestration
- Evidence collection and analysis
- Stakeholder communication

### Compliance & Reporting

- Automated compliance checking
- Security posture assessment
- Executive dashboard generation
- Audit trail maintenance

### Proactive Security

- Continuous vulnerability monitoring
- Predictive threat analysis
- Security control optimization
- Risk assessment automation

## Benefits

- **Enhanced Response Time**: Automated detection and response to security threats
- **Improved Accuracy**: AI-driven analysis reduces false positives
- **Scalable Operations**: Multi-agent architecture scales with organizational needs
- **Knowledge Retention**: Persistent learning from security incidents
- **Comprehensive Coverage**: Integration with industry-standard security tools

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

We welcome contributions to enhance the OASM Assistant. Please read our contributing guidelines before submitting pull requests.

## Disclaimer

OASM Assistant is designed for defensive security purposes only. Users are responsible for ensuring compliance with applicable laws and regulations in their jurisdiction.
