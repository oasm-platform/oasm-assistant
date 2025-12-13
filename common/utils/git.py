"""
Git operations utilities with robust retry and error handling
"""
import os
import shutil
import time
import git
from typing import Optional
from common.logger import logger

def clone_or_pull_repo(
    repo_url: str, 
    clone_dir: str, 
    max_retries: int = 3,
    retry_delay: int = 5
) -> bool:
    """
    Clone or pull a repository with built-in retry logic and HTTP/2 handling.
    
    Args:
        repo_url: URL of the git repository
        clone_dir: Local directory path
        max_retries: Number of retry attempts
        retry_delay: Seconds between retries
        
    Returns:
        bool: True if successful, False otherwise
    """
    for attempt in range(max_retries):
        try:
            if os.path.exists(clone_dir):
                # Pull latest changes
                logger.info(f"Pulling latest changes from {repo_url} (attempt {attempt + 1}/{max_retries})")
                try:
                    repo = git.Repo(clone_dir)
                except git.exc.InvalidGitRepositoryError:
                    # Handle case where dir exists but is not a valid repo
                    logger.warning(f"Directory {clone_dir} exists but is not a valid git repo. Re-cloning.")
                    shutil.rmtree(clone_dir, ignore_errors=True)
                    continue

                # Configure Git settings for reliability
                _configure_git_repo(repo)
                
                origin = repo.remotes.origin
                origin.pull(verbose=True)
            else:
                # Clone repository
                logger.info(f"Cloning repository from {repo_url} (attempt {attempt + 1}/{max_retries})")
                repo = git.Repo.clone_from(repo_url, clone_dir, depth=1)
                
                # Configure Git settings
                _configure_git_repo(repo)

            return True
            
        except git.exc.GitCommandError as e:
            logger.warning(f"Git command failed (attempt {attempt + 1}/{max_retries}): {e}")
            
            # Check if it's an HTTP/2 related error or other transient network issue
            err_str = str(e)
            if any(x in err_str for x in ['HTTP/2 stream', 'RPC failed', 'early EOF']):
                if attempt < max_retries - 1:
                    logger.info(f"Transient error detected, retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    
                    # Try basic recovery if repo exists
                    if os.path.exists(clone_dir):
                        _attempt_repo_recovery(clone_dir)
                    continue
            
            # For other errors, we might still want to retry or just fail
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            return False
            
        except Exception as e:
            logger.error(f"Unexpected error during git operation: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            return False
            
    return False

def _configure_git_repo(repo: git.Repo):
    """Apply safe configuration to handle large files/connections"""
    with repo.config_writer() as git_config:
        git_config.set_value('http', 'postBuffer', '524288000')  # 500MB
        git_config.set_value('http', 'version', 'HTTP/1.1')      # Force HTTP/1.1
        git_config.set_value('http', 'lowSpeedLimit', '1000')
        git_config.set_value('http', 'lowSpeedTime', '60')

def _attempt_repo_recovery(repo_dir: str):
    """Try to reset a corrupted repo or delete it for fresh clone"""
    try:
        repo = git.Repo(repo_dir)
        repo.git.reset('--hard', 'HEAD')
        repo.git.clean('-fdx')
    except Exception as e:
        logger.warning(f"Failed to recover repo, deleting for fresh start: {e}")
        shutil.rmtree(repo_dir, ignore_errors=True)
