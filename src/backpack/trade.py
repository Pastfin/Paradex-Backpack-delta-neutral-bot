import requests
from src.backpack.auth import get_auth_headers
from src.config.constants import logger
from utils.data import update_state
from utils.proxy import convert_proxy_to_dict
from src.config.constants import BACKPACK_HTTP_URL
from src.backpack.account import get_last_position_info


def open_position(
    api_key: str,
    ed25519_private_key_base64: str,
    side: str,
    symbol: str,
    quantity: str,
    proxy_str: str = None
):
    short_pk = ed25519_private_key_base64[:10]
    instruction = "orderExecute"

    order_payload = {
        "orderType": "Market",
        "symbol": symbol,
        "quantity": str(quantity),
        "side": side
    }

    headers = get_auth_headers(
        api_key=api_key,
        ed25519_private_key_base64=ed25519_private_key_base64,
        instruction=instruction,
        data=order_payload,
    )

    url = f"{BACKPACK_HTTP_URL}/order"
    response = requests.post(
        url,
        headers=headers,
        json=order_payload,
        proxies=convert_proxy_to_dict(proxy_str),
    )

    if response.status_code in [200, 202]:
        order = response.json()
        update_state(ed25519_private_key_base64, "last_order", order)
        logger.success(
            f"[{short_pk}] {order['side']} {order['quantity']} {order['symbol']} — "
            f"market order sent (id: {order.get('id', '')[:10]}...)"
        )
        return order

    logger.error(
        f"[{short_pk}] {order_payload['side']} {order_payload['quantity']} {order_payload['symbol']} — "
        f"failed: {response.text}"
    )
    raise ValueError("Backpack market order failed")

def close_last_position(
    api_key: str,
    ed25519_private_key_base64: str,
    proxy_str: str
):
    short_pk = ed25519_private_key_base64[:10]
    last_pos = get_last_position_info(api_key, ed25519_private_key_base64, proxy_str)

    if not last_pos or float(last_pos.get("netQuantity", 0)) == 0:
        logger.info(f"[{short_pk}] Backpack: all positions closed for this account")
        return

    symbol = last_pos["symbol"]
    net_qty = float(last_pos["netQuantity"])
    side = "Ask" if net_qty > 0 else "Bid"
    
    open_position(api_key, ed25519_private_key_base64, side, symbol, last_pos["netExposureQuantity"], proxy_str)
    update_state(ed25519_private_key_base64, "position", "closed")
    return
