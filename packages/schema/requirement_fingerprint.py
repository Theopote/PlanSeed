"""RequirementSpec 内容指纹 — 候选评价基准可追踪。"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from packages.schema.requirements import RequirementSpec


def requirement_revision_id(spec: RequirementSpec | dict[str, Any] | None) -> str | None:
    """
    稳定短指纹：面积 / 朝向 / 关系 / 偏好等影响求解与评价的字段。

    不含 raw_text 噪声；旧快照无 Spec 时返回 None。
    """
    if spec is None:
        return None
    if isinstance(spec, RequirementSpec):
        data = spec.model_dump(mode="json")
    elif isinstance(spec, dict):
        data = spec
    else:
        return None

    payload = {
        "floor_count": data.get("floor_count"),
        "site": data.get("site"),
        "household": data.get("household"),
        "spaces": sorted(
            data.get("spaces") or [],
            key=lambda s: (s.get("id") or "", s.get("name") or ""),
        ),
        "preferences": data.get("preferences"),
        "relation_intents": sorted(
            data.get("relation_intents") or [],
            key=lambda r: (r.get("a") or "", r.get("b") or "", r.get("kind") or ""),
        ),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"req-{digest[:12]}"
