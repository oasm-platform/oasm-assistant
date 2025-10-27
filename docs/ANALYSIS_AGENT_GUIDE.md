# Analysis Agent - Complete Guide

## Overview

The Analysis Agent is a comprehensive vulnerability analysis system that combines:

- **Database Knowledge**: CWE, OWASP, CVSS, compliance standards
- **Hybrid Retrieval**: BM25 + Vector search for intelligent knowledge retrieval (optional)
- **LLM Integration**: Context-aware recommendations
- **Automated Data Collection**: Scheduled updates from NVD, OWASP, CWE
- **MCP Integration**: Fetch scan results from OASM Core (optional)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Enhanced Analysis Agent                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Scan Data   │  │   Context    │  │  Standards   │     │
│  │  Input       │  │  Information │  │  (OWASP/PCI) │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                 │                  │              │
│         └─────────────────┼──────────────────┘              │
│                           ▼                                 │
│              ┌────────────────────────┐                     │
│              │  Normalization &       │                     │
│              │  Deduplication         │                     │
│              └────────────┬───────────┘                     │
│                           ▼                                 │
│              ┌────────────────────────┐                     │
│              │  Standard Mapping      │◄────┐              │
│              │  (OWASP, CWE)          │     │              │
│              └────────────┬───────────┘     │              │
│                           ▼                  │              │
│              ┌────────────────────────┐     │              │
│              │  Risk Scoring          │     │              │
│              │  (Context-based)       │     │              │
│              └────────────┬───────────┘     │              │
│                           ▼                  │              │
│              ┌────────────────────────┐     │              │
│              │  Compliance Assessment │     │              │
│              └────────────┬───────────┘     │              │
│                           ▼                  │              │
│              ┌────────────────────────┐     │              │
│              │  Remediation Plan      │◄────┤              │
│              │  Generation            │     │              │
│              └────────────┬───────────┘     │              │
│                           │                  │              │
│                           ▼                  │              │
│              ┌────────────────────────┐     │              │
│              │  Report Generation     │     │              │
│              └────────────┬───────────┘     │              │
│                           │                  │              │
│                           ▼                  │              │
└───────────────────────────┼──────────────────┼──────────────┘
                            │                  │
              ┌─────────────┴──────────────────┴───────────┐
              │                                             │
    ┌─────────▼─────────┐              ┌──────────────────▼────────┐
    │  Knowledge Base    │              │   RAG System              │
    │  Repositories      │              │   (Hybrid Search)         │
    ├────────────────────┤              ├───────────────────────────┤
    │ • OWASP Mappings   │              │ • PDF Playbooks           │
    │ • CWE Database     │              │ • OWASP Top 10 Guide      │
    │ • CVSS Scores      │              │ • CWE Top 25 Guide        │
    │ • Context Factors  │              │ • Remediation Playbook    │
    │ • Exploit Intel    │              │ • Incident Response       │
    │ • Compliance Stds  │              │ • Vector Store (PGVector) │
    │                    │              │ • BM25 Index              │
    └────────────────────┘              └───────────────────────────┘
```

## Quick Start

### 1. Initial Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Install additional dependencies for PDF generation
pip install reportlab PyPDF2 rank-bm25

# Setup database (ensure PostgreSQL with pgvector is running)
# Connection details in .env file
```

### 2. Seed Knowledge Base

```bash
# Seed database and generate playbooks
python data/database/seeders/seed_knowledge_base.py

# Skip playbook generation if already exists
python data/database/seeders/seed_knowledge_base.py --skip-playbooks

# Include external data collection from NVD (requires internet)
python data/database/seeders/seed_knowledge_base.py --collect-external
```

### 3. Run Analysis

```python
from data.database import postgres_db
from agents.specialized.analysis_agent_enhanced import (
    EnhancedAnalysisAgent,
    VulnerabilityContext
)

# Create agent
with postgres_db.get_session() as session:
    agent = EnhancedAnalysisAgent(db_session=session)

    # Sample scan results
    scan_results = [
        {
            "tool": "nuclei",
            "template-id": "sql-injection",
            "info": {
                "name": "SQL Injection Vulnerability",
                "severity": "critical",
                "tags": ["cwe-89"],
                "classification": {"cwe-id": "89"}
            },
            "host": "https://example.com/login"
        }
    ]

    # Run analysis
    results = agent.analyze_vulnerabilities(
        scan_results=scan_results,
        context=VulnerabilityContext(
            environment="production",
            data_sensitivity="pii",
            exposure="public_internet",
            asset_criticality="critical"
        ),
        standards=["OWASP", "PCI-DSS"]
    )

    # Access results
    if results["success"]:
        print(f"Total findings: {results['analysis']['summary']['total_findings']}")
        print(f"Critical: {results['analysis']['summary']['by_priority']['P0']}")

        # Print technical report
        print(results["reports"]["reports"]["technical"])

        # Print executive summary
        print(results["reports"]["reports"]["executive"])
```

## Features

### 1. Vulnerability Normalization

