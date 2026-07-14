from dataclasses import dataclass, field
import json
import os

import yaml


@dataclass
class Config:
    immich_url: str
    api_key: str
    refresh_times: list[str] = field(default_factory=lambda: ["07:30", "12:30"])
    cache_dir: str = "cache"
    state_file: str = "state/state.json"
    width: int = 800
    height: int = 480
    saturation: float = 0.5


def load_config(path: str) -> Config:
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return Config(**data)


def get_selected_album(state_file: str) -> str | None:
    try:
        with open(state_file) as f:
            return json.load(f).get("album_id")
    except FileNotFoundError:
        return None


def set_selected_album(state_file: str, album_id: str) -> None:
    os.makedirs(os.path.dirname(state_file) or ".", exist_ok=True)
    with open(state_file, "w") as f:
        json.dump({"album_id": album_id}, f)
