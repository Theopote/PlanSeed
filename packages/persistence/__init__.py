"""Phase 5 — 本地项目快照（SQLite）。"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def default_db_path() -> Path:
    env = os.environ.get("PLANSEED_DB")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".planseed" / "projects.db"


@dataclass
class ProjectMeta:
    id: str
    name: str
    updated_at: str


class ProjectStore:
    """projects(id, name, updated_at, payload_json)。"""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def list_projects(self) -> list[ProjectMeta]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, name, updated_at FROM projects ORDER BY updated_at DESC"
            ).fetchall()
        return [
            ProjectMeta(id=r["id"], name=r["name"], updated_at=r["updated_at"])
            for r in rows
        ]

    def get(self, project_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, name, updated_at, payload_json FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(row["payload_json"])
        return {
            "id": row["id"],
            "name": row["name"],
            "updated_at": row["updated_at"],
            "payload": payload,
        }

    def save(
        self,
        *,
        name: str,
        payload: dict[str, Any],
        project_id: str | None = None,
    ) -> dict[str, Any]:
        pid = project_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        blob = json.dumps(payload, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO projects (id, name, updated_at, payload_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    updated_at = excluded.updated_at,
                    payload_json = excluded.payload_json
                """,
                (pid, name, now, blob),
            )
            conn.commit()
        return {"id": pid, "name": name, "updated_at": now, "payload": payload}

    def delete(self, project_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()
            return cur.rowcount > 0
