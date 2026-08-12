import {
  fallbackRequirementFromForm,
  syncRequirementSpacesFromProgram,
  type CandidatePayload,
  type LayoutLocks,
  type MutationPreviewApiResult,
  type MutationRecordPayload,
  type ProgramSummary,
  type RequirementForm,
  type RequirementSpecPayload,
} from "../api/client";
import type { MutationPreviewResult } from "../lib/geometryMutation";

/** 发 Generate 前冻结 locks，避免请求过程中 UI 改锁改变语义 */
export function cloneLayoutLocks(locks: LayoutLocks): LayoutLocks {
  return {
    rooms: locks.rooms.map((r) => ({ ...r })),
    stair: locks.stair ? { ...locks.stair } : null,
    zones: locks.zones.map((z) => ({
      ...z,
      room_ids: z.room_ids ? [...z.room_ids] : [],
    })),
  };
}

export function apiPreviewToLocal(
  p: MutationPreviewApiResult,
): MutationPreviewResult {
  return {
    ok: p.ok,
    reasons: p.reasons ?? [],
    warnings: p.warnings ?? [],
    snapped: p.snapped ?? null,
    snappedPartner: p.snapped_partner ?? null,
    conflictRoomIds: p.conflict_room_ids ?? [],
  };
}

export function newMutationId(): string {
  return `mut-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

export function markCandidateDirty(
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

export type SchemaVersions = {
  solver_version: string | null;
  generator_version: string | null;
  evaluation_version: string | null;
};

export function buildSchemaVersions(
  solverIdentity: {
    solver_version: string;
    generator_version: string;
    evaluation_version: string;
  } | null,
  candidates: CandidatePayload[],
): SchemaVersions {
  const fromCand = candidates.find((c) => c.provenance)?.provenance;
  return {
    solver_version:
      solverIdentity?.solver_version ?? fromCand?.solver_version ?? null,
    generator_version:
      solverIdentity?.generator_version ?? fromCand?.generator_version ?? null,
    evaluation_version:
      solverIdentity?.evaluation_version ??
      fromCand?.evaluation_version ??
      null,
  };
}

/** 会话求解用的 RequirementSpec：canonical + Program 面积补丁。 */
export function resolveCanonicalSpecFrom(
  program: ProgramSummary | null,
  requirementSpec: RequirementSpecPayload | null,
  form: RequirementForm,
): RequirementSpecPayload | null {
  if (!program) return null;
  if (requirementSpec) {
    return syncRequirementSpacesFromProgram(requirementSpec, program);
  }
  return fallbackRequirementFromForm(form, program);
}
