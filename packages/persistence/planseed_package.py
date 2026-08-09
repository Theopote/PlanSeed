"""Phase 7.5-D — `.planseed` 项目包（ZIP 包装层，不改设计算法）。

布局::

    manifest.json
    project.json
    assets/      （可选二进制资源）
    previews/    （可选预览图）

manifest.format 固定为 ``planseed-project``。
"""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

PLANSEED_FORMAT = "planseed-project"
PLANSEED_PACKAGE_VERSION = 1
PLANSEED_EXTENSION = ".planseed"

_SAFE_REL = re.compile(r"^[A-Za-z0-9._\-]+(/[A-Za-z0-9._\-]+)*$")


class PlanseedPackageError(ValueError):
    """包格式 / 内容错误。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass
class PlanseedManifest:
    format: str
    version: int
    app_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "version": self.version,
            "app_version": self.app_version,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> PlanseedManifest:
        fmt = raw.get("format")
        if fmt != PLANSEED_FORMAT:
            raise PlanseedPackageError(
                "invalid_format",
                f"期望 format={PLANSEED_FORMAT!r}，收到 {fmt!r}",
            )
        ver = raw.get("version")
        if not isinstance(ver, int) or ver < 1:
            raise PlanseedPackageError(
                "invalid_version",
                f"manifest.version 须为正整数，收到 {ver!r}",
            )
        if ver > PLANSEED_PACKAGE_VERSION:
            raise PlanseedPackageError(
                "unsupported_version",
                f"包版本 {ver} 高于本机支持的 {PLANSEED_PACKAGE_VERSION}",
            )
        app = raw.get("app_version")
        if not isinstance(app, str) or not app.strip():
            raise PlanseedPackageError(
                "invalid_app_version",
                "manifest.app_version 须为非空字符串",
            )
        return cls(format=fmt, version=ver, app_version=app.strip())


@dataclass
class PlanseedBundle:
    """解包结果：manifest + 项目行 + 可选资源。"""

    manifest: PlanseedManifest
    project: dict[str, Any]
    assets: dict[str, bytes] = field(default_factory=dict)
    previews: dict[str, bytes] = field(default_factory=dict)

    @property
    def project_id(self) -> str:
        return str(self.project["id"])

    @property
    def name(self) -> str:
        return str(self.project["name"])

    @property
    def payload(self) -> dict[str, Any]:
        return dict(self.project["payload"])


def _require_project_row(row: dict[str, Any]) -> dict[str, Any]:
    for key in ("id", "name", "updated_at", "payload"):
        if key not in row:
            raise PlanseedPackageError(
                "invalid_project",
                f"project.json 缺少字段：{key}",
            )
    if not isinstance(row["id"], str) or not row["id"].strip():
        raise PlanseedPackageError("invalid_project", "project.id 无效")
    if not isinstance(row["name"], str) or not row["name"].strip():
        raise PlanseedPackageError("invalid_project", "project.name 无效")
    if not isinstance(row["updated_at"], str):
        raise PlanseedPackageError("invalid_project", "project.updated_at 无效")
    if not isinstance(row["payload"], dict):
        raise PlanseedPackageError("invalid_project", "project.payload 须为对象")
    return {
        "id": row["id"].strip(),
        "name": row["name"].strip(),
        "updated_at": row["updated_at"],
        "payload": row["payload"],
    }


def _safe_member(name: str) -> str:
    """拒绝 Zip Slip；归一为正斜杠相对路径。"""
    n = name.replace("\\", "/").lstrip("/")
    if not n or n.endswith("/"):
        return ""
    if ".." in n.split("/"):
        raise PlanseedPackageError("unsafe_path", f"非法路径：{name}")
    if n.startswith(("assets/", "previews/")):
        rest = n.split("/", 1)[1]
        if rest and not _SAFE_REL.match(rest):
            raise PlanseedPackageError("unsafe_path", f"非法资源名：{name}")
        return n
    if n in ("manifest.json", "project.json"):
        return n
    raise PlanseedPackageError("unexpected_entry", f"未知条目：{name}")


def pack_planseed(
    *,
    project_id: str,
    name: str,
    updated_at: str,
    payload: dict[str, Any],
    app_version: str,
    assets: dict[str, bytes] | None = None,
    previews: dict[str, bytes] | None = None,
    package_version: int = PLANSEED_PACKAGE_VERSION,
) -> bytes:
    """打包为 `.planseed` ZIP 字节。"""
    manifest = PlanseedManifest(
        format=PLANSEED_FORMAT,
        version=package_version,
        app_version=app_version,
    )
    row = _require_project_row(
        {
            "id": project_id,
            "name": name,
            "updated_at": updated_at,
            "payload": payload,
        }
    )
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "manifest.json",
            json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2) + "\n",
        )
        zf.writestr(
            "project.json",
            json.dumps(row, ensure_ascii=False, indent=2) + "\n",
        )
        # 目录占位，便于解压后可见结构
        zf.writestr("assets/", "")
        zf.writestr("previews/", "")
        for rel, data in (assets or {}).items():
            path = _safe_member(f"assets/{rel.lstrip('/')}")
            if path:
                zf.writestr(path, data)
        for rel, data in (previews or {}).items():
            path = _safe_member(f"previews/{rel.lstrip('/')}")
            if path:
                zf.writestr(path, data)
    return buf.getvalue()


def unpack_planseed(data: bytes) -> PlanseedBundle:
    """从 ZIP 字节解包；校验 format / version。"""
    if not data:
        raise PlanseedPackageError("empty_package", "空文件")
    try:
        zf = zipfile.ZipFile(BytesIO(data), "r")
    except zipfile.BadZipFile as e:
        raise PlanseedPackageError("not_zip", "不是有效的 ZIP / .planseed") from e

    with zf:
        names = zf.namelist()
        if "manifest.json" not in names:
            raise PlanseedPackageError("missing_manifest", "缺少 manifest.json")
        if "project.json" not in names:
            raise PlanseedPackageError("missing_project", "缺少 project.json")

        try:
            manifest_raw = json.loads(zf.read("manifest.json").decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise PlanseedPackageError(
                "bad_manifest",
                "manifest.json 无法解析",
            ) from e
        if not isinstance(manifest_raw, dict):
            raise PlanseedPackageError("bad_manifest", "manifest.json 须为对象")
        manifest = PlanseedManifest.from_dict(manifest_raw)

        try:
            project_raw = json.loads(zf.read("project.json").decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise PlanseedPackageError(
                "bad_project",
                "project.json 无法解析",
            ) from e
        if not isinstance(project_raw, dict):
            raise PlanseedPackageError("bad_project", "project.json 须为对象")
        project = _require_project_row(project_raw)

        assets: dict[str, bytes] = {}
        previews: dict[str, bytes] = {}
        for name in names:
            path = _safe_member(name)
            if not path or path in ("manifest.json", "project.json"):
                continue
            blob = zf.read(name)
            if path.startswith("assets/"):
                assets[path.removeprefix("assets/")] = blob
            elif path.startswith("previews/"):
                previews[path.removeprefix("previews/")] = blob

    return PlanseedBundle(
        manifest=manifest,
        project=project,
        assets=assets,
        previews=previews,
    )


def suggest_filename(project_name: str) -> str:
    """导出文件名建议。"""
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", (project_name or "").strip())
    stem = stem.strip(" .") or "project"
    if len(stem) > 80:
        stem = stem[:80].rstrip(" .")
    return f"{stem}{PLANSEED_EXTENSION}"


def write_planseed_file(path: Path | str, data: bytes) -> Path:
    out = Path(path)
    out.write_bytes(data)
    return out


def read_planseed_file(path: Path | str) -> PlanseedBundle:
    return unpack_planseed(Path(path).read_bytes())
