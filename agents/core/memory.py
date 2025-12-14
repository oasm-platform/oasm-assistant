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

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Save a checkpoint to the database."""
        thread_id = config["configurable"].get("thread_id")
        if not thread_id:
            return config

        try:
            # Serialize the checkpoint using dumps_typed (returns tuple of type and bytes)
            # JsonPlusSerializer defaults to msgpack, so we need to encode bytes for JSONB storage
            type_, data_bytes = self.serde.dumps_typed(checkpoint)
            
            # Prepare for JSONB storage by wrapping in a dict and hex-encoding bytes
            checkpoint_json = {
                "__serializer_type": type_,
                "__serializer_data": data_bytes.hex()
            }

            checkpoint_id = checkpoint["id"]
            
            # Upsert logic
            with self.db.get_session() as session:
                existing = session.query(STM).filter(
                    STM.thread_id == thread_id
                ).first()
                
                if existing:
                    existing.checkpoint = checkpoint_json
                    existing.checkpoint_id = checkpoint_id
                    existing.metadata_ = metadata
                    # We could store parent logic if available in metadata or logic
                else:
                    new_record = STM(
                        thread_id=thread_id,
                        checkpoint=checkpoint_json,
                        checkpoint_id=checkpoint_id,
                        metadata_=metadata
                    )
                    session.add(new_record)
                
                session.commit()
                # logger.debug(f"Saved checkpoint for thread {thread_id}")
                
        except Exception as e:
            logger.error(f"Error saving checkpoint: {e}")

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint["id"],
            }
        }