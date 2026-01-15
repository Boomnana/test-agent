import sys
from loguru import logger
from app.core.config import settings

# Configure Loguru
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)
logger.add("logs/app.log", rotation="500 MB", level="DEBUG")

def get_logger(name: str):
    return logger.bind(name=name)
