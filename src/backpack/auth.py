import base64
import time
import urllib.parse
from nacl.signing import SigningKey


def sign_request(
    instruction: str,
    timestamp: str,
    window: str,
    ed25519_private_key_base64: str,
    data: dict | None = None
) -> str:
    if data is not None:
        url_params = urllib.parse.urlencode(data)
        signing_string = f"instruction={instruction}&timestamp={timestamp}&window={window}&{url_params}"
    else:
        signing_string = f"instruction={instruction}&timestamp={timestamp}&window={window}"

    components = signing_string.split('&')
    key_value_pairs = [component.split('=') for component in components]
    sorted_pairs = sorted(key_value_pairs, key=lambda x: x[0])
    sorted_query_string = '&'.join(['='.join(pair) for pair in sorted_pairs])

    private_key_bytes = base64.b64decode(ed25519_private_key_base64)
    signing_key = SigningKey(private_key_bytes)
    signed_message = signing_key.sign(sorted_query_string.encode('utf-8'))
    signature = base64.b64encode(signed_message.signature).decode('utf-8')

    return signature


def get_auth_headers(
    api_key: str,
    ed25519_private_key_base64: str,
    instruction: str,
    data: dict | None = None
) -> dict:
    timestamp = str(int(time.time() * 1000))
    window = '10000'
    signature = sign_request(instruction, timestamp, window, ed25519_private_key_base64, data)

    headers = {
        'X-API-Key': api_key,
        'X-Timestamp': timestamp,
        'X-Window': window,
        'X-Signature': signature,
    }

    if data:
        headers['Content-Type'] = 'application/json'

    return headers
