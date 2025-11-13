from typing import List, Dict, Tuple, Optional
from langchain_core.messages import HumanMessage
from common.logger import logger
import re
import json
from llms import llm_manager
from tools.crawl_web import CrawlWeb
from common.config import configs
from app.protos import assistant_pb2, assistant_pb2_grpc
import grpc
from common.config import configs
from llms.prompts import DomainClassificationPrompts

class DomainClassifier(assistant_pb2_grpc.DomainClassifyServicer):
    def __init__(self):
        self.llm_manager = llm_manager
        self.crawler = CrawlWeb(
            timeout=configs.crawl_timeout,
            max_retries=configs.crawl_max_retries
        )
        
        self.categories = [
            "e-commerce", "news", "blog", "social_media", "education",
            "business", "technology", "health", "entertainment", "sports",
            "finance", "government", "nonprofit", "personal", "forum",
            "documentation", "portfolio", "landing_page", "adult",
            "travel", "food", "gaming", "music", "art", "photography",
            "fashion", "automotive", "real_estate", "job_portal", "dating",
            "streaming", "podcast", "wiki", "search_engine", "cloud_service",
            "api", "marketplace", "cryptocurrency", "banking", "insurance",
            "legal", "consulting", "marketing", "design", "startup",
            "agency", "saas", "tools", "utilities", "weather"
        ]

    def _extract_domain_info(self, domain: str) -> Dict[str, str]:
        """Extract information from domain name"""
        # Clean domain
        domain = domain.lower().strip()
        if domain.startswith('http'):
            domain = domain.split('://')[1]
        if '/' in domain:
            domain = domain.split('/')[0]
        
        # Extract TLD and subdomain
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


    def _classify_with_llm(self, domain: str, content: Optional[str] = None) -> Dict[str, any]:
        """Classify using LLM - Step 2 of specification"""
        try:
            llm = self.llm_manager.get_llm()

            # Prepare prompt using external prompt
            prompt = DomainClassificationPrompts.get_domain_classification_prompt(
                categories=self.categories,
                domain=domain,
                content=content
            )

            logger.info(f"Sending domain classification request for: {domain}")
            response = llm.invoke([HumanMessage(content=prompt)])

            # Parse response with improved error handling
            try:
                # Extract JSON from response - look for first complete JSON object
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response.content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())

                    # Validate required fields
                    if not isinstance(result.get('categories'), list):
                        result['categories'] = []
                    if not result.get('primary_category'):
                        result['primary_category'] = ""
                    if not result.get('reasoning'):
                        result['reasoning'] = "LLM classification completed"

                    logger.info(f"LLM classification successful for {domain}")
                    return result
                else:
                    logger.warning(f"No JSON found in LLM response for {domain}")
                    # Try to extract at least some info from text response
                    return self._fallback_parse_response(response.content)

            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error for {domain}: {e}")
                return self._fallback_parse_response(response.content)

        except Exception as e:
            logger.error(f"LLM classification error for {domain}: {e}")
            return {
                "primary_category": "",
                "categories": [],
                "reasoning": f"Error during LLM classification: {str(e)}"
            }

    def _fallback_parse_response(self, response_text: str) -> Dict[str, any]:
        """Fallback parsing when JSON extraction fails"""
        # Try to extract category names from response
        found_categories = []
        response_lower = response_text.lower()

        for category in self.categories:
            if category.lower() in response_lower:
                found_categories.append({
                    "category": category,
                    "confidence": 0.7  # Default confidence for fallback
                })

        return {
            "primary_category": found_categories[0]["category"] if found_categories else "",
            "categories": found_categories[:3],  # Max 3 categories
            "reasoning": "Fallback parsing - JSON extraction failed"
        }

    def classify_domain(self, domain: str) -> Dict[str, any]:
        """Main classification method - Following specification: Step 1: Collect data, Step 2: LLM classification"""
        try:
            # Step 1: Collect data from URL/subdomain
            domain_info = self._extract_domain_info(domain)

            # Get HTTP response and extract HTML title, meta tags, body content
            content = None
            crawl_result = self.crawler.crawl(domain)
            if crawl_result:
                content = crawl_result

            # Step 2: Aggregate data and use LLM for labeling
            llm_result = self._classify_with_llm(domain, content)

            # Process LLM results
            all_scores = {}
            labels = []

            # Extract categories from LLM result
            for cat_data in llm_result.get('categories', []):
                category = cat_data.get('category', 'unknown')
                confidence = cat_data.get('confidence', 0.0)

                # Only include categories with confidence >= 0.6 as per prompt specification
                if confidence >= 0.6:
                    all_scores[category] = confidence
                    labels.append(category)

            # Sort by confidence
            sorted_categories = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)

            # Use primary category from LLM if available and confidence is high enough
            primary_category = llm_result.get('primary_category', '')
            if primary_category and primary_category in labels:
                # Move primary category to front
                labels = [primary_category] + [cat for cat in labels if cat != primary_category]

            # Calculate overall confidence
            overall_confidence = max(all_scores.values()) if all_scores else 0.0

            result = {
                "domain": domain_info["domain"],
                "labels": labels,
                "confidence": overall_confidence,
                "category_scores": [{"category": cat, "score": score} for cat, score in sorted_categories],
                "content_summary": content[:200] + "..." if content and len(content) > 200 else content or "",
                "success": True,
                "reasoning": llm_result.get('reasoning', ''),
                "primary_category": primary_category
            }

            logger.info(f"Domain classified: {domain} -> {labels} (confidence: {overall_confidence:.2f})")
            return result

        except Exception as e:
            logger.error(f"Domain classification error for {domain}: {e}")
            return {
                "domain": domain,
                "labels": [],
                "confidence": 0.0,
                "category_scores": [],
                "content_summary": "",
                "success": False,
                "error": str(e),
                "primary_category": ""
            }

    def DomainClassify(self, request, context):
        """Domain classification endpoint"""
        try:
            domain = request.domain
            
            if not domain:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("Domain is required")
                return assistant_pb2.DomainClassifyResponse(
                    labels=[]
                )
            
            result = self.classify_domain(domain)
            
            # Build response (only using 'label' field from old proto)
            labels = result.get("labels", [])
            
            response = assistant_pb2.DomainClassifyResponse(
                labels=labels
            )
            
            logger.info(f"Domain classification completed for {domain}: {labels}")
            return response
            
        except Exception as e:
            logger.error(f"Domain classification error for {request.domain}: {e}")
            
            return assistant_pb2.DomainClassifyResponse(
                labels=[]
            )