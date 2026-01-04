from typing import Dict, Any, Optional, AsyncGenerator, List, Union
from uuid import UUID
from sqlalchemy.orm import Session
import re
import json
import asyncio
from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import JsonOutputParser

from agents.core.base_agent import BaseAgent, AgentRole, AgentType
from common.logger import logger
from common.config import configs
from llms import LLMManager
from llms.prompts import AnalysisAgentPrompts
from tools.mcp_client import MCPManager
from data.database import postgres_db

class CoTAgent(BaseAgent):
    """
    Base class for agents using Chain of Thought (CoT) reasoning with MCP tools.
    Provides standard reasoning loops, tool execution, and streaming event handling.
    """

    def __init__(
        self,
        name: str,
        role: AgentRole,
        db_session: Session,
        workspace_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        agent_type: AgentType = AgentType.GOAL_BASED,
        **kwargs
    ):
        super().__init__(
            name=name,
            role=role,
            agent_type=agent_type,
            **kwargs
        )

        self.session = db_session
        self.workspace_id = workspace_id
        self.user_id = user_id
        
        self.llm = LLMManager.get_llm(
            workspace_id=workspace_id,
            user_id=user_id
        )

        if workspace_id and user_id:
            self.mcp_manager = MCPManager(postgres_db, workspace_id, user_id)
            logger.debug(f"✓ MCP enabled for {self.name} in workspace {workspace_id}")
        else:
            self.mcp_manager = None
            logger.warning(f"MCP disabled for {self.name} - no workspace/user provided")

    async def _execute_cot_loop(
        self,
        question: str,
        chat_history: List[Dict] = None,
        max_steps: int = 5,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generic Chain of Thought (CoT) reasoning loop with MCP tools.
        
        Args:
            question: The user's question or task
            chat_history: Previous conversation context
            max_steps: Maximum reasoning steps to prevent infinite loops
            **kwargs: Additional parameters for prompt generation
            
        Yields:
            Standardized streaming events (thinking, tool_start, tool_output, delta, etc.)
        """
        if not self.mcp_manager:
            # Silently fallback to direct analysis

            # Fallback to direct analysis if MCP is not available
            async for event in self._generate_fallback_response(question, chat_history):
                yield event
            return

        try:
            await self.mcp_manager.initialize()
            all_tools = await self.mcp_manager.get_all_tools()
            tools_desc = self._format_tools_description(all_tools)
            
            steps = []
            final_answer = None
            initial_tasks = []
            parser = JsonOutputParser()
            
            for i in range(max_steps):
                # Get the reasoning prompt from the subclass
                prompt = self.get_reasoning_prompt(
                    question=question,
                    tools_description=tools_desc,
                    history=chat_history or [],
                    steps=steps,
                    initial_tasks=initial_tasks,
                    **kwargs
                )
                
                try:
                    # Robust parsing: call LLM first, clean comments, then parse
                    raw_response = await self.llm.ainvoke(prompt)
                    raw_content = raw_response.content if hasattr(raw_response, 'content') else str(raw_response)
                    
                    # Clean potential JS-style comments from LLM
                    clean_content = self._clean_json_comments(raw_content)
                    
                    try:
                        result = parser.parse(clean_content)
                    except Exception as parse_err:
                        logger.warning(f"[{self.name}] Parser failed, trying fuzzy search: {parse_err}")
                        # Fallback to standard parser which can sometimes handle messy strings
                        result = await parser.ainvoke(clean_content)

                except Exception as e:
                    logger.error(f"[{self.name}] CoT step {i} failed: {e}")
                    yield {"type": "error", "error": f"Reasoning failed: {str(e)}", "agent": self.name}
                    break

                # Parse LLM response
                thought = result.get("thought", "Thinking...")
                tasks = result.get("tasks", [])
                action = result.get("action")
                
                if i == 0 and tasks and isinstance(tasks, list):
                    initial_tasks = tasks
                

                if action == "final_answer":
                    final_answer = result.get("answer")
                    if final_answer:
                        # Stream the final answer instead of yielding it once
                        # We can either stream it as chunks or use a simulated stream if it's already generated
                        # Since LLM already generated it, we emit it but let's make it look like streaming for consistency
                        # Actually, better if we just yield it as a delta but in chunks
                        chunk_size = 20
                        for j in range(0, len(final_answer), chunk_size):
                            yield {"type": "delta", "text": final_answer[j:j+chunk_size], "agent": self.name}
                            await asyncio.sleep(0.01) # Small delay for visual effect
                    break
                
                if action == "call_tool":
                    tool_call = result.get("tool_call", {})
                    server = tool_call.get("server")
                    tool_name = tool_call.get("name")
                    args = tool_call.get("args", {})
                    
                    if not server or not tool_name:
                        continue

                    # Security: Enforce workspaceId
                    if self.workspace_id:
                        args["workspaceId"] = str(self.workspace_id)

                    # --- LOOP & DUPLICATE PREVENTION ---
                    if self._is_duplicate_call(steps, tool_name, args):
                        # log internally but don't bother user with thinking event
                        logger.debug(f"Duplicate tool call prevented: {tool_name}")
                        continue

                    # Validate tool exists
                    if not self._tool_exists(all_tools, server, tool_name):
                        error_msg = f"Tool '{tool_name}' not found on server '{server}'."
                        yield {"type": "delta", "text": f"\n\n> ❌ **Tool Error:** `{server}.{tool_name}` not found.\n", "agent": self.name}

                        steps.append({
                            "thought": thought,
                            "tool_call": tool_call,
                            "observation": {"content": error_msg, "isError": True}
                        })
                        continue

                    # Execute tool
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
                        
                        # Yield tool interaction as delta to be part of message
                        status_icon = "✅" if status == "success" else "❌"
                        # Include thought as description and add extra newline for separation
                        tool_md = f"\n\n> {status_icon} **Tool:** `{server}.{tool_name}`: *{thought}*\n\n"
                        if status != "success":
                            tool_md += f"> ⚠️ *Error: {observation.get('content', 'Unknown error')}*\n\n"
                        yield {"type": "delta", "text": tool_md, "agent": self.name}

                        
                        steps.append({
                            "thought": thought,
                            "tool_call": tool_call,
                            "observation": observation
                        })
                    except Exception as tool_err:
                        logger.error(f"[{self.name}] Tool execution failed: {tool_err}")
                        yield {"type": "delta", "text": f"\n\n> ❌ **Tool execution failed:** {str(tool_err)}\n", "agent": self.name}

                        steps.append({
                            "thought": thought,
                            "tool_call": tool_call,
                            "observation": {"error": str(tool_err), "isError": True}
                        })
                else:
                    logger.warning(f"[{self.name}] Unrecognized action from LLM: {action}")
                    if i == max_steps - 1:
                        yield {"type": "delta", "text": f"\n\n*I am having difficulty reasoning about this question.*", "agent": self.name}

            # If no final answer, generate summary from steps
            if not final_answer:
                if steps:
                    formatted_steps = self._format_steps_for_summary(steps)
                    summary_prompt = self.get_summary_prompt(question, formatted_steps, **kwargs)
                    
                    # Yield a thinking event for the summary phase
                    yield {"type": "thinking", "thought": "Synthesizing findings...", "agent": self.name}
                    
                    async for chunk in self._buffer_llm_chunks(self.llm.astream(summary_prompt), 50):
                        yield {"type": "delta", "text": chunk, "agent": self.name}
                else:
                    # No answer and no tools called - likely a reasoning failure or irrelevant question
                    msg = "I couldn't find specific information to answer your question through the available security tools."
                    yield {"type": "delta", "text": msg, "agent": self.name}

        except Exception as e:
            logger.exception(f"[{self.name}] CoT reasoning failed: {e}")
            yield {"type": "error", "error": f"Reasoning failure: {str(e)}", "agent": self.name}

    def get_reasoning_prompt(self, **kwargs) -> str:
        """Subclasses must implement to return the CoT reasoning prompt"""
        raise NotImplementedError

    def get_summary_prompt(self, question: str, steps: List[Dict], **kwargs) -> str:
        """Subclasses must implement to return the summary prompt"""
        raise NotImplementedError

    async def _generate_fallback_response(self, question: str, chat_history: List[Dict]) -> AsyncGenerator[Dict[str, Any], None]:
        """Override in subclass to handle cases without MCP"""
        yield {"type": "delta", "text": "I can only answer general knowledge questions when my security tools are unavailable.", "agent": self.name}

    def _format_tools_description(self, all_tools: Dict) -> str:
        """Utility to format tools for the prompt"""
        # This can be standardized or overridden
        return AnalysisAgentPrompts.format_tools_for_llm(all_tools)

    def _is_duplicate_call(self, steps: List[Dict], tool_name: str, args: Dict) -> bool:
        normalized_args = json.dumps(args, sort_keys=True).strip().lower()
        for step in steps:
            s_call = step.get('tool_call', {})
            s_args = json.dumps(s_call.get('args', {}), sort_keys=True).strip().lower()
            if s_call.get('name') == tool_name and s_args == normalized_args:
                return True
        return False

    def _tool_exists(self, all_tools: Dict, server: str, tool_name: str) -> bool:
        available_server_tools = all_tools.get(server, [])
        return any(t["name"] == tool_name for t in available_server_tools)

    def _format_steps_for_summary(self, steps: List[Dict], max_len: int = 2000) -> List[Dict]:
        formatted = []
        for s in steps:
            obs = s.get('observation', {})
            if isinstance(obs, dict) and 'content' in obs and isinstance(obs['content'], str):
                truncated_obs = obs.copy()
                if len(truncated_obs['content']) > max_len:
                    truncated_obs['content'] = truncated_obs['content'][:max_len] + "... [truncated]"
                formatted.append({**s, 'observation': truncated_obs})
            else:
                obs_str = str(obs)
                if len(obs_str) > max_len:
                    obs_str = obs_str[:max_len] + "... [truncated]"
                formatted.append({**s, 'observation': obs_str})
        return formatted

    def _clean_json_comments(self, text: str) -> str:
        """Remove JS-style comments (// and /* */) from a string that should be JSON"""
        # 1. Remove /* ... */ comments (multi-line)
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
        
        # 2. Remove // ... comments (line comments)
        # Robust check: only remove // if not part of a URL (heuristic: not preceded by : and not inside quotes)
        # We'll use a multi-pass approach or a more specific regex
        
        lines = text.split('\n')
        clean_lines = []
        for line in lines:
            # Match // ONLY if it's NOT preceded by a colon (potential URL)
            # and NOT inside a string (simplistic check: even number of quotes before it)
            
            comment_start = -1
            in_quote = False
            for idx in range(len(line)):
                if line[idx] == '"' and (idx == 0 or line[idx-1] != '\\'):
                    in_quote = not in_quote
                if not in_quote and line[idx:idx+2] == '//':
                    # Check if preceded by :
                    if idx > 0 and line[idx-1] == ':':
                        continue
                    comment_start = idx
                    break
            
            if comment_start != -1:
                line = line[:comment_start]
            clean_lines.append(line)
        
        text = '\n'.join(clean_lines)
        return text.strip()

