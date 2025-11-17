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
            # Let LLM generate a friendly response when no data is available
            no_data_response = self._generate_no_data_response(question)
            return {
                "success": False,
                "error": "No data available",
                "response": no_data_response
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

                # Check if result has actual data
                has_data = False

                # Check paginated response
                if "data" in result:
                    has_data = bool(result.get("data")) or result.get("total", 0) > 0
                # Check statistics response
                elif any(key in result for key in ["assets", "vuls", "vulnerabilities", "score"]):
                    # Statistics should have some meaningful values
                    has_data = (
                        result.get("assets", 0) > 0 or
                        result.get("vuls", 0) > 0 or
                        result.get("vulnerabilities", 0) > 0 or
                        "score" in result
                    )
                # Check generic response
                else:
                    has_data = bool(result and result != {})

                if not has_data:
                    logger.warning(f"MCP returned empty data for {tool_name}")
                    return None

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
            return None

    def _generate_no_data_response(self, question: str) -> str:
        """Generate a friendly response when no data is available"""
        prompt = f"""Bạn là trợ lý bảo mật. User hỏi: "{question}"

Tuy nhiên workspace này hiện chưa có dữ liệu quét bảo mật.

Hãy trả lời ngắn gọn, tự nhiên bằng tiếng Việt (2-3 câu):
- Giải thích rằng chưa có dữ liệu
- Gợi ý user cần chạy quét bảo mật trước
- Giữ giọng điệu thân thiện, chuyên nghiệp

CHÚ Ý: Chỉ trả lời bằng tiếng Việt, KHÔNG dịch sang tiếng Anh, KHÔNG giải thích thêm.

Câu trả lời:"""

        try:
            response = self.llm.invoke(prompt).content.strip()
            return response
        except Exception as e:
            logger.error(f"Failed to generate no-data response: {e}")
            # Fallback to a simple message
            return "Hiện tại workspace chưa có dữ liệu quét bảo mật. Vui lòng chạy quét bảo mật trước để tôi có thể phân tích và trả lời câu hỏi của bạn."

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
