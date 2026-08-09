/** PlanSeed API 客户端类型与调用。 */

let _apiBase =
  import.meta.env.VITE_API_BASE?.replace(/\/$/, "") || "http://127.0.0.1:8787";

export function getApiBase(): string {
  return _apiBase;
}

export function setApiBase(url: string): void {
  _apiBase = url.replace(/\/$/, "");
}

export type EngineLifecycle = "STARTING" | "READY" | "ERROR" | "STOPPED";

/** 与 EngineLifecycle 并列：Ollama / 模型就绪与解析会话态。 */
export type LlmHealthState =
  | "LLMUnavailable"
  | "ModelMissing"
  | "ModelReady"
  | "ParseRunning"
  | "ParseFailed";

export type LlmStatusPayload = {
  state: LlmHealthState;
  provider: string;
  model: string;
  detail: string | null;
  installed_models: string[];
};

/** 浏览器用默认端口；Tauri 内从 get_engine_url 覆盖。 */
export async function resolveEngineBase(): Promise<string> {
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    const url = await invoke<string>("get_engine_url");
    if (url && url.startsWith("http")) {
      setApiBase(url);
    }
  } catch {
    /* 非 Tauri / 命令未就绪 → 保留默认 */
  }
  return _apiBase;
}

/** Tauri：杀掉托管子进程并重新 spawn（浏览器需自行处理）。 */
export async function retryEngine(): Promise<void> {
  const { invoke } = await import("@tauri-apps/api/core");
  await invoke("retry_engine");
}

export type DesignFinding = {
  id: string;
  category: string;
  severity: "info" | "positive" | "warning" | "problem";
  title: string;
  message: string;
  room_ids: string[];
  metric: string | null;
  measured_value: number | null;
  recommended_action: string | null;
};

export type DesignScore = {
  program_score: number;
  spatial_score: number;
  circulation_score: number;
  privacy_score: number;
  environment_score: number;
  technical_score: number;
  robustness_score: number;
  total_score: number;
  evaluation_version?: string;
  findings: DesignFinding[];
  explanations: string[];
  warnings: string[];
  violations: Array<{
    constraint_id: string;
    message: string;
    hard: boolean;
  }>;
};

export type CandidateProvenance = {
  solver_version: string;
  generator_version: string;
  evaluation_version?: string | null;
};

export type RoomPlacementPayload = {
  room_id: string;
  floor_id: string;
  x: number;
  y: number;
  width: number;
  depth: number;
  area: number;
};

/** Phase 4.1 — 会话锁（不进 RequirementSpec）。 */
export type LockedRoomRect = {
  room_id: string;
  floor_id: string;
  x: number;
  y: number;
  width: number;
  depth: number;
};

export type LockedStairCore = {
  x: number;
  y: number;
  width: number;
  depth: number;
  core_placement?: string | null;
};

export type LockedZoneRect = {
  zone: string;
  floor_id: string;
  x: number;
  y: number;
  width: number;
  depth: number;
  room_ids?: string[];
  /** ZonePlacement.id，如 F1-day-0 */
  zone_id?: string | null;
};

export type LayoutLocks = {
  rooms: LockedRoomRect[];
  stair?: LockedStairCore | null;
  zones: LockedZoneRect[];
};

export type ZonePlacementPayload = {
  id?: string | null;
  zone: string;
  kind?: string | null;
  floor_id: string;
  x: number;
  y: number;
  width: number;
  depth: number;
  room_ids: string[];
};

export type MutationRecordPayload = {
  id: string;
  kind: string;
  room_id?: string | null;
  partner_room_id?: string | null;
  before?: Record<string, number> | null;
  after?: Record<string, number> | null;
  after_partner?: Record<string, number> | null;
  created_at?: string | null;
};

export type RevisionStatus = "generated" | "dirty" | "validated";

