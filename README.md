# 🤖 OASM ASSISTANT

**Support in Managing, Monitoring, and Preventing Attack Surfaces**

Built by: **Team OASM-Platform**

---

## Overview

OASM Assistant is an AI-powered layer built on top of the OASM-Platform (Open-ASM) that provides intelligent automation and optimization for external attack surface management. The system leverages multi-agent architecture with LangGraph to deliver comprehensive threat intelligence, vulnerability analysis, and incident response capabilities.

## OASM Ecosystem

### Open-ASM (Core Platform)

The foundation platform for External Attack Surface Management featuring:

- **Microservices architecture** for scalability and flexibility
- **Discovery tools**: Subfinder, Dnsx, Naabu, Httpx
- **Vulnerability scanning**: Nuclei, Nessus
- **Asset management** and job scheduling
- **RESTful APIs** and **Server-Sent Events (SSE)** support
- **MCP (Model Context Protocol)** integration

### OASM-ASSISTANT (AI Layer)

The intelligent layer on top of the core platform providing:

- **AI-powered automation** of security workflows
- **Multi-agent system** built with LangGraph
- **Intelligent orchestration** and decision-making
- **Real-time threat analysis** and response

## System Architecture

The OASM ecosystem consists of three main layers:

![OASM System Architecture](docs/system-architecture.png)

### 1. OASM ASSISTANT (AI Layer)

Intelligent agents that provide advanced security capabilities:

- **Domain Classifier Agent**
- **Threat Intelligence Agent**
- **Analysis Agent**
- **Incident Responder Agent**
- **Orchestration Agent**

Connected to OASM Core via **gRPC APIs**

### 2. OASM CORE (Central Block)

Central management and coordination:

- Asset Management
- Job Scheduling and Management
- Forward to OASM Assistant
- API Gateway
- MCP Integration
- Data Storage & Caching

Provides **RESTful APIs** and **SSE** for real-time updates

### 3. OASM WORKERS (Tools Execution Layer)

Execute security tools and return results to OASM Core:

- **Discovery**: Subfinder, dnsx, naabu, httpx
- **Vulnerability Scanning**: Nuclei, Nessus

## AI Agents

### Domain Classifier

Automatically classifies digital assets by analyzing HTML content:

- Assigns labels based on title and content
- Identifies high-value targets
- Helps prioritize asset management and monitoring
- Detects assets likely to be targeted by attackers

### Threat Intelligence Agent

Provides proactive threat monitoring:

- **Threat monitoring**: Continuous surveillance of attack surface
- **Intelligence analysis**: IOC (Indicator of Compromise) correlation
- **Exploring enemy weapons research**: Understanding attacker tools and techniques
- **Attack prediction**: Anticipating potential threats
- **Threat alerts**: Real-time notifications of security risks

### Analysis Agent

Comprehensive vulnerability assessment and reporting:

- **Collect results** from OASM Core
- **Compare security status** with international standards (OWASP, CWE, PCI-DSS, ISO 27001)
- **Prioritize vulnerabilities** by context and business impact
- **Prepare detailed reports** with remediation plans

### Incident Responder Agent

Automated incident response and investigation:

- **Detect attacks** in progress
- **Attack method analysis**: Understanding attacker techniques
- **Generate incident response plans**: Step-by-step remediation
- **Automatically prevent vulnerabilities**: Proactive security measures
- **Investigate the entire incident**: Complete forensic analysis

### Orchestrator Agent

Central coordination and user interaction:

- **Understanding user intent**: Natural language processing
- **Agent coordination**: Managing workflows across specialized agents
- **Summary of results**: Consolidated reporting
- **Manage conversations**: Interactive dialogue with users

## Technology Stack

### AI & Machine Learning

- **LangGraph**: Building LLM-powered agents with tools
- **LLMs**: GPT-4, Claude, Gemini, Llama, Mistral, Olama...
- **Transfer Learning & Reinforcement Learning**: Continuous improvement

### RAG (Retrieval Augmented Generation)

Built with **LangChain** framework for advanced document retrieval:

- **Hybrid Search Strategy**:
  - **pgvector**: Vector similarity search for semantic matching using cosine distance
  - **BM25**: Keyword-based full-text search for precise term matching
  - Combined ranking for optimal retrieval accuracy
- **Re-ranking**: Optimized result ordering using relevance scoring
- **Embedding Generation**: Support for OpenAI, Google Gemini, and HuggingFace embeddings
- Enhanced data sources:
  - Memory agent (conversation history and context)
  - Knowledge base (security standards, best practices)
  - Nuclei template library (vulnerability patterns)

### Communication & Integration

- **gRPC**: High-performance RPC between AI layer and Core platform
- **MCP (Model Context Protocol)**: Provide real-time asset context to AI agents
- **SearXNG**: Privacy-respecting metasearch engine integration

### Data Storage & Processing

- **PostgreSQL**: Primary database storage
- **Batch processing**: Efficient embedding generation
- **Content extraction**: PDF, DOCX, YAML, and more
- **Parallel vector search**: Fast similarity queries
- **pgvector extension**: Vector similarity search in PostgreSQL

## Key Features

### Intelligent Asset Classification

- Automatic categorization of digital assets
- AI-powered tag generation
- Priority-based asset management

### Threat Intelligence

- Real-time threat monitoring
- IOC correlation and analysis
- Attack prediction and alerting
- Adversary research capabilities

### Vulnerability Management

- Automated vulnerability scanning
- Standards-based compliance checking (OWASP, CWE, PCI-DSS, ISO 27001)
- Context-aware vulnerability prioritization
- Detailed remediation guidance

### Incident Response

- Automated attack detection
- Real-time attack analysis
- Generated response plans
- Complete incident investigation

### Multi-Agent Orchestration

- Natural language interaction
- Intelligent workflow coordination
- Consolidated reporting
- Conversational management

## Benefits

- **Reduced Costs**: Open source alternative to expensive commercial solutions
- **Enhanced Automation**: AI-powered workflows reduce manual effort
- **Improved Accuracy**: Multi-agent analysis provides comprehensive coverage
- **Real-time Response**: Immediate threat detection and response
- **Standards Compliance**: Automated checking against industry standards
- **Scalable Architecture**: Microservices design supports growth
- **Community-Driven**: Open source development for continuous improvement

## Use Cases

- **External Attack Surface Management**: Continuous discovery and monitoring of digital assets
- **Vulnerability Assessment**: Automated scanning and prioritization
- **Threat Hunting**: Proactive identification of security threats
- **Incident Response**: Rapid detection and response to security incidents
- **Compliance Monitoring**: Ongoing assessment against security standards
- **Security Reporting**: Automated generation of executive reports

## Getting Started

_Documentation coming soon_

## Contributing

We welcome contributions from the community. This project aims to be a reputable open source product for the international cybersecurity community.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

OASM Assistant is designed for **defensive security purposes only**. Users are responsible for ensuring compliance with applicable laws and regulations in their jurisdiction. This tool should only be used to assess and protect systems you own or have explicit permission to test.

---

**Built by Team OASM-Platform**
