import warnings
import pandas as pd
from decimal import Decimal
import time
import random

from src.config.constants import logger
from src.config.paths import DATA_DIR
from src.paradex.auth import get_account
from src.paradex.account import get_balance as get_balance_paradex, get_open_positions as get_open_positions_paradex
from src.backpack.account import get_balance as get_balance_backpack, get_open_positions as get_open_positions_backpack
from utils.general import _retry_request

warnings.filterwarnings("ignore")


def update_accounts_info():
    update_paradex_accounts_info()
    update_backpack_accounts_info()

def update_paradex_accounts_info():
    df = pd.read_excel(DATA_DIR + "/accounts_paradex.xlsx")

    for x in range(df.shape[0]):
        data = df.iloc[x]

        if not data["is_active"]:
            continue

        account = get_account(data["address"], data["private_key"])

        balance_data = _retry_request(get_balance_paradex, account, data["proxy"])
        for token_entry in balance_data.get("results", []):
            token = token_entry["token"]
            size = float(token_entry["size"])
            df.loc[x, token] = size

        position_data = _retry_request(get_open_positions_paradex, account, data["proxy"])
        positions = position_data.get("results", [])

        for pos in positions:
            if pos["status"].upper() == "CLOSED":
                continue

            side = pos.get("side", "")
            try:
                liq_price = float(pos.get("liquidation_price", 0))
            except Exception:
                liq_price = 0
            unrealized_pnl = Decimal(pos.get("unrealized_pnl", "0"))
            avg_price = Decimal(pos.get("average_entry_price", "0"))
            size = abs(Decimal(pos.get("size", "0")))

            if size > 0:
                direction = -1 if side.upper() == "SHORT" else 1
                mark_price = float((unrealized_pnl / (size * direction)) + avg_price)
            else:
                mark_price = 0.0

            df.loc[x, "position_market"] = str(pos.get("market", ""))
            df.loc[x, "position_side"] = str(side)
            df.loc[x, "position_size"] = float(size)
            df.loc[x, "position_avg_price"] = float(avg_price)
            df.loc[x, "position_mark_price"] = mark_price
            df.loc[x, "position_liq_price"] = liq_price
            df.loc[x, "position_pnl"] = float(unrealized_pnl)

            if liq_price > 0 and mark_price > 0:
                if side.upper() == "SHORT":
                    ltv = mark_price / liq_price
                elif side.upper() == "LONG":
                    ltv = liq_price / mark_price
                else:
                    ltv = None
            else:
                ltv = None

            df.loc[x, "position_ltv"] = ltv
            break
        else:
            df.loc[x, "position_market"] = ""
            df.loc[x, "position_side"] = ""
            df.loc[x, "position_size"] = None
            df.loc[x, "position_avg_price"] = None
            df.loc[x, "position_mark_price"] = None
            df.loc[x, "position_liq_price"] = None
            df.loc[x, "position_pnl"] = None
            df.loc[x, "position_ltv"] = None

        time.sleep(random.randint(3, 5))

    df.to_excel(DATA_DIR + "/accounts_paradex.xlsx", index=False)
    logger.success(f"Paradex: updated balances and open positions for {len(df)} accounts.")


def update_backpack_accounts_info():
    df = pd.read_excel(DATA_DIR + "/accounts_backpack.xlsx")

    for x in range(df.shape[0]):
        data = df.iloc[x]

        if not data["is_active"]:
            continue

        balance_data = _retry_request(get_balance_backpack, data["api_key"], data["api_secret"], data["proxy"])
        df.loc[x, "USDC"] = float(balance_data["USDC"]["available"])

        positions_data = _retry_request(get_open_positions_backpack, data["api_key"], data["api_secret"], data["proxy"])
        
        first_open_position = next(
            (p for p in positions_data if Decimal(p.get("netQuantity", "0")) != 0),
            None
        )

        if first_open_position:
            pos = first_open_position
            side = "SHORT" if Decimal(pos["netQuantity"]) < 0 else "LONG"
            size = abs(Decimal(pos["netQuantity"]))
            avg_price = Decimal(pos["entryPrice"])
            mark_price = Decimal(pos["markPrice"])
            unrealized_pnl = Decimal(pos["pnlUnrealized"])
            liq_price = float(pos.get("estLiquidationPrice", 0))

            df.loc[x, "position_market"] = pos.get("symbol", "")
            df.loc[x, "position_side"] = side
            df.loc[x, "position_size"] = float(size)
            df.loc[x, "position_avg_price"] = float(avg_price)
            df.loc[x, "position_mark_price"] = float(mark_price)
            df.loc[x, "position_liq_price"] = liq_price
            df.loc[x, "position_pnl"] = float(unrealized_pnl)

            if liq_price > 0 and mark_price > 0:
                if side == "SHORT":
                    ltv = float(mark_price) / liq_price
                elif side == "LONG":
                    ltv = liq_price / float(mark_price)
                else:
                    ltv = None
            else:
                ltv = None

            df.loc[x, "position_ltv"] = ltv
        else:
            df.loc[x, "position_market"] = ""
            df.loc[x, "position_side"] = ""
            df.loc[x, "position_size"] = None
            df.loc[x, "position_avg_price"] = None
            df.loc[x, "position_mark_price"] = None
            df.loc[x, "position_liq_price"] = None
            df.loc[x, "position_pnl"] = None
            df.loc[x, "position_ltv"] = None

        time.sleep(random.randint(3, 5))


    df.to_excel(DATA_DIR + "/accounts_backpack.xlsx", index=False)
    logger.success(f"Backpack: updated balances and open positions for {len(df)} accounts.")
