from __future__ import annotations

import os
from pathlib import Path

from .api import DesktopApi
from .storage import Storage


class FeniksApplication:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.root = Path(__file__).resolve().parent.parent
        self.data_dir = data_dir or self._default_data_dir()
        self.storage = Storage(self.data_dir / "feniks.db")
        self.api = DesktopApi(self.storage)

    @staticmethod
    def _default_data_dir() -> Path:
        try:
            from platformdirs import user_data_path

            return user_data_path("FeniksAIStudio", "Feniks", ensure_exists=True)
        except ImportError:
            path = Path.home() / ".feniks-ai-studio"
            path.mkdir(parents=True, exist_ok=True)
            return path

    def run(self) -> None:
        try:
            import webview
        except ImportError as exc:
            raise SystemExit("PyWebView не установлен. Выполните: pip install -r requirements.txt") from exc

        window = webview.create_window(
            "Feniks AI Studio",
            str(self.root / "web" / "index.html"),
            js_api=self.api,
            width=1440,
            height=900,
            min_size=(1080, 680),
            background_color="#0b1020",
        )
        self.api.attach_window(window)
        webview.start(debug=os.getenv("FENIKS_DEBUG") == "1")


def create_app(data_dir: Path | None = None) -> FeniksApplication:
    return FeniksApplication(data_dir)
