from flask import (
    Flask, Response, jsonify, redirect, render_template_string, request, url_for,
)

from .config import (
    Config, DEFAULT_LANGUAGE, get_language, get_selected_album, set_language,
    set_selected_album,
)
from .immich import ImmichClient

LANGUAGES = {
    "de": {
        "label": "Deutsch",
        "title": "Bilderrahmen",
        "heading": "Welches Album soll gezeigt werden?",
        "loading": "Neues Bild wird geladen – das dauert etwa eine Minute.",
        "failed": "Bild konnte nicht geladen werden. Das letzte Bild bleibt stehen.",
        "refresh": "Neues Bild jetzt zeigen",
        "offline": "Die Fotos sind gerade nicht erreichbar. Das Bild im Rahmen bleibt stehen.",
    },
    "en": {
        "label": "English",
        "title": "Photo frame",
        "heading": "Which album should be shown?",
        "loading": "Loading a new picture – this takes about a minute.",
        "failed": "Could not load a picture. The last one stays on screen.",
        "refresh": "Show a new picture now",
        "offline": "The photos are not reachable right now. The picture in the frame stays as it is.",
    },
    "ru": {
        "label": "Русский",
        "title": "Фоторамка",
        "heading": "Какой альбом показывать?",
        "loading": "Загружается новое фото – это займёт около минуты.",
        "failed": "Не удалось загрузить фото. Останется предыдущее.",
        "refresh": "Показать новое фото",
        "offline": "Фотографии сейчас недоступны. Фото в рамке останется прежним.",
    },
}

PAGE = """<!doctype html><html lang="{{ lang }}"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ t.title }}</title>
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
 .langs{display:flex;justify-content:center;gap:.4rem;margin-top:2rem;
   border-top:1px solid #e8e6df;padding-top:1rem}
 .langs form{margin:0}
 .langs button{all:unset;cursor:pointer;padding:.45rem .7rem;border-radius:8px;
   font-size:.9rem;color:#5d6b62}
 .langs button[aria-current="true"]{background:#eef3ef;color:#26483a;font-weight:600}
 @media (prefers-reduced-motion: reduce){ .dot{animation:none} }
</style></head><body data-busy="{{ 'true' if busy else 'false' }}">
<h1>{{ t.heading }}</h1>

<div class="note loading" id="banner" {% if not busy %}hidden{% endif %}>
 <span class="dot"></span>
 <span>{{ t.loading }}</span>
</div>

{% if offline %}
<div class="note failed">{{ t.offline }}</div>
{% elif error %}
<div class="note failed">{{ t.failed }}</div>
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
 <button type="submit">{{ t.refresh }}</button>
</form>

<nav class="langs">
{% for code, strings in languages.items() %}
 <form method="post" action="/language">
  <input type="hidden" name="lang" value="{{ code }}">
  <button type="submit" {% if code == lang %}aria-current="true"{% endif %}>{{ strings.label }}</button>
 </form>
{% endfor %}
</nav>

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

    @app.after_request
    def no_store(response):
        # The page and /status carry live state. A cached copy strands the
        # reader on a stale "loading" banner, and the reload serves the cache
        # too, so it never clears. Thumbnails may cache — they never change.
        if request.path != "/thumb" and not request.path.startswith("/thumb/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    def index():
        status = worker.status()
        lang = get_language(config.state_file)
        if lang not in LANGUAGES:
            lang = DEFAULT_LANGUAGE

        # The server may be down or the wifi broken — the picker still has to
        # answer. It is the only screen the recipient has.
        try:
            albums = immich.list_albums()
            offline = False
        except Exception:
            app.logger.exception("could not list albums")
            albums = []
            offline = True

        return render_template_string(
            PAGE,
            albums=albums,
            selected=get_selected_album(config.state_file),
            busy=status["busy"],
            error=status["error"],
            offline=offline,
            lang=lang,
            t=LANGUAGES[lang],
            languages=LANGUAGES,
        )

    @app.get("/status")
    def status():
        return jsonify(worker.status())

    @app.post("/language")
    def language():
        chosen = request.form.get("lang", "")
        if chosen in LANGUAGES:
            set_language(config.state_file, chosen)
        return redirect(url_for("index"))

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
        try:
            data = immich.download_asset(asset_id, size="thumbnail")
        except Exception:
            # A missing thumbnail must degrade to a blank tile, not a 500.
            return Response(status=404)
        return Response(data, mimetype="image/jpeg")

    return app
