import type { CandidatePayload, DesignFinding } from "../api/client";
import { ComparePanel } from "./ComparePanel";

type Props = {
  candidate: CandidatePayload | null;
  compareWith: CandidatePayload | null;
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
  { key: "environment_score", label: "Environment", hint: "朝向 / 外墙" },
  { key: "technical_score", label: "Technical", hint: "楼梯 / 湿区 / 入口" },
  { key: "robustness_score", label: "Robustness", hint: "repair / 稳定性" },
];

const SEV_ORDER = ["problem", "warning", "positive", "info"] as const;

const SEV_LABEL: Record<string, string> = {
  problem: "问题",
  warning: "注意",
  positive: "优势",
  info: "说明",
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

export function Inspector({ candidate, compareWith, onClearCompare }: Props) {
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
                      {list.map((f) => (
                        <li key={f.id}>
                          <div className="finding-title">
                            <span className="finding-cat">{f.category}</span>
                            {f.title}
                          </div>
                          <p className="finding-msg">{f.message}</p>
                          {f.recommended_action && (
                            <p className="finding-action">→ {f.recommended_action}</p>
                          )}
                        </li>
                      ))}
                    </ul>
                  </section>
                );
              })}
            </>
          )}

          {hard.length > 0 && (
            <>
              <h3>Hard violations</h3>
              <ul className="tiny-list bad">
                {hard.map((v, i) => (
                  <li key={`${v.constraint_id}-${i}`}>
                    <code>{v.constraint_id}</code> {v.message}
                  </li>
                ))}
              </ul>
            </>
          )}
          {soft.length > 0 && (
            <>
              <h3>Soft violations</h3>
              <ul className="tiny-list">
                {soft.map((v, i) => (
                  <li key={`${v.constraint_id}-${i}`}>
                    <code>{v.constraint_id}</code> {v.message}
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
