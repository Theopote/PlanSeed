type Props = {
  svg: string | null;
  emptyHint: string;
};

export function FloorplanView({ svg, emptyHint }: Props) {
  return (
    <main className="panel panel-center">
      <header className="panel-head compact">
        <h2>Floorplan</h2>
      </header>
      <div className="floorplan-stage">
        {svg ? (
          <div
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