export type CandidatePayload = {
  id: string;
  seed: number;
  score: number | null;
  label: string;
  svg: string;
  /** 每层独立 SVG（serializer）；报告优先；缺省退回整图 snapshot */
  floor_svgs?: Record<string, string>;
  design_score: DesignScore | null;
  validation: {
    valid: boolean;
    hard_violations: Array<{ constraint_id: string; message: string }>;
    soft_violations: Array<{ constraint_id: string; message: string }>;
    warnings: string[];
  } | null;
  metrics: Record<string, unknown>;
  provenance?: CandidateProvenance | null;
  /** Phase 5 血缘 */
  variant_parent_id?: string | null;
  variant_generation?: number;
  lock_snapshot_id?: string | null;
  /** Phase 5.1 revision */
  revision_status?: RevisionStatus;
  revision_parent_id?: string | null;
  mutations?: MutationRecordPayload[];
  placements?: RoomPlacementPayload[];
  zones?: ZonePlacementPayload[];
};

export type ProgramSummary = {
  project_id: string;
  site_width: number;
  site_depth: number;
  floor_count: number;
  rooms: Array<{
    id: string;
    name: string;
    category: string;
    target_area: number;
    floor_id: string | null;
  }>;
  floors: Array<{ id: string; label: string | null; room_ids: string[] }>;
  assumptions: Array<{ key: string; value: unknown; reason: string }>;
  unknowns: Array<{ key: string; description: string }>;
};

export type GenerateResponse = {
  generated: number;
  valid: number;
  rejected: number;
  program_summary: ProgramSummary;
  /** Phase 5.1.1：求解用 canonical RequirementSpec */
  requirement_spec?: RequirementSpecPayload | null;
  candidates: CandidatePayload[];
  violation_summary?: Record<string, number>;
  rejected_candidates?: RejectedCandidatePayload[];
  solver_identity?: {
    solver_version: string;
    generator_version: string;
    evaluation_version: string;
  };
};

/** Hard-fail 无效候选（≠ 有效但未进 Top-K）。 */
export type RejectedCandidatePayload = {
  id: string;
  seed: number;
  reasons: string[];
  constraint_ids: string[];
};

export type RequirementForm = {
  width: number;
  depth: number;
  floor_count: number;
  bedrooms: number;
  bathrooms: number;
  has_garage: boolean;
  prefer_south_facing_living: boolean;
};

export type ParseNLResponse = {
  requirement_spec: RequirementSpecPayload;
  attempts: number;
  repair_notes: string[];
  provider: string;
  raw?: Record<string, unknown>;
};

/** 用 RequirementSpec 的 known 字段回填简表（不覆盖未提供的项）。 */
export function patchFormFromRequirementSpec(
  form: RequirementForm,
  spec: RequirementSpecPayload,
): RequirementForm {
  const next = { ...form };
  if (spec.site?.width != null) next.width = spec.site.width;
  if (spec.site?.depth != null) next.depth = spec.site.depth;
  if (spec.floor_count != null) next.floor_count = spec.floor_count;
  if (spec.household?.bedrooms != null) next.bedrooms = spec.household.bedrooms;
  if (spec.household?.bathrooms != null)
    next.bathrooms = spec.household.bathrooms;
  if (spec.household?.has_garage != null)
    next.has_garage = spec.household.has_garage;
  if (spec.preferences?.prefer_south_facing_living != null) {
    next.prefer_south_facing_living =
      spec.preferences.prefer_south_facing_living;
  }
  return next;
}

async function readApiError(r: Response): Promise<string> {
  let msg = `HTTP ${r.status}`;
  try {
    const body = (await r.json()) as {
      detail?: string | { message?: string; errors?: string[] };
    };
    if (typeof body.detail === "string") msg = body.detail;
    else if (body.detail && typeof body.detail === "object") {
      const d = body.detail;
      msg = d.message ?? msg;
      if (d.errors?.length) msg = `${msg}（${d.errors[d.errors.length - 1]}）`;
    }
  } catch {
    /* keep */
  }
  return msg;
}

