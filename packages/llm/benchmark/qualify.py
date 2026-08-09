"""Phase 6.7 — Real Model Qualification 入口。

用法（本机 Ollama 就绪后）::

    uv run python -m packages.llm.benchmark.qualify
    uv run python -m packages.llm.benchmark.qualify --limit 3
    uv run python -m packages.llm.benchmark.qualify --gate
    # 多模型对比（判断 7B 是否够用，非排行榜）
    uv run python -m packages.llm.benchmark.qualify --models qwen2.5:7b,qwen2.5:14b

环境变量：
- PLANSEED_OLLAMA_*（见 factory）
- PLANSEED_LLM_QUALIFY_LIMIT：可选，只跑前 N 条（冒烟）
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import replace
from pathlib import Path

from packages.llm.benchmark.cases import load_benchmark_cases
from packages.llm.benchmark.gates import evaluate_alpha_gates
from packages.llm.benchmark.report import BenchmarkReport
from packages.llm.benchmark.runner import run_benchmark
from packages.llm.draft_schema import draft_json_schema
from packages.llm.factory import load_ollama_config
from packages.llm.ollama import OllamaProvider


def _make_provider(model: str) -> OllamaProvider:
    """按模型名新建 Provider（不复用共享 runtime，便于多模型对比）。"""
    cfg = replace(
        load_ollama_config(),
        model=model,
        response_format=draft_json_schema(),
    )
    return OllamaProvider(cfg)


def run_real_model_qualification(
    *,
    model: str | None = None,
    limit: int | None = None,
    with_repair: bool = True,
) -> BenchmarkReport:
    """对语料跑真模型（非 oracle），产出 Alpha Baseline 指标。"""
    cases = load_benchmark_cases()
    if limit is not None:
        cases = cases[:limit]
    cfg = load_ollama_config()
    resolved = (model or cfg.model).strip()
    provider = _make_provider(resolved)
    try:
        return run_benchmark(
            provider=provider,
            cases=cases,
            use_oracle=False,
            with_repair=with_repair,
            mode="real",
            model=resolved,
        )
    finally:
        provider.close()


def _failed_cases_payload(report: BenchmarkReport) -> list[dict]:
    return [
        {
            "id": c.case_id,
            "hallucinations": c.hallucinations,
            "notes": c.notes,
            "parse_failed": c.parse_failed,
            "geometry_fail": c.geometry_fail,
            "failure_kind": c.failure_kind.value if c.failure_kind else None,
            "repair_exhausted": c.repair_exhausted,
            "attempts": c.attempts,
            "latency_s": round(c.latency_s, 3),
        }
        for c in report.case_scores
        if not c.passed
    ]


def _write_baseline(
    report: BenchmarkReport,
    *,
    out_path: Path,
    gate: dict | None = None,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "note": (
            "LLM Alpha Baseline（真模型）。"
            "勿与 CI oracle 100% 混淆：oracle 只验证 harness。"
            "Phase 6 ✅ Alpha Qualified 仅当 Alpha Gate 全部通过。"
        ),
        "summary": report.summary(),
        "alpha_gate": gate,
        "failed_cases": _failed_cases_payload(report),
    }
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _parse_models(raw: str | None, default: str) -> list[str]:
    if not raw or not raw.strip():
        return [default]
    parts = [p.strip() for p in raw.split(",")]
    return [p for p in parts if p]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PlanSeed Phase 6.7 — Real Model Qualification",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="只跑前 N 条（冒烟）",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="单个模型（覆盖 PLANSEED_OLLAMA_MODEL）",
    )
    parser.add_argument(
        "--models",
        type=str,
        default=None,
        help="逗号分隔多模型对比，例：qwen2.5:7b,qwen2.5:14b",
    )
    parser.add_argument(
        "--gate",
        action="store_true",
        help="Alpha Gate 未通过时以非零退出（判定 Alpha Qualified）",
    )
    args = parser.parse_args(argv)

    limit_env = os.environ.get("PLANSEED_LLM_QUALIFY_LIMIT", "").strip()
    limit = args.limit
    if limit is None and limit_env.isdigit():
        limit = int(limit_env)

    cfg = load_ollama_config()
    models = _parse_models(args.models, args.model or cfg.model)

    print("PlanSeed Phase 6.7 — Real Model Qualification", flush=True)
    print(
        f"base_url={cfg.base_url} timeout_s={cfg.timeout_s} models={models}",
        flush=True,
    )
    if limit is not None:
        print(f"limit={limit}", flush=True)

    out_dir = Path("docs") / "baselines"
    compare_rows: list[dict] = []
    all_gates_ok = True

    for model in models:
        print(f"\n=== model={model} ===", flush=True)
        report = run_real_model_qualification(
            model=model,
            limit=limit,
            with_repair=True,
        )
        summary = report.summary()
        gate = evaluate_alpha_gates(report)
        gate_dict = gate.to_dict()
        print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
        print(
            json.dumps({"alpha_gate": gate_dict}, ensure_ascii=False, indent=2),
            flush=True,
        )
        if not gate.passed:
            all_gates_ok = False
            failed = [c.label for c in gate.checks if not c.passed]
            print(f"Alpha Gate FAIL: {', '.join(failed)}", flush=True)
        else:
            print("Alpha Gate PASS", flush=True)

        safe_name = model.replace(":", "_").replace("/", "_")
        if len(models) == 1:
            out_path = out_dir / "llm-alpha-baseline.json"
        else:
            out_path = out_dir / f"llm-alpha-baseline-{safe_name}.json"
        _write_baseline(report, out_path=out_path, gate=gate_dict)
        print(f"wrote {out_path}", flush=True)

        compare_rows.append(
            {
                "model": model,
                "summary": summary,
                "alpha_gate": gate_dict,
                "baseline_path": str(out_path).replace("\\", "/"),
            }
        )

    if len(models) > 1:
        compare_path = out_dir / "llm-alpha-compare.json"
        compare_payload = {
            "note": (
                "多模型对比：判断 7B 规模是否够 PlanSeed 需求解析；"
                "不是排行榜。local-first：能过 Alpha Gate 的最小够用模型优先。"
            ),
            "models": compare_rows,
            "any_alpha_qualified": any(
                r["alpha_gate"]["passed"] for r in compare_rows
            ),
        }
        compare_path.parent.mkdir(parents=True, exist_ok=True)
        compare_path.write_text(
            json.dumps(compare_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"\nwrote {compare_path}", flush=True)
        for row in compare_rows:
            mark = "PASS" if row["alpha_gate"]["passed"] else "FAIL"
            m = row["summary"]
            print(
                f"  [{mark}] {row['model']}: "
                f"pass_rate={m.get('case_pass_rate')} "
                f"field={m.get('field_accuracy')} "
                f"geom={m.get('geometry_violation')} "
                f"latency={m.get('average_latency_s')}s",
                flush=True,
            )

    if args.gate and not all_gates_ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
