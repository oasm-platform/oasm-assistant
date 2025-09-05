from typing import List, Dict, Any, Optional
from datetime import datetime

from common.config import settings
from common.logger import logger
import requests


class BingSearchTool:
    """Bing search tool for AI agents"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'BING_SEARCH_API_KEY', None)
        self.base_url = "https://api.bing.microsoft.com/v7.0/search"
        self.timeout = getattr(settings, 'BING_TIMEOUT', 10)
        self.max_results = getattr(settings, 'BING_MAX_RESULTS', 10)
        
        if self.api_key:
            self.headers = {"Ocp-Apim-Subscription-Key": self.api_key}
            self.available = True
        else:
            self.available = False
            logger.warning("Bing Search API key not configured")
    
    async def search(self, query: str, max_results: Optional[int] = None) -> List[Dict[str, Any]]:
        """Perform search using Bing Search API"""
        if not self.available:
            return [{
                "error": "Bing Search not available",
                "source": "Bing",
                "timestamp": datetime.now().isoformat()
            }]
        
        try:
            max_results = max_results or self.max_results
            
            params = {
                "q": query,
                "count": min(max_results, 50),  # Bing API limit
                "offset": 0,
                "mkt": "en-US"
            }
            
            response = requests.get(
                self.base_url,
                headers=self.headers,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            if "webPages" in data and "value" in data["webPages"]:
                for item in data["webPages"]["value"]:
                    results.append({
                        "title": item.get("name", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("snippet", ""),
                        "source": "Bing",
                        "timestamp": datetime.now().isoformat()
                    })
            
            logger.info(f"Bing search for '{query}' returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Error in Bing search: {e}")
            return [{
                "error": str(e),
                "source": "Bing",
                "timestamp": datetime.now().isoformat()
            }]