/** Phase 6.5 — NL → RequirementSpec（含服务端 repair）。 */
export async function parseRequirementsNl(
  text: string,
  opts?: { max_repairs?: number },
): Promise<ParseNLResponse> {
  const r = await fetch(`${_apiBase}/api/requirements/parse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text,
      max_repairs: opts?.max_repairs ?? 2,
    }),
  });
  if (!r.ok) throw new Error(await readApiError(r));
  return r.json() as Promise<ParseNLResponse>;
}

/** Phase 5.1.1 — 与 packages.schema.requirements.RequirementSpec 对齐的会话事实源。 */
export type RequirementSpecPayload = {
  raw_text?: string | null;
  site?: {
    width?: number | null;
    depth?: number | null;
    north_angle?: number | null;
    entrance_edge?: string | null;
    road_edges?: string[];
    setbacks?: Record<string, unknown> | null;
  };
  household?: {
    occupants?: number | null;
    bedrooms?: number | null;
    bathrooms?: number | null;
    has_garage?: boolean | null;
    notes?: string;
  };
  spaces?: Array<{
    id?: string | null;
    name: string;
    category?: string | null;
    target_area?: number | null;
    floor_preference?: string[];
    tags?: string[];
    preferred_orientation?: string | null;
    min_width?: number | null;
  }>;
  preferences?: {
    prefer_south_facing_living?: boolean | null;
    prefer_open_kitchen_dining?: boolean | null;
    prefer_compact_footprint?: boolean | null;
    prefer_short_corridor?: boolean | null;
    quiet_zone_away_from_entry?: boolean | null;
    wet_stack_preference?: boolean | null;
  };
  floor_count?: number | null;
  assumptions?: Array<{ key: string; value: unknown; reason?: string }>;
  unknowns?: Array<{ key: string; description?: string }>;
};

/** 用 ProgramSummary 房间面积/楼层补丁 spaces（Inspector 改面积后保持 spec 同步）。 */
export function syncRequirementSpacesFromProgram(
  spec: RequirementSpecPayload,
  program: ProgramSummary,
): RequirementSpecPayload {
  const byId = new Map(program.rooms.map((r) => [r.id, r]));
  const spaces = (spec.spaces ?? []).map((s) => {
    const id = s.id ?? null;
    if (!id || !byId.has(id)) return s;
    const room = byId.get(id)!;
    return {
      ...s,
      name: room.name || s.name,
      category: room.category ?? s.category,
      target_area: room.target_area,
      floor_preference: room.floor_id
        ? [room.floor_id]
        : (s.floor_preference ?? []),
    };
  });
  // 程序有、spec 无的房间（少见）追加
  const known = new Set(spaces.map((s) => s.id).filter(Boolean));
  for (const room of program.rooms) {
    if (known.has(room.id)) continue;
    spaces.push({
      id: room.id,
      name: room.name,
      category: room.category,
      target_area: room.target_area,
      floor_preference: room.floor_id ? [room.floor_id] : [],
    });
  }
  return {
    ...spec,
    site: {
      ...(spec.site ?? {}),
      width: program.site_width,
      depth: program.site_depth,
    },
    floor_count: program.floor_count,
    spaces,
  };
}

/** 仅在尚无 canonical spec 时的降级（旧项目）；新会话禁止依赖此路径。 */
export function fallbackRequirementFromForm(
  form: RequirementForm,
  program?: ProgramSummary | null,
): RequirementSpecPayload {
  if (program) {
    return {
      site: { width: program.site_width, depth: program.site_depth },
      household: {
        bedrooms: form.bedrooms,
        bathrooms: form.bathrooms,
        has_garage: form.has_garage,
      },
      preferences: {
        prefer_south_facing_living: form.prefer_south_facing_living,
      },
      floor_count: program.floor_count,
      spaces: program.rooms.map((room) => ({
        id: room.id,
        name: room.name,
        category: room.category,
        target_area: room.target_area,
        floor_preference: room.floor_id ? [room.floor_id] : [],
      })),
    };
  }
  return {
    site: { width: form.width, depth: form.depth },
    household: {
      bedrooms: form.bedrooms,
      bathrooms: form.bathrooms,
      has_garage: form.has_garage,
    },
    preferences: {
      prefer_south_facing_living: form.prefer_south_facing_living,
    },
    floor_count: form.floor_count,
  };
}

export type AxisCompareRow = {
  key: string;
  label: string;
  score_a: number;
  score_b: number;
};

export type CompareResponse = {
  label_a: string;
  label_b: string;
  rows: AxisCompareRow[];
  advantages_a: string[];
  advantages_b: string[];
};

export async function checkHealth(): Promise<boolean> {
  try {
    const r = await fetch(`${_apiBase}/api/health`);
    if (!r.ok) return false;
    const data = (await r.json()) as {
      ok?: boolean;
      service?: string;
      api_version?: string;
      engine_version?: string;
    };
    return (
      data.ok === true &&
      data.service === "planseed" &&
      data.api_version === "1" &&
      typeof data.engine_version === "string" &&
      data.engine_version.length > 0
    );
  } catch {
    return false;
  }
}

/** 探测 Ollama / 配置模型；失败时返回 LLMUnavailable 占位。 */
export async function fetchLlmStatus(): Promise<LlmStatusPayload> {
  try {
    const r = await fetch(`${_apiBase}/api/llm/status`);
    if (!r.ok) {
      return {
        state: "LLMUnavailable",
        provider: "ollama",
        model: "qwen2.5:7b",
        detail: `HTTP ${r.status}`,
        installed_models: [],
      };
    }
    return (await r.json()) as LlmStatusPayload;
  } catch (e) {
    return {
      state: "LLMUnavailable",
      provider: "ollama",
      model: "qwen2.5:7b",
      detail: e instanceof Error ? e.message : String(e),
      installed_models: [],
    };
  }
}

export async function compareCandidates(
  evaluationA: DesignScore,
  evaluationB: DesignScore,
  labelA = "A",
  labelB = "B",
): Promise<CompareResponse> {
  const r = await fetch(`${_apiBase}/api/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      evaluation_a: evaluationA,
      evaluation_b: evaluationB,
      label_a: labelA,
      label_b: labelB,
    }),
  });
  if (!r.ok) {
    let msg = `HTTP ${r.status}`;
    try {
      const body = (await r.json()) as { detail?: string };
      if (body.detail) msg = body.detail;
    } catch {
      /* keep */
    }
    throw new Error(msg);
  }
  return r.json() as Promise<CompareResponse>;
}

