class ConversationPrompts:
    """Prompts for conversation management tasks"""
    
    @staticmethod
    def get_conversation_title_prompt(question: str) -> str:
        """Get the conversation title generation prompt"""
        return f"""
        Generate a concise, specific, and professional title (3-8 words) that summarizes the core intent of the user's question.

        Guidelines:
        1. **Language**: Use the SAME LANGUAGE as the question (e.g., Vietnamese -> Vietnamese, English -> English).
        2. **Format**: Output ONLY the raw text of the title. Do NOT use quotation marks ("") or any other formatting.
        3. **Content**: Focus on the action or subject (e.g., "SQL Injection Analysis" instead of "I want to check for SQLi").
        4. **Length**: Keep it short but descriptive.

        Question: "{question}"

        Title:
        """