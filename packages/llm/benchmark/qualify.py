"""Phase 6.7.2 — Blind / Pipeline Qualification。

用法::

    # Blind + Pipeline（默认；严格独立资格认证）
    uv run python -m packages.llm.benchmark.qualify --gate

    # 已泄漏的 Holdout（工程回归，非严格证据）
    uv run python -m packages.llm.benchmark.qualify --set holdout

    # Development 集（调规则用）
    uv run python -m packages.llm.benchmark.qualify --set development

    # 仅模型 Raw（enrich=False，诊断）
    uv run python -m packages.llm.benchmark.qualify --mode model_raw --set blind

环境变量：PLANSEED_OLLAMA_*、PLANSEED_LLM_QUALIFY_LIMIT
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from packages.llm.benchmark.blind_cases_v2 import BLIND_VERSION, load_blind_cases
from packages.llm.benchmark.cases import load_benchmark_cases
from packages.llm.benchmark.gates import evaluate_alpha_gates
from packages.llm.benchmark.holdout_cases import HOLDOUT_VERSION, load_holdout_cases
from packages.llm.benchmark.report import BenchmarkReport
from packages.llm.benchmark.runner import run_benchmark
from packages.llm.draft_schema import draft_json_schema
from packages.llm.factory import load_ollama_config
from packages.llm.ollama import OllamaProvider

CaseSetName = Literal["development", "holdout", "blind"]
QualifyMode = Literal["pipeline", "model_raw"]


def _make_provider(model: str) -> OllamaProvider:
    cfg = replace(
        load_ollama_config(),
        model=model,
        response_format=draft_json_schema(),
    )
    return OllamaProvider(cfg)


def _load_cases(case_set: CaseSetName):
    if case_set == "blind":
        return load_blind_cases(), BLIND_VERSION
    if case_set == "holdout":
        return load_holdout_cases(), HOLDOUT_VERSION
    return load_benchmark_cases(), "development-v1"


def _git_commit() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip() or None
    except Exception:
        return None


def _host_metadata() -> dict[str, Any]:
    meta: dict[str, Any] = {
        "os": platform.platform(),
        "python": platform.python_version(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
    }
    try:
        import psutil  # type: ignore

        meta["ram_gb"] = round(psutil.virtual_memory().total / (1024**3), 1)
        meta["cpu_count"] = psutil.cpu_count(logical=True)
    except Exception:
        meta["ram_gb"] = None
        meta["cpu_count"] = os.cpu_count()
    # GPU：尽力探测，失败则留空（不依赖 CUDA 包）
    meta["gpu"] = None
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader",
            ],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        if lines:
            meta["gpu"] = lines
    except Exception:
        pass
    return meta


def run_qualification(
    *,
    model: str | None = None,
    limit: int | None = None,
    with_repair: bool = True,
    case_set: CaseSetName = "blind",
    mode: QualifyMode = "pipeline",
) -> tuple[BenchmarkReport, str]:
    """跑真模型；返回 (report, case_set_version)。默认 Blind。"""
    cases, version = _load_cases(case_set)
    if limit is not None:
        cases = cases[:limit]
    cfg = load_ollama_config()
    resolved = (model or cfg.model).strip()
    enrich = mode == "pipeline"
    provider = _make_provider(resolved)
    try:
        report = run_benchmark(
            provider=provider,
            cases=cases,
            use_oracle=False,
            with_repair=with_repair,
            mode=mode,
            model=resolved,
            case_set=case_set,
            enrich=enrich,
        )
        return report, version
    finally:
        provider.close()


# 兼容旧名
def run_real_model_qualification(
    *,
    model: str | None = None,
    limit: int | None = None,
    with_repair: bool = True,
) -> BenchmarkReport:
    report, _ = run_qualification(
        model=model,
        limit=limit,
        with_repair=with_repair,
        case_set="development",
        mode="pipeline",
    )
    return report


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
    case_set_version: str,
    detail_failed: bool,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "note": (
            "Requirement Parsing Pipeline Baseline（真模型）。"
            "勿与 CI oracle 100% 混淆。"
            "Strict Alpha Qualified 仅当 Blind + Pipeline 过 Alpha Gate；"
            "Holdout 已泄漏，仅作工程回归。"
        ),
        "meta": {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": _git_commit(),
            "case_set": report.case_set,
            "case_set_version": case_set_version,
            "mode": report.mode,
            "model": report.model,
            "host": _host_metadata(),
            "blind_discipline": (
                "Blind 失败时禁止对着本集逐案改 enrich/vocab/prompt 后再宣称通过。"
                if report.case_set == "blind"
                else None
            ),
        },
        "summary": report.summary(),
        "alpha_gate": gate,
    }
    # Blind / Holdout 默认只写 summary；开发集或显式要求才列 failed ids
    if detail_failed:
        payload["failed_cases"] = _failed_cases_payload(report)
    else:
        payload["failed_case_count"] = sum(
            1 for c in report.case_scores if not c.passed
        )
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
        description="PlanSeed Phase 6.7.2 — Blind / Pipeline Qualification",
    )
    parser.add_argument("--limit", type=int, default=None, help="只跑前 N 条（冒烟）")
    parser.add_argument("--model", type=str, default=None, help="单个模型")
    parser.add_argument(
        "--models",
        type=str,
        default=None,
        help="逗号分隔多模型对比",
    )
    parser.add_argument(
        "--set",
        dest="case_set",
        choices=("development", "holdout", "blind"),
        default="blind",
        help="语料集（默认 blind；严格 Gate 以 blind 为准）",
    )
    parser.add_argument(
        "--mode",
        choices=("pipeline", "model_raw"),
        default="pipeline",
        help="pipeline=LLM+enrich（默认）；model_raw=仅 LLM（诊断）",
    )
    parser.add_argument(
        "--detail-failed",
        action="store_true",
        help="写出 failed_cases 明细（blind/holdout 默认不写，防逐案过拟合）",
    )
    parser.add_argument(
        "--gate",
        action="store_true",
        help="Alpha Gate 未通过时非零退出",
    )
    args = parser.parse_args(argv)

    limit_env = os.environ.get("PLANSEED_LLM_QUALIFY_LIMIT", "").strip()
    limit = args.limit
    if limit is None and limit_env.isdigit():
        limit = int(limit_env)

    cfg = load_ollama_config()
    models = _parse_models(args.models, args.model or cfg.model)
    case_set: CaseSetName = args.case_set
    mode: QualifyMode = args.mode
    detail_failed = bool(args.detail_failed) or case_set == "development"

    print("PlanSeed Phase 6.7.2 — Blind / Pipeline Qualification", flush=True)
    print(
        f"base_url={cfg.base_url} set={case_set} mode={mode} models={models}",
        flush=True,
    )
    if case_set == "blind":
        print(
            "NOTE: Blind set — do not tune enricher from per-case failures.",
            flush=True,
        )
    if limit is not None:
        print(f"limit={limit}", flush=True)

    out_dir = Path("docs") / "baselines"
    compare_rows: list[dict] = []
    all_gates_ok = True

    for model in models:
        print(f"\n=== model={model} set={case_set} mode={mode} ===", flush=True)
        report, version = run_qualification(
            model=model,
            limit=limit,
            with_repair=True,
            case_set=case_set,
            mode=mode,
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
        parts = ["llm-alpha-baseline", case_set, mode]
        if len(models) > 1:
            parts.append(safe_name)
        # 单模型 blind+pipeline 写经典文件名（严格资格）
        if len(models) == 1 and case_set == "blind" and mode == "pipeline":
            out_path = out_dir / "llm-alpha-baseline.json"
        elif (
            len(models) == 1
            and case_set == "holdout"
            and mode == "pipeline"
        ):
            out_path = out_dir / "llm-alpha-baseline-holdout-pipeline.json"
        else:
            out_path = out_dir / ("-".join(parts) + ".json")

        _write_baseline(
            report,
            out_path=out_path,
            gate=gate_dict,
            case_set_version=version,
            detail_failed=detail_failed,
        )
        print(f"wrote {out_path}", flush=True)

        compare_rows.append(
            {
                "model": model,
                "case_set": case_set,
                "mode": mode,
                "summary": summary,
                "alpha_gate": gate_dict,
                "baseline_path": str(out_path).replace("\\", "/"),
            }
        )

    if len(models) > 1:
        compare_path = out_dir / f"llm-alpha-compare-{case_set}-{mode}.json"
        compare_payload = {
            "note": (
                "多模型对比：判断 Pipeline 是否够用；"
                "不是排行榜。严格 Gate 以 blind+pipeline 为准。"
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
                f"rel_p={m.get('relation_precision')} "
                f"unk_p={m.get('unknown_precision')} "
                f"p95={m.get('latency_p95')}s",
                flush=True,
            )

    if args.gate and not all_gates_ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
