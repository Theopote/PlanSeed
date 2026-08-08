/**
 * Phase 6.4 — 显式假设 / 未知（禁止偷偷补全）。
 * 事实源：RequirementSpec；无则回退 ProgramSummary。
 */
import { useState } from "react";
import type { RequirementSpecPayload } from "../api/client";

export type AssumptionRow = {
  key: string;
  value: unknown;
  reason?: string;
};

export type UnknownRow = {
  key: string;
  description?: string;
};

type Props = {
  assumptions: AssumptionRow[];
  unknowns: UnknownRow[];
  /** 是否已有 program / spec（决定是否显示空态） */
  active: boolean;
  sourceLabel: "requirementSpec" | "program" | null;
  onUpdateAssumption: (
    key: string,
    patch: { value: string; reason: string },
  ) => void;
  onRemoveAssumption: (key: string) => void;
  onDismissUnknown: (key: string) => void;
};

function valueToEditString(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  return String(value);
}

/** App 回调用：把编辑框字符串还原为较合理的 JSON 值。 */
export function coerceAssumptionValue(
  raw: string,
  previous: unknown,
): unknown {
  const t = raw.trim();
  if (t === "") return previous;
  if (t === "true") return true;
  if (t === "false") return false;
  if (/^-?\d+(\.\d+)?$/.test(t)) {
    const n = Number(t);
    if (!Number.isNaN(n)) return n;
  }
  return raw;
}

export function resolveRequirementGaps(
  spec: RequirementSpecPayload | null,
  program: {
    assumptions: AssumptionRow[];
    unknowns: UnknownRow[];
  } | null,
): {
  assumptions: AssumptionRow[];
  unknowns: UnknownRow[];
  sourceLabel: "requirementSpec" | "program" | null;
} {
  if (spec) {
    const assumptions =
      spec.assumptions !== undefined
        ? spec.assumptions
        : (program?.assumptions ?? []);
    const unknowns =
      spec.unknowns !== undefined
        ? (spec.unknowns ?? []).map((u) => ({
            key: u.key,
            description: u.description ?? "",
          }))
        : (program?.unknowns ?? []);
    return {
      assumptions,
      unknowns,
      sourceLabel: "requirementSpec",
    };
  }
  if (program) {
    return {
      assumptions: program.assumptions,
      unknowns: program.unknowns,
      sourceLabel: "program",
    };
  }
  return { assumptions: [], unknowns: [], sourceLabel: null };
}

export function RequirementGapsPanel({
  assumptions,
  unknowns,
  active,
  sourceLabel,
  onUpdateAssumption,
  onRemoveAssumption,
  onDismissUnknown,
}: Props) {
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [editReason, setEditReason] = useState("");

  if (!active) return null;

  const startEdit = (a: AssumptionRow) => {
    setEditingKey(a.key);
    setEditValue(valueToEditString(a.value));
    setEditReason(a.reason ?? "");
  };

  return (
    <section className="requirement-gaps" aria-label="假设与未知">
      <h3>假设</h3>
      <p className="muted tiny gaps-hint">
        系统或解析器的显式默认，须可改可删
        {sourceLabel
          ? ` · 来源 ${sourceLabel === "requirementSpec" ? "需求规格" : "程序摘要"}`
          : ""}
      </p>
      {assumptions.length === 0 ? (
        <p className="muted tiny">无显式假设</p>
      ) : (
        <ul className="tiny-list gaps-list">
          {assumptions.map((a) => (
            <li key={a.key} className="gaps-row">
              {editingKey === a.key ? (
                <div className="gaps-edit">
                  <code>{a.key}</code>
                  <label className="gaps-field">
                    <span>值</span>
                    <input
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      aria-label={`假设 ${a.key} 的值`}
                    />
                  </label>
                  <label className="gaps-field">
                    <span>理由</span>
                    <input
                      value={editReason}
                      onChange={(e) => setEditReason(e.target.value)}
                      aria-label={`假设 ${a.key} 的理由`}
                    />
                  </label>
                  <div className="gaps-actions">
                    <button
                      type="button"
                      className="secondary tiny-btn"
                      onClick={() => {
                        onUpdateAssumption(a.key, {
                          value: editValue,
                          reason: editReason,
                        });
                        setEditingKey(null);
                      }}
                    >
                      保存
                    </button>
                    <button
                      type="button"
                      className="secondary tiny-btn"
                      onClick={() => setEditingKey(null)}
                    >
                      取消
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="gaps-main">
                    <code>{a.key}</code>
                    <span>
                      = {String(a.value)}
                      {a.reason ? ` — ${a.reason}` : ""}
                    </span>
                  </div>
                  <div className="gaps-actions">
                    <button
                      type="button"
                      className="secondary tiny-btn"
                      onClick={() => startEdit(a)}
                    >
                      改
                    </button>
                    <button
                      type="button"
                      className="secondary tiny-btn"
                      onClick={() => onRemoveAssumption(a.key)}
                    >
                      清除
                    </button>
                  </div>
                </>
              )}
            </li>
          ))}
        </ul>
      )}

      <h3>未知</h3>
      <p className="muted tiny gaps-hint">
        未提供且未推断的项；关闭只表示已知悉，不会自动填值
      </p>
      {unknowns.length === 0 ? (
        <p className="muted tiny">无未决未知</p>
      ) : (
        <ul className="tiny-list gaps-list warn">
          {unknowns.map((u) => (
            <li key={u.key} className="gaps-row">
              <div className="gaps-main">
                <code>{u.key}</code>
                <span>{u.description || "（无说明）"}</span>
              </div>
              <div className="gaps-actions">
                <button
                  type="button"
                  className="secondary tiny-btn"
                  onClick={() => onDismissUnknown(u.key)}
                  title="从列表移除；不会自动补全该字段"
                >
                  已知悉
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
