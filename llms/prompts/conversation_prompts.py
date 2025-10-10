class ConversationPrompts:
    """Prompts for conversation management tasks"""
    
    @staticmethod
    def get_conversation_title_prompt(question: str) -> str:
        """Get the conversation title generation prompt"""
        return f"""Please create a concise, descriptive title for this conversation based on the following question.
The title should be no more than 8 words, focusing on the main topic or intent of the question.
The title should be clear, specific, and capture the essence of the question without being too generic.

Question: {question}

Title: """