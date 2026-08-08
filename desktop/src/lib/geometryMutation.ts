/** Phase 4.3 Geometry Mutation Authority（会话侧；与 solver/mutation 规则对齐）。 */

import type {
  LayoutLocks,
  RoomPlacementPayload,
  ZonePlacementPayload,
} from "../api/client";

export type MutationKind = "move" | "resize" | "lock" | "unlock";

export type PlacementRect = {
  x: number;
  y: number;
  width: number;
  depth: number;
};

export type GeometryMutation = {
  kind: MutationKind;
  room_id: string | null;
  floor_id: string;
  before: PlacementRect | null;
  proposed: PlacementRect | null;
  source?: "pointer" | "inspector" | "system";
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
};

/** 与 solver 对齐的绝对最小边长（米） */
export const HARD_MIN_EDGE = 0.9;

function snapValue(value: number, module: number): number {
  if (module <= 0) return value;
  return Math.round(value / module) * module;
}

function intersects(
  a: PlacementRect,
  b: PlacementRect,
  tol = 1e-4,
): boolean {
  return (
    a.x < b.x + b.width - tol &&
    a.x + a.width > b.x + tol &&
    a.y < b.y + b.depth - tol &&
    a.y + a.depth > b.y + tol
  );
}

function contains(
  outer: PlacementRect,
  inner: PlacementRect,
  tol = 1e-6,
): boolean {
  return (
    inner.x >= outer.x - tol &&
    inner.y >= outer.y - tol &&
    inner.x + inner.width <= outer.x + outer.width + tol &&
    inner.y + inner.depth <= outer.y + outer.depth + tol
  );
}

function zoneEnvelopes(
  locks: LayoutLocks,
): Map<string, PlacementRect> {
  const roomLocked = new Set(locks.rooms.map((r) => r.room_id));
  const map = new Map<string, PlacementRect>();
  for (const z of locks.zones) {
    const env = { x: z.x, y: z.y, width: z.width, depth: z.depth };
    for (const rid of z.room_ids ?? []) {
      if (roomLocked.has(rid)) continue;
      map.set(rid, env);
    }
  }
  return map;
}

function snapRectEdges(prop: PlacementRect, module: number): PlacementRect {
  const x0 = snapValue(prop.x, module);
  const y0 = snapValue(prop.y, module);
  const x1 = snapValue(prop.x + prop.width, module);
  const y1 = snapValue(prop.y + prop.depth, module);
  const w = module > 0 ? Math.max(module, x1 - x0) : Math.max(0, x1 - x0);
  const d = module > 0 ? Math.max(module, y1 - y0) : Math.max(0, y1 - y0);
  return { x: x0, y: y0, width: w, depth: d };
}

export type RoomSizeHints = {
  min_width?: number | null;
  min_area?: number | null;
  target_area?: number | null;
};

export type PreviewGeometryContext = {
  placements: RoomPlacementPayload[];
  locks: LayoutLocks;
  floorWidth: number;
  floorDepth: number;
  snapModule?: number;
  zones?: ZonePlacementPayload[];
  /** RESIZE soft 提示用 */
  roomHints?: RoomSizeHints;
};

function geometryReasons(
  roomId: string,
  floorId: string,
  currentFloorId: string,
  snapped: PlacementRect,
  ctx: PreviewGeometryContext,
): MutationReject[] {
  const reasons: MutationReject[] = [];
  const buildable = {
    x: 0,
    y: 0,
    width: ctx.floorWidth,
    depth: ctx.floorDepth,
  };
  if (!contains(buildable, snapped)) {
    reasons.push({
      code: "mutation.outside_buildable",
      message: "目标位置超出可建范围",
    });
  }

  const isRoomLocked = ctx.locks.rooms.some((r) => r.room_id === roomId);
  const envelopes = zoneEnvelopes(ctx.locks);
  if (!isRoomLocked && !roomId.startsWith("stair-")) {
    const env = envelopes.get(roomId);
    if (env && !contains(env, snapped)) {
      reasons.push({
        code: "mutation.zone_envelope",
        message: "不可移出锁定分区 envelope",
      });
    }
  }

  if (ctx.locks.stair && !roomId.startsWith("stair-")) {
    const stair = {
      x: ctx.locks.stair.x,
      y: ctx.locks.stair.y,
      width: ctx.locks.stair.width,
      depth: ctx.locks.stair.depth,
    };
    if (intersects(snapped, stair)) {
      reasons.push({
        code: "mutation.stair_overlap",
        message: "不可与锁定楼梯核重叠",
      });
    }
  }

  for (const p of ctx.placements) {
    if (p.room_id === roomId) continue;
    if (roomId.startsWith("stair-")) {
      if (p.room_id.startsWith("stair-")) continue;
      if (p.floor_id !== floorId) continue;
    } else if (p.floor_id !== currentFloorId) {
      continue;
    }
    const other = {
      x: p.x,
      y: p.y,
      width: p.width,
      depth: p.depth,
    };
    if (intersects(snapped, other)) {
      reasons.push({
        code: "mutation.overlap",
        message: `与房间 ${p.room_id} 重叠`,
      });
      break;
    }
  }

  for (const lr of ctx.locks.rooms) {
    if (lr.room_id === roomId) continue;
    if (lr.floor_id !== floorId) continue;
    if (
      intersects(snapped, {
        x: lr.x,
        y: lr.y,
        width: lr.width,
        depth: lr.depth,
      })
    ) {
      reasons.push({
        code: "mutation.lock_overlap",
        message: `与锁定房间 ${lr.room_id} 重叠`,
      });
      break;
    }
  }

  return reasons;
}

