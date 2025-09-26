from typing import List, Dict, Tuple, Optional
from langchain_core.messages import HumanMessage
from common.logger import logger
import re
import json
from llms import LLMManager
from tools.crawl_web import CrawlWeb
from common.config import configs
from app.protos import assistant_pb2, assistant_pb2_grpc
import grpc
from common.config import configs
from llms.prompts import DomainClassificationPrompts

class DomainClassifier(assistant_pb2_grpc.DomainClassifyServicer):
    def __init__(self):
        self.llm_manager = LLMManager(configs.llm)
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

    def _classify_by_domain_patterns(self, domain_info: Dict[str, str]) -> List[Tuple[str, float]]:
        """Classify based on domain patterns"""
        scores = []
        domain = domain_info["domain"]
        main_domain = domain_info["main_domain"]
        subdomain = domain_info["subdomain"]
        tld = domain_info["tld"]
        
        # E-commerce patterns
        ecommerce_patterns = ['shop', 'store', 'buy', 'sell', 'mart', 'commerce', 'cart']
        if any(pattern in main_domain for pattern in ecommerce_patterns):
            scores.append(("e-commerce", 0.8))
        
        # News patterns
        news_patterns = ['news', 'press', 'times', 'post', 'herald', 'tribune']
        if any(pattern in main_domain for pattern in news_patterns):
            scores.append(("news", 0.8))
        
        # Blog patterns
        blog_patterns = ['blog', 'diary', 'journal']
        if any(pattern in main_domain for pattern in blog_patterns) or subdomain == 'blog':
            scores.append(("blog", 0.7))
        
        # Social media patterns
        social_patterns = ['facebook', 'twitter', 'instagram', 'linkedin', 'youtube', 'tiktok']
        if any(pattern in domain for pattern in social_patterns):
            scores.append(("social_media", 0.9))
        
        # Government patterns
        if tld in ['gov', 'mil'] or 'government' in main_domain:
            scores.append(("government", 0.9))
        
        # Education patterns
        if tld == 'edu' or any(pattern in main_domain for pattern in ['school', 'university', 'college', 'academy']):
            scores.append(("education", 0.8))
        
        # Technology patterns
        tech_patterns = ['tech', 'software', 'app', 'dev', 'code', 'digital', 'ai', 'ml']
        if any(pattern in main_domain for pattern in tech_patterns):
            scores.append(("technology", 0.7))
        
        return scores

    def _classify_with_llm(self, domain: str, content: Optional[str] = None) -> Dict[str, any]:
        """Classify using LLM"""
        try:
            llm = self.llm_manager.get_llm()
            
            # Prepare prompt using external prompt
            prompt = DomainClassificationPrompts.get_domain_classification_prompt(
                categories=self.categories,
                domain=domain,
                content=content
            )
            
            response = llm.invoke([HumanMessage(content=prompt)])
            
            # Parse response
            try:
                # Extract JSON from response
                json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    return result
                else:
                    # Fallback parsing
                    return {
                        "primary_category": "",
                        "categories": [],
                        "reasoning": "Could not parse LLM response"
                    }
            except json.JSONDecodeError:
                return {
                    "primary_category": "",
                    "categories": [],
                    "reasoning": "Invalid JSON response from LLM"
                }
                
        except Exception as e:
            logger.error(f"LLM classification error: {e}")
            return {
                "primary_category": "",
                "categories": [],
                "reasoning": f"Error during LLM classification: {str(e)}"
            }

    def classify_domain(self, domain: str) -> Dict[str, any]:
        """Main classification method"""
        try:
            # Extract domain information
            domain_info = self._extract_domain_info(domain)
            
            # Get content by crawling
            content = None
            crawl_result = self.crawler.crawl(domain)
            if crawl_result:
                content = crawl_result
            
            # Pattern-based classification
            pattern_scores = self._classify_by_domain_patterns(domain_info)
            
            # LLM-based classification with content
            llm_result = self._classify_with_llm(domain, content)
            
            # Combine results
            all_scores = {}
            
            # Add pattern scores
            for category, score in pattern_scores:
                all_scores[category] = max(all_scores.get(category, 0), score)
            
            # Add LLM scores
            for cat_data in llm_result.get('categories', []):
                category = cat_data.get('category', 'unknown')
                confidence = cat_data.get('confidence', 0.5)
                all_scores[category] = max(all_scores.get(category, 0), confidence)
            
            # Sort by confidence
            sorted_categories = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)
            
            # Get top categories
            labels = [cat for cat, score in sorted_categories if score >= configs.classification_confidence_threshold]
            # Return empty array if no categories meet threshold
            
            # Calculate overall confidence
            overall_confidence = max(all_scores.values()) if all_scores else 0.5
            
            result = {
                "domain": domain_info["domain"],
                "labels": labels,
                "confidence": overall_confidence,
                "category_scores": [{"category": cat, "score": score} for cat, score in sorted_categories],
                "content_summary": '',
                "success": True,
                "reasoning": llm_result.get('reasoning', '')
            }
            
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
                "error": str(e)
            }

    def DomainClassify(self, request, context):
        """Domain classification endpoint"""
        try:
            domain = request.domain
            
            if not domain:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("Domain is required")
                return assistant_pb2.DomainClassifyResponse(
                    label=[]
                )
            
            result = self.classify_domain(domain)
            
            # Build response (only using 'label' field from old proto)
            labels = result.get("labels", [])
            
            response = assistant_pb2.DomainClassifyResponse(
                label=labels
            )
            
            logger.info(f"Domain classification completed for {domain}: {labels}")
            return response
            
        except Exception as e:
            logger.error(f"Domain classification error for {request.domain}: {e}")
            
            return assistant_pb2.DomainClassifyResponse(
                label=[]
            )