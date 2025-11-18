from typing import List


class DomainClassificationPrompts:
    """Prompts for domain classification tasks"""

    @staticmethod
    def get_domain_classification_prompt(categories: List[str], domain: str, content: str = None) -> str:
        """Get the improved domain classification prompt"""
        prompt = f"""
You are an AI system that classifies digital assets (domains and subdomains) using domain structure, HTML content, and metadata.

TASK:
Classify the domain "{domain}" using categories from the list below.

AVAILABLE CATEGORIES:
{', '.join(categories)}

"""

        if content:
            content_preview = content[:4000] + "..." if len(content) > 4000 else content
            prompt += f"""
INPUT DATA (TRUNCATED IF TOO LONG):
{content_preview}

"""

        prompt += f"""
CLASSIFICATION RULES:
1. Analyze domain/subdomain name patterns and keywords.
2. Use metadata such as title, description, keywords, generator, schema types if available.
3. Use main content and functional signals to determine purpose.
4. Ignore ads, boilerplate, and unrelated tracking scripts.
5. Assign labels strictly based on evidence — avoid speculation.
6. Select at least 3 labels and at most 6 labels.
7. All labels must exist in AVAILABLE CATEGORIES.

OUTPUT FORMAT (STRICT JSON):
{{
  "primary_category": "the single most relevant category",
  "categories": [
    "category1",
    "category2",
    "category3"
  ],
  "reasoning": "Concise explanation referencing domain name, metadata, and/or content."
}}

OUTPUT RULES:
- primary_category must be included inside the `categories` list.
- categories must contain at least 3 items and no more than 6.
- No scoring, no confidence values.
- Reasoning must cite actual observations (example: keywords detected, metadata hints, content themes).
"""
        return prompt
