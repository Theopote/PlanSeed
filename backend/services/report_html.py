"""DesignReport → HTML（Print/PDF 预览用；不做 Python PDF layout）。"""

from __future__ import annotations

import html
from typing import Any

from packages.schema.report import DesignReport
from packages.schema.report_i18n import (
    DEFAULT_REPORT_LOCALE,
    geometry_origin_label,
    normalize_report_locale,
    tr,
)

from backend.services.report_svg_sanitize import sanitize_report_svg


def render_report_html(report: DesignReport) -> str:
    """生成自包含 HTML 文档（内嵌消毒后的 SVG + CSS）；文案跟 report.project.locale。"""
    r = report
    locale = normalize_report_locale(getattr(r.project, "locale", None) or DEFAULT_REPORT_LOCALE)
    score = r.candidate.total_score
    score_s = f"{score:.0f}" if isinstance(score, (int, float)) else "—"
    origin_label = geometry_origin_label(locale, r.project.geometry_origin)
    status_val = (
        r.status.value if hasattr(r.status, "value") else str(r.status)
    )
    stale_banner = ""
    if status_val == "stale_evaluation" or not r.evaluation.evaluation_fresh:
        stale_banner = (
            "<div class='banner-stale'>"
            f"<strong>{html.escape(tr(locale, 'stale.title'))}</strong> — "
            f"{html.escape(tr(locale, 'stale.body'))}"
            "</div>"
        )

    empty_intents = html.escape(tr(locale, "empty.intents"))
    empty_list = html.escape(tr(locale, "empty.list"))
    intents = "".join(f"<li>{html.escape(x)}</li>" for x in r.requirement.key_intents) or (
        f"<li class='muted'>{empty_intents}</li>"
    )
    assumptions = (
        "".join(
            "<li><code>{}</code> = {} — {}</li>".format(
                html.escape(a.key),
                html.escape(_fmt_val(a.value)),
                html.escape(a.reason or "—"),
            )
            for a in r.assumptions
        )
        or f"<li class='muted'>{empty_list}</li>"
    )
    unknowns = (
        "".join(
            "<li><code>{}</code> — {}</li>".format(
                html.escape(u.key),
                html.escape(u.description or tr(locale, "section.unresolved")),
            )
            for u in r.unknowns
        )
        or f"<li class='muted'>{empty_list}</li>"
    )

    schedule_rows = "".join(
        f"<tr><td>{html.escape(row.name)}</td><td>{html.escape(row.floor_id)}</td><td>{html.escape(row.room_id)}</td><td>{row.width:.2f}</td><td>{row.depth:.2f}</td><td>{row.area:.2f}</td></tr>"
        for row in r.room_schedule
    ) or (
        f"<tr><td colspan='6' class='muted'>"
        f"{html.escape(tr(locale, 'empty.placements'))}</td></tr>"
    )

    axes = ""
    ds = r.evaluation.design_score
    if ds is not None:
        for axis_key, val in (
            ("axis.program", ds.program_score),
            ("axis.spatial", ds.spatial_score),
            ("axis.circulation", ds.circulation_score),
            ("axis.privacy", ds.privacy_score),
            ("axis.environment", ds.environment_score),
            ("axis.technical", ds.technical_score),
            ("axis.robustness", ds.robustness_score),
        ):
            axes += (
                f"<tr><td>{html.escape(tr(locale, axis_key))}</td>"
                f"<td>{val:.1f}</td></tr>"
            )

    findings = "".join(
        "<li class='sev-{}'><strong>{}</strong> — {}</li>".format(
            html.escape(str(f.severity.value if hasattr(f.severity, "value") else f.severity)),
            html.escape(f.title),
            html.escape(f.message),
        )
        for f in r.findings
    ) or f"<li class='muted'>{empty_list}</li>"

    plans = ""
    for fp in r.floor_plans:
        safe_svg = sanitize_report_svg(fp.svg)
        plans += (
            f"<section class='plan'>"
            f"<h3>{html.escape(fp.label)}"
            f" <span class='muted'>({html.escape(fp.floor_id)})</span></h3>"
            f"<div class='svg-wrap'>{safe_svg}</div></section>"
        )
    plans_heading = tr(
        locale,
        "section.floor_plans"
        if any(fp.floor_id != "all" for fp in r.floor_plans)
        else "section.plan_snapshot",
    )

    boundary = "".join(
        f"<div>{html.escape(line)}</div>" for line in r.provenance.boundary_lines
    )

    title = html.escape(r.project.project_name)
    label = html.escape(r.candidate.label)
    cid = html.escape(r.candidate.candidate_id)
    lang = html.escape(locale.value)

    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8"/>
