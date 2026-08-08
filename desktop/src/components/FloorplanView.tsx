import { useEffect, useRef, useState } from "react";
import type { RoomPlacementPayload } from "../api/client";
import { HARD_MIN_EDGE } from "../lib/geometryMutation";

const FLOOR_GAP = 1.0;
const DEFAULT_SNAP = 0.3;
/** 屏幕像素：超过才算拖拽，避免误触取消 click */
const DRAG_THRESHOLD_PX = 4;
const HANDLE_R = 0.18;

export type RoomMovePose = {
  x: number;
  y: number;
  floor_id: string;
  width: number;
  depth: number;
};

export type MutationDragKind = "move" | "resize";

export type ProposeMoveResult = {
  ok: boolean;
  message?: string;
  warning?: string | null;
  snapped?: { x: number; y: number; width: number; depth: number } | null;
  conflictRoomIds?: string[];
};

export type LivePreviewResult = {
  ok: boolean;
  message?: string | null;
  snapped?: { x: number; y: number; width: number; depth: number } | null;
  conflictRoomIds?: string[];
};

type ResizeEdge = "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";

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
  onProposeMove?: (
    roomId: string,
    pose: RoomMovePose,
    kind?: MutationDragKind,
  ) => ProposeMoveResult;
  /** 拖动中实时预览（虚线 / 冲突 / AccessImpact） */
  onLivePreview?: (
    roomId: string,
    pose: RoomMovePose,
    kind: MutationDragKind,
  ) => LivePreviewResult;
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

