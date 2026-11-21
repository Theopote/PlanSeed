import { useCallback, useEffect, useState } from "react";
import type {
  CandidatePayload,
  GenerateResponse,
  LayoutLocks,
  ProgramSummary,
  RequirementSpecPayload,
} from "../api/client";
import {
  appendCopilotMessage,
  applyIntentPatch,
  critiqueCandidate,
  generateWithStrategy,
  listCopilotStrategies,
  optimizeCandidate,
  parseIntentPatch,
  previewIntentPatch,
  type DesignIntentPatch,
  type TopologyStrategy,
} from "../api/client";
import { programPlacementsFromCandidate } from "../lib/regeneration";

type Props = {
  projectId: string | null;
  selectedCandidate: CandidatePayload | null;
  program: ProgramSummary | null;
  locks: LayoutLocks;
  requirementSpec: RequirementSpecPayload | null;
  regenerating: boolean;
  beginAsyncRequest: () => number;
  isAsyncCurrent: (token: number) => boolean;
  onError: (msg: string | null) => void;
  onMergeGenerate: (
    data: GenerateResponse,
    mode?: "replace" | "variant",
    token?: number,
  ) => void;
  onMergeBest: (best: CandidatePayload, token?: number) => void;
};

export function CopilotPanel({
  projectId,
  selectedCandidate,
  program,
  locks,
  requirementSpec,
  regenerating,
  beginAsyncRequest,
  isAsyncCurrent,
  onError,
  onMergeGenerate,
  onMergeBest,
}: Props) {
  /** 未保存项目也写入进程内会话，首次 Save 可一并持久化 */
  const conversationKey = projectId ?? "draft";
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [patch, setPatch] = useState<DesignIntentPatch | null>(null);
  const [previewLines, setPreviewLines] = useState<string[]>([]);
  const [strategies, setStrategies] = useState<TopologyStrategy[]>([]);
  const [critiqueSummary, setCritiqueSummary] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  const useBenchmark = !requirementSpec;
  const disabled = busy || regenerating;

  // 切换项目：清空与旧候选相关的局部 UI 状态
  useEffect(() => {
    setPatch(null);
    setPreviewLines([]);
    setCritiqueSummary(null);
    setStatus(null);
    setText("");
    setBusy(false);
  }, [projectId]);

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
    const token = beginAsyncRequest();
    const keyAtStart = conversationKey;
    setBusy(true);
    onError(null);
    setStatus(null);
    try {
      const p = await parseIntentPatch(text.trim());
      if (!isAsyncCurrent(token)) return;
      setPatch(p);
      const prev = await previewIntentPatch(p, {
        use_benchmark: useBenchmark,
        requirements: requirementSpec,
      });
      if (!isAsyncCurrent(token)) return;
      setPreviewLines([
        ...prev.preview.program_deltas,
        ...(prev.preview.warnings.length
          ? [`警告: ${prev.preview.warnings.join("; ")}`]
          : []),
        `锁定: ${prev.locked_rooms.join(", ") || "—"}`,
        `重排: ${prev.mutable_rooms.join(", ") || "—"}`,
      ]);
      await appendCopilotMessage(keyAtStart, "user", text.trim());
      await appendCopilotMessage(
        keyAtStart,
        "assistant",
        `已解析意图补丁（${p.changes.length} 项变更）`,
        { patch: p },
      );
    } catch (e) {
      if (isAsyncCurrent(token)) {
        onError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      if (isAsyncCurrent(token)) setBusy(false);
    }
  };

  const onApply = async () => {
    if (!patch) return;
    if (!selectedCandidate || !program) {
      onError("请先选中候选并完成一次生成");
      return;
    }
    const token = beginAsyncRequest();
    const keyAtStart = conversationKey;
    setBusy(true);
    onError(null);
    setStatus("正在应用意图并局部重生成…");
    try {
      const basePlacements = programPlacementsFromCandidate(
        selectedCandidate,
        program,
      );
      const data = await applyIntentPatch(patch, {
        base_placements: basePlacements,
        locks,
        requirements: requirementSpec,
        use_benchmark: useBenchmark,
        base_seed: (selectedCandidate.seed ?? 0) + 1,
      });
      if (!isAsyncCurrent(token)) return;
      onMergeGenerate(data, "variant", token);
      setStatus(`已生成 ${data.candidates.length} 个局部方案`);
      await appendCopilotMessage(
        keyAtStart,
        "assistant",
        `已执行意图补丁，得到 ${data.candidates.length} 个候选`,
      );
    } catch (e) {
      if (isAsyncCurrent(token)) {
        onError(e instanceof Error ? e.message : String(e));
        setStatus(null);
      }
    } finally {
      if (isAsyncCurrent(token)) setBusy(false);
    }
  };

  const onCritique = async () => {
    if (!selectedCandidate) {
      onError("请先选中一个候选方案");
      return;
    }
    const token = beginAsyncRequest();
    setBusy(true);
    onError(null);
    try {
      const r = await critiqueCandidate(
        selectedCandidate as unknown as Record<string, unknown>,
        { use_benchmark: useBenchmark, requirements: requirementSpec },
      );
      if (!isAsyncCurrent(token)) return;
      const must = (r.must_fix as unknown[] | undefined)?.length ?? 0;
      const should = (r.should_improve as unknown[] | undefined)?.length ?? 0;
      setCritiqueSummary(`必须修复 ${must} · 建议改善 ${should}`);
      if (!strategies.length) await loadStrategies();
    } catch (e) {
      if (isAsyncCurrent(token)) {
        onError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      if (isAsyncCurrent(token)) setBusy(false);
    }
  };

  const onOptimize = async () => {
    if (!selectedCandidate) {
      onError("请先选中一个候选方案");
      return;
    }
    const token = beginAsyncRequest();
    setBusy(true);
    onError(null);
    setStatus("受控优化中…");
    try {
      const r = await optimizeCandidate(
        selectedCandidate as unknown as Record<string, unknown>,
        {
          use_benchmark: useBenchmark,
          requirements: requirementSpec,
          locks,
          max_rounds: 2,
          candidate_budget: 4,
        },
      );
      if (!isAsyncCurrent(token)) return;
      if (r.improved && r.best) {
        onMergeBest(r.best, token);
        setStatus(`优化结束：${r.stopped_reason}，已加入最佳候选`);
      } else {
        setStatus(`优化结束：${r.stopped_reason}（无改善，未追加候选）`);
      }
    } catch (e) {
      if (isAsyncCurrent(token)) {
        onError(e instanceof Error ? e.message : String(e));
        setStatus(null);
      }
    } finally {
      if (isAsyncCurrent(token)) setBusy(false);
    }
  };

  const onStrategyGenerate = async (strategyId: string) => {
    const token = beginAsyncRequest();
    const keyAtStart = conversationKey;
    setBusy(true);
    onError(null);
    setStatus(`按策略「${strategyId}」生成中…`);
    try {
      const data = await generateWithStrategy(strategyId, {
        requirements: requirementSpec,
        use_benchmark: useBenchmark,
      });
      if (!isAsyncCurrent(token)) return;
      // 默认追加为可比较分支，不覆盖用户当前候选
      onMergeGenerate(data, "variant", token);
      const label =
        strategies.find((s) => s.id === strategyId)?.label ?? strategyId;
      setStatus(`策略「${label}」生成 ${data.candidates.length} 个候选`);
      await appendCopilotMessage(
        keyAtStart,
        "assistant",
        `已按策略「${label}」生成方案`,
        { strategy_id: strategyId },
      );
    } catch (e) {
      if (isAsyncCurrent(token)) {
        onError(e instanceof Error ? e.message : String(e));
        setStatus(null);
      }
    } finally {
      if (isAsyncCurrent(token)) setBusy(false);
    }
  };

  return (
    <section className="copilot-panel" aria-label="设计助手">
      <header className="copilot-panel__header">
        <h3>设计助手</h3>
        <p className="muted">针对当前方案下指令；几何仍由求解器证明</p>
      </header>
      <textarea
        className="copilot-panel__input"
        rows={3}
        value={text}
        disabled={disabled}
        placeholder="例如：保持客厅和厨房不变，主卧大一点，避免穿过卧室"
        onChange={(e) => setText(e.target.value)}
      />
      <div className="copilot-panel__actions">
        <button type="button" disabled={disabled} onClick={() => void onParse()}>
          解析意图
        </button>
        <button
          type="button"
          disabled={disabled || !patch}
          onClick={() => void onApply()}
        >
          应用并局部重生成
        </button>
        <button
          type="button"
          disabled={disabled || !selectedCandidate}
          onClick={() => void onCritique()}
        >
          审查
        </button>
        <button
          type="button"
          disabled={disabled || !selectedCandidate}
          onClick={() => void onOptimize()}
        >
          受控优化
        </button>
      </div>
      {previewLines.length > 0 && (
        <ul className="copilot-panel__preview">
          {previewLines.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}
      {critiqueSummary && (
        <p className="copilot-panel__critique muted">{critiqueSummary}</p>
      )}
      {status && <p className="copilot-panel__status muted">{status}</p>}
      <div className="copilot-panel__strategies">
        <button
          type="button"
          className="linkish"
          disabled={disabled}
          onClick={() => void loadStrategies()}
        >
          加载设计策略
        </button>
        {strategies.map((s) => (
          <button
            key={s.id}
            type="button"
            disabled={disabled}
            title={s.description}
            onClick={() => void onStrategyGenerate(s.id)}
          >
            {s.label}
          </button>
        ))}
      </div>
    </section>
  );
}
