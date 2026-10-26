import logging
import re
import sys
from typing import Optional


class SensitiveDataFilter(logging.Filter):
    """
    Log filter that redacts API keys and prevents dumping full document bodies into logs.
    """
    # Regex to catch API key patterns (e.g. AIza..., Bearer ..., sk-...)
    KEY_PATTERN = re.compile(r"(AIza[0-9A-Za-z\-_]{20,}|Bearer\s+[A-Za-z0-9\-_\.]+|sk-[a-zA-Z0-9]{20,})")

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.KEY_PATTERN.sub("[REDACTED_SECRET]", record.msg)
        return True


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """
    Configure structured, privacy-preserving application logger.
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    logger = logging.getLogger("jd_analytics")
    logger.setLevel(numeric_level)
    
    # Avoid duplicate handlers if reloaded
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(numeric_level)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        handler.addFilter(SensitiveDataFilter())
        logger.addHandler(handler)
        logger.propagate = False

    return logger
