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
    """Dynamic Security Analysis Agent with MCP Integration"""

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

        if workspace_id and user_id:
            self.mcp_manager = MCPManager(postgres_db, workspace_id, user_id)
            logger.info(f"✓ MCP enabled for workspace {workspace_id}")
        else:
            self.mcp_manager = None
            logger.warning("⚠ MCP disabled - no workspace/user provided")

    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        try:
            action = task.get("action", "analyze_vulnerabilities")
            question = task.get("question", "Provide security summary")

            if action == "analyze_vulnerabilities":
                return asyncio.run(self.analyze_vulnerabilities(question))

            return {"success": False, "error": f"Unknown action: {action}"}
        except Exception as e:
            logger.error(f"Task execution failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def analyze_vulnerabilities(self, question: str) -> Dict[str, Any]:
        logger.info(f"Analyzing: {question[:100]}...")

        scan_data = await self._fetch_mcp_data(question)
        response = self._generate_analysis(question, scan_data)

        if not scan_data:
            return {
                "success": False,
                "error": "No data available",
                "response": response
            }

        return {
            "success": True,
            "response": response,
            "data_source": scan_data.get("source", "MCP"),
            "stats": scan_data.get("stats")
        }

    async def _fetch_mcp_data(self, question: str) -> Optional[Dict[str, Any]]:
        if not self.mcp_manager:
            logger.warning("MCP not available")
            return None

        try:
            await self.mcp_manager.initialize()

            all_tools = await self.mcp_manager.get_all_tools()
            if not all_tools:
                logger.warning("No MCP tools available")
                return None

            logger.info(f"Discovered {sum(len(tools) for tools in all_tools.values())} MCP tools from {len(all_tools)} servers")

            selected = self._select_tool_with_llm(question, all_tools)
            if not selected:
                logger.warning("LLM could not select appropriate tool")
                return None

            server_name = selected["server"]
            tool_name = selected["tool"]
            tool_args = selected["args"]

            logger.info(f"LLM selected: {server_name}.{tool_name}")
            logger.debug(f"Arguments: {tool_args}")

            result = await self.mcp_manager.call_tool(
                server=server_name,
                tool=tool_name,
                args=tool_args
            )

            if not result or result.get("isError"):
                logger.warning(f"MCP call failed: {result.get('content') if result else 'No response'}")
                return None

            if not self._has_data(result, tool_name):
                logger.warning(f"MCP returned empty data for {tool_name}")
                return None

            return {
                "source": f"MCP ({server_name}/{tool_name})",
                "stats": result,
                "tool": tool_name
            }

        except Exception as e:
            logger.error(f"MCP fetch error: {e}", exc_info=True)
            return None

    def _select_tool_with_llm(self, question: str, all_tools: Dict[str, List[Dict]]) -> Optional[Dict]:
        prompt = AnalysisAgentPrompts.get_mcp_tool_selection_prompt(
            question=question,
            workspace_id=str(self.workspace_id),
            tools_description=AnalysisAgentPrompts.format_tools_for_llm(all_tools)
        )

        try:
            content = self.llm.invoke(prompt).content.strip()
            if not content:
                logger.error("LLM returned empty response")
                return None

            # Extract JSON from markdown code blocks or other formatting
            original_content = content

            # Try to extract from ```json ... ```
            if "```json" in content:
                parts = content.split("```json")
                if len(parts) > 1:
                    content = parts[1].split("```")[0].strip()
            # Try to extract from ``` ... ```
            elif "```" in content:
                parts = content.split("```")
                if len(parts) >= 3:
                    content = parts[1].strip()

            # Try to find JSON object directly (starts with { and ends with })
            if not content.startswith("{"):
                # Search for first { and last }
                start_idx = content.find("{")
                end_idx = content.rfind("}")
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    content = content[start_idx:end_idx + 1]

            if not content or not content.strip():
                logger.error("No JSON content found after extraction")
                logger.error(f"Original response: {original_content[:500]}")
                return None

            result = json.loads(content)

            # Validate required fields
            if not all(key in result for key in ["server", "tool", "args"]):
                logger.error(f"Missing required fields in JSON: {result}")
                return None

            return result

        except json.JSONDecodeError as e:
            logger.error(f"LLM response is not valid JSON: {e}")
            logger.error(f"Extracted content: {content[:500] if 'content' in locals() else 'N/A'}")
            logger.error(f"Original response: {original_content[:500] if 'original_content' in locals() else 'N/A'}")
            return None
        except Exception as e:
            logger.error(f"LLM tool selection failed: {e}", exc_info=True)
            return None

    def _has_data(self, result: Dict, tool_name: str) -> bool:
        if "data" in result:
            return bool(result.get("data")) or result.get("total", 0) > 0

        if any(key in result for key in ["assets", "vuls", "vulnerabilities", "score"]):
            return (
                result.get("assets", 0) > 0 or
                result.get("vuls", 0) > 0 or
                result.get("vulnerabilities", 0) > 0 or
                "score" in result
            )

        return bool(result and result != {})

    def _generate_analysis(self, question: str, scan_data: Optional[Dict]) -> str:
        # No data case
        if not scan_data:
            prompt = AnalysisAgentPrompts.get_no_data_response_prompt(question)
            try:
                return self.llm.invoke(prompt).content.strip()
            except Exception as e:
                logger.error(f"Failed to generate no-data response: {e}")
                return "This workspace currently has no security scan data. Please run a security scan first so I can analyze and answer your questions."

        # Has data - generate appropriate report
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
