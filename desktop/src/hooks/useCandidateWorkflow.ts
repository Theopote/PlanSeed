import {
  useCallback,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";
import {
  fetchLlmStatus,
  generateBenchmark,
  generateFromForm,
  generateFromProgram,
  parseRequirementsNl,
  type CandidatePayload,
  type GenerateResponse,
  type LayoutLocks,
  type LlmHealthState,
  type LlmStatusPayload,
  type LockedRoomRect,
  type LockedStairCore,
  type LockedZoneRect,
  type ProgramSummary,
  type RejectedCandidatePayload,
  type RequirementForm,
  type RequirementSpecPayload,
} from "../api/client";
import { locksFingerprint } from "../lib/lineage";
import { cloneLayoutLocks } from "./sessionHelpers";

const EMPTY_LOCKS: LayoutLocks = { rooms: [], stair: null, zones: [] };

export type SolverIdentity = {
  solver_version: string;
  generator_strategy?: string;
  generator_version: string;
  selection_strategy?: string;
  selection_version?: string;
  evaluation_version: string;
  assignment_strategy?: string;
  geometry_backend?: string;
};

function identityFromPayload(
  sid: Record<string, unknown> | SolverIdentity,
): SolverIdentity {
  const s = sid as Record<string, unknown>;
  const opt = (key: string): string | undefined =>
    s[key] != null ? String(s[key]) : undefined;
  return {
    solver_version: String(s.solver_version ?? ""),
    generator_strategy: opt("generator_strategy"),
    generator_version: String(s.generator_version ?? ""),
    selection_strategy: opt("selection_strategy"),
    selection_version: opt("selection_version"),
    evaluation_version: String(s.evaluation_version ?? ""),
    assignment_strategy: opt("assignment_strategy"),
    geometry_backend: opt("geometry_backend"),
  };
}

export type CandidateStats = {
  generated: number;
  valid: number;
  rejected: number;
};

export type UseCandidateWorkflowArgs = {
  setError: Dispatch<SetStateAction<string | null>>;
  form: RequirementForm;
  setRequirementSpec: Dispatch<SetStateAction<RequirementSpecPayload | null>>;
  resolveCanonicalSpec: () => RequirementSpecPayload | null;
  nlText: string;
  setNlBusy: Dispatch<SetStateAction<boolean>>;
  setNlHint: Dispatch<SetStateAction<string | null>>;
  applyParsedSpec: (spec: RequirementSpecPayload) => void;
  setLlmSessionState: Dispatch<SetStateAction<LlmHealthState | null>>;
  setLlmStatus: Dispatch<SetStateAction<LlmStatusPayload | null>>;
  setMutationHint: Dispatch<SetStateAction<string | null>>;
};

export function useCandidateWorkflow({
  setError,
  form,
  setRequirementSpec,
  resolveCanonicalSpec,
  nlText,
  setNlBusy,
  setNlHint,
  applyParsedSpec,
  setLlmSessionState,
  setLlmStatus,
  setMutationHint,
}: UseCandidateWorkflowArgs) {
  const [loading, setLoading] = useState(false);
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
  const [rejectedCandidates, setRejectedCandidates] = useState<
    RejectedCandidatePayload[]
  >([]);
  const [violationSummary, setViolationSummary] = useState<
    Record<string, number>
  >({});
  const [stats, setStats] = useState<CandidateStats | null>(null);
  const [solverIdentity, setSolverIdentity] = useState<SolverIdentity | null>(
    null,
  );

  const selected = candidates.find((c) => c.id === selectedId) ?? null;
  const compareWith =
    compareId && compareId !== selectedId
      ? (candidates.find((c) => c.id === compareId) ?? null)
      : null;

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
    (data: GenerateResponse, lockSnap?: string) => {
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
        setSolverIdentity(identityFromPayload(data.solver_identity));
      }
      const fp = lockSnap ?? locksFingerprint(locks);
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
    [relabel, stampRootLineage, locks, setRequirementSpec, setMutationHint, setError],
  );

  const runSeq = useRef(0);

  const run = useCallback(
    async (mode: "form" | "benchmark" | "program" | "variant") => {
      const token = ++runSeq.current;
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
          if (data.solver_identity) {
            setSolverIdentity(identityFromPayload(data.solver_identity));
          }
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
          const labeled = relabel([...candidates, ...fresh]);
          const keepIds = new Set<string>();
          if (prevSelected) keepIds.add(prevSelected);
          if (fresh[0]) keepIds.add(fresh[0].id);
          let merged = labeled;
          if (labeled.length > 16) {
            const tail = labeled.slice(-16);
            const missing = labeled.filter(
              (c) => keepIds.has(c.id) && !tail.some((t) => t.id === c.id),
            );
            merged = [...missing, ...tail].slice(-16);
          }
          if (token !== runSeq.current) return;
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
            if (
              prevSelected &&
              prevSelected !== pick.id &&
              merged.some((c) => c.id === prevSelected)
            ) {
              setCompareId(prevSelected);
            }
          }
          setHighlightRoomIds([]);
          setSelectedRoomId(null);
          setMutationHint(null);
          setError(null);
          return;
        }

        if (mode === "benchmark") {
          setLocks({ ...EMPTY_LOCKS });
          const data = await generateBenchmark();
          if (token !== runSeq.current) return;
          applyResult(data, locksFingerprint(EMPTY_LOCKS));
          return;
        }
        if (mode === "program") {
          if (!program) throw new Error("尚无 Program，请先 Generate");
          const spec = resolveCanonicalSpec();
          if (!spec) throw new Error("缺少 RequirementSpec");
          const snap = locksFingerprint(locks);
          const data = await generateFromProgram(spec, {
            locks: cloneLayoutLocks(locks),
          });
          if (token !== runSeq.current) return;
          applyResult(data, snap);
          return;
        }
        setLocks({ ...EMPTY_LOCKS });
        const data = await generateFromForm(form);
        if (token !== runSeq.current) return;
        applyResult(data, locksFingerprint(EMPTY_LOCKS));
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
      setRequirementSpec,
      setError,
      setMutationHint,
    ],
  );

  const onParseAndGenerate = useCallback(async () => {
    const token = ++runSeq.current;
    setNlBusy(true);
    setLoading(true);
    setLlmSessionState("ParseRunning");
    setNlHint(null);
    setError(null);
    try {
      const parsed = await parseRequirementsNl(nlText);
      applyParsedSpec(parsed.requirement_spec);
      setLocks({ ...EMPTY_LOCKS });
      const data = await generateFromProgram(parsed.requirement_spec, {
        candidate_count: 16,
        return_top_k: 5,
      });
      if (token !== runSeq.current) return;
      applyResult(data, locksFingerprint(EMPTY_LOCKS));
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
  }, [
    nlText,
    applyParsedSpec,
    applyResult,
    setNlBusy,
    setNlHint,
    setLlmSessionState,
    setLlmStatus,
    setError,
  ]);

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
          room_ids: [...(z.room_ids ?? [])],
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
      const rooms = [
        ...new Set(matches.flatMap((z) => z.room_ids ?? []).filter(Boolean)),
      ];
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
    locks.rooms.length + (locks.stair ? 1 : 0) + locks.zones.length;
  const lockedZoneRoomIds = locks.zones.flatMap((z) => z.room_ids ?? []);

  return {
    loading,
    setLoading,
    program,
    setProgram,
    candidates,
    setCandidates,
    selectedId,
    setSelectedId,
    compareId,
    setCompareId,
    highlightRoomIds,
    setHighlightRoomIds,
    selectedRoomId,
    setSelectedRoomId,
    locks,
    setLocks,
    rejectedCandidates,
    setRejectedCandidates,
    violationSummary,
    setViolationSummary,
    stats,
    setStats,
    solverIdentity,
    setSolverIdentity,
    selected,
    compareWith,
    relabel,
    stampRootLineage,
    applyResult,
    run,
    onParseAndGenerate,
    onToggleRoomLock,
    onClearLocks,
    onToggleZoneLock,
    onSelectZone,
    onSelectRoom,
    onComparePick,
    onSelectCandidate,
    lockCount,
    lockedZoneRoomIds,
  };
}
