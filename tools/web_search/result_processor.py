from typing import List, Dict, Any
from datetime import datetime
from urllib.parse import urlparse
import re

from common.logger import logger


class SearchResultProcessor:
    """Processes search results for AI agents"""
    
    def __init__(self):
        self.min_snippet_length = 50
        self.max_snippet_length = 500
    
    async def process_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process and clean search results"""
        try:
            processed_results = []
            seen_urls = set()
            
            for result in results:
                # Skip error results
                if "error" in result:
                    processed_results.append(result)
                    continue
                
                # Deduplicate by URL
                url = result.get("url", "")
                if url and url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)
                
                # Clean and format result
                cleaned_result = await self._clean_result(result)   
                if cleaned_result:
                    processed_results.append(cleaned_result)
            
            return processed_results
            
        except Exception as e:
            logger.error(f"Error processing results: {e}")
            return results
    
    async def _clean_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Clean individual result"""
        try:
            cleaned = result.copy()
            
            # Extract content from various fields
            content = (
                result.get("content") or
                result.get("snippet") or
                result.get("description") or
                ""
            )
            
            # Clean content
            content = self._clean_text(content)
            
            # Truncate if too long
            if len(content) > self.max_snippet_length:
                content = content[:self.max_snippet_length] + "..."
            
            # Skip if content is too short
            if len(content) < self.min_snippet_length and "content" not in result:
                return None
            
            cleaned["content"] = content
            
            # Extract domain from URL
            url = result.get("url", "")
            if url:
                try:
                    domain = urlparse(url).netloc
                    cleaned["domain"] = domain
                except:
                    cleaned["domain"] = "unknown"
            
            # Add processed timestamp
            cleaned["processed_at"] = datetime.now().isoformat()
            
            return cleaned
            
        except Exception as e:
            logger.warning(f"Error cleaning result: {e}")
            return result
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s\.\,\!\?\;\:\-\(\)]', ' ', text)
        
        # Fix spacing around punctuation
        text = re.sub(r'\s+([\.!?:;,])', r'\1', text)
        
        return text
    
    async def format_for_llm(self, results: List[Dict[str, Any]]) -> str:
        """Format results for LLM consumption"""
        try:
            formatted = "Search Results:\n\n"
            
            for i, result in enumerate(results, 1):
                if "error" in result:
                    continue
                    
                title = result.get("title", f"Result {i}")
                content = result.get("content", "")
                url = result.get("url", "")
                
                formatted += f"{i}. {title}\n\n"
                if content:
                    formatted += f"   {content}\n\n"
                if url:
                    formatted += f"   Source: {url}\n\n"
            
            return formatted.strip()
            
        except Exception as e:
            logger.error(f"Error formatting for LLM: {e}")
            return "Error formatting search results"
    
    async def extract_key_points(self, results: List[Dict[str, Any]]) -> List[str]:
        """Extract key points from results"""
        try:
            key_points = []
            
            for result in results:
                if "error" in result:
                    continue
                    
                content = result.get("content", "")
                if content:
                    # Simple extraction of sentences that seem important
                    sentences = re.split(r'[\.!?]+', content)
                    for sentence in sentences:
                        sentence = sentence.strip()
                        if len(sentence) > 20 and len(sentence) < 200:
                            key_points.append(sentence)
            
            return key_points[:10]  # Limit to 10 key points
            
        except Exception as e:
            logger.error(f"Error extracti   ng key points: {e}")
            return []