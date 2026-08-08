import { useState, type FormEvent } from "react";
import type {
  ProgramSummary,
  RejectedCandidatePayload,
  RequirementForm,
} from "../api/client";

type Props = {
  form: RequirementForm;
  onChange: (next: RequirementForm) => void;
  onGenerate: () => void;
  onBenchmark: () => void;
  loading: boolean;
  apiOk: boolean | null;
  program: ProgramSummary | null;
  error: string | null;
  stats: { generated: number; valid: number; rejected: number } | null;
  rejectedCandidates: RejectedCandidatePayload[];
  violationSummary: Record<string, number>;
};

function topViolationEntries(
  summary: Record<string, number>,
  limit = 5,
): Array<[string, number]> {
  return Object.entries(summary)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, limit);
}

export function RequirementsPanel({
  form,
  onChange,
  onGenerate,
  onBenchmark,
  loading,
  apiOk,
  program,
  error,
  stats,
  rejectedCandidates,
  violationSummary,
}: Props) {
  const [rejectedOpen, setRejectedOpen] = useState(true);

  function set<K extends keyof RequirementForm>(key: K, value: RequirementForm[K]) {
    onChange({ ...form, [key]: value });
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    onGenerate();
  }

  const hasRejected =
    (stats?.rejected ?? 0) > 0 &&
    (rejectedCandidates.length > 0 || Object.keys(violationSummary).length > 0);
  const topViolations = topViolationEntries(violationSummary);

  return (
    <aside className="panel panel-left">
      <header className="panel-head">
        <h1 className="brand">PlanSeed</h1>
        <p className="muted">需求 → 生成 → 评价</p>
        <p className={`api-status ${apiOk === true ? "ok" : apiOk === false ? "bad" : ""}`}>
          引擎{" "}
          {apiOk === null ? "启动中…" : apiOk ? "已就绪" : "未就绪"}
        </p>
      </header>

      <form className="req-form" onSubmit={handleSubmit}>
        <label>
          地块宽 (m)
          <input
            type="number"
            min={6}
            max={60}
            step={0.5}
            value={form.width}
            onChange={(e) => set("width", Number(e.target.value))}
          />
        </label>
        <label>
          地块深 (m)
          <input
            type="number"
            min={6}
            max={60}
            step={0.5}
            value={form.depth}
            onChange={(e) => set("depth", Number(e.target.value))}
          />
        </label>
        <label>
          层数
          <input
            type="number"
            min={1}
            max={3}
            value={form.floor_count}
            onChange={(e) => set("floor_count", Number(e.target.value))}
          />
        </label>
        <label>
          卧室
          <input
            type="number"
            min={1}
            max={10}
            value={form.bedrooms}
            onChange={(e) => set("bedrooms", Number(e.target.value))}
          />
        </label>
        <label>
          卫生间
          <input
            type="number"
            min={1}
            max={8}
            value={form.bathrooms}
            onChange={(e) => set("bathrooms", Number(e.target.value))}
          />
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={form.has_garage}
            onChange={(e) => set("has_garage", e.target.checked)}
          />
          含车库
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={form.prefer_south_facing_living}
            onChange={(e) => set("prefer_south_facing_living", e.target.checked)}
          />
          客厅朝南
        </label>

        <div className="actions">
          <button type="submit" disabled={loading || apiOk === false}>
            {loading ? "生成中…" : "Generate"}
          </button>
          <button
            type="button"
            className="secondary"
            disabled={loading || apiOk === false}
            onClick={onBenchmark}
          >
            基准案例
          </button>
        </div>
      </form>

      {error && <p className="error">{error}</p>}

      {stats && (
        <p className="muted stats">
          生成 {stats.generated} · 有效 {stats.valid} · 拒绝 {stats.rejected}
        </p>
      )}

      {hasRejected && (
        <section className="rejected-block">
          <button
            type="button"
            className="rejected-toggle"
            aria-expanded={rejectedOpen}
            onClick={() => setRejectedOpen((o) => !o)}
          >
            被淘汰（硬性失败 {stats?.rejected ?? rejectedCandidates.length}）
            <span className="muted">{rejectedOpen ? "▾" : "▸"}</span>
          </button>
          {rejectedOpen && (
            <div className="rejected-body">
              {topViolations.length > 0 && (
                <p className="rejected-summary muted">
                  汇总：{" "}
                  {topViolations
                    .map(([id, n]) => `${id} ×${n}`)
                    .join(" · ")}
                </p>
              )}
              <ul className="rejected-list">
                {rejectedCandidates.map((r) => (
                  <li key={r.id}>
                    <div className="rejected-seed">Seed {r.seed}</div>
                    {r.reasons.length > 0 ? (
                      <ul className="rejected-reasons">
                        {r.reasons.map((msg, i) => (
                          <li key={`${r.id}-${i}`}>{msg}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="muted">无硬性违规说明</p>
                    )}
                  </li>
                ))}
              </ul>
              {(stats?.rejected ?? 0) > rejectedCandidates.length && (
                <p className="muted tiny">
                  仅展示前 {rejectedCandidates.length} 条样例
                </p>
              )}
            </div>
          )}
        </section>
      )}

      {program && (
        <section className="program-meta">
          <h2>Program</h2>
          <p className="muted">
            {program.site_width}×{program.site_depth} m · {program.floor_count} 层 ·{" "}
            {program.rooms.length} 房间
          </p>
          <ul className="room-list">
            {program.rooms.map((r) => (
              <li key={r.id}>
                <span>{r.name}</span>
                <span className="muted">
                  {r.target_area}㎡ · {r.category}
                </span>
              </li>
            ))}
          </ul>
          {program.assumptions.length > 0 && (
            <>
              <h3>Assumptions</h3>
              <ul className="tiny-list">
                {program.assumptions.map((a) => (
                  <li key={a.key}>
                    <code>{a.key}</code> = {String(a.value)}
                    {a.reason ? ` — ${a.reason}` : ""}
                  </li>
                ))}
              </ul>
            </>
          )}
          {program.unknowns.length > 0 && (
            <>
              <h3>Unknowns</h3>
              <ul className="tiny-list">
                {program.unknowns.map((u) => (
                  <li key={u.key}>
                    <code>{u.key}</code> {u.description}
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}
    </aside>
  );
}
