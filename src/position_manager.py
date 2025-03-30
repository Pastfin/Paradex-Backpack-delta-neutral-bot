import random
import time
from typing import Dict, Any
import pandas as pd
import threading

from src.config.constants import logger
from src.config.paths import DATA_DIR
from src.paradex.auth import get_account
from src.paradex.trade import open_position as open_position_paradex
from src.paradex.trade import close_last_position as close_last_position_paradex
from src.paradex.account import get_last_position_info as get_last_position_info_paradex
from src.paradex.account import get_balance as get_balance_paradex
from src.paradex.market import get_pair_data as get_pair_data_paradex
from src.paradex.market import get_pair_data_by_symbol
from src.paradex.market import get_pair_price
from utils.data import update_state, get_user_state, USER_CONFIG
from utils.calc import calc_size
from src.backpack.trade import open_position as open_position_backpack
from src.backpack.trade import close_last_position as close_last_position_backpack
from src.backpack.account import get_last_position_info as get_last_position_info_backpack
from src.backpack.account import get_balance as get_balance_backpack
from src.backpack.market import get_pair_data as get_pair_data_backpack


class TradingManager:
    def __init__(
        self,
        paradex_address: str,
        paradex_private_key: str,
        paradex_proxy: str,
        backpack_api_key: str,
        backpack_api_secret: str,
        backpack_proxy: str,
        stop_event: threading.Event = None
    ) -> None:
        self.paradex_creds: Dict[str, str] = {
            "address": paradex_address,
            "private_key": paradex_private_key,
            "proxy": paradex_proxy
        }
        self.backpack_creds: Dict[str, str] = {
            "api_key": backpack_api_key,
            "api_secret": backpack_api_secret,
            "proxy": backpack_proxy
        }
        self.config: Dict[str, Any] = USER_CONFIG
        self.df_accounts: pd.DataFrame = pd.DataFrame({})
        self.retries = self.config["retries"]
        self.stop_event = stop_event or threading.Event()
        thread_name = threading.current_thread().name
        self.thread_id = thread_name.split('-')[1].split()[0]  # Берем только число после "Thread-"
        self.short_pk_paradex = self.get_short_pk(self.paradex_creds["private_key"])
        self.short_pk_backpack = self.get_short_pk(self.backpack_creds["api_secret"])

    def get_random_from_range(self, key: str) -> int:
        if key in self.config and isinstance(self.config[key], dict):
            minimum = self.config[key].get("min", 0)
            maximum = self.config[key].get("max", 0)
            return random.randint(minimum, maximum)
        raise ValueError(f"Invalid or missing config range for '{key}'")

    def select_market_data(self, df_markets: pd.DataFrame) -> Dict[str, Any]:
        max_attempts = len(df_markets)
        for _ in range(max_attempts):
            idx = random.randint(0, len(df_markets) - 1)
            market_row = df_markets.iloc[idx]
            try:
                pair_data = get_pair_data_by_symbol(market_row["symbol"])
                if pair_data is not None:
                    logger.debug(f"[{self.thread_id}] [{self.short_pk_paradex}] [{self.short_pk_backpack}] Selected market: {market_row['symbol']}")
                    return pair_data
            except Exception as exc:
                logger.warning(f"[{self.thread_id}] [{self.short_pk_paradex}] [{self.short_pk_backpack}] Error selecting market {market_row['symbol']}: {exc}")
        logger.error(f"[{self.thread_id}] [{self.short_pk_paradex}] [{self.short_pk_backpack}] Failed to find market after {max_attempts} attempts")
        raise ValueError("All markets unavailable or non-existent")

    def opposite_side(self, paradex_side: str) -> str:
        return "Ask" if paradex_side == "BUY" else "Bid"

    def opposite_order_side(self, paradex_side: str) -> str:
        return "SELL" if paradex_side == "BUY" else "BUY"

    def get_short_pk(self, pk: str) -> str:
        return pk[:10]

    def safe_get(self, data, key, default=0):
        try:
            return data.get(key, default)
        except Exception:
            return default

    def start_trading(self) -> None:
        while not self.stop_event.is_set():
            order_value = self.get_random_from_range("order_value_usd")
            order_duration = self.get_random_from_range("order_duration_min")

            df_markets = pd.read_excel(f"{DATA_DIR}/active_pairs.xlsx")
            pair_data = self.select_market_data(df_markets)
            token = pair_data["base_currency"]

            max_order_value = self.get_max_order_value()
            order_value = min(order_value, max_order_value)

            current_price = get_pair_price(token)
            size = calc_size(order_value, token, current_price)

            logger.info(
                f"[{self.thread_id}] [{self.short_pk_paradex}] [{self.short_pk_backpack}] Starting trade: {token}, ${order_value}, {order_duration} min, Size: {size}"
            )

            try:
                self.open_positions(size, token)
            except RuntimeError as exc:
                logger.error(f"[{self.thread_id}] [{self.short_pk_paradex}] [{self.short_pk_backpack}] Trade aborted: {exc}")
                break

            logger.info(f"[{self.thread_id}] [{self.short_pk_paradex}] [{self.short_pk_backpack}] Positions opened, waiting {order_duration} min")
            self.monitor_ltv(order_duration)

            if self.stop_event.is_set():
                logger.info(f"[{self.thread_id}] [{self.short_pk_paradex}] [{self.short_pk_backpack}] Thread stopped")
                break

            self.close_positions()

            delay_between_cycles = self.get_random_from_range("delay_between_trading_cycles_min")
            logger.info(f"[{self.thread_id}] [{self.short_pk_paradex}] [{self.short_pk_backpack}] Waiting {delay_between_cycles} min for next cycle")
            time.sleep(delay_between_cycles * 60)

    def get_max_order_value(self) -> float:
        paradex_account = get_account(self.paradex_creds["address"], self.paradex_creds["private_key"])
        paradex_balance_json = get_balance_paradex(paradex_account, self.paradex_creds["proxy"])

        paradex_balance = 0.0
        for token_entry in paradex_balance_json.get("results", []):
            if token_entry["token"] == "USDC":
                paradex_balance = float(token_entry["size"])

        backpack_balance_json = get_balance_backpack(
            self.backpack_creds["api_key"], self.backpack_creds["api_secret"], self.backpack_creds["proxy"]
        )
        backpack_balance = float(backpack_balance_json["USDC"]["available"])

        min_balance = min(paradex_balance, backpack_balance)
        max_order_value = USER_CONFIG["max_leverage"] * min_balance
        return max_order_value

    def open_positions(self, size: str, token: str) -> None:
        paradex_account = get_account(self.paradex_creds["address"], self.paradex_creds["private_key"])
        pk_paradex = hex(paradex_account.signer.private_key)

        paradex_side = random.choice(["BUY", "SELL"])
        backpack_side = self.opposite_side(paradex_side)

        pair_data_pd = get_pair_data_paradex(token)
        pair_data_bp = get_pair_data_backpack(token)
        market_paradex = pair_data_pd["symbol"]
        market_backpack = pair_data_bp["symbol"]

        logger.info(
            f"[{self.thread_id}] [{self.short_pk_paradex}] [{self.short_pk_backpack}] Opening: Paradex {paradex_side} ({market_paradex}), Backpack {backpack_side} ({market_backpack}), Size: {size}"
        )

        paradex_success = False
        for attempt in range(1, self.retries + 1):
            try:
                open_position_paradex(
                    paradex_account, paradex_side, market_paradex, size, self.paradex_creds["proxy"]
                )
                paradex_success = True
                logger.info(f"[{self.thread_id}] [{self.short_pk_paradex}] Paradex {paradex_side} opened on attempt {attempt}")
                break
            except Exception as exc:
                logger.warning(f"[{self.thread_id}] [{self.short_pk_paradex}] Paradex {paradex_side} failed on attempt {attempt}: {exc}")
                time.sleep(1)

        backpack_success = False
        for attempt in range(1, self.retries + 1):
            try:
                open_position_backpack(
                    self.backpack_creds["api_key"], self.backpack_creds["api_secret"],
                    backpack_side, market_backpack, size, self.backpack_creds["proxy"]
                )
                backpack_success = True
                logger.info(f"[{self.thread_id}] [{self.short_pk_backpack}] Backpack {backpack_side} opened on attempt {attempt}")
                break
            except Exception as exc:
                logger.warning(f"[{self.thread_id}] [{self.short_pk_backpack}] Backpack {backpack_side} failed on attempt {attempt}: {exc}")
                time.sleep(1)

        if not (paradex_success or backpack_success):
            logger.error(f"[{self.thread_id}] [{self.short_pk_paradex}] [{self.short_pk_backpack}] Failed to open positions")
            self.close_positions()
            raise RuntimeError("Unable to open positions")

        delay = random.randint(5, 10)
        time.sleep(delay)

        last_pd = get_last_position_info_paradex(paradex_account, self.paradex_creds["proxy"])
        last_bp = get_last_position_info_backpack(
            self.backpack_creds["api_key"], self.backpack_creds["api_secret"], self.backpack_creds["proxy"]
        )

        if not (last_pd or last_bp):
            logger.error(f"[{self.thread_id}] [{self.short_pk_paradex}] [{self.short_pk_backpack}] Failed to get position info")
            self.close_positions()
            raise RuntimeError("Unable to retrieve position info")

        liq_pd = self.safe_get(last_pd, "liquidation_price", 0)
        update_state(pk_paradex, "position", "active")
        update_state(pk_paradex, "order_side", paradex_side)
        update_state(pk_paradex, "order_liq_price", liq_pd)

        liq_bp = self.safe_get(last_bp, "estLiquidationPrice", 0)
        update_state(self.backpack_creds["api_secret"], "position", "active")
        update_state(self.backpack_creds["api_secret"], "order_side", backpack_side)
        update_state(self.backpack_creds["api_secret"], "order_liq_price", liq_bp)

    def close_positions(self) -> None:
        paradex_account = get_account(self.paradex_creds["address"], self.paradex_creds["private_key"])

        logger.info(f"[{self.thread_id}] [{self.short_pk_paradex}] [{self.short_pk_backpack}] Closing positions")

        paradex_success = False
        for attempt in range(1, self.retries + 1):
            try:
                close_last_position_paradex(paradex_account, self.paradex_creds["proxy"])
                paradex_success = True
                logger.debug(f"[{self.thread_id}] [{self.short_pk_paradex}] Paradex closed on attempt {attempt}")
                break
            except Exception as exc:
                logger.warning(f"[{self.thread_id}] [{self.short_pk_paradex}] Paradex close failed on attempt {attempt}: {exc}")
                time.sleep(1)

        backpack_success = False
        for attempt in range(1, self.retries + 1):
            try:
                close_last_position_backpack(
                    self.backpack_creds["api_key"], self.backpack_creds["api_secret"], self.backpack_creds["proxy"]
                )
                backpack_success = True
                logger.debug(f"[{self.thread_id}] [{self.short_pk_backpack}] Backpack closed on attempt {attempt}")
                break
            except Exception as exc:
                logger.warning(f"[{self.thread_id}] [{self.short_pk_backpack}] Backpack close failed on attempt {attempt}: {exc}")
                time.sleep(1)

        if not (paradex_success or backpack_success):
            logger.error(f"[{self.thread_id}] [{self.short_pk_paradex}] [{self.short_pk_backpack}] Failed to close positions")
            raise RuntimeError("Unable to close positions")

    def monitor_ltv(self, duration_min: int) -> None:
        logger.info(f"[{self.thread_id}] [{self.short_pk_paradex}] [{self.short_pk_backpack}] Monitoring LTV for {duration_min} min")
        end_time = time.time() + duration_min * 60
        logger.debug(f"[{self.thread_id}] [{self.short_pk_paradex}] [{self.short_pk_backpack}] duration_min={duration_min}, end_time={end_time}")

        while time.time() < end_time and not self.stop_event.is_set():
            try:
                state: Dict[str, Dict[str, Any]] = get_user_state()
                paradex_key = self.paradex_creds["private_key"]
                backpack_key = self.backpack_creds["api_secret"]

                paradex_info = state.get(paradex_key, {})
                backpack_info = state.get(backpack_key, {})
                current_price_pd = 0
                logger.debug(f"[{self.thread_id}] [{self.short_pk_paradex}] [{self.short_pk_backpack}] State received. Paradex: {paradex_info}, Backpack: {backpack_info}")

                if paradex_info.get("position") == "active":
                    logger.debug(f"[{self.thread_id}] [{self.short_pk_paradex}] Paradex position active, calculating LTV")
                    side_pd = paradex_info.get("order_side", "").upper()
                    liq_pd = paradex_info.get("order_liq_price", 0.0)
                    last_order_pd = paradex_info.get("last_order", {})
                    market_pd = last_order_pd.get("market", "")
                    logger.debug(f"[{self.thread_id}] [{self.short_pk_paradex}] Side: {side_pd}, LiqPrice: {liq_pd}, Market: {market_pd}")

                    if market_pd:
                        base_token_pd = market_pd.split("-")[0]
                        current_price_pd = get_pair_price(base_token_pd)
                        logger.debug(f"[{self.thread_id}] [{self.short_pk_paradex}] Current price for {base_token_pd}: {current_price_pd}")

                        if current_price_pd and liq_pd:
                            if side_pd == "SELL":
                                ltv_pd = current_price_pd / float(liq_pd)
                            elif side_pd == "BUY":
                                ltv_pd = float(liq_pd) / current_price_pd
                            else:
                                ltv_pd = 0

                            ltv_pd *= 100
                            ltv_pd_rounded = round(ltv_pd, 1)

                            logger.debug(
                                f"[{self.thread_id}] [{self.short_pk_paradex}] Paradex LTV={ltv_pd_rounded}% | "
                                f"Side={side_pd} | Market={market_pd} | CurrentPrice={current_price_pd} | LiqPrice={liq_pd}"
                            )

                            if ltv_pd > self.config["max_position_ltv"]:
                                logger.info(
                                    f"[{self.thread_id}] [{self.short_pk_paradex}] Paradex LTV={ltv_pd_rounded}% exceeds max ({self.config['max_position_ltv']}%), Side={side_pd}, Market={market_pd}"
                                )
                                logger.warning(f"[{self.thread_id}] [{self.short_pk_paradex}] Stopping due to high LTV")
                                self.close_positions()
                                self.stop_event.set()
                                return

                if backpack_info.get("position") == "active":
                    logger.debug(f"[{self.thread_id}] [{self.short_pk_backpack}] Backpack position active, calculating LTV")
                    side_bp = backpack_info.get("order_side", "").upper()
                    liq_bp = backpack_info.get("order_liq_price", 0.0)
                    logger.debug(f"[{self.thread_id}] [{self.short_pk_backpack}] Side: {side_bp}, LiqPrice: {liq_bp}")

                    if isinstance(liq_bp, str):
                        if liq_bp.strip() == '':
                            liq_bp = 0.0
                        else:
                            try:
                                liq_bp = float(liq_bp)
                            except ValueError:
                                liq_bp = 0.0
                        logger.debug(f"[{self.thread_id}] [{self.short_pk_backpack}] Converted LiqPrice to float: {liq_bp}")

                    if current_price_pd and liq_bp:
                        if side_bp == "ASK":
                            ltv_bp = current_price_pd / liq_bp
                        elif side_bp == "BID":
                            ltv_bp = liq_bp / current_price_pd
                        else:
                            ltv_bp = 0

                        ltv_bp *= 100
                        ltv_bp_rounded = round(ltv_bp, 1)

                        logger.debug(
                            f"[{self.thread_id}] [{self.short_pk_backpack}] Backpack LTV={ltv_bp_rounded}% | "
                            f"Side={side_bp} | Market={market_pd} | CurrentPrice={current_price_pd} | LiqPrice={liq_bp}"
                        )

                        if ltv_bp > self.config["max_position_ltv"]:
                            logger.info(
                                f"[{self.thread_id}] [{self.short_pk_backpack}] Backpack LTV={ltv_bp_rounded}% exceeds max ({self.config['max_position_ltv']}%), Side={side_bp}, Market={market_pd}"
                            )
                            logger.info(f"[{self.thread_id}] [{self.short_pk_backpack}] Stopping due to high LTV")
                            self.close_positions()
                            self.stop_event.set()
                            return

            except Exception as exc:
                logger.warning(f"[{self.thread_id}] [{self.short_pk_paradex}] [{self.short_pk_backpack}] LTV monitoring error: {exc}")

            wait_time = self.get_random_from_range("ltv_checks_sec")
            logger.debug(f"[{self.thread_id}] [{self.short_pk_paradex}] [{self.short_pk_backpack}] Next LTV check in {wait_time}s")
            time.sleep(wait_time)

        logger.info(f"[{self.thread_id}] [{self.short_pk_paradex}] [{self.short_pk_backpack}] LTV monitoring finished")