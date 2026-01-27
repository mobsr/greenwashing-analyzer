"""
Logging-Konfiguration für den Greenwashing Analyzer.

Stellt ein einheitliches Logging-System für das gesamte Projekt bereit.
"""

import logging
import sys
from typing import Optional


def setup_logger(
    name: str = "greenwashing_analyzer",
    level: int = logging.INFO,
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    Konfiguriert und returnt einen Logger für die Anwendung.
    
    Args:
        name: Name des Loggers (Standard: "greenwashing_analyzer")
        level: Logging-Level (Standard: logging.INFO)
        log_file: Optional Pfad zu Log-Datei für File-Output
    
    Returns:
        Konfigurierter Logger
    
    Example:
        >>> logger = setup_logger("analyzer", logging.DEBUG)
        >>> logger.info("Processing started")
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Verhindere doppelte Handler
    if logger.handlers:
        return logger
    
    # Formatter mit Timestamp
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File Handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


# Default Logger für einfache Verwendung
logger = setup_logger()
