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

    @staticmethod
    def get_conversation_summary_prompt(current_summary: str, new_lines: str) -> str:
        """Prompt to update conversation summary with new interactions"""
        if not current_summary:
            return f"""Progressively summarize the lines of conversation provided, adding to the previous summary returning a new summary.

EXAMPLE
Current summary:
The human asks what the AI thinks of artificial intelligence. The AI thinks artificial intelligence is a force for good.

New lines of conversation:
Human: Why do you think artificial intelligence is a force for good?
AI: Because artificial intelligence will help humans reach their full potential.

New summary:
The human asks what the AI thinks of artificial intelligence. The AI thinks artificial intelligence is a force for good because it will help humans reach their full potential.
END OF EXAMPLE

Current summary:
(No previous summary)

New lines of conversation:
{new_lines}

New summary:"""
        
        return f"""Progressively summarize the lines of conversation provided, adding to the previous summary returning a new summary.

Current summary:
{current_summary}

New lines of conversation:
{new_lines}

New summary:"""
