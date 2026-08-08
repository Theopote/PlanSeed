import { useEffect, useRef } from "react";

type Props = {
  svg: string | null;
  emptyHint: string;
  highlightRoomIds: string[];
};

export function FloorplanView({ svg, emptyHint, highlightRoomIds }: Props) {
  const stageRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = stageRef.current;
    if (!root) return;
    const shapes = root.querySelectorAll<SVGElement>(".room-shape[data-room-id]");
    const want = new Set(highlightRoomIds);
    shapes.forEach((el) => {
      const id = el.getAttribute("data-room-id");
      if (id && want.has(id)) {
        el.classList.add("is-hl");
      } else {
        el.classList.remove("is-hl");
      }
    });
  }, [svg, highlightRoomIds]);

  return (
    <main className="panel panel-center">
      <header className="panel-head compact">
        <h2>Floorplan</h2>
        {highlightRoomIds.length > 0 && (
          <p className="muted">高亮 {highlightRoomIds.length} 个房间</p>
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
