"""DesignReport → HTML（Print/PDF 预览用；不做 Python PDF layout）。

Phase 7.1：建筑方案报告信息层级 — Cover → Brief → Plans → Schedule →
Evaluation → Findings → Assumptions/Unknowns → Provenance。
"""

from __future__ import annotations

import html
from typing import Any

from packages.schema.report import DesignReport, ReportUnknown
from packages.schema.report_i18n import (
    DEFAULT_REPORT_LOCALE,
    geometry_origin_label,
    normalize_report_locale,
    tr,
)

from backend.services.report_evaluation_presenter import present_evaluation
from backend.services.report_orientation import north_arrow_css_rotation_deg
from backend.services.report_svg_sanitize import sanitize_report_svg


def render_report_html(report: DesignReport) -> str:
    """生成自包含 HTML 文档（内嵌消毒后的 SVG + CSS）；文案跟 report.project.locale。"""
    r = report
    locale = normalize_report_locale(getattr(r.project, "locale", None) or DEFAULT_REPORT_LOCALE)
    score = r.candidate.total_score
    score_s = f"{score:.0f}" if isinstance(score, (int, float)) else "—"
    origin_label = geometry_origin_label(locale, r.project.geometry_origin)
    status_val = r.status.value if hasattr(r.status, "value") else str(r.status)

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

    blocking = [u for u in r.unknowns if _is_blocking_unknown(u)]
    blocking_banner = ""
    if blocking:
        items = "".join(
            f"<li><strong>{html.escape(u.description or u.key)}</strong></li>"
            for u in blocking
        )
        blocking_banner = (
            f"<div class='banner-blocking'>"
            f"<strong>{html.escape(tr(locale, 'section.blocking'))}</strong>"
            f"<ul>{items}</ul></div>"
        )

    cover_intents = "".join(
        f"<li>{html.escape(x)}</li>" for x in r.requirement.key_intents[:5]
    ) or f"<li class='muted'>{empty_intents}</li>"

    intents = "".join(f"<li>{html.escape(x)}</li>" for x in r.requirement.key_intents) or (
        f"<li class='muted'>{empty_intents}</li>"
    )
    assumptions = (
        "".join(
            f"<li>{html.escape(a.reason or a.key)} — {html.escape(_fmt_val(a.value))}</li>"
            for a in r.assumptions
        )
        or f"<li class='muted'>{empty_list}</li>"
    )
    unknowns = (
        "".join(
            f"<li>{html.escape(u.description or u.key)}</li>"
            for u in r.unknowns
        )
        or f"<li class='muted'>{empty_list}</li>"
    )

    schedule_rows = "".join(_schedule_row_html(row) for row in r.room_schedule) or (
        f"<tr><td colspan='6' class='muted'>"
        f"{html.escape(tr(locale, 'empty.placements'))}</td></tr>"
    )

    ds = r.evaluation.design_score
    eval_block = ""
    findings_block = ""
    executive = ""
    if ds is not None:
        presented = present_evaluation(
            locale=locale,
            design_score=ds,
            findings=list(r.findings),
            key_intents=list(r.requirement.key_intents),
            candidate_label=r.candidate.label,
        )
        executive = html.escape(presented.executive_summary)
        axes = "".join(
            "<tr>"
            f"<td>{html.escape(ax.label)}</td>"
            f"<td class='num'>{ax.score:.0f}</td>"
            f"<td><span class='band {html.escape(ax.band_key.split('.')[-1])}'>"
            f"{html.escape(ax.band_label)}</span></td>"
            "</tr>"
            for ax in presented.axes
        )
        strengths = (
            "".join(
                f"<li class='sev-positive'><strong>{html.escape(f.title)}</strong>"
                f" — {html.escape(f.message)}</li>"
                for f in presented.strengths
            )
            or f"<li class='muted'>{empty_list}</li>"
        )
        concerns = (
            "".join(
                "<li class='sev-{}'><strong>{}</strong> — {}</li>".format(
                    html.escape(
                        f.severity.value if hasattr(f.severity, "value") else str(f.severity)
                    ),
                    html.escape(f.title),
                    html.escape(f.message),
                )
                for f in presented.concerns
            )
            or f"<li class='muted'>{empty_list}</li>"
        )
        eval_block = f"""
    <section class="chapter" id="evaluation">
      <h2>{html.escape(tr(locale, "section.evaluation"))}</h2>
      <table class="eval-table">
        <thead><tr>
          <th>{html.escape(tr(locale, "table.axis"))}</th>
          <th>{html.escape(tr(locale, "table.score"))}</th>
          <th>{html.escape(tr(locale, "table.band"))}</th>
        </tr></thead>
        <tbody>{axes}</tbody>
      </table>
      <div class="eval-columns">
        <div>
          <h3>{html.escape(tr(locale, "section.strengths"))}</h3>
          <ul>{strengths}</ul>
        </div>
        <div>
          <h3>{html.escape(tr(locale, "section.concerns"))}</h3>
          <ul>{concerns}</ul>
        </div>
      </div>
    </section>
"""
        findings_block = "".join(
            "<li class='sev-{}'><strong>{}</strong> — {}</li>".format(
                html.escape(
                    f.severity.value if hasattr(f.severity, "value") else str(f.severity)
                ),
                html.escape(f.title),
                html.escape(f.message),
            )
            for f in r.findings
        ) or f"<li class='muted'>{empty_list}</li>"
    else:
        findings_block = f"<li class='muted'>{empty_list}</li>"

    plans = ""
    for fp in r.floor_plans:
        safe_svg = sanitize_report_svg(fp.svg)
        north_meta = _north_compass_html(locale, fp.north_angle_deg)
        plans += f"""
      <section class="plan-page">
        <header class="plan-head">
          <h3>{html.escape(fp.label)}</h3>
          <div class="plan-meta">
            <span class="floor-id">{html.escape(fp.floor_id)}</span>
            {north_meta}
          </div>
        </header>
        <div class="svg-wrap">{safe_svg}</div>
        <p class="plan-note">{html.escape(tr(locale, "meta.scale"))}</p>
        <p class="plan-note muted">{html.escape(tr(locale, "meta.legend"))}</p>
      </section>
"""
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
{_REPORT_CSS}
</style>
</head>
<body>
  <article class="sheet">
    <header class="cover">
      <div class="eyebrow">{html.escape(tr(locale, "cover.eyebrow"))}</div>
      <h1>{title}</h1>
      {stale_banner}
      {blocking_banner}
      <div class="cover-meta">
        <div class="cover-line">
          {html.escape(origin_label)}
          · {html.escape(tr(locale, "meta.candidate"))}
          <strong>{label}</strong>
          <span class="score">{score_s}</span>
        </div>
        <p class="executive"><strong>{html.escape(tr(locale, "cover.summary"))}</strong>
          — {executive or html.escape(tr(locale, "empty.list"))}</p>
        <ul class="cover-intents">{cover_intents}</ul>
        <nav class="toc" aria-label="{html.escape(tr(locale, 'meta.toc'))}">
          <div class="toc-title">{html.escape(tr(locale, "meta.toc"))}</div>
          <ol>
            <li><a href="#brief">{html.escape(tr(locale, "section.brief"))}</a></li>
            <li><a href="#plans">{html.escape(plans_heading)}</a></li>
            <li><a href="#schedule">{html.escape(tr(locale, "section.room_schedule"))}</a></li>
            <li><a href="#evaluation">{html.escape(tr(locale, "section.evaluation"))}</a></li>
            <li><a href="#findings">{html.escape(tr(locale, "section.findings"))}</a></li>
            <li><a href="#assumptions">{html.escape(tr(locale, "section.assumptions_unknowns"))}</a></li>
            <li><a href="#provenance">{html.escape(tr(locale, "section.provenance"))}</a></li>
          </ol>
        </nav>
      </div>
    </header>

    <section class="chapter" id="brief">
      <h2>{html.escape(tr(locale, "section.brief"))}</h2>
      <ul>{intents}</ul>
    </section>

    <section class="chapter plans-chapter" id="plans">
      <h2>{html.escape(plans_heading)}</h2>
      {plans or f"<p class='muted'>{html.escape(tr(locale, 'empty.plans'))}</p>"}
    </section>

    <section class="chapter" id="schedule">
      <h2>{html.escape(tr(locale, "section.room_schedule"))}</h2>
      <table class="schedule-table">
        <thead><tr>
          <th>{html.escape(tr(locale, "table.room"))}</th>
          <th>{html.escape(tr(locale, "table.floor"))}</th>
          <th>{html.escape(tr(locale, "table.target_area"))}</th>
          <th>{html.escape(tr(locale, "table.area"))}</th>
          <th>{html.escape(tr(locale, "table.delta"))}</th>
          <th>{html.escape(tr(locale, "table.wxd"))}</th>
        </tr></thead>
        <tbody>{schedule_rows}</tbody>
      </table>
    </section>

    {eval_block}

    <section class="chapter" id="findings">
      <h2>{html.escape(tr(locale, "section.findings"))}</h2>
      <ul>{findings_block}</ul>
    </section>

    <section class="chapter appendix" id="assumptions">
      <h2>{html.escape(tr(locale, "section.assumptions_unknowns"))}</h2>
      <h3>{html.escape(tr(locale, "section.assumptions"))}</h3>
      <ul>{assumptions}</ul>
      <h3>{html.escape(tr(locale, "section.unresolved"))}</h3>
      <ul>{unknowns}</ul>
    </section>

    <footer class="boundary chapter" id="provenance">
      <h2>{html.escape(tr(locale, "section.provenance"))}</h2>
      <div class="prov-grid">
        <div>{html.escape(tr(locale, "meta.report_generated_at"))}:
          {html.escape(r.project.generated_at or "—")}</div>
        <div>{html.escape(tr(locale, "meta.id"))}: {cid}</div>
        <div>{html.escape(tr(locale, "meta.source_revision"))}:
          {html.escape(r.source_revision_id or "—")}</div>
        <div>{html.escape(tr(locale, "meta.evaluation_fresh"))}:
          {str(r.evaluation.evaluation_fresh).lower()}</div>
        <div>{html.escape(tr(locale, "meta.export"))}:
          {html.escape(r.provenance.export_mode)}</div>
        <div>solver={html.escape(r.provenance.solver_version or "—")}</div>
        <div>generator={html.escape(r.provenance.generator_version or "—")}</div>
        <div>evaluation={html.escape(r.provenance.evaluation_version or "—")}</div>
      </div>
      {boundary}
    </footer>
  </article>
