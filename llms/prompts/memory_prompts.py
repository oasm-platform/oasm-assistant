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
    def get_conversation_summary_prompt(current_summary: str, new_lines: str) -> str:
        """Prompt to update conversation summary with new interactions."""
        return f"""You are an expert conversation summarizer.
Goal: Update (or create) a concise summary of the conversation between the User and the AI.

Rules: 
1. Language: MUST match the language used in the 'New conversation lines'.
2. Length: Keep the summary between 50-120 tokens (approx. 3-6 sentences). NEVER exceed 150 tokens.
3. Content: Focus on the main intent, key questions, and concrete solutions/actions. Identify the user's goal.
4. Coherence: Merge specific details into a smooth narrative. Avoid generic phrases like "The user asked...".

Current summary:
{current_summary if current_summary else "N/A"}

New conversation lines:
{new_lines}

Updated summary (in the same language as conversation):"""
