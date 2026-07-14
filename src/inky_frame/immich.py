from dataclasses import dataclass

import httpx


@dataclass
class Album:
    id: str
    name: str
    thumbnail_asset_id: str | None


@dataclass
class Asset:
    id: str
    type: str


class ImmichClient:
    def __init__(self, base_url: str, api_key: str, client: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = client or httpx.Client(timeout=30)

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self.api_key, "Accept": "application/json"}

    def list_albums(self) -> list[Album]:
        r = self._client.get(f"{self.base_url}/api/albums", headers=self._headers())
        r.raise_for_status()
        return [
            Album(
                id=a["id"],
                name=a["albumName"],
                thumbnail_asset_id=a.get("albumThumbnailAssetId"),
            )
            for a in r.json()
        ]

    def get_album_assets(self, album_id: str) -> list[Asset]:
        r = self._client.get(
            f"{self.base_url}/api/albums/{album_id}", headers=self._headers()
        )
        r.raise_for_status()
        return [
            Asset(id=a["id"], type=a.get("type", "IMAGE"))
            for a in r.json().get("assets", [])
        ]

    def download_asset(self, asset_id: str, size: str = "preview") -> bytes:
        r = self._client.get(
            f"{self.base_url}/api/assets/{asset_id}/thumbnail",
            params={"size": size},
            headers={"x-api-key": self.api_key},
        )
        r.raise_for_status()
        return r.content
