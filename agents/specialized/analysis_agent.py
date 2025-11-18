from typing import Dict, Any, Optional, AsyncGenerator
from uuid import UUID
from sqlalchemy.orm import Session
import asyncio
import json
import re

from langchain_core.messages import BaseMessage
from agents.core import BaseAgent, AgentRole, AgentType
from common.logger import logger
from common.config import configs
from llms import llm_manager
from llms.prompts import AnalysisAgentPrompts
from tools.mcp_client import MCPManager
from data.database import postgres_db


class AnalysisAgent(BaseAgent):
    """Dynamic Security Analysis Agent with MCP Integration and Streaming Support"""

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
        """Synchronous task execution"""
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
        """
        Execute task with streaming support

        Yields streaming events like ChatGPT/Claude
        """
        try:
            action = task.get("action", "analyze_vulnerabilities")
            question = task.get("question", "Provide security summary")

            # Yield thinking event
            yield {
                "type": "thinking",
                "thought": "Analyzing security data and preparing response",
                "agent": self.name
            }

            if action == "analyze_vulnerabilities":
                async for event in self.analyze_vulnerabilities_streaming(question):
                    yield event
            else:
                yield {
                    "type": "error",
                    "error": f"Unknown action: {action}",
                    "agent": self.name
                }

        except Exception as e:
            logger.error(f"Streaming task execution failed: {e}", exc_info=True)
            yield {
                "type": "error",
                "error": str(e),
                "agent": self.name
            }

    async def analyze_vulnerabilities(self, question: str) -> Dict[str, Any]:
        """Synchronous vulnerability analysis"""
        logger.info(f"Analyzing: {question[:100]}...")

        scan_data = await self._fetch_mcp_data(question)
        response = await self._generate_analysis(question, scan_data)

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

    async def analyze_vulnerabilities_streaming(self, question: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streaming vulnerability analysis - like ChatGPT/Claude

        Yields:
            Streaming events with LLM text chunks as they are generated
        """
        logger.info(f"Streaming analysis: {question[:100]}...")

        # Yield tool start - fetching MCP data
        yield {
            "type": "tool_start",
            "tool_name": "mcp_data_fetch",
            "tool_description": "Fetching security scan data from MCP",
            "agent": self.name
        }

        # Fetch MCP data
        scan_data = await self._fetch_mcp_data(question)

        # Yield tool output
        yield {
            "type": "tool_output",
            "tool_name": "mcp_data_fetch",
            "status": "success" if scan_data else "no_data",
            "output": {
                "has_data": bool(scan_data),
                "source": scan_data.get("source") if scan_data else None
            },
            "agent": self.name
        }

        # Yield tool_end
        yield {
            "type": "tool_end",
            "tool_name": "mcp_data_fetch",
            "agent": self.name
        }

        # Stream LLM analysis
        async for event in self._generate_analysis_streaming(question, scan_data):
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
        """Fetch data from MCP tools"""
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

            selected = await self._select_tool_with_llm(question, all_tools)
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

    async def _select_tool_with_llm(self, question: str, all_tools: Dict) -> Optional[Dict]:
        """Select appropriate MCP tool using LLM"""
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

            # Extract JSON from markdown code blocks
            original_content = content

            if "```json" in content:
                parts = content.split("```json")
                if len(parts) > 1:
                    content = parts[1].split("```")[0].strip()
            elif "```" in content:
                parts = content.split("```")
                if len(parts) >= 3:
                    content = parts[1].strip()

            # Find JSON object
            if not content.startswith("{"):
                start_idx = content.find("{")
                end_idx = content.rfind("}")
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    content = content[start_idx:end_idx + 1]

            if not content or not content.strip():
                logger.error("No JSON content found after extraction")
                return None

            # Clean up content
            content = content.encode('utf-8', 'ignore').decode('utf-8')
            content = content.replace('\u201c', '"').replace('\u201d', '"')
            content = content.replace('\u2018', "'").replace('\u2019', "'")
            content = re.sub(r',(\s*[}\]])', r'\1', content)

            # Check if JSON is properly closed
            open_braces = content.count('{')
            close_braces = content.count('}')
            if open_braces > close_braces:
                content = content.rstrip() + ('}' * (open_braces - close_braces))

            result = json.loads(content)

            # Validate required fields
            if not all(key in result for key in ["server", "tool", "args"]):
                logger.error(f"Missing required fields in JSON: {result}")
                return None

            return result

        except json.JSONDecodeError as e:
            logger.error(f"LLM response is not valid JSON: {e}")
            # Try regex fallback
            try:
                server_match = re.search(r'"server"\s*:\s*"([^"]+)"', original_content)
                tool_match = re.search(r'"tool"\s*:\s*"([^"]+)"', original_content)
                args_match = re.search(r'"args"\s*:\s*(\{(?:[^{}]|\{[^{}]*\})*\})', original_content)

                if server_match and tool_match and args_match:
                    logger.info("Using regex fallback extraction")
                    args_str = args_match.group(1)
                    args_str = args_str.encode('utf-8', 'ignore').decode('utf-8')
                    args_str = args_str.replace('\u201c', '"').replace('\u201d', '"')
                    args_str = re.sub(r',(\s*[}\]])', r'\1', args_str)

                    return {
                        "server": server_match.group(1),
                        "tool": tool_match.group(1),
                        "args": json.loads(args_str)
                    }
            except Exception:
                pass

            return None
        except Exception as e:
            logger.error(f"LLM tool selection failed: {e}", exc_info=True)
            return None

    def _has_data(self, result: Dict, tool_name: str) -> bool:
        """Check if MCP result has meaningful data"""
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

    async def _generate_analysis(self, question: str, scan_data: Optional[Dict]) -> str:
        """Generate analysis response (synchronous)"""
        # No data case
        if not scan_data:
            prompt = AnalysisAgentPrompts.get_no_data_response_prompt(question)
            try:
                return self.llm.invoke(prompt).content.strip()
            except Exception as e:
                logger.error(f"Failed to generate no-data response: {e}")
                return "This workspace currently has no security scan data. Please run a security scan first."

        # Has data - generate LLM-based analysis
        stats = scan_data.get("stats", {})
        tool = scan_data.get("tool", "unknown")

        try:
            # Select appropriate prompt based on data type
            if "statistics" in tool or "score" in str(stats):
                prompt = AnalysisAgentPrompts.get_statistics_analysis_prompt(question, stats)
            elif "vulnerabilities" in tool or "severity" in str(stats):
                prompt = AnalysisAgentPrompts.get_vulnerabilities_analysis_prompt(question, stats)
            elif "assets" in tool or "targets" in tool:
                prompt = AnalysisAgentPrompts.get_assets_analysis_prompt(question, stats)
            else:
                prompt = AnalysisAgentPrompts.get_generic_analysis_prompt(question, stats)

            response = self.llm.invoke(prompt).content.strip()
            return response

        except Exception as e:
            logger.error(f"Failed to generate analysis: {e}", exc_info=True)
            return f"Analysis data retrieved:\n\n{json.dumps(stats, indent=2)[:500]}"

    async def _buffer_llm_chunks(
        self,
        llm_stream: AsyncGenerator,
        min_chunk_size: int
    ) -> AsyncGenerator[str, None]:
        """
        Buffer LLM chunks to reduce number of responses sent

        Args:
            llm_stream: Async generator from LLM
            min_chunk_size: Minimum characters before yielding

        Yields:
            Buffered text chunks
        """
        buffer = ""

        async for chunk in llm_stream:
            # Extract text from chunk
            if isinstance(chunk, BaseMessage) and chunk.content:
                text = chunk.content
            elif isinstance(chunk, str):
                text = chunk
            else:
                continue

            buffer += text

            # Yield when buffer reaches min size
            if len(buffer) >= min_chunk_size:
                yield buffer
                buffer = ""

        # Yield remaining buffer
        if buffer:
            yield buffer

    async def _generate_analysis_streaming(
        self,
        question: str,
        scan_data: Optional[Dict]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate analysis response with LLM streaming (like ChatGPT/Claude)

        Yields delta events as LLM generates text (buffered to reduce responses)
        """
        # Get min chunk size from config
        min_chunk_size = configs.llm.min_chunk_size

        # No data case
        if not scan_data:
            prompt = AnalysisAgentPrompts.get_no_data_response_prompt(question)
            try:
                # Buffer chunks before yielding
                async for buffered_text in self._buffer_llm_chunks(self.llm.astream(prompt), min_chunk_size):
                    yield {
                        "type": "delta",
                        "text": buffered_text,
                        "agent": self.name
                    }
            except Exception as e:
                logger.error(f"Failed to stream no-data response: {e}")
                yield {
                    "type": "delta",
                    "text": "This workspace currently has no security scan data. Please run a security scan first.",
                    "agent": self.name
                }
            return

        # Has data - stream LLM-based analysis
        stats = scan_data.get("stats", {})
        tool = scan_data.get("tool", "unknown")

        try:
            # Select appropriate prompt based on data type
            if "statistics" in tool or "score" in str(stats):
                prompt = AnalysisAgentPrompts.get_statistics_analysis_prompt(question, stats)
            elif "vulnerabilities" in tool or "severity" in str(stats):
                prompt = AnalysisAgentPrompts.get_vulnerabilities_analysis_prompt(question, stats)
            elif "assets" in tool or "targets" in tool:
                prompt = AnalysisAgentPrompts.get_assets_analysis_prompt(question, stats)
            else:
                prompt = AnalysisAgentPrompts.get_generic_analysis_prompt(question, stats)

            # Stream LLM response with buffering
            async for buffered_text in self._buffer_llm_chunks(self.llm.astream(prompt), min_chunk_size):
                yield {
                    "type": "delta",
                    "text": buffered_text,
                    "agent": self.name
                }

        except Exception as e:
            logger.error(f"Failed to stream analysis: {e}", exc_info=True)
            yield {
                "type": "delta",
                "text": f"\n\nAnalysis data:\n{json.dumps(stats, indent=2)[:500]}",
                "agent": self.name
            }
