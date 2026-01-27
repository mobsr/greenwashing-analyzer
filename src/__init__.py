"""
Greenwashing Analyzer Package.

Dieses Package enthält die Kernfunktionalität zur Analyse von Greenwashing
in Nachhaltigkeitsberichten mittels KI.
"""

from .analyzer import GreenwashingAnalyzer
from .loader import ReportLoader
from .logger_config import setup_logger

__version__ = "0.1.0"
__all__ = ["GreenwashingAnalyzer", "ReportLoader", "setup_logger"]