export async function generateBenchmark(
  opts?: { candidate_count?: number; return_top_k?: number },
): Promise<GenerateResponse> {
  const r = await fetch(`${_apiBase}/api/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      use_benchmark: true,
      candidate_count: opts?.candidate_count ?? 16,
      return_top_k: opts?.return_top_k ?? 5,
    }),
  });
  if (!r.ok) {
    const detail = await r.text();
    throw new Error(detail || `HTTP ${r.status}`);
  }
  return r.json() as Promise<GenerateResponse>;
}

export async function generateFromForm(
  form: RequirementForm,
  opts?: { candidate_count?: number; return_top_k?: number },
): Promise<GenerateResponse> {
  const r = await fetch(`${_apiBase}/api/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      use_benchmark: false,
      candidate_count: opts?.candidate_count ?? 16,
      return_top_k: opts?.return_top_k ?? 5,
      requirements: {
        site: {
          width: form.width,
          depth: form.depth,
        },
        household: {
          bedrooms: form.bedrooms,
          bathrooms: form.bathrooms,
          has_garage: form.has_garage,
        },
        preferences: {
          prefer_south_facing_living: form.prefer_south_facing_living,
        },
        floor_count: form.floor_count,
      },
    }),
  });
  if (!r.ok) {
    let msg = `HTTP ${r.status}`;
    try {
      const body = (await r.json()) as { detail?: string };
      if (body.detail) msg = body.detail;
    } catch {
      /* keep msg */
    }
    throw new Error(msg);
  }
  return r.json() as Promise<GenerateResponse>;
}

