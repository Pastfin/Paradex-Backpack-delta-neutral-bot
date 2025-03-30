import time
import json
from decimal import Decimal
from typing import Dict, Union

from starknet_py.common import int_from_bytes

from src.config.constants import STARKNET_CHAIN_ID


def hex_to_int(val: str) -> int:
    return int(val, 16)


def build_auth_message(
    method: str,
    path: str,
    body: Union[dict, str],
    timestamp: int = None,
    expiration: int = None
) -> Dict:
    now = int(time.time())
    timestamp = timestamp or now
    expiration = expiration or now + 24 * 60 * 60

    body_str = body if isinstance(body, str) else json.dumps(body, separators=(",", ":"))

    return {
        "message": {
            "method": method,
            "path": path,
            "body": body_str,
            "timestamp": timestamp,
            "expiration": expiration,
        },
        "domain": {
            "name": "Paradex",
            "chainId": hex(int_from_bytes(STARKNET_CHAIN_ID.encode("utf-8"))),
            "version": "1"
        },
        "primaryType": "Request",
        "types": {
            "StarkNetDomain": [
                {"name": "name", "type": "felt"},
                {"name": "chainId", "type": "felt"},
                {"name": "version", "type": "felt"},
            ],
            "Request": [
                {"name": "method", "type": "felt"},
                {"name": "path", "type": "felt"},
                {"name": "body", "type": "felt"},
                {"name": "timestamp", "type": "felt"},
                {"name": "expiration", "type": "felt"},
            ],
        },
    }


def build_trade_message(
    market: str,
    order_type: str,
    order_side: str,
    size: Decimal,
    timestamp: int
) -> Dict:
    chain_id = int_from_bytes(STARKNET_CHAIN_ID.encode("utf-8"))

    return {
        "domain": {
            "name": "Paradex",
            "version": "1",
            "chainId": hex(chain_id)
        },
        "primaryType": "Order",
        "types": {
            "StarkNetDomain": [
                {"name": "name", "type": "felt"},
                {"name": "chainId", "type": "felt"},
                {"name": "version", "type": "felt"}
            ],
            "Order": [
                {"name": "timestamp", "type": "felt"},
                {"name": "market", "type": "felt"},
                {"name": "side", "type": "felt"},
                {"name": "orderType", "type": "felt"},
                {"name": "size", "type": "felt"},
                {"name": "price", "type": "felt"},
            ]
        },
        "message": {
            "timestamp": str(timestamp),
            "market": market,
            "side": "1" if order_side.lower() == "buy" else "2",
            "orderType": order_type,
            "size": chain_size(size),
            "price": "0"
        }
    }


def chain_size(size: Decimal) -> str:
    return str(int(size.scaleb(8)))
