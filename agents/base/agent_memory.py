"""
Memory system for agents in OASM Assistant
"""
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field
import json
import hashlib


class MemoryItem(BaseModel):
    """Represents a single memory item"""
    id: str
    content: Union[str, Dict[str, Any]]
    timestamp: datetime = Field(default_factory=datetime.now)
    importance: float = 0.0  # 0.0 to 1.0
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentMemory:
    """Main memory system for agents"""
    
    def __init__(self, max_short_term_items: int = 1000, max_long_term_items: int = 10000):
        self.short_term_memory: List[MemoryItem] = []
        self.long_term_memory: Dict[str, MemoryItem] = {}
        self.max_short_term_items = max_short_term_items
        self.max_long_term_items = max_long_term_items
    
    def _generate_id(self, content: Union[str, Dict[str, Any]]) -> str:
        """Generate a unique ID for memory items"""
        content_str = content if isinstance(content, str) else json.dumps(content, sort_keys=True)
        return hashlib.md5(content_str.encode()).hexdigest()
    
    def add_memory(
        self, 
        content: Union[str, Dict[str, Any]], 
        importance: float = 0.0,
        tags: List[str] = None,
        metadata: Dict[str, Any] = None,
        is_long_term: bool = False
    ) -> str:
        """Add a new memory item"""
        if tags is None:
            tags = []
        if metadata is None:
            metadata = {}
            
        memory_id = self._generate_id(content)
        memory_item = MemoryItem(
            id=memory_id,
            content=content,
            importance=importance,
            tags=tags,
            metadata=metadata
        )
        
        if is_long_term:
            # Add to long-term memory
            self.long_term_memory[memory_id] = memory_item
            # If we exceed the limit, remove the least important item
            if len(self.long_term_memory) > self.max_long_term_items:
                min_importance_id = min(
                    self.long_term_memory.keys(),
                    key=lambda k: self.long_term_memory[k].importance
                )
                del self.long_term_memory[min_importance_id]
        else:
            # Add to short-term memory
            self.short_term_memory.append(memory_item)
            # If we exceed the limit, remove the oldest item
            if len(self.short_term_memory) > self.max_short_term_items:
                self.short_term_memory.pop(0)
        
        return memory_id
    
    def get_memory(self, memory_id: str) -> Optional[MemoryItem]:
        """Retrieve a specific memory item by ID"""
        # Check long-term memory first
        if memory_id in self.long_term_memory:
            return self.long_term_memory[memory_id]
        
        # Check short-term memory
        for item in self.short_term_memory:
            if item.id == memory_id:
                return item
        
        return None
    
    def search_memories(
        self, 
        query: str = None, 
        tags: List[str] = None, 
        limit: int = 10,
        include_long_term: bool = True
    ) -> List[MemoryItem]:
        """Search memories based on query or tags"""
        results = []
        
        # Search in short-term memory
        results.extend(self._search_in_memory_list(
            self.short_term_memory, query, tags
        ))
        
        # Search in long-term memory if requested
        if include_long_term:
            long_term_list = list(self.long_term_memory.values())
            results.extend(self._search_in_memory_list(
                long_term_list, query, tags
            ))
        
        # Sort by importance and timestamp (newest first)
        results.sort(
            key=lambda x: (x.importance, x.timestamp),
            reverse=True
        )
        
        return results[:limit]
    
    def _search_in_memory_list(
        self, 
        memory_list: List[MemoryItem], 
        query: str = None, 
        tags: List[str] = None
    ) -> List[MemoryItem]:
        """Helper method to search in a list of memory items"""
        results = []
        
        for item in memory_list:
            # Match by tags if provided
            if tags:
                if any(tag in item.tags for tag in tags):
                    results.append(item)
                    continue
            
            # Match by query if provided
            if query:
                content_str = (
                    item.content 
                    if isinstance(item.content, str) 
                    else json.dumps(item.content)
                )
                if query.lower() in content_str.lower():
                    results.append(item)
                    continue
            
            # If neither query nor tags, include all items
            if not query and not tags:
                results.append(item)
        
        return results
    
    def get_recent_memories(self, count: int = 10) -> List[MemoryItem]:
        """Get the most recent memories from short-term memory"""
        return self.short_term_memory[-count:] if self.short_term_memory else []
    
    def clear_short_term_memory(self) -> None:
        """Clear short-term memory"""
        self.short_term_memory.clear()
    
    def consolidate_memory(self) -> None:
        """Move important short-term memories to long-term memory"""
        for item in self.short_term_memory:
            if item.importance > 0.7:  # Threshold for importance
                self.long_term_memory[item.id] = item
        
        # Clear short-term memory after consolidation
        self.clear_short_term_memory()