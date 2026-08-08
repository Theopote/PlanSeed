import type { CandidatePayload } from "../api/client";
import { compareScores } from "../lib/compare";

type Props = {
  a: CandidatePayload;
  b: CandidatePayload;
  onClear: () => void;
};

export function ComparePanel({ a, b, onClear }: Props) {
  const sa = a.design_score;
  const sb = b.design_score;
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

  const cmp = compareScores(sa, sb, a.label, b.label);

  return (
    <div className="inspector-body compare-body">
      <div className="compare-head">
        <h3>
          Compare {cmp.labelA} vs {cmp.labelB}
        </h3>
        <button type="button" className="btn-ghost" onClick={onClear}>
          退出
        </button>
      </div>

      <table className="compare-table">
        <thead>
          <tr>
            <th />
            <th>{cmp.labelA}</th>
            <th>{cmp.labelB}</th>
          </tr>
        </thead>
        <tbody>
          {cmp.rows.map((row) => {
            const better =
              row.scoreA - row.scoreB >= 3
                ? "a"
                : row.scoreB - row.scoreA >= 3
                  ? "b"
                  : null;
            return (
              <tr key={row.key}>
                <td>{row.label}</td>
                <td className={better === "a" ? "win" : ""}>
                  {row.scoreA.toFixed(0)}
                </td>
                <td className={better === "b" ? "win" : ""}>
                  {row.scoreB.toFixed(0)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <section className="finding-block sev-positive">
        <h3>{cmp.labelA} 的优势</h3>
        {cmp.advantagesA.length === 0 ? (
          <p className="muted tiny">无明显领先项</p>
        ) : (
          <ul className="adv-list">
            {cmp.advantagesA.map((x) => (
              <li key={x}>+ {x}</li>
            ))}
          </ul>
        )}
      </section>

      <section className="finding-block sev-positive">
        <h3>{cmp.labelB} 的优势</h3>
        {cmp.advantagesB.length === 0 ? (
          <p className="muted tiny">无明显领先项</p>
        ) : (
          <ul className="adv-list">
            {cmp.advantagesB.map((x) => (
              <li key={x}>+ {x}</li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
