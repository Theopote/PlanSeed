/** 候选确定性比较 — 与 solver/evaluation/compare.py 规则对齐。 */

import type { DesignFinding, DesignScore } from "../api/client";

export const AXIS_MARGIN = 3;

export type AxisKey =
  | "total_score"
  | "program_score"
  | "spatial_score"
  | "circulation_score"
  | "privacy_score"
  | "environment_score"
  | "technical_score"
  | "robustness_score";

const AXIS_SPECS: Array<{ key: AxisKey; label: string; reason: string }> = [
  { key: "total_score", label: "Total", reason: "综合得分更高" },
  { key: "program_score", label: "Program", reason: "空间清单 / 面积 / 邻接更贴合" },
  { key: "spatial_score", label: "Spatial", reason: "比例与紧凑度更好" },
  {
    key: "circulation_score",
    label: "Circulation",
    reason: "交通更直接 / 可达更好",
  },
  { key: "privacy_score", label: "Privacy", reason: "私密过渡更好" },
  {
    key: "environment_score",
    label: "Environment",
    reason: "朝向 / 外墙更优",
  },
  {
    key: "technical_score",
    label: "Technical",
    reason: "楼梯 / 湿区 / 入口更稳",
  },
  {
    key: "robustness_score",
    label: "Robustness",
    reason: "更少 repair、布局更稳",
  },
];

export type AxisCompareRow = {
  key: AxisKey;
  label: string;
  scoreA: number;
  scoreB: number;
};

export type CandidateComparison = {
  labelA: string;
  labelB: string;
  rows: AxisCompareRow[];
  advantagesA: string[];
  advantagesB: string[];
};

function uniq(items: string[], limit = 8): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const x of items) {
    if (seen.has(x)) continue;
    seen.add(x);
    out.push(x);
    if (out.length >= limit) break;
  }
  return out;
}

function findingBullet(f: DesignFinding): string {
  return (f.title || f.message || f.id).trim();
}

export function compareScores(
  scoreA: DesignScore,
  scoreB: DesignScore,
  labelA = "A",
  labelB = "B",
  axisMargin = AXIS_MARGIN,
): CandidateComparison {
  const rows: AxisCompareRow[] = [];
  const advantagesA: string[] = [];
  const advantagesB: string[] = [];

  for (const { key, label, reason } of AXIS_SPECS) {
    const sa = scoreA[key];
    const sb = scoreB[key];
    rows.push({ key, label, scoreA: sa, scoreB: sb });
    if (key === "total_score") continue;
    const delta = sa - sb;
    if (delta >= axisMargin) {
      advantagesA.push(`${reason}（${label} ${Math.round(sa)} vs ${Math.round(sb)}）`);
    } else if (delta <= -axisMargin) {
      advantagesB.push(`${reason}（${label} ${Math.round(sb)} vs ${Math.round(sa)}）`);
    }
  }

  const posA = new Map(
    scoreA.findings
      .filter((f) => f.severity === "positive")
      .map((f) => [f.id, findingBullet(f)]),
  );
  const posB = new Map(
    scoreB.findings
      .filter((f) => f.severity === "positive")
      .map((f) => [f.id, findingBullet(f)]),
  );
  for (const [id, text] of posA) {
    if (!posB.has(id) && text) advantagesA.push(text);
  }
  for (const [id, text] of posB) {
    if (!posA.has(id) && text) advantagesB.push(text);
  }

  const probA = new Set(
    scoreA.findings.filter((f) => f.severity === "problem").map((f) => f.id),
  );
  const probB = new Set(
    scoreB.findings.filter((f) => f.severity === "problem").map((f) => f.id),
  );
  for (const f of scoreB.findings) {
    if (f.severity === "problem" && !probA.has(f.id)) {
      const t = findingBullet(f);
      if (t) advantagesA.push(`避免：${t}`);
    }
  }
  for (const f of scoreA.findings) {
    if (f.severity === "problem" && !probB.has(f.id)) {
      const t = findingBullet(f);
      if (t) advantagesB.push(`避免：${t}`);
    }
  }

  return {
    labelA,
    labelB,
    rows,
    advantagesA: uniq(advantagesA),
    advantagesB: uniq(advantagesB),
  };
}
