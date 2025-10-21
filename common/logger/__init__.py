from .logger import setup_logging
from loguru import logger

# Initialize logging configuration
setup_logging()

__all__ = ["logger", "setup_logging"]
