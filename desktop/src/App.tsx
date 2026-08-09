import { useCallback, useEffect, useRef, useState } from "react";
import {
  checkHealth,
  fetchLlmStatus,
  generateBenchmark,
  generateFromForm,
  generateFromProgram,
  listProjects,
  loadProject,
  buildReport,
  downloadBlob,
  exportPng,
  exportSvg,
  parseRequirementsNl,
  patchFormFromRequirementSpec,
  previewMutation,
  revalidateMutation,
  resolveEngineBase,
  retryEngine,
  saveProject,
  setApiBase,
  syncRequirementSpacesFromProgram,
  fallbackRequirementFromForm,
  type CandidatePayload,
  type EngineLifecycle,
  type GenerateResponse,
  type LayoutLocks,
  type LockedRoomRect,
  type LockedStairCore,
  type LockedZoneRect,
  type LlmHealthState,
  type LlmStatusPayload,
  type MutationPreviewApiResult,
  type MutationRecordPayload,
  type ProgramSummary,
  type ProjectSummary,
  type RejectedCandidatePayload,
  type RequirementForm,
  type RequirementSpecPayload,
  type SvgExportScope,
  type PngExportSize,
} from "./api/client";
import { CandidateStrip } from "./components/CandidateStrip";
import { ReportPreview } from "./components/ReportPreview";
import { locksFingerprint } from "./lib/lineage";
import {
  mutationLiveMessage,
  mutationRejectMessage,
  mutationWarningMessage,
  visualSnapRect,
  type MutationPreviewResult,
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
import { coerceAssumptionValue } from "./lib/requirementGaps";
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

function apiPreviewToLocal(p: MutationPreviewApiResult): MutationPreviewResult {
  return {
    ok: p.ok,
    reasons: p.reasons,
    warnings: p.warnings,
    snapped: p.snapped,
    snappedPartner: p.snapped_partner,
    conflictRoomIds: p.conflict_room_ids,
  };
}

function newMutationId(): string {
  return `mut-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

function markCandidateDirty(
  c: CandidatePayload,
  record: MutationRecordPayload,
  placements: NonNullable<CandidatePayload["placements"]>,
): CandidatePayload {
  return {
    ...c,
    placements,
    revision_status: "dirty",
    revision_parent_id: c.revision_parent_id ?? c.id,
    mutations: [...(c.mutations ?? []), record],
    validation: null,
  };
}

function App() {
  const [form, setForm] = useState<RequirementForm>(DEFAULT_FORM);
  const [engineStatus, setEngineStatus] = useState<EngineLifecycle>("STARTING");
  const [engineHint, setEngineHint] = useState<string | null>(null);
  const [llmStatus, setLlmStatus] = useState<LlmStatusPayload | null>(null);
  const [llmSessionState, setLlmSessionState] = useState<LlmHealthState | null>(
    null,
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [program, setProgram] = useState<ProgramSummary | null>(null);
  const [requirementSpec, setRequirementSpec] =
    useState<RequirementSpecPayload | null>(null);
  const [nlText, setNlText] = useState("");
  const [nlBusy, setNlBusy] = useState(false);
  const [nlHint, setNlHint] = useState<string | null>(null);
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
  const [projectId, setProjectId] = useState<string | null>(null);
  const [projectName, setProjectName] = useState("未命名项目");
  const [projectBusy, setProjectBusy] = useState(false);
  const [versionHint, setVersionHint] = useState<string | null>(null);
  const [projectPicker, setProjectPicker] = useState<ProjectSummary[] | null>(
    null,
  );
  const [reportHtml, setReportHtml] = useState<string | null>(null);
  const [reportBusy, setReportBusy] = useState(false);
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
  const [solverIdentity, setSolverIdentity] = useState<{
    solver_version: string;
    generator_version: string;
    evaluation_version: string;
  } | null>(null);
  const [revalidating, setRevalidating] = useState(false);
  const livePreviewTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

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

  useEffect(() => {
    if (engineStatus !== "READY") {
      setLlmStatus(null);
      setLlmSessionState(null);
      return;
    }
    let cancelled = false;
    async function refresh() {
      const status = await fetchLlmStatus();
      if (cancelled) return;
      setLlmStatus(status);
      setLlmSessionState((prev) => {
        if (prev === "ParseRunning" || prev === "ParseFailed") return prev;
        return null;
      });
    }
    void refresh();
    const id = window.setInterval(() => {
      void refresh();
    }, 8000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [engineStatus]);

  const displayLlmState: LlmHealthState | null =
    llmSessionState ?? llmStatus?.state ?? null;

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

  const stampRootLineage = useCallback(
    (list: CandidatePayload[], lockSnap: string): CandidatePayload[] =>
      list.map((c) => ({
        ...c,
        variant_parent_id: c.variant_parent_id ?? null,
        variant_generation: c.variant_generation ?? 0,
        lock_snapshot_id: c.lock_snapshot_id ?? lockSnap,
        revision_status: c.revision_status ?? "generated",
        mutations: c.mutations ?? [],
      })),
    [],
  );

  const applyResult = useCallback(
    (data: GenerateResponse) => {
      setProgram(data.program_summary);
      if (data.requirement_spec) {
        const spec: RequirementSpecPayload = { ...data.requirement_spec };
        // 保证假设/未知进入会话事实源（与 Program 对齐）
        if (spec.assumptions === undefined) {
          spec.assumptions = data.program_summary.assumptions ?? [];
        }
        if (spec.unknowns === undefined) {
          spec.unknowns = data.program_summary.unknowns ?? [];
        }
        setRequirementSpec(spec);
      }
      if (data.solver_identity) {
        setSolverIdentity(data.solver_identity);
      }
      const fp = locksFingerprint(locks);
      setCandidates(stampRootLineage(relabel(data.candidates), fp));
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
      setMutationHint(null);
      setError(null);
    },
    [relabel, stampRootLineage, locks],
  );

  /** 会话求解用的 RequirementSpec：canonical + Program 面积补丁。 */
  const resolveCanonicalSpec = useCallback((): RequirementSpecPayload | null => {
    if (!program) return null;
    if (requirementSpec) {
      return syncRequirementSpacesFromProgram(requirementSpec, program);
    }
    return fallbackRequirementFromForm(form, program);
  }, [program, requirementSpec, form]);

  const run = useCallback(
    async (mode: "form" | "benchmark" | "program" | "variant") => {
      setLoading(true);
      setError(null);
      try {
        if (mode === "variant") {
          if (!program) throw new Error("尚无 Program，请先 Generate");
          const spec = resolveCanonicalSpec();
          if (!spec) throw new Error("缺少 RequirementSpec");
          const prevSelected = selectedId;
          const parent = candidates.find((c) => c.id === prevSelected) ?? null;
          const parentGen = parent?.variant_generation ?? 0;
          const fp = locksFingerprint(locks);
          const maxSeed = candidates.reduce((m, c) => Math.max(m, c.seed), -1);
          const data = await generateFromProgram(spec, {
            locks: cloneLayoutLocks(locks),
            base_seed: maxSeed + 1,
            candidate_count: 8,
            return_top_k: 3,
          });
          if (data.requirement_spec) setRequirementSpec(data.requirement_spec);
          setProgram(data.program_summary);
          if (data.solver_identity) setSolverIdentity(data.solver_identity);
          const fresh = data.candidates
            .filter((c) => !candidates.some((e) => e.id === c.id))
            .map((c) => ({
              ...c,
              variant_parent_id: prevSelected,
              variant_generation: parentGen + 1,
              lock_snapshot_id: fp,
              revision_status: c.revision_status ?? "generated",
              mutations: c.mutations ?? [],
            }));
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

        if (mode === "benchmark") {
          setLocks({ rooms: [], stair: null, zones: [] });
          applyResult(await generateBenchmark());
          return;
        }
        if (mode === "program") {
          if (!program) throw new Error("尚无 Program，请先 Generate");
          const spec = resolveCanonicalSpec();
          if (!spec) throw new Error("缺少 RequirementSpec");
          applyResult(
            await generateFromProgram(spec, {
              locks: cloneLayoutLocks(locks),
            }),
          );
          return;
        }
        setLocks({ rooms: [], stair: null, zones: [] });
        applyResult(await generateFromForm(form));
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    },
    [
      applyResult,
      form,
      program,
      locks,
      candidates,
      selectedId,
      relabel,
      resolveCanonicalSpec,
    ],
  );

  const onUpdateRoomTargetArea = useCallback(
    (roomId: string, targetArea: number) => {
      setProgram((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          rooms: prev.rooms.map((r) =>
            r.id === roomId ? { ...r, target_area: targetArea } : r,
          ),
        };
      });
      setRequirementSpec((prev) => {
        if (!prev?.spaces) return prev;
        return {
          ...prev,
          spaces: prev.spaces.map((s) =>
            s.id === roomId ? { ...s, target_area: targetArea } : s,
          ),
        };
      });
      setLocks((prev) => ({
        ...prev,
        rooms: prev.rooms.filter((r) => r.room_id !== roomId),
      }));
    },
    [],
  );

  /** Phase 6.4 — 假设/未知写入 requirementSpec，并镜像 program。 */
  const ensureEditableSpec = useCallback((): RequirementSpecPayload => {
    if (requirementSpec) return requirementSpec;
    return fallbackRequirementFromForm(form, program);
  }, [requirementSpec, form, program]);

  const onUpdateAssumption = useCallback(
    (key: string, patch: { value: string; reason: string }) => {
      const base = ensureEditableSpec();
      const prevList = base.assumptions ?? [];
      const existing = prevList.find((a) => a.key === key);
      const nextValue = coerceAssumptionValue(
        patch.value,
        existing?.value ?? patch.value,
      );
      const nextAssumptions = prevList.map((a) =>
        a.key === key
          ? {
              ...a,
              key,
              value: nextValue,
              reason: patch.reason,
            }
          : a,
      );
      setRequirementSpec({ ...base, assumptions: nextAssumptions });
      setProgram((prev) =>
        prev
          ? {
              ...prev,
              assumptions: nextAssumptions.map((a) => ({ ...a })),
            }
          : prev,
      );
    },
    [ensureEditableSpec],
  );

  const onRemoveAssumption = useCallback(
    (key: string) => {
      const base = ensureEditableSpec();
      const nextAssumptions = (base.assumptions ?? []).filter((a) => a.key !== key);
      setRequirementSpec({ ...base, assumptions: nextAssumptions });
      setProgram((prev) =>
        prev
          ? {
              ...prev,
              assumptions: prev.assumptions.filter((a) => a.key !== key),
            }
          : prev,
      );
    },
    [ensureEditableSpec],
  );

  const onDismissUnknown = useCallback(
    (key: string) => {
      const base = ensureEditableSpec();
      const nextUnknowns = (base.unknowns ?? []).filter((u) => u.key !== key);
      setRequirementSpec({ ...base, unknowns: nextUnknowns });
      setProgram((prev) =>
        prev
          ? {
              ...prev,
              unknowns: prev.unknowns.filter((u) => u.key !== key),
            }
          : prev,
      );
    },
    [ensureEditableSpec],
  );

  const applyParsedSpec = useCallback((spec: RequirementSpecPayload) => {
    setRequirementSpec(spec);
    setForm((prev) => patchFormFromRequirementSpec(prev, spec));
    if (spec.raw_text) setNlText(spec.raw_text);
  }, []);

  const onParseNl = useCallback(async () => {
    setNlBusy(true);
    setLlmSessionState("ParseRunning");
    setNlHint(null);
    setError(null);
    try {
      const data = await parseRequirementsNl(nlText);
      applyParsedSpec(data.requirement_spec);
      const notes =
        data.attempts > 1
          ? `已解析（含 ${data.attempts - 1} 次修复）· ${data.provider}`
          : `已解析 · ${data.provider}`;
      setNlHint(notes);
      setLlmSessionState(null);
      void fetchLlmStatus().then(setLlmStatus);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setLlmSessionState("ParseFailed");
    } finally {
      setNlBusy(false);
    }
  }, [nlText, applyParsedSpec]);

  const onParseAndGenerate = useCallback(async () => {
    setNlBusy(true);
    setLoading(true);
    setLlmSessionState("ParseRunning");
    setNlHint(null);
    setError(null);
    try {
      const parsed = await parseRequirementsNl(nlText);
      applyParsedSpec(parsed.requirement_spec);
      setLocks({ rooms: [], stair: null, zones: [] });
      const data = await generateFromProgram(parsed.requirement_spec, {
        candidate_count: 16,
        return_top_k: 5,
      });
      applyResult(data);
      const notes =
        parsed.attempts > 1
          ? `已解析并生成（修复 ${parsed.attempts - 1} 次）`
          : "已解析并生成";
      setNlHint(notes);
      setLlmSessionState(null);
      void fetchLlmStatus().then(setLlmStatus);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setLlmSessionState("ParseFailed");
    } finally {
      setNlBusy(false);
      setLoading(false);
    }
  }, [nlText, applyParsedSpec, applyResult]);

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

  /** Phase 5.1：权威预览走 Python；TS 仅 visual。 */
  const callAuthorityPreview = useCallback(
    async (
      mutation: Parameters<typeof previewMutation>[0]["mutation"],
    ): Promise<MutationPreviewResult | null> => {
      if (!selected?.placements || !program) return null;
      const spec = resolveCanonicalSpec();
      if (!spec) {
        setMutationHint("缺少 RequirementSpec");
        return null;
      }
      try {
        const raw = await previewMutation({
          requirementSpec: spec,
          placements: selected.placements,
          locks,
          mutation,
          snapModule: 0.3,
        });
        return apiPreviewToLocal(raw);
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        setMutationHint(msg);
        return {
          ok: false,
          reasons: [{ code: "mutation.api_error", message: msg }],
          warnings: [],
          snapped: null,
          snappedPartner: null,
          conflictRoomIds: [],
        };
      }
    },
    [selected, program, locks, resolveCanonicalSpec],
  );

  const scheduleAuthorityLiveHint = useCallback(
    (mutation: Parameters<typeof previewMutation>[0]["mutation"]) => {
      if (livePreviewTimer.current) clearTimeout(livePreviewTimer.current);
      livePreviewTimer.current = setTimeout(() => {
        void (async () => {
          const preview = await callAuthorityPreview(mutation);
          if (!preview) return;
          setMutationHint(mutationLiveMessage(preview));
        })();
      }, 80);
    },
    [callAuthorityPreview],
  );

  const onLivePreview = useCallback(
    (
      roomId: string,
      pose: RoomMovePose,
      kind: MutationDragKind,
    ): LivePreviewResult => {
      if (!program) {
        return { ok: false, message: "无候选可编辑", conflictRoomIds: [] };
      }
      const snapped = visualSnapRect(
        { x: pose.x, y: pose.y, width: pose.width, depth: pose.depth },
        program.site_width,
        program.site_depth,
        0.3,
        kind === "resize" ? "resize" : "move",
      );
      scheduleAuthorityLiveHint({
        kind: kind === "resize" ? "resize" : "move",
        room_id: roomId,
        floor_id: pose.floor_id,
        proposed: snapped,
        source: "pointer",
      });
      return {
        ok: true,
        message: null,
        snapped,
        conflictRoomIds: [],
      };
    },
    [program, scheduleAuthorityLiveHint],
  );

  const onLiveWallPreview = useCallback(
    (pose: WallAdjustPose): LivePreviewResult => {
      scheduleAuthorityLiveHint({
        kind: "adjust_wall",
        room_id: pose.room_id,
        partner_room_id: pose.partner_room_id,
        floor_id: pose.floor_id,
        wall_axis: pose.wall_axis,
        wall_coord: pose.wall_coord,
        source: "pointer",
      });
      return {
        ok: true,
        message: null,
        snapped: null,
        partnerRoomId: pose.partner_room_id,
        conflictRoomIds: [],
      };
    },
    [scheduleAuthorityLiveHint],
  );

  const onProposeWall = useCallback(
    async (pose: WallAdjustPose): Promise<ProposeMoveResult> => {
      if (!selected?.placements || !program) {
        return { ok: false, message: "无候选可编辑", snapped: null };
      }
      const preview = await callAuthorityPreview({
        kind: "adjust_wall",
        room_id: pose.room_id,
        partner_room_id: pose.partner_room_id,
        floor_id: pose.floor_id,
        wall_axis: pose.wall_axis,
        wall_coord: pose.wall_coord,
        source: "pointer",
      });
      if (!preview || !preview.ok || !preview.snapped || !preview.snappedPartner) {
        const msg = preview
          ? mutationRejectMessage(preview)
          : "无候选可编辑";
        setMutationHint(msg);
        return {
          ok: false,
          message: msg,
          snapped: preview?.snapped ?? null,
          snappedPartner: preview?.snappedPartner ?? null,
          partnerRoomId: pose.partner_room_id,
          conflictRoomIds: preview?.conflictRoomIds,
        };
      }
      const sA = preview.snapped;
      const sB = preview.snappedPartner;
      const idA = pose.room_id;
      const idB = pose.partner_room_id;
      const beforeA = selected.placements.find((p) => p.room_id === idA);
      const record: MutationRecordPayload = {
        id: newMutationId(),
        kind: "adjust_wall",
        room_id: idA,
        partner_room_id: idB,
        before: beforeA
          ? {
              x: beforeA.x,
              y: beforeA.y,
              width: beforeA.width,
              depth: beforeA.depth,
            }
          : null,
        after: { x: sA.x, y: sA.y, width: sA.width, depth: sA.depth },
        after_partner: { x: sB.x, y: sB.y, width: sB.width, depth: sB.depth },
        created_at: new Date().toISOString(),
      };
      setCandidates((prev) =>
        prev.map((c) => {
          if (c.id !== selectedId || !c.placements) return c;
          const placements = c.placements.map((p) => {
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
          });
          return markCandidateDirty(c, record, placements);
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
      setMutationHint(
        warn
          ? `已编辑 · ${warn}`
          : "已编辑 · Evaluation outdated · Revalidate to update",
      );
      return {
        ok: true,
        snapped: sA,
        snappedPartner: sB,
        partnerRoomId: idB,
        warning: warn,
        conflictRoomIds: preview.conflictRoomIds,
      };
    },
    [selected, selectedId, program, callAuthorityPreview],
  );

  const onProposeMove = useCallback(
    async (
      roomId: string,
      pose: RoomMovePose,
      kind: MutationDragKind = "move",
    ): Promise<ProposeMoveResult> => {
      if (!selected?.placements || !program) {
        return { ok: false, message: "无候选可编辑", snapped: null };
      }
      const proposed = {
        x: pose.x,
        y: pose.y,
        width: pose.width,
        depth: pose.depth,
      };
      const preview = await callAuthorityPreview({
        kind: kind === "resize" ? "resize" : "move",
        room_id: roomId,
        floor_id: pose.floor_id,
        proposed,
        source: "pointer",
      });
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
      const before = selected.placements.find((p) =>
        isStair ? p.room_id.startsWith("stair-") : p.room_id === roomId,
      );
      const record: MutationRecordPayload = {
        id: newMutationId(),
        kind: kind === "resize" ? "resize" : "move",
        room_id: roomId,
        before: before
          ? {
              x: before.x,
              y: before.y,
              width: before.width,
              depth: before.depth,
            }
          : null,
        after: { x: s.x, y: s.y, width: s.width, depth: s.depth },
        created_at: new Date().toISOString(),
      };
      setCandidates((prev) =>
        prev.map((c) => {
          if (c.id !== selectedId || !c.placements) return c;
          const placements = c.placements.map((p) => {
            if (isStair) {
              if (!p.room_id.startsWith("stair-")) return p;
              return {
                ...p,
                x: s.x,
                y: s.y,
                width: kind === "resize" ? s.width : p.width,
                depth: kind === "resize" ? s.depth : p.depth,
                area:
                  Math.round(
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
          });
          return markCandidateDirty(c, record, placements);
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
      setMutationHint(
        warn
          ? `已编辑 · ${warn}`
          : "已编辑 · Evaluation outdated · Revalidate to update",
      );
      return {
        ok: true,
        snapped: s,
        warning: warn,
        conflictRoomIds: preview.conflictRoomIds,
      };
    },
    [selected, selectedId, program, callAuthorityPreview],
  );

  const onToggleZoneLock = useCallback(
    (zone: string, floorId: string) => {
      const zones = selected?.zones;
      if (!zones) return;
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
        const matches = zones.filter(
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

  const onSaveProject = useCallback(async () => {
    if (!program) {
      setError("请先 Generate 再保存");
      return;
    }
    setProjectBusy(true);
    setError(null);
    try {
      const fromCand = candidates.find((c) => c.provenance)?.provenance;
      const schema_versions = {
        solver_version:
          solverIdentity?.solver_version ??
          fromCand?.solver_version ??
          null,
        generator_version:
          solverIdentity?.generator_version ??
          fromCand?.generator_version ??
          null,
        evaluation_version:
          solverIdentity?.evaluation_version ??
          fromCand?.evaluation_version ??
          null,
      };
      const saved = await saveProject({
        name: projectName.trim() || "未命名项目",
        id: projectId,
        payload: {
          form,
          program,
          requirement_spec: resolveCanonicalSpec(),
          locks: cloneLayoutLocks(locks),
          candidates,
          selected_id: selectedId,
          compare_id: compareId,
          schema_versions,
        },
      });
      setProjectId(saved.id);
      setProjectName(saved.name);
      // 仅保存不得清除 mismatch；用服务端回传判断
      if (saved.evaluation_version_mismatch) {
        setVersionHint(
          `评价版本已变（快照 ${saved.payload.schema_versions?.evaluation_version ?? "?"} → 当前 ${saved.current_evaluation_version}）：分数可能不可比；布局几何仍按快照。`,
        );
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setProjectBusy(false);
    }
  }, [
    program,
    projectName,
    projectId,
    form,
    locks,
    candidates,
    selectedId,
    compareId,
    solverIdentity,
    resolveCanonicalSpec,
  ]);

  const onExportReport = useCallback(async () => {
    if (!program || candidates.length === 0) {
      setError("请先 Generate 再导出报告");
      return;
    }
    if (!selectedId) {
      setError("请先选择要导出的候选");
      return;
    }
    const selected = candidates.find((c) => c.id === selectedId);
    if (selected?.revision_status === "dirty") {
      setError(
        "方案已修改，评价结果已过期。请先重新验证后再导出正式评价报告。",
      );
      return;
    }
    setReportBusy(true);
    setError(null);
    try {
      // 正式报告只引用已保存快照（禁止 client 任意 SVG payload）
      const fromCand = candidates.find((c) => c.provenance)?.provenance;
      const schema_versions = {
        solver_version:
          solverIdentity?.solver_version ?? fromCand?.solver_version ?? null,
        generator_version:
          solverIdentity?.generator_version ?? fromCand?.generator_version ?? null,
        evaluation_version:
          solverIdentity?.evaluation_version ??
          fromCand?.evaluation_version ??
          null,
      };
      const saved = await saveProject({
        name: projectName.trim() || "未命名项目",
        id: projectId,
        payload: {
          form,
          program,
          requirement_spec: resolveCanonicalSpec(),
          locks: cloneLayoutLocks(locks),
          candidates,
          selected_id: selectedId,
          compare_id: compareId,
          schema_versions,
        },
      });
      setProjectId(saved.id);
      setProjectName(saved.name);
      const stored = saved.payload.candidates?.find((c) => c.id === selectedId);
      const revisionId =
        stored?.revision_id ?? selected?.revision_id ?? selectedId;
      const out = await buildReport({
        mode: "final",
        projectId: saved.id,
        candidateId: selectedId,
        revisionId,
        projectName: saved.name,
      });
      if (!out.html) {
        setError("报告未返回 HTML");
        return;
      }
      setReportHtml(out.html);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setReportBusy(false);
    }
  }, [
    program,
    candidates,
    projectName,
    projectId,
    selectedId,
    form,
    locks,
    compareId,
    solverIdentity,
    resolveCanonicalSpec,
  ]);

  const onExportSvg = useCallback(
    async (scope: SvgExportScope) => {
      if (!program || candidates.length === 0) {
        setError("请先 Generate 再导出 SVG");
        return;
      }
      if (!selectedId) {
        setError("请先选择要导出的候选");
        return;
      }
      const selected = candidates.find((c) => c.id === selectedId);
      if (selected?.revision_status === "dirty") {
        setError(
          "方案已修改，评价结果已过期。请先重新验证后再导出 SVG。",
        );
        return;
      }
      setReportBusy(true);
      setError(null);
      try {
        const fromCand = candidates.find((c) => c.provenance)?.provenance;
        const schema_versions = {
          solver_version:
            solverIdentity?.solver_version ?? fromCand?.solver_version ?? null,
          generator_version:
            solverIdentity?.generator_version ??
            fromCand?.generator_version ??
            null,
          evaluation_version:
            solverIdentity?.evaluation_version ??
            fromCand?.evaluation_version ??
            null,
        };
        const saved = await saveProject({
          name: projectName.trim() || "未命名项目",
          id: projectId,
          payload: {
            form,
            program,
            requirement_spec: resolveCanonicalSpec(),
            locks: cloneLayoutLocks(locks),
            candidates,
            selected_id: selectedId,
            compare_id: compareId,
            schema_versions,
          },
        });
        setProjectId(saved.id);
        setProjectName(saved.name);
        const stored = saved.payload.candidates?.find((c) => c.id === selectedId);
        const revisionId =
          stored?.revision_id ?? selected?.revision_id ?? selectedId;
        let floorId: string | undefined;
        if (scope === "floor") {
          const fromRoom = selected?.placements?.find(
            (p) => p.room_id === selectedRoomId,
          )?.floor_id;
          floorId =
            fromRoom ??
            program.floors[0]?.id ??
            (selected?.floor_svgs
              ? Object.keys(selected.floor_svgs)[0]
              : undefined) ??
            "F1";
        }
        const out = await exportSvg({
          projectId: saved.id,
          candidateId: selectedId,
          revisionId,
          scope,
          floorId,
        });
        downloadBlob(out.blob, out.filename);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setReportBusy(false);
      }
    },
    [
      program,
      candidates,
      projectName,
      projectId,
      selectedId,
      selectedRoomId,
      form,
      locks,
      compareId,
      solverIdentity,
      resolveCanonicalSpec,
    ],
  );

  const onExportPng = useCallback(
    async (scope: SvgExportScope, size: PngExportSize) => {
      if (!program || candidates.length === 0) {
        setError("请先 Generate 再导出 PNG");
        return;
      }
      if (!selectedId) {
        setError("请先选择要导出的候选");
        return;
      }
      const selected = candidates.find((c) => c.id === selectedId);
      if (selected?.revision_status === "dirty") {
        setError(
          "方案已修改，评价结果已过期。请先重新验证后再导出 PNG。",
        );
        return;
      }
      setReportBusy(true);
      setError(null);
      try {
        const fromCand = candidates.find((c) => c.provenance)?.provenance;
        const schema_versions = {
          solver_version:
            solverIdentity?.solver_version ?? fromCand?.solver_version ?? null,
          generator_version:
            solverIdentity?.generator_version ??
            fromCand?.generator_version ??
            null,
          evaluation_version:
            solverIdentity?.evaluation_version ??
            fromCand?.evaluation_version ??
            null,
        };
        const saved = await saveProject({
          name: projectName.trim() || "未命名项目",
          id: projectId,
          payload: {
            form,
            program,
            requirement_spec: resolveCanonicalSpec(),
            locks: cloneLayoutLocks(locks),
            candidates,
            selected_id: selectedId,
            compare_id: compareId,
            schema_versions,
          },
        });
        setProjectId(saved.id);
        setProjectName(saved.name);
        const stored = saved.payload.candidates?.find((c) => c.id === selectedId);
        const revisionId =
          stored?.revision_id ?? selected?.revision_id ?? selectedId;
        let floorId: string | undefined;
        if (scope === "floor") {
          const fromRoom = selected?.placements?.find(
            (p) => p.room_id === selectedRoomId,
          )?.floor_id;
          floorId =
            fromRoom ??
            program.floors[0]?.id ??
            (selected?.floor_svgs
              ? Object.keys(selected.floor_svgs)[0]
              : undefined) ??
            "F1";
        }
        const out = await exportPng({
          projectId: saved.id,
          candidateId: selectedId,
          revisionId,
          scope,
          floorId,
          size,
        });
        downloadBlob(out.blob, out.filename);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setReportBusy(false);
      }
    },
    [
      program,
      candidates,
      projectName,
      projectId,
      selectedId,
      selectedRoomId,
      form,
      locks,
      compareId,
      solverIdentity,
      resolveCanonicalSpec,
    ],
  );

  const onOpenProjects = useCallback(async () => {
    setProjectBusy(true);
    setError(null);
    try {
      const list = await listProjects();
      setProjectPicker(list);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setProjectBusy(false);
    }
  }, []);

  const onLoadProject = useCallback(async (id: string) => {
    setProjectBusy(true);
    setError(null);
    try {
      const detail = await loadProject(id);
      const p = detail.payload;
      setProjectId(detail.id);
      setProjectName(detail.name);
      if (p.form && typeof p.form === "object") {
        setForm({ ...DEFAULT_FORM, ...(p.form as RequirementForm) });
      }
      setProgram((p.program as ProgramSummary) ?? null);
      if (p.requirement_spec) {
        const spec = p.requirement_spec as RequirementSpecPayload;
        setRequirementSpec(spec);
        if (spec.raw_text) setNlText(spec.raw_text);
      } else if (p.program) {
        setRequirementSpec(
          fallbackRequirementFromForm(
            { ...DEFAULT_FORM, ...(p.form as RequirementForm) },
            p.program as ProgramSummary,
          ),
        );
      } else {
        setRequirementSpec(null);
      }
      setLocks({
        rooms: p.locks?.rooms ?? [],
        stair: p.locks?.stair ?? null,
        zones: p.locks?.zones ?? [],
      });
      setCandidates(p.candidates ?? []);
      setSelectedId(p.selected_id ?? p.candidates?.[0]?.id ?? null);
      setCompareId(p.compare_id ?? null);
      setHighlightRoomIds([]);
      setSelectedRoomId(null);
      setStats(null);
      setRejectedCandidates([]);
      setViolationSummary({});
      setProjectPicker(null);
      if (
        p.schema_versions?.solver_version &&
        p.schema_versions.generator_version &&
        p.schema_versions.evaluation_version
      ) {
        setSolverIdentity({
          solver_version: p.schema_versions.solver_version,
          generator_version: p.schema_versions.generator_version,
          evaluation_version: p.schema_versions.evaluation_version,
        });
      }
      const dirty = (p.candidates ?? []).some(
        (c) => c.revision_status === "dirty",
      );
      const missingSpec = !p.requirement_spec;
      if (detail.evaluation_version_mismatch) {
        setVersionHint(
          `评价版本已变（快照 ${p.schema_versions?.evaluation_version ?? "?"} → 当前 ${detail.current_evaluation_version}）：分数可能不可比；布局几何仍按快照。`,
        );
      } else if (dirty) {
        setVersionHint(
          "项目含已编辑草稿（Evaluation outdated）；评分非当前几何。",
        );
      } else if (missingSpec) {
        setVersionHint(
          "旧项目缺少 RequirementSpec，已用 form+program 降级重建；请重新 Generate 以固化意图。",
        );
      } else {
        setVersionHint(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setProjectBusy(false);
    }
  }, []);

  const onSelectCandidate = useCallback((id: string) => {
    setSelectedId(id);
    setHighlightRoomIds([]);
    setSelectedRoomId(null);
  }, []);

  const onRevalidate = useCallback(async () => {
    if (!selected?.placements || !program) {
      setError("无候选可重算");
      return;
    }
    if (selected.revision_status !== "dirty") {
      setMutationHint("当前候选无需 Revalidate");
      return;
    }
    setRevalidating(true);
    setError(null);
    try {
      const spec = resolveCanonicalSpec();
      if (!spec) throw new Error("缺少 RequirementSpec");
      const labelIndex = Math.max(
        0,
        candidates.findIndex((c) => c.id === selected.id),
      );
      const next = await revalidateMutation({
        requirementSpec: spec,
        placements: selected.placements,
        locks: cloneLayoutLocks(locks),
        zones: selected.zones ?? [],
        candidateId: selected.id,
        seed: selected.seed,
        labelIndex: Math.min(labelIndex, 25),
        variantParentId: selected.variant_parent_id,
        variantGeneration: selected.variant_generation,
        lockSnapshotId: selected.lock_snapshot_id,
        mutations: selected.mutations ?? [],
        revisionParentId: selected.revision_parent_id ?? selected.id,
      });
      const merged: CandidatePayload = {
        ...next,
        label: selected.label,
        revision_status: "validated",
        mutations: selected.mutations ?? next.mutations ?? [],
      };
      setCandidates((prev) =>
        prev.map((c) => (c.id === selected.id ? merged : c)),
      );
      if (merged.provenance?.evaluation_version) {
        setSolverIdentity({
          solver_version: merged.provenance.solver_version,
          generator_version: merged.provenance.generator_version,
          evaluation_version: merged.provenance.evaluation_version,
        });
      }
      setMutationHint(
        merged.validation?.valid === false
          ? "Revalidate 完成 · 存在硬性违规"
          : `Revalidate 完成 · Score ${merged.score?.toFixed(1) ?? "—"}`,
      );
      setVersionHint(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRevalidating(false);
    }
  }, [selected, program, locks, candidates, resolveCanonicalSpec]);

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
      {projectPicker !== null && (
        <div className="project-picker-backdrop" role="presentation">
          <div className="project-picker" role="dialog" aria-label="打开项目">
            <header className="project-picker-head">
              <h3>打开项目</h3>
              <button
                type="button"
                className="secondary"
                onClick={() => setProjectPicker(null)}
              >
                关闭
              </button>
            </header>
            {projectPicker.length === 0 ? (
              <p className="muted">尚无已保存项目</p>
            ) : (
              <ul className="project-picker-list">
                {projectPicker.map((p) => (
                  <li key={p.id}>
                    <button
                      type="button"
                      className="project-picker-item"
                      disabled={projectBusy}
                      onClick={() => void onLoadProject(p.id)}
                    >
                      <span className="project-picker-name">{p.name}</span>
                      <span className="muted project-picker-time">
                        {p.updated_at.slice(0, 19).replace("T", " ")}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
      {reportHtml ? (
        <ReportPreview
          html={reportHtml}
          title={`${projectName.trim() || "未命名"} · 设计报告`}
          onClose={() => setReportHtml(null)}
        />
      ) : null}
      <div className="app-main">
        <RequirementsPanel
          form={form}
          onChange={setForm}
          onGenerate={() => void run("form")}
          onBenchmark={() => void run("benchmark")}
          nlText={nlText}
          onNlTextChange={setNlText}
          onParseNl={() => void onParseNl()}
          onParseAndGenerate={() => void onParseAndGenerate()}
          nlBusy={nlBusy}
          nlHint={nlHint}
          loading={loading}
          engineStatus={engineStatus}
          onRetryEngine={() => void onRetryEngine()}
          llmState={displayLlmState}
          llmModel={llmStatus?.model ?? null}
          llmDetail={llmStatus?.detail ?? null}
          program={program}
          requirementSpec={requirementSpec}
          onUpdateAssumption={onUpdateAssumption}
          onRemoveAssumption={onRemoveAssumption}
          onDismissUnknown={onDismissUnknown}
          error={error ?? engineHint}
          stats={stats}
          rejectedCandidates={rejectedCandidates}
          violationSummary={violationSummary}
          projectName={projectName}
          onProjectNameChange={setProjectName}
          onSaveProject={() => void onSaveProject()}
          onExportReport={() => void onExportReport()}
          onExportSvg={(scope) => void onExportSvg(scope)}
          onExportPng={(scope, size) => void onExportPng(scope, size)}
          onOpenProjects={() => void onOpenProjects()}
          projectBusy={projectBusy}
          reportBusy={reportBusy}
          versionHint={versionHint}
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
          onRevalidate={() => void onRevalidate()}
          regenerating={loading}
          revalidating={revalidating}
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
