import { useEffect, useRef } from "react";

type Props = {
  svg: string | null;
  emptyHint: string;
  highlightRoomIds: string[];
  selectedRoomId: string | null;
  lockedRoomIds: string[];
  onSelectRoom: (roomId: string | null) => void;
};

export function FloorplanView({
  svg,
  emptyHint,
  highlightRoomIds,
  selectedRoomId,
  lockedRoomIds,
  onSelectRoom,
}: Props) {
  const stageRef = useRef<HTMLDivElement>(null);

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
      el.style.cursor = "pointer";
    });
  }, [svg, highlightRoomIds, selectedRoomId, lockedRoomIds]);

  useEffect(() => {
    const root = stageRef.current;
    if (!root || !svg) return;

    function onClick(ev: MouseEvent) {
      const t = ev.target as Element | null;
      if (!t) return;
      const shape = t.closest(".room-shape[data-room-id]");
      if (!shape) {
        onSelectRoom(null);
        return;
      }
      const id = shape.getAttribute("data-room-id");
      if (!id) return;
      onSelectRoom(id);
    }

    root.addEventListener("click", onClick);
    return () => root.removeEventListener("click", onClick);
  }, [svg, onSelectRoom]);

  return (
    <main className="panel panel-center">
      <header className="panel-head compact">
        <h2>Floorplan</h2>
        {selectedRoomId ? (
          <p className="muted">已选 · 可锁定后 Regenerate unlocked</p>
        ) : lockedRoomIds.length > 0 ? (
          <p className="muted">已锁 {lockedRoomIds.length} 处</p>
        ) : (
          <p className="muted">点击房间或楼梯</p>
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
