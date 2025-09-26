from typing import List


class DomainClassificationPrompts:
    """Prompts for domain classification tasks"""
    
    @staticmethod
    def get_domain_classification_prompt(categories: List[str], domain: str, content: str = None) -> str:
        """Get the domain classification prompt"""
        prompt = f"""
Classify the website domain "{domain}" into one or more of these categories:
{', '.join(categories)}

"""

        if content:
            # Limit content for LLM
            content_preview = content[:2000] + "..." if len(content) > 2000 else content
            prompt += f"""
Website content preview:
{content_preview}

"""

        prompt += f"""
Analyze the domain name and content (if provided) to determine the most appropriate categories.

Respond in JSON format:
{{
  "primary_category": "main category",
  "categories": [
    {{"category": "category1", "confidence": 0.9}},
    {{"category": "category2", "confidence": 0.7}}
  ],
  "reasoning": "Brief explanation of classification"
}}

Focus on the most relevant categories with confidence scores between 0.0 and 1.0.
"""
        return prompt