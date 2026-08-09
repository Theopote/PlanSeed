import { useEffect, useState, type FormEvent } from "react";
import type {
  EngineLifecycle,
  LlmHealthState,
  ProgramSummary,
  RejectedCandidatePayload,
  RequirementForm,
  RequirementSpecPayload,
} from "../api/client";
import { resolveRequirementGaps } from "../lib/requirementGaps";
import { RequirementGapsPanel } from "./RequirementGapsPanel";

type Props = {
  form: RequirementForm;
  onChange: (next: RequirementForm) => void;
  onGenerate: () => void;
  onBenchmark: () => void;
  nlText: string;
  onNlTextChange: (text: string) => void;
  onParseNl: () => void;
  onParseAndGenerate: () => void;
  nlBusy?: boolean;
  nlHint?: string | null;
  loading: boolean;
  engineStatus: EngineLifecycle;
  onRetryEngine: () => void;
  llmState?: LlmHealthState | null;
  llmModel?: string | null;
  llmDetail?: string | null;
  program: ProgramSummary | null;
  requirementSpec: RequirementSpecPayload | null;
  onUpdateAssumption: (
    key: string,
    patch: { value: string; reason: string },
  ) => void;
  onRemoveAssumption: (key: string) => void;
  onDismissUnknown: (key: string) => void;
  error: string | null;
  stats: { generated: number; valid: number; rejected: number } | null;
  rejectedCandidates: RejectedCandidatePayload[];
  violationSummary: Record<string, number>;
  projectName: string;
  onProjectNameChange: (name: string) => void;
  onSaveProject: () => void;
  onExportReport?: () => void;
  onExportReportJson?: () => void;
  onExportSvg?: (scope: "floor" | "snapshot" | "all_floors") => void;
  onExportPng?: (
    scope: "floor" | "snapshot" | "all_floors",
    size: 2048 | 4096,
  ) => void;
  onOpenProjects: () => void;
  projectBusy?: boolean;
  versionHint?: string | null;
  reportBusy?: boolean;
};

function topViolationEntries(
  summary: Record<string, number>,
  limit = 5,
): Array<[string, number]> {
  return Object.entries(summary)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, limit);
}

function statusLabel(status: EngineLifecycle): string {
  switch (status) {
    case "READY":
      return "已就绪";
    case "STARTING":
      return "启动中…";
    case "ERROR":
      return "异常";
    case "STOPPED":
      return "已停止";
  }
}

function llmStatusLabel(state: LlmHealthState): string {
  switch (state) {
    case "ModelReady":
      return "模型就绪";
    case "ModelMissing":
      return "模型未安装";
    case "LLMUnavailable":
      return "Ollama 不可用";
    case "ParseRunning":
      return "解析中…";
    case "ParseFailed":
      return "解析失败";
  }
}

