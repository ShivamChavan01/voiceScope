import sys
import json
from loguru import logger

logger.remove()

logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{extra[correlation_id]}</cyan> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
    colorize=True
)

logger.add(
    "logs/voicescope_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="7 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[correlation_id]} | {name}:{function}:{line} - {message}",
    level="DEBUG",
    serialize=True
)

logger.configure(extra={"correlation_id": "-"})


def set_correlation_id(correlation_id: str):
    logger.configure(extra={"correlation_id": correlation_id})
