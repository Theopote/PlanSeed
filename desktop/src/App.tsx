import { useCallback, useEffect, useRef, useState } from "react";
import {
  checkHealth,
  generateBenchmark,
  generateFromForm,
  generateFromProgram,
  resolveEngineBase,
  retryEngine,
  setApiBase,
  type CandidatePayload,
  type EngineLifecycle,
  type GenerateResponse,
  type LayoutLocks,
  type LockedRoomRect,
  type LockedStairCore,
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
  const [selectedRoomId, setSelectedRoomId] = useState<string | null>(null);
  const [locks, setLocks] = useState<LayoutLocks>({ rooms: [], stair: null });
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
          applyEngineStatus("ERROR", "本地引擎连接中断，请重试。");
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

  const relabel = useCallback((list: CandidatePayload[]) => {
    return list.map((c, i) => ({
      ...c,
      label: i < 26 ? String.fromCharCode(65 + i) : `C${i}`,
    }));
  }, []);

  const applyResult = useCallback(
    (data: GenerateResponse) => {
      setProgram(data.program_summary);
      setCandidates(relabel(data.candidates));
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
      setSelectedRoomId(null);
      // 锁跨 regenerate 保留；整案 Generate / Benchmark 在 run 里清
      setError(null);
    },
    [relabel],
  );

  const run = useCallback(
    async (mode: "form" | "benchmark" | "program" | "variant") => {
      setLoading(true);
      setError(null);
      try {
        if (mode === "variant") {
          if (!program) throw new Error("尚无 Program，请先 Generate");
          const prevSelected = selectedId;
          const maxSeed = candidates.reduce((m, c) => Math.max(m, c.seed), -1);
          const data = await generateFromProgram(form, program, {
            locks,
            base_seed: maxSeed + 1,
            candidate_count: 8,
            return_top_k: 3,
          });
          setProgram(data.program_summary);
          const fresh = data.candidates.filter(
            (c) => !candidates.some((e) => e.id === c.id),
          );
          const merged = relabel([...candidates, ...fresh]).slice(-16);
          setCandidates(merged);
          setStats({
            generated: data.generated,
            valid: data.valid,
            rejected: data.rejected,
          });
          setRejectedCandidates(data.rejected_candidates ?? []);
          setViolationSummary(data.violation_summary ?? {});
          const pick = fresh[0] ?? merged[merged.length - 1];
          if (pick) {
            setSelectedId(pick.id);
            if (prevSelected && prevSelected !== pick.id) {
              setCompareId(prevSelected);
            }
          }
          setHighlightRoomIds([]);
          setSelectedRoomId(null);
          setError(null);
          return;
        }

        let data: GenerateResponse;
        if (mode === "benchmark") {
          setLocks({ rooms: [], stair: null });
          data = await generateBenchmark();
        } else if (mode === "program") {
          if (!program) throw new Error("尚无 Program，请先 Generate");
          data = await generateFromProgram(form, program, { locks });
        } else {
          setLocks({ rooms: [], stair: null });
          data = await generateFromForm(form);
        }
        applyResult(data);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    },
    [applyResult, form, program, locks, candidates, selectedId, relabel],
  );

  const onUpdateRoomTargetArea = useCallback((roomId: string, targetArea: number) => {
    setProgram((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        rooms: prev.rooms.map((r) =>
          r.id === roomId ? { ...r, target_area: targetArea } : r,
        ),
      };
    });
    // 改面积后解除该房间锁（避免面积与钉死几何冲突）
    setLocks((prev) => ({
      ...prev,
      rooms: prev.rooms.filter((r) => r.room_id !== roomId),
    }));
  }, []);

  const onToggleRoomLock = useCallback(
    (roomId: string) => {
      if (!selected) return;
      const isStair = roomId.startsWith("stair-");
      if (isStair) {
        setLocks((prev) => {
          if (prev.stair) {
            return { ...prev, stair: null };
          }
          const pl = selected.placements?.find((p) => p.room_id === roomId);
          if (!pl) return prev;
          const stair: LockedStairCore = {
            x: pl.x,
            y: pl.y,
            width: pl.width,
            depth: pl.depth,
          };
          return { ...prev, stair };
        });
        return;
      }
      setLocks((prev) => {
        const exists = prev.rooms.some((r) => r.room_id === roomId);
        if (exists) {
          return {
            ...prev,
            rooms: prev.rooms.filter((r) => r.room_id !== roomId),
          };
        }
        const pl = selected.placements?.find((p) => p.room_id === roomId);
        if (!pl) return prev;
        const next: LockedRoomRect = {
          room_id: pl.room_id,
          floor_id: pl.floor_id,
          x: pl.x,
          y: pl.y,
          width: pl.width,
          depth: pl.depth,
        };
        return { ...prev, rooms: [...prev.rooms, next] };
      });
    },
    [selected],
  );

  const onClearLocks = useCallback(() => {
    setLocks({ rooms: [], stair: null });
  }, []);

  const onSelectRoom = useCallback((roomId: string | null) => {
    setSelectedRoomId(roomId);
    setHighlightRoomIds(roomId ? [roomId] : []);
  }, []);

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
    setSelectedRoomId(null);
  }, []);

  const lockCount =
    locks.rooms.length + (locks.stair ? 1 : 0);
  const emptyHint =
    engineStatus === "ERROR"
      ? engineHint || "本地引擎异常，请重试"
      : engineStatus === "STARTING"
        ? "正在连接本地引擎…"
        : engineStatus === "STOPPED"
          ? "引擎已停止"
          : "Generate → 锁定 → Regenerate unlocked / Create Variant → Alt+点比较";

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
          selectedRoomId={selectedRoomId}
          lockedRoomIds={[
            ...locks.rooms.map((r) => r.room_id),
            ...(locks.stair
              ? (selected?.placements
                  ?.filter((p) => p.room_id.startsWith("stair-"))
                  .map((p) => p.room_id) ?? [])
              : []),
          ]}
          onSelectRoom={onSelectRoom}
        />
        <Inspector
          candidate={selected}
          compareWith={compareWith}
          program={program}
          selectedRoomId={selectedRoomId}
          highlightRoomIds={highlightRoomIds}
          locks={locks}
          lockCount={lockCount}
          onHighlightRooms={setHighlightRoomIds}
          onSelectRoom={onSelectRoom}
          onClearCompare={() => setCompareId(null)}
          onUpdateRoomTargetArea={onUpdateRoomTargetArea}
          onToggleRoomLock={onToggleRoomLock}
          onClearLocks={onClearLocks}
          onRegenerate={() => void run("program")}
          onCreateVariant={() => void run("variant")}
          regenerating={loading}
          canRegenerate={!!program && engineStatus === "READY"}
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