/** 用 canonical RequirementSpec（spaces 已与 Program 同步）重生成。 */
export async function generateFromProgram(
  requirementSpec: RequirementSpecPayload,
  opts?: {
    candidate_count?: number;
    return_top_k?: number;
    base_seed?: number;
    locks?: LayoutLocks | null;
  },
): Promise<GenerateResponse> {
  const body: Record<string, unknown> = {
    use_benchmark: false,
    candidate_count: opts?.candidate_count ?? 16,
    return_top_k: opts?.return_top_k ?? 5,
    requirements: requirementSpec,
  };
  if (opts?.base_seed != null) {
    body.base_seed = opts.base_seed;
  }
  if (
    opts?.locks &&
    (opts.locks.rooms.length > 0 ||
      opts.locks.stair ||
      (opts.locks.zones?.length ?? 0) > 0)
  ) {
    body.locks = {
      rooms: opts.locks.rooms,
      stair: opts.locks.stair ?? null,
      zones: opts.locks.zones ?? [],
    };
  }
  const r = await fetch(`${_apiBase}/api/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    let msg = `HTTP ${r.status}`;
    try {
      const errBody = (await r.json()) as { detail?: string };
      if (errBody.detail) msg = errBody.detail;
    } catch {
      /* keep */
    }
    throw new Error(msg);
  }
  return r.json() as Promise<GenerateResponse>;
}

export type ProjectSummary = {
  id: string;
  name: string;
  updated_at: string;
};

export type ProjectPayload = {
  form: RequirementForm | Record<string, unknown>;
  program: ProgramSummary | null;
  requirement_spec?: RequirementSpecPayload | null;
  locks: LayoutLocks;
  candidates: CandidatePayload[];
  selected_id: string | null;
  compare_id?: string | null;
  schema_versions?: {
    solver_version?: string | null;
    generator_version?: string | null;
    evaluation_version?: string | null;
  };
  project_meta?: {
    format_version: string;
    app_version: string;
  };
};

export type ProjectDetail = {
  id: string;
  name: string;
  updated_at: string;
  payload: ProjectPayload;
  evaluation_version_mismatch: boolean;
  current_evaluation_version: string;
};

export async function listProjects(): Promise<ProjectSummary[]> {
  const r = await fetch(`${_apiBase}/api/projects`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json() as Promise<ProjectSummary[]>;
}

export async function saveProject(opts: {
  name: string;
  id?: string | null;
  payload: ProjectPayload;
}): Promise<ProjectDetail> {
  const r = await fetch(`${_apiBase}/api/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: opts.name,
      id: opts.id ?? null,
      payload: opts.payload,
    }),
  });
  if (!r.ok) {
    let msg = `HTTP ${r.status}`;
    try {
      const body = (await r.json()) as { detail?: string };
      if (typeof body.detail === "string") msg = body.detail;
    } catch {
      /* keep */
    }
    throw new Error(msg);
  }
  return r.json() as Promise<ProjectDetail>;
}

export async function loadProject(id: string): Promise<ProjectDetail> {
  const r = await fetch(`${_apiBase}/api/projects/${encodeURIComponent(id)}`);
  if (!r.ok) {
    let msg = `HTTP ${r.status}`;
    try {
      const body = (await r.json()) as { detail?: string };
      if (typeof body.detail === "string") msg = body.detail;
    } catch {
      /* keep */
    }
    throw new Error(msg);
  }
  return r.json() as Promise<ProjectDetail>;
}

/** Phase 7 — Design Report（权威 JSON + HTML 预览）。 */
export type BuildReportResponse = {
  report: {
    status?: string;
    source_revision_id?: string | null;
    project: { project_name: string; edited?: boolean };
    candidate: { candidate_id: string; label: string; total_score: number | null };
    requirement: { key_intents: string[] };
    evaluation?: { evaluation_fresh?: boolean };
  };
  html: string | null;
};

function formatReportErrorDetail(detail: unknown, status: number): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const d = detail as { code?: string; message?: string };
    if (d.code === "candidate_requires_revalidation") {
      return (
        d.message ??
        "方案已修改，评价结果已过期。请先重新验证后再导出正式评价报告。"
      );
    }
    if (typeof d.message === "string") return d.message;
    return JSON.stringify(detail);
  }
  return `HTTP ${status}`;
}

export async function buildReport(opts: {
  projectName?: string;
  payload: ProjectPayload;
  candidateId?: string | null;
  includeHtml?: boolean;
  /** 默认 false：dirty 候选由后端 409 拒绝正式评价报告 */
  allowStaleEvaluation?: boolean;
}): Promise<BuildReportResponse> {
  const r = await fetch(`${_apiBase}/api/reports/build`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_name: opts.projectName ?? "Untitled",
      payload: opts.payload,
      candidate_id: opts.candidateId ?? opts.payload.selected_id,
      include_html: opts.includeHtml ?? true,
      allow_stale_evaluation: opts.allowStaleEvaluation ?? false,
    }),
  });
  if (!r.ok) {
    let msg = `HTTP ${r.status}`;
    try {
      const body = (await r.json()) as { detail?: unknown };
      msg = formatReportErrorDetail(body.detail, r.status);
    } catch {
      /* keep */
    }
    throw new Error(msg);
  }
  return r.json() as Promise<BuildReportResponse>;
}

