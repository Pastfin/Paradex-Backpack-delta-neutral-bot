import requests
from typing import List, Dict, Any, Optional
from decimal import Decimal

from src.backpack.auth import get_auth_headers
from src.config.constants import BACKPACK_HTTP_URL
from utils.proxy import convert_proxy_to_dict
from utils.general import _retry_request

def get_balance(api_key: str, api_secret: str, proxy: str):
    url = f"{BACKPACK_HTTP_URL}/capital"

    headers = get_auth_headers(
        api_key=api_key,
        ed25519_private_key_base64=api_secret,
        instruction="balanceQuery"
    )

    response = requests.get(url, headers=headers, proxies=convert_proxy_to_dict(proxy))
    response.raise_for_status()
    balances = response.json()

    lend_positions = get_lend_positions(api_key, api_secret, proxy)

    for position in lend_positions:
        symbol = position.get("symbol")
        quantity = float(position.get("netQuantity", "0"))
        if quantity == 0:
            continue
        if symbol in balances:
            current = float(balances[symbol].get("available", "0"))
            balances[symbol]["available"] = str(current + quantity)
            balances[symbol]["lent"] = str(quantity)
        else:
            balances[symbol] = {
                "available": str(quantity),
                "locked": "0",
                "staked": "0",
                "lent": str(quantity)
            }

    return balances


def get_lend_positions(api_key: str, api_secret: str, proxy: str = None):
    url = f"{BACKPACK_HTTP_URL}/borrowLend/positions"
    headers = get_auth_headers(api_key, api_secret, instruction="borrowLendPositionQuery")

    response = requests.get(url, headers=headers, proxies=convert_proxy_to_dict(proxy), timeout=10)
    response.raise_for_status()
    return response.json()


def get_open_positions(api_key: str, api_secret: str, proxy: str):
    url = f"{BACKPACK_HTTP_URL}/position"

    headers = get_auth_headers(
        api_key=api_key,
        ed25519_private_key_base64=api_secret,
        instruction="positionQuery"
    )

    response = requests.get(url, headers=headers, proxies=convert_proxy_to_dict(proxy))
    response.raise_for_status()
    return response.json()


def get_last_position_info(api_key: str, api_secret: str, proxy: str) -> Optional[Dict[str, Any]]:
    position_data = _retry_request(get_open_positions, api_key, api_secret, proxy)

    first_open_position = next(
        (p for p in position_data if Decimal(p.get("netQuantity", "0")) != 0),
        None
    )

    return first_open_position

