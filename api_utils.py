"""
API utility functions for AMI Recruiter.
Provides retry logic with exponential backoff for Claude API calls.
"""

import time
import logging

logger = logging.getLogger('ami_recruiter')


def retry_api_call(func, max_retries=3, base_delay=2.0, max_delay=60.0):
    """Execute a function with exponential backoff retry.

    Args:
        func: Callable that makes the API request
        max_retries: Maximum number of retry attempts (default 3)
        base_delay: Initial delay in seconds between retries (default 2.0)
        max_delay: Maximum delay cap in seconds (default 60.0)

    Returns:
        The return value of func()

    Raises:
        The last exception if all retries are exhausted
    """
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries:
                logger.error(f"API call failed after {max_retries + 1} attempts: {e}")
                raise
            delay = min(base_delay * (2 ** attempt), max_delay)
            logger.warning(
                f"API call failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                f"Retrying in {delay:.0f}s..."
            )
            time.sleep(delay)
