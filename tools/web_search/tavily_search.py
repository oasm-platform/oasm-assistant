import requests
from typing import List, Dict, Any, Optional
from datetime import datetime

from common.config import settings

from common.logger import logger


class TavilySearchTool:
    """Tavily search tool optimized for AI agents"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'TAVILY_API_KEY', None)
        self.base_url = "https://api.tavily.com/search"
        self.timeout = getattr(settings, 'TAVILY_TIMEOUT', 10)
        self.max_results = getattr(settings, 'TAVILY_MAX_RESULTS', 5)
        
        if self.api_key:
            self.available = True
        else:
            self.available = False
            logger.warning("Tavily API key not configured")
    
    async def search(self, query: str, max_results: Optional[int] = None) -> List[Dict[str, Any]]:
        """Perform search using Tavily API"""
        if not self.available:
            return [{
                "error": "Tavily Search not available",
                "source": "Tavily",
                "timestamp": datetime.now().isoformat()
            }]
        
        try:
            max_results = max_results or self.max_results
            
            payload = {
                "api_key": self.api_key,
                "query": query,
                "search_depth": "basic",
                "include_answer": True,
                "include_images": False,
                "include_raw_content": False,
                "max_results": min(max_results, 10),  # Tavily API limit
                "exclude_domains": []
            }
            
            response = requests.post(
                self.base_url,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            # Add answer if available
            if "answer" in data and data["answer"]:
                results.append({
                    "title": "Direct Answer",
                    "content": data["answer"],
                    "source": "Tavily Answer",
                    "timestamp": datetime.now().isoformat()
                })
            
            # Add search results
            if "results" in data:
                for item in data["results"]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "content": item.get("content", ""),
                        "score": item.get("score", 0),
                        "source": "Tavily Search",
                        "timestamp": datetime.now().isoformat()
                    })
            
            logger.info(f"Tavily search for '{query}' returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Error in Tavily search: {e}")
            return [{
                "error": str(e),
                "source": "Tavily",
                "timestamp": datetime.now().isoformat()
            }]