/**
 * Phase 6.4 — 显式假设 / 未知（禁止偷偷补全）。
 * 事实源：RequirementSpec；无则回退 ProgramSummary。
 * Phase 6：保留 assumption.source / unknown.priority（报告 Cover blocking 依赖）。
 */
import { useState } from "react";
import type {
  AssumptionSource,
  UnknownPriority,
} from "../api/client";
import type { AssumptionRow, UnknownRow } from "../lib/requirementGaps";

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
const ASSUMPTION_SOURCE_LABEL: Record<string, string> = {
  user_authorized: "用户授权",
  planseed_default: "产品默认",
  llm_inference: "模型推断",
};

const UNKNOWN_PRIORITY_LABEL: Record<string, string> = {
  blocking: "阻塞",
  recommended: "建议",
  optional: "可选",
};

function assumptionSourceLabel(
  source?: AssumptionSource | string | null,
): string | null {
  if (!source) return null;
  return ASSUMPTION_SOURCE_LABEL[source] ?? source;
}

function unknownPriorityLabel(
  priority?: UnknownPriority | string | null,
): string | null {
  if (!priority) return null;
  return UNKNOWN_PRIORITY_LABEL[priority] ?? priority;
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
          {assumptions.map((a) => {
            const src = assumptionSourceLabel(a.source);
            return (
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
                      {src ? (
                        <span
                          className="gaps-badge muted"
                          title="assumption.source"
                        >
                          {src}
                        </span>
                      ) : null}
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
            );
          })}
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
          {unknowns.map((u) => {
            const pri = unknownPriorityLabel(u.priority);
            const isBlocking = u.priority === "blocking";
            return (
              <li
                key={u.key}
                className={`gaps-row${isBlocking ? " gaps-row-blocking" : ""}`}
              >
                <div className="gaps-main">
                  <code>{u.key}</code>
                  <span>{u.description || "（无说明）"}</span>
                  {pri ? (
                    <span
                      className={`gaps-badge${isBlocking ? " gaps-badge-blocking" : " muted"}`}
                      title="unknown.priority"
                    >
                      {pri}
                    </span>
                  ) : null}
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
            );
          })}
        </ul>
      )}
    </section>
  );
}
