class ConversationPrompts:
    """Prompts for conversation management tasks"""
    
    @staticmethod
    def get_conversation_title_prompt(question: str) -> str:
        """Get the conversation title generation prompt"""
        return f"""
        Create a concise and specific title (maximum 8 words) that accurately reflects the main topic of the user's question.
        Guidelines:
        - Focus on the primary intent or subject.
        - Avoid vague or generic titles.
        - Do not repeat the full question.
        - Keep the title short, clear, and meaningful.
        - **Use the SAME LANGUAGE as the question** (if question is in Vietnamese, title must be in Vietnamese; if in English, title in English)

        Question: {question}

        Title:
        """