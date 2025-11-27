from typing import List, Dict, Optional
import re
import json

from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from common.logger import logger
from llms import llm_manager
from tools.crawl_web import CrawlWeb
from common.config import configs
from app.protos import assistant_pb2, assistant_pb2_grpc
import grpc
from llms.prompts import DomainClassificationPrompts
from app.interceptors import get_metadata_interceptor

class DomainClassifier(assistant_pb2_grpc.DomainClassifyServicer):
    def __init__(self):
        self.llm_manager = llm_manager
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

    def _extract_domain_info(self, domain: str) -> Dict[str, str]:
        domain = domain.lower().strip()
        if domain.startswith('http'):
            domain = domain.split('://')[1]
        if '/' in domain:
            domain = domain.split('/')[0]

        parts = domain.split('.')
        tld = parts[-1] if len(parts) > 1 else ""
        subdomain = parts[0] if len(parts) > 2 else ""
        main_domain = parts[-2] if len(parts) > 1 else parts[0]

        return {
            "domain": domain,
            "main_domain": main_domain,
            "tld": tld,
            "subdomain": subdomain
        }

    async def _classify_with_llm(self, domain: str, content: Optional[str] = None, retry_count: int = 0) -> List[str]:
        """
        Classify using LLM - returns list of category strings
        """
        try:
            llm = self.llm_manager.get_llm()

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
                logger.error(f"JSON parse error for {domain}: {e}")
                return []

        except Exception as e:
            logger.error(f"LLM classification error for {domain}: {e}")
            return []

    async def classify_domain(self, domain: str) -> Dict[str, any]:
        """
        Main classification method with retry logic
        """
        try:
            domain_info = self._extract_domain_info(domain)

            content = None
            crawl_result = self.crawler.crawl(domain)
            if crawl_result:
                content = crawl_result

            labels = []
            retry_count = 0

            while len(labels) < self.min_labels and retry_count < self.max_retries:
                labels = await self._classify_with_llm(domain, content, retry_count)

                if len(labels) >= self.min_labels:
                    break

                retry_count += 1
                if retry_count < self.max_retries:
                    logger.warning(
                        f"Only got {len(labels)} labels (need {self.min_labels}), "
                        f"retrying... (attempt {retry_count + 1}/{self.max_retries})"
                    )

            if len(labels) < self.min_labels:
                logger.warning(
                    f"After {self.max_retries} retries, only got {len(labels)} labels for {domain}. "
                    f"Using fallback categories."
                )
                fallback_categories = ["business", "technology", "web"]
                labels.extend([cat for cat in fallback_categories if cat not in labels])
                labels = labels[:self.min_labels]

            if len(labels) > self.max_labels:
                labels = labels[:self.max_labels]

            return {
                "domain": domain_info["domain"],
                "labels": labels,
                "success": True,
            }

        except Exception as e:
            logger.error(f"Domain classification error for {domain}: {e}")
            return {
                "domain": domain,
                "labels": [],
                "success": False,
                "error": str(e)
            }
    @get_metadata_interceptor
    async def DomainClassify(self, request, context):
        try:
            domain = request.domain
            logger.info(f"Domain classification request for: {domain}")
            if not domain:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("Domain is required")
                return assistant_pb2.DomainClassifyResponse(labels=[])

            result = await self.classify_domain(domain)
            labels = result.get("labels", [])

            logger.info(f"Domain classification completed for {domain}: {labels}")

            return assistant_pb2.DomainClassifyResponse(labels=labels)

        except Exception as e:
            logger.error(f"Domain classification error for {request.domain}: {e}")
            return assistant_pb2.DomainClassifyResponse(labels=[])
