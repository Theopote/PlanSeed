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

export type LayoutLocks = {
  rooms: LockedRoomRect[];
  stair?: LockedStairCore | null;
};

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
  placements?: RoomPlacementPayload[];
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
  if (opts?.locks && (opts.locks.rooms.length > 0 || opts.locks.stair)) {
    body.locks = {
      rooms: opts.locks.rooms,
      stair: opts.locks.stair ?? null,
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
