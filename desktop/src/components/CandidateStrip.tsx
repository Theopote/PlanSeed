import type { CandidatePayload } from "../api/client";
import { lineageLabel } from "../lib/lineage";

type Props = {
  candidates: CandidatePayload[];
  selectedId: string | null;
  compareId: string | null;
  onSelect: (id: string) => void;
  onComparePick: (id: string) => void;
  onClearCompare: () => void;
};

export function CandidateStrip({
  candidates,
  selectedId,
  compareId,
  onSelect,
  onComparePick,
  onClearCompare,
}: Props) {
  const a = candidates.find((c) => c.id === selectedId);
  const b = candidates.find((c) => c.id === compareId);
  const canCompare =
    a &&
    b &&
    a.id !== b.id &&
    a.design_score &&
    b.design_score &&
    a.revision_status !== "dirty" &&
    b.revision_status !== "dirty";

  const scored = candidates.filter((c) => c.revision_status !== "dirty");
  const anyGateMetric = scored.some(
    (c) => c.metrics?.architectural_gate_pass !== undefined,
  );
  const nonePassGate =
    anyGateMetric &&
    scored.length > 0 &&
    scored.every((c) => {
      const g = c.metrics?.architectural_gate_pass;
      return g === false || g === "false";
    });

  return (
    <footer className="candidate-strip">
      {nonePassGate && (
        <p className="strip-batch-gate-warn" role="status">
          本批次没有通过 Architectural Gate 的推荐方案；下列为门槛外高分补充，请勿当作正常推荐。
        </p>
      )}
      <div className="strip-tools">
        <span className="strip-hint">点击选中 · Alt+点击比较</span>
        {compareId && (
          <button type="button" className="strip-btn" onClick={onClearCompare}>
            清除比较
          </button>
        )}
        {canCompare && (
          <span className="strip-compare-badge">
            {lineageLabel(a.label, a.variant_generation ?? 0)} vs{" "}
            {lineageLabel(b.label, b.variant_generation ?? 0)}
          </span>
        )}
      </div>
      {candidates.length === 0 ? (
        <p className="muted strip-empty">尚无候选</p>
      ) : (
        candidates.map((c) => {
          const active = c.id === selectedId;
          const comparing = c.id === compareId;
          const score =
            c.revision_status === "dirty"
              ? "edited"
              : c.score != null
                ? Math.round(c.score)
                : c.design_score
                  ? Math.round(c.design_score.total_score)
                  : "—";
          const gen = c.variant_generation ?? 0;
          const display = lineageLabel(c.label, gen);
          const selectionRole =
            typeof c.metrics?.selection_role === "string"
              ? c.metrics.selection_role
              : null;
          const selectionLabel =
            typeof c.metrics?.selection_label === "string"
              ? c.metrics.selection_label
              : null;
          const gatePass = c.metrics?.architectural_gate_pass;
          const gateFailed = gatePass === false || gatePass === "false";
          const roleClass =
            selectionRole === "score_fill" || selectionRole === "gate_fill"
              ? "role-fill"
              : selectionRole === "top_score"
                ? "role-top"
                : selectionRole
                  ? "role-axis"
                  : "";
          const tipParts = [
            selectionLabel,
            gateFailed ? "Architectural Gate 未通过（门槛外）" : null,
            "点击选中；Alt+点击设为比较对象",
            c.revision_status === "dirty"
              ? "Modified · Evaluation outdated"
              : null,
            gen > 0 && c.variant_parent_id
              ? `父：${c.variant_parent_id}`
              : null,
            c.lock_snapshot_id ? `锁指纹：${c.lock_snapshot_id}` : null,
          ].filter(Boolean);
          return (
            <button
              key={c.id}
              type="button"
              className={`strip-item ${active ? "active" : ""} ${comparing ? "compare" : ""} ${gen > 0 ? "is-variant" : ""} ${c.revision_status === "dirty" ? "is-dirty" : ""} ${gateFailed ? "is-gate-fail" : ""} ${roleClass}`}
              style={gen > 0 ? { marginLeft: Math.min(gen, 4) * 6 } : undefined}
              title={tipParts.join(" · ")}
              onClick={(e) => {
                if (e.altKey || e.metaKey) {
                  onComparePick(c.id);
                } else {
                  onSelect(c.id);
                }
              }}
            >
              <span className="strip-label">{display}</span>
              <span className="strip-score">{score}</span>
              {selectionLabel ? (
                <span className={`strip-role ${roleClass}`}>{selectionLabel}</span>
              ) : null}
              <span className="strip-seed">s{c.seed}</span>
            </button>
          );
        })
      )}
    </footer>
  );
}
