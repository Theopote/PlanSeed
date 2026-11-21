"""从 design-benchmark 自动 findings 生成 agent-draft 评级（非建筑师签章）。

规则（保守）：
- 暗卫（非洗衣）/ 入口未进公区+意图弱 / 多重卧室深访问 → C
- 其余 valid → B（穿室、进深等可改）
- invalid 不写入（合并时仍为 D）

用法：
  uv run python scripts/draft_ab_grades_from_findings.py \\
    --report debug/design-benchmark-v2/auto_rerun_for_ab.json \\
    --out debug/design-benchmark-v2/review-ab-rerate/grades-agent-draft.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def grade_valid(c: dict) -> tuple[str, str]:
    ids = [str(f.get("id") or "") for f in (c.get("findings_summary") or [])]
    soft = set(ids)
    notes: list[str] = []
    black = [x for x in ids if "black_wet" in x and "laundry" not in x]
    black_laundry = [x for x in ids if "black_wet" in x and "laundry" in x]
    deep_priv = [x for x in ids if x.startswith("privacy.deep_access")]
    through_room = "circulation.through_room" in soft
    entry_bad = "circulation.entry_not_public" in soft
    intent_weak = "circulation.intent_weak" in soft
    deep_rooms = "circulation.deep_rooms" in soft
    slender = "spatial.slender_rooms" in soft

    if black:
        notes.append("暗卫:" + ",".join(black[:2]))
        return "C", "; ".join(notes)
    if entry_bad and intent_weak:
        notes.append("入口未进公区+流线意图弱")
        if len(deep_priv) >= 2:
            notes.append(f"深访问卧室x{len(deep_priv)}")
        return "C", "; ".join(notes)
    if len(deep_priv) >= 3:
        notes.append(f"深访问卧室x{len(deep_priv)}")
        if through_room:
            notes.append("穿室")
        return "C", "; ".join(notes)
    if len(deep_priv) >= 2 and (deep_rooms or through_room):
        notes.append(f"深访问x{len(deep_priv)}+流线问题")
        return "C", "; ".join(notes)
    if black_laundry and (deep_priv or slender):
        notes.append("洗衣间暗室+其它问题")
        return "C", "; ".join(notes)

    if black_laundry:
        notes.append("洗衣间暗室")
    if through_room:
        notes.append("穿室交通")
    if deep_rooms:
        notes.append("房间进深大")
    if slender:
        notes.append("细长房间")
    if not notes:
        notes.append("valid 软问题少")
    return "B", "; ".join(notes)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))

    grades: dict[str, dict] = {}
    counts = {k: 0 for k in "ABCD"}
    for case in report.get("cases") or []:
        cid = case["case_id"]
        grades[cid] = {}
        for c in case.get("candidates") or []:
            if not c.get("valid"):
                continue
            g, notes = grade_valid(c)
            counts[g] += 1
            idx = str(c["index"])
            grades[cid][idx] = {
                "grade": g,
                "notes": notes,
                "svg": f"{cid}/candidate_{int(idx):03d}.svg",
            }

    ab = sum(
        1
        for cid in grades
        for v in grades[cid].values()
        if v["grade"] in ("A", "B")
    )
    all_n = sum(int(case.get("candidate_count") or 0) for case in report["cases"])
    out = {
        "suite": "design-benchmark-v2",
        "suite_version": report.get("suite_version", "v2"),
        "candidate_count": report.get("candidate_count", 32),
        "reviewer": "agent-draft",
        "reviewed_at": "2026-11-21",
        "notes": (
            "证据驱动草案（findings 规则）；非建筑师签章。"
            f" valid 内 AB={ab}；相对全部候选 ab_rate≈{ab / max(1, all_n):.4f}。"
            " 待人工复核后替换 reviewer。"
        ),
        "grades": grades,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {args.out}")
    print("valid grade counts", counts)
    print(f"draft ab_rate (AB/all) = {ab}/{all_n} = {ab / max(1, all_n):.4f}")


if __name__ == "__main__":
    main()
