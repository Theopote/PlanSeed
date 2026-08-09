"""Phase 6.7 — Real Model Qualification 入口。

用法（本机 Ollama 就绪后）::

    uv run python -m packages.llm.benchmark.qualify

环境变量：
- PLANSEED_OLLAMA_*（见 factory）
- PLANSEED_LLM_QUALIFY_LIMIT：可选，只跑前 N 条（冒烟）
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from packages.llm.benchmark.cases import load_benchmark_cases
from packages.llm.benchmark.report import BenchmarkReport
from packages.llm.benchmark.runner import run_benchmark
from packages.llm.factory import create_requirement_llm_provider, load_ollama_config


def run_real_model_qualification(
    *,
    limit: int | None = None,
    with_repair: bool = True,
) -> BenchmarkReport:
    """对语料跑真模型（非 oracle），产出 Alpha Baseline 指标。"""
    cases = load_benchmark_cases()
    if limit is not None:
        cases = cases[:limit]
    cfg = load_ollama_config()
    provider = create_requirement_llm_provider()
    return run_benchmark(
        provider=provider,
        cases=cases,
        use_oracle=False,
        with_repair=with_repair,
        mode="real",
        model=cfg.model,
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    limit_env = os.environ.get("PLANSEED_LLM_QUALIFY_LIMIT", "").strip()
    limit: int | None = int(limit_env) if limit_env.isdigit() else None
    if "--limit" in argv:
        i = argv.index("--limit")
        limit = int(argv[i + 1])

    print("PlanSeed Phase 6.7 — Real Model Qualification", flush=True)
    cfg = load_ollama_config()
    print(f"model={cfg.model} base_url={cfg.base_url} timeout_s={cfg.timeout_s}", flush=True)
    if limit is not None:
        print(f"limit={limit}", flush=True)

    report = run_real_model_qualification(limit=limit, with_repair=True)
    summary = report.summary()
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)

    out_dir = Path("docs") / "baselines"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "llm-alpha-baseline.json"
    payload = {
        "note": (
            "LLM Alpha Baseline（真模型）。"
            "勿与 CI oracle 100% 混淆：oracle 只验证 harness。"
        ),
        "summary": summary,
        "failed_cases": [
            {
                "id": c.case_id,
                "hallucinations": c.hallucinations,
                "notes": c.notes,
                "parse_failed": c.parse_failed,
                "geometry_fail": c.geometry_fail,
                "attempts": c.attempts,
                "latency_s": round(c.latency_s, 3),
            }
            for c in report.case_scores
            if not c.passed
        ],
    }
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