<title>PlanSeed Design Report — {title}</title>
<style>
  :root {{
    --ink: #1a1a1a;
    --muted: #666;
    --line: #ddd;
    --bg: #faf9f7;
    --card: #fff;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 2rem 1.5rem 4rem;
    font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    color: var(--ink); background: var(--bg); line-height: 1.45;
  }}
  .sheet {{
    max-width: 880px; margin: 0 auto; background: var(--card);
    padding: 2rem 2.25rem; border: 1px solid var(--line);
  }}
  h1 {{ font-size: 1.65rem; font-weight: 650; margin: 0 0 0.25rem; letter-spacing: -0.02em; }}
  .eyebrow {{ text-transform: uppercase; letter-spacing: 0.08em; font-size: 0.72rem; color: var(--muted); }}
  .meta {{ color: var(--muted); margin-bottom: 1.5rem; font-size: 0.95rem; }}
  .score {{
    display: inline-block; font-size: 1.75rem; font-weight: 700;
    border: 1px solid var(--ink); padding: 0.15rem 0.6rem; margin-left: 0.5rem;
  }}
  h2 {{ font-size: 1.05rem; margin: 1.75rem 0 0.6rem; border-bottom: 1px solid var(--line); padding-bottom: 0.3rem; }}
  ul {{ margin: 0.3rem 0 0; padding-left: 1.2rem; }}
  li {{ margin: 0.25rem 0; }}
  .muted {{ color: var(--muted); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; margin-top: 0.4rem; }}
  th, td {{ border-bottom: 1px solid var(--line); padding: 0.35rem 0.4rem; text-align: left; }}
  th {{ color: var(--muted); font-weight: 600; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; }}
  .svg-wrap {{ margin-top: 0.75rem; overflow: auto; border: 1px solid var(--line); background: #fff; }}
  .svg-wrap svg {{ max-width: 100%; height: auto; display: block; }}
  footer.boundary {{
    margin-top: 2.5rem; padding-top: 1rem; border-top: 1px solid var(--line);
    font-size: 0.78rem; color: var(--muted); line-height: 1.55;
  }}
  code {{ font-size: 0.85em; }}
  .sev-problem {{ color: #8b1e1e; }}
  .sev-warning {{ color: #8a5a00; }}
  .sev-positive {{ color: #1e5b2f; }}
  .banner-stale {{
    margin: 0 0 1.25rem; padding: 0.75rem 1rem;
    border: 1px solid #8a5a00; background: #fff8e8; color: #5c3d00;
    font-size: 0.9rem;
  }}
  @media print {{
    body {{ background: #fff; padding: 0; }}
    .sheet {{ border: none; max-width: none; }}
    .no-print {{ display: none !important; }}
  }}
</style>
</head>
<body>
  <article class="sheet">
    <div class="eyebrow">PlanSeed Design Report · {html.escape(status_val)}</div>
    <h1>{title}</h1>
    {stale_banner}
    <div class="meta">
      {html.escape(origin_label)}
      · {html.escape(tr(locale, "meta.candidate"))} <strong>{label}</strong>
      <span class="score">{score_s}</span>
      <div style="margin-top:0.35rem">{html.escape(tr(locale, "meta.id"))}: {cid}
        · {html.escape(tr(locale, "meta.evaluation_fresh"))}={str(r.evaluation.evaluation_fresh).lower()}
        · {html.escape(tr(locale, "meta.source_revision"))}={html.escape(r.source_revision_id or "—")}
        · {html.escape(tr(locale, "meta.export"))}={html.escape(r.provenance.export_mode)}</div>
    </div>

    <h2>{html.escape(tr(locale, "section.key_intent"))}</h2>
    <ul>{intents}</ul>

    <h2>{html.escape(tr(locale, "section.assumptions"))}</h2>
    <ul>{assumptions}</ul>

    <h2>{html.escape(tr(locale, "section.unresolved"))}</h2>
    <ul>{unknowns}</ul>

    <h2>{html.escape(plans_heading)}</h2>
    {plans or f"<p class='muted'>{html.escape(tr(locale, 'empty.plans'))}</p>"}

    <h2>{html.escape(tr(locale, "section.room_schedule"))}</h2>
    <table>
      <thead><tr>
        <th>{html.escape(tr(locale, "table.room"))}</th>
        <th>{html.escape(tr(locale, "table.floor"))}</th>
        <th>{html.escape(tr(locale, "table.id"))}</th>
        <th>{html.escape(tr(locale, "table.w"))}</th>
        <th>{html.escape(tr(locale, "table.d"))}</th>
        <th>{html.escape(tr(locale, "table.area"))}</th>
      </tr></thead>
      <tbody>{schedule_rows}</tbody>
    </table>

    <h2>{html.escape(tr(locale, "section.evaluation"))}</h2>
    <table>
      <thead><tr>
        <th>{html.escape(tr(locale, "table.axis"))}</th>
        <th>{html.escape(tr(locale, "table.score"))}</th>
      </tr></thead>
      <tbody>{axes or f"<tr><td colspan='2' class='muted'>{html.escape(tr(locale, 'empty.scores'))}</td></tr>"}</tbody>
    </table>

    <h2>{html.escape(tr(locale, "section.findings"))}</h2>
    <ul>{findings}</ul>

    <footer class="boundary">
      <strong>{html.escape(tr(locale, "section.provenance"))}</strong>
      <div>solver={html.escape(r.provenance.solver_version or "—")}
        · generator={html.escape(r.provenance.generator_version or "—")}
        · evaluation={html.escape(r.provenance.evaluation_version or "—")}</div>
      {boundary}
    </footer>
  </article>
</body>
</html>
"""


def _fmt_val(v: Any) -> str:
    if v is None:
        return "—"
    return str(v)
