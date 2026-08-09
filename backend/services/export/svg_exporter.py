"""Phase 7.2.1 — Canonical SVG 导出（不重渲几何）。"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from typing import Any, Literal

from backend.services.report_svg_sanitize import SvgSanitizeError, sanitize_report_svg

SvgScope = Literal["floor", "snapshot", "all_floors"]


class SvgExportError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class SvgExportResult:
    """单文件或 zip 字节。"""

    body: bytes
    media_type: str
    filename: str


_UNSAFE = re.compile(r"[^\w\-.\u4e00-\u9fff]+", re.UNICODE)


def sanitize_export_filename(name: str, *, max_len: int = 80) -> str:
    """文件名安全化：保留字母数字、中文、._-。"""
    s = (name or "").strip() or "Untitled"
    s = _UNSAFE.sub("_", s)
    s = s.strip("._") or "Untitled"
    return s[:max_len]


def content_disposition_attachment(filename: str) -> str:
    """RFC 5987：中文文件名不可直接放 latin-1 header。"""
    from urllib.parse import quote

    safe = (filename or "export.bin").replace("\r", "").replace("\n", "")
    ascii_name = (
        safe.encode("ascii", "ignore").decode("ascii").replace('"', "")
        or "export.bin"
    )
    return (
        f'attachment; filename="{ascii_name}"; '
        f"filename*=UTF-8''{quote(safe, safe='')}"
    )


def resolve_svg_bytes(
    candidate: dict[str, Any],
    *,
    scope: SvgScope,
    floor_id: str | None,
) -> tuple[str, str]:
    """
    从 canonical candidate 取 SVG 原文（尚未 sanitize）。

    返回 (raw_svg, stem_suffix) — stem_suffix 如 F1 / ALL / floors。
    """
    if scope == "snapshot":
        raw = candidate.get("svg")
        if not isinstance(raw, str) or not raw.strip():
            raise SvgExportError(
                "svg_missing",
                "候选缺少整图 svg（Candidate Snapshot）",
            )
        return raw, "ALL"

    if scope == "floor":
        fid = (floor_id or "").strip()
        if not fid:
            raise SvgExportError("floor_id_required", "导出单层须提供 floor_id")
        floors = candidate.get("floor_svgs")
        if not isinstance(floors, dict) or fid not in floors:
            raise SvgExportError(
                "floor_not_found",
                f"候选无楼层 SVG：{fid}",
            )
        raw = floors[fid]
        if not isinstance(raw, str) or not raw.strip():
            raise SvgExportError(
                "floor_not_found",
                f"楼层 SVG 为空：{fid}",
            )
        return raw, fid

    # all_floors — 由 export_svg_package 处理
    raise SvgExportError("invalid_scope", "all_floors 请用 export_svg_package")


def export_single_svg(
    candidate: dict[str, Any],
    *,
    scope: SvgScope,
    floor_id: str | None,
    project_name: str,
    candidate_label: str,
) -> SvgExportResult:
    if scope == "all_floors":
        raise SvgExportError("invalid_scope", "单文件导出不支持 all_floors")
    raw, suffix = resolve_svg_bytes(candidate, scope=scope, floor_id=floor_id)
    try:
        clean = sanitize_report_svg(raw)
    except SvgSanitizeError as exc:
        raise SvgExportError("svg_sanitize_failed", str(exc)) from exc
    proj = sanitize_export_filename(project_name)
    label = sanitize_export_filename(candidate_label or "A")
    filename = f"{proj}_{label}_{suffix}.svg"
    return SvgExportResult(
        body=clean.encode("utf-8"),
        media_type="image/svg+xml; charset=utf-8",
        filename=filename,
    )


def export_all_floors_zip(
    candidate: dict[str, Any],
    *,
    project_name: str,
    candidate_label: str,
) -> SvgExportResult:
    floors = candidate.get("floor_svgs")
    if not isinstance(floors, dict) or not floors:
        raise SvgExportError(
            "floor_not_found",
            "候选无 floor_svgs，无法导出全部楼层",
        )
    proj = sanitize_export_filename(project_name)
    label = sanitize_export_filename(candidate_label or "A")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fid in sorted(str(k) for k in floors.keys()):
            raw = floors.get(fid)
            if not isinstance(raw, str) or not raw.strip():
                continue
            try:
                clean = sanitize_report_svg(raw)
            except SvgSanitizeError as exc:
                raise SvgExportError(
                    "svg_sanitize_failed",
                    f"{fid}: {exc}",
                ) from exc
            safe_fid = sanitize_export_filename(fid)
            zf.writestr(f"{proj}_{label}_{safe_fid}.svg", clean.encode("utf-8"))
    data = buf.getvalue()
    if not data:
        raise SvgExportError("floor_not_found", "没有可导出的楼层 SVG")
    return SvgExportResult(
        body=data,
        media_type="application/zip",
        filename=f"{proj}_{label}_floors.svg.zip",
    )


def export_svg(
    candidate: dict[str, Any],
    *,
    scope: SvgScope,
    floor_id: str | None,
    project_name: str,
    candidate_label: str,
) -> SvgExportResult:
    if scope == "all_floors":
        return export_all_floors_zip(
            candidate,
            project_name=project_name,
            candidate_label=candidate_label,
        )
    return export_single_svg(
        candidate,
        scope=scope,
        floor_id=floor_id,
        project_name=project_name,
        candidate_label=candidate_label,
    )
