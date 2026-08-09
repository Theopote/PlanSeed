"""v001 — 初始 projects 表（与 Phase 5 ProjectStore 一致）。"""

from __future__ import annotations

import sqlite3

VERSION = 1


def upgrade(conn: sqlite3.Connection) -> None:
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
