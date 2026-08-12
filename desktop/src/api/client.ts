/** PlanSeed API 客户端：fetch / 错误处理 / UI·domain helper。
 *
 * 核心 DTO 来自 OpenAPI → generated.ts → schemas.ts（Phase 7.5-A）。
 * 勿在本文件手抄与后端重复的字段表。
 */

export type {
  AssumptionPayload,
  AssumptionSource,
  AxisCompareRow,
  BuildReportResponse,
  CandidatePayload,
  CandidateProvenance,
  CompareResponse,
  DesignFinding,
  DesignScore,
  GenerateResponse,
  GeometryMutationRequest,
  LayoutLocks,
  LockedRoomRect,
  LockedStairCore,
  LockedZoneRect,
  MutationPreviewApiResult,
  MutationRecordPayload,
  ParseNLResponse,
  PngExportSize,
  ProgramSummary,
  ProjectDetail,
  ProjectPayload,
  ProjectSummary,
  RejectedCandidatePayload,
  RelationIntentPayload,
  RelationKind,
  RelationStrength,
  ReportExportMode,
  RequirementSpecPayload,
  RevisionStatus,
  RoomPlacementPayload,
  SetbackPayload,
  SpaceRequirementPayload,
  SvgExportScope,
  UnknownPayload,
  UnknownPriority,
  ZonePlacementPayload,
} from "./schemas";

import type {
  AssumptionPayload,
  BuildReportResponse,
  CandidatePayload,
  CompareResponse,
  DesignScore,
  GenerateResponse,
  GeometryMutationRequest,
  LayoutLocks,
  MutationPreviewApiResult,
  MutationRecordPayload,
  ParseNLResponse,
  PngExportSize,
  ProgramSummary,
  ProjectDetail,
  ProjectPayload,
  ProjectSummary,
  RequirementSpecPayload,
  RoomPlacementPayload,
  SvgExportScope,
  UnknownPayload,
  ReportExportMode,
  ZonePlacementPayload,
} from "./schemas";

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
  base_url?: string | null;
  endpoint_remote?: boolean;
  remote_blocked?: boolean;
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

/** UI 简表（非 OpenAPI schema；仅桌面表单状态）。 */
export type RequirementForm = {
  width: number;
  depth: number;
  floor_count: number;
  bedrooms: number;
  bathrooms: number;
  has_garage: boolean;
  prefer_south_facing_living: boolean;
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
      detail?:
        | string
        | {
            message?: string;
            errors?: string[];
            issues?: Array<{ message?: string }>;
          };
    };
    if (typeof body.detail === "string") msg = body.detail;
    else if (body.detail && typeof body.detail === "object") {
      const d = body.detail;
      msg = d.message ?? msg;
      if (d.errors?.length) msg = `${msg}（${d.errors[d.errors.length - 1]}）`;
      else if (d.issues?.length) {
        const last = d.issues[d.issues.length - 1]?.message;
        if (last) msg = `${msg}（${last}）`;
      }
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

/** RequirementSpec DTO 见 schemas.ts（OpenAPI）；复制时禁止瘦 map。 */

/** 保真复制：不得丢掉 priority。 */
export function cloneUnknownPayload(u: UnknownPayload): UnknownPayload {
  return { ...u, description: u.description ?? "" };
}

/** 保真复制：不得丢掉 source。 */
export function cloneAssumptionPayload(a: AssumptionPayload): AssumptionPayload {
  return { ...a, reason: a.reason ?? "" };
}

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

/** 仅在尚无 canonical spec 时的降级（旧项目）；新会话禁止依赖此路径。
 * 若有 ProgramSummary，必须带回 assumptions / unknowns（含 source / priority）。
 */
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
        notes: "",
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
      assumptions: (program.assumptions ?? []).map(cloneAssumptionPayload),
      unknowns: (program.unknowns ?? []).map(cloneUnknownPayload),
    };
  }
  return {
    site: { width: form.width, depth: form.depth },
    household: {
      bedrooms: form.bedrooms,
      bathrooms: form.bathrooms,
      has_garage: form.has_garage,
      notes: "",
    },
    preferences: {
      prefer_south_facing_living: form.prefer_south_facing_living,
    },
    floor_count: form.floor_count,
  };
}

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
  if (!r.ok) throw new Error(await readApiError(r));
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
  if (!r.ok) throw new Error(await readApiError(r));
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
          notes: "",
        },
        preferences: {
          prefer_south_facing_living: form.prefer_south_facing_living,
        },
        floor_count: form.floor_count,
      },
    }),
  });
  if (!r.ok) throw new Error(await readApiError(r));
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
  if (!r.ok) throw new Error(await readApiError(r));
  return r.json() as Promise<GenerateResponse>;
}

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

/** Phase 7.5-D — 导出 `.planseed` 项目包。 */
export async function exportPlanseedPackage(
  projectId: string,
): Promise<{ blob: Blob; filename: string }> {
  const r = await fetch(
    `${_apiBase}/api/projects/${encodeURIComponent(projectId)}/package`,
  );
  if (!r.ok) {
    let msg = `HTTP ${r.status}`;
    try {
      const body = (await r.json()) as { detail?: string | { message?: string } };
      if (typeof body.detail === "string") msg = body.detail;
      else if (body.detail && typeof body.detail.message === "string") {
        msg = body.detail.message;
      }
    } catch {
      /* keep */
    }
    throw new Error(msg);
  }
  const blob = await r.blob();
  const filename =
    parseContentDispositionFilename(r.headers.get("Content-Disposition")) ??
    "project.planseed";
  return { blob, filename };
}

