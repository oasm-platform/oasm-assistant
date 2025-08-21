from typing import Any, Dict

class ToolBase():
    """Base class for all tools"""
    
    name: str
    description: str
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    def run(self, **kwargs) -> Any:
        raise NotImplementedError("The run method must be implemented by subclasses")
    