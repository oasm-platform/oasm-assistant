from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

from common.config import settings

from common.logger import logger


class GoogleSearchTool:
    """Google search tool for AI agents"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'GOOGLE_SEARCH_API_KEY', None)
        self.search_engine_id = getattr(settings, 'GOOGLE_SEARCH_ENGINE_ID', None)
        self.max_results = getattr(settings, 'GOOGLE_MAX_RESULTS', 10)
        
        if GOOGLE_API_AVAILABLE and self.api_key and self.search_engine_id:
            try:
                self.service = build("customsearch", "v1", developerKey=self.api_key)
                self.available = True
            except Exception as e:
                logger.error(f"Failed to initialize Google Search: {e}")
                self.available = False
        else:
            self.available = False
            if not GOOGLE_API_AVAILABLE:
                logger.warning("Google API client not installed")
            elif not self.api_key:
                logger.warning("Google Search API key not configured")
            elif not self.search_engine_id:
                logger.warning("Google Search Engine ID not configured")
    
    async def search(self, query: str, max_results: Optional[int] = None) -> List[Dict[str, Any]]:
        """Perform search using Google Custom Search API"""
        if not self.available:
            return [{
                "error": "Google Search not available",
                "source": "Google",
                "timestamp": datetime.now().isoformat()
            }]
        
        try:
            max_results = max_results or self.max_results
            
            result = self.service.cse().list(
                q=query,
                cx=self.search_engine_id,
                num=min(max_results, 10)  # Google API limit
            ).execute()
            
            results = []
            if "items" in result:
                for item in result["items"]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("link", ""),
                        "snippet": item.get("snippet", ""),
                        "source": "Google",
                        "timestamp": datetime.now().isoformat()
                    })
            
            logger.info(f"Google search for '{query}' returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Error in Google search: {e}")
            return [{
                "error": str(e),
                "source": "Google",
                "timestamp": datetime.now().isoformat()
            }]