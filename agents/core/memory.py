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


class STMCheckpointer(BaseCheckpointSaver):
    """
    Persist LangGraph state to PostgreSQL database.
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
        """Get a checkpoint tuple from the database."""
        conversation_id = config["configurable"].get("thread_id")
        if not conversation_id:
            return None

        try:
            with self.db.get_session() as session:
                # Retrieve the latest checkpoint for this conversation
                row = session.query(STM).filter(
                    STM.conversation_id == uuid.UUID(conversation_id)
                ).first()

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
            logger.exception("Error reading checkpoint: {}", e)
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
        # Simplification: we only store latest state in this table design for now.
        yield from []

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Async version of put that runs the synchronous `put` method in a separate thread to avoid blocking."""
        return await asyncio.to_thread(
            self.put, config, checkpoint, metadata, new_versions
        )

    def _summarize_sync(self, current_summary: str, messages_to_summarize: list) -> str:
        """Generate summary synchronously"""
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
            llm = LLMManager.get_llm(workspace_id=self.workspace_id, user_id=self.user_id)
            # Use invoke for sync call
            summary = llm.invoke(prompt)
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
        """Save a checkpoint to the database with STM optimization (Sliding Window + Summary)."""
        conversation_id = config["configurable"].get("thread_id")
        if not conversation_id:
            return config

        try:
            # STM Optimization: Batch Cycle Pattern (Count 1 -> Limit -> Reset)
            channel_values = checkpoint.get("channel_values", {})
            messages = channel_values.get("messages", [])
            messages_len = len(messages)
            
            # Configs (Unit: Pairs)
            context_pairs = configs.memory.stm_context_messages
            stack_pairs = configs.memory.stm_summary_stack_messages
            
            context_limit_msg = context_pairs * 2
            
            # Redis Logic: Increment and Check
            redis_key = f"stm:stack_count:{conversation_id}"
            
            # Because 'put' is called after AI generation (1 pair added), we increment.
            # However, put might be called multiple times. 
            # Ideally, we read current val, checking if we should trigger.
            # But the user wants "Question 1 -> Redis 1".
            # The most robust way is: Calculate Term Count relative to the last check? 
            # No, user wants simple counter.
            
            # Let's trust the logic: Current Total Pairs
            current_total_pairs = messages_len // 2
            
            # We need a volatile counter that resets. Total Pairs doesn't reset.
            # So we use INCR.
            # Warning: Repeated calls to put for same state? LangGraph usually checkpoints once per step.
            
            # Increment atomic
            try:
                # Increment atomic and get new count directly
                # Removed redundant get() call as incr() returns the new value
                new_count = redis_client.incr(redis_key)
                redis_client.expire(redis_key, 86400)
                
                if new_count >= stack_pairs:
                    # Force Summary based on Stack Config
                    target_cut_msg = stack_pairs * 2
                    trim_count = min(messages_len, target_cut_msg)
                    
                    messages_to_process = list(messages)
                    current_summary = metadata.get("summary", "")
                    
                    messages_to_summarize = messages_to_process[:trim_count]
                    messages_to_keep = messages_to_process[trim_count:]
                    
                    new_summary = self._summarize_sync(current_summary, messages_to_summarize)
                    metadata["summary"] = new_summary
                    
                    checkpoint = checkpoint.copy()
                    checkpoint["channel_values"] = checkpoint["channel_values"].copy()
                    checkpoint["channel_values"]["messages"] = messages_to_keep

                    # Reset Redis
                    redis_client.set(redis_key, 0, ex=86400)
                    
            except Exception as e:
                logger.exception("STM Logic Error: {}", e)
                
            # Serialize for JSONB storage (hex-encoded binary)
            type_, data_bytes = self.serde.dumps_typed(checkpoint)
            
            checkpoint_json = {
                "__serializer_type": type_,
                "__serializer_data": data_bytes.hex()
            }

            checkpoint_id = checkpoint["id"]
            
            # Persist to database
            with self.db.get_session() as session:
                existing = session.query(STM).filter(
                    STM.conversation_id == uuid.UUID(conversation_id)
                ).first()
                
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
                
                session.commit()
                
        except Exception as e:
            logger.exception("Error saving checkpoint: {}", e)

        return {
            "configurable": {
                "thread_id": conversation_id,
                "checkpoint_id": checkpoint["id"],
            }
        }