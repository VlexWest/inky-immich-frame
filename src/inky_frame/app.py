import argparse

from .config import load_config
from .display import InkyDisplay
from .immich import ImmichClient
from .renderer import Renderer
from .scheduler import build_scheduler
from .web import create_app
from .worker import RenderWorker


def main() -> None:
    parser = argparse.ArgumentParser(description="Inky Immich Frame")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    config = load_config(args.config)
    immich = ImmichClient(config.immich_url, config.api_key)
    display = InkyDisplay(saturation=config.saturation)
    renderer = Renderer(immich, display, config)

    worker = RenderWorker(renderer.render_once)

    scheduler = build_scheduler(config.refresh_times, worker.request)
    scheduler.start()

    worker.request()  # first picture on boot, without delaying the page

    app = create_app(immich, config, worker)
    app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