Supports multiple scan tool formats:
- **Nuclei**: Template-based vulnerability scanner
- **Nessus**: Enterprise vulnerability scanner
- **Generic**: Custom scan formats

Automatically deduplicates findings based on:
- CVE ID + Affected Asset
- CWE ID + Affected Asset
- Title + Affected Asset

### 2. Standard Mapping

Maps vulnerabilities to:
- **OWASP Top 10 2021**: A01-A10 categories
- **CWE Top 25**: Most dangerous software weaknesses
- **Compliance Standards**: PCI-DSS, OWASP, SANS Top 25

### 3. Context-Based Risk Scoring

Risk Score = `CVSS Base Score × Context Multiplier × Exploit Multiplier`

**Context Factors**:
- **Environment**: production (1.3x), staging (1.1x), dev (1.0x)
- **Data Sensitivity**: payment (1.5x), pii (1.3x), general (1.0x)
- **Exposure**: public_internet (1.5x), internal (1.0x)
- **Asset Criticality**: critical (1.4x), high (1.2x), medium (1.0x)

**Exploit Multiplier**:
- Has public exploit: 1.2x
- Actively exploited: 1.5x
- PoC available: 1.1x

**Priority Assignment**:
- **P0 (Critical)**: Risk Score >= 9.0
- **P1 (High)**: Risk Score >= 7.0
- **P2 (Medium)**: Risk Score >= 4.0
- **P3 (Low)**: Risk Score < 4.0

### 4. Remediation Plans

3-Phase approach:

**Phase 1: Immediate (2-4 hours)**
- Temporary fixes and mitigations
- WAF rules, feature disabling
- Monitoring setup

**Phase 2: Short-term (1-3 days)**
- Proper code fixes
- Security patches
- Testing and validation

**Phase 3: Long-term (1-2 weeks)**
- Architectural improvements
- Security controls
- Process updates

Enhanced with:
- Code examples from playbooks
- Best practices from CWE database
- Testing checklists from OWASP

### 5. Compliance Assessment

Checks against:
- **OWASP Top 10**: Category coverage
- **PCI-DSS**: Requirements 6.5, 6.6
- **Custom standards**: Extensible framework

### 6. Report Generation

**Technical Report**:
- Detailed vulnerability analysis
- Risk scoring breakdown
- Remediation plans
- Playbook references

**Executive Summary**:
- Business impact
- Cost estimates
- Compliance status
- Recommended actions

**Compliance Report**:
- Standards compliance status
- Gap analysis
- Remediation timeline

**Action List**:
- Prioritized fix list
- Assignable tasks
- Deadlines

## Knowledge Base

### Database Tables

1. **owasp_mappings**: CWE to OWASP Top 10 mappings
2. **cwes**: CWE database with mitigations
3. **cvss_scores**: CVSS scores from NVD
4. **context_factors**: Risk scoring multipliers
5. **exploit_intelligence**: Exploit availability data
6. **compliance_standards**: Compliance requirements
7. **compliance_benchmarks**: Industry benchmarks

### PDF Playbooks

1. **OWASP_Top10_2021_Playbook.pdf**
   - All 10 OWASP categories
   - Attack examples
   - Secure code examples
   - Testing checklists

2. **CWE_Top25_2023_Playbook.pdf**
   - Top 25 most dangerous weaknesses
   - Language-specific guidance
   - Mitigation strategies

3. **Remediation_Guide_Playbook.pdf**
   - 3-phase remediation approach
   - Effort estimation
   - Verification methods

4. **Incident_Response_Playbook.pdf**
   - 6-phase incident response
   - Containment strategies
   - Post-incident analysis

### RAG System

**Hybrid Search**: Combines BM25 keyword search with vector similarity

**Retrieval Methods**:
```python
# Retrieve for specific vulnerability
results = rag_system.retrieve_for_vulnerability(
    cwe_id="CWE-89",
    owasp_category="A03:2021",
    query="SQL injection"
)

# Get remediation plan
plan = rag_system.retrieve_remediation_plan(
    "SQL Injection",
    severity="Critical"
)

# Query by category
docs = rag_system.query_owasp_category("A03:2021")

# Secure coding examples
examples = rag_system.query_secure_coding("Python", "SQL Injection")
```

## Automation

### Scheduler

Automated knowledge base updates:

```bash
# Start scheduler
python scripts/knowledge_scheduler.py
```

**Schedule**:
- Daily 02:00: Collect NVD CVEs (last 7 days)
- Sunday 03:00: Update CWE data
- Sunday 04:00: Update OWASP mappings
- Daily 05:00: Update exploit intelligence
- Monthly: Regenerate playbooks (1st of month, 06:00)

### Manual Data Collection

```bash
# Collect all data
python scripts/knowledge_data_collector.py

# Generate playbooks only
python scripts/generate_security_playbooks.py
```

## Testing

### Run All Tests

```bash
# Basic tests
pytest tests/test_enhanced_analysis_agent.py -v

# Integration tests (requires full knowledge base)
pytest tests/test_enhanced_analysis_agent.py -v -m integration

# Specific test
pytest tests/test_enhanced_analysis_agent.py::TestEnhancedAnalysisAgent::test_complete_analysis_workflow -v
```

