from src.config.paths import LOGS_DIR
from loguru import logger
import os
import sys

from utils.data import USER_CONFIG

logger.remove()
logger.add(sys.stdout, level=USER_CONFIG["debug_level"])
logger.add(os.path.join(LOGS_DIR, "app.log"), level=USER_CONFIG["debug_level"], encoding="utf-8", enqueue=True)


def get_logger():
    return logger
