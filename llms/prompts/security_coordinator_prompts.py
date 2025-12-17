from typing import List, Dict, Any, Optional
import json

class SecurityCoordinatorPrompts:
    """Prompts for the Security Coordinator (Router) and Orchestration"""
    
    @staticmethod
    def get_routing_prompt(question: str) -> str:
        """Prompt to route the user's question to the most appropriate agent"""
        return f"""You are a Security Assistant Router responsible for directing user requests to the specialized agent best suited to handle them.

**Available Specialized Agents:**

1. **AnalysisAgent** (`analysis`)
   - **Role**: Security Analyst & Threat Hunter
   - **Capabilities**: 
     - Analyzing security vulnerabilities, CVEs, and scan results
     - Checking system security status, assets, and targets
     - querying MCP tools for security data (wazuh, nmap, etc.)
     - Answering general security questions
   - **Keywords**: "vulnerability", "scan", "status", "security", "cve", "check", "analyze", "list assets"

2. **NucleiGeneratorAgent** (`nuclei`)
   - **Role**: Nuclei Template Developer
   - **Capabilities**: 
     - Generating YAML templates for Nuclei scans
     - Writing custom vulnerability detection rules
     - Creating matchers and requests for specific CVEs
   - **Keywords**: "create template", "generate nuclei", "write a rule", "nuclei yaml", "matcher for", "rule for cve"

3. **GeneralChat** (`general`)
   - **Role**: Helpful Assistant
   - **Capabilities**: 
     - Handling greetings, small talk, and general questions unrelated to security operations
   - **Example**: "Hi", "Hello", "How are you?", "Who are you?"

**User Question:**
"{question}"

**Your Task:**
Determine the best agent to handle this request.
- If the user asks about security status, vulnerabilities, or analysis -> Select `analysis`
- If the user specifically asks to CREATE/GENERATE a Nuclei template/rule -> Select `nuclei`
- If the user is just saying hello or asking general questions -> Select `general`

**Output Format:**
You must respond with valid JSON only:
{{
    "agent": "analysis" | "nuclei" | "general",
    "reasoning": "Brief explanation of why this agent was selected"
}}

**Response:**"""
