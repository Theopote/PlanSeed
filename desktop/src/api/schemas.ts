/**
 * OpenAPI components.schemas 别名（Phase 7.5-A）。
 * 源：generated.ts（由 desktop/openapi.json 生成）。勿手抄字段表。
 *
 * 对 pydantic 默认值导致的「必填变可选」、以及 dict/Any 变宽的嵌套，
 * 仅做 Desktop 消费侧窄化（不另发明后端契约）。
 */
import type { components } from "./generated";

export type Schemas = components["schemas"];

export type DesignFinding = Omit<
  Schemas["DesignFinding"],
  "room_ids" | "metric" | "measured_value"
> & {
  room_ids: string[];
  metric: string | null;
  measured_value: number | null;
};

export type DesignScore = Omit<
  Schemas["DesignScore"],
  "findings" | "explanations" | "warnings" | "violations"
> & {
  findings: DesignFinding[];
  explanations: string[];
  warnings: string[];
  violations: Schemas["Violation"][];
};

export type CandidateProvenance = Schemas["CandidateProvenance"];
export type RoomPlacementPayload = Schemas["RoomPlacementPayload"];
export type LockedRoomRect = Schemas["LockedRoomRect"];
export type LockedStairCore = Schemas["LockedStairCore"];

/** zone 在会话 UI 可能先是自由 string，再落到 ArchitecturalZone。 */
export type LockedZoneRect = Omit<Schemas["LockedZoneRect"], "zone"> & {
  zone: string;
};

export type ZonePlacementPayload = Omit<
  Schemas["ZonePlacementPayload"],
  "zone" | "room_ids"
> & {
  zone: string;
  room_ids: string[];
};

export type MutationRecordPayload = Schemas["MutationRecordPayload"];

export type CandidatePayload = Omit<
  Schemas["CandidatePayload"],
  | "design_score"
  | "validation"
  | "metrics"
  | "revision_status"
  | "zones"
  | "placements"
> & {
  design_score: DesignScore | null;
  validation: {
    valid: boolean;
    hard_violations: Array<{ constraint_id: string; message: string }>;
    soft_violations: Array<{ constraint_id: string; message: string }>;
    warnings: string[];
  } | null;
  metrics: Record<string, unknown>;
  revision_status?: "generated" | "dirty" | "validated";
  placements?: RoomPlacementPayload[];
  zones?: ZonePlacementPayload[];
};

export type RejectedCandidatePayload = Omit<
  Schemas["RejectedCandidatePayload"],
  "reasons" | "constraint_ids"
> & {
  reasons: string[];
  constraint_ids: string[];
};

export type ParseNLResponse = Schemas["ParseNLResponse"];
export type ParserAudit = Schemas["ParserAudit"];
export type RelationIntentPayload = Schemas["RelationIntent"];
export type SetbackPayload = Schemas["SetbackSpec"];
export type SpaceRequirementPayload = Schemas["SpaceRequirement"];

export type AssumptionPayload = Omit<Schemas["Assumption"], "value"> & {
  /** UI 编辑中可能暂为任意 JSON；提交前应可序列化为标量。 */
  value: string | number | boolean | null;
};

export type UnknownPayload = Schemas["UnknownRequirement"];

export type RequirementSpecPayload = Omit<
  Schemas["RequirementSpec"],
  "assumptions" | "unknowns" | "household"
> & {
  assumptions?: AssumptionPayload[];
  unknowns?: UnknownPayload[];
  household?: {
    occupants?: number | null;
    bedrooms?: number | null;
    bathrooms?: number | null;
    has_garage?: boolean | null;
    notes?: string;
  };
};

export type AxisCompareRow = Schemas["AxisCompareRowPayload"];

export type CompareResponse = Omit<
  Schemas["CompareResponse"],
  "rows" | "advantages_a" | "advantages_b"
> & {
  rows: AxisCompareRow[];
  advantages_a: string[];
  advantages_b: string[];
};

export type ProjectSummary = Schemas["ProjectSummaryOut"];

export type BuildReportResponse = Schemas["BuildReportResponse"];

export type GeometryMutationRequest = Schemas["GeometryMutation"];

export type MutationPreviewApiResult = Schemas["MutationPreviewResult"];

/** 会话锁：OpenAPI 字段可选；UI 始终持有 rooms/zones 数组。 */
export type LayoutLocks = {
  rooms: LockedRoomRect[];
  stair?: LockedStairCore | null;
  zones: LockedZoneRect[];
};

/** v0.2-B：局部重生成作用域（OpenAPI 待同步；字段与后端一致）。 */
export type RegenerationScope = {
  mutable_rooms: string[];
  locked_rooms?: string[];
  affected_neighbors?: string[];
  preserve_topology?: boolean;
  preserve_floor_assignment?: boolean;
};

export type ProgramSummary = Omit<
  Schemas["ProgramSummary"],
  "floors" | "assumptions" | "unknowns" | "rooms"
> & {
  rooms: Array<{
    id: string;
    name: string;
    category: string;
    target_area: number;
    floor_id: string | null;
  }>;
  floors: Array<{ id: string; label: string | null; room_ids: string[] }>;
  assumptions: AssumptionPayload[];
  unknowns: UnknownPayload[];
};

export type GenerateResponse = Omit<
  Schemas["GenerateResponse"],
  "program_summary" | "candidates" | "solver_identity" | "rejected_candidates"
> & {
  program_summary: ProgramSummary;
  candidates: CandidatePayload[];
  rejected_candidates?: RejectedCandidatePayload[];
  solver_identity?: {
    solver_version: string;
    generator_strategy?: string;
    generator_version: string;
    selection_strategy?: string;
    selection_version?: string;
    evaluation_version: string;
    assignment_strategy?: string;
    geometry_backend?: string;
  };
};

export type ProjectPayload = {
  form?: Record<string, unknown>;
  program?: ProgramSummary | null;
  requirement_spec?: RequirementSpecPayload | null;
  locks?: LayoutLocks;
  candidates?: CandidatePayload[];
  selected_id?: string | null;
  compare_id?: string | null;
  schema_versions?: Schemas["SchemaVersions"];
  project_meta?: Schemas["ProjectMeta"];
};

export type ProjectDetail = Omit<Schemas["ProjectDetail"], "payload"> & {
  payload: ProjectPayload;
};

export type RevisionStatus = NonNullable<CandidatePayload["revision_status"]>;
export type AssumptionSource = AssumptionPayload["source"];
export type UnknownPriority = UnknownPayload["priority"];
export type RelationKind = RelationIntentPayload["kind"];
export type RelationStrength = RelationIntentPayload["strength"];
export type ReportExportMode = Schemas["BuildReportRequest"]["mode"];
export type SvgExportScope = Schemas["SvgExportRequest"]["scope"];
export type PngExportSize = Schemas["PngExportRequest"]["size"];
