from typing import Callable

from flask import Flask, Response, redirect, render_template_string, request, url_for

from .config import Config, get_selected_album, set_selected_album
from .immich import ImmichClient

PAGE = """<!doctype html><html><head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bilderrahmen</title>
<style>
 body{font-family:system-ui,sans-serif;margin:0;padding:1rem;background:#faf9f7;color:#222}
 h1{font-size:1.3rem;margin:0 0 1rem}
 .grid{display:grid;grid-template-columns:1fr 1fr;gap:.8rem}
 .card{border:3px solid transparent;border-radius:14px;overflow:hidden;background:#fff;
   box-shadow:0 1px 3px rgba(0,0,0,.08)}
 .card.sel{border-color:#3aa675}
 .card img{width:100%;height:120px;object-fit:cover;display:block;background:#eee}
 .card .name{padding:.5rem;font-size:.95rem}
 form.pick{margin:0}
 form.pick button{all:unset;display:block;cursor:pointer;width:100%}
 form.now{margin-top:1.2rem}
 form.now button{font-size:1.05rem;padding:.8rem 1rem;border:0;border-radius:12px;
   background:#3aa675;color:#fff;width:100%}
</style></head><body>
<h1>Welches Album soll gezeigt werden?</h1>
<div class="grid">
{% for a in albums %}
 <form class="pick" method="post" action="/select">
  <input type="hidden" name="album_id" value="{{ a.id }}">
  <button type="submit">
   <div class="card {% if a.id == selected %}sel{% endif %}">
    {% if a.thumbnail_asset_id %}<img src="/thumb/{{ a.thumbnail_asset_id }}" alt="">{% endif %}
    <div class="name">{{ a.name }}{% if a.id == selected %} &#10003;{% endif %}</div>
   </div>
  </button>
 </form>
{% endfor %}
</div>
<form class="now" method="post" action="/refresh">
 <button type="submit">Neues Bild jetzt zeigen</button>
</form>
</body></html>"""


def _safe_refresh(on_refresh: Callable[[], None] | None, app: Flask | None = None) -> None:
    if not on_refresh:
        return
    try:
        on_refresh()
    except Exception:
        if app is not None:
            app.logger.exception("on_refresh failed")


def create_app(
    immich: ImmichClient,
    config: Config,
    on_refresh: Callable[[], None] | None = None,
) -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        albums = immich.list_albums()
        selected = get_selected_album(config.state_file)
        return render_template_string(PAGE, albums=albums, selected=selected)

    @app.post("/select")
    def select():
        set_selected_album(config.state_file, request.form["album_id"])
        _safe_refresh(on_refresh, app)
        return redirect(url_for("index"))

    @app.post("/refresh")
    def refresh():
        _safe_refresh(on_refresh, app)
        return redirect(url_for("index"))

    @app.get("/thumb/<asset_id>")
    def thumb(asset_id):
        data = immich.download_asset(asset_id, size="thumbnail")
        return Response(data, mimetype="image/jpeg")

    return app
