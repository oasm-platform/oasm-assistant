from .settings import Settings
from .logger import setup_logging

setup_logging()
settings = Settings()

__doc__ = "Settings for the application"

__all__ = ["settings"]