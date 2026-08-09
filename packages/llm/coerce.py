"""LLM 草稿确定性容错 — Hybrid Parser 的 schema 缓冲层。

在严格 Pydantic 校验前，消化常见模型走形（字符串数字、别名 kind、残缺项），
避免把可恢复错误全部推给 LLM repair。

原则：只做无损/可解释的归一；不臆造用户未说的需求内容。
"""

from __future__ import annotations

from typing import Any

_VALID_RELATION_KINDS = frozenset(
    {
        "adjacency",
        "near",
        "separation",
        "access",
        "open_connection",
        "visual_connection",
    }
)

_KIND_ALIASES: dict[str, str] = {
    "adjacent": "adjacency",
    "adjacency": "adjacency",
    "near": "near",
    "nearby": "near",
    "close": "near",
    "proximity": "near",
    "separate": "separation",
    "separation": "separation",
    "away": "separation",
    "access": "access",
    "accessible": "access",
    "passage": "access",
    "open": "open_connection",
    "open_connection": "open_connection",
    "openconnection": "open_connection",
    "connected": "open_connection",
    "visual": "visual_connection",
    "visual_connection": "visual_connection",
    "visibility": "visual_connection",
    # 中文种别名（模型偶发直出）
    "邻接": "adjacency",
    "靠近": "near",
    "邻近": "near",
    "远离": "separation",
    "分离": "separation",
    "通行": "access",
    "相连": "access",
    "连通": "open_connection",
    "开敞": "open_connection",
    "视线": "visual_connection",
}

_ORIENT_ALIASES: dict[str, str] = {
    "north": "north",
    "south": "south",
    "east": "east",
    "west": "west",
    "n": "north",
    "s": "south",
    "e": "east",
    "w": "west",
    "北": "north",
    "南": "south",
    "东": "east",
    "西": "west",
    "朝北": "north",
    "朝南": "south",
    "朝东": "east",
    "朝西": "west",
    "北向": "north",
    "南向": "south",
    "东向": "east",
    "西向": "west",
}


def coerce_llm_draft_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """返回可尝试 model_validate 的浅拷贝归一结果。"""
    data = dict(payload)
    # 偶发包一层
    if "known" not in data and isinstance(data.get("draft"), dict):
        data = dict(data["draft"])

    if "known" in data and data["known"] is None:
        data["known"] = {}
    if "assumptions" in data and data["assumptions"] is None:
        data["assumptions"] = []
    if "unknowns" in data and data["unknowns"] is None:
        data["unknowns"] = []

    known = data.get("known")
    if isinstance(known, dict):
        data["known"] = _coerce_known(known)

    data["assumptions"] = _coerce_assumptions(data.get("assumptions"))
    data["unknowns"] = _coerce_unknowns(data.get("unknowns"))
    return data


def _as_int(value: Any, *, lo: int | None = None, hi: int | None = None) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        n = value
    elif isinstance(value, float) and value.is_integer():
        n = int(value)
    elif isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            n = int(float(s))
        except ValueError:
            return None
    else:
        return None
    if lo is not None and n < lo:
        return None
    if hi is not None and n > hi:
        return None
    return n


def _as_float(
    value: Any, *, lo: float | None = None, hi: float | None = None
) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        x = float(value)
    elif isinstance(value, str):
        s = value.strip().rstrip("米mM")
        if not s:
            return None
        try:
            x = float(s)
        except ValueError:
            return None
    else:
        return None
    if lo is not None and x < lo:
        return None
    if hi is not None and x > hi:
        return None
    return x


def _as_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ("true", "yes", "y", "1", "是", "要", "有"):
            return True
        if s in ("false", "no", "n", "0", "否", "不要", "无"):
            return False
    return None


def _coerce_known(known: dict[str, Any]) -> dict[str, Any]:
    out = dict(known)
    if "floor_count" in out:
        out["floor_count"] = _as_int(out["floor_count"], lo=1, hi=3)

    site = out.get("site")
    if isinstance(site, dict):
        s = dict(site)
        if "width" in s:
            s["width"] = _as_float(s["width"], lo=6, hi=60)
        if "depth" in s:
            s["depth"] = _as_float(s["depth"], lo=6, hi=60)
        out["site"] = s
    elif site is None:
        out["site"] = {}

    hh = out.get("household")
    if isinstance(hh, dict):
        h = dict(hh)
        if "occupants" in h:
            h["occupants"] = _as_int(h["occupants"], lo=1, hi=20)
        if "bedrooms" in h:
            h["bedrooms"] = _as_int(h["bedrooms"], lo=1, hi=10)
        if "bathrooms" in h:
            h["bathrooms"] = _as_int(h["bathrooms"], lo=1, hi=8)
        if "has_garage" in h:
            h["has_garage"] = _as_bool(h["has_garage"])
        out["household"] = h
    elif hh is None:
        out["household"] = {}

    prefs = out.get("preferences")
    if isinstance(prefs, dict):
        p = dict(prefs)
        for key in (
            "prefer_south_facing_living",
            "prefer_open_kitchen_dining",
            "prefer_compact_footprint",
            "prefer_short_corridor",
            "quiet_zone_away_from_entry",
            "wet_stack_preference",
        ):
            if key in p:
                p[key] = _as_bool(p[key])
        out["preferences"] = p
    elif prefs is None:
        out["preferences"] = {}

    out["spaces"] = _coerce_spaces(out.get("spaces"))
    out["relation_intents"] = _coerce_relations(out.get("relation_intents"))
    return out


