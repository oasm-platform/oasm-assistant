"""
Development server with auto-reload functionality using watchfiles
"""
import sys
import asyncio
from pathlib import Path
from watchfiles import run_process

from common.logger import logger


def run_server():
    """Entry point for watchfiles to run the async server"""
    from app.main import serve
    asyncio.run(serve())


def main():
    """Start development server with auto-reload"""
    logger.info("Starting development server with auto-reload...")

    # Watch current directory (all subdirectories)
    watch_paths = [Path(".")]

    # Define ignore patterns
    def should_watch(_change, path: str) -> bool:
        """Filter function to determine which files to watch"""
        # Only watch Python files
        if not path.endswith('.py'):
            return False

        # Ignore specific files (to avoid reloading heavy models)
        ignore_files = [
            'llm_manager.py',
            'embedding_manager.py'
        ]

        # Check if filename matches any ignore file
        filename = Path(path).name
        if filename in ignore_files:
            return False

        # Ignore common directories
        ignore_patterns = [
            'venv', '.venv', 'env', '.env',
            '__pycache__', '.git', '.pytest_cache',
            'node_modules', '.idea', '.vscode',
            'logs', '.egg-info', 'dist', 'build'
        ]

        # Check if path contains any ignore pattern
        path_parts = path.replace('\\', '/').split('/')
        for pattern in ignore_patterns:
            if any(pattern in part for part in path_parts):
                return False

        return True

    try:
        # Run process with auto-reload on .py file changes
        run_process(
            *watch_paths,
            target=run_server,
            watch_filter=should_watch,
            grace_period=1.0,  # Wait 1 second after file change before reloading
            debug=False
        )
    except KeyboardInterrupt:
        logger.info("\nShutting down development server...")
        sys.exit(0)


if __name__ == "__main__":
    main()
