import requests
from typing import List, Dict, Any, Optional
from datetime import datetime

from common.config import settings

from common.logger import logger


class SerpApiSearchTool:
    """SerpApi search tool for AI agents"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'SERPAPI_API_KEY', None)
        self.base_url = "https://serpapi.com/search"
        self.timeout = getattr(settings, 'SERPAPI_TIMEOUT', 10)
        self.max_results = getattr(settings, 'SERPAPI_MAX_RESULTS', 10)
        
        if self.api_key:
            self.available = True
        else:
            self.available = False
            logger.warning("SerpApi API key not configured")
    
    async def search(self, query: str, search_engine: str = "google", max_results: Optional[int] = None) -> List[Dict[str, Any]]:
        """Perform search using SerpApi"""
        if not self.available:
            return [{
                "error": "SerpApi Search not available",
                "source": "SerpApi",
                "timestamp": datetime.now().isoformat()
            }]
        
        try:
            max_results = max_results or self.max_results
            
            params = {
                "api_key": self.api_key,
                "q": query,
                "engine": search_engine,
                "num": min(max_results, 100),  # SerpApi limit
            }
            
            response = requests.get(
                self.base_url,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            # Handle different search engine results
            if search_engine == "google":
                if "organic_results" in data:
                    for item in data["organic_results"][:max_results]:
                        results.append({
                            "title": item.get("title", ""),
                            "url": item.get("link", ""),
                            "snippet": item.get("snippet", ""),
                            "source": "SerpApi (Google)",
                            "timestamp": datetime.now().isoformat()
                        })
            elif search_engine == "bing":
                if "organic_results" in data:
                    for item in data["organic_results"][:max_results]:
                        results.append({
                            "title": item.get("title", ""),
                            "url": item.get("link", ""),
                            "snippet": item.get("snippet", ""),
                            "source": "SerpApi (Bing)",
                            "timestamp": datetime.now().isoformat()
                        })
            
            logger.info(f"SerpApi {search_engine} search for '{query}' returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Error in SerpApi search: {e}")
            return [{
                "error": str(e),
                "source": "SerpApi",
                "timestamp": datetime.now().isoformat()
            }]