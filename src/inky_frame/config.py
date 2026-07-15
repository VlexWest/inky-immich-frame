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
    # What fills the space around a photo that does not match the panel's
    # shape: "white" (a mat, like a real frame) or "blur" (a blurred copy of
    # the photo). Nothing is ever cropped either way.
    background: str = "white"


def load_config(path: str) -> Config:
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return Config(**data)


DEFAULT_LANGUAGE = "de"


def _read_state(state_file: str) -> dict:
    try:
        with open(state_file) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _update_state(state_file: str, **values) -> None:
    """Merge values into the state file. The album and the language live in the
    same file, so a plain overwrite would drop whichever wasn't being set."""
    state = _read_state(state_file)
    state.update(values)
    os.makedirs(os.path.dirname(state_file) or ".", exist_ok=True)
    with open(state_file, "w") as f:
        json.dump(state, f)


def get_selected_album(state_file: str) -> str | None:
    return _read_state(state_file).get("album_id")


def set_selected_album(state_file: str, album_id: str) -> None:
    # Choosing an album is also how the reader resumes the rotation, so it
    # releases whatever photo was pinned.
    _update_state(state_file, album_id=album_id, pinned_asset_id=None)


def get_pinned_asset(state_file: str) -> str | None:
    return _read_state(state_file).get("pinned_asset_id")


def set_pinned_asset(state_file: str, asset_id: str) -> None:
    _update_state(state_file, pinned_asset_id=asset_id)


def get_language(state_file: str) -> str:
    return _read_state(state_file).get("language", DEFAULT_LANGUAGE)


def set_language(state_file: str, language: str) -> None:
    _update_state(state_file, language=language)
