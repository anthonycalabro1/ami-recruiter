"""
Logging configuration for AMI Recruiter.
Sets up file + console logging with daily log rotation.
"""

import logging
import os
from datetime import datetime


def setup_logging(log_dir=None):
    """Configure logging with file and console handlers.

    Returns the configured logger instance.
    Log files are written to logs/ directory with daily filenames.
    """
    if log_dir is None:
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, f"ami_recruiter_{datetime.now().strftime('%Y%m%d')}.log")

    logger = logging.getLogger('ami_recruiter')

    # Prevent duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # File handler — detailed with timestamps
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))

    # Console handler — info level, clean output
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('%(message)s'))

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger
