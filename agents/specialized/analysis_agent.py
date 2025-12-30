"""Security analysis agent with MCP integration and streaming support"""

from typing import Dict, Any, Optional, AsyncGenerator, List
from uuid import UUID
from sqlalchemy.orm import Session
import asyncio
import json
import traceback

from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import JsonOutputParser
from agents.core import BaseAgent, AgentRole, AgentType
from common.logger import logger
from common.config import configs
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
        self.llm = LLMManager.get_llm(workspace_id=workspace_id, user_id=user_id, **llm_config)

        if workspace_id and user_id:
            self.mcp_manager = MCPManager(postgres_db, workspace_id, user_id)
            logger.debug(f"✓ MCP enabled for workspace {workspace_id}")
        else:
            self.mcp_manager = None
            logger.warning("MCP disabled - no workspace/user provided")

    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task synchronously"""
        try:
            action = task.get("action", "analyze_vulnerabilities")
            question = task.get("question", "Provide security summary")
            chat_history = task.get("chat_history")

            if action == "analyze_vulnerabilities":
                return asyncio.run(self.analyze_vulnerabilities(question, chat_history))

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

            yield {
                "type": "thinking",
                "thought": "Analyzing security data and preparing response",
                "agent": self.name
            }

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
        """Analyze with streaming - single LLM call for classification and tool selection"""
        logger.info(f"Streaming analysis: {question[:100]}...")

        # Use CoT reasoning for complex multi-tool tasks
        async for event in self._execute_cot_reasoning(question, chat_history):
            yield event

        # Yield final result
        yield {
            "type": "result",
            "data": {
                "success": True,
                "agent": self.name
            }
        }

    async def _execute_cot_reasoning(
        self,
        question: str,
        chat_history: List[Dict] = None,
        max_steps: int = 5
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute Chain of Thought (CoT) reasoning loop with MCP tools"""
        if not self.mcp_manager:
            yield {"type": "thinking", "thought": "MCP is disabled. I will answer based on general knowledge.", "agent": self.name}
            async for event in self._generate_analysis_streaming(question, None, QuestionType.GENERAL_KNOWLEDGE, chat_history):
                yield event
            return

        try:
            await self.mcp_manager.initialize()
            all_tools = await self.mcp_manager.get_all_tools()
            tools_desc = AnalysisAgentPrompts.format_tools_for_llm(all_tools)
            logger.info(f"Available MCP Tools for AI:\n{tools_desc}")
            
            steps = []
            final_answer = None
            initial_tasks = []  # Track the original task list
            parser = JsonOutputParser()
            
            for i in range(max_steps):
                prompt = AnalysisAgentPrompts.get_cot_reasoning_prompt(
                    question=question,
                    tools_description=tools_desc,
                    history=chat_history or [],
                    steps=steps,
                    initial_tasks=initial_tasks
                )
                
                try:
                    chain = self.llm | parser
                    result = await chain.ainvoke(prompt)
                except Exception as e:
                    logger.error(f"CoT step {i} failed: {e}")
                    yield {"type": "error", "error": f"Reasoning failed at step {i+1}: {str(e)}", "agent": self.name}
                    break

                # Process the step
                thought = result.get("thought", "Thinking...")
                plan = result.get("plan")
                tasks = result.get("tasks", [])
                
                # Store initial tasks on first step
                if i == 0 and tasks and isinstance(tasks, list):
                    initial_tasks = tasks
                
                # Show thought in UI only (not in message content)
                yield {"type": "thinking", "thought": thought, "agent": self.name}
                
                # Dynamic checklist: Show ONCE at the beginning if multiple tasks
                if i == 0 and tasks and isinstance(tasks, list) and len(tasks) > 1:
                    # Initial checklist display
                    checklist_md = "\n### Kế hoạch\n"
                    yield {"type": "delta", "text": checklist_md, "agent": self.name}
                
                action = result.get("action")
                
                if action == "final_answer":
                    final_answer = result.get("answer")
                    yield {"type": "delta", "text": f"\n### Kết quả\n{final_answer}\n", "agent": self.name}
                    break
                
                if action == "call_tool":
                    tool_call = result.get("tool_call", {})
                    server = tool_call.get("server")
                    tool_name = tool_call.get("name")
                    args = tool_call.get("args", {})
                    
                    if not server or not tool_name:
                        yield {"type": "thinking", "thought": "Invalid tool call. Continuing...", "agent": self.name}
                        continue

                    # Overwrite workspaceId for security
                    if self.workspace_id:
                        args["workspaceId"] = str(self.workspace_id)

                    # --- TASK COMPLETION CHECK ---
                    # If we have a task list, check if we're calling the right tool
                    if initial_tasks:
                        completed_tools = [s.get('tool_call', {}).get('name') for s in steps]
                        pending_tasks = [t for t in initial_tasks if t not in completed_tools]
                        
                        # If there are pending tasks and we're trying to call a tool we already called
                        if pending_tasks and tool_name in completed_tools:
                            yield {"type": "thinking", "thought": f"I already called {tool_name}. I should call {pending_tasks[0]} next.", "agent": self.name}
                            continue
                    
                    # --- LOOP PREVENTION ---
                    # Check if this EXACT tool + args has been called already (allow once, prevent loops)
                    # Use a normalized version of args to catch slight variations like spaces
                    normalized_args = json.dumps(args, sort_keys=True).strip().lower()
                    call_id = f"{server}:{tool_name}:{normalized_args}"
                    duplicate_count = sum(1 for s in steps if f"{s['tool_call'].get('server')}:{s['tool_call'].get('name')}:{json.dumps(s['tool_call'].get('args'), sort_keys=True).strip().lower()}" == call_id)
                    
                    if duplicate_count >= 1:  # Changed from 2 to 1 - don't allow ANY duplicates
                        yield {"type": "thinking", "thought": f"I already called {tool_name}. Moving to next task or final answer.", "agent": self.name}
                        # Don't break, just continue to let AI decide next step
                        continue

                    # Validate tool exists to prevent hallucination
                    available_server_tools = all_tools.get(server, [])
                    if not any(t["name"] == tool_name for t in available_server_tools):
                        error_msg = f"Tool '{tool_name}' not found on server '{server}'."
                        yield {"type": "thinking", "thought": f"I tried to call a tool that doesn't exist: {tool_name}. I must stick to the available tools list.", "agent": self.name}
                        yield {"type": "delta", "text": f"\n> Lỗi: Công cụ `{tool_name}` không tồn tại trên server `{server}`.\n", "agent": self.name}
                        steps.append({
                            "thought": thought,
                            "tool_call": tool_call,
                            "observation": {"content": error_msg, "isError": True}
                        })
                        continue

                    yield {
                        "type": "tool_start",
                        "tool_name": tool_name,
                        "tool_description": f"Executing {server}.{tool_name}",
                        "parameters": args,
                        "agent": self.name
                    }
                    
                    try:
                        observation = await self.mcp_manager.call_tool(server=server, tool=tool_name, args=args)
                        status = "success" if not observation.get("isError") else "error"
                        
                        yield {
                            "type": "tool_output",
                            "tool_name": tool_name,
                            "status": status,
                            "output": observation,
                            "agent": self.name
                        }
                        
                        # Add tool execution to message content
                        status_icon = "✅" if status == "success" else "❌"
                        tool_md = f"\n> {status_icon} **Công cụ:** `{server}.{tool_name}`: {thought}\n"
                        
                        if status != "success":
                            # MCPManager puts error message in 'content' field
                            error_detail = observation.get('content', 'Unknown error')
                            tool_md += f"> ⚠️ *Lỗi: {error_detail}*\n"
                            
                        yield {"type": "delta", "text": tool_md, "agent": self.name}
                        
                        steps.append({
                            "thought": thought,
                            "tool_call": tool_call,
                            "observation": observation
                        })
                    except Exception as tool_err:
                        logger.error(f"Tool execution failed: {tool_err}")
                        yield {
                            "type": "tool_output",
                            "tool_name": tool_name,
                            "status": "error",
                            "error": str(tool_err),
                            "agent": self.name
                        }
                        yield {"type": "delta", "text": f"\n> Lỗi gọi Tool: {str(tool_err)}\n", "agent": self.name}
                        
                        steps.append({
                            "thought": thought,
                            "tool_call": tool_call,
                            "observation": {"error": str(tool_err), "isError": True}
                        })
                else:
                    yield {"type": "thinking", "thought": "I need to rethink my approach.", "agent": self.name}

            if not final_answer and steps:
                yield {"type": "thinking", "thought": "Summarizing results...", "agent": self.name}
                yield {"type": "delta", "text": "\n### Tóm tắt kết quả\n", "agent": self.name}

                # Format steps with truncated observations to prevent context window overflow
                formatted_steps = []
                for s in steps:
                    obs = s.get('observation', {})
                    if isinstance(obs, dict) and 'content' in obs and isinstance(obs['content'], str):
                        truncated_obs = obs.copy()
                        if len(truncated_obs['content']) > 2000:
                            truncated_obs['content'] = truncated_obs['content'][:2000] + "... [truncated]"
                        formatted_steps.append({**s, 'observation': truncated_obs})
                    else:
                        obs_str = str(obs)
                        if len(obs_str) > 2000:
                            obs_str = obs_str[:2000] + "... [truncated]"
                        formatted_steps.append({**s, 'observation': obs_str})

                summary_prompt = AnalysisAgentPrompts.get_summary_prompt(question, formatted_steps)
                async for event in self._buffer_llm_chunks(self.llm.astream(summary_prompt), 50):
                    yield {"type": "delta", "text": event, "agent": self.name}

        except Exception as e:
            logger.exception("CoT reasoning failed: {}", e)
            yield {"type": "error", "error": f"CoT failure: {str(e)}", "agent": self.name}

    async def _fetch_mcp_data_streaming(self, question: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Fetch data from MCP with events streaming"""
        if not self.mcp_manager:
            logger.warning("MCP not available")
            return
        try:
            yield {"type": "thinking", "thought": "Initializing MCP tools...", "agent": self.name}
            await self.mcp_manager.initialize()

            all_tools = await self.mcp_manager.get_all_tools()
            if not all_tools:
                logger.warning("No MCP tools available")
                return

            tool_count = sum(len(tools) for tools in all_tools.values())
            yield {
                "type": "thinking", 
                "thought": f"Exploring {tool_count} tools from {len(all_tools)} servers to find the best match...", 
                "agent": self.name
            }
            logger.debug(f"Discovered {tool_count} MCP tools from {len(all_tools)} servers")

            selected = await self._classify_and_select_tool_combined(question, all_tools)
            if not selected:
                logger.warning("LLM could not classify and select tool")
                yield {"type": "thinking", "thought": "Could not determine appropriate tool.", "agent": self.name}
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