from typing import List, Dict, Any, Optional
from datetime import datetime

from .duckduckgo_search import DuckDuckGoSearchTool
from .google_search import GoogleSearchTool
from .bing_search import BingSearchTool
from .tavily_search import TavilySearchTool
from .serpapi_search import SerpApiSearchTool
from .result_processor import SearchResultProcessor
from .source_validator import SourceValidator

from common.config import settings

from common.logger import logger


class SearchCoordinator:
    """Coordinates multiple search engines for AI agents"""
    
    def __init__(self):
        # Initialize all search tools
        self.search_tools = {
            "duckduckgo": DuckDuckGoSearchTool(),
            "google": GoogleSearchTool(),
            "bing": BingSearchTool(),
            "tavily": TavilySearchTool(),
            "serpapi": SerpApiSearchTool()
        }
        
        # Initialize processors
        self.result_processor = SearchResultProcessor()
        self.source_validator = SourceValidator()
        
        # Get configuration
        self.default_engines = getattr(settings, 'DEFAULT_SEARCH_ENGINES', ['duckduckgo'])
        self.max_results_per_engine = getattr(settings, 'MAX_RESULTS_PER_ENGINE', 5)
        self.validate_sources = getattr(settings, 'VALIDATE_SEARCH_SOURCES', True)
        
        # Filter available engines
        self.available_engines = {
            name: tool for name, tool in self.search_tools.items() 
            if hasattr(tool, 'available') and tool.available
        }
        
        # Add engines that don't have availability check (like DuckDuckGo)
        for name, tool in self.search_tools.items():
            if name not in self.available_engines and not hasattr(tool, 'available'):
                self.available_engines[name] = tool
        
        logger.info(f"Search Coordinator initialized with {len(self.available_engines)} available engines")
    
    async def search(self, query: str, engines: Optional[List[str]] = None, 
                    max_results: Optional[int] = None) -> List[Dict[str, Any]]:
        """Coordinate search across multiple engines"""
        try:
            engines = engines or self.default_engines
            max_results = max_results or self.max_results_per_engine
            
            # Filter to only available engines
            active_engines = {
                name: tool for name, tool in self.available_engines.items() 
                if name in engines
            }
            
            if not active_engines:
                return [{
                    "error": "No search engines available",
                    "source": "SearchCoordinator",
                    "timestamp": datetime.now().isoformat()
                }]
            
            # Perform searches
            all_results = []
            for engine_name, engine_tool in active_engines.items():
                try:
                    results = await engine_tool.search(query, max_results)
                    all_results.extend(results)
                except Exception as e:
                    logger.error(f"Error searching with {engine_name}: {e}")
                    continue
            
            # Validate sources if enabled
            if self.validate_sources:
                validated_results = []
                for result in all_results:
                    if "error" not in result:
                        is_valid = await self.source_validator.validate(result)
                        if is_valid:
                            validated_results.append(result)
                    else:
                        validated_results.append(result)
                all_results = validated_results
            
            # Process and deduplicate results
            processed_results = await self.result_processor.process_results(all_results)
            
            # Sort by relevance/scoring
            processed_results = await self._sort_results(processed_results)
            
            logger.info(f"Search coordinator returned {len(processed_results)} results from {len(active_engines)} engines")
            return processed_results[:max_results * len(active_engines)]
            
        except Exception as e:
            logger.error(f"Error in search coordination: {e}")
            return [{
                "error": str(e),
                "source": "SearchCoordinator",
                "timestamp": datetime.now().isoformat()
            }]
    
    async def _sort_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort results by relevance"""
        try:
            # Sort by score if available, then by source priority
            source_priority = {
                "Tavily Answer": 10,
                "Tavily Search": 9,
                "Google": 8,
                "Bing": 7,
                "SerpApi": 6,
                "DuckDuckGo": 5
            }
            
            def sort_key(result):
                score = result.get("score", 0)
                source = result.get("source", "")
                priority = source_priority.get(source, 0)
                return (score, priority)
            
            return sorted(results, key=sort_key, reverse=True)
        except:
            return results
    
    def get_available_engines(self) -> List[str]:
        """Get list of available search engines"""
        return list(self.available_engines.keys())
    
    async def search_with_fallback(self, query: str, preferred_engines: List[str] = None,
                                  max_results: int = 5) -> List[Dict[str, Any]]:
        """Search with fallback engines if preferred ones fail"""
        preferred_engines = preferred_engines or self.default_engines
        fallback_engines = [e for e in self.available_engines.keys() if e not in preferred_engines]
        all_engines = preferred_engines + fallback_engines
        
        for engine in all_engines:
            try:
                results = await self.search(query, [engine], max_results)
                # Check if we got valid results (not just errors)
                valid_results = [r for r in results if "error" not in r]
                if valid_results:
                    return results
            except Exception as e:
                logger.warning(f"Fallback search with {engine} failed: {e}")
                continue
        
        return [{
            "error": "All search engines failed",
            "source": "SearchCoordinator",
            "timestamp": datetime.now().isoformat()
        }]