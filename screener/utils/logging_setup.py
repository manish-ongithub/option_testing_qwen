"""
Logging configuration for the screener.
"""

import logging
from logging.handlers import RotatingFileHandler

LOG_FILE = "screener.log"

# Create logger
logger = logging.getLogger("smart_options_screener")
logger.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter(
    "%(asctime)s %(levelname)s %(name)s - %(message)s", 
    "%Y-%m-%d %H:%M:%S"
)

# Console handler
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)

# File handler with rotation
fh = RotatingFileHandler(
    LOG_FILE, 
    maxBytes=5 * 1024 * 1024, 
    backupCount=3, 
    encoding="utf-8"
)
fh.setLevel(logging.INFO)
fh.setFormatter(formatter)
logger.addHandler(fh)


def setup_logger(name=None, level=logging.INFO):
    """
    Get or create a logger with the specified name.
    
    Args:
        name: Logger name. If None, returns the default screener logger.
        level: Logging level.
    
    Returns:
        Logger instance.
    """
    if name is None:
        return logger
    
    new_logger = logging.getLogger(name)
    new_logger.setLevel(level)
    
    if not new_logger.handlers:
        new_logger.addHandler(ch)
        new_logger.addHandler(fh)
    
    return new_logger

