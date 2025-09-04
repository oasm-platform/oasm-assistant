from pathlib import Path
import logging
import logging.config
import sys

def setup_logging():
    """Setup logging configuration."""
    logging_config_path = Path(__file__).parent.parent / "logging.ini"
    
    if logging_config_path.exists():
        logging.config.fileConfig(str(logging_config_path), disable_existing_loggers=False)
    else:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )
    
    # Disable noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.ERROR)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)