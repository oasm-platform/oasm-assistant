from typing import Dict, Any, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
import asyncio
import json

from agents.core import BaseAgent, AgentRole, AgentType
from common.logger import logger
from llms import llm_manager
from llms.prompts import AnalysisAgentPrompts
from tools.mcp_client import MCPManager
from data.database import postgres_db

class AnalysisAgent(BaseAgent):
    """
    Dynamic Analysis Agent with MCP Integration

    How it works (like ChatGPT/Claude Desktop):
    1. Discover all available MCP tools dynamically
    2. LLM reads tool descriptions and selects the best one
    3. Call the selected tool with appropriate arguments
    4. Generate human-friendly response from tool results
    """

    def __init__(
        self,
        db_session: Session,
        workspace_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        **kwargs
    ):
        super().__init__(
            name="AnalysisAgent",
            role=AgentRole.ANALYSIS_AGENT,
            agent_type=AgentType.GOAL_BASED,
            **kwargs
        )

        self.session = db_session
        self.workspace_id = workspace_id
        self.user_id = user_id
        self.llm = llm_manager.get_llm()

        # MCP setup - dynamic discovery
        if workspace_id and user_id:
            self.mcp_manager = MCPManager(postgres_db, workspace_id, user_id)
            logger.info(f"✓ MCP enabled for workspace {workspace_id}")
        else:
            self.mcp_manager = None
            logger.warning("⚠ MCP disabled - no workspace/user provided")

    # Abstract methods (required by BaseAgent)

    def setup_tools(self) -> List[Any]:
        """No traditional tools - uses dynamic MCP instead"""
        return []

    def create_prompt_template(self) -> str:
        """Prompts are inline in methods"""
        return ""

    def process_observation(self, observation: Any) -> Dict[str, Any]:
        """Basic observation processing"""
        return {"observation": observation, "processed": True}

    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute analysis task"""
        try:
            action = task.get("action", "analyze_vulnerabilities")
            question = task.get("question", "Provide security summary")

            if action == "analyze_vulnerabilities":
                # Simply use asyncio.run with nest_asyncio support
                # nest_asyncio allows this to work even in running event loops
                return asyncio.run(self.analyze_vulnerabilities(question))
            else:
                return {"success": False, "error": f"Unknown action: {action}"}

        except Exception as e:
            logger.error(f"Task execution failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    # Main analysis method
    async def analyze_vulnerabilities(self, question: str) -> Dict[str, Any]:
        """
        Analyze security vulnerabilities dynamically

        Flow (like ChatGPT/Claude):
        1. Discover available MCP tools
        2. LLM selects best tool for the question
        3. Call the tool with LLM-generated arguments
        4. Format response in human-friendly way
        """
        logger.info(f"Analyzing: {question[:100]}...")

        # Step 1: Fetch data via dynamic MCP
        scan_data = await self._fetch_mcp_data_dynamic(question)

        if not scan_data:
            return {
                "success": False,
                "error": "No data available",
                "response": "Unable to fetch security data. Please ensure MCP is configured and workspace has data."
            }

        # Step 2: Generate human-friendly analysis
        analysis = self._generate_analysis(question, scan_data)

        return {
            "success": True,
            "response": analysis,
            "data_source": scan_data.get("source", "MCP"),
            "stats": scan_data.get("stats")
        }

    # Dynamic MCP tool discovery and selection (like ChatGPT/Claude)

    async def _fetch_mcp_data_dynamic(self, question: str) -> Optional[Dict[str, Any]]:
        """
        Dynamically discover and use MCP tools

        This is how ChatGPT, Claude Desktop, and other modern AI assistants work:
        - No hardcoded tool names
        - LLM reads all available tools and their descriptions
        - LLM selects the best tool for the user's question
        - LLM generates appropriate arguments
        """
        if not self.mcp_manager:
            logger.warning("MCP not available")
            return None

        try:
            # Initialize MCP connection
            await self.mcp_manager.initialize()

            # Step 1: Discover all available tools (dynamic)
            all_tools = await self.mcp_manager.get_all_tools()
            if not all_tools:
                logger.warning("No MCP tools available")
                return None

            logger.info(f"Discovered {sum(len(tools) for tools in all_tools.values())} MCP tools from {len(all_tools)} servers")

            # Step 2: Let LLM select the best tool
            selected = self._llm_select_tool(question, all_tools)
            if not selected:
                logger.warning("LLM could not select appropriate tool")
                return None

            server_name = selected["server"]
            tool_name = selected["tool"]
            tool_args = selected["args"]

            logger.info(f"LLM selected: {server_name}.{tool_name}")
            logger.debug(f"Arguments: {tool_args}")

            # Step 3: Call the selected tool
            result = await self.mcp_manager.call_tool(
                server=server_name,
                tool=tool_name,
                args=tool_args
            )

            if result and not result.get("isError"):
                # Handle different response structures:
                # - Paginated tools (get_vulnerabilities, get_assets, get_targets): {data: [], total, page, ...}
                # - Non-paginated tools (get_statistics): {assets, vuls, score, ...}

                # For paginated responses, pass the whole object (not just data array)
                # This preserves pagination info (total, page, etc.) for proper formatting
                stats_data = result

                return {
                    "source": f"MCP ({server_name}/{tool_name})",
                    "stats": stats_data,
                    "tool": tool_name
                }
            else:
                logger.warning(f"MCP call failed: {result.get('content') if result else 'No response'}")
                return None

        except Exception as e:
            logger.error(f"MCP fetch error: {e}", exc_info=True)
            return None

    def _llm_select_tool(self, question: str, all_tools: Dict[str, List[Dict]]) -> Optional[Dict]:
        """Use LLM to select the best tool (like ChatGPT/Claude)"""
        prompt = AnalysisAgentPrompts.get_mcp_tool_selection_prompt(
            question=question,
            workspace_id=str(self.workspace_id),
            tools_description=AnalysisAgentPrompts.format_tools_for_llm(all_tools)
        )

        try:
            content = self.llm.invoke(prompt).content.strip()
            # Extract JSON from markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            result = json.loads(content)
            logger.info(f"LLM reasoning: {result.get('reasoning', 'N/A')}")
            return result

        except Exception as e:
            logger.error(f"LLM tool selection failed: {e}")
            return self._fallback_tool_selection(question, all_tools)

    def _fallback_tool_selection(self, question: str, all_tools: Dict[str, List[Dict]]) -> Optional[Dict]:
        """Fallback tool selection using keyword matching"""
        oasm_tools = all_tools.get("oasm-platform", [])
        if not oasm_tools:
            logger.warning("Fallback: No suitable tools found")
            return None

        question_lower = question.lower()

        # Keyword mapping: (keywords, tool_name, extra_args)
        keyword_map = [
            (["summary", "overview", "statistics", "tình hình", "tổng quan", "thống kê", "như thế nào", "ra sao"],
             "get_statistics", {}),
            (["vulnerabilit", "lỗ hổng", "lỗi bảo mật", "vulnerability", "weakness"],
             "get_vulnerabilities", {"limit": 20, "page": 1}),
            (["asset", "target", "tài sản", "mục tiêu", "host", "domain"],
             "get_assets", {"limit": 20, "page": 1})
        ]

        # Try to match keywords
        for keywords, tool_name, extra_args in keyword_map:
            if any(kw in question_lower for kw in keywords):
                tool = next((t for t in oasm_tools if t["name"] == tool_name), None)
                if tool:
                    logger.info(f"Fallback: Using {tool_name}")
                    return {
                        "server": "oasm-platform",
                        "tool": tool_name,
                        "args": {"workspaceId": str(self.workspace_id), **extra_args},
                        "reasoning": f"Fallback: keyword match → {tool_name}"
                    }

        # Default to get_statistics or first OASM tool
        stats_tool = next((t for t in oasm_tools if t["name"] == "get_statistics"), None)
        if stats_tool:
            logger.info("Fallback: Default to get_statistics")
            return {
                "server": "oasm-platform",
                "tool": "get_statistics",
                "args": {"workspaceId": str(self.workspace_id)},
                "reasoning": "Fallback: default statistics"
            }

        # Use first available tool
        first_tool = oasm_tools[0]
        logger.info(f"Fallback: Using first OASM tool {first_tool['name']}")
        return {
            "server": "oasm-platform",
            "tool": first_tool["name"],
            "args": self._generate_tool_args(first_tool),
            "reasoning": f"Fallback: first tool ({first_tool['name']})"
        }

    def _generate_tool_args(self, tool: Dict) -> Dict[str, Any]:
        """Generate appropriate arguments for a tool based on its schema"""
        schema = tool.get('input_schema', {})
        properties = schema.get('properties', {})
        required = schema.get('required', [])
        args = {}

        # Always include workspaceId if available
        if 'workspaceId' in properties:
            args['workspaceId'] = str(self.workspace_id)

        # Add pagination for list-type tools
        tool_name = tool.get('name', '')
        if any(kw in tool_name.lower() for kw in ['get_vulnerabilities', 'get_assets', 'get_targets']):
            if 'limit' in properties:
                args['limit'] = 20
            if 'page' in properties:
                args['page'] = 1

        # Handle other required parameters with type-based defaults
        type_defaults = {'string': '', 'number': 0, 'integer': 0, 'boolean': False, 'array': [], 'object': {}}
        for param in required:
            if param not in args:
                param_type = properties.get(param, {}).get('type', 'string')
                args[param] = type_defaults.get(param_type, '')

        return args

    def _generate_analysis(self, question: str, scan_data: Dict) -> str:
        """Generate human-friendly analysis"""
        stats = scan_data.get("stats", {})
        tool = scan_data.get("tool", "unknown")

        if "statistics" in tool or "score" in str(stats):
            return AnalysisAgentPrompts.format_statistics_report(stats)
        elif "vulnerabilities" in tool or "severity" in str(stats):
            return AnalysisAgentPrompts.format_vulnerabilities_report(stats)
        elif "assets" in tool or "targets" in tool:
            return AnalysisAgentPrompts.format_assets_report(stats)
        else:
            return AnalysisAgentPrompts.format_generic_report(question, stats)
