import { useEffect, useRef } from "react";
import type { RoomPlacementPayload } from "../api/client";

const FLOOR_GAP = 1.0;
const DEFAULT_SNAP = 0.3;
/** 屏幕像素：超过才算拖拽，避免误触取消 click */
const DRAG_THRESHOLD_PX = 4;

export type RoomMovePose = {
  x: number;
  y: number;
  floor_id: string;
  width: number;
  depth: number;
};

export type ProposeMoveResult = {
  ok: boolean;
  message?: string;
  snapped?: { x: number; y: number; width: number; depth: number } | null;
};

type Props = {
  svg: string | null;
  emptyHint: string;
  highlightRoomIds: string[];
  selectedRoomId: string | null;
  lockedRoomIds: string[];
  placements?: RoomPlacementPayload[];
  /** 与 SVG 堆叠顺序一致的楼层 id */
  floorIds?: string[];
  floorWidth?: number;
  floorDepth?: number;
  snapModule?: number;
  onSelectRoom: (roomId: string | null) => void;
  /** Geometry Mutation Authority：预览+提交；失败则 Snap Back */
  onProposeMove?: (roomId: string, pose: RoomMovePose) => ProposeMoveResult;
  mutationHint?: string | null;
};

type BasePose = {
  svgX: number;
  svgY: number;
  width: number;
  depth: number;
  floorId: string;
  floorIndex: number;
};

function snapValue(value: number, module: number): number {
  if (module <= 0) return value;
  return Math.round(value / module) * module;
}

function clamp(value: number, min: number, max: number): number {
  if (max < min) return min;
  return Math.min(max, Math.max(min, value));
}

function clientToSvg(
  svgEl: SVGSVGElement,
  clientX: number,
  clientY: number,
): { x: number; y: number } | null {
  const ctm = svgEl.getScreenCTM();
  if (!ctm) return null;
  const pt = svgEl.createSVGPoint();
  pt.x = clientX;
  pt.y = clientY;
  const local = pt.matrixTransform(ctm.inverse());
  return { x: local.x, y: local.y };
}

function floorOffset(floorIndex: number, floorDepth: number): number {
  return floorIndex * (floorDepth + FLOOR_GAP);
}