</body>
</html>
"""


_REPORT_CSS = """
  :root {
    --ink: #1c1917;
    --muted: #78716c;
    --line: #e7e5e4;
    --bg: #f5f5f4;
    --card: #fff;
    --band-good: #166534;
    --band-fair: #a16207;
    --band-improve: #9f1239;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 2rem 1.25rem 4rem;
    font-family: "Iowan Old Style", "Palatino Linotype", "Songti SC",
      "Source Han Serif SC", "Noto Serif CJK SC", Georgia, serif;
    color: var(--ink); background: var(--bg); line-height: 1.5;
  }
  .sheet {
    max-width: 920px; margin: 0 auto; background: var(--card);
    padding: 2.5rem 2.5rem 3rem; border: 1px solid var(--line);
  }
  .cover { margin-bottom: 2rem; padding-bottom: 1.5rem; border-bottom: 1px solid var(--line); }
  .eyebrow {
    letter-spacing: 0.12em; font-size: 0.72rem; color: var(--muted);
    text-transform: uppercase; font-family: "Segoe UI", "PingFang SC", sans-serif;
  }
  h1 {
    font-size: 2rem; font-weight: 600; margin: 0.4rem 0 0.75rem;
    letter-spacing: -0.02em; line-height: 1.2;
  }
  h2 {
    font-size: 1.05rem; margin: 0 0 0.75rem; font-weight: 650;
    font-family: "Segoe UI", "PingFang SC", sans-serif;
    letter-spacing: 0.02em;
  }
  h3 {
    font-size: 0.92rem; margin: 1rem 0 0.4rem;
    font-family: "Segoe UI", "PingFang SC", sans-serif; font-weight: 600;
  }
  .cover-meta { color: var(--ink); }
  .cover-line { font-size: 1rem; margin-bottom: 0.75rem; }
  .executive { margin: 0.5rem 0 0.75rem; font-size: 1.02rem; }
  .cover-intents { margin: 0; padding-left: 1.2rem; color: var(--muted); }
  .toc {
    margin-top: 1.25rem; padding-top: 1rem; border-top: 1px solid var(--line);
    font-family: "Segoe UI", "PingFang SC", sans-serif; font-size: 0.88rem;
  }
  .toc-title {
    color: var(--muted); font-size: 0.72rem; letter-spacing: 0.08em;
    text-transform: uppercase; margin-bottom: 0.35rem;
  }
  .toc ol { margin: 0; padding-left: 1.2rem; color: var(--ink); }
  .toc a { color: inherit; text-decoration: none; border-bottom: 1px dotted var(--line); }
  .toc a:hover { border-bottom-color: var(--ink); }
  .score {
    display: inline-block; font-size: 1.85rem; font-weight: 700;
    border: 1.5px solid var(--ink); padding: 0.1rem 0.55rem; margin-left: 0.55rem;
    font-family: "Segoe UI", "PingFang SC", sans-serif; vertical-align: middle;
  }
  .chapter { margin-top: 2.25rem; }
  .chapter.appendix { margin-top: 2.5rem; color: var(--ink); }
  .chapter.appendix h2, .chapter.appendix h3 { color: var(--muted); }
  ul { margin: 0.3rem 0 0; padding-left: 1.2rem; }
  li { margin: 0.28rem 0; }
  .muted { color: var(--muted); }
  table { width: 100%; border-collapse: collapse; font-size: 0.9rem; margin-top: 0.35rem;
    font-family: "Segoe UI", "PingFang SC", sans-serif; }
  th, td { border-bottom: 1px solid var(--line); padding: 0.45rem 0.4rem; text-align: left; }
  th {
    color: var(--muted); font-weight: 600; font-size: 0.72rem;
    text-transform: uppercase; letter-spacing: 0.05em;
  }
  td.num, .schedule-table td:nth-child(n+3) { font-variant-numeric: tabular-nums; }
  .eval-columns {
    display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; margin-top: 1rem;
  }
  .band {
    font-size: 0.78rem; font-weight: 650; letter-spacing: 0.02em;
  }
  .band.good { color: var(--band-good); }
  .band.fair { color: var(--band-fair); }
  .band.improve { color: var(--band-improve); }
  .plan-page {
    margin: 1.25rem 0 2rem; padding: 1rem 0 1.5rem;
    break-inside: avoid; page-break-inside: avoid;
  }
  .plan-head {
    display: flex; justify-content: space-between; align-items: flex-start;
    gap: 1rem; margin-bottom: 0.75rem;
  }
  .plan-head h3 { margin: 0; font-size: 1rem; }
  .plan-meta { display: flex; align-items: center; gap: 0.75rem; color: var(--muted);
    font-family: "Segoe UI", "PingFang SC", sans-serif; font-size: 0.8rem; }
  .north-wrap {
    display: inline-flex; flex-direction: column; align-items: center; gap: 0.1rem;
  }
  .north {
    display: inline-flex; flex-direction: column; align-items: center;
    width: 2rem; line-height: 1; color: var(--ink);
    transform-origin: 50% 45%;
  }
  .north .arrow { font-size: 0.95rem; }
  .north .n { font-size: 0.65rem; font-weight: 700; letter-spacing: 0.06em; }
  .north-angle {
    font-size: 0.65rem; color: var(--muted); margin-top: 0.15rem;
    font-family: "Segoe UI", "PingFang SC", sans-serif;
  }
  .north-undefined {
    font-size: 0.72rem; color: var(--muted);
    font-family: "Segoe UI", "PingFang SC", sans-serif;
  }
  .svg-wrap {
    margin-top: 0.35rem; overflow: auto; border: 1px solid var(--line);
    background: #fff; padding: 1.25rem 1rem;
  }
  .svg-wrap svg { max-width: 100%; height: auto; display: block; margin: 0 auto; }
  .plan-note { margin: 0.55rem 0 0; font-size: 0.78rem; color: var(--muted);
    font-family: "Segoe UI", "PingFang SC", sans-serif; }
  footer.boundary {
    margin-top: 2.75rem; padding-top: 1.25rem; border-top: 1px solid var(--line);
    font-size: 0.78rem; color: var(--muted); line-height: 1.55;
    font-family: "Segoe UI", "PingFang SC", sans-serif;
  }
  footer.boundary h2 { color: var(--muted); font-size: 0.95rem; }
  .prov-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: 0.25rem 1rem; margin: 0.5rem 0 0.75rem;
  }
  .sev-problem { color: #9f1239; }
  .sev-warning { color: #a16207; }
  .sev-positive { color: #166534; }
  .sev-info { color: var(--muted); }
  .banner-stale {
    margin: 0 0 1rem; padding: 0.75rem 1rem;
    border: 1px solid #a16207; background: #fffbeb; color: #713f12; font-size: 0.9rem;
    font-family: "Segoe UI", "PingFang SC", sans-serif;
  }
  .banner-blocking {
    margin: 0 0 1rem; padding: 0.75rem 1rem;
    border: 1px solid #9f1239; background: #fff1f2; color: #881337; font-size: 0.9rem;
    font-family: "Segoe UI", "PingFang SC", sans-serif;
  }
  .banner-blocking ul { margin: 0.35rem 0 0; }
  /* Phase 7.2.4 — Print polish（HTML→WebView2→Print；非 PDF 引擎） */
  @page {
    size: A4 portrait;
    margin: 14mm 12mm 16mm 12mm;
  }
  @media print {
    body {
      background: #fff;
      padding: 0;
      color: #000;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }
    .sheet {
      border: none;
      max-width: none;
      padding: 0;
      margin: 0;
    }
    .cover {
      page-break-after: always;
      break-after: page;
      border-bottom: none;
      margin-bottom: 0;
      padding-bottom: 0;
    }
    .cover h1 {
      orphans: 2;
      widows: 2;
      break-after: avoid;
      page-break-after: avoid;
    }
    .banner-stale,
    .banner-blocking {
      break-inside: avoid;
      page-break-inside: avoid;
    }
    .toc a {
      border-bottom: none;
      text-decoration: none;
      color: inherit;
    }
    /* 平面：每层尽量独占一页；禁止整章强制同页（会制造大块空白） */
    .plans-chapter > h2 {
      break-after: avoid;
      page-break-after: avoid;
    }
    .plan-page {
      page-break-after: always;
      break-after: page;
      break-inside: avoid;
      page-break-inside: avoid;
      margin: 0 0 0;
      padding: 0 0 8mm;
    }
    .plan-page:last-child {
      page-break-after: auto;
      break-after: auto;
    }
    .plan-head,
    .svg-wrap {
      break-inside: avoid;
      page-break-inside: avoid;
    }
    .svg-wrap {
      overflow: visible;
    }
    h2, h3 {
      break-after: avoid;
      page-break-after: avoid;
      orphans: 3;
      widows: 3;
    }
    p, li {
      orphans: 3;
      widows: 3;
    }
    /* 跨页表：表头重复；行尽量不拆 */
    thead {
      display: table-header-group;
    }
    tfoot {
      display: table-footer-group;
    }
    tr {
      break-inside: avoid;
      page-break-inside: avoid;
    }
    .schedule-table,
    .eval-table {
      break-inside: auto;
      page-break-inside: auto;
    }
    .eval-columns {
      break-inside: avoid;
      page-break-inside: avoid;
    }
    footer.boundary {
      break-before: page;
      page-break-before: always;
    }
    .no-print { display: none !important; }
  }
  @media (max-width: 640px) {
    .eval-columns, .prov-grid { grid-template-columns: 1fr; }
    .sheet { padding: 1.25rem; }
  }
"""


def _is_blocking_unknown(u: ReportUnknown) -> bool:
    return str(u.priority or "").lower() == "blocking"


def _schedule_row_html(row: Any) -> str:
    target = f"{row.target_area:.2f}" if row.target_area is not None else "—"
    delta = f"{row.area_delta:+.2f}" if row.area_delta is not None else "—"
    wxd = f"{row.width:.2f} × {row.depth:.2f}"
    return (
        f"<tr>"
        f"<td>{html.escape(row.name)}</td>"
        f"<td>{html.escape(row.floor_id)}</td>"
        f"<td>{target}</td>"
        f"<td>{row.area:.2f}</td>"
        f"<td>{delta}</td>"
        f"<td>{wxd}</td>"
        f"</tr>"
    )


def _north_compass_html(locale: Any, north_angle_deg: float | None) -> str:
    """北针只消费 FloorPlanBlock.north_angle_deg；禁止在此读 site / 猜 0°。"""
    if north_angle_deg is None:
        return (
            f'<span class="north-undefined">'
            f"{html.escape(tr(locale, 'meta.north_undefined'))}"
            f"</span>"
        )
    rot = north_arrow_css_rotation_deg(north_angle_deg)
    label = tr(locale, "meta.north")
    title = f"{label} · north_angle={north_angle_deg:.0f}°"
    return (
        f'<span class="north-wrap">'
        f'<span class="north" style="transform: rotate({rot:.4f}deg)" '
        f'title="{html.escape(title)}">'
        f'<span class="arrow" aria-hidden="true">▲</span>'
        f'<span class="n">{html.escape(label)}</span>'
        f"</span>"
        f'<span class="north-angle">∠{north_angle_deg:.0f}°</span>'
        f"</span>"
    )


def _fmt_val(v: Any) -> str:
    if v is None:
        return "—"
    return str(v)
