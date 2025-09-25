"""
Prompt templates for OASM Assistant agents
"""

from .nuclei_generation_prompts import NucleiGenerationPrompts
from .security_agent_prompts import SecurityAgentPrompts

# Import coordination prompts if they exist
try:
    from .coordination_prompts import CoordinationPrompts
    coordination_available = True
except ImportError:
    coordination_available = False

__all__ = [
    "NucleiGenerationPrompts",
    "SecurityAgentPrompts",
]

if coordination_available:
    __all__.append("CoordinationPrompts")