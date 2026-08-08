import { useCallback, useEffect, useState } from "react";
import {
  checkHealth,
  generateBenchmark,
  generateFromForm,
  resolveEngineBase,
  setApiBase,
  type CandidatePayload,
  type GenerateResponse,
  type ProgramSummary,
  type RejectedCandidatePayload,
  type RequirementForm,
} from "./api/client";
import { CandidateStrip } from "./components/CandidateStrip";
import { FloorplanView } from "./components/FloorplanView";
import { Inspector } from "./components/Inspector";
import { RequirementsPanel } from "./components/RequirementsPanel";
import "./App.css";

const DEFAULT_FORM: RequirementForm = {
  width: 11,
  depth: 13,
  floor_count: 2,
  bedrooms: 3,
  bathrooms: 2,
  has_garage: true,
  prefer_south_facing_living: true,
};

type EngineReadyPayload = {
  url: string;
  ready: boolean;
  error?: string;
};

function App() {
  const [form, setForm] = useState<RequirementForm>(DEFAULT_FORM);
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [engineHint, setEngineHint] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [program, setProgram] = useState<ProgramSummary | null>(null);
  const [candidates, setCandidates] = useState<CandidatePayload[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [compareId, setCompareId] = useState<string | null>(null);
  const [highlightRoomIds, setHighlightRoomIds] = useState<string[]>([]);
  const [rejectedCandidates, setRejectedCandidates] = useState<
    RejectedCandidatePayload[]
  >([]);
  const [violationSummary, setViolationSummary] = useState<Record<string, number>>(
    {},
  );
  const [stats, setStats] = useState<{
    generated: number;
    valid: number;
    rejected: number;
  } | null>(null);

  const selected = candidates.find((c) => c.id === selectedId) ?? null;
  const compareWith =
    compareId && compareId !== selectedId
      ? (candidates.find((c) => c.id === compareId) ?? null)
      : null;

  useEffect(() => {
    let cancelled = false;
    let attempts = 0;
    let unlisten: (() => void) | undefined;

    async function boot() {
      await resolveEngineBase();

      try {
        const { listen } = await import("@tauri-apps/api/event");
        unlisten = await listen<EngineReadyPayload>("engine-ready", (ev) => {
          if (cancelled) return;
          const p = ev.payload;
          if (p.url) setApiBase(p.url);
          setApiOk(p.ready);
          setEngineHint(
            p.ready
              ? null
              : p.error || "本地引擎启动超时，请稍后重试或检查杀毒拦截",
          );
        });
      } catch {
        /* 浏览器模式：无 Tauri 事件 */
      }

      async function ping() {
        const ok = await checkHealth();
        if (cancelled) return;
        if (ok) {
          setApiOk(true);
          setEngineHint(null);
          return;
        }
        setApiOk((prev) => (prev === true ? true : false));
        attempts += 1;
        if (attempts < 90) {
          window.setTimeout(() => {
            if (!cancelled) void ping();
          }, 500);
        }
      }
      void ping();
    }

    void boot();
    const id = window.setInterval(() => {
      void checkHealth().then((ok) => {
        if (!cancelled && ok) {
          setApiOk(true);
          setEngineHint(null);
        }
      });
    }, 8000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
      unlisten?.();
    };
  }, []);

  const applyResult = useCallback((data: GenerateResponse) => {
    setProgram(data.program_summary);
    setCandidates(data.candidates);
    setStats({
      generated: data.generated,
      valid: data.valid,
      rejected: data.rejected,
    });
    setRejectedCandidates(data.rejected_candidates ?? []);
    setViolationSummary(data.violation_summary ?? {});
    setSelectedId(data.candidates[0]?.id ?? null);
    setCompareId(null);
    setHighlightRoomIds([]);
    setError(null);
  }, []);

  const run = useCallback(
    async (mode: "form" | "benchmark") => {
      setLoading(true);
      setError(null);
      try {
        const data =
          mode === "benchmark"
            ? await generateBenchmark()
            : await generateFromForm(form);
        applyResult(data);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    },
    [applyResult, form],
  );

  const onComparePick = useCallback(
    (id: string) => {
      if (id === selectedId) return;
      setCompareId(id);
      setHighlightRoomIds([]);
    },
    [selectedId],
  );

  const onSelectCandidate = useCallback((id: string) => {
    setSelectedId(id);
    setHighlightRoomIds([]);
  }, []);

  const emptyHint =
    apiOk === false
      ? engineHint || "本地引擎启动中，窗口已就绪，请稍候…"
      : apiOk === null
        ? "正在连接本地引擎…"
        : "点击 Generate 或「基准案例」生成平面";

  return (
    <div className="app-shell">
      <div className="app-main">
        <RequirementsPanel
          form={form}
          onChange={setForm}
          onGenerate={() => void run("form")}
          onBenchmark={() => void run("benchmark")}
          loading={loading}
          apiOk={apiOk}
          program={program}
          error={error ?? engineHint}
          stats={stats}
          rejectedCandidates={rejectedCandidates}
          violationSummary={violationSummary}
        />
        <FloorplanView
          svg={selected?.svg ?? null}
          emptyHint={emptyHint}
          highlightRoomIds={highlightRoomIds}
        />
        <Inspector
          candidate={selected}
          compareWith={compareWith}
          program={program}
          highlightRoomIds={highlightRoomIds}
          onHighlightRooms={setHighlightRoomIds}
          onClearCompare={() => setCompareId(null)}
        />
      </div>
      <CandidateStrip
        candidates={candidates}
        selectedId={selectedId}
        compareId={compareId}
        onSelect={onSelectCandidate}
        onComparePick={onComparePick}
        onClearCompare={() => setCompareId(null)}
      />
    </div>
  );
}

export default App;