type DragState = {
  kind: MutationDragKind;
  edge: ResizeEdge | null;
  roomId: string;
  pointerId: number;
  startClientX: number;
  startClientY: number;
  originModelX: number;
  originModelY: number;
  originWidth: number;
  originDepth: number;
  floorId: string;
  floorIndex: number;
  moved: boolean;
  siblingIds: string[];
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

function resizeFromDelta(
  edge: ResizeEdge,
  ox: number,
  oy: number,
  ow: number,
  od: number,
  dx: number,
  dy: number,
  floorW: number,
  floorD: number,
): { x: number; y: number; width: number; depth: number } {
  let x = ox;
  let y = oy;
  let w = ow;
  let d = od;
  const moveE = edge.includes("e");
  const moveW = edge.includes("w");
  const moveS = edge.includes("s");
  const moveN = edge.includes("n");

  if (moveE) w = ow + dx;
  if (moveW) {
    x = ox + dx;
    w = ow - dx;
  }
  if (moveS) d = od + dy;
  if (moveN) {
    y = oy + dy;
    d = od - dy;
  }

  // 硬最小边：拖拽预览也钳制，避免负宽
  if (w < HARD_MIN_EDGE) {
    if (moveW) x = ox + ow - HARD_MIN_EDGE;
    w = HARD_MIN_EDGE;
  }
  if (d < HARD_MIN_EDGE) {
    if (moveN) y = oy + od - HARD_MIN_EDGE;
    d = HARD_MIN_EDGE;
  }

  x = clamp(x, 0, Math.max(0, floorW - w));
  y = clamp(y, 0, Math.max(0, floorD - d));
  w = clamp(w, HARD_MIN_EDGE, Math.max(HARD_MIN_EDGE, floorW - x));
  d = clamp(d, HARD_MIN_EDGE, Math.max(HARD_MIN_EDGE, floorD - y));
  return { x, y, width: w, depth: d };
}

const EDGE_CURSOR: Record<ResizeEdge, string> = {
  n: "ns-resize",
  s: "ns-resize",
  e: "ew-resize",
  w: "ew-resize",
  ne: "nesw-resize",
  sw: "nesw-resize",
  nw: "nwse-resize",
  se: "nwse-resize",
};

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
  onLivePreview,
  mutationHint = null,
}: Props) {
  const stageRef = useRef<HTMLDivElement>(null);
  const basesRef = useRef<Map<string, BasePose>>(new Map());
  const dragRef = useRef<DragState | null>(null);
  const [liveHint, setLiveHint] = useState<string | null>(null);
  const [liveConflict, setLiveConflict] = useState(false);

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

  const applyNodeGeometry = (
    roomId: string,
    modelX: number,
    modelY: number,
    width: number,
    depth: number,
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

    const rect = node.querySelector("rect.room-shape");
    if (rect) {
      rect.setAttribute("width", String(width));
      rect.setAttribute("height", String(depth));
    }
    const cx = base.svgX + width / 2;
    const cy = base.svgY + depth / 2;
    const texts = node.querySelectorAll("text");
    const showDetail = width >= 1.4 && depth >= 1.2;
    texts.forEach((t, i) => {
      t.setAttribute("x", String(cx));
      if (!showDetail) {
        t.setAttribute("y", String(cy));
        return;
      }
      if (i === 0) t.setAttribute("y", String(cy - 0.28));
      else if (i === 1) t.setAttribute("y", String(cy));
      else t.setAttribute("y", String(cy + 0.28));
    });
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
      applyNodeGeometry(roomId, pl.x, pl.y, pl.width, pl.depth);
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

  const syncHandles = () => {
    const root = stageRef.current;
    if (!root) return;
    const svgEl = root.querySelector("svg");
    if (!svgEl) return;
    let layer = svgEl.querySelector<SVGGElement>("g.mutation-handles");
    if (!layer) {
      layer = document.createElementNS("http://www.w3.org/2000/svg", "g");
      layer.setAttribute("class", "mutation-handles");
      svgEl.appendChild(layer);
    }
    layer.replaceChildren();
    if (!selectedRoomId || !onProposeMove || floorDepth <= 0) return;
    if (selectedRoomId.startsWith("stair-")) return;

    const pl = placementById(selectedRoomId);
    const base = basesRef.current.get(selectedRoomId);
    if (!pl || !base) return;
    const oy = floorOffset(base.floorIndex, floorDepth);
    const x0 = pl.x;
    const y0 = oy + pl.y;
    const x1 = pl.x + pl.width;
    const y1 = oy + pl.y + pl.depth;
    const midX = (x0 + x1) / 2;
    const midY = (y0 + y1) / 2;
    const points: Array<{ edge: ResizeEdge; x: number; y: number }> = [
      { edge: "nw", x: x0, y: y0 },
      { edge: "n", x: midX, y: y0 },
      { edge: "ne", x: x1, y: y0 },
      { edge: "e", x: x1, y: midY },
      { edge: "se", x: x1, y: y1 },
      { edge: "s", x: midX, y: y1 },
      { edge: "sw", x: x0, y: y1 },
      { edge: "w", x: x0, y: midY },
    ];
    for (const p of points) {
      const c = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      c.setAttribute("class", "resize-handle");
      c.setAttribute("data-edge", p.edge);
      c.setAttribute("data-room-id", selectedRoomId);
      c.setAttribute("cx", String(p.x));
      c.setAttribute("cy", String(p.y));
      c.setAttribute("r", String(HANDLE_R));
      c.style.cursor = EDGE_CURSOR[p.edge];
      layer.appendChild(c);
    }
  };

  const clearLiveFeedback = () => {
    setLiveHint(null);
    setLiveConflict(false);
    const root = stageRef.current;
    if (!root) return;
    root
      .querySelectorAll(".room-shape.is-conflict")
      .forEach((el) => el.classList.remove("is-conflict"));
    const svgEl = root.querySelector("svg");
    const layer = svgEl?.querySelector("g.mutation-preview");
    layer?.replaceChildren();
  };

  const syncPreviewOverlay = (
    floorIndex: number,
    snapped: { x: number; y: number; width: number; depth: number } | null,
    ok: boolean,
    hasWarning: boolean,
    conflictIds: string[],
  ) => {
    const root = stageRef.current;
    if (!root) return;
    const svgEl = root.querySelector("svg");
    if (!svgEl) return;
    let layer = svgEl.querySelector<SVGGElement>("g.mutation-preview");
    if (!layer) {
      layer = document.createElementNS("http://www.w3.org/2000/svg", "g");
      layer.setAttribute("class", "mutation-preview");
      svgEl.appendChild(layer);
    }
    layer.replaceChildren();
    root
      .querySelectorAll(".room-shape.is-conflict")
      .forEach((el) => el.classList.remove("is-conflict"));
    for (const id of conflictIds) {
      if (id === "__stair__") {
        root
          .querySelectorAll('.room-shape[data-room-id^="stair-"]')
          .forEach((el) => el.classList.add("is-conflict"));
        continue;
      }
      root
        .querySelector(`.room-shape[data-room-id="${CSS.escape(id)}"]`)
        ?.classList.add("is-conflict");
    }
    if (!snapped) return;
    const oy = floorOffset(floorIndex, floorDepth);
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("class", "proposed-rect");
    rect.classList.toggle("is-invalid", !ok);
    rect.classList.toggle("is-warn", ok && hasWarning);
    rect.setAttribute("x", String(snapped.x));
    rect.setAttribute("y", String(oy + snapped.y));
    rect.setAttribute("width", String(snapped.width));
    rect.setAttribute("height", String(snapped.depth));
    rect.setAttribute("fill", "none");
    layer.appendChild(rect);
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

  useEffect(() => {
    if (!svg) {
      basesRef.current = new Map();
      return;
    }
    captureBases();
    syncFromPlacements();
    syncHandles();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 仅在 svg 换批时重建基准
  }, [svg]);

  useEffect(() => {
    if (!svg || dragRef.current) return;
    syncFromPlacements();
    syncHandles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [placements, floorDepth, floorIds, svg, selectedRoomId, onProposeMove]);

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
        syncHandles();
        clearLiveFeedback();
        return;
      }

      const fw = floorWidth > 0 ? floorWidth : Number.POSITIVE_INFINITY;
      const fd = floorDepth > 0 ? floorDepth : Number.POSITIVE_INFINITY;
      const svgEl = root?.querySelector("svg");
      let pose = {
        x: drag.originModelX,
        y: drag.originModelY,
        width: drag.originWidth,
        depth: drag.originDepth,
        floor_id: drag.floorId,
      };

      if (svgEl) {
        const pt = clientToSvg(svgEl, ev.clientX, ev.clientY);
        const startPt = clientToSvg(
          svgEl,
          drag.startClientX,
          drag.startClientY,
        );
        if (pt && startPt) {
          const dx = pt.x - startPt.x;
          const dy = pt.y - startPt.y;
          if (drag.kind === "resize" && drag.edge) {
            const r = resizeFromDelta(
              drag.edge,
              drag.originModelX,
              drag.originModelY,
              drag.originWidth,
              drag.originDepth,
              dx,
              dy,
              fw,
              fd,
            );
            pose = { ...r, floor_id: drag.floorId };
          } else {
            let x = snapValue(drag.originModelX + dx, snapModule);
            let y = snapValue(drag.originModelY + dy, snapModule);
            x = clamp(x, 0, Math.max(0, fw - drag.originWidth));
            y = clamp(y, 0, Math.max(0, fd - drag.originDepth));
            pose = {
              x,
              y,
              width: drag.originWidth,
              depth: drag.originDepth,
              floor_id: drag.floorId,
            };
          }
        }
      }

      const ids = [drag.roomId, ...drag.siblingIds];
      for (const id of ids) {
        applyNodeGeometry(id, pose.x, pose.y, pose.width, pose.depth);
      }

      const result = onProposeMove?.(drag.roomId, pose, drag.kind);
      clearLiveFeedback();
      if (!result?.ok) {
        syncFromPlacements();
        syncHandles();
        return;
      }
      if (result.snapped) {
        const s = result.snapped;
        for (const id of ids) {
          applyNodeGeometry(id, s.x, s.y, s.width, s.depth);
        }
      }
      syncHandles();
    }

    function onPointerDown(ev: PointerEvent) {
      if (ev.button !== 0) return;
      const t = ev.target as Element | null;
      if (!t) return;

      const handle = t.closest(".resize-handle[data-edge]");
      if (handle && onProposeMove && floorDepth > 0) {
        const roomId = handle.getAttribute("data-room-id");
        const edge = handle.getAttribute("data-edge") as ResizeEdge | null;
        if (!roomId || !edge) return;
        const pl = placementById(roomId);
        const base = basesRef.current.get(roomId);
        if (!pl || !base) return;
        onSelectRoom(roomId);
        dragRef.current = {
          kind: "resize",
          edge,
          roomId,
          pointerId: ev.pointerId,
          startClientX: ev.clientX,
          startClientY: ev.clientY,
          originModelX: pl.x,
          originModelY: pl.y,
          originWidth: pl.width,
          originDepth: pl.depth,
          floorId: pl.floor_id,
          floorIndex: base.floorIndex,
          moved: false,
          siblingIds: [],
        };
        (ev.currentTarget as HTMLElement).setPointerCapture(ev.pointerId);
        ev.preventDefault();
        ev.stopPropagation();
        return;
      }

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
        kind: "move",
        edge: null,
        roomId,
        pointerId: ev.pointerId,
        startClientX: ev.clientX,
        startClientY: ev.clientY,
        originModelX: pl.x,
        originModelY: pl.y,
        originWidth: pl.width,
        originDepth: pl.depth,
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

      const fw = floorWidth > 0 ? floorWidth : Number.POSITIVE_INFINITY;
      const fd = floorDepth > 0 ? floorDepth : Number.POSITIVE_INFINITY;
      const dx = pt.x - startPt.x;
      const dy = pt.y - startPt.y;

      let x = drag.originModelX;
      let y = drag.originModelY;
      let w = drag.originWidth;
      let d = drag.originDepth;

      if (drag.kind === "resize" && drag.edge) {
        const r = resizeFromDelta(
          drag.edge,
          drag.originModelX,
          drag.originModelY,
          drag.originWidth,
          drag.originDepth,
          dx,
          dy,
          fw,
          fd,
        );
        x = r.x;
        y = r.y;
        w = r.width;
        d = r.depth;
      } else {
        x = clamp(
          drag.originModelX + dx,
          0,
          Math.max(0, fw - drag.originWidth),
        );
        y = clamp(
          drag.originModelY + dy,
          0,
          Math.max(0, fd - drag.originDepth),
        );
      }

      const ids = [drag.roomId, ...drag.siblingIds];
      for (const id of ids) {
        const node = root.querySelector(
          `g.room-node[data-room-id="${CSS.escape(id)}"]`,
        );
        node?.classList.add("is-dragging");
        applyNodeGeometry(id, x, y, w, d);
      }

      const live = onLivePreview?.(
        drag.roomId,
        { x, y, width: w, depth: d, floor_id: drag.floorId },
        drag.kind,
      );
      if (live) {
        const msg = live.message ?? null;
        setLiveHint(msg);
        setLiveConflict(!live.ok);
        syncPreviewOverlay(
          drag.floorIndex,
          live.snapped ?? { x, y, width: w, depth: d },
          live.ok,
          !!(live.ok && msg),
          live.conflictRoomIds ?? [],
        );
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
    onLivePreview,
  ]);

  const canEdit = !!onProposeMove && floorDepth > 0;
  const headerHint = liveHint ?? mutationHint;

  return (
    <main className="panel panel-center">
      <header className="panel-head compact">
        <h2>Floorplan</h2>
        {headerHint ? (
          <p
            className={
              liveConflict
                ? "muted warn-hint is-live-bad"
                : liveHint
                  ? "muted warn-hint is-live-warn"
                  : "muted warn-hint"
            }
          >
            {headerHint}
          </p>
        ) : selectedRoomId ? (
          <p className="muted">
            {canEdit
              ? selectedRoomId.startsWith("stair-")
                ? "受控平移楼梯 · 手柄缩放仅房间"
                : "拖移房间 · 手柄缩放 · 拖动中预览冲突"
              : "已选 · 可锁定后 Regenerate unlocked"}
          </p>
        ) : lockedRoomIds.length > 0 ? (
          <p className="muted">已锁 {lockedRoomIds.length} 处</p>
        ) : (
          <p className="muted">
            {canEdit ? "点击选中 · 拖移或拉手柄" : "点击房间或楼梯"}
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