def _coerce_floor_pref(item: Any) -> str | None:
    if item is None:
        return None
    s = str(item).strip().upper().replace(" ", "")
    if not s:
        return None
    if s in ("F1", "F2", "F3"):
        return s
    mapping = {
        "1": "F1",
        "2": "F2",
        "3": "F3",
        "一层": "F1",
        "二层": "F2",
        "三层": "F3",
        "楼下": "F1",
        "首层": "F1",
    }
    # 中文未 upper
    raw = str(item).strip()
    if raw in mapping:
        return mapping[raw]
    if s in mapping:
        return mapping[s]
    return None


def _coerce_orientation(value: Any) -> str | None:
    if value is None or value == "":
        return None
    key = str(value).strip().lower()
    if key in _ORIENT_ALIASES:
        return _ORIENT_ALIASES[key]
    raw = str(value).strip()
    if raw in _ORIENT_ALIASES:
        return _ORIENT_ALIASES[raw]
    return None


def _coerce_spaces(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            name = item.strip()
            if name:
                out.append({"name": name})
            continue
        if not isinstance(item, dict):
            continue
        sp = dict(item)
        name = sp.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        sp["name"] = name.strip()
        if "target_area" in sp:
            sp["target_area"] = _as_float(sp["target_area"], lo=0.01)
        if "min_width" in sp:
            sp["min_width"] = _as_float(sp["min_width"], lo=0.01)
        prefs = sp.get("floor_preference")
        if isinstance(prefs, str):
            prefs = [prefs]
        if isinstance(prefs, list):
            cleaned = [p for p in (_coerce_floor_pref(x) for x in prefs) if p]
            sp["floor_preference"] = cleaned
        if "preferred_orientation" in sp:
            ori = _coerce_orientation(sp.get("preferred_orientation"))
            if ori is None:
                sp.pop("preferred_orientation", None)
            else:
                sp["preferred_orientation"] = ori
        out.append(sp)
    return out


def _coerce_relations(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        a = item.get("a")
        b = item.get("b")
        if not isinstance(a, str) or not a.strip():
            continue
        if not isinstance(b, str) or not b.strip():
            continue
        kind_raw = item.get("kind", "adjacency")
        kind_key = str(kind_raw).strip().lower() if kind_raw is not None else "adjacency"
        kind = _KIND_ALIASES.get(kind_key) or _KIND_ALIASES.get(str(kind_raw).strip())
        if kind is None or kind not in _VALID_RELATION_KINDS:
            # 无法识别的 kind：丢弃该项（precision-first），不整份 draft 失败
            continue
        strength = item.get("strength", "preferred")
        if strength not in ("required", "preferred"):
            strength = "preferred"
        rel: dict[str, Any] = {
            "a": a.strip(),
            "b": b.strip(),
            "kind": kind,
            "strength": strength,
        }
        note = item.get("note")
        if isinstance(note, str):
            rel["note"] = note
        out.append(rel)
    return out


def _coerce_assumptions(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if not isinstance(key, str) or not key.strip():
            continue
        if "value" not in item or item["value"] is None:
            continue
        a = dict(item)
        a["key"] = key.strip()
        if not isinstance(a.get("reason"), str) or not a["reason"].strip():
            a["reason"] = "（模型未提供理由）"
        src = a.get("source")
        if src not in ("user_authorized", "planseed_default", "llm_inference"):
            a["source"] = "llm_inference"
        out.append(a)
    return out


def _coerce_unknowns(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            key = item.strip()
            if key:
                out.append({"key": key, "description": ""})
            continue
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if not isinstance(key, str) or not key.strip():
            continue
        u = dict(item)
        u["key"] = key.strip()
        if not isinstance(u.get("description"), str):
            u["description"] = ""
        pri = u.get("priority")
        if pri not in ("blocking", "recommended", "optional"):
            u["priority"] = "recommended"
        out.append(u)
    return out
