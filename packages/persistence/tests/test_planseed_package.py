"""Phase 7.5-D — .planseed 包单测。"""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from packages.persistence.planseed_package import (
    PLANSEED_FORMAT,
    PLANSEED_PACKAGE_VERSION,
    PlanseedPackageError,
    pack_planseed,
    suggest_filename,
    unpack_planseed,
)


def test_pack_unpack_roundtrip():
    raw = pack_planseed(
        project_id="p1",
        name="示范宅",
        updated_at="2026-01-01T00:00:00+00:00",
        payload={"form": {"width": 12}, "selected_id": "c1"},
        app_version="0.1.0",
        assets={"note.txt": b"hello"},
        previews={"thumb.png": b"\x89PNG"},
    )
    bundle = unpack_planseed(raw)
    assert bundle.manifest.format == PLANSEED_FORMAT
    assert bundle.manifest.version == PLANSEED_PACKAGE_VERSION
    assert bundle.project_id == "p1"
    assert bundle.name == "示范宅"
    assert bundle.payload["form"]["width"] == 12
    assert bundle.assets["note.txt"] == b"hello"
    assert bundle.previews["thumb.png"] == b"\x89PNG"

    with zipfile.ZipFile(BytesIO(raw)) as zf:
        names = set(zf.namelist())
    assert "manifest.json" in names
    assert "project.json" in names
    assert "assets/" in names
    assert "previews/" in names


def test_reject_wrong_format():
    raw = pack_planseed(
        project_id="p1",
        name="x",
        updated_at="t",
        payload={},
        app_version="0.1.0",
    )
    # 篡改 manifest
    with zipfile.ZipFile(BytesIO(raw), "r") as zin:
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename == "manifest.json":
                    data = b'{"format":"other","version":1,"app_version":"0.1.0"}\n'
                zout.writestr(info, data)
        bad = buf.getvalue()
    with pytest.raises(PlanseedPackageError) as ei:
        unpack_planseed(bad)
    assert ei.value.code == "invalid_format"


def test_reject_zip_slip():
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "manifest.json",
            '{"format":"planseed-project","version":1,"app_version":"0.1.0"}\n',
        )
        zf.writestr(
            "project.json",
            '{"id":"p","name":"n","updated_at":"t","payload":{}}\n',
        )
        zf.writestr("../evil.txt", b"nope")
    with pytest.raises(PlanseedPackageError) as ei:
        unpack_planseed(buf.getvalue())
    assert ei.value.code == "unsafe_path"


def test_suggest_filename():
    assert suggest_filename("My House").endswith(".planseed")
    assert "/" not in suggest_filename('a/b<>c')
    assert suggest_filename("").startswith("project")


def test_write_read_file(tmp_path: Path):
    from packages.persistence.planseed_package import read_planseed_file, write_planseed_file

    raw = pack_planseed(
        project_id="p2",
        name="file-test",
        updated_at="t",
        payload={"form": {}},
        app_version="0.1.0",
    )
    path = write_planseed_file(tmp_path / "x.planseed", raw)
    bundle = read_planseed_file(path)
    assert bundle.project_id == "p2"
