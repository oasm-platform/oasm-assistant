import requests
from typing import List, Dict, Any, Optional
from datetime import datetime

from common.config import settings

from common.logger import logger


class DuckDuckGoSearchTool:
    """DuckDuckGo search tool for AI agents"""
    
    def __init__(self):
        self.base_url = "https://api.duckduckgo.com/"
        self.timeout = getattr(settings, 'DUCKDUCKGO_TIMEOUT', 10)
        self.max_results = getattr(settings, 'DUCKDUCKGO_MAX_RESULTS', 10)
    
    async def search(self, query: str, max_results: Optional[int] = None) -> List[Dict[str, Any]]:
        """Perform search using DuckDuckGo API"""
        try:
            max_results = max_results or self.max_results
            
            params = {
                "q": query,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1"
            }
            
            response = requests.get(
                self.base_url, 
                params=params, 
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            # Parse related topics and results
            items = []
            if "RelatedTopics" in data:
                items.extend(data["RelatedTopics"])
            if "Results" in data:
                items.extend(data["Results"])
            
            for item in items[:max_results]:
                if "FirstURL" in item and "Text" in item:
                    results.append({
                        "title": self._clean_title(item.get("FirstURL", "")),
                        "url": item.get("FirstURL", ""),
                        "snippet": item.get("Text", ""),
                        "source": "DuckDuckGo",
                        "timestamp": datetime.now().isoformat()
                    })
            
            logger.info(f"DuckDuckGo search for '{query}' returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Error in DuckDuckGo search: {e}")
            return [{
                "error": str(e),
                "source": "DuckDuckGo",
                "timestamp": datetime.now().isoformat()
            }]
    
    def _clean_title(self, url: str) -> str:
        """Extract clean title from URL"""
        try:
            title = url.split("/")[-1].replace("_", " ").replace("-", " ")
            return title.capitalize()
        except:
            return "Untitled"