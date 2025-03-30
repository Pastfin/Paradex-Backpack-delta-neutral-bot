import threading
import time
import random
from typing import Dict, Any
import pandas as pd

from src.config.constants import logger
from src.config.paths import DATA_DIR
from utils.data import USER_CONFIG
from src.paradex.auth import get_account
from src.paradex.trade import close_last_position as close_last_position_paradex
from src.backpack.trade import close_last_position as close_last_position_backpack
from src.position_manager import TradingManager


class TradingController:
    def __init__(self) -> None:
        self.config: Dict[str, Any] = USER_CONFIG
        self.retries = self.config["retries"]
        self.threads = {}

    def run_trading_managers(self) -> None:
        df_paradex = pd.read_excel(f"{DATA_DIR}/accounts_paradex.xlsx")
        df_paradex = df_paradex[df_paradex["is_active"] == True].sample(frac=1).reset_index(drop=True)

        df_backpack = pd.read_excel(f"{DATA_DIR}/accounts_backpack.xlsx")
        df_backpack = df_backpack[df_backpack["is_active"] == True].sample(frac=1).reset_index(drop=True)

        n_workers = min(len(df_paradex), len(df_backpack))
        max_retries = self.retries

        logger.info(f"Starting {n_workers} trading threads")

        def thread_worker(paradex_data: pd.Series, backpack_data: pd.Series, stop_event: threading.Event) -> None:
            attempts = 0
            thread_name = threading.current_thread().name
            thread_id = thread_name.split('-')[1].split()[0]
            short_pk_paradex = paradex_data["private_key"][:10]
            short_pk_backpack = backpack_data["api_secret"][:10]

            paradex_address = paradex_data["address"]
            paradex_private_key = paradex_data["private_key"]
            paradex_proxy = paradex_data["proxy"]

            backpack_api_key = backpack_data["api_key"]
            backpack_api_secret = backpack_data["api_secret"]
            backpack_proxy = backpack_data["proxy"]

            manager = TradingManager(
                paradex_address=paradex_address,
                paradex_private_key=paradex_private_key,
                paradex_proxy=paradex_proxy,
                backpack_api_key=backpack_api_key,
                backpack_api_secret=backpack_api_secret,
                backpack_proxy=backpack_proxy,
                stop_event=stop_event
            )

            while attempts < max_retries and not stop_event.is_set():
                try:
                    manager.start_trading()
                    break
                except Exception as exc:
                    attempts += 1
                    logger.error(f"[{thread_id}] [{short_pk_paradex}] [{short_pk_backpack}] Error (Attempt {attempts}/{max_retries}): {exc}")
                    
                    try:
                        manager.close_positions()
                    except Exception as close_exc:
                        logger.error(f"[{thread_id}] [{short_pk_paradex}] [{short_pk_backpack}] Close failed: {close_exc}")

                    if attempts < max_retries:
                        delay = random.randint(5, 10)
                        logger.info(f"[{thread_id}] [{short_pk_paradex}] [{short_pk_backpack}] Retrying after {delay}s")
                        time.sleep(delay)
                    else:
                        logger.error(f"[{thread_id}] [{short_pk_paradex}] [{short_pk_backpack}] Failed after {max_retries} attempts")

        for n in range(n_workers):
            paradex_data = df_paradex.iloc[n]
            backpack_data = df_backpack.iloc[n]
            stop_event = threading.Event()
            
            t = threading.Thread(target=thread_worker, args=(paradex_data, backpack_data, stop_event))
            thread_id = f"Thread-{n}"
            self.threads[thread_id] = {"thread": t, "stop_event": stop_event}
            logger.info(f"[{n}] Starting thread with Paradex {paradex_data['private_key'][:10]} and Backpack {backpack_data['api_secret'][:10]}")
            t.start()

            delay_cfg = self.config["delay_between_starting_new_thread_sec"]
            delay = random.randint(delay_cfg["min"], delay_cfg["max"])
            time.sleep(delay)

        for thread_id, thread_info in self.threads.items():
            thread_info["thread"].join()

        logger.info("All threads finished")

    def stop_thread(self, thread_id: str) -> None:
        if thread_id in self.threads:
            thread_num = thread_id.split('-')[1]
            logger.info(f"[{thread_num}] Stopping thread")
            self.threads[thread_id]["stop_event"].set()
            self.threads[thread_id]["thread"].join()
            del self.threads[thread_id]
        else:
            logger.warning(f"[{thread_id}] Thread not found")

    def close_all_positions(self) -> None:
        delay_cfg = self.config["delay_between_starting_new_thread_sec"]

        df_paradex = pd.read_excel(f"{DATA_DIR}/accounts_paradex.xlsx")
        df_paradex = df_paradex[df_paradex["is_active"] == True].sample(frac=1).reset_index(drop=True)

        for i in range(df_paradex.shape[0]):
            data = df_paradex.iloc[i]
            account = get_account(data["address"], data["private_key"])
            short_pk_paradex = hex(account.signer.private_key)[:10]
            success = False

            for attempt in range(1, self.retries + 1):
                try:
                    close_last_position_paradex(account, data["proxy"])
                    success = True
                    logger.info(f"[{short_pk_paradex}] Paradex closed on attempt {attempt}")
                    break
                except Exception as exc:
                    logger.warning(f"[{short_pk_paradex}] Paradex close failed on attempt {attempt}: {exc}")
                    time.sleep(1)

            if not success:
                logger.error(f"[{short_pk_paradex}] Failed to close Paradex after {self.retries} attempts")
                
            delay = random.randint(delay_cfg["min"], delay_cfg["max"])
            logger.info(f"Waiting {delay} sec..")
            time.sleep(delay)

        df_backpack = pd.read_excel(f"{DATA_DIR}/accounts_backpack.xlsx")
        df_backpack = df_backpack[df_backpack["is_active"] == True].sample(frac=1).reset_index(drop=True)

        for i in range(df_backpack.shape[0]):
            data = df_backpack.iloc[i]
            short_pk_backpack = str(data["api_secret"])[:10]
            success = False

            for attempt in range(1, self.retries + 1):
                try:
                    close_last_position_backpack(data["api_key"], data["api_secret"], data["proxy"])
                    success = True
                    logger.info(f"[{short_pk_backpack}] Backpack closed on attempt {attempt}")
                    break
                except Exception as exc:
                    logger.warning(f"[{short_pk_backpack}] Backpack close failed on attempt {attempt}: {exc}")
                    time.sleep(1)

            if not success:
                logger.error(f"[{short_pk_backpack}] Failed to close Backpack after {self.retries} attempts")
                
            delay = random.randint(delay_cfg["min"], delay_cfg["max"])
            time.sleep(delay)