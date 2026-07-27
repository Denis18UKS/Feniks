from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any


DEFAULT_AGENTS = [
    ("stellaris-advisor", "Stellaris Strategist", "Игровой советник", "advisor", "active", "ST"),
    ("desktop-copilot", "Desktop Copilot", "Компьютерный помощник", "observer", "paused", "DC"),
    ("factory-planner", "Factory Planner", "Satisfactory", "assistant", "training", "FP"),
]


class Storage:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.lock = Lock()
        self._migrate()

    def _migrate(self) -> None:
        with self.connection:
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL,
                    mode TEXT NOT NULL, status TEXT NOT NULL, initials TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, agent_id TEXT NOT NULL,
                    role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
                    level TEXT NOT NULL, category TEXT NOT NULL, event TEXT NOT NULL,
                    message TEXT NOT NULL, agent_id TEXT, payload TEXT NOT NULL
                );
                """
            )
            count = self.connection.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
            if count == 0:
                self.connection.executemany("INSERT INTO agents VALUES (?, ?, ?, ?, ?, ?)", DEFAULT_AGENTS)

    def agents(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.connection.execute("SELECT * FROM agents ORDER BY name")]

    def messages(self, agent_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT role, content, created_at FROM messages WHERE agent_id = ? ORDER BY id", (agent_id,)
        )
        return [dict(row) for row in rows]

    def add_message(self, agent_id: str, role: str, content: str) -> dict[str, Any]:
        item = {"role": role, "content": content.strip(), "created_at": self.now()}
        with self.lock, self.connection:
            self.connection.execute(
                "INSERT INTO messages(agent_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (agent_id, item["role"], item["content"], item["created_at"]),
            )
        return item

    def add_log(self, level: str, category: str, event: str, message: str, agent_id: str | None = None,
                payload: dict[str, Any] | None = None) -> dict[str, Any]:
        item = {"timestamp": self.now(), "level": level, "category": category, "event": event,
                "message": message, "agent_id": agent_id, "payload": payload or {}}
        with self.lock, self.connection:
            self.connection.execute(
                "INSERT INTO logs(timestamp, level, category, event, message, agent_id, payload) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (*[item[key] for key in ("timestamp", "level", "category", "event", "message", "agent_id")],
                 json.dumps(item["payload"], ensure_ascii=False)),
            )
        return item

    def logs(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.connection.execute("SELECT * FROM logs ORDER BY id DESC LIMIT ?", (min(limit, 500),))
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item["payload"])
            result.append(item)
        return result

    @staticmethod
    def now() -> str:
        return datetime.now(UTC).isoformat(timespec="milliseconds")
