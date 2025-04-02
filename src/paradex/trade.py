import time
import requests
from decimal import Decimal
from starknet_py.net.account.account import Account

from utils.stark import build_trade_message
from utils.data import update_state
from src.paradex.auth import get_jwt_token
from src.config.constants import PARADEX_HTTP_URL, logger
from utils.proxy import convert_proxy_to_dict
from src.paradex.account import get_last_position_info


def open_position(account: Account, side: str, market: str, size: str, proxy_str):
    private_key = hex(account.signer.private_key)
    short_pk = private_key[:10]

    jwt = get_jwt_token(account, proxy_str)
    if not jwt:
        raise Exception("JWT token is empty, auth failed")

    timestamp = int(time.time())
    signature_timestamp_ms = timestamp * 1000

    order_payload = {
        "market": market,
        "type": "MARKET",
        "side": side.upper(),
        "size": str(size),
        "signature_timestamp": signature_timestamp_ms,
    }

    signable = build_trade_message(
        market=order_payload["market"],
        order_type=order_payload["type"],
        order_side=order_payload["side"],
        size=Decimal(order_payload["size"]),
        timestamp=order_payload["signature_timestamp"],
    )

    sig = account.sign_message(signable)
    signature_str = f'["{hex(sig[0])}","{hex(sig[1])}"]'
    order_payload["signature"] = signature_str

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {jwt}",
    }

    url = f"{PARADEX_HTTP_URL}/orders"
    response = requests.post(
        url,
        headers=headers,
        json=order_payload,
        proxies=convert_proxy_to_dict(proxy_str),
    )

    if response.status_code == 201:
        order = response.json()
        order_id = order["id"]
        order_info = get_order_info_by_id(account, order_id, proxy_str)

        cancel_reason = order_info.get("cancel_reason", "").strip()

        if cancel_reason:
            logger.error(
                f"[{short_pk}] {order_payload['side']} {order_payload['size']} {order_payload['market']} — "
                f"failed: {cancel_reason}"
            )
            raise ValueError("Error opening a new position")

        update_state(private_key, "last_order", order)
        logger.success(
            f"[{short_pk}] {order['side']} {order['size']} {order['market']} — "
            f"market order sent (id: {order['id'][:10]}...)"
        )
        return True

    logger.error(
        f"[{short_pk}] {order_payload['side']} {order_payload['size']} {order_payload['market']} — "
        f"failed: {response.text}"
    )
    raise ValueError("Error opening a new position")


def close_last_position(account: Account, proxy_str: str) -> None:
    pk = hex(account.signer.private_key)
    short_pk = pk[:10]

    pos = get_last_position_info(account, proxy_str)

    if not pos:
        logger.info(f"[{short_pk}] Paradex: all positions closed for this account")
        return

    market = pos["market"]
    size = abs(float(pos["size"]))
    side = pos["side"].upper()
    close_side = "SELL" if side == "LONG" else "BUY"

    open_position(account, close_side, market, str(size), proxy_str)
    update_state(pk, "position", "closed")

    return


def get_order_info_by_id(account: Account, order_id: str, proxy_str: str) -> dict:
    jwt = get_jwt_token(account, proxy_str)
    if not jwt:
        raise ValueError("JWT token is empty, auth failed")

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {jwt}",
    }

    url = f"{PARADEX_HTTP_URL}/orders/{order_id}"

    response = requests.get(url, headers=headers, proxies=convert_proxy_to_dict(proxy_str))

    return response.json()
