from __future__ import annotations

import sqlite3
from typing import Any

from .storage import Storage


MODES = {"observer", "advisor", "assistant", "autonomous"}
CATEGORIES = {"assistant", "game", "desktop", "research", "custom"}


class DesktopApi:
    """Validated JSON API exposed only to the trusted local WebView."""

    def __init__(self, storage: Storage) -> None:
        self.storage = storage
        self.window: Any = None

    def attach_window(self, window: Any) -> None:
        self.window = window

    def bootstrap(self) -> dict[str, Any]:
        return {"agents": self.storage.agents(), "logs": self.storage.logs(),
                "settings": self.storage.settings(), "version": "0.2.0"}

    def create_agent(self, data: dict[str, Any]) -> dict[str, Any]:
        name = str(data.get("name", "")).strip()
        mode, category = data.get("mode", "observer"), data.get("category", "assistant")
        if not name or len(name) > 80:
            return {"ok": False, "error": "Название должно содержать от 1 до 80 символов"}
        if mode not in MODES or category not in CATEGORIES:
            return {"ok": False, "error": "Некорректный тип или режим агента"}
        agent = self.storage.create_agent(name, category, str(data.get("description", "")), mode)
        log = self.storage.add_log("INFO", "agent.lifecycle", "agent_created", f"Создан агент «{name}»",
                                   agent["id"], {"mode": mode, "category": category})
        return {"ok": True, "agent": agent, "log": log}

    def delete_agent(self, agent_id: str) -> dict[str, Any]:
        deleted = self.storage.delete_agent(agent_id)
        if deleted:
            self.storage.add_log("WARNING", "agent.lifecycle", "agent_deleted", "Агент и его чаты удалены",
                                 agent_id)
        return {"ok": deleted}

    def get_chats(self, agent_id: str) -> list[dict[str, Any]]:
        return self.storage.chats(agent_id)

    def create_chat(self, agent_id: str, title: str = "Новый чат", parent_id: str | None = None,
                    inherit_mode: str = "clean") -> dict[str, Any]:
        if inherit_mode not in {"clean", "copy"}:
            return {"ok": False, "error": "Неизвестный способ наследования"}
        try:
            chat = self.storage.create_chat(agent_id, title[:100], parent_id, inherit_mode)
        except sqlite3.IntegrityError:
            return {"ok": False, "error": "Агент или родительский чат не найден"}
        self.storage.add_log("INFO", "chat.lifecycle", "chat_created", f"Создан чат «{chat['title']}»",
                             agent_id, {"chat_id": chat["id"], "inherit_mode": inherit_mode})
        return {"ok": True, "chat": chat}

    def delete_chat(self, chat_id: str) -> dict[str, Any]:
        return {"ok": self.storage.delete_chat(chat_id)}

    def get_messages(self, chat_id: str) -> list[dict[str, Any]]:
        return self.storage.messages(chat_id)

    def send_message(self, agent_id: str, chat_id: str, content: str) -> dict[str, Any]:
        content = str(content).strip()
        if not content or len(content) > 20_000:
            return {"ok": False, "error": "Сообщение должно содержать от 1 до 20 000 символов"}
        message = self.storage.add_message(chat_id, agent_id, "user", content, "saved")
        log = self.storage.add_log("INFO", "chat.message", "message_saved", "Сообщение сохранено",
                                   agent_id, {"chat_id": chat_id, "message_id": message["id"]})
        return {"ok": True, "message": message, "log": log,
                "model_status": "not_configured"}

    def set_agent_mode(self, agent_id: str, mode: str) -> dict[str, Any]:
        if mode not in MODES:
            return {"ok": False, "error": "Неизвестный режим"}
        with self.storage.lock, self.storage.connection:
            cursor = self.storage.connection.execute("UPDATE agents SET mode=? WHERE id=?", (mode, agent_id))
        if cursor.rowcount == 0:
            return {"ok": False, "error": "Агент не найден"}
        self.storage.add_log("SECURITY", "agent.permissions", "mode_changed", f"Режим изменён: {mode}",
                             agent_id, {"mode": mode})
        return {"ok": True, "mode": mode}

    def save_setting(self, key: str, value: Any) -> dict[str, Any]:
        if key not in {"theme", "language", "confirm_autonomous_actions"}:
            return {"ok": False, "error": "Настройка не разрешена"}
        self.storage.set_setting(key, value)
        return {"ok": True}

    def get_logs(self) -> list[dict[str, Any]]:
        return self.storage.logs()
