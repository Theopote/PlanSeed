import type { CandidatePayload, DesignFinding, ProgramSummary } from "../api/client";
import { AXIS_SCOPE } from "../lib/axisScope";
import { ComparePanel } from "./ComparePanel";

type Props = {
  candidate: CandidatePayload | null;
  compareWith: CandidatePayload | null;
  program: ProgramSummary | null;
  highlightRoomIds: string[];
  onHighlightRooms: (roomIds: string[]) => void;
  onClearCompare: () => void;
};

const SCORE_ROWS: Array<{
  key: keyof NonNullable<CandidatePayload["design_score"]>;
  label: string;
  hint: string;
}> = [
  { key: "program_score", label: "Program", hint: "空间清单 / 面积 / 邻接" },
  { key: "spatial_score", label: "Spatial", hint: "比例 / 紧凑 / 形状" },
  { key: "circulation_score", label: "Circulation", hint: "可达 / 深度 / 穿堂" },
  { key: "privacy_score", label: "Privacy", hint: "动静 / 过渡 / 穿卧" },
  {
    key: "environment_score",
    label: AXIS_SCOPE.environment.label,
    hint: AXIS_SCOPE.environment.hint,
  },
  {
    key: "technical_score",
    label: AXIS_SCOPE.technical.label,
    hint: AXIS_SCOPE.technical.hint,
  },
  { key: "robustness_score", label: "Robustness", hint: "repair / 稳定性" },
];

const SEV_ORDER = ["problem", "warning", "positive", "info"] as const;

const SEV_LABEL: Record<string, string> = {
  problem: "问题",
  warning: "注意",
  positive: "优势",
  info: "说明",
};

const CATEGORY_ZH: Record<string, string> = {
  program: "空间程序",
  spatial: "空间形态",
  circulation: "交通流线",
  privacy: "私密分区",
  environment: AXIS_SCOPE.environment.categoryZh,
  technical: AXIS_SCOPE.technical.categoryZh,
  robustness: "稳健性",
};

function groupFindings(findings: DesignFinding[]) {
  const groups: Record<string, DesignFinding[]> = {
    problem: [],
    warning: [],
    positive: [],
    info: [],
  };
  for (const f of findings) {
    const k = f.severity in groups ? f.severity : "info";
    groups[k].push(f);
  }
  return groups;
}

function roomLabel(program: ProgramSummary | null, id: string): string {
  const name = program?.rooms.find((r) => r.id === id)?.name;
  return name || id;
}

function sameIds(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  const sa = [...a].sort().join("\0");
  const sb = [...b].sort().join("\0");
  return sa === sb;
}

function formatMeasured(metric: string | null, value: number | null): string | null {
  if (metric == null && value == null) return null;
  if (metric != null && value != null) {
    return `${metric} = ${Number.isInteger(value) ? value : value.toFixed(2)}`;
  }
  if (metric != null) return metric;
  return String(value);
}

export function Inspector({
  candidate,
  compareWith,
  program,
  highlightRoomIds,
  onHighlightRooms,
  onClearCompare,
}: Props) {
  if (candidate && compareWith && candidate.id !== compareWith.id) {
    return (
      <aside className="panel panel-right">
        <header className="panel-head compact">
          <h2>Inspector</h2>
          <p className="muted">方案比较</p>
        </header>
        <ComparePanel a={candidate} b={compareWith} onClear={onClearCompare} />
      </aside>
    );
  }

  const ds = candidate?.design_score ?? null;
  const hard = candidate?.validation?.hard_violations ?? [];
  const soft = candidate?.validation?.soft_violations ?? [];
  const findings = ds?.findings ?? [];
  const groups = groupFindings(findings);

  function toggleFinding(f: DesignFinding) {
    if (!f.room_ids.length) {
      onHighlightRooms([]);
      return;
    }
    if (sameIds(highlightRoomIds, f.room_ids)) {
      onHighlightRooms([]);
    } else {
      onHighlightRooms(f.room_ids);
    }
  }

  return (
    <aside className="panel panel-right">
      <header className="panel-head compact">
        <h2>Inspector</h2>
        {candidate && (
          <p className="muted">
            {candidate.label} · seed {candidate.seed}
            {candidate.score != null ? ` · ${candidate.score.toFixed(1)}` : ""}
          </p>
        )}
      </header>

      {!candidate && (
        <p className="empty-hint">
          选择下方候选查看评价；Alt+点击另一候选可比较
        </p>
      )}

      {candidate && (
        <div className="inspector-body">
          {ds && (
            <>
              <div className="total-score">
                <span>Total</span>
                <strong>{ds.total_score.toFixed(1)}</strong>
              </div>
              <ul className="score-rows">
                {SCORE_ROWS.map(({ key, label, hint }) => {
                  const v = ds[key];
                  if (typeof v !== "number") return null;
                  return (
                    <li key={key} title={hint}>
                      <span>
                        {label}
                        <span className="axis-hint"> {hint}</span>
                      </span>
                      <span>{v.toFixed(1)}</span>
                    </li>
                  );
                })}
              </ul>

              {SEV_ORDER.map((sev) => {
                const list = groups[sev];
                if (!list.length) return null;
                return (
                  <section key={sev} className={`finding-block sev-${sev}`}>
                    <h3>{SEV_LABEL[sev]}</h3>
                    <ul className="finding-list">
                      {list.map((f) => {
                        const active =
                          f.room_ids.length > 0 &&
                          sameIds(highlightRoomIds, f.room_ids);
                        const measured = formatMeasured(f.metric, f.measured_value);
                        const rooms = f.room_ids
                          .map((id) => roomLabel(program, id))
                          .join("、");
                        const catZh = CATEGORY_ZH[f.category] ?? f.category;
                        return (
                          <li key={f.id}>
                            <button
                              type="button"
                              className={`finding-item ${active ? "active" : ""} ${f.room_ids.length ? "clickable" : ""}`}
                              onClick={() => toggleFinding(f)}
                              disabled={!f.room_ids.length}
                            >
                              <div className="finding-title">
                                <span className="finding-cat">{catZh}</span>
                                {f.title}
                              </div>
                              <p className="finding-msg">{f.message}</p>
                              {(rooms || measured) && (
                                <p className="finding-meta">
                                  {rooms && <span>房间：{rooms}</span>}
                                  {rooms && measured && <span> · </span>}
                                  {measured && <span>{measured}</span>}
                                </p>
                              )}
                              {f.recommended_action && (
                                <p className="finding-action">
                                  → {f.recommended_action}
                                </p>
                              )}
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </section>
                );
              })}
              {findings.length > 0 && (
                <p className="finding-disclaimer muted">
                  以上为设计启发式，不构成规范合规或法规审查结论。
                </p>
              )}
            </>
          )}

          {hard.length > 0 && (
            <>
              <h3>硬性违规</h3>
              <ul className="tiny-list bad">
                {hard.map((v, i) => (
                  <li key={`${v.constraint_id}-${i}`}>
                    <span>{v.message}</span>
                    <code className="violation-id">{v.constraint_id}</code>
                  </li>
                ))}
              </ul>
            </>
          )}
          {soft.length > 0 && (
            <>
              <h3>软性约束</h3>
              <ul className="tiny-list">
                {soft.map((v, i) => (
                  <li key={`${v.constraint_id}-${i}`}>
                    <span>{v.message}</span>
                    <code className="violation-id">{v.constraint_id}</code>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </aside>
  );
}