/** Phase 7.5-D — 导入 / 打开 `.planseed`（body = ZIP 字节）。 */
export async function importPlanseedPackage(
  file: Blob,
  opts?: { overwrite?: boolean },
): Promise<ProjectDetail> {
  const qs = opts?.overwrite ? "?overwrite=true" : "";
  const r = await fetch(`${_apiBase}/api/projects/import${qs}`, {
    method: "POST",
    headers: { "Content-Type": "application/zip" },
    body: file,
  });
  if (!r.ok) {
    if (r.status === 409 && !opts?.overwrite) {
      const retry = window.confirm("已存在同 id 项目。覆盖本地版本？");
      if (retry) return importPlanseedPackage(file, { overwrite: true });
    }
    throw new Error(await readApiError(r));
  }
  return r.json() as Promise<ProjectDetail>;
}

/** Phase 7 — Design Report。 */
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
    if (d.code === "revision_mismatch") {
      return (
        d.message ??
        "revision_id 与已保存候选不一致；请重新保存后再导出正式报告。"
      );
    }
    if (typeof d.message === "string") return d.message;
    return JSON.stringify(detail);
  }
  return `HTTP ${status}`;
}

function parseContentDispositionFilename(header: string | null): string | null {
  if (!header) return null;
  const star = /filename\*\s*=\s*UTF-8''([^;]+)/i.exec(header);
  if (star?.[1]) {
    try {
      return decodeURIComponent(star[1].trim());
    } catch {
      /* fall through */
    }
  }
  const plain = /filename\s*=\s*"([^"]+)"/i.exec(header);
  if (plain?.[1]) return plain[1];
  const bare = /filename\s*=\s*([^;]+)/i.exec(header);
  return bare?.[1]?.trim() ?? null;
}

function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** Phase 7.2.1 — Canonical SVG（Store + revision；禁止 DOM outerHTML）。 */
export async function exportSvg(opts: {
  projectId: string;
  candidateId: string;
  revisionId: string;
  scope: SvgExportScope;
  floorId?: string | null;
}): Promise<{ blob: Blob; filename: string }> {
  const r = await fetch(`${_apiBase}/api/exports/svg`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_id: opts.projectId,
      candidate_id: opts.candidateId,
      revision_id: opts.revisionId,
      scope: opts.scope,
      floor_id: opts.floorId ?? undefined,
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
  const blob = await r.blob();
  const filename =
    parseContentDispositionFilename(r.headers.get("content-disposition")) ??
    (opts.scope === "all_floors" ? "export_floors.svg.zip" : "export.svg");
  return { blob, filename };
}

/** Phase 7.2.2 — Canonical SVG → PNG（resvg；禁止 HTML 截图）。 */
export async function exportPng(opts: {
  projectId: string;
  candidateId: string;
  revisionId: string;
  scope: SvgExportScope;
  floorId?: string | null;
  size?: PngExportSize;
}): Promise<{ blob: Blob; filename: string }> {
  const r = await fetch(`${_apiBase}/api/exports/png`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_id: opts.projectId,
      candidate_id: opts.candidateId,
      revision_id: opts.revisionId,
      scope: opts.scope,
      floor_id: opts.floorId ?? undefined,
      size: opts.size ?? 2048,
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
  const blob = await r.blob();
  const filename =
    parseContentDispositionFilename(r.headers.get("content-disposition")) ??
    (opts.scope === "all_floors" ? "export_floors.png.zip" : "export.png");
  return { blob, filename };
}

/** Phase 7.2.3 — DesignReport JSON（≠ Project Snapshot）。 */
export async function exportReportJson(opts: {
  projectId: string;
  candidateId: string;
  revisionId: string;
  includeSvg?: boolean;
}): Promise<{ blob: Blob; filename: string }> {
  const r = await fetch(`${_apiBase}/api/exports/report-json`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_id: opts.projectId,
      candidate_id: opts.candidateId,
      revision_id: opts.revisionId,
      include_svg: opts.includeSvg ?? true,
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
  const blob = await r.blob();
  const filename =
    parseContentDispositionFilename(r.headers.get("content-disposition")) ??
    "DesignReport.json";
  return { blob, filename };
}

/** 触发浏览器 / WebView 下载。 */
export function downloadBlob(blob: Blob, filename: string): void {
  triggerBlobDownload(blob, filename);
}

/** Final Export：project_id + candidate_id + revision_id（从 store 读取）。 */
export async function buildReport(opts: {
  mode?: ReportExportMode;
  projectId: string;
  candidateId: string;
  revisionId: string;
  projectName?: string;
  includeHtml?: boolean;
  allowStaleEvaluation?: boolean;
}): Promise<BuildReportResponse> {
  const r = await fetch(`${_apiBase}/api/reports/build`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mode: opts.mode ?? "final",
      project_id: opts.projectId,
      candidate_id: opts.candidateId,
      revision_id: opts.revisionId,
      project_name: opts.projectName,
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

/** Preview：可直接传 payload（开发预览；非正式交付）。 */
export async function previewReport(opts: {
  projectName?: string;
  payload: ProjectPayload;
  candidateId?: string | null;
  includeHtml?: boolean;
  allowStaleEvaluation?: boolean;
}): Promise<BuildReportResponse> {
  const r = await fetch(`${_apiBase}/api/reports/build`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mode: "preview",
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
  if (!r.ok) throw new Error(await readApiError(r));
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
