import httpx
import respx
from inky_frame.immich import ImmichClient, Album, Asset

BASE = "http://immich.test:2283"


@respx.mock
def test_list_albums_parses_and_sends_key():
    route = respx.get(f"{BASE}/api/albums").mock(
        return_value=httpx.Response(200, json=[
            {"id": "a1", "albumName": "Urlaub", "albumThumbnailAssetId": "t1"},
            {"id": "a2", "albumName": "Familie", "albumThumbnailAssetId": None},
        ])
    )
    albums = ImmichClient(BASE, "secret").list_albums()
    assert albums == [
        Album(id="a1", name="Urlaub", thumbnail_asset_id="t1"),
        Album(id="a2", name="Familie", thumbnail_asset_id=None),
    ]
    assert route.calls.last.request.headers["x-api-key"] == "secret"


@respx.mock
def test_get_album_assets_filters_shape():
    respx.get(f"{BASE}/api/albums/a1").mock(
        return_value=httpx.Response(200, json={
            "id": "a1",
            "assets": [
                {"id": "i1", "type": "IMAGE"},
                {"id": "v1", "type": "VIDEO"},
            ],
        })
    )
    assets = ImmichClient(BASE, "k").get_album_assets("a1")
    assert assets == [Asset(id="i1", type="IMAGE"), Asset(id="v1", type="VIDEO")]


@respx.mock
def test_download_asset_returns_bytes_with_size_param():
    route = respx.get(f"{BASE}/api/assets/i1/thumbnail").mock(
        return_value=httpx.Response(200, content=b"JPEGDATA")
    )
    data = ImmichClient(BASE, "k").download_asset("i1", size="preview")
    assert data == b"JPEGDATA"
    assert route.calls.last.request.url.params["size"] == "preview"
