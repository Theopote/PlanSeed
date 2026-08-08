import type { FormEvent } from "react";
import type { ProgramSummary, RequirementForm } from "../api/client";

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
};

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
}: Props) {
  function set<K extends keyof RequirementForm>(key: K, value: RequirementForm[K]) {
    onChange({ ...form, [key]: value });
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    onGenerate();
  }

  return (
    <aside className="panel panel-left">
      <header className="panel-head">
        <h1 className="brand">PlanSeed</h1>
        <p className="muted">需求 → 生成 → 评价</p>
        <p className={`api-status ${apiOk === true ? "ok" : apiOk === false ? "bad" : ""}`}>
          API {apiOk === null ? "…" : apiOk ? "已连接" : "离线"}
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
