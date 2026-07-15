from flask import (
    Flask, Response, jsonify, redirect, render_template_string, request, url_for,
)

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
 .note{padding:.8rem 1rem;border-radius:12px;margin-bottom:1rem;font-size:1rem}
 .loading{background:#fff5d6;border:1px solid #e8cf7a;display:flex;align-items:center;gap:.6rem}
 .failed{background:#ffe9e6;border:1px solid #f0b3aa}
 .dot{width:.8rem;height:.8rem;border-radius:50%;background:#e0a800;flex:none;
   animation:pulse 1s ease-in-out infinite}
 @keyframes pulse{0%,100%{opacity:.3}50%{opacity:1}}
 body[data-busy="true"] .grid,body[data-busy="true"] form.now{opacity:.45}
 button[disabled]{cursor:default}
</style></head><body data-busy="{{ 'true' if busy else 'false' }}">
<h1>Welches Album soll gezeigt werden?</h1>

<div class="note loading" id="banner" {% if not busy %}hidden{% endif %}>
 <span class="dot"></span>
 <span>Neues Bild wird geladen &ndash; das dauert etwa eine Minute.</span>
</div>

{% if error %}
<div class="note failed">Bild konnte nicht geladen werden. Das letzte Bild bleibt stehen.</div>
{% endif %}

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

<script>
 var banner = document.getElementById("banner");
 var wasBusy = document.body.dataset.busy === "true";

 function setBusy(b) {
   document.body.dataset.busy = b ? "true" : "false";
   banner.hidden = !b;
   var bs = document.querySelectorAll("button");
   for (var i = 0; i < bs.length; i++) { bs[i].disabled = b; }
 }
 setBusy(wasBusy);

 var forms = document.querySelectorAll("form");
 for (var i = 0; i < forms.length; i++) {
   forms[i].addEventListener("submit", function () { wasBusy = true; setBusy(true); });
 }

 function poll() {
   fetch("/status", {cache: "no-store"})
     .then(function (r) { return r.json(); })
     .then(function (s) {
       if (wasBusy && !s.busy) { location.reload(); return; }
       wasBusy = s.busy;
       setBusy(s.busy);
       setTimeout(poll, 2000);
     })
     .catch(function () { setTimeout(poll, 2000); });
 }
 setTimeout(poll, 2000);
</script>
</body></html>"""


def create_app(immich: ImmichClient, config: Config, worker) -> Flask:
    """Album picker for a non-technical reader.

    `worker` runs renders off the request thread (see RenderWorker): a refresh
    takes ~40s, so requests only ask for one and return immediately, and the
    page reflects progress instead of hanging the browser.
    """
    app = Flask(__name__)

    @app.get("/")
    def index():
        status = worker.status()
        return render_template_string(
            PAGE,
            albums=immich.list_albums(),
            selected=get_selected_album(config.state_file),
            busy=status["busy"],
            error=status["error"],
        )

    @app.get("/status")
    def status():
        return jsonify(worker.status())

    @app.post("/select")
    def select():
        set_selected_album(config.state_file, request.form["album_id"])
        worker.request()
        return redirect(url_for("index"))

    @app.post("/refresh")
    def refresh():
        worker.request()
        return redirect(url_for("index"))

    @app.get("/thumb/<asset_id>")
    def thumb(asset_id):
        data = immich.download_asset(asset_id, size="thumbnail")
        return Response(data, mimetype="image/jpeg")

    return app
