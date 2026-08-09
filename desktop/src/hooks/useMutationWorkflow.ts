import {
  useCallback,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";
import {
  previewMutation,
  revalidateMutation,
  type CandidatePayload,
  type LayoutLocks,
  type LockedRoomRect,
  type ProgramSummary,
  type MutationRecordPayload,
  type RequirementSpecPayload,
} from "../api/client";
import {
  mutationLiveMessage,
  mutationRejectMessage,
  mutationWarningMessage,
  visualSnapRect,
  type MutationPreviewResult,
} from "../lib/geometryMutation";
import type {
  LivePreviewResult,
  MutationDragKind,
  ProposeMoveResult,
  RoomMovePose,
  WallAdjustPose,
} from "../components/FloorplanView";
import type { SolverIdentity } from "./useCandidateWorkflow";
import {
  apiPreviewToLocal,
  cloneLayoutLocks,
  markCandidateDirty,
  newMutationId,
} from "./sessionHelpers";

export type UseMutationWorkflowArgs = {
  setError: Dispatch<SetStateAction<string | null>>;
  selected: CandidatePayload | null;
  selectedId: string | null;
  program: ProgramSummary | null;
  locks: LayoutLocks;
  setLocks: Dispatch<SetStateAction<LayoutLocks>>;
  candidates: CandidatePayload[];
  setCandidates: Dispatch<SetStateAction<CandidatePayload[]>>;
  resolveCanonicalSpec: () => RequirementSpecPayload | null;
  setSolverIdentity: Dispatch<SetStateAction<SolverIdentity | null>>;
  setVersionHint: Dispatch<SetStateAction<string | null>>;
};

export function useMutationWorkflow({
  setError,
  selected,
  selectedId,
  program,
  locks,
  setLocks,
  candidates,
  setCandidates,
  resolveCanonicalSpec,
  setSolverIdentity,
  setVersionHint,
}: UseMutationWorkflowArgs) {
  const [mutationHint, setMutationHint] = useState<string | null>(null);
  const [revalidating, setRevalidating] = useState(false);
  const livePreviewTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

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
    [selected, selectedId, program, callAuthorityPreview, setCandidates, setLocks],
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
    [selected, selectedId, program, callAuthorityPreview, setCandidates, setLocks],
  );

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
          generator_strategy: merged.provenance.generator_strategy ?? undefined,
          generator_version: merged.provenance.generator_version,
          selection_strategy: merged.provenance.selection_strategy ?? undefined,
          selection_version: merged.provenance.selection_version ?? undefined,
          evaluation_version: merged.provenance.evaluation_version,
          assignment_strategy:
            merged.provenance.assignment_strategy ?? undefined,
          geometry_backend: merged.provenance.geometry_backend ?? undefined,
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
  }, [
    selected,
    program,
    locks,
    candidates,
    resolveCanonicalSpec,
    setCandidates,
    setSolverIdentity,
    setVersionHint,
    setError,
  ]);

  return {
    mutationHint,
    setMutationHint,
    revalidating,
    onLivePreview,
    onLiveWallPreview,
    onProposeMove,
    onProposeWall,
    onRevalidate,
  };
}
