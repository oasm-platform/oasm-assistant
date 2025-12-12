import sys
from loguru import logger

def setup_logging():
    """Setup logging configuration using Loguru."""

    # Remove default handler
    logger.remove()

    # Add custom handler with formatting
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

    # Disable noisy third-party loggers by setting their level to WARNING
    logger.disable("urllib3")
    logger.disable("watchfiles")
    logger.disable("uvicorn.access")