export function FloorplanView({
  svg,
  emptyHint,
  highlightRoomIds,
  selectedRoomId,
  lockedRoomIds,
  placements = [],
  floorIds = [],
  floorWidth = 0,
  floorDepth = 0,
  snapModule = DEFAULT_SNAP,
  onSelectRoom,
  onProposeMove,
  mutationHint = null,
}: Props) {
  const stageRef = useRef<HTMLDivElement>(null);
  const basesRef = useRef<Map<string, BasePose>>(new Map());
  const dragRef = useRef<{
    roomId: string;
    pointerId: number;
    startClientX: number;
    startClientY: number;
    originModelX: number;
    originModelY: number;
    width: number;
    depth: number;
    floorId: string;
    floorIndex: number;
    moved: boolean;
    /** 楼梯：同 core 的其它 room_id */
    siblingIds: string[];
  } | null>(null);

  const placementById = (id: string) =>
    placements.find((p) => p.room_id === id) ?? null;

  const floorIndexOf = (floorId: string, fallbackSvgY: number): number => {
    const idx = floorIds.indexOf(floorId);
    if (idx >= 0) return idx;
    if (floorDepth > 0) {
      return Math.max(0, Math.round(fallbackSvgY / (floorDepth + FLOOR_GAP)));
    }
    return 0;
  };

  const applyNodeTransform = (
    roomId: string,
    modelX: number,
    modelY: number,
  ) => {
    const root = stageRef.current;
    const base = basesRef.current.get(roomId);
    if (!root || !base) return;
    const node = root.querySelector<SVGGElement>(
      `g.room-node[data-room-id="${CSS.escape(roomId)}"]`,
    );
    if (!node) return;
    const oy = floorOffset(base.floorIndex, floorDepth);
    const dx = modelX - base.svgX;
    const dy = oy + modelY - base.svgY;
    node.setAttribute("transform", `translate(${dx} ${dy})`);
  };

  const syncFromPlacements = () => {
    const root = stageRef.current;
    if (!root || floorDepth <= 0) return;
    for (const [roomId, base] of basesRef.current) {
      const pl = placementById(roomId);
      if (!pl) {
        const node = root.querySelector<SVGGElement>(
          `g.room-node[data-room-id="${CSS.escape(roomId)}"]`,
        );
        node?.removeAttribute("transform");
        continue;
      }
      applyNodeTransform(roomId, pl.x, pl.y);
    }
  };

  const captureBases = () => {
    const root = stageRef.current;
    const map = new Map<string, BasePose>();
    if (!root) {
      basesRef.current = map;
      return;
    }
    root.querySelectorAll<SVGGElement>("g.room-node[data-room-id]").forEach((g) => {
      const id = g.getAttribute("data-room-id");
      if (!id) return;
      const rect = g.querySelector("rect.room-shape");
      if (!rect) return;
      const svgX = Number(rect.getAttribute("x") || 0);
      const svgY = Number(rect.getAttribute("y") || 0);
      const width = Number(rect.getAttribute("width") || 0);
      const depth = Number(rect.getAttribute("height") || 0);
      const pl = placementById(id);
      const floorId = pl?.floor_id ?? "";
      const floorIndex = floorIndexOf(floorId, svgY);
      map.set(id, { svgX, svgY, width, depth, floorId, floorIndex });
      g.removeAttribute("transform");
    });
    basesRef.current = map;
  };

  useEffect(() => {
    const root = stageRef.current;
    if (!root) return;
    const shapes = root.querySelectorAll<SVGElement>(".room-shape[data-room-id]");
    const want = new Set(highlightRoomIds);
    const locked = new Set(lockedRoomIds);
    shapes.forEach((el) => {
      const id = el.getAttribute("data-room-id");
      el.classList.toggle("is-hl", !!(id && want.has(id)));
      el.classList.toggle("is-selected", !!(id && id === selectedRoomId));
      el.classList.toggle("is-locked", !!(id && locked.has(id)));
      el.style.cursor = onProposeMove ? "grab" : "pointer";
    });
  }, [svg, highlightRoomIds, selectedRoomId, lockedRoomIds, onProposeMove]);

  // SVG 注入后记录基准位，再按 placements 对齐（拖拽预览的事实源）
  useEffect(() => {
    if (!svg) {
      basesRef.current = new Map();
      return;
    }
    captureBases();
    syncFromPlacements();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 仅在 svg 换批时重建基准
  }, [svg]);

  useEffect(() => {
    if (!svg || dragRef.current) return;
    syncFromPlacements();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [placements, floorDepth, floorIds, svg]);

  useEffect(() => {
    const root = stageRef.current;
    if (!root || !svg) return;

    function finishDrag(ev: PointerEvent, commit: boolean) {
      const drag = dragRef.current;
      if (!drag || drag.pointerId !== ev.pointerId) return;
      dragRef.current = null;
      const target = ev.currentTarget as HTMLElement;
      try {
        target.releasePointerCapture(ev.pointerId);
      } catch {
        /* already released */
      }
      root
        ?.querySelectorAll(".room-node.is-dragging")
        .forEach((el) => el.classList.remove("is-dragging"));

      if (!commit || !drag.moved) {
        syncFromPlacements();
        return;
      }

      const w = floorWidth > 0 ? floorWidth : Number.POSITIVE_INFINITY;
      const d = floorDepth > 0 ? floorDepth : Number.POSITIVE_INFINITY;
      let x = snapValue(drag.originModelX, snapModule);
      let y = snapValue(drag.originModelY, snapModule);
      // 用拖拽过程最后一次写入的 transform 反推；再从当前 pointer 算更稳
      const svgEl = root?.querySelector("svg");
      if (svgEl) {
        const pt = clientToSvg(svgEl, ev.clientX, ev.clientY);
        const startPt = clientToSvg(
          svgEl,
          drag.startClientX,
          drag.startClientY,
        );
        if (pt && startPt) {
          x = snapValue(
            drag.originModelX + (pt.x - startPt.x),
            snapModule,
          );
          y = snapValue(
            drag.originModelY + (pt.y - startPt.y),
            snapModule,
          );
        }
      }
      x = clamp(x, 0, Math.max(0, w - drag.width));
      y = clamp(y, 0, Math.max(0, d - drag.depth));

      const ids = [drag.roomId, ...drag.siblingIds];
      for (const id of ids) {
        applyNodeTransform(id, x, y);
      }

      const pose = {
        x,
        y,
        floor_id: drag.floorId,
        width: drag.width,
        depth: drag.depth,
      };
      const result = onProposeMove?.(drag.roomId, pose);
      if (!result?.ok) {
        syncFromPlacements();
        return;
      }
      if (result.snapped) {
        const s = result.snapped;
        for (const id of ids) {
          applyNodeTransform(id, s.x, s.y);
        }
      }
    }

    function onPointerDown(ev: PointerEvent) {
      if (ev.button !== 0) return;
      const t = ev.target as Element | null;
      if (!t) return;
      const shape = t.closest(".room-shape[data-room-id]");
      if (!shape) {
        onSelectRoom(null);
        return;
      }
      const roomId = shape.getAttribute("data-room-id");
      if (!roomId) return;
      onSelectRoom(roomId);

      if (!onProposeMove || floorDepth <= 0) return;

      const pl = placementById(roomId);
      const base = basesRef.current.get(roomId);
      if (!pl || !base) return;

      const isStair = roomId.startsWith("stair-");
      const siblingIds = isStair
        ? placements
            .filter(
              (p) => p.room_id.startsWith("stair-") && p.room_id !== roomId,
            )
            .map((p) => p.room_id)
        : [];

      dragRef.current = {
        roomId,
        pointerId: ev.pointerId,
        startClientX: ev.clientX,
        startClientY: ev.clientY,
        originModelX: pl.x,
        originModelY: pl.y,
        width: pl.width,
        depth: pl.depth,
        floorId: pl.floor_id,
        floorIndex: base.floorIndex,
        moved: false,
        siblingIds,
      };
      (ev.currentTarget as HTMLElement).setPointerCapture(ev.pointerId);
      ev.preventDefault();
    }

    function onPointerMove(ev: PointerEvent) {
      const drag = dragRef.current;
      if (!drag || drag.pointerId !== ev.pointerId) return;
      const dist = Math.hypot(
        ev.clientX - drag.startClientX,
        ev.clientY - drag.startClientY,
      );
      if (!drag.moved && dist < DRAG_THRESHOLD_PX) return;
      drag.moved = true;

      const svgEl = root.querySelector("svg");
      if (!svgEl) return;
      const pt = clientToSvg(svgEl, ev.clientX, ev.clientY);
      const startPt = clientToSvg(
        svgEl,
        drag.startClientX,
        drag.startClientY,
      );
      if (!pt || !startPt) return;

      const w = floorWidth > 0 ? floorWidth : Number.POSITIVE_INFINITY;
      const d = floorDepth > 0 ? floorDepth : Number.POSITIVE_INFINITY;
      let x = drag.originModelX + (pt.x - startPt.x);
      let y = drag.originModelY + (pt.y - startPt.y);
      x = clamp(x, 0, Math.max(0, w - drag.width));
      y = clamp(y, 0, Math.max(0, d - drag.depth));

      const ids = [drag.roomId, ...drag.siblingIds];
      for (const id of ids) {
        const node = root.querySelector(
          `g.room-node[data-room-id="${CSS.escape(id)}"]`,
        );
        node?.classList.add("is-dragging");
        applyNodeTransform(id, x, y);
      }
    }

    function onPointerUp(ev: PointerEvent) {
      finishDrag(ev, true);
    }

    function onPointerCancel(ev: PointerEvent) {
      finishDrag(ev, false);
    }

    root.addEventListener("pointerdown", onPointerDown);
    root.addEventListener("pointermove", onPointerMove);
    root.addEventListener("pointerup", onPointerUp);
    root.addEventListener("pointercancel", onPointerCancel);
    return () => {
      root.removeEventListener("pointerdown", onPointerDown);
      root.removeEventListener("pointermove", onPointerMove);
      root.removeEventListener("pointerup", onPointerUp);
      root.removeEventListener("pointercancel", onPointerCancel);
    };
  }, [
    svg,
    placements,
    floorWidth,
    floorDepth,
    floorIds,
    snapModule,
    onSelectRoom,
    onProposeMove,
  ]);

  const canDrag = !!onProposeMove && floorDepth > 0;

  return (
    <main className="panel panel-center">
      <header className="panel-head compact">
        <h2>Floorplan</h2>
        {mutationHint ? (
          <p className="muted warn-hint">{mutationHint}</p>
        ) : selectedRoomId ? (
          <p className="muted">
            {canDrag
              ? "受控拖拽 · Authority 校验 · 非法回弹"
              : "已选 · 可锁定后 Regenerate unlocked"}
          </p>
        ) : lockedRoomIds.length > 0 ? (
          <p className="muted">已锁 {lockedRoomIds.length} 处</p>
        ) : (
          <p className="muted">
            {canDrag ? "点击或拖拽房间 / 楼梯" : "点击房间或楼梯"}
          </p>
        )}
      </header>
      <div className="floorplan-stage">
        {svg ? (
          <div
            ref={stageRef}
            className="floorplan-svg"
            dangerouslySetInnerHTML={{ __html: svg }}
          />
        ) : (
          <p className="empty-hint">{emptyHint}</p>
        )}
      </div>
    </main>
  );
}
