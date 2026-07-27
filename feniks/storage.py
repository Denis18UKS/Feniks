from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any


class Storage:
    """Thread-safe SQLite repository. All user-facing state is persisted here."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.lock = RLock()
        self._migrate()

    def _migrate(self) -> None:
        with self.connection:
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL DEFAULT 'assistant',
                    description TEXT NOT NULL DEFAULT '', mode TEXT NOT NULL DEFAULT 'observer',
                    status TEXT NOT NULL DEFAULT 'ready', initials TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS chats (
                    id TEXT PRIMARY KEY, agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
                    title TEXT NOT NULL, parent_id TEXT REFERENCES chats(id) ON DELETE SET NULL,
                    inherit_mode TEXT NOT NULL DEFAULT 'clean', created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT REFERENCES chats(id) ON DELETE CASCADE,
                    agent_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'saved', created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
                    level TEXT NOT NULL, category TEXT NOT NULL, event TEXT NOT NULL,
                    message TEXT NOT NULL, agent_id TEXT, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                """
            )
            self._ensure_column("agents", "description", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("agents", "created_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("agents", "initials", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("messages", "chat_id", "TEXT")
            self._ensure_column("messages", "status", "TEXT NOT NULL DEFAULT 'saved'")

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in self.connection.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def agents(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT a.*, COUNT(c.id) chat_count FROM agents a LEFT JOIN chats c ON c.agent_id=a.id "
            "GROUP BY a.id ORDER BY a.created_at DESC, a.name"
        )
        return [dict(row) for row in rows]

    def create_agent(self, name: str, category: str, description: str, mode: str) -> dict[str, Any]:
        agent = {"id": str(uuid.uuid4()), "name": name.strip(), "category": category,
                 "description": description.strip(), "mode": mode, "status": "ready", "created_at": self.now()}
        with self.lock, self.connection:
            initials = "".join(word[0] for word in agent["name"].split()[:2]).upper()
            self.connection.execute(
                "INSERT INTO agents(id,name,category,description,mode,status,initials,created_at) "
                "VALUES(:id,:name,:category,:description,:mode,:status,:initials,:created_at)",
                {**agent, "initials": initials})
        agent["chat_count"] = 0
        return agent

    def delete_agent(self, agent_id: str) -> bool:
        with self.lock, self.connection:
            cursor = self.connection.execute("DELETE FROM agents WHERE id=?", (agent_id,))
        return cursor.rowcount > 0

    def chats(self, agent_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT c.*, COUNT(m.id) message_count FROM chats c LEFT JOIN messages m ON m.chat_id=c.id "
            "WHERE c.agent_id=? GROUP BY c.id ORDER BY c.updated_at DESC", (agent_id,)
        )
        return [dict(row) for row in rows]

    def create_chat(self, agent_id: str, title: str, parent_id: str | None = None,
                    inherit_mode: str = "clean") -> dict[str, Any]:
        now = self.now()
        chat = {"id": str(uuid.uuid4()), "agent_id": agent_id, "title": title.strip() or "Новый чат",
                "parent_id": parent_id, "inherit_mode": inherit_mode, "created_at": now, "updated_at": now}
        with self.lock, self.connection:
            self.connection.execute(
                "INSERT INTO chats(id,agent_id,title,parent_id,inherit_mode,created_at,updated_at) "
                "VALUES(:id,:agent_id,:title,:parent_id,:inherit_mode,:created_at,:updated_at)", chat)
            if parent_id and inherit_mode == "copy":
                self.connection.execute(
                    "INSERT INTO messages(chat_id,agent_id,role,content,status,created_at) "
                    "SELECT ?,agent_id,role,content,status,created_at FROM messages WHERE chat_id=? ORDER BY id",
                    (chat["id"], parent_id))
        chat["message_count"] = 0
        return chat

    def delete_chat(self, chat_id: str) -> bool:
        with self.lock, self.connection:
            cursor = self.connection.execute("DELETE FROM chats WHERE id=?", (chat_id,))
        return cursor.rowcount > 0

    def messages(self, chat_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT id,role,content,status,created_at FROM messages WHERE chat_id=? ORDER BY id", (chat_id,))
        return [dict(row) for row in rows]

    def add_message(self, chat_id: str, agent_id: str, role: str, content: str,
                    status: str = "saved") -> dict[str, Any]:
        item = {"chat_id": chat_id, "agent_id": agent_id, "role": role, "content": content.strip(),
                "status": status, "created_at": self.now()}
        with self.lock, self.connection:
            cursor = self.connection.execute(
                "INSERT INTO messages(chat_id,agent_id,role,content,status,created_at) "
                "VALUES(:chat_id,:agent_id,:role,:content,:status,:created_at)", item)
            self.connection.execute("UPDATE chats SET updated_at=? WHERE id=?", (item["created_at"], chat_id))
        item["id"] = cursor.lastrowid
        return item

    def add_log(self, level: str, category: str, event: str, message: str,
                agent_id: str | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        item = {"timestamp": self.now(), "level": level, "category": category, "event": event,
                "message": message, "agent_id": agent_id, "payload": payload or {}}
        with self.lock, self.connection:
            self.connection.execute(
                "INSERT INTO logs(timestamp,level,category,event,message,agent_id,payload) VALUES(?,?,?,?,?,?,?)",
                (item["timestamp"], level, category, event, message, agent_id,
                 json.dumps(item["payload"], ensure_ascii=False)))
        return item

    def logs(self, limit: int = 200) -> list[dict[str, Any]]:
        rows = self.connection.execute("SELECT * FROM logs ORDER BY id DESC LIMIT ?", (min(limit, 1000),))
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item["payload"])
            result.append(item)
        return result

    def settings(self) -> dict[str, Any]:
        return {row["key"]: json.loads(row["value"]) for row in self.connection.execute("SELECT * FROM settings")}

    def set_setting(self, key: str, value: Any) -> None:
        with self.lock, self.connection:
            self.connection.execute(
                "INSERT INTO settings(key,value,updated_at) VALUES(?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",
                (key, json.dumps(value, ensure_ascii=False), self.now()))

    @staticmethod
    def now() -> str:
        return datetime.now(UTC).isoformat(timespec="milliseconds")
