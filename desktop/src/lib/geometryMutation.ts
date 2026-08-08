/**
 * NON-AUTHORITATIVE CLIENT PREVIEW — Phase 5.1 / 5.1.1
 *
 * 本文件仅服务指针跟随、粗 snap、共墙手柄与文案。
 * 几何合法性裁决在 solver.mutation.authority / POST /api/mutations/preview。
 * 禁止在此添加 HARD_MIN_EDGE / zone lock / access 等 solver 规则复制。
 */

import type { RoomPlacementPayload } from "../api/client";

export type MutationKind = "move" | "resize" | "adjust_wall" | "lock" | "unlock";

export type PlacementRect = {
  x: number;
  y: number;
  width: number;
  depth: number;
};

export type WallAxis = "x" | "y";

export type SharedWall = {
  floor_id: string;
  room_a: string;
  room_b: string;
  axis: WallAxis;
  coord: number;
  along0: number;
  along1: number;
};

export type MutationReject = {
  code: string;
  message: string;
};

export type MutationPreviewResult = {
  ok: boolean;
  reasons: MutationReject[];
  warnings: MutationReject[];
  snapped: PlacementRect | null;
  snappedPartner: PlacementRect | null;
  conflictRoomIds: string[];
};

/**
 * 指针拖拽时的视觉下限（米）。非权威：真正硬拒由 Python Authority 决定。
 * FloorplanView resize 夹紧用，避免手柄拖到 0 宽崩溃。
 */
export const VISUAL_MIN_EDGE = 0.9;

/** 共墙手柄检测阈值（米）；可编辑性最终以 Python list_shared_walls / Authority 为准。 */
const VISUAL_SHARED_WALL_MIN = 0.9;

export function snapValue(value: number, module: number): number {
  if (module <= 0) return value;
  return Math.round(value / module) * module;
}

function clamp(value: number, min: number, max: number): number {
  if (max < min) return min;
  return Math.min(max, Math.max(min, value));
}

/** 拖拽过程粗 snap：贴格 + 夹在场地内。不检查 lock / overlap / zone。 */
export function visualSnapRect(
  proposed: PlacementRect,
  floorWidth: number,
  floorDepth: number,
  snapModule: number,
  kind: "move" | "resize" = "move",
): PlacementRect {
  const module = snapModule > 0 ? snapModule : 0.3;
  let x: number;
  let y: number;
  let width: number;
  let depth: number;
  if (kind === "resize") {
    const x0 = snapValue(proposed.x, module);
    const y0 = snapValue(proposed.y, module);
    const x1 = snapValue(proposed.x + proposed.width, module);
    const y1 = snapValue(proposed.y + proposed.depth, module);
    width = Math.max(VISUAL_MIN_EDGE, x1 - x0);
    depth = Math.max(VISUAL_MIN_EDGE, y1 - y0);
    x = x0;
    y = y0;
  } else {
    x = snapValue(proposed.x, module);
    y = snapValue(proposed.y, module);
    width = proposed.width;
    depth = proposed.depth;
  }
  x = clamp(x, 0, Math.max(0, floorWidth - width));
  y = clamp(y, 0, Math.max(0, floorDepth - depth));
  width = clamp(width, VISUAL_MIN_EDGE, Math.max(VISUAL_MIN_EDGE, floorWidth - x));
  depth = clamp(depth, VISUAL_MIN_EDGE, Math.max(VISUAL_MIN_EDGE, floorDepth - y));
  return { x, y, width, depth };
}

function rectOf(p: RoomPlacementPayload): PlacementRect {
  return { x: p.x, y: p.y, width: p.width, depth: p.depth };
}

function sharedEdgeLength(a: PlacementRect, b: PlacementRect): number {
  const tol = 1e-6;
  if (Math.abs(a.x + a.width - b.x) <= tol || Math.abs(b.x + b.width - a.x) <= tol) {
    const y0 = Math.max(a.y, b.y);
    const y1 = Math.min(a.y + a.depth, b.y + b.depth);
    return Math.max(0, y1 - y0);
  }
  if (Math.abs(a.y + a.depth - b.y) <= tol || Math.abs(b.y + b.depth - a.y) <= tol) {
    const x0 = Math.max(a.x, b.x);
    const x1 = Math.min(a.x + a.width, b.x + b.width);
    return Math.max(0, x1 - x0);
  }
  return 0;
}

