import time
import requests

from starknet_py.net.signer.stark_curve_signer import KeyPair
from starknet_py.net.full_node_client import FullNodeClient
from starknet_py.common import int_from_bytes
from starknet_py.net.account.account import Account

from src.config.constants import STARKNET_FULLNODE_RPC_URL, STARKNET_CHAIN_ID, PARADEX_HTTP_URL, logger
from utils.data import update_state, get_user_state
from utils.stark import build_auth_message, hex_to_int
from utils.proxy import convert_proxy_to_dict


def get_account(account_address: str, account_key: str) -> Account:
    client = FullNodeClient(node_url=STARKNET_FULLNODE_RPC_URL)
    key_pair = KeyPair.from_private_key(key=hex_to_int(account_key))
    chain = int_from_bytes(STARKNET_CHAIN_ID.encode("utf-8"))

    return Account(
        client=client,
        address=account_address,
        key_pair=key_pair,
        chain=chain,
    )


def get_jwt_token(account: Account, proxy_str: str) -> str:
    private_key = hex(account.signer.private_key)
    short_pk = private_key[:10]
    now = int(time.time())
    state = get_user_state().get(private_key, {})

    jwt = state.get("jwt")
    expiry = state.get("expiry", 0)

    if jwt and now < expiry:
        return jwt

    new_expiry = now + 24 * 60 * 60

    message_dict = build_auth_message(
        method="POST",
        path="/v1/auth",
        body="",
        timestamp=now,
        expiration=new_expiry,
    )

    sig = account.sign_message(message_dict)
    signature_str = f'["{hex(sig[0])}","{hex(sig[1])}"]'

    headers = {
        "PARADEX-STARKNET-ACCOUNT": hex(account.address),
        "PARADEX-STARKNET-SIGNATURE": signature_str,
        "PARADEX-TIMESTAMP": str(now),
        "PARADEX-SIGNATURE-EXPIRATION": str(new_expiry),
    }

    url = f"{PARADEX_HTTP_URL}/auth"
    response = requests.post(url, headers=headers, proxies=convert_proxy_to_dict(proxy_str))
    jwt = response.json().get("jwt_token", "")

    if response.status_code == 200 and jwt:
        update_state(private_key, "jwt", jwt)
        update_state(private_key, "expiry", now + 5 * 60)
        logger.info(f"[{short_pk}] JWT token retrieved successfully")
        return jwt

    raise ValueError(f"Failed to get JWT token: {response.status_code} - {response.text}")
