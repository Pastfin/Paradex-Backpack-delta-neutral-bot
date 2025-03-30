import json
from pathlib import Path
import requests

from src.config.paths import FUTURE_PAIRS_BACKPACK_PATH, DATA_DIR
from src.config.constants import BACKPACK_HTTP_URL, logger
from utils.data import load_json, _find_pair_by_key, _load_pairs


def get_pair_data(token: str) -> dict:
    return _find_pair_by_key("base_currency", token, FUTURE_PAIRS_BACKPACK_PATH)


def get_pair_data_by_symbol(symbol: str) -> dict:
    return _find_pair_by_key("symbol", symbol, FUTURE_PAIRS_BACKPACK_PATH)


def get_pair_data(token: str) -> dict:
    return _find_pair_by_key("baseSymbol", token, FUTURE_PAIRS_BACKPACK_PATH)

def get_pair_data_by_symbol(symbol: str) -> dict:
    return _find_pair_by_key("symbol", symbol, FUTURE_PAIRS_BACKPACK_PATH)

def update_markets():
    logger.info("Backpack futures pairs information update has started")
    response = requests.get(f"{BACKPACK_HTTP_URL}/markets")
    print(response.json())
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        logger.error(f"Error fetching current futures pairs: {response.text}")
        raise exc

    data = response.json()
    filtered_results = []

    for item in data:
        if item.get("marketType") == "PERP":
            filters = item.get("filters", {})
            price_filter = filters.get("price", {})
            quantity_filter = filters.get("quantity", {})

            item.update({
                "tickSize": price_filter.get("tickSize"),
                "stepSize": quantity_filter.get("stepSize"),
                "minQuantity": quantity_filter.get("min")
            })
            filtered_results.append(item)

    file_path = Path(DATA_DIR) / "pairs_backpack.json"
    with open(file_path, "w", encoding="utf-8") as file:
        json.dump({"results": filtered_results}, file, ensure_ascii=False, indent=2)

    logger.success("Information on Backpack futures pairs has been updated")
