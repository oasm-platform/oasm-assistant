
"""Nuclei Template Generation Agent"""

from typing import Dict, Any, Optional, AsyncGenerator, List
from uuid import UUID
from sqlalchemy.orm import Session
import asyncio
import traceback

from agents.core import BaseAgent, AgentRole, AgentType, AgentCapability
from common.logger import logger
from common.config import configs
from llms import llm_manager
from llms.prompts.nuclei_generator_agent_prompts import NucleiGenerationPrompts
from langchain_core.messages import BaseMessage

class NucleiGeneratorAgent(BaseAgent):
    """Generates Nuclei templates using LLM"""

    def __init__(
        self,
        db_session: Optional[Session] = None,
        workspace_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        **kwargs
    ):
        super().__init__(
            name="NucleiGeneratorAgent",
            role=AgentRole.NUCLEI_GENERATOR_AGENT,
            agent_type=AgentType.GOAL_BASED,
            capabilities=[
                AgentCapability(
                    name="nuclei_template_generation",
                    description="Generates high-quality, production-ready Nuclei templates from natural language descriptions for automated vulnerability scanning and security assessment."
                )
            ],
            **kwargs
        )
        self.session = db_session
        self.workspace_id = workspace_id
        self.user_id = user_id
        self.llm = llm_manager.get_llm()

    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task synchronously"""
        try:
            question = task.get("question", "")
            return asyncio.run(self.generate_template(question))
        except Exception as e:
            logger.error(f"Nuclei generation failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def execute_task_streaming(self, task: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute task with streaming events"""
        try:
            question = task.get("question", "")

            yield {
                "type": "thinking",
                "thought": "Generating Nuclei template based on description...",
                "agent": self.name
            }

            async for event in self.generate_template_streaming(question):
                yield event

        except Exception as e:
            error_details = traceback.format_exc()
            logger.error("Streaming template generation failed: %s", str(e), exc_info=True)
            yield {
                "type": "error",
                "error": str(e),
                "error_type": "TemplateGenerationError",
                "agent": self.name
            }

    async def generate_template(self, question: str) -> Dict[str, Any]:
        """Generate template synchronously"""
        prompt = NucleiGenerationPrompts.get_nuclei_template_generation_prompt(question)
        response = await self.llm.ainvoke(prompt)
        content = response.content.strip()
        
        return {
            "success": True,
            "response": content
        }

    async def generate_template_streaming(self, question: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream template generation"""
        prompt = NucleiGenerationPrompts.get_nuclei_template_generation_prompt(question)
        
        # Buffer similar to AnalysisAgent to avoid too many small chunks
        buffer = ""
        min_chunk_size = configs.llm.min_chunk_size

        try:
            async for chunk in self.llm.astream(prompt):
                if isinstance(chunk, BaseMessage) and chunk.content:
                    text = chunk.content
                elif isinstance(chunk, str):
                    text = chunk
                else:
                    continue
                
                buffer += text
                if len(buffer) >= min_chunk_size:
                    yield {"type": "delta", "text": buffer, "agent": self.name}
                    buffer = ""
            
            if buffer:
                yield {"type": "delta", "text": buffer, "agent": self.name}
                
        except Exception as e:
             logger.error(f"Failed to stream template generation: {e}", exc_info=True)
             yield {"type": "error", "error": str(e), "agent": self.name}

