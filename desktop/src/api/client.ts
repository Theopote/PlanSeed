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

/** 用当前 Program 房间清单（含已改 target_area）重生成 — Phase 4.0/4.1/4.2。 */
export async function generateFromProgram(
  form: RequirementForm,
  program: ProgramSummary,
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
    requirements: {
      site: {
        width: program.site_width,
        depth: program.site_depth,
      },
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
    },
  };
  if (opts?.base_seed != null) {
    body.base_seed = opts.base_seed;
  }
  if (opts?.locks && (opts.locks.rooms.length > 0 || opts.locks.stair || (opts.locks.zones?.length ?? 0) > 0)) {
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
  form: RequirementForm;
  program: ProgramSummary;
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
    body.requirements = {
      site: {
        width: opts.program.site_width,
        depth: opts.program.site_depth,
      },
      household: {
        bedrooms: opts.form.bedrooms,
        bathrooms: opts.form.bathrooms,
        has_garage: opts.form.has_garage,
      },
      preferences: {
        prefer_south_facing_living: opts.form.prefer_south_facing_living,
      },
      floor_count: opts.program.floor_count,
      spaces: opts.program.rooms.map((room) => ({
        id: room.id,
        name: room.name,
        category: room.category,
        target_area: room.target_area,
        floor_preference: room.floor_id ? [room.floor_id] : [],
      })),
    };
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
  form: RequirementForm;
  program: ProgramSummary;
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
    body.requirements = {
      site: {
        width: opts.program.site_width,
        depth: opts.program.site_depth,
      },
      household: {
        bedrooms: opts.form.bedrooms,
        bathrooms: opts.form.bathrooms,
        has_garage: opts.form.has_garage,
      },
      preferences: {
        prefer_south_facing_living: opts.form.prefer_south_facing_living,
      },
      floor_count: opts.program.floor_count,
      spaces: opts.program.rooms.map((room) => ({
        id: room.id,
        name: room.name,
        category: room.category,
        target_area: room.target_area,
        floor_preference: room.floor_id ? [room.floor_id] : [],
      })),
    };
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
