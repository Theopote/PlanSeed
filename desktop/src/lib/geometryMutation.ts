/** Phase 4.3 Geometry Mutation Authority（会话侧；与 solver/mutation 规则对齐）。 */

import type {
  LayoutLocks,
  RoomPlacementPayload,
  ZonePlacementPayload,
} from "../api/client";

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

export type GeometryMutation = {
  kind: MutationKind;
  room_id: string | null;
  partner_room_id?: string | null;
  floor_id: string;
  before: PlacementRect | null;
  proposed: PlacementRect | null;
  proposed_partner?: PlacementRect | null;
  wall_axis?: WallAxis | null;
  wall_coord?: number | null;
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
  snappedPartner: PlacementRect | null;
  conflictRoomIds: string[];
};

/** 与 solver 对齐的绝对最小边长（米） */
export const HARD_MIN_EDGE = 0.9;
/** 与 MIN_ACCESS_WALL 对齐 */
export const MIN_ACCESS_WALL = 0.9;

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

/** 共边长度（贴边且投影重叠）；无共边返回 0 */
export function sharedEdgeLength(
  a: PlacementRect,
  b: PlacementRect,
  tol = 1e-6,
): number {
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

function geometryCheck(
  roomId: string,
  floorId: string,
  currentFloorId: string,
  snapped: PlacementRect,
  ctx: PreviewGeometryContext,
  ignoreRoomIds: Set<string> = new Set(),
): { reasons: MutationReject[]; conflictRoomIds: string[] } {
  const reasons: MutationReject[] = [];
  const conflictRoomIds: string[] = [];
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
      conflictRoomIds.push("__stair__");
    }
  }

  for (const p of ctx.placements) {
    if (p.room_id === roomId || ignoreRoomIds.has(p.room_id)) continue;
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
      conflictRoomIds.push(p.room_id);
      break;
    }
  }

  for (const lr of ctx.locks.rooms) {
    if (lr.room_id === roomId || ignoreRoomIds.has(lr.room_id)) continue;
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
      if (!conflictRoomIds.includes(lr.room_id)) {
        conflictRoomIds.push(lr.room_id);
      }
      break;
    }
  }

  return { reasons, conflictRoomIds };
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

/** 原共边邻居在 proposed 后丢失共边 → soft AccessImpact */
export function accessImpactWarnings(
  roomId: string,
  before: PlacementRect,
  after: PlacementRect,
  floorId: string,
  placements: RoomPlacementPayload[],
  minWall = MIN_ACCESS_WALL,
  ignoreRoomIds: Set<string> = new Set(),
): MutationReject[] {
  const lost: string[] = [];
  for (const p of placements) {
    if (p.room_id === roomId || ignoreRoomIds.has(p.room_id)) continue;
    if (p.floor_id !== floorId) continue;
    const other = { x: p.x, y: p.y, width: p.width, depth: p.depth };
    if (sharedEdgeLength(before, other) + 1e-9 < minWall) continue;
    if (sharedEdgeLength(after, other) + 1e-9 < minWall) {
      lost.push(p.room_id);
    }
  }
  if (!lost.length) return [];
  const names = lost.slice(0, 3).join("、");
  const more = lost.length > 3 ? ` 等${lost.length}处` : "";
  return [
    {
      code: "mutation.access_impact",
      message: `可能打断与 ${names}${more} 的通行共边`,
    },
  ];
}

function emptyFail(reasons: MutationReject[]): MutationPreviewResult {
  return {
    ok: false,
    reasons,
    warnings: [],
    snapped: null,
    snappedPartner: null,
    conflictRoomIds: [],
  };
}

