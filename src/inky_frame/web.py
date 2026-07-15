from flask import (
    Flask, Response, jsonify, redirect, render_template_string, request, url_for,
)

from .config import (
    Config, DEFAULT_LANGUAGE, get_language, get_pinned_asset, get_selected_album,
    set_language, set_pinned_asset, set_selected_album,
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
        "rotate": "Bilder wechseln lassen",
        "back": "Zurück",
        "pick_photo": "Oder ein Bild aussuchen, das bleiben soll:",
    },
    "en": {
        "label": "English",
        "title": "Photo frame",
        "heading": "Which album should be shown?",
        "loading": "Loading a new picture – this takes about a minute.",
        "failed": "Could not load a picture. The last one stays on screen.",
        "refresh": "Show a new picture now",
        "offline": "The photos are not reachable right now. The picture in the frame stays as it is.",
        "rotate": "Let the pictures change",
        "back": "Back",
        "pick_photo": "Or pick one picture to keep on the frame:",
    },
    "ru": {
        "label": "Русский",
        "title": "Фоторамка",
        "heading": "Какой альбом показывать?",
        "loading": "Загружается новое фото – это займёт около минуты.",
        "failed": "Не удалось загрузить фото. Останется предыдущее.",
        "refresh": "Показать новое фото",
        "offline": "Фотографии сейчас недоступны. Фото в рамке останется прежним.",
        "rotate": "Пусть фото меняются",
        "back": "Назад",
        "pick_photo": "Или выбери одно фото, которое останется:",
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
 a.pick{display:block;text-decoration:none;color:inherit}
 [hidden]{display:none !important}
 .note{padding:.8rem 1rem;border-radius:12px;margin-bottom:1rem;font-size:1rem}
 .loading{background:#fff5d6;border:1px solid #e8cf7a;display:flex;align-items:center;gap:.6rem}
 .failed{background:#ffe9e6;border:1px solid #f0b3aa}
 .dot{width:.8rem;height:.8rem;border-radius:50%;background:#e0a800;flex:none;
   animation:pulse 1s ease-in-out infinite}
 @keyframes pulse{0%,100%{opacity:.3}50%{opacity:1}}
 body[data-busy="true"] .grid{opacity:.45}
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
 <a class="pick" href="/album/{{ a.id }}">
   <div class="card {% if a.id == selected %}sel{% endif %}">
    {% if a.thumbnail_asset_id %}<img src="/thumb/{{ a.thumbnail_asset_id }}" alt="" loading="lazy">{% endif %}
    <div class="name">{{ a.name }}{% if a.id == selected %} &#10003;{% endif %}</div>
   </div>
 </a>
{% endfor %}
</div>

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

ALBUM_PAGE = """<!doctype html><html lang="{{ lang }}"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ album_name }}</title>
<style>
 body{font-family:system-ui,sans-serif;margin:0;padding:1rem;background:#faf9f7;color:#222}
 h1{font-size:1.3rem;margin:0 0 1rem}
 p.hint{margin:1.2rem 0 .8rem;font-size:.95rem;color:#5d6b62}
 .grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:.5rem}
 .card{border:3px solid transparent;border-radius:10px;overflow:hidden;background:#fff}
 .card.sel{border-color:#3aa675}
 .card img{width:100%;aspect-ratio:1;object-fit:cover;display:block;background:#eee}
 form.pick{margin:0}
 form.pick button{all:unset;display:block;cursor:pointer;width:100%}
 form.rotate button{font-size:1.05rem;padding:.8rem 1rem;border:0;border-radius:12px;
   background:#3aa675;color:#fff;width:100%}
 [hidden]{display:none !important}
 .note{padding:.8rem 1rem;border-radius:12px;margin-bottom:1rem;font-size:1rem}
 .loading{background:#fff5d6;border:1px solid #e8cf7a;display:flex;align-items:center;gap:.6rem}
 .failed{background:#ffe9e6;border:1px solid #f0b3aa}
 .dot{width:.8rem;height:.8rem;border-radius:50%;background:#e0a800;flex:none;
   animation:pulse 1s ease-in-out infinite}
 @keyframes pulse{0%,100%{opacity:.3}50%{opacity:1}}
 body[data-busy="true"] .grid,body[data-busy="true"] form.rotate{opacity:.45}
 a.back{display:inline-block;margin-top:1.5rem;color:#5d6b62;font-size:.95rem}
 @media (prefers-reduced-motion: reduce){ .dot{animation:none} }
</style></head><body data-busy="{{ 'true' if busy else 'false' }}">
<h1>{{ album_name }}</h1>

<div class="note loading" id="banner" {% if not busy %}hidden{% endif %}>
 <span class="dot"></span><span>{{ t.loading }}</span>
</div>

{% if offline %}
<div class="note failed">{{ t.offline }}</div>
{% elif error %}
<div class="note failed">{{ t.failed }}</div>
{% endif %}

<form class="rotate" method="post" action="/select">
 <input type="hidden" name="album_id" value="{{ album_id }}">
 <button type="submit">{{ t.rotate }}</button>
</form>

<p class="hint">{{ t.pick_photo }}</p>

<div class="grid">
{% for a in assets %}
 <form class="pick" method="post" action="/pin">
  <input type="hidden" name="album_id" value="{{ album_id }}">
  <input type="hidden" name="asset_id" value="{{ a.id }}">
  <button type="submit">
   <div class="card {% if a.id == pinned %}sel{% endif %}">
    <img src="/thumb/{{ a.id }}" alt="" loading="lazy">
   </div>
  </button>
 </form>
{% endfor %}
</div>

<a class="back" href="/">&#8592; {{ t.back }}</a>

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
       wasBusy = s.busy; setBusy(s.busy); setTimeout(poll, 2000);
     })
     .catch(function () { setTimeout(poll, 2000); });
 }
 setTimeout(poll, 2000);
</script>
</body></html>"""


def create_app(immich: ImmichClient, config: Config, worker, thumbs) -> Flask:
    """Album picker for a non-technical reader.

    `worker` runs renders off the request thread (see RenderWorker). `thumbs` is a
    ThumbnailCache — the grid asks for up to 200 tiles and each one would otherwise
    be a fresh round trip to Immich.
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

    @app.get("/album/<album_id>")
    def album(album_id):
        status = worker.status()
        lang = get_language(config.state_file)
        if lang not in LANGUAGES:
            lang = DEFAULT_LANGUAGE
        try:
            albums = immich.list_albums()
            name = next((a.name for a in albums if a.id == album_id), album_id)
            assets = [a for a in immich.get_album_assets(album_id) if a.type == "IMAGE"]
            offline = False
        except Exception:
            app.logger.exception("could not load album %s", album_id)
            name, assets, offline = album_id, [], True
        return render_template_string(
            ALBUM_PAGE,
            album_id=album_id,
            album_name=name,
            assets=assets,
            pinned=get_pinned_asset(config.state_file),
            busy=status["busy"],
            error=status["error"],
            offline=offline,
            lang=lang,
            t=LANGUAGES[lang],
        )

    @app.post("/pin")
    def pin():
        set_selected_album(config.state_file, request.form["album_id"])
        set_pinned_asset(config.state_file, request.form["asset_id"])
        worker.request()
        return redirect(url_for("album", album_id=request.form["album_id"]))

    @app.get("/thumb/<asset_id>")
    def thumb(asset_id):
        try:
            data = thumbs.get(asset_id)
        except Exception:
            # A missing thumbnail must degrade to a blank tile, not a 500.
            return Response(status=404)
        return Response(data, mimetype="image/jpeg",
                         headers={"Cache-Control": "public, max-age=31536000, immutable"})

    return app
