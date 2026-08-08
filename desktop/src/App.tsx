import { useCallback, useEffect, useRef, useState } from "react";
import {
  checkHealth,
  generateBenchmark,
  generateFromForm,
  resolveEngineBase,
  retryEngine,
  setApiBase,
  type CandidatePayload,
  type EngineLifecycle,
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

type EngineStatusPayload = {
  status: EngineLifecycle;
  url: string;
  error?: string;
};

function App() {
  const [form, setForm] = useState<RequirementForm>(DEFAULT_FORM);
  const [engineStatus, setEngineStatus] = useState<EngineLifecycle>("STARTING");
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

  const engineStatusRef = useRef<EngineLifecycle>(engineStatus);
  engineStatusRef.current = engineStatus;

  const selected = candidates.find((c) => c.id === selectedId) ?? null;
  const compareWith =
    compareId && compareId !== selectedId
      ? (candidates.find((c) => c.id === compareId) ?? null)
      : null;

  const applyEngineStatus = useCallback((status: EngineLifecycle, errorMsg?: string) => {
    setEngineStatus(status);
    engineStatusRef.current = status;
    if (status === "READY") {
      setEngineHint(null);
    } else if (status === "ERROR") {
      setEngineHint(errorMsg || "本地引擎异常，可点击重试");
    } else if (status === "STOPPED") {
      setEngineHint("引擎已停止");
    } else {
      setEngineHint(null);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    let attempts = 0;
    let unlisten: (() => void) | undefined;
    let inTauri = false;

    async function boot() {
      await resolveEngineBase();

      try {
        const { listen } = await import("@tauri-apps/api/event");
        inTauri = true;
        // 唯一事实源：engine-status（不再听 engine-ready）
        unlisten = await listen<EngineStatusPayload>("engine-status", (ev) => {
          if (cancelled) return;
          const p = ev.payload;
          if (p.url) setApiBase(p.url);
          applyEngineStatus(p.status, p.error);
        });
      } catch {
        /* 浏览器模式：无 Tauri 事件，靠 health 轮询 */
      }

      // 浏览器 / 事件未到前的启动探测；Tauri 下就绪以 engine-status 为准
      async function ping() {
        const ok = await checkHealth();
        if (cancelled) return;
        if (ok) {
          if (!inTauri || engineStatusRef.current === "STARTING") {
            applyEngineStatus("READY");
          }
          return;
        }
        attempts += 1;
        if (attempts < 90) {
          window.setTimeout(() => {
            if (!cancelled) void ping();
          }, 500);
        } else if (!inTauri || engineStatusRef.current === "STARTING") {
          applyEngineStatus("ERROR", "本地引擎启动超时，请重试或检查杀毒拦截");
        }
      }
      void ping();
    }

    void boot();
    // reuse / 失联兜底：连续失败才 ERROR（自启引擎以 Rust watch_child_exit 为准）
    const HEALTH_INTERVAL_MS = 2000;
    const HEALTH_FAIL_THRESHOLD = 3;
    let consecutiveHealthFailures = 0;
    const id = window.setInterval(() => {
      void checkHealth().then((ok) => {
        if (cancelled) return;
        const cur = engineStatusRef.current;
        if (ok) {
          consecutiveHealthFailures = 0;
          if (cur === "READY" || cur === "STARTING") {
            applyEngineStatus("READY");
          }
          return;
        }
        if (cur !== "READY") {
          consecutiveHealthFailures = 0;
          return;
        }
        consecutiveHealthFailures += 1;
        if (consecutiveHealthFailures >= HEALTH_FAIL_THRESHOLD) {
          consecutiveHealthFailures = 0;
          applyEngineStatus("ERROR", "本地引擎连接中断");
        }
      });
    }, HEALTH_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
      unlisten?.();
    };
  }, [applyEngineStatus]);

  const onRetryEngine = useCallback(async () => {
    applyEngineStatus("STARTING");
    setEngineHint(null);
    try {
      await retryEngine();
      await resolveEngineBase();
    } catch (e) {
      applyEngineStatus(
        "ERROR",
        e instanceof Error ? e.message : "重试失败",
      );
    }
  }, [applyEngineStatus]);

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
    engineStatus === "ERROR"
      ? engineHint || "本地引擎异常，请重试"
      : engineStatus === "STARTING"
        ? "正在连接本地引擎…"
        : engineStatus === "STOPPED"
          ? "引擎已停止"
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
          engineStatus={engineStatus}
          onRetryEngine={() => void onRetryEngine()}
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
