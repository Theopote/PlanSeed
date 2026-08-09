"""Phase 7.2.2 — Canonical SVG → PNG（resvg；非 HTML 截图）。"""

from __future__ import annotations

import io
import re
import struct
import zipfile
from dataclasses import dataclass
from typing import Any, Literal
from xml.etree import ElementTree as ET

import resvg_py

from backend.services.export.svg_exporter import (
    SvgExportError,
    resolve_svg_bytes,
    sanitize_export_filename,
)
from backend.services.report_svg_sanitize import SvgSanitizeError, sanitize_report_svg

PngScope = Literal["floor", "snapshot", "all_floors"]

ALLOWED_PNG_SIZES: frozenset[int] = frozenset({2048, 4096})

_VIEWBOX_RE = re.compile(
    r"viewBox\s*=\s*[\"']\s*([-\d.eE+]+)\s+([-\d.eE+]+)\s+"
    r"([-\d.eE+]+)\s+([-\d.eE+]+)\s*[\"']",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PngExportResult:
    body: bytes
    media_type: str
    filename: str
    width: int
    height: int


def parse_svg_aspect(svg: str) -> tuple[float, float]:
    """从 viewBox 或 width/height 取宽高比；失败则 1:1。"""
    m = _VIEWBOX_RE.search(svg)
    if m:
        w = abs(float(m.group(3)))
        h = abs(float(m.group(4)))
        if w > 0 and h > 0:
            return w, h
    try:
        root = ET.fromstring(svg)
    except ET.ParseError:
        return 1.0, 1.0
    def _num(raw: str | None) -> float | None:
        if not raw:
            return None
        s = raw.strip().removesuffix("px").removesuffix("pt").strip()
        try:
            v = float(s)
        except ValueError:
            return None
        return v if v > 0 else None

    aw = _num(root.attrib.get("width"))
    ah = _num(root.attrib.get("height"))
    if aw is not None and ah is not None:
        return aw, ah
    return 1.0, 1.0


def fit_pixel_size(svg: str, max_px: int) -> tuple[int, int]:
    """最长边 = max_px，保持比例。"""
    if max_px not in ALLOWED_PNG_SIZES:
        raise SvgExportError(
            "invalid_size",
            f"PNG 边长仅支持 {sorted(ALLOWED_PNG_SIZES)}，收到 {max_px}",
        )
    aw, ah = parse_svg_aspect(svg)
    if aw >= ah:
        w = max_px
        h = max(1, round(max_px * ah / aw))
    else:
        h = max_px
        w = max(1, round(max_px * aw / ah))
    return w, h


def rasterize_svg_to_png(svg: str, *, max_px: int) -> tuple[bytes, int, int]:
    """白底光栅化；确定性：同 SVG + max_px → 同像素尺寸。"""
    try:
        clean = sanitize_report_svg(svg)
    except SvgSanitizeError as exc:
        raise SvgExportError("svg_sanitize_failed", str(exc)) from exc
    width, height = fit_pixel_size(clean, max_px)
    try:
        png = resvg_py.svg_to_bytes(
            svg_string=clean,
            width=width,
            height=height,
            background="#ffffff",
        )
    except ValueError as exc:
        raise SvgExportError("png_rasterize_failed", str(exc)) from exc
    raw = bytes(png)
    if raw[:8] != b"\x89PNG\r\n\x1a\n" or len(raw) < 24:
        raise SvgExportError("png_rasterize_failed", "光栅化未返回有效 PNG")
    out_w, out_h = struct.unpack(">II", raw[16:24])
    return raw, int(out_w), int(out_h)


def export_single_png(
    candidate: dict[str, Any],
    *,
    scope: PngScope,
    floor_id: str | None,
    project_name: str,
    candidate_label: str,
    size: int,
) -> PngExportResult:
    if scope == "all_floors":
        raise SvgExportError("invalid_scope", "单文件 PNG 不支持 all_floors")
    raw, suffix = resolve_svg_bytes(candidate, scope=scope, floor_id=floor_id)
    body, width, height = rasterize_svg_to_png(raw, max_px=size)
    proj = sanitize_export_filename(project_name)
    label = sanitize_export_filename(candidate_label or "A")
    filename = f"{proj}_{label}_{suffix}_{size}.png"
    return PngExportResult(
        body=body,
        media_type="image/png",
        filename=filename,
        width=width,
        height=height,
    )


def export_all_floors_png_zip(
    candidate: dict[str, Any],
    *,
    project_name: str,
    candidate_label: str,
    size: int,
) -> PngExportResult:
    floors = candidate.get("floor_svgs")
    if not isinstance(floors, dict) or not floors:
        raise SvgExportError(
            "floor_not_found",
            "候选无 floor_svgs，无法导出全部楼层 PNG",
        )
    if size not in ALLOWED_PNG_SIZES:
        raise SvgExportError(
            "invalid_size",
            f"PNG 边长仅支持 {sorted(ALLOWED_PNG_SIZES)}，收到 {size}",
        )
    proj = sanitize_export_filename(project_name)
    label = sanitize_export_filename(candidate_label or "A")
    buf = io.BytesIO()
    last_w, last_h = 0, 0
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fid in sorted(str(k) for k in floors.keys()):
            raw = floors.get(fid)
            if not isinstance(raw, str) or not raw.strip():
                continue
            body, last_w, last_h = rasterize_svg_to_png(raw, max_px=size)
            safe_fid = sanitize_export_filename(fid)
            zf.writestr(f"{proj}_{label}_{safe_fid}_{size}.png", body)
    data = buf.getvalue()
    if not data:
        raise SvgExportError("floor_not_found", "没有可导出的楼层 PNG")
    return PngExportResult(
        body=data,
        media_type="application/zip",
        filename=f"{proj}_{label}_floors_{size}.png.zip",
        width=last_w,
        height=last_h,
    )


def export_png(
    candidate: dict[str, Any],
    *,
    scope: PngScope,
    floor_id: str | None,
    project_name: str,
    candidate_label: str,
    size: int,
) -> PngExportResult:
    if scope == "all_floors":
        return export_all_floors_png_zip(
            candidate,
            project_name=project_name,
            candidate_label=candidate_label,
            size=size,
        )
    return export_single_png(
        candidate,
        scope=scope,
        floor_id=floor_id,
        project_name=project_name,
        candidate_label=candidate_label,
        size=size,
    )
