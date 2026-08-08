import type { CandidatePayload } from "../api/client";

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
    b.design_score;

  return (
    <footer className="candidate-strip">
      <div className="strip-tools">
        <span className="strip-hint">点击选中 · Alt+点击比较</span>
        {compareId && (
          <button type="button" className="strip-btn" onClick={onClearCompare}>
            清除比较
          </button>
        )}
        {canCompare && (
          <span className="strip-compare-badge">
            {a.label} vs {b.label}
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
            c.score != null
              ? Math.round(c.score)
              : c.design_score
                ? Math.round(c.design_score.total_score)
                : "—";
          return (
            <button
              key={c.id}
              type="button"
              className={`strip-item ${active ? "active" : ""} ${comparing ? "compare" : ""}`}
              title="点击选中；Alt+点击设为比较对象"
              onClick={(e) => {
                if (e.altKey || e.metaKey) {
                  onComparePick(c.id);
                } else {
                  onSelect(c.id);
                }
              }}
            >
              <span className="strip-label">{c.label}</span>
              <span className="strip-score">{score}</span>
              <span className="strip-seed">s{c.seed}</span>
            </button>
          );
        })
      )}
    </footer>
  );
}
