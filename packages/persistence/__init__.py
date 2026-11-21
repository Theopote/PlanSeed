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


class ProjectConflictError(Exception):
    """乐观并发冲突：expected_updated_at 与库中不一致。"""

    def __init__(
        self,
        message: str,
        *,
        project_id: str,
        current_updated_at: str,
        expected_updated_at: str,
    ) -> None:
        super().__init__(message)
        self.project_id = project_id
        self.current_updated_at = current_updated_at
        self.expected_updated_at = expected_updated_at


class ProjectStore:
    """projects(id, name, updated_at, payload_json)；打开时自动 migrate。"""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA foreign_keys=ON")
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
        expected_updated_at: str | None = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """
        保存项目快照。

        ``expected_updated_at``：已有项目时须与库中 ``updated_at`` 一致，否则
        抛 ``ProjectConflictError``（除非 ``overwrite=True``）。新建项目忽略该字段。
        """
        pid = project_id or str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        blob = json.dumps(payload, ensure_ascii=False)
        conn = self._connect()
        # 手动事务 + IMMEDIATE 写锁：版本检查与写入不可被其它连接插入
        prev_isolation = conn.isolation_level
        try:
            conn.isolation_level = None
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT updated_at FROM projects WHERE id = ?",
                (pid,),
            ).fetchone()
            # 仅当调用方提供 expected_updated_at 时启用乐观锁（桌面端）；
            # 未提供则保持旧行为，兼容内部脚本与未升级客户端。
            if (
                existing is not None
                and expected_updated_at is not None
                and not overwrite
            ):
                current = str(existing["updated_at"])
                if expected_updated_at != current:
                    conn.execute("ROLLBACK")
                    raise ProjectConflictError(
                        "项目已被其它会话更新，拒绝覆盖",
                        project_id=pid,
                        current_updated_at=current,
                        expected_updated_at=expected_updated_at,
                    )
                cur = conn.execute(
                    """
                    UPDATE projects
                    SET name = ?, updated_at = ?, payload_json = ?
                    WHERE id = ? AND updated_at = ?
                    """,
                    (name, now, blob, pid, expected_updated_at),
                )
                if cur.rowcount != 1:
                    row = conn.execute(
                        "SELECT updated_at FROM projects WHERE id = ?",
                        (pid,),
                    ).fetchone()
                    conn.execute("ROLLBACK")
                    raise ProjectConflictError(
                        "项目已被其它会话更新，拒绝覆盖",
                        project_id=pid,
                        current_updated_at=str(row["updated_at"]) if row else "",
                        expected_updated_at=expected_updated_at,
                    )
            else:
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
            conn.execute("COMMIT")
        except ProjectConflictError:
            raise
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            conn.isolation_level = prev_isolation
            conn.close()
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
    "ProjectConflictError",
    "ProjectMeta",
    "ProjectStore",
    "default_db_path",
    "migrate",
    "pack_planseed",
    "unpack_planseed",
]