### Test Coverage

Tests cover:
- ✓ Agent initialization
- ✓ Scan result normalization
- ✓ Standard mapping (OWASP, CWE)
- ✓ Risk scoring with context
- ✓ Remediation plan generation
- ✓ Compliance assessment
- ✓ Report generation
- ✓ RAG system integration
- ✓ Error handling
- ✓ Performance

## Advanced Usage

### Custom Vulnerability Context

```python
context = VulnerabilityContext(
    environment="production",          # production, staging, dev
    data_sensitivity="payment",        # payment, pii, general
    exposure="public_internet",        # public_internet, internal
    asset_criticality="critical",      # critical, high, medium, low
    industry_sector="healthcare",      # finance, healthcare, etc.
    company_size="enterprise"          # enterprise, large, medium, small
)
```

### Filter Scan Results by Severity

```python
# Only analyze critical and high severity
critical_scans = [
    scan for scan in scan_results
    if scan.get("info", {}).get("severity") in ["critical", "high"]
]

results = agent.analyze_vulnerabilities(scan_results=critical_scans)
```

### Custom Compliance Standards

```python
# Check against custom standards
results = agent.analyze_vulnerabilities(
    scan_results=scan_results,
    standards=["OWASP", "PCI-DSS", "NIST", "ISO-27001"]
)
```

### Export Reports

```python
results = agent.analyze_vulnerabilities(scan_results=scan_results)

# Save technical report
with open("technical_report.md", "w") as f:
    f.write(results["reports"]["reports"]["technical"])

# Save executive summary
with open("executive_summary.md", "w") as f:
    f.write(results["reports"]["reports"]["executive"])
```

## Troubleshooting

### RAG System Not Working

```bash
# Re-ingest playbooks
python -c "
from knowledge.rag_system import PlaybookRAGSystem
rag = PlaybookRAGSystem()
rag.ingest_playbooks(force_refresh=True)
"
```

### Knowledge Base Empty

```bash
# Re-seed database
python data/database/seeders/seed_knowledge_base.py
```

### Playbooks Not Generated

```bash
# Generate playbooks manually
python scripts/generate_security_playbooks.py
```

### NVD API Rate Limit

Add API key to environment:
```bash
export NVD_API_KEY="your-api-key-here"
```

Or in code:
```python
collector = KnowledgeDataCollector(session)
collector.nvd_api_key = "your-api-key"
```

## Performance Optimization

### Batch Processing

```python
# Process in batches
batch_size = 100
for i in range(0, len(all_scans), batch_size):
    batch = all_scans[i:i+batch_size]
    results = agent.analyze_vulnerabilities(scan_results=batch)
```

### Async Processing

```python
import asyncio

async def analyze_workspace(workspace_id):
    # Fetch scans via MCP
    scans = await fetch_scans(workspace_id)

    # Analyze
    results = agent.analyze_vulnerabilities(scan_results=scans)

    return results

# Run multiple workspaces in parallel
results = await asyncio.gather(*[
    analyze_workspace(ws_id) for ws_id in workspace_ids
])
```

## API Integration

### MCP Integration

```python
from tools.mcp_client import MCPManager

# Create agent with MCP
agent = EnhancedAnalysisAgent(
    db_session=session,
    mcp_manager=mcp_manager
)

# Fetch scans from OASM Core via MCP
results = agent.analyze_vulnerabilities(
    scan_id="scan-123",  # Fetch from MCP
    context=context
)
```

### REST API Endpoint

```python
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

app = FastAPI()

@app.post("/api/analyze")
def analyze_vulnerabilities(
    request: AnalysisRequest,
    db: Session = Depends(get_db)
):
    agent = EnhancedAnalysisAgent(db_session=db)

    results = agent.analyze_vulnerabilities(
        scan_results=request.scan_results,
        context=request.context,
        standards=request.standards
    )

    return results
```

## Best Practices

1. **Always provide context**: Risk scoring is much more accurate with context
2. **Use batch processing**: For large scan sets (>1000 findings)
3. **Update knowledge base regularly**: Run scheduler or manual updates weekly
4. **Review playbooks**: Ensure playbooks are current with latest threats
5. **Customize for your organization**: Add custom compliance standards and context factors
6. **Monitor performance**: Track analysis time and optimize if needed
7. **Validate results**: Spot-check critical findings before acting

## Contributing

To add new playbooks:
1. Create PDF in `knowledge/playbooks/`
2. Run `rag_system.ingest_playbooks(force_refresh=True)`

To add new compliance standards:
1. Update `compliance_standards` table
2. Implement check in `ComplianceRepository`
3. Add to `assess_compliance()` method

## Support

- Documentation: `docs/`
- Tests: `tests/test_enhanced_analysis_agent.py`
- Examples: See test files and main analysis agent code

---

**Version**: 1.0.0
**Last Updated**: 2025-10-24
