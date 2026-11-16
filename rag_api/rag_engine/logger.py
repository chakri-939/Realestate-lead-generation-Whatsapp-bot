"""
Structured Logger Utility — Bilingual WhatsApp RAG API
========================================================
Provides centralized, structured logging with rotating file handlers
and clean stderr console output for monitoring production operations.
"""

import os
import sys
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

def get_logger(name: str = "rag_api") -> logging.Logger:
    """
    Get or create a structured logger with both console (stderr) and rotating file handlers.
    
    Args:
        name: Name of the logger (module name or component name).
        
    Returns:
        logging.Logger: Configured logger instance.
    """
    logger = logging.getLogger(name)
    
    if logger.handlers:
        return logger
        
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, log_level, logging.INFO))
    
    # 1. Console Handler (stderr)
    console_handler = logging.StreamHandler(sys.stderr)
    console_formatter = logging.Formatter(
        fmt="%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # 2. Rotating File Handler (logs/rag_api.log)
    try:
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "rag_api.log"
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10_000_000,  # 10 MB per file
            backupCount=5,        # Keep up to 5 archive files
            encoding="utf-8"
        )
        file_formatter = logging.Formatter(
            fmt="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        console_handler.setLevel(logging.WARNING)
        logger.warning(f"Failed to initialize file logger: {e}")
        
    return logger