export function RequirementsPanel({
  form,
  onChange,
  onGenerate,
  onBenchmark,
  nlText,
  onNlTextChange,
  onParseNl,
  onParseAndGenerate,
  nlBusy = false,
  nlHint = null,
  loading,
  engineStatus,
  onRetryEngine,
  llmState = null,
  llmModel = null,
  llmDetail = null,
  program,
  requirementSpec,
  onUpdateAssumption,
  onRemoveAssumption,
  onDismissUnknown,
  error,
  stats,
  rejectedCandidates,
  violationSummary,
  projectName,
  onProjectNameChange,
  onSaveProject,
  onExportReport,
  onExportReportJson,
  onExportSvg,
  onExportPng,
  onOpenProjects,
  projectBusy = false,
  versionHint = null,
  reportBusy = false,
}: Props) {
  const [rejectedOpen, setRejectedOpen] = useState(true);
  const [retryBusy, setRetryBusy] = useState(false);
  const engineReady = engineStatus === "READY";
  const canParseNl =
    engineReady &&
    llmState !== "ModelMissing" &&
    llmState !== "LLMUnavailable";
  const gaps = resolveRequirementGaps(requirementSpec, program);

  useEffect(() => {
    if (engineStatus !== "STARTING") {
      setRetryBusy(false);
    }
  }, [engineStatus]);

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
        <p
          className={`api-status ${
            engineStatus === "READY"
              ? "ok"
              : engineStatus === "ERROR" || engineStatus === "STOPPED"
                ? "bad"
                : ""
          }`}
        >
          引擎 {statusLabel(engineStatus)}
        </p>
        {llmState ? (
          <p
            className={`api-status ${
              llmState === "ModelReady"
                ? "ok"
                : llmState === "ModelMissing" ||
                    llmState === "LLMUnavailable" ||
                    llmState === "ParseFailed"
                  ? "bad"
                  : ""
            }`}
          >
            AI {llmStatusLabel(llmState)}
            {llmModel ? ` · ${llmModel}` : ""}
          </p>
        ) : null}
        {llmState === "ModelMissing" && llmDetail ? (
          <p className="warn-hint llm-hint">{llmDetail}</p>
        ) : null}
        {(engineStatus === "ERROR" ||
          engineStatus === "STOPPED" ||
          retryBusy) && (
          <button
            type="button"
            className="secondary engine-retry"
            disabled={retryBusy || engineStatus === "STARTING"}
            onClick={() => {
              setRetryBusy(true);
              onRetryEngine();
            }}
          >
            {engineStatus === "STARTING" || retryBusy
              ? "启动中…"
              : "重试引擎"}
          </button>
        )}
      </header>

      <div className="project-bar">
        <label className="project-name">
          项目名
          <input
            type="text"
            value={projectName}
            onChange={(e) => onProjectNameChange(e.target.value)}
            placeholder="未命名项目"
            disabled={!engineReady}
          />
        </label>
        <div className="project-actions">
          <button
            type="button"
            className="secondary"
            disabled={!engineReady || projectBusy || !program}
            onClick={onSaveProject}
          >
            {projectBusy ? "…" : "保存"}
          </button>
          <button
            type="button"
            className="secondary"
            disabled={!engineReady || reportBusy || !program || !onExportReport}
            onClick={onExportReport}
            title="导出 Design Report（HTML / Print PDF）"
          >
            {reportBusy ? "…" : "报告"}
          </button>
          <button
            type="button"
            className="secondary"
            disabled={
              !engineReady || reportBusy || !program || !onExportReportJson
            }
            onClick={onExportReportJson}
            title="导出 DesignReport JSON（交付契约，≠ 项目快照）"
          >
            JSON
          </button>
          <details className="export-svg-menu">
            <summary
              className="secondary"
              title="导出 Canonical SVG（Store + revision）"
              aria-disabled={
                !engineReady || reportBusy || !program || !onExportSvg
              }
            >
              SVG
            </summary>
            <div className="export-svg-menu-panel" role="menu">
              <button
                type="button"
                role="menuitem"
                disabled={
                  !engineReady || reportBusy || !program || !onExportSvg
                }
                onClick={() => onExportSvg?.("floor")}
              >
                当前层
              </button>
              <button
                type="button"
                role="menuitem"
                disabled={
                  !engineReady || reportBusy || !program || !onExportSvg
                }
                onClick={() => onExportSvg?.("all_floors")}
              >
                全部楼层 (zip)
              </button>
              <button
                type="button"
                role="menuitem"
                disabled={
                  !engineReady || reportBusy || !program || !onExportSvg
                }
                onClick={() => onExportSvg?.("snapshot")}
              >
                整图快照
              </button>
            </div>
          </details>
          <details className="export-svg-menu">
            <summary
              className="secondary"
              title="导出 PNG（Canonical SVG → resvg；白底）"
              aria-disabled={
                !engineReady || reportBusy || !program || !onExportPng
              }
            >
              PNG
            </summary>
            <div className="export-svg-menu-panel" role="menu">
              <button
                type="button"
                role="menuitem"
                disabled={
                  !engineReady || reportBusy || !program || !onExportPng
                }
                onClick={() => onExportPng?.("floor", 2048)}
              >
                当前层 2048
              </button>
              <button
                type="button"
                role="menuitem"
                disabled={
                  !engineReady || reportBusy || !program || !onExportPng
                }
                onClick={() => onExportPng?.("floor", 4096)}
              >
                当前层 4096
              </button>
              <button
                type="button"
                role="menuitem"
                disabled={
                  !engineReady || reportBusy || !program || !onExportPng
                }
                onClick={() => onExportPng?.("snapshot", 2048)}
              >
                整图 2048
              </button>
              <button
                type="button"
                role="menuitem"
                disabled={
                  !engineReady || reportBusy || !program || !onExportPng
                }
                onClick={() => onExportPng?.("all_floors", 2048)}
              >
                全部楼层 zip
              </button>
            </div>
          </details>
          <button
            type="button"
            className="secondary"
            disabled={!engineReady || projectBusy}
            onClick={onOpenProjects}
          >
            打开…
          </button>
        </div>
      </div>
      {versionHint ? <p className="warn-hint version-hint">{versionHint}</p> : null}

      <section className="nl-block" aria-label="自然语言需求">
        <h2 className="nl-heading">自然语言</h2>
        <p className="muted tiny gaps-hint">
          解析为 RequirementSpec（不直接出几何）；假设/未知见下方
        </p>
        <textarea
          className="nl-input"
          rows={4}
          value={nlText}
          onChange={(e) => onNlTextChange(e.target.value)}
          placeholder="例：两层三卧两卫，客厅朝南，地块约 11×13 米"
          disabled={!engineReady || loading || nlBusy}
        />
        <div className="actions nl-actions">
          <button
            type="button"
            className="secondary"
            disabled={
              !canParseNl || loading || nlBusy || !nlText.trim()
            }
            onClick={onParseNl}
          >
            {nlBusy ? "解析中…" : "解析需求"}
          </button>
          <button
            type="button"
            disabled={
              !canParseNl || loading || nlBusy || !nlText.trim()
            }
            onClick={onParseAndGenerate}
          >
            {loading || nlBusy ? "处理中…" : "解析并生成"}
          </button>
        </div>
        {nlHint ? <p className="muted tiny nl-hint">{nlHint}</p> : null}
      </section>

      <form className="req-form" onSubmit={handleSubmit}>
        <h2 className="nl-heading">简表</h2>
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
          <button type="submit" disabled={loading || !engineReady}>
            {loading ? "生成中…" : "Generate"}
          </button>
          <button
            type="button"
            className="secondary"
            disabled={loading || !engineReady}
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
          <RequirementGapsPanel
            active={Boolean(program || requirementSpec)}
            assumptions={gaps.assumptions}
            unknowns={gaps.unknowns}
            sourceLabel={gaps.sourceLabel}
            onUpdateAssumption={onUpdateAssumption}
            onRemoveAssumption={onRemoveAssumption}
            onDismissUnknown={onDismissUnknown}
          />
        </section>
      )}

      {!program && requirementSpec && (
        <section className="program-meta">
          <h2>需求规格</h2>
          <p className="muted tiny">尚未生成 Program；仍可查看假设 / 未知</p>
          <RequirementGapsPanel
            active
            assumptions={gaps.assumptions}
            unknowns={gaps.unknowns}
            sourceLabel={gaps.sourceLabel}
            onUpdateAssumption={onUpdateAssumption}
            onRemoveAssumption={onRemoveAssumption}
            onDismissUnknown={onDismissUnknown}
          />
        </section>
      )}
    </aside>
  );
}