function sharedWallBetween(
  idA: string,
  ra: PlacementRect,
  idB: string,
  rb: PlacementRect,
  floorId: string,
  minLength: number,
): SharedWall | null {
  const len = sharedEdgeLength(ra, rb);
  if (len + 1e-9 < minLength) return null;
  const tol = 1e-6;
  for (const [left, right, lid, rid] of [
    [ra, rb, idA, idB] as const,
    [rb, ra, idB, idA] as const,
  ]) {
    if (Math.abs(left.x + left.width - right.x) <= tol) {
      const y0 = Math.max(left.y, right.y);
      const y1 = Math.min(left.y + left.depth, right.y + right.depth);
      if (y1 - y0 + 1e-9 >= minLength) {
        return {
          floor_id: floorId,
          room_a: lid,
          room_b: rid,
          axis: "x",
          coord: left.x + left.width,
          along0: y0,
          along1: y1,
        };
      }
    }
  }
  for (const [top, bottom, tid, bid] of [
    [ra, rb, idA, idB] as const,
    [rb, ra, idB, idA] as const,
  ]) {
    if (Math.abs(top.y + top.depth - bottom.y) <= tol) {
      const x0 = Math.max(top.x, bottom.x);
      const x1 = Math.min(top.x + top.width, bottom.x + bottom.width);
      if (x1 - x0 + 1e-9 >= minLength) {
        return {
          floor_id: floorId,
          room_a: tid,
          room_b: bid,
          axis: "y",
          coord: top.y + top.depth,
          along0: x0,
          along1: x1,
        };
      }
    }
  }
  return null;
}

function hasTJunction(
  wall: SharedWall,
  rooms: RoomPlacementPayload[],
  ignore: Set<string>,
): boolean {
  const tol = 1e-4;
  for (const p of rooms) {
    if (ignore.has(p.room_id) || p.floor_id !== wall.floor_id) continue;
    const r = rectOf(p);
    if (wall.axis === "x") {
      const onLine =
        Math.abs(r.x - wall.coord) <= tol ||
        Math.abs(r.x + r.width - wall.coord) <= tol;
      if (!onLine) continue;
      const y0 = Math.max(r.y, wall.along0);
      const y1 = Math.min(r.y + r.depth, wall.along1);
      if (y1 - y0 > tol) return true;
    } else {
      const onLine =
        Math.abs(r.y - wall.coord) <= tol ||
        Math.abs(r.y + r.depth - wall.coord) <= tol;
      if (!onLine) continue;
      const x0 = Math.max(r.x, wall.along0);
      const x1 = Math.min(r.x + r.width, wall.along1);
      if (x1 - x0 > tol) return true;
    }
  }
  return false;
}

/** 枚举共墙手柄候选（UI）；提交合法性由 Python Authority 裁决。 */
export function listSharedWalls(
  placements: RoomPlacementPayload[],
  floorId?: string,
  minLength = VISUAL_SHARED_WALL_MIN,
): SharedWall[] {
  const rooms = placements.filter(
    (p) =>
      !p.room_id.startsWith("stair-") &&
      (floorId == null || p.floor_id === floorId),
  );
  const walls: SharedWall[] = [];
  for (let i = 0; i < rooms.length; i++) {
    const a = rooms[i];
    for (let j = i + 1; j < rooms.length; j++) {
      const b = rooms[j];
      if (a.floor_id !== b.floor_id) continue;
      const wall = sharedWallBetween(
        a.room_id,
        rectOf(a),
        b.room_id,
        rectOf(b),
        a.floor_id,
        minLength,
      );
      if (!wall) continue;
      if (hasTJunction(wall, rooms, new Set([wall.room_a, wall.room_b]))) {
        continue;
      }
      walls.push(wall);
    }
  }
  return walls;
}

/** 拖拽过程粗算两侧几何（视觉）；权威仍走 API。 */
export function applyWallCoord(
  rectA: PlacementRect,
  rectB: PlacementRect,
  axis: WallAxis,
  coord: number,
  hardMin = VISUAL_MIN_EDGE,
): { a: PlacementRect; b: PlacementRect } | { error: string } {
  if (axis === "x") {
    const aLeft = rectA.x;
    const bRight = rectB.x + rectB.width;
    if (coord <= aLeft + hardMin - 1e-9 || coord >= bRight - hardMin + 1e-9) {
      return { error: "mutation.min_edge" };
    }
    return {
      a: { x: rectA.x, y: rectA.y, width: coord - rectA.x, depth: rectA.depth },
      b: {
        x: coord,
        y: rectB.y,
        width: bRight - coord,
        depth: rectB.depth,
      },
    };
  }
  const aTop = rectA.y;
  const bBottom = rectB.y + rectB.depth;
  if (coord <= aTop + hardMin - 1e-9 || coord >= bBottom - hardMin + 1e-9) {
    return { error: "mutation.min_edge" };
  }
  return {
    a: { x: rectA.x, y: rectA.y, width: rectA.width, depth: coord - rectA.y },
    b: {
      x: rectB.x,
      y: coord,
      width: rectB.width,
      depth: bBottom - coord,
    },
  };
}

export function mutationRejectMessage(result: MutationPreviewResult): string {
  return result.reasons.map((r) => r.message).join("；") || "无法提交变更";
}

export function mutationWarningMessage(
  result: MutationPreviewResult,
): string | null {
  if (!result.warnings.length) return null;
  return result.warnings.map((r) => r.message).join("；");
}

export function mutationLiveMessage(
  result: MutationPreviewResult,
): string | null {
  if (!result.ok) return mutationRejectMessage(result);
  return mutationWarningMessage(result);
}

/** @deprecated 使用 VISUAL_MIN_EDGE；非权威 */
export const HARD_MIN_EDGE = VISUAL_MIN_EDGE;
