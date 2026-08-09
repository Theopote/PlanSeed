"""SQLite schema migrations via PRAGMA user_version（不上 Alembic）。"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Final

from packages.persistence.migrations import v001_initial

UpgradeFn = Callable[[sqlite3.Connection], None]

# version → upgrade(conn)；必须从 1 连续编号。
_MIGRATIONS: Final[dict[int, UpgradeFn]] = {
    v001_initial.VERSION: v001_initial.upgrade,
}

CURRENT_VERSION: Final[int] = max(_MIGRATIONS)


def get_user_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0]) if row is not None else 0


def set_user_version(conn: sqlite3.Connection, version: int) -> None:
    # PRAGMA 不接受绑定参数
    conn.execute(f"PRAGMA user_version = {int(version)}")


def migrate(
    conn: sqlite3.Connection,
    from_version: int | None = None,
    to_version: int | None = None,
) -> int:
    """
    将连接从 from_version 升到 to_version（默认：当前 PRAGMA → CURRENT_VERSION）。

    每步：执行 upgrade，再 PRAGMA user_version = n。
    返回最终 version。
    """
    start = get_user_version(conn) if from_version is None else int(from_version)
    target = CURRENT_VERSION if to_version is None else int(to_version)

    if target < start:
        raise ValueError(f"不支持降级：{start} → {target}")
    if target > CURRENT_VERSION:
        raise ValueError(f"未知目标版本 {target}（当前最高 {CURRENT_VERSION}）")
    if start < 0:
        raise ValueError(f"非法 from_version={start}")

    version = start
    while version < target:
        nxt = version + 1
        upgrade = _MIGRATIONS.get(nxt)
        if upgrade is None:
            raise RuntimeError(f"缺少 migration v{nxt:03d}")
        upgrade(conn)
        set_user_version(conn, nxt)
        version = nxt
    return version
