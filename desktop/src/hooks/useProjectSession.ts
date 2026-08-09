import {
  useCallback,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";
import {
  downloadBlob,
  exportPlanseedPackage,
  fallbackRequirementFromForm,
  importPlanseedPackage,
  listProjects,
  loadProject,
  saveProject,
  type CandidatePayload,
  type LayoutLocks,
  type ProgramSummary,
  type ProjectDetail,
  type ProjectSummary,
  type RejectedCandidatePayload,
  type RequirementForm,
  type RequirementSpecPayload,
} from "../api/client";
import { DEFAULT_FORM } from "./useRequirementWorkflow";
import type { CandidateStats, SolverIdentity } from "./useCandidateWorkflow";
import { buildSchemaVersions, cloneLayoutLocks } from "./sessionHelpers";

export type UseProjectSessionArgs = {
  setError: Dispatch<SetStateAction<string | null>>;
  form: RequirementForm;
  setForm: Dispatch<SetStateAction<RequirementForm>>;
  program: ProgramSummary | null;
  setProgram: Dispatch<SetStateAction<ProgramSummary | null>>;
  setRequirementSpec: Dispatch<SetStateAction<RequirementSpecPayload | null>>;
  setNlText: Dispatch<SetStateAction<string>>;
  locks: LayoutLocks;
  setLocks: Dispatch<SetStateAction<LayoutLocks>>;
  candidates: CandidatePayload[];
  setCandidates: Dispatch<SetStateAction<CandidatePayload[]>>;
  selectedId: string | null;
  setSelectedId: Dispatch<SetStateAction<string | null>>;
  compareId: string | null;
  setCompareId: Dispatch<SetStateAction<string | null>>;
  setHighlightRoomIds: Dispatch<SetStateAction<string[]>>;
  setSelectedRoomId: Dispatch<SetStateAction<string | null>>;
  setStats: Dispatch<SetStateAction<CandidateStats | null>>;
  setRejectedCandidates: Dispatch<
    SetStateAction<RejectedCandidatePayload[]>
  >;
  setViolationSummary: Dispatch<SetStateAction<Record<string, number>>>;
  solverIdentity: SolverIdentity | null;
  setSolverIdentity: Dispatch<SetStateAction<SolverIdentity | null>>;
  resolveCanonicalSpec: () => RequirementSpecPayload | null;
};

export function useProjectSession({
  setError,
  form,
  setForm,
  program,
  setProgram,
  setRequirementSpec,
  setNlText,
  locks,
  setLocks,
  candidates,
  setCandidates,
  selectedId,
  setSelectedId,
  compareId,
  setCompareId,
  setHighlightRoomIds,
  setSelectedRoomId,
  setStats,
  setRejectedCandidates,
  setViolationSummary,
  solverIdentity,
  setSolverIdentity,
  resolveCanonicalSpec,
}: UseProjectSessionArgs) {
  const [projectId, setProjectId] = useState<string | null>(null);
  const [projectName, setProjectName] = useState("未命名项目");
  const [projectBusy, setProjectBusy] = useState(false);
  const [versionHint, setVersionHint] = useState<string | null>(null);
  const [projectPicker, setProjectPicker] = useState<ProjectSummary[] | null>(
    null,
  );

  const applyProjectDetail = useCallback(
    (detail: ProjectDetail) => {
      const p = detail.payload;
      setProjectId(detail.id);
      setProjectName(detail.name);
      if (p.form && typeof p.form === "object") {
        setForm({ ...DEFAULT_FORM, ...(p.form as RequirementForm) });
      }
      setProgram((p.program as ProgramSummary) ?? null);
      if (p.requirement_spec) {
        const spec = p.requirement_spec as RequirementSpecPayload;
        setRequirementSpec(spec);
        if (spec.raw_text) setNlText(spec.raw_text);
      } else if (p.program) {
        setRequirementSpec(
          fallbackRequirementFromForm(
            { ...DEFAULT_FORM, ...(p.form as RequirementForm) },
            p.program as ProgramSummary,
          ),
        );
      } else {
        setRequirementSpec(null);
      }
      setLocks({
        rooms: p.locks?.rooms ?? [],
        stair: p.locks?.stair ?? null,
        zones: p.locks?.zones ?? [],
      });
      setCandidates(p.candidates ?? []);
      setSelectedId(p.selected_id ?? p.candidates?.[0]?.id ?? null);
      setCompareId(p.compare_id ?? null);
      setHighlightRoomIds([]);
      setSelectedRoomId(null);
      setStats(null);
      setRejectedCandidates([]);
      setViolationSummary({});
      setProjectPicker(null);
      if (
        p.schema_versions?.solver_version &&
        p.schema_versions.generator_version &&
        p.schema_versions.evaluation_version
      ) {
        setSolverIdentity({
          solver_version: p.schema_versions.solver_version,
          generator_version: p.schema_versions.generator_version,
          evaluation_version: p.schema_versions.evaluation_version,
        });
      }
      const dirty = (p.candidates ?? []).some(
        (c) => c.revision_status === "dirty",
      );
      const missingSpec = !p.requirement_spec;
      if (detail.evaluation_version_mismatch) {
        setVersionHint(
          `评价版本已变（快照 ${p.schema_versions?.evaluation_version ?? "?"} → 当前 ${detail.current_evaluation_version}）：分数可能不可比；布局几何仍按快照。`,
        );
      } else if (dirty) {
        setVersionHint(
          "项目含已编辑草稿（Evaluation outdated）；评分非当前几何。",
        );
      } else if (missingSpec) {
        setVersionHint(
          "旧项目缺少 RequirementSpec，已用 form+program 降级重建；请重新 Generate 以固化意图。",
        );
      } else {
        setVersionHint(null);
      }
    },
    [
      setForm,
      setProgram,
      setRequirementSpec,
      setNlText,
      setLocks,
      setCandidates,
      setSelectedId,
      setCompareId,
      setHighlightRoomIds,
      setSelectedRoomId,
      setStats,
      setRejectedCandidates,
      setViolationSummary,
      setSolverIdentity,
    ],
  );

  const onSaveProject = useCallback(async () => {
    if (!program) {
      setError("请先 Generate 再保存");
      return;
    }
    setProjectBusy(true);
    setError(null);
    try {
      const schema_versions = buildSchemaVersions(solverIdentity, candidates);
      const saved = await saveProject({
        name: projectName.trim() || "未命名项目",
        id: projectId,
        payload: {
          form,
          program,
          requirement_spec: resolveCanonicalSpec(),
          locks: cloneLayoutLocks(locks),
          candidates,
          selected_id: selectedId,
          compare_id: compareId,
          schema_versions,
        },
      });
      setProjectId(saved.id);
      setProjectName(saved.name);
      // 仅保存不得清除 mismatch；用服务端回传判断
      if (saved.evaluation_version_mismatch) {
        setVersionHint(
          `评价版本已变（快照 ${saved.payload.schema_versions?.evaluation_version ?? "?"} → 当前 ${saved.current_evaluation_version}）：分数可能不可比；布局几何仍按快照。`,
        );
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setProjectBusy(false);
    }
  }, [
    program,
    projectName,
    projectId,
    form,
    locks,
    candidates,
    selectedId,
    compareId,
    solverIdentity,
    resolveCanonicalSpec,
    setError,
  ]);

  const onLoadProject = useCallback(
    async (id: string) => {
      setProjectBusy(true);
      setError(null);
      try {
        const detail = await loadProject(id);
        applyProjectDetail(detail);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setProjectBusy(false);
      }
    },
    [applyProjectDetail, setError],
  );

  const onExportPlanseed = useCallback(async () => {
    if (!program) {
      setError("请先 Generate 再导出项目包");
      return;
    }
    setProjectBusy(true);
    setError(null);
    try {
      const schema_versions = buildSchemaVersions(solverIdentity, candidates);
      const saved = await saveProject({
        name: projectName.trim() || "未命名项目",
        id: projectId,
        payload: {
          form,
          program,
          requirement_spec: resolveCanonicalSpec(),
          locks: cloneLayoutLocks(locks),
          candidates,
          selected_id: selectedId,
          compare_id: compareId,
          schema_versions,
        },
      });
      setProjectId(saved.id);
      setProjectName(saved.name);
      const out = await exportPlanseedPackage(saved.id);
      downloadBlob(out.blob, out.filename);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setProjectBusy(false);
    }
  }, [
    program,
    projectName,
    projectId,
    form,
    locks,
    candidates,
    selectedId,
    compareId,
    solverIdentity,
    resolveCanonicalSpec,
    setError,
  ]);

  const onImportPlanseed = useCallback(
    async (file: File) => {
      setProjectBusy(true);
      setError(null);
      try {
        const detail = await importPlanseedPackage(file);
        applyProjectDetail(detail);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setProjectBusy(false);
      }
    },
    [applyProjectDetail, setError],
  );

  const onOpenProjects = useCallback(async () => {
    setProjectBusy(true);
    setError(null);
    try {
      const list = await listProjects();
      setProjectPicker(list);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setProjectBusy(false);
    }
  }, [setError]);

  return {
    projectId,
    setProjectId,
    projectName,
    setProjectName,
    projectBusy,
    versionHint,
    setVersionHint,
    projectPicker,
    setProjectPicker,
    applyProjectDetail,
    onSaveProject,
    onLoadProject,
    onExportPlanseed,
    onImportPlanseed,
    onOpenProjects,
  };
}
