import sys

from loguru import logger


def private_log_record(record):
    # Provider exceptions can embed request text, signed URLs and credentials.
    if record['exception']:
        record['extra']['error_type'] = record['exception'].type.__name__
        record['exception'] = None
    return True

logger.remove()

logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{extra[correlation_id]}</cyan> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
    colorize=True,
    filter=private_log_record,
    diagnose=False,
    backtrace=False,
)

logger.add(
    "logs/voicescope_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="7 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[correlation_id]} | {name}:{function}:{line} - {message}",
    level="DEBUG",
    serialize=True,
    filter=private_log_record,
    diagnose=False,
    backtrace=False,
)

logger.configure(extra={"correlation_id": "-"})


def set_correlation_id(correlation_id: str):
    logger.configure(extra={"correlation_id": correlation_id})
