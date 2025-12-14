from typing import List, Dict, Any

class MemoryPrompts:
    @staticmethod
    def format_short_term_memory(chat_history: List[Dict[str, Any]]) -> str:
        """Format chat history (STM) for inclusion in prompts"""
        if not chat_history:
            return ""
        
        history_str = "\n\n**Chat History (Short Term Memory):**\n"
        for msg in chat_history:
            role = msg.get("role", "unknown").capitalize()
            content = msg.get("content", "")
            # Truncate long content to save tokens while keeping context
            if len(content) > 300:
                content = content[:300] + "..."
            history_str += f"{role}: {content}\n"
        
        return history_str

    @staticmethod
    def get_long_term_memory_prompt(context: str = "") -> str:
        """Format for Long Term Memory inclusion"""
        if not context:
            return ""
        
        return f"\n\n**Relevant Past Knowledge (Long Term Memory):**\n{context}\n"
