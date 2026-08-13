"""验证 Desktop Gate C 预制 .planseed 包（导入前静态检查）。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "debug" / "desktop-hand-gate" / "alpha-v0.1-hand-gate.planseed"


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    if not path.is_file():
        print(f"FAIL: missing {path}")
        return 1

    from packages.persistence.planseed_package import unpack_planseed
    from packages.schema.identity import EVALUATION_VERSION, SELECTION_VERSION

    bundle = unpack_planseed(path.read_bytes())
    payload = bundle.payload
    errors: list[str] = []

    if not payload.get("requirement_spec"):
        errors.append("missing requirement_spec")
    if not payload.get("program"):
        errors.append("missing program")
    cands = payload.get("candidates") or []
    if not cands:
        errors.append("missing candidates")
    else:
        c0 = cands[0]
        prov = c0.get("provenance") or {}
        if prov.get("generator_strategy") != "guillotine":
            errors.append(f"provenance.generator_strategy={prov.get('generator_strategy')!r}")
        if prov.get("selection_strategy") != "axis-diverse":
            errors.append(f"provenance.selection_strategy={prov.get('selection_strategy')!r}")
        if prov.get("evaluation_version") != EVALUATION_VERSION:
            errors.append(f"provenance.evaluation_version={prov.get('evaluation_version')!r}")
        if not c0.get("revision_id"):
            errors.append("missing revision_id")
        locks = payload.get("locks") or {}
        if not (locks.get("rooms") or []):
            errors.append("locks.rooms empty")
        if not (c0.get("mutations") or []):
            errors.append("mutations empty")

    sv = payload.get("schema_versions") or {}
    if sv.get("geometry_backend") != "rect":
        errors.append(f"schema_versions.geometry_backend={sv.get('geometry_backend')!r}")
    if sv.get("selection_version") != SELECTION_VERSION:
        errors.append(f"schema_versions.selection_version={sv.get('selection_version')!r}")

    if errors:
        print(f"FAIL: {path}")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"OK: hand-gate fixture {path.name}")
    print(f"  candidates={len(cands)} locks={len((payload.get('locks') or {}).get('rooms') or [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
