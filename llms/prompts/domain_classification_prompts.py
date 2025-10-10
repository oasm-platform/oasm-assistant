from typing import List


class DomainClassificationPrompts:
    """Prompts for domain classification tasks"""
    
    @staticmethod
    def get_domain_classification_prompt(categories: List[str], domain: str, content: str = None) -> str:
        """Get the domain classification prompt"""
        prompt = f"""
You are an AI specialist in classifying and labeling digital assets based on HTML content, metadata, and technical characteristics of domains/subdomains.

TASK: Classify the domain "{domain}" into one or more most appropriate categories.

AVAILABLE CATEGORIES:
{', '.join(categories)}

"""

        if content:
            # Limit content for LLM but keep it substantial
            content_preview = content[:4000] + "..." if len(content) > 4000 else content
            prompt += f"""
ANALYSIS DATA:
{content_preview}

"""

        prompt += f"""
ANALYSIS GUIDELINES:
1. Analyze the domain/subdomain name to identify characteristic keywords
2. Examine metadata (title, description, keywords, generator, schema types...) to understand website purpose
3. Analyze main content to determine the type of service/application
4. Assess the importance level and risk of this domain

JSON RESPONSE FORMAT:
{{
  "primary_category": "most appropriate main category",
  "categories": [
    {{"category": "category1", "confidence": 0.9}},
    {{"category": "category2", "confidence": 0.7}}
  ],
  "reasoning": "Detailed explanation of the classification basis, including factors from domain name, metadata, and content used to make the decision"
}}

REQUIREMENTS:
- Confidence score from 0.0 to 1.0 (1.0 = 100% certain)
- Only assign categories with confidence >= 0.6
- Prioritize maximum 3 most appropriate categories
- Reasoning must be specific and based on actual data
"""
        return prompt