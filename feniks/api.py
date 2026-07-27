from __future__ import annotations

from typing import Any

from .storage import Storage


class DesktopApi:
    """Small, serializable API exposed to the trusted local WebView."""

    def __init__(self, storage: Storage) -> None:
        self.storage = storage
        self.window: Any = None

    def attach_window(self, window: Any) -> None:
        self.window = window

    def bootstrap(self) -> dict[str, Any]:
        return {"agents": self.storage.agents(), "logs": self.storage.logs(), "version": "0.1.0"}

    def get_messages(self, agent_id: str) -> list[dict[str, Any]]:
        return self.storage.messages(agent_id)

    def send_message(self, agent_id: str, content: str) -> dict[str, Any]:
        if not content or not content.strip():
            return {"ok": False, "error": "Сообщение не может быть пустым"}
        user = self.storage.add_message(agent_id, "user", content)
        response = self.storage.add_message(
            agent_id,
            "assistant",
            "Задача принята. Я сформирую безопасный план, проверю доступные инструменты и буду сообщать о прогрессе.",
        )
        log = self.storage.add_log("INFO", "agent.task", "task_received", content.strip(), agent_id,
                                   {"status": "queued", "source": "chat"})
        return {"ok": True, "messages": [user, response], "log": log}

    def set_agent_mode(self, agent_id: str, mode: str) -> dict[str, Any]:
        allowed = {"observer", "advisor", "assistant", "autonomous"}
        if mode not in allowed:
            return {"ok": False, "error": "Неизвестный режим"}
        with self.storage.lock, self.storage.connection:
            self.storage.connection.execute("UPDATE agents SET mode = ? WHERE id = ?", (mode, agent_id))
        self.storage.add_log("SECURITY", "agent.permissions", "mode_changed", f"Режим изменён: {mode}",
                             agent_id, {"mode": mode})
        return {"ok": True, "mode": mode}

    def get_logs(self) -> list[dict[str, Any]]:
        return self.storage.logs()
