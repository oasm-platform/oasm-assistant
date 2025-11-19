from typing import List


class DomainClassificationPrompts:
    """Prompts for domain classification tasks"""

    @staticmethod
    def get_domain_classification_prompt(
        categories: List[str],
        domain: str,
        content: str = None,
        min_labels: int = 3,
        max_labels: int = 5
    ) -> str:
        """Get the improved domain classification prompt"""
        prompt = f"""You are a domain classification expert. Your task is to classify the domain "{domain}" into {min_labels} to {max_labels} categories.

AVAILABLE CATEGORIES:
{', '.join(categories)}

"""

        if content:
            content_preview = content[:4000] + "..." if len(content) > 4000 else content
            prompt += f"""WEBSITE CONTENT:
{content_preview}

"""

        prompt += f"""CLASSIFICATION GUIDELINES:
1. Analyze the domain name structure and keywords
2. Review the website content, title, meta description, and main text
3. Identify the primary purpose and functionality
4. Consider secondary features and services
5. Select {min_labels} to {max_labels} most relevant categories
6. ALL categories MUST be from the AVAILABLE CATEGORIES list above (exact match)

CRITICAL INSTRUCTIONS:
- Return ONLY valid JSON - no explanations, no reasoning text, no additional commentary
- Use exact category names from the list (case-sensitive: "E-Commerce", "Social Media", etc.)
- Do not create new categories
- Do not use lowercase or modified versions

REQUIRED JSON FORMAT:
{{
  "categories": ["Category 1", "Category 2", "Category 3"]
}}

Example valid response:
{{"categories": ["E-Commerce", "Business", "Technology"]}}

Now classify the domain "{domain}" and respond with ONLY the JSON object:"""
        return prompt
