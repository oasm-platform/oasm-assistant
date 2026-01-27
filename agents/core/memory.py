import json
from typing import Dict, Any, Optional, Iterator
from contextlib import contextmanager

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    ChannelVersions
)

from common.logger import logger
from data.database.models import STM
from data.database import postgres_db
from common.config import configs
from llms import LLMManager
from llms.prompts.memory_prompts import MemoryPrompts
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
import asyncio
import uuid
from data.redis import redis_client
from sqlalchemy import select

class STMCheckpointer(BaseCheckpointSaver):
    """
    Persist LangGraph state to PostgreSQL database (Async).
    """
    def __init__(self, serde=None, workspace_id=None, user_id=None):
        super().__init__(serde=serde)
        self.db = postgres_db
        self.workspace_id = workspace_id
        self.user_id = user_id

    @staticmethod
    def get_chat_history_window(messages: list) -> list[dict]:
        """Get formatted chat history based on STM context window configuration"""
        chat_history = []
        if not messages:
            return chat_history
            
        # Use stm_context_messages (1 Unit = 2 raw messages)
        window_size = configs.memory.stm_context_messages * 2
        recent_messages = messages[-window_size:]
        
        for msg in recent_messages:
            role = "user" if msg.type == "human" else "assistant"
            chat_history.append({"role": role, "content": msg.content})
            
        return chat_history

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Get a checkpoint tuple from the database (Sync - Not Supported/Not Recommended)."""
        # Since we switched to Async database, sync access is problematic.
        # Ideally, we shouldn't be calling this in an async app.
        raise NotImplementedError("STMCheckpointer only supports async operations via aget_tuple")

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Get a checkpoint tuple from the database (Async)."""
        conversation_id = config["configurable"].get("thread_id")
        if not conversation_id:
            return None

        try:
            async with self.db.get_session() as session:
                # Retrieve the latest checkpoint for this conversation
                result = await session.execute(select(STM).filter(
                    STM.conversation_id == uuid.UUID(conversation_id)
                ))
                row = result.scalars().first()

                if not row:
                    return None

                # Load checkpoint data
                checkpoint_data = row.checkpoint
                
                # Strategy: Handle new serialization format with hex-encoded binary
                if isinstance(checkpoint_data, dict) and "__serializer_type" in checkpoint_data:
                    type_ = checkpoint_data["__serializer_type"]
                    bytes_ = bytes.fromhex(checkpoint_data["__serializer_data"])
                    checkpoint = self.serde.loads_typed((type_, bytes_))
                else:
                    # Fallback for any existing data or raw dicts (may lack custom types)
                    checkpoint = checkpoint_data
                
                metadata = row.metadata_ or {}
                parent_id = row.parent_checkpoint_id
                
                parent_config = None
                if parent_id:
                    parent_config = {
                        "configurable": {
                            "thread_id": conversation_id,
                            "checkpoint_id": parent_id,
                        }
                    }

                return CheckpointTuple(
                    config=config,
                    checkpoint=checkpoint,
                    metadata=metadata,
                    parent_config=parent_config,
                )
        except Exception as e:
            # logger.exception("Error reading checkpoint: {}", e) # avoid log spam on init
            logger.warning("Error reading checkpoint: {}", e)
            return None

    def list(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        """List checkpoints (Not implemented for STM focus)."""
        yield from []

    async def _summarize_async(self, current_summary: str, messages_to_summarize: list) -> str:
        """Generate summary asynchronously"""
        try:
            conversation_text = ""
            for msg in messages_to_summarize:
                if isinstance(msg, HumanMessage):
                    role = "Human"
                elif isinstance(msg, AIMessage):
                    role = "AI"
                elif msg.type == "tool":
                    role = "Tool Output" 
                elif msg.type == "system":
                    role = "System"
                else:
                    role = msg.type.capitalize()
                
                conversation_text += f"{role}: {msg.content}\n"
            
            prompt = MemoryPrompts.get_conversation_summary_prompt(current_summary, conversation_text)
            
            llm_config = await LLMManager.resolve_llm_config_async(workspace_id=self.workspace_id, user_id=self.user_id)
            llm = LLMManager.get_llm(llm_config=llm_config)
            
            summary = await llm.ainvoke(prompt)
            return summary.content.strip()
        except Exception as e:
            logger.exception("STM Summarization failed: {}", e)
            return current_summary

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Sync put - Not supported."""
        raise NotImplementedError("STMCheckpointer only supports async operations via aput")

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Async version of put that saves state using async DB methods."""
        conversation_id = config["configurable"].get("thread_id")
        if not conversation_id:
            return config

        try:
            # STM Optimization: Batch Cycle Pattern (Count 1 -> Limit -> Reset)
            channel_values = checkpoint.get("channel_values", {})
            messages = channel_values.get("messages", [])
            messages_len = len(messages)
            
            stack_pairs = configs.memory.stm_summary_stack_messages
            
            # Redis Logic: Increment and Check
            redis_key = f"stm:stack_count:{conversation_id}"
            
            # Increment atomic
            try:
                # Use async redis client
                new_count = await redis_client.async_client.incr(redis_key)
                await redis_client.async_client.expire(redis_key, 86400)
                
                if new_count >= stack_pairs:
                    # Force Summary based on Stack Config
                    target_cut_msg = stack_pairs * 2
                    trim_count = min(messages_len, target_cut_msg)
                    
                    messages_to_process = list(messages)
                    current_summary = metadata.get("summary", "")
                    
                    messages_to_summarize = messages_to_process[:trim_count]
                    messages_to_keep = messages_to_process[trim_count:]
                    
                    # Use ASYNC summarize
                    new_summary = await self._summarize_async(current_summary, messages_to_summarize)
                    metadata["summary"] = new_summary
                    
                    checkpoint = checkpoint.copy()
                    checkpoint["channel_values"] = checkpoint["channel_values"].copy()
                    checkpoint["channel_values"]["messages"] = messages_to_keep

                    # Reset Redis
                    await redis_client.async_client.set(redis_key, 0, ex=86400)
                    
            except Exception as e:
                logger.exception("STM Logic Error: {}", e)
                
            # Serialize
            type_, data_bytes = self.serde.dumps_typed(checkpoint)
            checkpoint_json = {
                "__serializer_type": type_,
                "__serializer_data": data_bytes.hex()
            }
            checkpoint_id = checkpoint["id"]
            
            # Persist to database (Async)
            async with self.db.get_session() as session:
                result = await session.execute(select(STM).filter(
                    STM.conversation_id == uuid.UUID(conversation_id)
                ))
                existing = result.scalars().first()
                
                if existing:
                    existing.checkpoint = checkpoint_json
                    existing.stm_id = checkpoint_id
                    existing.metadata_ = metadata
                else:
                    new_record = STM(
                        conversation_id=uuid.UUID(conversation_id),
                        checkpoint=checkpoint_json,
                        stm_id=checkpoint_id,
                        metadata_=metadata
                    )
                    session.add(new_record)
                
                await session.commit()
                
        except Exception as e:
            logger.exception("Error saving checkpoint: {}", e)

        return {
            "configurable": {
                "thread_id": conversation_id,
                "checkpoint_id": checkpoint["id"],
            }
        }