"""
Simple logger module - alias to structured_logger for backward compatibility.
Use structured_logger directly for new code.
"""
from app.utils.structured_logger import logger, setup_logger, StructuredLogger

__all__ = ["logger", "setup_logger", "StructuredLogger"]

