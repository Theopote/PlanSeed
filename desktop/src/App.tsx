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
  type LockedZoneRect,
  type ProgramSummary,
  type RejectedCandidatePayload,
  type RequirementForm,
} from "./api/client";
import { CandidateStrip } from "./components/CandidateStrip";
import {
  mutationLiveMessage,
  mutationRejectMessage,
  mutationWarningMessage,
  previewAdjustWall,
  previewMove,
  previewResize,
} from "./lib/geometryMutation";
import {
  FloorplanView,
  type LivePreviewResult,
  type MutationDragKind,
  type ProposeMoveResult,
  type RoomMovePose,
  type WallAdjustPose,
} from "./components/FloorplanView";
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

/** 发 Generate 前冻结 locks，避免请求过程中 UI 改锁改变语义 */
function cloneLayoutLocks(locks: LayoutLocks): LayoutLocks {
  return {
    rooms: locks.rooms.map((r) => ({ ...r })),
    stair: locks.stair ? { ...locks.stair } : null,
    zones: locks.zones.map((z) => ({
      ...z,
      room_ids: z.room_ids ? [...z.room_ids] : [],
    })),
  };
}

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
  const [locks, setLocks] = useState<LayoutLocks>({
    rooms: [],
    stair: null,
    zones: [],
  });
  const [mutationHint, setMutationHint] = useState<string | null>(null);
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
            locks: cloneLayoutLocks(locks),
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
          setLocks({ rooms: [], stair: null, zones: [] });
          data = await generateBenchmark();
        } else if (mode === "program") {
          if (!program) throw new Error("尚无 Program，请先 Generate");
          data = await generateFromProgram(form, program, {
            locks: cloneLayoutLocks(locks),
          });
        } else {
          setLocks({ rooms: [], stair: null, zones: [] });
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
    setLocks({ rooms: [], stair: null, zones: [] });
  }, []);

  /** Geometry Mutation Authority：MOVE/RESIZE → Commit 或 Snap Back */
  const runPreview = useCallback(
    (
      roomId: string,
      pose: RoomMovePose,
      kind: MutationDragKind,
    ) => {
      if (!selected?.placements || !program) return null;
      const roomMeta = program.rooms.find((r) => r.id === roomId);
      const ctx = {
        placements: selected.placements,
        locks,
        floorWidth: program.site_width,
        floorDepth: program.site_depth,
        snapModule: 0.3 as const,
        roomHints: roomMeta
          ? { target_area: roomMeta.target_area }
          : undefined,
      };
      const proposed = {
        x: pose.x,
        y: pose.y,
        width: pose.width,
        depth: pose.depth,
      };
      return kind === "resize"
        ? previewResize(roomId, proposed, pose.floor_id, ctx)
        : previewMove(roomId, proposed, pose.floor_id, ctx);
    },
    [selected, program, locks],
  );

  const onLivePreview = useCallback(
    (
      roomId: string,
      pose: RoomMovePose,
      kind: MutationDragKind,
    ): LivePreviewResult => {
      const preview = runPreview(roomId, pose, kind);
      if (!preview) {
        return { ok: false, message: "无候选可编辑", conflictRoomIds: [] };
      }
      return {
        ok: preview.ok,
        message: mutationLiveMessage(preview),
        snapped: preview.snapped,
        conflictRoomIds: preview.conflictRoomIds,
      };
    },
    [runPreview],
  );

  const onLiveWallPreview = useCallback(
    (pose: WallAdjustPose): LivePreviewResult => {
      if (!selected?.placements || !program) {
        return { ok: false, message: "无候选可编辑", conflictRoomIds: [] };
      }
      const preview = previewAdjustWall(
        pose.room_id,
        pose.partner_room_id,
        pose.floor_id,
        pose.wall_axis,
        pose.wall_coord,
        {
          placements: selected.placements,
          locks,
          floorWidth: program.site_width,
          floorDepth: program.site_depth,
          snapModule: 0.3,
        },
      );
      return {
        ok: preview.ok,
        message: mutationLiveMessage(preview),
        snapped: preview.snapped,
        snappedPartner: preview.snappedPartner,
        partnerRoomId: pose.partner_room_id,
        conflictRoomIds: preview.conflictRoomIds,
      };
    },
    [selected, program, locks],
  );

  const onProposeWall = useCallback(
    (pose: WallAdjustPose): ProposeMoveResult => {
      if (!selected?.placements || !program) {
        return { ok: false, message: "无候选可编辑", snapped: null };
      }
      const preview = previewAdjustWall(
        pose.room_id,
        pose.partner_room_id,
        pose.floor_id,
        pose.wall_axis,
        pose.wall_coord,
        {
          placements: selected.placements,
          locks,
          floorWidth: program.site_width,
          floorDepth: program.site_depth,
          snapModule: 0.3,
        },
      );
      if (!preview.ok || !preview.snapped || !preview.snappedPartner) {
        const msg = mutationRejectMessage(preview);
        setMutationHint(msg);
        return {
          ok: false,
          message: msg,
          snapped: preview.snapped,
          snappedPartner: preview.snappedPartner,
          partnerRoomId: pose.partner_room_id,
          conflictRoomIds: preview.conflictRoomIds,
        };
      }
      const sA = preview.snapped;
      const sB = preview.snappedPartner;
      const idA = pose.room_id;
      const idB = pose.partner_room_id;
      setCandidates((prev) =>
        prev.map((c) => {
          if (c.id !== selectedId || !c.placements) return c;
          return {
            ...c,
            placements: c.placements.map((p) => {
              if (p.room_id === idA) {
                return {
                  ...p,
                  x: sA.x,
                  y: sA.y,
                  width: sA.width,
                  depth: sA.depth,
                  area: Math.round(sA.width * sA.depth * 100) / 100,
                };
              }
              if (p.room_id === idB) {
                return {
                  ...p,
                  x: sB.x,
                  y: sB.y,
                  width: sB.width,
                  depth: sB.depth,
                  area: Math.round(sB.width * sB.depth * 100) / 100,
                };
              }
              return p;
            }),
          };
        }),
      );
      setLocks((prev) => {
        const rest = prev.rooms.filter(
          (r) => r.room_id !== idA && r.room_id !== idB,
        );
        const locksNext: LockedRoomRect[] = [
          ...rest,
          {
            room_id: idA,
            floor_id: pose.floor_id,
            x: sA.x,
            y: sA.y,
            width: sA.width,
            depth: sA.depth,
          },
          {
            room_id: idB,
            floor_id: pose.floor_id,
            x: sB.x,
            y: sB.y,
            width: sB.width,
            depth: sB.depth,
          },
        ];
        return { ...prev, rooms: locksNext };
      });
      const warn = mutationWarningMessage(preview);
      setMutationHint(warn);
      return {
        ok: true,
        snapped: sA,
        snappedPartner: sB,
        partnerRoomId: idB,
        warning: warn,
        conflictRoomIds: preview.conflictRoomIds,
      };
    },
    [selected, selectedId, program, locks],
  );

  const onProposeMove = useCallback(
    (
      roomId: string,
      pose: RoomMovePose,
      kind: MutationDragKind = "move",
    ): ProposeMoveResult => {
      if (!selected?.placements || !program) {
        return { ok: false, message: "无候选可编辑", snapped: null };
      }
      const preview = runPreview(roomId, pose, kind);
      if (!preview || !preview.ok || !preview.snapped) {
        const msg = preview
          ? mutationRejectMessage(preview)
          : "无候选可编辑";
        setMutationHint(msg);
        return {
          ok: false,
          message: msg,
          snapped: preview?.snapped ?? null,
          conflictRoomIds: preview?.conflictRoomIds,
        };
      }
      const s = preview.snapped;
      const isStair = roomId.startsWith("stair-");
      setCandidates((prev) =>
        prev.map((c) => {
          if (c.id !== selectedId || !c.placements) return c;
          return {
            ...c,
            placements: c.placements.map((p) => {
              if (isStair) {
                if (!p.room_id.startsWith("stair-")) return p;
                return {
                  ...p,
                  x: s.x,
                  y: s.y,
                  width: kind === "resize" ? s.width : p.width,
                  depth: kind === "resize" ? s.depth : p.depth,
                  area: Math.round(
                    (kind === "resize" ? s.width : p.width) *
                      (kind === "resize" ? s.depth : p.depth) *
                      100,
                  ) / 100,
                };
              }
              if (p.room_id !== roomId) return p;
              return {
                ...p,
                x: s.x,
                y: s.y,
                width: s.width,
                depth: s.depth,
                area: Math.round(s.width * s.depth * 100) / 100,
              };
            }),
          };
        }),
      );
      if (isStair) {
        setLocks((prev) => ({
          ...prev,
          stair: {
            x: s.x,
            y: s.y,
            width: kind === "resize" ? s.width : (prev.stair?.width ?? s.width),
            depth: kind === "resize" ? s.depth : (prev.stair?.depth ?? s.depth),
            core_placement: prev.stair?.core_placement ?? null,
          },
        }));
      } else {
        setLocks((prev) => {
          const rest = prev.rooms.filter((r) => r.room_id !== roomId);
          const next: LockedRoomRect = {
            room_id: roomId,
            floor_id: pose.floor_id,
            x: s.x,
            y: s.y,
            width: s.width,
            depth: s.depth,
          };
          return { ...prev, rooms: [...rest, next] };
        });
      }
      const warn = mutationWarningMessage(preview);
      setMutationHint(warn);
      return {
        ok: true,
        snapped: s,
        warning: warn,
        conflictRoomIds: preview.conflictRoomIds,
      };
    },
    [selected, selectedId, program, runPreview],
  );

  const onToggleZoneLock = useCallback(
    (zone: string, floorId: string) => {
      if (!selected?.zones) return;
      setLocks((prev) => {
        const exists = prev.zones.some(
          (z) => z.zone === zone && z.floor_id === floorId,
        );
        if (exists) {
          return {
            ...prev,
            zones: prev.zones.filter(
              (z) => !(z.zone === zone && z.floor_id === floorId),
            ),
          };
        }
        const matches = selected.zones.filter(
          (z) => z.zone === zone && z.floor_id === floorId,
        );
        if (!matches.length) return prev;
        const next: LockedZoneRect[] = matches.map((z) => ({
          zone: z.kind ?? z.zone,
          floor_id: z.floor_id,
          x: z.x,
          y: z.y,
          width: z.width,
          depth: z.depth,
          room_ids: [...z.room_ids],
          zone_id: z.id ?? null,
        }));
        return { ...prev, zones: [...prev.zones, ...next] };
      });
    },
    [selected],
  );

  const onSelectZone = useCallback(
    (zone: string, floorId: string) => {
      const matches =
        selected?.zones?.filter(
          (z) => (z.kind ?? z.zone) === zone && z.floor_id === floorId,
        ) ?? [];
      if (!matches.length) return;
      const rooms = [...new Set(matches.flatMap((z) => z.room_ids))];
      setHighlightRoomIds(rooms);
      setSelectedRoomId(null);
    },
    [selected],
  );

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
    locks.rooms.length +
    (locks.stair ? 1 : 0) +
    locks.zones.length;
  const lockedZoneRoomIds = locks.zones.flatMap((z) => z.room_ids ?? []);
  const emptyHint =
    engineStatus === "ERROR"
      ? engineHint || "本地引擎异常，请重试"
      : engineStatus === "STARTING"
        ? "正在连接本地引擎…"
        : engineStatus === "STOPPED"
          ? "引擎已停止"
          : "Generate → 拖拽/锁定 → Regenerate unlocked / Create Variant → Alt+点比较";

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
            ...lockedZoneRoomIds,
            ...(locks.stair
              ? (selected?.placements
                  ?.filter((p) => p.room_id.startsWith("stair-"))
                  .map((p) => p.room_id) ?? [])
              : []),
          ]}
          placements={selected?.placements}
          floorIds={program?.floors.map((f) => f.id)}
          floorWidth={program?.site_width}
          floorDepth={program?.site_depth}
          snapModule={0.3}
          onSelectRoom={onSelectRoom}
          onProposeMove={program ? onProposeMove : undefined}
          onProposeWall={program ? onProposeWall : undefined}
          onLivePreview={program ? onLivePreview : undefined}
          onLiveWallPreview={program ? onLiveWallPreview : undefined}
          mutationHint={mutationHint}
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
          onSelectZone={onSelectZone}
          onClearCompare={() => setCompareId(null)}
          onUpdateRoomTargetArea={onUpdateRoomTargetArea}
          onToggleRoomLock={onToggleRoomLock}
          onToggleZoneLock={onToggleZoneLock}
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
