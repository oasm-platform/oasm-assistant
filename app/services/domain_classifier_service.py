from typing import List, Dict, Optional, Any
import re
import json

from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from common.logger import logger
from llms import LLMManager
from tools.crawl_web import CrawlWeb
from common.config import configs
from llms.prompts import DomainClassificationPrompts

from data.database import postgres_db
from data.database.models import LLMConfig

class DomainClassifierService:
    def __init__(self):
        # LLM Manager is now a static utility
        self.db = postgres_db
        self.crawler = CrawlWeb(
            timeout=configs.crawl_timeout,
            max_retries=configs.crawl_max_retries
        )
        self.min_labels = configs.domain_classifier.min_labels
        self.max_labels = configs.domain_classifier.max_labels
        self.max_retries = configs.domain_classifier.max_retries
        self.categories = configs.domain_classifier.categories

        # LangChain JSON parser
        self.json_parser = JsonOutputParser()

    def _extract_domain_info(self, domain: str) -> str:
        """Extract domain from URL or string"""
        from urllib.parse import urlparse
        domain = domain.lower().strip()
        if '://' not in domain:
            domain = 'http://' + domain
        
        parsed = urlparse(domain)
        return parsed.netloc or parsed.path.split('/')[0]

    async def _classify_with_llm(self, domain: str, content: Optional[str] = None, retry_count: int = 0, workspace_id: Optional[str] = None, user_id: Optional[str] = None) -> List[str]:
        """
        Classify using LLM - returns list of category strings
        """
        try:
            llm = LLMManager.get_llm(workspace_id=workspace_id, user_id=user_id)

            prompt = DomainClassificationPrompts.get_domain_classification_prompt(
                categories=self.categories,
                domain=domain,
                content=content,
                min_labels=self.min_labels,
                max_labels=self.max_labels
            )

            response = await llm.ainvoke([HumanMessage(content=prompt)])

            # Parse response - extract JSON from LLM output
            try:
                response_text = response.content

                # Try LangChain parser first
                try:
                    parsed = self.json_parser.parse(response_text)
                except Exception:
                    # Fallback: Extract JSON manually using regex
                    # Look for JSON object in the response
                    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
                    if not json_match:
                        logger.warning(f"No JSON found in LLM response for {domain}")
                        return []

                    parsed = json.loads(json_match.group())

                categories = parsed.get("categories", [])

                if not isinstance(categories, list):
                    logger.warning(f"LLM returned invalid 'categories' type for {domain}")
                    return []

                # Filter to only valid categories (case-insensitive matching)
                valid_categories = []
                for cat in categories:
                    if not isinstance(cat, str):
                        continue

                    # Try exact match first
                    if cat in self.categories:
                        valid_categories.append(cat)
                    else:
                        # Try case-insensitive match
                        cat_lower = cat.lower()
                        for valid_cat in self.categories:
                            if valid_cat.lower() == cat_lower:
                                valid_categories.append(valid_cat)
                                break

                return valid_categories

            except Exception as e:
                logger.error("JSON parse error for {}: {}", domain, e)
                return []

        except Exception as e:
            logger.error("LLM classification error for {}: {}", domain, e)
            raise e

    async def classify_domain(self, domain: str, workspace_id: Optional[Any] = None, user_id: Optional[Any] = None) -> Dict[str, Any]:
        """
        Main classification method with retry logic
        """
        try:
            cleaned_domain = self._extract_domain_info(domain)

            content = None
            crawl_result = self.crawler.crawl(domain)
            if crawl_result:
                # Truncate content to avoid too much unnecessary info
                content = crawl_result[:10000] if isinstance(crawl_result, str) else str(crawl_result)[:10000]

            labels = await self._classify_with_llm(cleaned_domain, content, 0, workspace_id=workspace_id, user_id=user_id)

            if not labels:
                logger.warning(
                    f"LLM returned 0 labels for {domain}. Using fallback categories."
                )
                labels = ["Business", "Technology", "Web"]

            if len(labels) > self.max_labels:
                labels = labels[:self.max_labels]

            # Ensure all labels are formatted as Title Case
            labels = [label.title() for label in labels]

            return {
                "domain": cleaned_domain,
                "labels": labels,
                "success": True,
            }

        except Exception as e:
            logger.error("Domain classification error for {}: {}", domain, e)
            return {
                "domain": domain,
                "labels": [],
                "success": False,
                "error": str(e)
            }
