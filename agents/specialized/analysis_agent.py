"""Security analysis agent with MCP integration and streaming support"""

from typing import Dict, Any, Optional, AsyncGenerator, List
from uuid import UUID
from sqlalchemy.orm import Session
import asyncio
import json
import traceback

from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import JsonOutputParser
from agents.core import CoTAgent, AgentRole, AgentType
from common.logger import logger
from common.config import configs
from common.types import QuestionType
from llms import LLMManager
from llms.prompts import AnalysisAgentPrompts
from data.database import postgres_db


class AnalysisAgent(CoTAgent):
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
            db_session=db_session,
            workspace_id=workspace_id,
            user_id=user_id,
            agent_type=AgentType.GOAL_BASED,
            **kwargs
        )

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task asynchronously"""
        try:
            action = task.get("action", "analyze_vulnerabilities")
            question = task.get("question", "Provide security summary")
            chat_history = task.get("chat_history")

            if action == "analyze_vulnerabilities":
                return await self.analyze_vulnerabilities(question, chat_history)

            return {"success": False, "error": f"Unknown action: {action}"}
        except Exception as e:
            logger.error("Task execution failed: {}", e)
            return {"success": False, "error": str(e)}

    async def execute_task_streaming(self, task: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute task with streaming events"""
        try:
            action = task.get("action", "analyze_vulnerabilities")
            question = task.get("question", "Provide security summary")
            chat_history = task.get("chat_history")

            if action == "analyze_vulnerabilities":
                async for event in self.analyze_vulnerabilities_streaming(question, chat_history):
                    yield event
            else:
                yield {"type": "error", "error": f"Unknown action: {action}", "agent": self.name}

        except Exception as e:
            logger.exception("Streaming task execution failed: {}", e)
            
            error_message = LLMManager.get_friendly_error_message(e)
            
            yield {
                "type": "error", 
                "error": error_message,
                "error_type": type(e).__name__,
                "error_message": f"Failed to execute task: {error_message}",
                "agent": self.name,
                "recoverable": True,
                "retry_suggested": True
            }

    async def analyze_vulnerabilities(self, question: str, chat_history: List[Dict] = None) -> Dict[str, Any]:
        """Analyze vulnerabilities with combined classification and tool selection"""
        logger.info(f"Analyzing: {question[:100]}...")

        scan_data = await self._fetch_mcp_data(question)
        question_type = self._ensure_question_type_enum(scan_data.get("question_type") if scan_data else None)
        response = await self._generate_analysis(question, scan_data, question_type, chat_history)

        if not scan_data:
            return {"success": False, "error": "No data available", "response": response}

        return {
            "success": True,
            "response": response,
            "data_source": scan_data.get("source", "MCP"),
            "stats": scan_data.get("stats")
        }

    async def analyze_vulnerabilities_streaming(self, question: str, chat_history: List[Dict] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """Analyze with streaming - using centralized CoT reasoning"""
        logger.info(f"Streaming analysis: {question[:100]}...")

        async for event in self._execute_cot_loop(question, chat_history):
            yield event

        yield {
            "type": "result",
            "data": {
                "success": True,
                "agent": self.name
            }
        }

    def get_reasoning_prompt(self, **kwargs) -> str:
        """Provide specialized CoT prompt for security analysis"""
        return AnalysisAgentPrompts.get_cot_reasoning_prompt(**kwargs)

    def get_summary_prompt(self, question: str, steps: List[Dict], **kwargs) -> str:
        """Provide specialized summary prompt for security analysis"""
        return AnalysisAgentPrompts.get_summary_prompt(question, steps)

    async def _generate_fallback_response(self, question: str, chat_history: List[Dict]) -> AsyncGenerator[Dict[str, Any], None]:
        """Specific fallback for AnalysisAgent when MCP is unavailable"""
        async for event in self._generate_analysis_streaming(question, None, QuestionType.GENERAL_KNOWLEDGE, chat_history):
            yield event


    async def _fetch_mcp_data_streaming(self, question: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Fetch data from MCP with events streaming"""
        if not self.mcp_manager:
            logger.warning("MCP not available")
            return
        try:
            await self.mcp_manager.initialize()


            all_tools = await self.mcp_manager.get_all_tools()
            if not all_tools:
                logger.warning("No MCP tools available")
                return

            tool_count = sum(len(tools) for tools in all_tools.values())
            logger.debug(f"Discovered {tool_count} MCP tools from {len(all_tools)} servers")


            selected = await self._classify_and_select_tool_combined(question, all_tools)
            if not selected:
                logger.warning("LLM could not classify and select tool")
                return


            server_name = selected["server"]
            tool_name = selected["tool"]
            tool_args = selected["args"]
            
            # Force overwrite workspaceId to prevent prompt injection
            if self.workspace_id:
                tool_args["workspaceId"] = str(self.workspace_id)
                
            question_type = selected.get("question_type", QuestionType.SECURITY_RELATED)

            # Validate tool exists
            tool_description = "Fetching data from MCP"
            tool_exists = False
            for server, tools in all_tools.items():
                if server == server_name:
                    for tool_info in tools:
                        if tool_info.get("name") == tool_name:
                            tool_exists = True
                            tool_description = tool_info.get("description", tool_description)
                            break
                if tool_exists:
                    break
            
            if not tool_exists:
                yield {
                    "type": "error",
                    "error": f"Selected tool {tool_name} not found",
                    "agent": self.name
                }
                logger.warning(f"Selected tool {server_name}/{tool_name} not found")
                return

            logger.debug(f"LLM classified as '{question_type}' and selected: {server_name}.{tool_name}")
            
            # Yield tool start event BEFORE execution
            yield {
                "type": "tool_start", 
                "tool_name": tool_name, 
                "tool_description": tool_description, 
                "parameters": tool_args,
                "agent": self.name
            }
            yield {"type": "delta", "text": f"\n\n> 🔍 **Searching:** Calling tool `{server_name}.{tool_name}`...\n", "agent": self.name}


            # Execute tool
            result = await self.mcp_manager.call_tool(server=server_name, tool=tool_name, args=tool_args)

            if not result or result.get("isError"):
                error_msg = result.get('content') if result else 'No response'
                logger.warning(f"MCP call failed: {error_msg}")
                yield {
                    "type": "tool_output",
                    "tool_name": tool_name,
                    "status": "error",
                    "error": error_msg,
                    "agent": self.name
                }
                return

            has_data = self._has_data(result, tool_name)
            if not has_data:
                logger.warning(f"MCP returned empty data for {tool_name}")
            
            # Yield tool output event AFTER execution
            full_tool_name = f"{server_name}/{tool_name}"
            yield {
                "type": "tool_output",
                "tool_name": tool_name,
                "status": "success",
                "output": {
                    "has_data": has_data,
                    "source": f"MCP ({full_tool_name})",
                    "full_tool_name": full_tool_name
                },
                "agent": self.name
            }
            yield {"type": "delta", "text": f"> ✅ **Found data:** {full_tool_name}\n\n", "agent": self.name}


            final_data = {
                "source": f"MCP ({server_name}/{tool_name})",
                "stats": result,
                "tool": tool_name,
                "server": server_name,
                "tool_description": tool_description,
                "question_type": question_type
            }
            
            # Yield internal result data for the caller to use
            yield {"type": "result_data", "data": final_data}

        except Exception as e:
            logger.exception("MCP fetch streaming error: {}", e)
            
            # Provide user-friendly error message
            error_message = LLMManager.get_friendly_error_message(e)
            
            yield {
                "type": "error", 
                "error": error_message,
                "error_type": "MCPFetchError",
                "error_message": f"Failed to fetch data from MCP tools: {error_message}",
                "agent": self.name,
                "recoverable": True,
                "retry_suggested": True
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

            logger.debug(f"Discovered {sum(len(tools) for tools in all_tools.values())} MCP tools from {len(all_tools)} servers")

            selected = await self._classify_and_select_tool_combined(question, all_tools)
            if not selected:
                logger.warning("LLM could not classify and select tool")
                return None

            server_name = selected["server"]
            tool_name = selected["tool"]
            tool_args = selected["args"]
            
            # Force overwrite workspaceId to prevent prompt injection
            if self.workspace_id:
                tool_args["workspaceId"] = str(self.workspace_id)

            question_type = selected.get("question_type", QuestionType.SECURITY_RELATED)

            # Validate that the selected tool actually exists
            tool_description = "Fetching data from MCP"
            tool_exists = False
            for server, tools in all_tools.items():
                if server == server_name:
                    for tool_info in tools:
                        if tool_info.get("name") == tool_name:
                            tool_exists = True
                            tool_description = tool_info.get("description", tool_description)
                            break
                if tool_exists:
                    break

            if not tool_exists:
                logger.warning(f"Selected tool {server_name}/{tool_name} not found in available tools")
                # Try to fuzzy match or find tool in other servers? 
                # For now, just log and return None to trigger fallback
                return None

            logger.debug(f"LLM classified as '{question_type}' and selected: {server_name}.{tool_name}")
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
            logger.error("MCP fetch error: {}", e)
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
                logger.error("Missing required fields in JSON: {}", result)
                return None

            try:
                question_type_str = result["question_type"]
                result["question_type"] = QuestionType.from_string(question_type_str)
            except ValueError as e:
                logger.error("Invalid question_type '{}': {}", result.get('question_type'), e)
                result["question_type"] = QuestionType.SECURITY_RELATED
                logger.warning(f"Defaulting to {QuestionType.SECURITY_RELATED.value}")

            return result

        except Exception as e:
            logger.exception("LLM combined classification and tool selection failed: {}", e)
            # Re-raise to be caught by the caller who can handle friendly error messages
            raise e

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

    def _select_prompt(self, question: str, scan_data: Optional[Dict], question_type: QuestionType, chat_history: List[Dict] = None) -> str:
        """Select appropriate prompt based on question type and data"""
        if not scan_data:
            return AnalysisAgentPrompts.get_no_data_response_prompt(question, chat_history)

        stats = scan_data.get("stats", {})
        tool = scan_data.get("tool", "unknown")

        if question_type == QuestionType.GENERAL_KNOWLEDGE:
            return AnalysisAgentPrompts.get_general_knowledge_prompt(question, stats, chat_history)

        tool_lower = tool.lower()
        stats_str_lower = str(stats).lower()

        if "statistics" in tool_lower or "score" in stats_str_lower:
            return AnalysisAgentPrompts.get_statistics_analysis_prompt(question, stats, chat_history)
        elif "vulnerab" in tool_lower or "severity" in stats_str_lower:
            return AnalysisAgentPrompts.get_vulnerabilities_analysis_prompt(question, stats, chat_history)
        elif "asset" in tool_lower or "target" in tool_lower:
            return AnalysisAgentPrompts.get_assets_analysis_prompt(question, stats, chat_history)
        else:
            return AnalysisAgentPrompts.get_generic_analysis_prompt(question, stats, chat_history)

    async def _generate_analysis(
        self,
        question: str,
        scan_data: Optional[Dict],
        question_type: QuestionType,
        chat_history: List[Dict] = None
    ) -> str:
        """Generate analysis response (sync)"""
        prompt = self._select_prompt(question, scan_data, question_type, chat_history)

        try:
            return self.llm.invoke(prompt).content.strip()
        except Exception as e:
            logger.exception("Failed to generate analysis: {}", e)
            if scan_data:
                stats = scan_data.get("stats", {})
                return f"Analysis data retrieved:\n\n{json.dumps(stats, indent=2)[:500]}"
            return f"Error during analysis: {LLMManager.get_friendly_error_message(e)}"


    async def _generate_analysis_streaming(
        self,
        question: str,
        scan_data: Optional[Dict],
        question_type: QuestionType = None,
        chat_history: List[Dict] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream LLM analysis with buffering"""
        min_chunk_size = configs.llm.min_chunk_size
        prompt = self._select_prompt(question, scan_data, question_type, chat_history)

        try:
            async for buffered_text in self._buffer_llm_chunks(self.llm.astream(prompt), min_chunk_size):
                yield {"type": "delta", "text": buffered_text, "agent": self.name}
        except Exception as e:
            logger.exception("Failed to stream analysis: {}", e)
            error_message = LLMManager.get_friendly_error_message(e)
            
            if scan_data:
                stats = scan_data.get("stats", {})
                yield {"type": "delta", "text": f"\n\n**Error during analysis:** {error_message}\n\nAnalysis data:\n{json.dumps(stats, indent=2)[:500]}", "agent": self.name}
            else:
                yield {"type": "delta", "text": f"\n\n**Error:** {error_message}", "agent": self.name}
            
            # Also yield an error event
            yield {
                "type": "error",
                "error": error_message,
                "agent": self.name
            }