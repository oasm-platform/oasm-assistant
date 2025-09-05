"""
Source Validator for AI Agents
Validates credibility and reliability of search sources
"""
from typing import Dict, Any, Optional
from urllib.parse import urlparse
import re

from common.logger import logger

class SourceValidator:
    """Validates search result sources for AI agents"""
    
    def __init__(self):
        # Trusted domains (educational, government, reputable news)
        self.trusted_domains = {
            # Educational
            'edu', 'ac.uk', 'edu.au', 'ac.jp',
            # Government
            'gov', 'gov.uk', 'gov.au', 'gov.ca',
            # Reputable news
            'reuters.com', 'apnews.com', 'bbc.com', 'nytimes.com',
            'washingtonpost.com', 'theguardian.com', 'wsj.com',
            'bloomberg.com', 'ft.com', 'economist.com',
            # Tech/Science
            'nature.com', 'science.org', 'ieee.org', 'acm.org',
            # Medical
            'mayoclinic.org', 'webmd.com', 'nih.gov', 'cdc.gov',
            'who.int', 'medlineplus.gov'
        }
        
        # Suspicious patterns
        self.suspicious_patterns = [
            r'click\s*here',
            r'free\s*money',
            r'lose\s*weight',
            r'get\s*rich',
            r'miracle\s*cure',
            r'one\s*weird\s*trick',
            r'you\s*wont\s*believe'
        ]
        
        # Questionable domains
        self.questionable_domains = {
            'taboola.com', 'outbrain.com', 'clickbank.net',
            'offerjuice.me', 'clkmon.com', 'clkrev.com'
        }
    
    async def validate(self, result: Dict[str, Any]) -> bool:
        """Validate a search result source"""
        try:
            # Check if it's an error result
            if "error" in result:
                return True  # Don't filter out error results
            
            url = result.get("url", "")
            content = result.get("content", result.get("snippet", ""))
            
            # Validate URL
            if url and not await self._validate_url(url):
                return False
            
            # Validate content
            if content and not await self._validate_content(content):
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Error validating source: {e}")
            return True  # Default to accepting if validation fails
    
    async def _validate_url(self, url: str) -> bool:
        """Validate URL credibility"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Check for questionable domains
            for questionable in self.questionable_domains:
                if questionable in domain:
                    return False
            
            # Check domain extension
            domain_parts = domain.split('.')
            if len(domain_parts) > 1:
                tld = domain_parts[-1]
                # Very short TLDs are suspicious
                if len(tld) < 2:
                    return False
            
            return True
            
        except:
            return False
    
    async def _validate_content(self, content: str) -> bool:
        """Validate content quality"""
        try:
            content_lower = content.lower()
            
            # Check for suspicious patterns
            for pattern in self.suspicious_patterns:
                if re.search(pattern, content_lower):
                    return False
            
            # Check content length
            if len(content) < 10:
                return False
            
            # Check for excessive caps (spam indicator)
            caps_ratio = sum(1 for c in content if c.isupper()) / len(content)
            if caps_ratio > 0.5:
                return False
            
            return True
            
        except:
            return True
    
    async def score_source(self, result: Dict[str, Any]) -> float:
        """Score source credibility (0.0 to 1.0)"""
        try:
            score = 0.5  # Base score
            
            url = result.get("url", "")
            content = result.get("content", result.get("snippet", ""))
            
            if url:
                parsed = urlparse(url)
                domain = parsed.netloc.lower()
                
                # Boost for trusted domains
                for trusted in self.trusted_domains:
                    if trusted in domain:
                        score += 0.3
                        break
                
                # Penalty for questionable domains
                for questionable in self.questionable_domains:
                    if questionable in domain:
                        score -= 0.4
                        break
            
            if content:
                content_lower = content.lower()
                
                # Penalty for suspicious content
                for pattern in self.suspicious_patterns:
                    if re.search(pattern, content_lower):
                        score -= 0.2
                
                # Boost for well-formatted content
                if len(content) > 100:
                    score += 0.1
            
            return max(0.0, min(1.0, score))
            
        except:
            return 0.5
    
    async def get_source_info(self, url: str) -> Dict[str, Any]:
        """Get information about a source"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            info = {
                "domain": domain,
                "is_trusted": False,
                "is_questionable": False,
                "domain_type": "unknown"
            }
            
            # Determine domain type
            domain_parts = domain.split('.')
            if len(domain_parts) > 1:
                tld = domain_parts[-1]
                if tld in ['edu', 'gov', 'org']:
                    info["domain_type"] = "institutional"
                elif tld in ['com', 'net', 'io']:
                    info["domain_type"] = "commercial"
            
            # Check if trusted
            for trusted in self.trusted_domains:
                if trusted in domain:
                    info["is_trusted"] = True
                    break
            
            # Check if questionable
            for questionable in self.questionable_domains:
                if questionable in domain:
                    info["is_questionable"] = True
                    break
            
            return info
            
        except Exception as e:
            return {
                "domain": "unknown",
                "is_trusted": False,
                "is_questionable": False,
                "domain_type": "unknown",
                "error": str(e)
            }