export type GeometryMutationRequest = {
  kind: "move" | "resize" | "adjust_wall" | "lock" | "unlock";
  room_id?: string | null;
  partner_room_id?: string | null;
  floor_id: string;
  before?: {
    x: number;
    y: number;
    width: number;
    depth: number;
  } | null;
  proposed?: {
    x: number;
    y: number;
    width: number;
    depth: number;
  } | null;
  wall_axis?: "x" | "y" | null;
  wall_coord?: number | null;
  source?: "pointer" | "inspector" | "system";
};

export type MutationPreviewApiResult = {
  ok: boolean;
  reasons: Array<{ code: string; message: string }>;
  warnings: Array<{ code: string; message: string }>;
  snapped: {
    x: number;
    y: number;
    width: number;
    depth: number;
  } | null;
  snapped_partner: {
    x: number;
    y: number;
    width: number;
    depth: number;
  } | null;
  conflict_room_ids: string[];
};

/** Phase 5.1 — Python Geometry Mutation Authority。 */
export async function previewMutation(opts: {
  useBenchmark?: boolean;
  requirementSpec?: RequirementSpecPayload | null;
  placements: RoomPlacementPayload[];
  locks: LayoutLocks;
  mutation: GeometryMutationRequest;
  snapModule?: number;
}): Promise<MutationPreviewApiResult> {
  const body: Record<string, unknown> = {
    use_benchmark: opts.useBenchmark ?? false,
    placements: opts.placements,
    locks: {
      rooms: opts.locks.rooms,
      stair: opts.locks.stair ?? null,
      zones: opts.locks.zones ?? [],
    },
    mutation: opts.mutation,
    snap_module: opts.snapModule ?? 0.3,
  };
  if (!opts.useBenchmark) {
    if (!opts.requirementSpec) {
      throw new Error("缺少 requirement_spec，无法预览 mutation");
    }
    body.requirements = opts.requirementSpec;
  }
  const r = await fetch(`${_apiBase}/api/mutations/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    let msg = `HTTP ${r.status}`;
    try {
      const errBody = (await r.json()) as { detail?: string };
      if (typeof errBody.detail === "string") msg = errBody.detail;
    } catch {
      /* keep */
    }
    throw new Error(msg);
  }
  return r.json() as Promise<MutationPreviewApiResult>;
}

/** Phase 5.1 — 重算 openings / access / evaluation（不改几何）。 */
export async function revalidateMutation(opts: {
  useBenchmark?: boolean;
  requirementSpec?: RequirementSpecPayload | null;
  placements: RoomPlacementPayload[];
  locks: LayoutLocks;
  zones?: ZonePlacementPayload[];
  candidateId: string;
  seed: number;
  labelIndex?: number;
  variantParentId?: string | null;
  variantGeneration?: number;
  lockSnapshotId?: string | null;
  mutations?: MutationRecordPayload[];
  revisionParentId?: string | null;
}): Promise<CandidatePayload> {
  const body: Record<string, unknown> = {
    use_benchmark: opts.useBenchmark ?? false,
    placements: opts.placements,
    locks: {
      rooms: opts.locks.rooms,
      stair: opts.locks.stair ?? null,
      zones: opts.locks.zones ?? [],
    },
    zones: opts.zones ?? [],
    candidate_id: opts.candidateId,
    seed: opts.seed,
    label_index: opts.labelIndex ?? 0,
    variant_parent_id: opts.variantParentId ?? null,
    variant_generation: opts.variantGeneration ?? 0,
    lock_snapshot_id: opts.lockSnapshotId ?? null,
    mutations: opts.mutations ?? [],
    revision_parent_id: opts.revisionParentId ?? opts.candidateId,
  };
  if (!opts.useBenchmark) {
    if (!opts.requirementSpec) {
      throw new Error("缺少 requirement_spec，无法 Revalidate");
    }
    body.requirements = opts.requirementSpec;
  }
  const r = await fetch(`${_apiBase}/api/mutations/revalidate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    let msg = `HTTP ${r.status}`;
    try {
      const errBody = (await r.json()) as { detail?: string };
      if (typeof errBody.detail === "string") msg = errBody.detail;
    } catch {
      /* keep */
    }
    throw new Error(msg);
  }
  return r.json() as Promise<CandidatePayload>;
}
