from typing import List, Dict, Any
import re
from datetime import datetime

from common.logger import logger


class KnowledgeExtractor:
    """Extracts structured knowledge from search results"""
    
    def __init__(self):
        # Patterns for different types of information
        self.patterns = {
            "date": r'\b(?:\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})\b',
            "number": r'\b\d+(?:\.\d+)?\s*(?:million|billion|thousand|%)?\b',
            "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "phone": r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b',
            "url": r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?'
        }
    
    async def extract_knowledge(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract structured knowledge from search results"""
        try:
            knowledge = {
                "facts": [],
                "entities": {},
                "statistics": [],
                "dates": [],
                "contacts": [],
                "links": [],
                "summary": "",
                "extracted_at": datetime.now().isoformat()
            }
            
            all_content = ""
            for result in results:
                if "error" not in result:
                    content = result.get("content", result.get("snippet", ""))
                    all_content += content + " "
                    
                    # Extract specific knowledge from each result
                    await self._extract_from_result(result, knowledge)
            
            # Extract from combined content
            await self._extract_from_content(all_content, knowledge)
            
            # Generate summary
            knowledge["summary"] = await self._generate_summary(knowledge)
            
            return knowledge
            
        except Exception as e:
            logger.error(f"Error extracting knowledge: {e}")
            return {
                "error": str(e),
                "extracted_at": datetime.now().isoformat()
            }
    
    async def _extract_from_result(self, result: Dict[str, Any], knowledge: Dict[str, Any]):
        """Extract knowledge from individual result"""
        try:
            title = result.get("title", "")
            content = result.get("content", result.get("snippet", ""))
            url = result.get("url", "")
            
            # Extract links
            if url:
                knowledge["links"].append({
                    "url": url,
                    "title": title,
                    "domain": result.get("domain", "unknown")
                })
            
            # Extract dates from result
            dates = re.findall(self.patterns["date"], content)
            for date in dates:
                if date not in knowledge["dates"]:
                    knowledge["dates"].append(date)
            
        except Exception as e:
            logger.warning(f"Error extracting from result: {e}")
    
    async def _extract_from_content(self, content: str, knowledge: Dict[str, Any]):
        """Extract knowledge from combined content"""
        try:
            # Extract numbers/statistics
            numbers = re.findall(self.patterns["number"], content)
            knowledge["statistics"].extend([
                {"value": num, "context": self._get_context(content, num)}
                for num in numbers[:10]  # Limit to 10
            ])
            
            # Extract emails
            emails = re.findall(self.patterns["email"], content)
            knowledge["contacts"].extend([
                {"type": "email", "value": email}
                for email in set(emails)  # Remove duplicates
            ])
            
            # Extract phones
            phones = re.findall(self.patterns["phone"], content)
            knowledge["contacts"].extend([
                {"type": "phone", "value": phone}
                for phone in set(phones)  # Remove duplicates
            ])
            
            # Extract URLs
            urls = re.findall(self.patterns["url"], content)
            for url in urls:
                if url not in [link["url"] for link in knowledge["links"]]:
                    knowledge["links"].append({
                        "url": url,
                        "title": "Extracted URL",
                        "domain": url.split("/")[2] if len(url.split("/")) > 2 else "unknown"
                    })
            
        except Exception as e:
            logger.warning(f"Error extracting from content: {e}")
    
    def _get_context(self, text: str, target: str, context_length: int = 50) -> str:
        """Get context around a target string"""
        try:
            index = text.find(target)
            if index == -1:
                return ""
            
            start = max(0, index - context_length)
            end = min(len(text), index + len(target) + context_length)
            return text[start:end].strip()
        except:
            return ""
    
    async def _generate_summary(self, knowledge: Dict[str, Any]) -> str:
        """Generate a summary of extracted knowledge"""
        try:
            summary_parts = []
            
            if knowledge.get("facts"):
                summary_parts.append(f"Found {len(knowledge['facts'])} facts")
            
            if knowledge.get("statistics"):
                summary_parts.append(f"Extracted {len(knowledge['statistics'])} statistics")
            
            if knowledge.get("dates"):
                summary_parts.append(f"Identified {len(knowledge['dates'])} dates")
            
            if knowledge.get("contacts"):
                summary_parts.append(f"Discovered {len(knowledge['contacts'])} contact details")
            
            if knowledge.get("links"):
                summary_parts.append(f"Located {len(knowledge['links'])} relevant links")
            
            return "; ".join(summary_parts) if summary_parts else "No structured knowledge extracted"
            
        except Exception as e:
            logger.warning(f"Error generating summary: {e}")
            return "Error generating knowledge summary"
    
    async def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract named entities from text"""
        try:
            entities = {
                "organizations": [],
                "persons": [],
                "locations": [],
                "misc": []
            }
            
            # Simple pattern-based extraction
            # In a real implementation, you might use spaCy or similar
            
            # Extract potential organizations (capitalized phrases) 
            org_patterns = [
                r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b',  # Multi-word capitalized
                r'\b[A-Z]{2,}\b'  # All caps acronyms
            ]
            
            for pattern in org_patterns:
                matches = re.findall(pattern, text)
                entities["organizations"].extend(matches)
            
            # Remove duplicates and limit
            for key in entities:
                entities[key] = list(set(entities[key]))[:10]
            
            return entities
            
        except Exception as e:
            logger.warning(f"Error extracting entities: {e}")
            return {"organizations": [], "persons": [], "locations": [], "misc": []}