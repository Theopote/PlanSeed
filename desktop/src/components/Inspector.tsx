import { useEffect, useState, type FormEvent } from "react";
import type {
  CandidatePayload,
  DesignFinding,
  LayoutLocks,
  ProgramSummary,
  RoomPlacementPayload,
  ZonePlacementPayload,
} from "../api/client";
import { AXIS_SCOPE } from "../lib/axisScope";
import { ComparePanel } from "./ComparePanel";

function uniqueZones(zones: ZonePlacementPayload[]): ZonePlacementPayload[] {
  const seen = new Set<string>();
  const out: ZonePlacementPayload[] = [];
  for (const z of zones) {
    const key = `${z.floor_id}:${z.zone}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(z);
  }
  return out;
}

type Props = {
  candidate: CandidatePayload | null;
  compareWith: CandidatePayload | null;
  program: ProgramSummary | null;
  selectedRoomId: string | null;
  highlightRoomIds: string[];
  locks: LayoutLocks;
  lockCount: number;
  onHighlightRooms: (roomIds: string[]) => void;
  onSelectRoom: (roomId: string | null) => void;
  onSelectZone: (zone: string, floorId: string) => void;
  onClearCompare: () => void;
  onUpdateRoomTargetArea: (roomId: string, targetArea: number) => void;
  onToggleRoomLock: (roomId: string) => void;
  onToggleZoneLock: (zone: string, floorId: string) => void;
  onClearLocks: () => void;
  onRegenerate: () => void;
  onCreateVariant: () => void;
  regenerating: boolean;
  canRegenerate: boolean;
};

const ZONE_LABEL: Record<string, string> = {
  day: "日间 / Day",
  night: "夜间 / Night",
  service: "服务 / Service",
  circulation: "交通",
};

const SCORE_ROWS: Array<{
  key: keyof NonNullable<CandidatePayload["design_score"]>;
  label: string;
  hint: string;
}> = [
  { key: "program_score", label: "Program", hint: "空间清单 / 面积 / 邻接" },
  { key: "spatial_score", label: "Spatial", hint: "比例 / 紧凑 / 形状" },
  { key: "circulation_score", label: "Circulation", hint: "可达 / 深度 / 穿堂" },
  { key: "privacy_score", label: "Privacy", hint: "动静 / 过渡 / 穿卧" },
  {
    key: "environment_score",
    label: AXIS_SCOPE.environment.label,
    hint: AXIS_SCOPE.environment.hint,
  },
  {
    key: "technical_score",
    label: AXIS_SCOPE.technical.label,
    hint: AXIS_SCOPE.technical.hint,
  },
  { key: "robustness_score", label: "Robustness", hint: "repair / 稳定性" },
];

const SEV_ORDER = ["problem", "warning", "positive", "info"] as const;

const SEV_LABEL: Record<string, string> = {
  problem: "问题",
  warning: "注意",
  positive: "优势",
  info: "说明",
};

const CATEGORY_ZH: Record<string, string> = {
  program: "空间程序",
  spatial: "空间形态",
  circulation: "交通流线",
  privacy: "私密分区",
  environment: AXIS_SCOPE.environment.categoryZh,
  technical: AXIS_SCOPE.technical.categoryZh,
  robustness: "稳健性",
};

function groupFindings(findings: DesignFinding[]) {
  const groups: Record<string, DesignFinding[]> = {
    problem: [],
    warning: [],
    positive: [],
    info: [],
  };
  for (const f of findings) {
    const k = f.severity in groups ? f.severity : "info";
    groups[k].push(f);
  }
  return groups;
}

function roomLabel(program: ProgramSummary | null, id: string): string {
  const name = program?.rooms.find((r) => r.id === id)?.name;
  return name || id;
}

function sameIds(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  const sa = [...a].sort().join("\0");
  const sb = [...b].sort().join("\0");
  return sa === sb;
}

function formatMeasured(metric: string | null, value: number | null): string | null {
  if (metric == null && value == null) return null;
  if (metric != null && value != null) {
    return `${metric} = ${Number.isInteger(value) ? value : value.toFixed(2)}`;
  }
  if (metric != null) return metric;
  return String(value);
}

function RoomDetail({
  program,
  placement,
  roomId,
  isLocked,
  onUpdateTargetArea,
  onToggleLock,
  onClear,
}: {
  program: ProgramSummary | null;
  placement: RoomPlacementPayload | null;
  roomId: string;
  isLocked: boolean;
  onUpdateTargetArea: (roomId: string, targetArea: number) => void;
  onToggleLock: (roomId: string) => void;
  onClear: () => void;
}) {
  const isStair = roomId.startsWith("stair-");
  const spec = program?.rooms.find((r) => r.id === roomId);
  const title = isStair ? "楼梯核" : (spec?.name ?? roomId);
  const [draft, setDraft] = useState(String(spec?.target_area ?? ""));

  useEffect(() => {
    setDraft(String(spec?.target_area ?? ""));
  }, [roomId, spec?.target_area]);

  function submitArea(e: FormEvent) {
    e.preventDefault();
    if (isStair) return;
    const n = Number(draft);
    if (!Number.isFinite(n) || n <= 0) return;
    onUpdateTargetArea(roomId, n);
  }

  return (
    <section className="room-detail">
      <div className="room-detail-head">
        <h3>
          {title}
          {isLocked ? " · 已锁" : ""}
        </h3>
        <button type="button" className="btn-ghost" onClick={onClear}>
          清除
        </button>
      </div>

      {!isStair && spec && (
        <>
          <h4>RoomSpec</h4>
          <ul className="room-meta">
            <li>
              <span>id</span>
              <code>{spec.id}</code>
            </li>
            <li>
              <span>category</span>
              <span>{spec.category}</span>
            </li>
            <li>
              <span>floor</span>
              <span>{spec.floor_id ?? "—"}</span>
            </li>
          </ul>

          <form className="room-area-form" onSubmit={submitArea}>
            <label>
              target area (㎡)
              <input
                type="number"
                min={1}
                max={200}
                step={0.5}
                value={draft}
                disabled={isLocked}
                onChange={(e) => setDraft(e.target.value)}
              />
            </label>
            <button type="submit" className="secondary" disabled={isLocked}>
              应用面积
            </button>
          </form>
        </>
      )}

      {isStair && (
        <p className="muted tiny">锁定楼梯核后，重生成保持核位与尺寸不变</p>
      )}

      <h4>Placement</h4>
      {placement ? (
        <ul className="room-meta">
          <li>
            <span>floor</span>
            <span>{placement.floor_id}</span>
          </li>
          <li>
            <span>x, y</span>
            <span>
              {placement.x.toFixed(2)}, {placement.y.toFixed(2)}
            </span>
          </li>
          <li>
            <span>w × d</span>
            <span>
              {placement.width.toFixed(2)} × {placement.depth.toFixed(2)} m
            </span>
          </li>
          <li>
            <span>area</span>
            <span>{placement.area.toFixed(1)} ㎡</span>
          </li>
        </ul>
      ) : (
        <p className="muted tiny">当前候选无此放置</p>
      )}

      <div className="room-lock-actions">
        <button
          type="button"
          className="secondary"
          disabled={!placement}
          onClick={() => onToggleLock(roomId)}
        >
          {isLocked ? "解锁" : isStair ? "锁定楼梯" : "锁定房间"}
        </button>
      </div>
      <p className="muted tiny">
        {isLocked
          ? "已锁定几何；拖拽可改位置，Create Variant 会保留钉死位置"
          : "可拖拽定位（松手自动锁定），或点锁定后 Regenerate"}
      </p>
    </section>
  );
}

export function Inspector({
  candidate,
  compareWith,
  program,
  selectedRoomId,
  highlightRoomIds,
  locks,
  lockCount,
  onHighlightRooms,
  onSelectRoom,
  onSelectZone,
  onClearCompare,
  onUpdateRoomTargetArea,
  onToggleRoomLock,
  onToggleZoneLock,
  onClearLocks,
  onRegenerate,
  onCreateVariant,
  regenerating,
  canRegenerate,
}: Props) {
  if (candidate && compareWith && candidate.id !== compareWith.id) {
    return (
      <aside className="panel panel-right">
        <header className="panel-head compact">
          <h2>Inspector</h2>
          <p className="muted">方案比较</p>
        </header>
        <ComparePanel a={candidate} b={compareWith} onClear={onClearCompare} />
      </aside>
    );
  }

  const ds = candidate?.design_score ?? null;
  const hard = candidate?.validation?.hard_violations ?? [];
  const soft = candidate?.validation?.soft_violations ?? [];
  const findings = ds?.findings ?? [];
  const groups = groupFindings(findings);
  const placement =
    selectedRoomId && candidate
      ? (candidate.placements?.find((p) => p.room_id === selectedRoomId) ?? null)
      : null;
  const selectedLocked = selectedRoomId
    ? selectedRoomId.startsWith("stair-")
      ? !!locks.stair
      : locks.rooms.some((r) => r.room_id === selectedRoomId)
    : false;

  function toggleFinding(f: DesignFinding) {
    if (!f.room_ids.length) {
      onHighlightRooms([]);
      return;
    }
    if (sameIds(highlightRoomIds, f.room_ids)) {
      onHighlightRooms([]);
    } else {
      onHighlightRooms(f.room_ids);
      if (f.room_ids[0]) onSelectRoom(f.room_ids[0]);
    }
  }

  return (
    <aside className="panel panel-right">
      <header className="panel-head compact">
        <h2>Inspector</h2>
        {candidate && (
          <p className="muted">
            {candidate.label} · seed {candidate.seed}
            {candidate.score != null ? ` · ${candidate.score.toFixed(1)}` : ""}
            {lockCount > 0 ? ` · 锁 ${lockCount}` : ""}
          </p>
        )}
      </header>

      {!candidate && (
        <p className="empty-hint">
          选择下方候选；锁定后可 Regenerate / Create Variant；Alt+点击比较
        </p>
      )}

      {candidate && (
        <div className="inspector-body">
          {lockCount > 0 && (
            <p className="lock-banner">
              已锁 {lockCount} 处
              <button type="button" className="btn-ghost" onClick={onClearLocks}>
                全部解锁
              </button>
            </p>
          )}

          <div className="session-actions">
            <button
              type="button"
              className="room-regen"
              disabled={!canRegenerate || regenerating}
              onClick={onRegenerate}
            >
              {regenerating
                ? "生成中…"
                : lockCount > 0
                  ? "Regenerate unlocked"
                  : "Regenerate"}
            </button>
            <button
              type="button"
              className="secondary"
              disabled={!canRegenerate || regenerating}
              onClick={onCreateVariant}
            >
              Create Variant
            </button>
            <p className="muted tiny">
              Regenerate 替换条带；Variant 追加并自动进入比较
            </p>
          </div>

          {(candidate.zones?.length ?? 0) > 0 && (
            <section className="zone-list">
              <h3>Zones</h3>
              <p className="muted tiny">
                锁分区 = 钉死 envelope；区内房间仍可重排
              </p>
              <ul className="zone-rows">
                {uniqueZones(candidate.zones ?? []).map((z) => {
                  const locked = locks.zones.some(
                    (lz) =>
                      lz.zone === z.zone && lz.floor_id === z.floor_id,
                  );
                  return (
                    <li key={`${z.floor_id}:${z.zone}`}>
                      <button
                        type="button"
                        className="zone-pick"
                        onClick={() => onSelectZone(z.zone, z.floor_id)}
                      >
                        <span>
                          {ZONE_LABEL[z.zone] ?? z.zone} · {z.floor_id}
                        </span>
                        <span className="muted tiny">
                          {z.width.toFixed(1)}×{z.depth.toFixed(1)} ·{" "}
                          {z.room_ids.length} 房
                        </span>
                      </button>
                      <button
                        type="button"
                        className="secondary zone-lock-btn"
                        onClick={() =>
                          onToggleZoneLock(z.zone, z.floor_id)
                        }
                      >
                        {locked ? "解锁区" : "锁定区"}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
          )}

          {selectedRoomId && (
            <RoomDetail
              program={program}
              placement={placement}
              roomId={selectedRoomId}
              isLocked={selectedLocked}
              onUpdateTargetArea={onUpdateRoomTargetArea}
              onToggleLock={onToggleRoomLock}
              onClear={() => onSelectRoom(null)}
            />
          )}

          {ds && (
            <>
              <div className="total-score">
                <span>Total</span>
                <strong>{ds.total_score.toFixed(1)}</strong>
              </div>
              <ul className="score-rows">
                {SCORE_ROWS.map(({ key, label, hint }) => {
                  const v = ds[key];
                  if (typeof v !== "number") return null;
                  return (
                    <li key={key} title={hint}>
                      <span>
                        {label}
                        <span className="axis-hint"> {hint}</span>
                      </span>
                      <span>{v.toFixed(1)}</span>
                    </li>
                  );
                })}
              </ul>

              {SEV_ORDER.map((sev) => {
                const list = groups[sev];
                if (!list.length) return null;
                return (
                  <section key={sev} className={`finding-block sev-${sev}`}>
                    <h3>{SEV_LABEL[sev]}</h3>
                    <ul className="finding-list">
                      {list.map((f) => {
                        const active =
                          f.room_ids.length > 0 &&
                          sameIds(highlightRoomIds, f.room_ids);
                        const measured = formatMeasured(f.metric, f.measured_value);
                        const rooms = f.room_ids
                          .map((id) => roomLabel(program, id))
                          .join("、");
                        const catZh = CATEGORY_ZH[f.category] ?? f.category;
                        return (
                          <li key={f.id}>
                            <button
                              type="button"
                              className={`finding-item ${active ? "active" : ""} ${f.room_ids.length ? "clickable" : ""}`}
                              onClick={() => toggleFinding(f)}
                              disabled={!f.room_ids.length}
                            >
                              <div className="finding-title">
                                <span className="finding-cat">{catZh}</span>
                                {f.title}
                              </div>
                              <p className="finding-msg">{f.message}</p>
                              {(rooms || measured) && (
                                <p className="finding-meta">
                                  {rooms && <span>房间：{rooms}</span>}
                                  {rooms && measured && <span> · </span>}
                                  {measured && <span>{measured}</span>}
                                </p>
                              )}
                              {f.recommended_action && (
                                <p className="finding-action">
                                  → {f.recommended_action}
                                </p>
                              )}
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </section>
                );
              })}
              {findings.length > 0 && (
                <p className="finding-disclaimer muted">
                  以上为设计启发式，不构成规范合规或法规审查结论。
                </p>
              )}
            </>
          )}

          {hard.length > 0 && (
            <>
              <h3>硬性违规</h3>
              <ul className="tiny-list bad">
                {hard.map((v, i) => (
                  <li key={`${v.constraint_id}-${i}`}>
                    <span>{v.message}</span>
                    <code className="violation-id">{v.constraint_id}</code>
                  </li>
                ))}
              </ul>
            </>
          )}
          {soft.length > 0 && (
            <>
              <h3>软性约束</h3>
              <ul className="tiny-list">
                {soft.map((v, i) => (
                  <li key={`${v.constraint_id}-${i}`}>
                    <span>{v.message}</span>
                    <code className="violation-id">{v.constraint_id}</code>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </aside>
  );
}
