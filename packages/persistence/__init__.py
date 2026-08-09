"""Phase 5 — 本地项目快照（SQLite）+ Phase 7.5-C migrations · 7.5-D 包导出。"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.persistence.migrations import CURRENT_VERSION, get_user_version, migrate
from packages.persistence.planseed_package import (
    PLANSEED_EXTENSION,
    PLANSEED_FORMAT,
    pack_planseed,
    unpack_planseed,
)


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
    """projects(id, name, updated_at, payload_json)；打开时自动 migrate。"""

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
            migrate(conn)
            conn.commit()

    @property
    def schema_version(self) -> int:
        with self._connect() as conn:
            return get_user_version(conn)

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
        now = datetime.now(UTC).isoformat()
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


__all__ = [
    "CURRENT_VERSION",
    "PLANSEED_EXTENSION",
    "PLANSEED_FORMAT",
    "ProjectMeta",
    "ProjectStore",
    "default_db_path",
    "migrate",
    "pack_planseed",
    "unpack_planseed",
]
