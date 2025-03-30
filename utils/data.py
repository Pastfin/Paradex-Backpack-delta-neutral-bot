import json
from pathlib import Path
from typing import Any, Dict

from src.config.paths import CONFIG_PATH, STATE_PATH


def _load_pairs(path: Path) -> list:
    try:
        data = load_json(path)
        return data.get("results", [])
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Failed to load pairs data from {path}") from exc


def _find_pair_by_key(key: str, value: str, path: str) -> dict:
    pairs = _load_pairs(Path(path))
    value_upper = value.upper()
    for pair in pairs:
        if pair.get(key, "").upper() == value_upper:
            return pair
    raise ValueError(f"{key.capitalize()} '{value}' not found in futures pairs")


def load_json(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def dump_json(path: Path, json_file: dict) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(json_file, file, ensure_ascii=False, indent=2)


def update_state(private_key: str, key: Any, value: Any) -> None:
    path = Path(STATE_PATH)
    state = load_json(path)

    if private_key not in state:
        state[private_key] = {}

    state[private_key][str(key)] = value
    dump_json(path, state)


def get_user_state() -> Dict[str, Any]:
    return load_json(Path(STATE_PATH))


USER_CONFIG: Dict[str, Any] = load_json(Path(CONFIG_PATH))
