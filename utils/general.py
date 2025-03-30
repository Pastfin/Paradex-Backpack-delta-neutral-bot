from src.config.constants import logger
from utils.data import USER_CONFIG

def _retry_request(func, *args, **kwargs):
    retries = USER_CONFIG["retries"]
    last_exception = None

    for attempt in range(1, retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            logger.warning(f"Attempt {attempt}/{retries} failed for {func.__name__}: {e}")

    raise RuntimeError(f"All {retries} attempts failed for {func.__name__}") from last_exception
