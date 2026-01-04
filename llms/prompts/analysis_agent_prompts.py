from typing import List, Dict, Any
import json
from llms.prompts.memory_prompts import MemoryPrompts
from common.types import QuestionType



class AnalysisAgentPrompts:
    @staticmethod
    def get_base_security_prompt(agent_name: str, role: str, capabilities: List[str] = None) -> str:
        capabilities_text = ", ".join(capabilities) if capabilities else "general security analysis"

        return f"""You are {agent_name}, a specialized AI security agent with the role of {role}.

Your primary responsibilities:
- Threat detection and analysis
- Vulnerability assessment
- Security monitoring and incident response
- Threat intelligence correlation
- Security tool coordination

Current capabilities: {capabilities_text}

Always respond with:
1. Clear, actionable security recommendations
2. Risk assessments with severity levels (low/medium/high/critical)
3. Specific technical details when analyzing threats
4. Confidence levels for your assessments (0.0-1.0)

You have access to security tools and databases. Use your expertise to provide comprehensive security analysis."""


    @staticmethod
    def get_combined_classification_and_tool_selection_prompt(
        question: str,
        workspace_id: str,
        tools_description: str
    ) -> str:
        """
        OPTIMIZED: Combined prompt for question classification AND tool selection in ONE LLM call.
        This reduces latency by 50% compared to separate calls.
        """
        # Get valid question types from enum
        valid_types = QuestionType.list_values()
        valid_types_str = " or ".join([f'"{qt}"' for qt in valid_types])

        return f"""You are an Elite Security Analysis System. Your task is to perform an initial assessment of the user's inquiry and determine the optimal path for data retrieval.

**USER INQUIRY:**
"{question}"

**MCP SECURITY INFRASTRUCTURE (Available Tools):**
{tools_description}

**INTERNAL CLASSIFICATION PROTOCOL:**
You MUST categorize this question into exactly one of these types: {valid_types}

1. **{QuestionType.SECURITY_RELATED.value}**: Inquiries about vulnerabilities, CVEs, scans, attack surface, or security metrics. 
   - *Action*: Select the most relevant security MCP tool.
   
2. **{QuestionType.GENERAL_KNOWLEDGE.value}**: Inquiries about general topics, educational content, or non-security facts.
   - *Action*: Select a general search or knowledge tool if available.

**STRICT OUTPUT REQUIREMENT (JSON ONLY):**
Respond with a single, pure JSON object. NO comments, NO markdown.
{{
    "question_type": "security_related", 
    "server": "mcp-server-name",
    "tool": "tool-name",
    "args": {{ "arg_name": "value", "workspaceId": "your_workspace_id" }},
    "reasoning": "A professional justification for this tool selection, written in the EXACT same language as the user's question."
}}

**LANGUAGE COMPLIANCE:**
- Detected language for "{question}" MUST be used for the "reasoning" field.
- If user asks in English, reasoning MUST be English.
- If user asks in Vietnamese, reasoning MUST be Vietnamese.

**YOUR ASSESSMENT (JSON):**"""

    @staticmethod
    def get_mcp_tool_selection_prompt(question: str, workspace_id: str, tools_description: str) -> str:
        """
        Prompt for LLM to select the best MCP tool for a given question.
        Used in dynamic tool discovery and selection (like ChatGPT/Claude).
        
        NOTE: Consider using get_combined_classification_and_tool_selection_prompt() 
        for better performance (50% faster).
        """
        return f"""You are a security analysis assistant with access to MCP (Model Context Protocol) tools.

**User Question:**
{question}

**Available MCP Tools:**
{tools_description}

**Your Task:**
1. Analyze the user's question carefully
2. Select the MOST appropriate tool from the list above that best matches the question
3. Generate the correct arguments for that tool

**CRITICAL INSTRUCTIONS:**
- You MUST respond with ONLY valid JSON, nothing else
- Do NOT include any explanation, commentary, or markdown formatting
- Do NOT wrap the JSON in code blocks (no ```)
- Check "Required Parameters" for each tool and include them in args
- Only use tools from the list above
- Choose based on tool description and user question intent

**Required JSON structure (NO COMMENTS, NO MARKDOWN):**
{{
    "server": "server-name",
    "tool": "tool-name",
    "args": {{ "arg_name": "value", "workspaceId": "your_workspace_id" }},
    "reasoning": "brief explanation in the user's language"
}}

**LANGUAGE COMPLIANCE:** You MUST respond in the SAME LANGUAGE as the user question: "{question}"

**Your JSON response:**"""



    @staticmethod
    def get_statistics_analysis_prompt(question: str, stats: Dict, chat_history: List[Dict] = None) -> str:
        """Prompt for analyzing security statistics and generating natural response"""
        if isinstance(stats, list):
            stats = stats[0] if stats else {}

        stats_json = json.dumps(stats, indent=2)
        history_section = MemoryPrompts.format_short_term_memory(chat_history)

        return f"""You are an elite Lead Security Analyst providing strategic insights on workspace security posture.

**User's Question:**
"{question}"

**Security Metrics Snapshot (JSON):**
```json
{stats_json}
```
{history_section}

**Your Task:**
Perform a high-level security posture analysis. Your response MUST follow this structure:

1. **📊 Executive Summary**: A concise overview of the current security health. Mention the overall **Security Score** and the total asset count.
2. **🛡️ Attack Surface Overview**: Summarize the scope (Assets, Targets, Technologies, Ports). Identify if the footprint is large or compact.
3. **⚠️ Vulnerability Profile**: Breakdown issues by severity (Critical, High, Medium, Low). Highlight any alarming counts.
4. **💡 Strategic Recommendations**: Provide 2-3 high-level security improvements based on these metrics.

**Response Requirements:**
- **LANGUAGE**: You MUST respond EXCLUSIVELY in the same language as the user's question: "{question}".
- **TONE**: Professional, authoritative, and data-driven.
- **STYLE**: Use clear headings and bullet points. Avoid fluff.
- **LENGTH**: 6-10 sentences total.

**Your expert analysis:**"""

    @staticmethod
    def get_vulnerabilities_analysis_prompt(question: str, data: Dict, chat_history: List[Dict] = None) -> str:
        """Prompt for analyzing vulnerabilities and generating natural response"""
        vulns = data.get("data", []) if isinstance(data, dict) else []
        total = data.get("total", len(vulns)) if isinstance(data, dict) else len(vulns)

        # Format vulnerabilities for context
        vuln_list = []
        for vuln in vulns[:20]:  # Limit to first 20 for context
            vuln_list.append({
                "name": vuln.get("name", "Unknown"),
                "severity": vuln.get("severity", "unknown"),
                "id": vuln.get("id", "")
            })

        vulns_json = json.dumps(vuln_list, indent=2)
        history_section = MemoryPrompts.format_short_term_memory(chat_history)

        return f"""You are a Senior Vulnerability Management Expert. Your goal is to transform raw scan data into an actionable remediation plan.

**User's Question:**
"{question}"

**Vulnerability Intelligence:**
- Total Vulnerabilities: {total}
- Sample Data (JSON):
```json
{vulns_json}
```
{history_section}

**Your Task:**
Synthesize the vulnerability data into a professional remediation report. Use this structure:

1. **🔴 Critical & High Risks**: Identify the most dangerous vulnerabilities. Explain the potential business impact (why should they care?).
2. **📉 Severity Distribution**: Briefly summarize the counts (e.g., "Found 5 Critical, 12 High...").
3. **✅ Immediate Action Plan**: Provide clear, technical steps to fix the top 3 issues. 
4. **🛡️ Long-term Hardening**: Suggest one process improvement (e.g., patching policy, WAF) to prevent these issues.

**Response Requirements:**
- **LANGUAGE**: You MUST respond EXCLUSIVELY in the same language as the user's question: "{question}".
- **TONE**: Urgent yet professional.
- **STYLE**: Focus on "Action over Observation". Use bold text for key terms.
- **LIMIT**: Show a Maximum of top 5 vulnerabilities if listing them.

**Your expert analysis:**"""

    @staticmethod
    def get_assets_analysis_prompt(question: str, data: Dict, chat_history: List[Dict] = None) -> str:
        """Prompt for analyzing assets/targets and generating natural response"""
        items = data.get("data", []) if isinstance(data, dict) else []
        total = data.get("total", len(items)) if isinstance(data, dict) else len(items)

        # Format assets for context
        asset_list = []
        for item in items[:15]:  # Limit to first 15
            asset_list.append({
                "value": item.get("value", "Unknown"),
                "id": item.get("id", "")
            })

        assets_json = json.dumps(asset_list, indent=2)
        history_section = MemoryPrompts.format_short_term_memory(chat_history)

        return f"""You are an Attack Surface Management (ASM) Expert. Your goal is to map out the digital footprint and identify exposure points.

**User's Question:**
"{question}"

**Asset Intelligence:**
- Total Discovered Items: {total}
- Specific Assets (JSON):
```json
{assets_json}
```
{history_section}

**Your Task:**
Provide a professional attack surface analysis. Use this structure:

1. **🌐 Digital Footprint Summary**: Describe the composition of the workspace (Domains, IP Ranges, Cloud services).
2. **🔍 Critical Assets**: Identify the 3-5 most important or exposed assets. Explain their role.
3. **🚩 Potential Exposure**: Point out any assets that look suspicious or high-risk (e.g., dev environments exposed to internet).
4. **📋 Governance Tips**: Suggest how to maintain this inventory and monitor for "Shadow IT".

**Response Requirements:**
- **LANGUAGE**: You MUST respond EXCLUSIVELY in the same language as the user's question: "{question}".
- **TONE**: Insightful and organized.
- **STYLE**: Use categories to group assets (e.g., "Web Endpoints", "Infrastructure").

**Your expert analysis:**"""

    @staticmethod
    def get_generic_analysis_prompt(question: str, data: Any, chat_history: List[Dict] = None) -> str:
        """Prompt for analyzing generic/unknown data types"""
        # Safely serialize data with size limit
        try:
            data_json = json.dumps(data, indent=2)[:1500]  # Limit to 1500 chars
            if len(json.dumps(data, indent=2)) > 1500:
                data_json += "\n... (data truncated)"
        except Exception:
            data_json = str(data)[:1500]
            
        history_section = MemoryPrompts.format_short_term_memory(chat_history)

        return f"""You are an expert security analyst helping users understand security scan data.

**User's Question:**
"{question}"

**Security Data Retrieved:**
```json
{data_json}
```
{history_section}

**Your Task:**
Analyze the provided data and generate a helpful, natural response that:

1. **Directly answers the user's question** based on available data
2. **Interprets the data structure**:
   - Explain what type of security data this represents
   - Highlight key metrics or findings
   - Identify important patterns or anomalies
3. **Provides insights**:
   - What this data tells us about security posture
   - Notable findings that require attention
   - Context for understanding the results
4. **Offers guidance**:
   - What actions should be taken based on this data
   - How to interpret the findings
5. **Responds in the SAME LANGUAGE as the user's question**

**Response Guidelines:**
- Be clear and educational
- Help the user understand what they're looking at
- Extract the most important information
- Provide actionable takeaways
- Keep response informative but concise (4-8 sentences)

**Your analysis:**"""

    @staticmethod
    def format_tools_for_llm(all_tools: Dict[str, List[Dict]]) -> str:
        """Format tools description for LLM"""
        formatted = []

        for server_name, tools in all_tools.items():
            for tool in tools:
                schema = tool.get('input_schema', {})
                properties = schema.get('properties', {})
                required = schema.get('required', [])
                
                tool_info = f"""
Server: {server_name}
Tool: {tool['name']}
Description: {tool['description']}
Input Schema: {json.dumps(properties)}
Required: {json.dumps(required)}
"""
                formatted.append(tool_info.strip())

        return "\n---\n".join(formatted)

    @staticmethod
    def get_question_classification_prompt(question: str) -> str:
        """Prompt for classifying question type (general knowledge vs security-related)"""
        # Get valid question types from enum
        valid_types = QuestionType.list_values()

        return f"""You are a question classifier for a security analysis system. Analyze the user's question and classify it.

**Valid Question Types:** {valid_types}

1. **{QuestionType.SECURITY_RELATED.value}**: ONLY questions explicitly about:
   - Security vulnerabilities, CVEs, exploits
   - Security scans, penetration testing results
   - Security assets, targets, attack surface
   - Threat intelligence, security statistics
   - Security tools, security configurations
   - Questions containing keywords: vulnerability, CVE, scan, security, threat, exploit, asset (in security context)

2. **{QuestionType.GENERAL_KNOWLEDGE.value}**: ALL other questions including:
   - Weather, news, current events
   - Educational topics (learning English, studying, courses)
   - General facts, definitions, how-to guides
   - Recommendations, advice (non-security)
   - ANY topic NOT explicitly related to cybersecurity

**CRITICAL RULES:**
- If the question does NOT contain security/vulnerability/scan keywords → {QuestionType.GENERAL_KNOWLEDGE.value}
- If unsure → default to {QuestionType.GENERAL_KNOWLEDGE.value}
- Educational/learning questions → {QuestionType.GENERAL_KNOWLEDGE.value}
- Only classify as {QuestionType.SECURITY_RELATED.value} if CLEARLY about cybersecurity

**User's Question:**
"{question}"

**Examples:**
- "What's the weather in Hanoi?" → {QuestionType.GENERAL_KNOWLEDGE.value}
- "Thời tiết ngày 27/11 thế nào ở Hà Nội?" → {QuestionType.GENERAL_KNOWLEDGE.value}
- "Đưa cho tôi lộ trình học tiếng anh B1" → {QuestionType.GENERAL_KNOWLEDGE.value}
- "How to learn Python?" → {QuestionType.GENERAL_KNOWLEDGE.value}
- "Recommend a good restaurant" → {QuestionType.GENERAL_KNOWLEDGE.value}
- "What are the critical vulnerabilities?" → {QuestionType.SECURITY_RELATED.value}
- "Show me security statistics" → {QuestionType.SECURITY_RELATED.value}
- "Có bao nhiêu lỗ hổng nghiêm trọng?" → {QuestionType.SECURITY_RELATED.value}
- "List all scanned assets" → {QuestionType.SECURITY_RELATED.value}

**Your classification (must be one of {valid_types}):**"""

    @staticmethod
    def get_general_knowledge_prompt(question: str, context: Any = None, chat_history: List[Dict] = None) -> str:
        """Prompt for answering general knowledge questions using MCP tools"""
        context_str = ""
        if context:
            try:
                context_str = f"\n\n**Retrieved Information:**\n```json\n{json.dumps(context, indent=2)[:2000]}\n```"
            except Exception:
                context_str = f"\n\n**Retrieved Information:**\n{str(context)[:2000]}"
                
        history_section = MemoryPrompts.format_short_term_memory(chat_history)

        return f"""You are a helpful AI assistant with access to various information sources.

**User's Question:**
"{question}"
{context_str}
{history_section}

**Your Task:**
Provide a comprehensive, detailed answer to the user's question based on the information available.

**CRITICAL LANGUAGE REQUIREMENT:**
- **MUST respond in EXACTLY the same language as the user's question**
- If question is in Vietnamese → answer in Vietnamese ONLY
- If question is in English → answer in English ONLY
- If question is in another language → answer in that language ONLY
- DO NOT mix languages or translate the question language

**Response Guidelines:**
1. **Provide detailed, comprehensive information** - include specific facts, numbers, dates, and relevant details
2. **Use all relevant retrieved information** - extract and present key details from the context
3. **Structure your answer clearly**:
   - Start with a direct answer to the main question
   - Provide supporting details and explanations
   - Include specific examples or data points when available
4. **Be thorough but organized** - aim for 4-8 sentences with rich information
5. **Be conversational and friendly** - don't mention that you're a security agent
6. **If information is incomplete**, explain what you know and what's missing
7. **Include relevant context** that helps the user understand the topic better

**Examples of Detail Level Expected:**
- Instead of: "It will be sunny"
- Provide: "The temperature will reach 28°C with clear skies and 60% humidity. Wind speed is expected at 15 km/h from the east."

**Your detailed response:"""

    @staticmethod
    def get_no_data_response_prompt(question: str, chat_history: List[Dict] = None) -> str:
        """Prompt for generating response when no scan data is available"""
        history_section = MemoryPrompts.format_short_term_memory(chat_history)
        
        return f"""You are an expert security analysis assistant specializing in vulnerability assessment and threat intelligence.

**User's Question:**
"{question}"
{history_section}

**Current Situation:**
This workspace currently has no security scan data available. No assets, vulnerabilities, or security metrics have been collected yet.

**Your Task:**
Generate a helpful, professional response that:
1. Directly acknowledges the user's question
2. Clearly explains that no scan data exists in this workspace
3. Guides the user on next steps (running a security scan to collect data)
4. Maintains a friendly, supportive tone without being overly apologetic
5. **IMPORTANT: Respond in the SAME LANGUAGE as the user's question**

**Response Guidelines:**
- Be concise (2-3 sentences maximum)
- Use natural, conversational language
- Avoid technical jargon unless necessary
- Focus on actionable next steps
- **Match the language of the user's question (English, Vietnamese, etc.)**

**Your Response:"""

    @staticmethod
    def get_cot_reasoning_prompt(
        question: str,
        tools_description: str,
        history: List[Dict[str, Any]],
        steps: List[Dict[str, Any]],
        initial_tasks: List[str] = None
    ) -> str:
        """
        Prompt for Chain of Thought (CoT) / ReAct reasoning loop.
        Allows the LLM to call multiple tools sequentially to answer the question.
        """
        steps_text = ""
        if steps:
            steps_text = "\n**Previous Steps:**\n"
            for i, step in enumerate(steps):
                steps_text += f"{i+1}. Thought: {step.get('thought')}\n"
                if 'tool_call' in step:
                    call = step['tool_call']
                    steps_text += f"   Tool: {call.get('server')}.{call.get('name')}\n"
                    steps_text += f"   Output: {json.dumps(step.get('observation'))[:1000]}\n"

        # Check for pending tasks to inject as a reminder
        pending_reminder = ""
        if initial_tasks and steps:
            completed_tools = [s.get('tool_call', {}).get('name') for s in steps]
            pending_tasks = [t for t in initial_tasks if t not in completed_tools]
            if pending_tasks:
                pending_reminder = f"""
**URGENT REMINDER:** You have NOT completed all tasks yet.
Pending tasks: {pending_tasks}
You MUST call {pending_tasks[0]} next. DO NOT provided 'final_answer' until these are done."""

        history_section = MemoryPrompts.format_short_term_memory(history)

        template = """### SYSTEM PROTOCOL: LANGUAGE COMPLIANCE
- The user's language is: "{question}"
- You MUST use this language for BOTH the 'thought' and 'answer' fields.
- PROHIBITED: Do not use any other language (like Korean, Chinese, or English) if the user's question is in a different language.

You are an Elite Security Orchestrator (Level 5 Analyst).
Your mission is to gather and analyze security intelligence following a strict Chain-of-Thought process.

**MISSION TARGET (User Question):**
"{question}"

**MCP INTELLIGENCE TOOLS:**
{tools_description}
{history_section}
{steps_text}
{pending_reminder}

**OPERATIONAL PHASE:**
1. **Assessment**: Determine if multiple data points are needed for a complete answer.
2. **Strategy**: 
   - If complex: Create a 'tasks' list of tool names to call.
   - If simple: Call the tool directly.
3. **Execution**: You MUST execute every tool in your 'tasks' list before providing a 'final_answer'.
4. **No Hallucinations**: DO NOT use placeholders like "[Actual data here]" or templates. If no data is found, state that clearly in the user's language.

**JSON OUTPUT SPECIFICATION (STRICT):**
You MUST provide ONLY a single, valid JSON object.
- NO comments inside the JSON.
- NO markdown delimiters.
- If 'workspaceId' is required and unknown, use "your_workspace_id".

{{
    "thought": "Deep reasoning in the USER'S LANGUAGE",
    "tasks": ["optional_list_of_tool_names"],
    "action": "call_tool",
    "tool_call": {{ "server": "server-name", "name": "tool-name", "args": {{ "arg": "val" }} }},
    "answer": "Professional synthesis/answer in the USER'S LANGUAGE (REQUIRED only if action is final_answer)"
}}

**YOUR ANALYTICAL RESPONSE (PURE JSON):**"""
        
        return template.format(
            question=question,
            tools_description=tools_description,
            history_section=history_section,
            steps_text=steps_text,
            pending_reminder=pending_reminder
        )

    @staticmethod
    def get_summary_prompt(
        question: str,
        formatted_steps: List[Dict[str, Any]]
    ) -> str:
        """
        Prompt for the final summary answer after all steps are completed.
        """
        return f"""### CRITICAL: LANGUAGE COMPLIANCE
1. User language: "{question}"
2. You MUST synthesize information and respond EXCLUSIVELY in that language.
3. DO NOT use Chinese or English if the user asked in Vietnamese.

**Expert Synthesis Context:**
USER QUESTION: {question}

**Raw Intelligence Gathered:**
{json.dumps(formatted_steps, indent=2)}

**Your Task:**
As an Elite Security Orchestrator, provide the final definitive answer. Your response MUST be:
- **Comprehensive**: Summarize ALL data found across all tools.
- **Structured**: Use clear headings (e.g., Summary, Findings, Next Steps).
- **Technical yet Actionable**: Provide specific IDs or names of vulnerabilities/assets found.
- **Direct**: Answer the question immediately in the first paragraph.

**Final Response Format:**
1. **Summary**: Direct answer to user question.
2. **Deep Dive/Findings**: The technical details extracted from the tools.
3. **Conclusion/Advisory**: What the user should do right now.

**Expert FINAL RESPONSE:**"""
