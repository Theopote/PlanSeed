import {
  useCallback,
  type Dispatch,
  type SetStateAction,
} from "react";
import {
  downloadBlob,
  exportPng,
  exportReportJson,
  exportSvg,
  saveProject,
  type CandidatePayload,
  type LayoutLocks,
  type PngExportSize,
  type ProgramSummary,
  type RequirementForm,
  type RequirementSpecPayload,
  type SvgExportScope,
} from "../api/client";
import type { SolverIdentity } from "./useCandidateWorkflow";
import { buildSchemaVersions, cloneLayoutLocks } from "./sessionHelpers";

export type UseExportWorkflowArgs = {
  setError: Dispatch<SetStateAction<string | null>>;
  setReportBusy: Dispatch<SetStateAction<boolean>>;
  form: RequirementForm;
  program: ProgramSummary | null;
  locks: LayoutLocks;
  candidates: CandidatePayload[];
  selectedId: string | null;
  selectedRoomId: string | null;
  compareId: string | null;
  projectId: string | null;
  setProjectId: Dispatch<SetStateAction<string | null>>;
  projectName: string;
  setProjectName: Dispatch<SetStateAction<string>>;
  solverIdentity: SolverIdentity | null;
  resolveCanonicalSpec: () => RequirementSpecPayload | null;
};

export function useExportWorkflow({
  setError,
  setReportBusy,
  form,
  program,
  locks,
  candidates,
  selectedId,
  selectedRoomId,
  compareId,
  projectId,
  setProjectId,
  projectName,
  setProjectName,
  solverIdentity,
  resolveCanonicalSpec,
}: UseExportWorkflowArgs) {
  const onExportSvg = useCallback(
    async (scope: SvgExportScope) => {
      if (!program || candidates.length === 0) {
        setError("请先 Generate 再导出 SVG");
        return;
      }
      if (!selectedId) {
        setError("请先选择要导出的候选");
        return;
      }
      const selected = candidates.find((c) => c.id === selectedId);
      if (selected?.revision_status === "dirty") {
        setError(
          "方案已修改，评价结果已过期。请先重新验证后再导出 SVG。",
        );
        return;
      }
      setReportBusy(true);
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
        const stored = saved.payload.candidates?.find((c) => c.id === selectedId);
        const revisionId =
          stored?.revision_id ?? selected?.revision_id ?? selectedId;
        let floorId: string | undefined;
        if (scope === "floor") {
          const fromRoom = selected?.placements?.find(
            (p) => p.room_id === selectedRoomId,
          )?.floor_id;
          floorId =
            fromRoom ??
            program.floors[0]?.id ??
            (selected?.floor_svgs
              ? Object.keys(selected.floor_svgs)[0]
              : undefined) ??
            "F1";
        }
        const out = await exportSvg({
          projectId: saved.id,
          candidateId: selectedId,
          revisionId,
          scope,
          floorId,
        });
        downloadBlob(out.blob, out.filename);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setReportBusy(false);
      }
    },
    [
      program,
      candidates,
      projectName,
      projectId,
      selectedId,
      selectedRoomId,
      form,
      locks,
      compareId,
      solverIdentity,
      resolveCanonicalSpec,
      setProjectId,
      setProjectName,
      setReportBusy,
      setError,
    ],
  );

  const onExportPng = useCallback(
    async (scope: SvgExportScope, size: PngExportSize) => {
      if (!program || candidates.length === 0) {
        setError("请先 Generate 再导出 PNG");
        return;
      }
      if (!selectedId) {
        setError("请先选择要导出的候选");
        return;
      }
      const selected = candidates.find((c) => c.id === selectedId);
      if (selected?.revision_status === "dirty") {
        setError(
          "方案已修改，评价结果已过期。请先重新验证后再导出 PNG。",
        );
        return;
      }
      setReportBusy(true);
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
        const stored = saved.payload.candidates?.find((c) => c.id === selectedId);
        const revisionId =
          stored?.revision_id ?? selected?.revision_id ?? selectedId;
        let floorId: string | undefined;
        if (scope === "floor") {
          const fromRoom = selected?.placements?.find(
            (p) => p.room_id === selectedRoomId,
          )?.floor_id;
          floorId =
            fromRoom ??
            program.floors[0]?.id ??
            (selected?.floor_svgs
              ? Object.keys(selected.floor_svgs)[0]
              : undefined) ??
            "F1";
        }
        const out = await exportPng({
          projectId: saved.id,
          candidateId: selectedId,
          revisionId,
          scope,
          floorId,
          size,
        });
        downloadBlob(out.blob, out.filename);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setReportBusy(false);
      }
    },
    [
      program,
      candidates,
      projectName,
      projectId,
      selectedId,
      selectedRoomId,
      form,
      locks,
      compareId,
      solverIdentity,
      resolveCanonicalSpec,
      setProjectId,
      setProjectName,
      setReportBusy,
      setError,
    ],
  );

  const onExportReportJson = useCallback(async () => {
    if (!program || candidates.length === 0) {
      setError("请先 Generate 再导出 DesignReport JSON");
      return;
    }
    if (!selectedId) {
      setError("请先选择要导出的候选");
      return;
    }
    const selected = candidates.find((c) => c.id === selectedId);
    if (selected?.revision_status === "dirty") {
      setError(
        "方案已修改，评价结果已过期。请先重新验证后再导出 JSON。",
      );
      return;
    }
    setReportBusy(true);
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
      const stored = saved.payload.candidates?.find((c) => c.id === selectedId);
      const revisionId =
        stored?.revision_id ?? selected?.revision_id ?? selectedId;
      const out = await exportReportJson({
        projectId: saved.id,
        candidateId: selectedId,
        revisionId,
        includeSvg: true,
      });
      downloadBlob(out.blob, out.filename);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setReportBusy(false);
    }
  }, [
    program,
    candidates,
    projectName,
    projectId,
    selectedId,
    form,
    locks,
    compareId,
    solverIdentity,
    resolveCanonicalSpec,
    setProjectId,
    setProjectName,
    setReportBusy,
    setError,
  ]);

  return {
    onExportSvg,
    onExportPng,
    onExportReportJson,
  };
}
