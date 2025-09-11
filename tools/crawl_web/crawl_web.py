import requests
from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString
from urllib.parse import urlparse
import re
from typing import Optional, List, Dict
import time
import unicodedata


class CrawlWeb:
    def __init__(self, user_agent: str = None, timeout: int = 10, max_retries: int = 3):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': user_agent or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Cache-Control': 'max-age=0'
        })
        self.timeout = timeout
        self.max_retries = max_retries

    def _is_visible_element(self, element) -> bool:
        """Check if element is visible"""
        if not element or not hasattr(element, 'parent'):
            return False
        
        # Skip non-visible tags
        if hasattr(element, 'parent') and element.parent and hasattr(element.parent, 'name'):
            if element.parent.name in ['style', 'script', 'head', 'title', 'meta', '[document]', 'noscript']:
                return False
        
        if isinstance(element, Comment):
            return False
        
        # Check CSS hidden properties
        if hasattr(element, 'get') and element.get('style'):
            style = element.get('style').lower()
            if any(hide in style.replace(' ', '') for hide in ['display:none', 'visibility:hidden']):
                return False
        
        # Check hidden classes
        if hasattr(element, 'get') and element.get('class'):
            classes = ' '.join(element.get('class')).lower()
            if any(hide in classes for hide in ['hidden', 'invisible', 'sr-only']):
                return False
        
        return True

    def _clean_text(self, text: str) -> str:
        """Clean text by removing extra whitespace"""
        if not text:
            return ""
        return re.sub(r'\s+', ' ', text).strip()

    def _get_heading_level(self, tag_name: str) -> int:
        """Get heading level from tag name"""
        if tag_name and tag_name[0] == 'h' and tag_name[1:].isdigit():
            return int(tag_name[1:])
        return 0

    def _extract_all_text(self, element) -> str:
        """Extract all text from element, including deeply nested text"""
        if not element:
            return ""
        
        texts = []
        
        # If it's a text node
        if isinstance(element, NavigableString):
            text = str(element).strip()
            if text and text not in ['', '\n', '\t']:
                texts.append(text)
        else:
            # For elements, get text from all children
            if hasattr(element, 'children'):
                for child in element.children:
                    if self._is_visible_element(child):
                        child_text = self._extract_all_text(child)
                        if child_text:
                            texts.append(child_text)
        
        return ' '.join(texts)

    def _process_element(self, element, current_level: int = 0) -> List[Dict]:
        """Process element and extract structured content"""
        content = []
        
        if not element or not hasattr(element, 'name'):
            return content
        
        # Skip invisible elements
        if not self._is_visible_element(element):
            return content

        # Process headings
        if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            heading_text = self._clean_text(self._extract_all_text(element))
            if heading_text:
                content.append({
                    'type': 'heading',
                    'level': self._get_heading_level(element.name),
                    'content': heading_text
                })

        # Process paragraphs and containers
        elif element.name in ['p', 'div', 'span', 'article', 'section', 'main', 'aside', 'blockquote', 'figcaption']:
            # Check if element contains headings
            child_headings = element.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            
            if child_headings:
                # If has headings, process each child separately
                for child in element.children:
                    if hasattr(child, 'name') and child.name:
                        content.extend(self._process_element(child, current_level))
            else:
                # Get text directly
                text = self._clean_text(self._extract_all_text(element))
                if text and len(text) > 2:  # Only meaningful text
                    content.append({
                        'type': 'paragraph',
                        'level': current_level,
                        'content': text
                    })

        # Process lists
        elif element.name in ['ul', 'ol']:
            list_items = []
            for li in element.find_all('li', recursive=False):
                item_text = self._clean_text(self._extract_all_text(li))
                if item_text:
                    list_items.append(f"• {item_text}")
            
            if list_items:
                content.append({
                    'type': 'list',
                    'level': current_level,
                    'content': '\n'.join(list_items)
                })

        # Process tables
        elif element.name == 'table':
            rows = []
            for tr in element.find_all('tr'):
                cells = []
                for td in tr.find_all(['th', 'td']):
                    cell_text = self._clean_text(self._extract_all_text(td))
                    cells.append(cell_text or "")
                
                if any(cells):
                    rows.append(' | '.join(cells))
            
            if rows:
                content.append({
                    'type': 'table',
                    'level': current_level,
                    'content': '\n'.join(rows)
                })

        # Process other text elements
        elif element.name in ['td', 'th', 'li', 'dt', 'dd', 'label', 'legend', 'caption']:
            text = self._clean_text(self._extract_all_text(element))
            if text and len(text) > 1:
                content.append({
                    'type': 'text',
                    'level': current_level,
                    'content': text
                })

        # Process forms and inputs (may contain important text)
        elif element.name in ['form', 'fieldset']:
            for child in element.children:
                if hasattr(child, 'name') and child.name:
                    content.extend(self._process_element(child, current_level))

        # Process input labels and values
        elif element.name == 'input':
            input_text = ""
            if element.get('value'):
                input_text = element.get('value')
            elif element.get('placeholder'):
                input_text = element.get('placeholder')
            
            if input_text:
                content.append({
                    'type': 'text',
                    'level': current_level,
                    'content': self._clean_text(input_text)
                })

        # Recursively process children for other elements
        else:
            if hasattr(element, 'children'):
                for child in element.children:
                    if hasattr(child, 'name') and child.name:
                        content.extend(self._process_element(child, current_level))

        return content

    def _structure_to_text(self, structured: List[Dict]) -> str:
        """Convert structured content to text"""
        if not structured:
            return ""
        
        result = []
        for item in structured:
            content_text = item.get('content', '').strip()
            if not content_text:
                continue
            
            if item['type'] == 'heading':
                result.append(f"\n{'#' * item['level']} {content_text}\n")
            elif item['type'] == 'paragraph':
                result.append(f"{content_text}\n")
            elif item['type'] == 'text':
                result.append(f"{content_text}")
            elif item['type'] == 'list':
                result.append(f"{content_text}\n")
            elif item['type'] == 'table':
                result.append(f"\n{content_text}\n")
        
        return '\n'.join(result)

    def _extract_metadata(self, soup) -> Dict[str, str]:
        """Extract metadata from page"""
        metadata = {}
        
        # Title
        if soup.title and soup.title.string:
            metadata['title'] = self._clean_text(soup.title.string)
        
        # Meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            metadata['description'] = self._clean_text(meta_desc.get('content'))
        
        # Meta keywords
        meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
        if meta_keywords and meta_keywords.get('content'):
            metadata['keywords'] = self._clean_text(meta_keywords.get('content'))
        
        # Open Graph tags
        og_title = soup.find('meta', attrs={'property': 'og:title'})
        if og_title and og_title.get('content'):
            metadata['og_title'] = self._clean_text(og_title.get('content'))
        
        og_description = soup.find('meta', attrs={'property': 'og:description'})
        if og_description and og_description.get('content'):
            metadata['og_description'] = self._clean_text(og_description.get('content'))
        
        return metadata

    def _clean_vietnamese_text(self, text: str) -> str:
        """Clean Vietnamese text"""
        if not text:
            return ""
        
        # Normalize unicode
        text = unicodedata.normalize('NFC', text)
        
        # Replace special characters
        replacements = {
            '&nbsp;': ' ', '&amp;': '&', '&lt;': '<', '&gt;': '>',
            '&quot;': '"', '&apos;': "'", '&copy;': '©', '&reg;': '®',
            '\u200b': '', '\u200c': '', '\u200d': '', '\ufeff': '',
            '\xa0': ' ', '\t': ' ', '\r\n': '\n', '\r': '\n'
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Clean whitespace
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # Max 2 empty lines
        text = re.sub(r' +', ' ', text)  # Multiple spaces to single
        text = text.strip()
        
        # Keep only printable characters and spaces
        return ''.join(c for c in text if c.isprintable() or c.isspace())

    def crawl(self, url: str, include_metadata: bool = True) -> Optional[str]:
        """Crawl URL and return full content"""
        # Validate URL
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            return None

        # Retry logic
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, timeout=self.timeout)
                
                if response.status_code >= 500:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                
                if response.status_code == 403:
                    return None
                
                response.raise_for_status()
                break
            
            except requests.RequestException:
                if attempt < self.max_retries - 1:  # Don't sleep on last attempt
                    time.sleep(2 ** attempt)
        else:
            return None

        # Handle encoding
        if response.encoding and response.encoding.lower() in ['iso-8859-1', 'windows-1252']:
            response.encoding = response.apparent_encoding or 'utf-8'

        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract metadata
        metadata = self._extract_metadata(soup) if include_metadata else {}

        # Remove unwanted elements
        unwanted_selectors = [
            'script', 'style', 'noscript', 'iframe', 'object', 'embed',
            'nav', 'footer', 'header', 'aside[class*="sidebar"]',
            '[class*="advertisement"]', '[class*="ads"]', '[id*="ad"]',
            '[class*="social"]', '[class*="share"]', '[class*="comment"]',
            '[class*="popup"]', '[class*="modal"]'
        ]
        
        for selector in unwanted_selectors:
            for element in soup.select(selector):
                element.decompose()

        # Find main content with multiple strategies
        main_content = None
        content_selectors = [
            'main',
            'article',
            '[role="main"]',
            '.main-content',
            '.content',
            '.post-content',
            '.entry-content',
            '#content',
            '#main-content',
            '.container .content',
            'body'
        ]
        
        for selector in content_selectors:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        if not main_content:
            main_content = soup.body or soup

        # Extract structured content
        structured = self._process_element(main_content)
        
        # Fallback: if no structured content, get all text
        if not structured:
            raw_text = self._extract_all_text(main_content)
            content = self._clean_vietnamese_text(raw_text)
        else:
            content = self._structure_to_text(structured)
            content = self._clean_vietnamese_text(content)

        # Format final output
        result_parts = []
        
        # Add metadata
        if metadata.get('title'):
            result_parts.append(f"Title: {metadata['title']}")
        
        result_parts.append(f"URL: {url}")
        
        if metadata.get('description'):
            result_parts.append(f"Description: {metadata['description']}")
        
        if metadata.get('keywords'):
            result_parts.append(f"Keywords: {metadata['keywords']}")
        
        # Add main content
        if content:
            result_parts.append(content)
        else:
            result_parts.append("No content extracted")

        final_result = '\n'.join(result_parts)
        
        return final_result