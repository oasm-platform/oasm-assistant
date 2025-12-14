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
from llms import llm_manager
from llms.prompts.memory_prompts import MemoryPrompts
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
import asyncio


class STMCheckpointer(BaseCheckpointSaver):
    """
    Persist LangGraph state to PostgreSQL database.
    """
    def __init__(self, serde=None):
        super().__init__(serde=serde)
        self.db = postgres_db

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Get a checkpoint tuple from the database."""
        thread_id = config["configurable"].get("thread_id")
        if not thread_id:
            return None

        try:
            with self.db.get_session() as session:
                # Retrieve the latest checkpoint for this thread
                row = session.query(STM).filter(
                    STM.thread_id == thread_id
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
                            "thread_id": thread_id,
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
            logger.error(f"Error reading checkpoint: {e}")
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
        """Async version of put (Not strictly enforced by BaseCheckpointSaver but useful for async usage)"""
        return self.put(config, checkpoint, metadata, new_versions)

    def _summarize_sync(self, current_summary: str, messages_to_summarize: list) -> str:
        """Generate summary synchronously"""
        try:
            conversation_text = ""
            for msg in messages_to_summarize:
                role = "Human" if isinstance(msg, HumanMessage) else "AI"
                conversation_text += f"{role}: {msg.content}\n"
            
            prompt = MemoryPrompts.get_conversation_summary_prompt(current_summary, conversation_text)
            llm = llm_manager.get_llm()
            # Use invoke for sync call
            summary = llm.invoke(prompt)
            return summary.content.strip()
        except Exception as e:
            logger.error(f"STM Summarization failed: {e}")
            return current_summary

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Save a checkpoint to the database with STM optimization (Sliding Window + Summary)."""
        thread_id = config["configurable"].get("thread_id")
        if not thread_id:
            return config

        try:
            # STM Optimization: Summarize and truncate if exceeding limit
            channel_values = checkpoint.get("channel_values", {})
            messages = channel_values.get("messages", [])
            max_messages = configs.memory.stm_max_messages
            
            if len(messages) > max_messages:
                # Clone to avoid mutating original reference
                messages_to_process = list(messages)
                current_summary = metadata.get("summary", "")
                
                # Calculate trim range
                trim_count = len(messages_to_process) - max_messages
                messages_to_summarize = messages_to_process[:trim_count]
                messages_to_keep = messages_to_process[trim_count:]
                
                logger.info(f"STM: Summarizing {len(messages_to_summarize)} old messages for thread {thread_id}...")
                
                # Generate summary
                new_summary = self._summarize_sync(current_summary, messages_to_summarize)
                metadata["summary"] = new_summary
                
                # Update checkpoint with optimized data
                checkpoint = checkpoint.copy()
                checkpoint["channel_values"] = checkpoint["channel_values"].copy()
                checkpoint["channel_values"]["messages"] = messages_to_keep
                
                logger.debug(f"STM: Optimized memory. Messages: {len(messages)} -> {len(messages_to_keep)}. Summary updated.")

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
                    STM.thread_id == thread_id
                ).first()
                
                if existing:
                    existing.checkpoint = checkpoint_json
                    existing.checkpoint_id = checkpoint_id
                    existing.metadata_ = metadata
                else:
                    new_record = STM(
                        thread_id=thread_id,
                        checkpoint=checkpoint_json,
                        checkpoint_id=checkpoint_id,
                        metadata_=metadata
                    )
                    session.add(new_record)
                
                session.commit()
                
        except Exception as e:
            logger.error(f"Error saving checkpoint: {e}", exc_info=True)

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint["id"],
            }
        }