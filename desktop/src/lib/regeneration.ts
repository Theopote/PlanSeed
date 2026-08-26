import type {
  CandidatePayload,
  ProgramSummary,
  RegenerationScope,
  RoomPlacementPayload,
} from "../api/client";

/** 从候选提取 program 房间 + 楼梯放置，供 partial regen API 构建 locks。 */
export function programPlacementsFromCandidate(
  candidate: CandidatePayload,
  program: ProgramSummary,
): RoomPlacementPayload[] {
  const programIds = new Set(program.rooms.map((r) => r.id));
  return (candidate.placements ?? []).filter(
    (p) => programIds.has(p.room_id) || p.room_id.startsWith("stair-"),
  );
}

export function buildPartialRegenerationScope(
  mutableRoomId: string,
): RegenerationScope {
  return {
    mutable_rooms: [mutableRoomId],
    locked_rooms: [],
    affected_neighbors: [],
    preserve_topology: true,
    preserve_floor_assignment: true,
  };
}

export function canPartialRegenerateRoom(
  roomId: string,
  program: ProgramSummary | null,
): boolean {
  if (!program) return false;
  if (roomId.startsWith("stair-") || roomId.startsWith("void-")) return false;
  return program.rooms.some((r) => r.id === roomId);
}
