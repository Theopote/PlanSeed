"""Phase 5 — Variant 血缘与 locks 指纹。"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from packages.schema.locks import LayoutLocks


def locks_fingerprint(locks: LayoutLocks | dict[str, Any] | None) -> str:
    """
    规范化 LayoutLocks → 短哈希（16 hex）。

    同锁同指纹；字段顺序无关。空锁仍有稳定指纹。
    """
    if locks is None:
        data: dict[str, Any] = {"rooms": [], "stair": None, "zones": []}
    elif isinstance(locks, LayoutLocks):
        data = locks.model_dump(mode="json")
    else:
        data = dict(locks)
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def lineage_label(base_label: str, generation: int) -> str:
    """Strip 展示：A / A·1 / A·2（generation 相对根）。"""
    if generation <= 0:
        return base_label
    return f"{base_label}·{generation}"
