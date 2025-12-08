"""Security analysis agent with MCP integration and streaming support"""

from typing import Dict, Any, Optional, AsyncGenerator
from uuid import UUID
from sqlalchemy.orm import Session
import asyncio
import json

from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import JsonOutputParser
from agents.core import BaseAgent, AgentRole, AgentType
from common.logger import logger
from common.config import configs
from common.types import QuestionType
from llms import llm_manager
from llms.prompts import AnalysisAgentPrompts
from tools.mcp_client import MCPManager
from data.database import postgres_db


class AnalysisAgent(BaseAgent):
    """Analyzes security vulnerabilities using LLM and MCP tools"""

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
        """Execute task synchronously"""
        try:
            action = task.get("action", "analyze_vulnerabilities")
            question = task.get("question", "Provide security summary")

            if action == "analyze_vulnerabilities":
                return asyncio.run(self.analyze_vulnerabilities(question))

            return {"success": False, "error": f"Unknown action: {action}"}
        except Exception as e:
            logger.error(f"Task execution failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def execute_task_streaming(self, task: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute task with streaming events"""
        try:
            action = task.get("action", "analyze_vulnerabilities")
            question = task.get("question", "Provide security summary")

            yield {
                "type": "thinking",
                "thought": "Analyzing security data and preparing response",
                "agent": self.name
            }

            if action == "analyze_vulnerabilities":
                async for event in self.analyze_vulnerabilities_streaming(question):
                    yield event
            else:
                yield {"type": "error", "error": f"Unknown action: {action}", "agent": self.name}

        except Exception as e:
            logger.error(f"Streaming task execution failed: {e}", exc_info=True)
            yield {"type": "error", "error": str(e), "agent": self.name}

    async def analyze_vulnerabilities(self, question: str) -> Dict[str, Any]:
        """Analyze vulnerabilities with combined classification and tool selection"""
        logger.info(f"Analyzing: {question[:100]}...")

        scan_data = await self._fetch_mcp_data(question)
        question_type = self._ensure_question_type_enum(scan_data.get("question_type") if scan_data else None)
        response = await self._generate_analysis(question, scan_data, question_type)

        if not scan_data:
            return {"success": False, "error": "No data available", "response": response}

        return {
            "success": True,
            "response": response,
            "data_source": scan_data.get("source", "MCP"),
            "stats": scan_data.get("stats")
        }

    async def analyze_vulnerabilities_streaming(self, question: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Analyze with streaming - single LLM call for classification and tool selection"""
        logger.info(f"Streaming analysis: {question[:100]}...")

        scan_data = await self._fetch_mcp_data(question)
        question_type = self._ensure_question_type_enum(scan_data.get("question_type") if scan_data else None)

        # Extract tool info for events
        if scan_data:
            tool_name = scan_data.get("tool", "mcp_tool")
            tool_description = scan_data.get("tool_description", "Fetching data from MCP")
            full_tool_name = f"{scan_data.get('server', 'unknown')}/{tool_name}"
        else:
            tool_name = "mcp_tool_selection"
            tool_description = "Searching for appropriate MCP tool"
            full_tool_name = tool_name

        # Yield tool execution events
        yield {"type": "tool_start", "tool_name": tool_name, "tool_description": tool_description, "agent": self.name}
        yield {
            "type": "tool_output",
            "tool_name": tool_name,
            "status": "success" if scan_data else "no_data",
            "output": {
                "has_data": bool(scan_data),
                "source": scan_data.get("source") if scan_data else None,
                "full_tool_name": full_tool_name
            },
            "agent": self.name
        }
        yield {"type": "tool_end", "tool_name": tool_name, "agent": self.name}

        # Stream LLM analysis
        async for event in self._generate_analysis_streaming(question, scan_data, question_type):
            yield event

        # Yield final result
        yield {
            "type": "result",
            "data": {
                "success": bool(scan_data),
                "has_data": bool(scan_data),
                "data_source": scan_data.get("source", "MCP") if scan_data else None
            },
            "agent": self.name
        }

    async def _fetch_mcp_data(self, question: str) -> Optional[Dict[str, Any]]:
        """Fetch data from MCP with combined classification and tool selection"""
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

            selected = await self._classify_and_select_tool_combined(question, all_tools)
            if not selected:
                logger.warning("LLM could not classify and select tool")
                return None

            server_name = selected["server"]
            tool_name = selected["tool"]
            tool_args = selected["args"]
            question_type = selected.get("question_type", QuestionType.SECURITY_RELATED)

            # Get tool description
            tool_description = "Fetching data from MCP"
            for server, tools in all_tools.items():
                if server == server_name:
                    for tool_info in tools:
                        if tool_info.get("name") == tool_name:
                            tool_description = tool_info.get("description", tool_description)
                            break

            logger.info(f"LLM classified as '{question_type}' and selected: {server_name}.{tool_name}")
            logger.debug(f"Arguments: {tool_args}")

            result = await self.mcp_manager.call_tool(server=server_name, tool=tool_name, args=tool_args)

            if not result or result.get("isError"):
                logger.warning(f"MCP call failed: {result.get('content') if result else 'No response'}")
                return None

            if not self._has_data(result, tool_name):
                logger.warning(f"MCP returned empty data for {tool_name}")
                return None

            return {
                "source": f"MCP ({server_name}/{tool_name})",
                "stats": result,
                "tool": tool_name,
                "server": server_name,
                "tool_description": tool_description,
                "question_type": question_type
            }

        except Exception as e:
            logger.error(f"MCP fetch error: {e}", exc_info=True)
            return None

    async def _classify_and_select_tool_combined(self, question: str, all_tools: Dict) -> Optional[Dict]:
        """Classify question type and select MCP tool in single LLM call"""
        parser = JsonOutputParser()

        base_prompt = AnalysisAgentPrompts.get_combined_classification_and_tool_selection_prompt(
            question=question,
            workspace_id=str(self.workspace_id),
            tools_description=AnalysisAgentPrompts.format_tools_for_llm(all_tools)
        )

        valid_types = QuestionType.list_values()
        format_instructions = parser.get_format_instructions()
        enhanced_prompt = f"""{base_prompt}

{format_instructions}

You MUST respond with valid JSON containing exactly these fields:
- "question_type": one of {valid_types} (string)
- "server": the server name (string)
- "tool": the tool name (string)
- "args": the tool arguments (object)
- "reasoning": brief explanation (string)
"""
        try:
            chain = self.llm | parser
            result = await chain.ainvoke(enhanced_prompt)

            required_fields = ["server", "tool", "args", "question_type", "reasoning"]
            if not all(key in result for key in required_fields):
                logger.error(f"Missing required fields in JSON: {result}")
                return None

            try:
                question_type_str = result["question_type"]
                result["question_type"] = QuestionType.from_string(question_type_str)
            except ValueError as e:
                logger.error(f"Invalid question_type '{result.get('question_type')}': {e}")
                result["question_type"] = QuestionType.SECURITY_RELATED
                logger.warning(f"Defaulting to {QuestionType.SECURITY_RELATED.value}")

            return result

        except Exception as e:
            logger.error(f"LLM combined classification and tool selection failed: {e}", exc_info=True)
            return None

    def _ensure_question_type_enum(self, question_type: Any) -> QuestionType:
        """Convert question_type to QuestionType enum"""
        if isinstance(question_type, QuestionType):
            return question_type

        if isinstance(question_type, str):
            try:
                return QuestionType.from_string(question_type)
            except ValueError:
                logger.warning(f"Invalid question_type '{question_type}', defaulting to SECURITY_RELATED")
                return QuestionType.SECURITY_RELATED

        return QuestionType.SECURITY_RELATED

    def _has_data(self, result: Dict, tool_name: str) -> bool:
        """Check if MCP result contains data"""
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

    def _select_prompt(self, question: str, scan_data: Optional[Dict], question_type: QuestionType) -> str:
        """Select appropriate prompt based on question type and data"""
        if not scan_data:
            return AnalysisAgentPrompts.get_no_data_response_prompt(question)

        stats = scan_data.get("stats", {})
        tool = scan_data.get("tool", "unknown")

        if question_type == QuestionType.GENERAL_KNOWLEDGE:
            return AnalysisAgentPrompts.get_general_knowledge_prompt(question, stats)

        tool_lower = tool.lower()
        stats_str_lower = str(stats).lower()

        if "statistics" in tool_lower or "score" in stats_str_lower:
            return AnalysisAgentPrompts.get_statistics_analysis_prompt(question, stats)
        elif "vulnerab" in tool_lower or "severity" in stats_str_lower:
            return AnalysisAgentPrompts.get_vulnerabilities_analysis_prompt(question, stats)
        elif "asset" in tool_lower or "target" in tool_lower:
            return AnalysisAgentPrompts.get_assets_analysis_prompt(question, stats)
        else:
            return AnalysisAgentPrompts.get_generic_analysis_prompt(question, stats)

    async def _generate_analysis(
        self,
        question: str,
        scan_data: Optional[Dict],
        question_type: QuestionType
    ) -> str:
        """Generate analysis response (sync)"""
        prompt = self._select_prompt(question, scan_data, question_type)

        try:
            return self.llm.invoke(prompt).content.strip()
        except Exception as e:
            logger.error(f"Failed to generate analysis: {e}", exc_info=True)
            if scan_data:
                stats = scan_data.get("stats", {})
                return f"Analysis data retrieved:\n\n{json.dumps(stats, indent=2)[:500]}"
            return "This workspace currently has no security scan data. Please run a security scan first."

    async def _buffer_llm_chunks(
        self,
        llm_stream: AsyncGenerator,
        min_chunk_size: int
    ) -> AsyncGenerator[str, None]:
        """Buffer LLM chunks to reduce response count"""
        buffer = ""

        async for chunk in llm_stream:
            if isinstance(chunk, BaseMessage) and chunk.content:
                text = chunk.content
            elif isinstance(chunk, str):
                text = chunk
            else:
                continue

            buffer += text

            if len(buffer) >= min_chunk_size:
                yield buffer
                buffer = ""

        if buffer:
            yield buffer

    async def _generate_analysis_streaming(
        self,
        question: str,
        scan_data: Optional[Dict],
        question_type: QuestionType = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream LLM analysis with buffering"""
        min_chunk_size = configs.llm.min_chunk_size
        prompt = self._select_prompt(question, scan_data, question_type)

        try:
            async for buffered_text in self._buffer_llm_chunks(self.llm.astream(prompt), min_chunk_size):
                yield {"type": "delta", "text": buffered_text, "agent": self.name}
        except Exception as e:
            logger.error(f"Failed to stream analysis: {e}", exc_info=True)
            if scan_data:
                stats = scan_data.get("stats", {})
                yield {"type": "delta", "text": f"\n\nAnalysis data:\n{json.dumps(stats, indent=2)[:500]}", "agent": self.name}
            else:
                yield {"type": "delta", "text": "This workspace currently has no security scan data. Please run a security scan first.", "agent": self.name}