function rectOf(p: RoomPlacementPayload): PlacementRect {
  return { x: p.x, y: p.y, width: p.width, depth: p.depth };
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
  // 竖向共边：左|右
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
  exclude: Set<string>,
  tol = 1e-4,
): boolean {
  for (const p of rooms) {
    if (exclude.has(p.room_id) || p.floor_id !== wall.floor_id) continue;
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

/** 枚举可编辑共墙（拒楼梯 / 不足长度 / T 接）。 */
export function listSharedWalls(
  placements: RoomPlacementPayload[],
  floorId?: string,
  minLength = MIN_ACCESS_WALL,
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

export function applyWallCoord(
  rectA: PlacementRect,
  rectB: PlacementRect,
  axis: WallAxis,
  coord: number,
  hardMin = HARD_MIN_EDGE,
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

/** ADJUST_WALL：共墙法向挪位，两侧联动。 */
export function previewAdjustWall(
  roomId: string,
  partnerRoomId: string,
  floorId: string,
  wallAxis: WallAxis,
  wallCoord: number,
  ctx: PreviewGeometryContext,
): MutationPreviewResult {
  const module = ctx.snapModule ?? 0.3;
  const pa = ctx.placements.find((p) => p.room_id === roomId);
  const pb = ctx.placements.find((p) => p.room_id === partnerRoomId);
  if (!pa || !pb) {
    return emptyFail([
      { code: "mutation.unknown_room", message: "共墙两侧房间不存在" },
    ]);
  }
  if (pa.floor_id !== pb.floor_id || pa.floor_id !== floorId) {
    return emptyFail([
      { code: "mutation.wall_floor", message: "共墙两侧须同层" },
    ]);
  }
  const editable = listSharedWalls(ctx.placements, floorId);
  const match = editable.find(
    (w) =>
      w.axis === wallAxis &&
      new Set([w.room_a, w.room_b]).size === 2 &&
      new Set([w.room_a, w.room_b, roomId, partnerRoomId]).size === 2,
  );
  if (!match) {
    return emptyFail([
      {
        code: "mutation.wall_not_editable",
        message: "该共墙不可编辑（须恰好两房贴边且无 T 接）",
      },
    ]);
  }
  const plA = ctx.placements.find((p) => p.room_id === match.room_a)!;
  const plB = ctx.placements.find((p) => p.room_id === match.room_b)!;
  const coord = snapValue(wallCoord, module);
  const applied = applyWallCoord(rectOf(plA), rectOf(plB), wallAxis, coord);
  if ("error" in applied) {
    return emptyFail([
      {
        code: applied.error,
        message: `边长不可小于 ${HARD_MIN_EDGE} m`,
      },
    ]);
  }
  const ignore = new Set([match.room_a, match.room_b]);
  const reasons: MutationReject[] = [];
  const conflictRoomIds: string[] = [];
  for (const [sid, snapped] of [
    [match.room_a, applied.a] as const,
    [match.room_b, applied.b] as const,
  ]) {
    const geo = geometryCheck(sid, floorId, floorId, snapped, ctx, ignore);
    reasons.push(...geo.reasons);
    for (const c of geo.conflictRoomIds) {
      if (!conflictRoomIds.includes(c)) conflictRoomIds.push(c);
    }
  }
  const warnings: MutationReject[] = [];
  const seen = new Set<string>();
  for (const [sid, before, after] of [
    [match.room_a, rectOf(plA), applied.a] as const,
    [match.room_b, rectOf(plB), applied.b] as const,
  ]) {
    const partner = sid === match.room_a ? match.room_b : match.room_a;
    for (const w of accessImpactWarnings(
      sid,
      before,
      after,
      floorId,
      ctx.placements,
      MIN_ACCESS_WALL,
      new Set([partner]),
    )) {
      if (seen.has(w.message)) continue;
      seen.add(w.message);
      warnings.push(w);
    }
  }
  const snapped = roomId === match.room_a ? applied.a : applied.b;
  const snappedPartner = roomId === match.room_a ? applied.b : applied.a;
  return {
    ok: reasons.length === 0,
    reasons,
    warnings,
    snapped,
    snappedPartner,
    conflictRoomIds,
  };
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
    return emptyFail([
      { code: "mutation.unknown_room", message: `未知房间：${roomId}` },
    ]);
  }

  const snapped: PlacementRect = {
    x: snapValue(proposed.x, module),
    y: snapValue(proposed.y, module),
    width: proposed.width,
    depth: proposed.depth,
  };
  const { reasons, conflictRoomIds } = geometryCheck(
    roomId,
    floorId,
    current.floor_id,
    snapped,
    ctx,
  );
  const before = rectOf(current);
  const warnings = accessImpactWarnings(
    roomId,
    before,
    snapped,
    current.floor_id,
    ctx.placements,
  );
  return {
    ok: reasons.length === 0,
    reasons,
    warnings,
    snapped,
    snappedPartner: null,
    conflictRoomIds,
  };
}

/** RESIZE 预览：四边 snap + 最小边硬拒 + soft min_width/area / AccessImpact。 */
export function previewResize(
  roomId: string,
  proposed: PlacementRect,
  floorId: string,
  ctx: PreviewGeometryContext,
): MutationPreviewResult {
  const module = ctx.snapModule ?? 0.3;
  const current = ctx.placements.find((p) => p.room_id === roomId);
  if (!current) {
    return emptyFail([
      { code: "mutation.unknown_room", message: `未知房间：${roomId}` },
    ]);
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
  const geo = geometryCheck(roomId, floorId, current.floor_id, snapped, ctx);
  reasons.push(...geo.reasons);
  const before = rectOf(current);
  const warnings = [
    ...softSizeWarnings(roomId, snapped, ctx.roomHints),
    ...accessImpactWarnings(
      roomId,
      before,
      snapped,
      current.floor_id,
      ctx.placements,
    ),
  ];
  return {
    ok: reasons.length === 0,
    reasons,
    warnings,
    snapped,
    snappedPartner: null,
    conflictRoomIds: geo.conflictRoomIds,
  };
}

export function mutationRejectMessage(result: MutationPreviewResult): string {
  return result.reasons.map((r) => r.message).join("；") || "无法提交变更";
}

export function mutationWarningMessage(result: MutationPreviewResult): string | null {
  if (!result.warnings.length) return null;
  return result.warnings.map((r) => r.message).join("；");
}

export function mutationLiveMessage(result: MutationPreviewResult): string | null {
  if (!result.ok) return mutationRejectMessage(result);
  return mutationWarningMessage(result);
}

/** @deprecated 使用 PreviewGeometryContext */
export type PreviewMoveContext = PreviewGeometryContext;
