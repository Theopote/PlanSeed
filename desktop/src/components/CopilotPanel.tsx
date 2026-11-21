import { useCallback, useState } from "react";
import {
  appendCopilotMessage,
  critiqueCandidate,
  listCopilotStrategies,
  parseIntentPatch,
  previewIntentPatch,
  type DesignIntentPatch,
  type TopologyStrategy,
} from "../api/client";

type Props = {
  projectId: string | null;
  selectedCandidate: Record<string, unknown> | null;
  onError: (msg: string | null) => void;
};

export function CopilotPanel({ projectId, selectedCandidate, onError }: Props) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [patch, setPatch] = useState<DesignIntentPatch | null>(null);
  const [previewLines, setPreviewLines] = useState<string[]>([]);
  const [strategies, setStrategies] = useState<TopologyStrategy[]>([]);
  const [critiqueSummary, setCritiqueSummary] = useState<string | null>(null);

  const loadStrategies = useCallback(async () => {
    try {
      const list = await listCopilotStrategies();
      setStrategies(list);
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    }
  }, [onError]);

  const onParse = async () => {
    if (!text.trim()) return;
    setBusy(true);
    onError(null);
    try {
      const p = await parseIntentPatch(text.trim());
      setPatch(p);
      const prev = await previewIntentPatch(p);
      setPreviewLines([
        ...prev.preview.program_deltas,
        ...(prev.preview.warnings.length
          ? [`警告: ${prev.preview.warnings.join("; ")}`]
          : []),
        `锁定: ${prev.locked_rooms.join(", ") || "—"}`,
        `重排: ${prev.mutable_rooms.join(", ") || "—"}`,
      ]);
      if (projectId) {
        await appendCopilotMessage(projectId, "user", text.trim());
        await appendCopilotMessage(
          projectId,
          "assistant",
          `已解析意图补丁（${p.changes.length} 项变更）`,
          { patch: p },
        );
      }
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onCritique = async () => {
    if (!selectedCandidate) {
      onError("请先选中一个候选方案");
      return;
    }
    setBusy(true);
    onError(null);
    try {
      const r = await critiqueCandidate(selectedCandidate);
      const must = (r.must_fix as unknown[] | undefined)?.length ?? 0;
      const should = (r.should_improve as unknown[] | undefined)?.length ?? 0;
      setCritiqueSummary(`必须修复 ${must} · 建议改善 ${should}`);
      if (!strategies.length) await loadStrategies();
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="copilot-panel" aria-label="设计助手">
      <header className="copilot-panel__header">
        <h3>设计助手</h3>
        <p className="muted">针对当前方案下指令；不直接改几何</p>
      </header>
      <textarea
        className="copilot-panel__input"
        rows={3}
        placeholder="例如：保持客厅和厨房不变，主卧大一点，避免穿过卧室…"
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={busy}
      />
      <div className="copilot-panel__actions">
        <button type="button" onClick={onParse} disabled={busy || !text.trim()}>
          解析意图
        </button>
        <button type="button" onClick={onCritique} disabled={busy}>
          审查当前方案
        </button>
        <button type="button" onClick={loadStrategies} disabled={busy}>
          设计策略
        </button>
      </div>
      {critiqueSummary ? (
        <p className="copilot-panel__critique">{critiqueSummary}</p>
      ) : null}
      {strategies.length > 0 ? (
        <ul className="copilot-panel__strategies">
          {strategies.map((s) => (
            <li key={s.id}>
              <strong>{s.label}</strong>
              <span className="muted"> — {s.description}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {patch ? (
        <div className="copilot-panel__preview">
          <h4>意图预览</h4>
          <ul>
            {previewLines.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <p className="muted">确认后请用局部重生成执行（preserve → 锁定房间）</p>
        </div>
      ) : null}
    </section>
  );
}
