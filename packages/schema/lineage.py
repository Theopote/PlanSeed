"""Phase 5 — Variant 血缘与 locks 指纹。"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from packages.schema.locks import LayoutLocks


def _canonicalize_locks_dict(data: dict[str, Any]) -> dict[str, Any]:
    """规范化列表顺序，使「同锁同指纹」与房间/分区插入序无关。"""
    rooms = [dict(r) for r in (data.get("rooms") or [])]
    zones_raw = [dict(z) for z in (data.get("zones") or [])]

    def room_key(r: dict[str, Any]) -> tuple:
        return (
            str(r.get("room_id") or ""),
            str(r.get("floor_id") or ""),
            float(r.get("x") or 0),
            float(r.get("y") or 0),
            float(r.get("width") or 0),
            float(r.get("depth") or 0),
        )

    def zone_key(z: dict[str, Any]) -> tuple:
        room_ids = sorted(str(x) for x in (z.get("room_ids") or []))
        zone = z.get("zone")
        zone_s = zone.value if hasattr(zone, "value") else str(zone or "")
        return (
            zone_s,
            str(z.get("floor_id") or ""),
            float(z.get("x") or 0),
            float(z.get("y") or 0),
            float(z.get("width") or 0),
            float(z.get("depth") or 0),
            tuple(room_ids),
            str(z.get("zone_id") or ""),
        )

    rooms_sorted = sorted(rooms, key=room_key)
    zones_out: list[dict[str, Any]] = []
    for z in sorted(zones_raw, key=zone_key):
        z = dict(z)
        z["room_ids"] = sorted(str(x) for x in (z.get("room_ids") or []))
        zones_out.append(z)

    return {
        "rooms": rooms_sorted,
        "stair": data.get("stair"),
        "zones": zones_out,
    }


def locks_fingerprint(locks: LayoutLocks | dict[str, Any] | None) -> str:
    """
    规范化 LayoutLocks → 短哈希（16 hex）。

    同锁同指纹；字段顺序与 rooms/zones 列表顺序无关。空锁仍有稳定指纹。
    """
    if locks is None:
        data: dict[str, Any] = {"rooms": [], "stair": None, "zones": []}
    elif isinstance(locks, LayoutLocks):
        data = locks.model_dump(mode="json")
    else:
        data = dict(locks)
    data = _canonicalize_locks_dict(data)
    data = _js_like_numbers(data)
    # UTF-8 + integral floats as ints — 对齐 desktop/src/lib/lineage.ts JSON.stringify
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _js_like_numbers(value: Any) -> Any:
    """Match JSON.stringify number formatting (1.0 → 1)."""
    if isinstance(value, dict):
        return {k: _js_like_numbers(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_js_like_numbers(v) for v in value]
    if isinstance(value, float) and value.is_integer() and abs(value) < 2**53:
        return int(value)
    return value


def lineage_label(base_label: str, generation: int) -> str:
    """Strip 展示：A / A·1 / A·2（generation 相对根）。"""
    if generation <= 0:
        return base_label
    return f"{base_label}·{generation}"
