from typing import Dict, Any, Optional, AsyncGenerator, List
from uuid import UUID
from sqlalchemy.orm import Session
import asyncio
import json
import re
import traceback

from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import JsonOutputParser
from agents.core import BaseAgent, AgentRole, AgentType
from common.logger import logger
from common.types import QuestionType
from llms import LLMManager
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
        
        llm_config = kwargs.get('llm_config', {})
        self.llm = LLMManager.get_llm(
            workspace_id=workspace_id,
            user_id=user_id,
            llm_config=llm_config
        )

        if workspace_id and user_id:
            self.mcp_manager = MCPManager(postgres_db, workspace_id, user_id)
            logger.debug(f"✓ MCP enabled for {self.name} in workspace {workspace_id}")
        else:
            self.mcp_manager = None
            logger.warning(f"MCP disabled for {self.name} - no workspace/user provided")

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
        """Analyze with streaming - fetch data then generate analysis"""
        logger.info(f"Streaming analysis: {question[:100]}...")

        # Fetch MCP data with streaming events
        scan_data = None
        async for event in self._fetch_mcp_data_streaming(question):
            if event.get("type") == "result_data":
                scan_data = event.get("data")
            else:
                yield event

        # Determine question type
        question_type = self._ensure_question_type_enum(
            scan_data.get("question_type") if scan_data else None
        )

        # Generate analysis with streaming
        async for event in self._generate_analysis_streaming(question, scan_data, question_type, chat_history):
            yield event

        # Final result
        yield {
            "type": "result",
            "data": {
                "success": True,
                "agent": self.name
            }
        }


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

            for server, tools in all_tools.items():
                all_tools[server] = [t for t in tools if t['name'] != 'get_workspaces']

            tool_count = sum(len(tools) for tools in all_tools.values())
            logger.debug(f"Discovered {tool_count} MCP tools from {len(all_tools)} servers")

            selected = await self._classify_and_select_tool_combined(question, all_tools)
            if not selected:
                logger.warning("LLM could not classify and select tool")
                return


            tool_calls = selected.get("tool_calls", [])
            if not tool_calls:
                logger.warning("No tools selected by LLM")
                return

            results = []
            question_type = selected.get("question_type", QuestionType.SECURITY_RELATED)

            for call in tool_calls:
                server_name = call.get("server")
                tool_name = call.get("tool")
                tool_args = call.get("args", {})
                
                # Force overwrite workspaceId to prevent prompt injection
                if self.workspace_id:
                    tool_args["workspaceId"] = str(self.workspace_id)

                # Validate tool exists
                tool_description = "Fetching data"
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
                    logger.warning(f"Selected tool {server_name}.{tool_name} not found")
                    continue

                logger.debug(f"Executing tool call: {server_name}.{tool_name}")
                
                # Inform UI about tool start
                yield {
                    "type": "tool_start",
                    "tool": tool_name,
                    "server": server_name,
                    "reasoning": call.get("reasoning", "")
                }

                # Execute tool
                result = await self.mcp_manager.call_tool(server=server_name, tool=tool_name, args=tool_args)

                if result and not result.get("isError"):
                    results.append({
                        "tool": tool_name,
                        "server": server_name,
                        "description": tool_description,
                        "data": result
                    })
                    yield {
                        "type": "tool_output",
                        "tool_name": tool_name,
                        "status": "success",
                        "agent": self.name
                    }
                else:
                    error_msg = result.get('content') if result else 'No response'
                    yield {
                        "type": "tool_output",
                        "tool_name": tool_name,
                        "status": "error",
                        "error": error_msg,
                        "agent": self.name
                    }

            if not results:
                logger.warning("All tool calls failed or no calls made")
                return

            final_data = {
                "source": "Multiple MCP Tools" if len(results) > 1 else f"MCP ({results[0]['server']}/{results[0]['tool']})",
                "stats": results if len(results) > 1 else results[0]["data"],
                "tool": results[0]["tool"] if len(results) == 1 else "multi_tool",
                "details": results,
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

            for server, tools in all_tools.items():
                all_tools[server] = [t for t in tools if t['name'] != 'get_workspaces']

            selected = await self._classify_and_select_tool_combined(question, all_tools)
            if not selected:
                logger.warning("LLM could not classify and select tool")
                return None

            tool_calls = selected.get("tool_calls", [])
            if not tool_calls:
                logger.warning("No tools selected")
                return None

            results = []
            question_type = selected.get("question_type", QuestionType.SECURITY_RELATED)

            for call in tool_calls:
                server_name = call.get("server")
                tool_name = call.get("tool")
                tool_args = call.get("args", {})
                
                if self.workspace_id:
                    tool_args["workspaceId"] = str(self.workspace_id)

                # Validate tool
                tool_exists = False
                tool_desc = ""
                for server, tools in all_tools.items():
                    if server == server_name:
                        for t in tools:
                            if t["name"] == tool_name:
                                tool_exists = True
                                tool_desc = t.get("description", "")
                                break
                    if tool_exists: break
                
                if not tool_exists: continue

                result = await self.mcp_manager.call_tool(server=server_name, tool=tool_name, args=tool_args)
                if result and not result.get("isError"):
                    results.append({
                        "tool": tool_name,
                        "server": server_name,
                        "data": result,
                        "description": tool_desc
                    })

            if not results: return None

            return {
                "source": "Multiple MCP Tools" if len(results) > 1 else f"MCP ({results[0]['server']}/{results[0]['tool']})",
                "stats": results if len(results) > 1 else results[0]["data"],
                "question_type": question_type,
                "details": results
            }

        except Exception as e:
            logger.error("MCP fetch error: {}", e)
            return None

    def _extract_all_json_objects(self, text: str) -> List[Dict]:
        """Helper to extract all valid JSON objects from mixed text"""
        objects = []
        decoder = json.JSONDecoder()
        pos = 0
        while pos < len(text):
            # Search for the next '{'
            next_start = text.find('{', pos)
            if next_start == -1:
                break
            
            try:
                # Attempt to decode a JSON object starting at next_start
                # raw_decode returns (object, end_index)
                obj, end_pos = decoder.raw_decode(text, next_start)
                objects.append(obj)
                pos = end_pos # Advance to end of this object
            except json.JSONDecodeError:
                # Not a valid object start, move forward by 1
                pos = next_start + 1
        return objects

    async def _classify_and_select_tool_combined(self, question: str, all_tools: Dict) -> Optional[Dict]:
        """Classify question type and select MCP tool in single LLM call"""
        parser = JsonOutputParser()
        prompt = AnalysisAgentPrompts.get_combined_classification_and_tool_selection_prompt(
            question=question,
            tools_description=AnalysisAgentPrompts.format_tools_for_llm(all_tools)
        )

        try:
            response = await self.llm.ainvoke(prompt)
            raw_content = response.content if hasattr(response, 'content') else str(response)
            clean_content = raw_content.strip()

            result = None
            
            # Strategy 1: Regex for Code Block (Most reliable for chatty LLMs)
            json_block = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', clean_content, re.DOTALL)
            if json_block:
                try:
                    result = json.loads(json_block.group(1))
                except: pass
            
            # Strategy 2: Multi-object extraction
            if result is None:
                json_objects = self._extract_all_json_objects(clean_content)
                candidates = []
                for obj in json_objects:
                    if isinstance(obj, dict):
                        score = 0
                        if "question_type" in obj: score += 2
                        if "tool_calls" in obj: score += 2
                        if "tool" in obj: score += 1
                        if "reasoning" in obj: score += 1
                        if score > 0: candidates.append((score, obj))
                
                candidates.sort(key=lambda x: x[0], reverse=True)
                if candidates: 
                    result = candidates[0][1]

            # Strategy 3: Outermost braces (Fallback)
            if result is None:
                 try:
                    start_idx = clean_content.find('{')
                    end_idx = clean_content.rfind('}')
                    if start_idx != -1 and end_idx != -1:
                        s = clean_content[start_idx : end_idx + 1]
                        # Mild repair for python-dict style
                        s = s.replace("'", '"').replace("False", "false").replace("True", "true").replace("None", "null")
                        result = json.loads(s)
                 except: pass

            if result is None:
                logger.error(f"Failed to parse JSON. Raw: {clean_content[:200]}")
                return None

            # Normalization and Soft Validation
            if "question_type" not in result:
                 result["question_type"] = "security_related"
            
            if "reasoning" not in result:
                 result["reasoning"] = "Inferred from content"

            # Normalize legacy single 'tool' to 'tool_calls'
            if "tool_calls" not in result and "tool" in result:
                result["tool_calls"] = [{
                    "server": result.get("server"),
                    "tool": result.get("tool"),
                    "args": result.get("args", {}),
                    "reasoning": result.get("reasoning")
                }]

            # Convert enum safely
            try:
                if isinstance(result["question_type"], str):
                    result["question_type"] = QuestionType.from_string(result["question_type"])
            except:
                result["question_type"] = QuestionType.SECURITY_RELATED

            return result

        except Exception as e:
            logger.exception("LLM classification failed: {}", e)
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



    def _select_prompt(self, question: str, scan_data: Optional[Dict], question_type: QuestionType, chat_history: List[Dict] = None) -> str:
        """Select appropriate prompt based on question type and data"""
        if not scan_data:
            return AnalysisAgentPrompts.get_no_data_response_prompt(question, chat_history)

        stats = scan_data.get("stats", {})
        tool = scan_data.get("tool", "unknown")

        # Cleanup stats for list_tools to avoid huge prompts and technical noise
        if tool == "list_tools" and isinstance(stats, dict) and "data" in stats:
            tools = stats["data"]
            if isinstance(tools, list):
                # Only keep essential fields
                stats = [
                    {
                        "name": t.get("name"), 
                        "description": (t.get("description") or "")[:150],
                        "installed": t.get("isInstalled", False),
                        "type": t.get("type", "unknown")
                    } 
                    for t in tools
                ]

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
        """Stream LLM analysis with buffering and fallback"""
        prompt = self._select_prompt(question, scan_data, question_type, chat_history)

        try:
            async for buffered_text in self._buffer_llm_chunks(self.llm, prompt):
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