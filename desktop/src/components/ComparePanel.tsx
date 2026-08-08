import { useEffect, useState } from "react";
import {
  compareCandidates,
  type CandidatePayload,
  type CompareResponse,
} from "../api/client";

type Props = {
  a: CandidatePayload;
  b: CandidatePayload;
  onClear: () => void;
};

/** 展示层：比较规则只在 Python POST /api/compare。 */
export function ComparePanel({ a, b, onClear }: Props) {
  const sa = a.design_score;
  const sb = b.design_score;
  const [cmp, setCmp] = useState<CompareResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!sa || !sb) {
      setCmp(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    void compareCandidates(sa, sb, a.label, b.label)
      .then((res) => {
        if (!cancelled) setCmp(res);
      })
      .catch((e) => {
        if (!cancelled) {
          setCmp(null);
          setError(e instanceof Error ? e.message : String(e));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sa, sb, a.label, b.label]);

  if (!sa || !sb) {
    return (
      <div className="inspector-body">
        <p className="empty-hint">两个候选都需要完整评价才能比较</p>
        <button type="button" className="btn-ghost" onClick={onClear}>
          退出比较
        </button>
      </div>
    );
  }

  if (loading && !cmp) {
    return (
      <div className="inspector-body">
        <p className="muted">比较中…</p>
      </div>
    );
  }

  if (error || !cmp) {
    return (
      <div className="inspector-body">
        <p className="error">{error || "比较失败"}</p>
        <button type="button" className="btn-ghost" onClick={onClear}>
          退出比较
        </button>
      </div>
    );
  }

  return (
    <div className="inspector-body compare-body">
      <div className="compare-head">
        <h3>
          Compare {cmp.label_a} vs {cmp.label_b}
        </h3>
        <button type="button" className="btn-ghost" onClick={onClear}>
          退出
        </button>
      </div>

      <table className="compare-table">
        <thead>
          <tr>
            <th />
            <th>{cmp.label_a}</th>
            <th>{cmp.label_b}</th>
          </tr>
        </thead>
        <tbody>
          {cmp.rows.map((row) => {
            const better =
              row.score_a - row.score_b >= 3
                ? "a"
                : row.score_b - row.score_a >= 3
                  ? "b"
                  : null;
            return (
              <tr key={row.key}>
                <td>{row.label}</td>
                <td className={better === "a" ? "win" : ""}>
                  {row.score_a.toFixed(0)}
                </td>
                <td className={better === "b" ? "win" : ""}>
                  {row.score_b.toFixed(0)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <section className="finding-block sev-positive">
        <h3>{cmp.label_a} 的优势</h3>
        {cmp.advantages_a.length === 0 ? (
          <p className="muted tiny">无明显领先项</p>
        ) : (
          <ul className="adv-list">
            {cmp.advantages_a.map((x) => (
              <li key={x}>+ {x}</li>
            ))}
          </ul>
        )}
      </section>

      <section className="finding-block sev-positive">
        <h3>{cmp.label_b} 的优势</h3>
        {cmp.advantages_b.length === 0 ? (
          <p className="muted tiny">无明显领先项</p>
        ) : (
          <ul className="adv-list">
            {cmp.advantages_b.map((x) => (
              <li key={x}>+ {x}</li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
