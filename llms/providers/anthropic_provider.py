"""
Anthropic Claude models
"""

import anthropic
from typing import List, Dict, Tuple
from .base_provider import OnlineProvider

class AnthropicProvider(OnlineProvider):
    """Anthropic Claude API provider implementation."""
    
    def __init__(self, api_key: str, model_version: str, **kwargs):
        """Initialize Anthropic Claude provider.
        
        Args:
            api_key: Anthropic API key
            model_version: Claude model version (e.g., 'claude-3-opus-20240229')
            **kwargs: Additional configuration
        """
        self.client = None
        super().__init__(model_version, api_key, **kwargs)
    
    def _initialize(self, **kwargs) -> None:
        """Initialize Anthropic client."""
        try:
            self.client = anthropic.Anthropic(api_key=self.api_key)
            # Test connection - this will validate the API key
        except Exception as e:
            raise ConnectionError(f"Failed to initialize Anthropic client: {e}")
    
    def _convert_messages(self, prompt: List[Dict[str, str]]) -> Tuple[str, List[Dict[str, str]]]:
        """Convert prompt messages to Anthropic format.
        
        Returns:
            Tuple of (system_message, formatted_messages)
        """
        system_message = ""
        messages = []
        
        role_mapping = {
            "human": "user",
            "ai": "assistant", 
            "claude": "assistant"
        }
        
        for msg in prompt:
            role = msg["role"].lower()
            content = msg["content"]
            
            if role == "system":
                system_message = content
            elif role in ["user", "assistant"]:
                messages.append({"role": role, "content": content})
            elif role in role_mapping:
                mapped_role = role_mapping[role]
                messages.append({"role": mapped_role, "content": content})
            else:
                # Default unknown roles to user
                messages.append({"role": "user", "content": content})
        
        return system_message, messages
    
    def _generate_raw_content(self, prompt: List[Dict[str, str]]) -> str:
        """Generate content using Anthropic Claude API."""
        try:
            system_message, messages = self._convert_messages(prompt)
            
            request_params = {
                "model": self.model_version,
                "messages": messages,
                "max_tokens": min(self.max_tokens, 4096),  # Anthropic limit
            }
            
            if system_message:
                request_params["system"] = system_message
            
            response = self.client.messages.create(**request_params)
            
            if response.content and len(response.content) > 0:
                content = response.content[0]
                if hasattr(content, 'text'):
                    return content.text
                else:
                    return str(content)
            else:
                return ""
                
        except anthropic.APIError as e:
            raise RuntimeError(f"Anthropic API error: {e}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error during content generation: {e}")