function softSizeWarnings(
  roomId: string,
  snapped: PlacementRect,
  hints?: RoomSizeHints,
): MutationReject[] {
  if (!hints || roomId.startsWith("stair-")) return [];
  const warnings: MutationReject[] = [];
  const minDim = Math.min(snapped.width, snapped.depth);
  if (hints.min_width != null && minDim < hints.min_width - 1e-9) {
    warnings.push({
      code: "mutation.soft_min_width",
      message: `净宽偏小：${minDim.toFixed(2)} < 建议 ${hints.min_width.toFixed(2)} m`,
    });
  }
  const minArea =
    hints.min_area != null
      ? hints.min_area
      : hints.target_area != null
        ? hints.target_area * 0.85
        : null;
  const area = snapped.width * snapped.depth;
  if (minArea != null && area < minArea - 1e-9) {
    warnings.push({
      code: "mutation.soft_min_area",
      message: `面积偏小：${area.toFixed(1)} < 建议 ${minArea.toFixed(1)} m²`,
    });
  }
  return warnings;
}

/** MOVE 预览：snap 原点 + LockGuard/几何约束；ok 才可 Commit。 */
export function previewMove(
  roomId: string,
  proposed: PlacementRect,
  floorId: string,
  ctx: PreviewGeometryContext,
): MutationPreviewResult {
  const module = ctx.snapModule ?? 0.3;
  const current = ctx.placements.find((p) => p.room_id === roomId);
  if (!current) {
    return {
      ok: false,
      reasons: [{ code: "mutation.unknown_room", message: `未知房间：${roomId}` }],
      warnings: [],
      snapped: null,
    };
  }

  const snapped: PlacementRect = {
    x: snapValue(proposed.x, module),
    y: snapValue(proposed.y, module),
    width: proposed.width,
    depth: proposed.depth,
  };
  const reasons = geometryReasons(
    roomId,
    floorId,
    current.floor_id,
    snapped,
    ctx,
  );
  return {
    ok: reasons.length === 0,
    reasons,
    warnings: [],
    snapped,
  };
}

/** RESIZE 预览：四边 snap + 最小边硬拒 + soft min_width/area。 */
export function previewResize(
  roomId: string,
  proposed: PlacementRect,
  floorId: string,
  ctx: PreviewGeometryContext,
): MutationPreviewResult {
  const module = ctx.snapModule ?? 0.3;
  const current = ctx.placements.find((p) => p.room_id === roomId);
  if (!current) {
    return {
      ok: false,
      reasons: [{ code: "mutation.unknown_room", message: `未知房间：${roomId}` }],
      warnings: [],
      snapped: null,
    };
  }

  const snapped = snapRectEdges(proposed, module);
  const reasons: MutationReject[] = [];
  if (
    snapped.width < HARD_MIN_EDGE - 1e-9 ||
    snapped.depth < HARD_MIN_EDGE - 1e-9
  ) {
    reasons.push({
      code: "mutation.min_edge",
      message: `边长不可小于 ${HARD_MIN_EDGE} m`,
    });
  }
  reasons.push(
    ...geometryReasons(roomId, floorId, current.floor_id, snapped, ctx),
  );
  const warnings = softSizeWarnings(roomId, snapped, ctx.roomHints);
  return {
    ok: reasons.length === 0,
    reasons,
    warnings,
    snapped,
  };
}

export function mutationRejectMessage(result: MutationPreviewResult): string {
  return result.reasons.map((r) => r.message).join("；") || "无法提交变更";
}

export function mutationWarningMessage(result: MutationPreviewResult): string | null {
  if (!result.warnings.length) return null;
  return result.warnings.map((r) => r.message).join("；");
}

/** @deprecated 使用 PreviewGeometryContext */
export type PreviewMoveContext = PreviewGeometryContext;
