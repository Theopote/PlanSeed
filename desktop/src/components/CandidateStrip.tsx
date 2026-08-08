import type { CandidatePayload } from "../api/client";

type Props = {
  candidates: CandidatePayload[];
  selectedId: string | null;
  onSelect: (id: string) => void;
};

export function CandidateStrip({ candidates, selectedId, onSelect }: Props) {
  return (
    <footer className="candidate-strip">
      {candidates.length === 0 ? (
        <p className="muted strip-empty">尚无候选</p>
      ) : (
        candidates.map((c) => {
          const active = c.id === selectedId;
          const score =
            c.score != null ? Math.round(c.score) : c.design_score
              ? Math.round(c.design_score.total_score)
              : "—";
          return (
            <button
              key={c.id}
              type="button"
              className={`strip-item ${active ? "active" : ""}`}
              onClick={() => onSelect(c.id)}
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
