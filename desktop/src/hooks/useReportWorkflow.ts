import {
  useCallback,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";
import {
  buildReport,
  saveProjectWithConflictPrompt,
  type CandidatePayload,
  type LayoutLocks,
  type ProgramSummary,
  type RequirementForm,
  type RequirementSpecPayload,
} from "../api/client";
import type { SolverIdentity } from "./useCandidateWorkflow";
import { buildSchemaVersions, cloneLayoutLocks } from "./sessionHelpers";

export type UseReportWorkflowArgs = {
  setError: Dispatch<SetStateAction<string | null>>;
  form: RequirementForm;
  program: ProgramSummary | null;
  locks: LayoutLocks;
  candidates: CandidatePayload[];
  selectedId: string | null;
  compareId: string | null;
  projectId: string | null;
  setProjectId: Dispatch<SetStateAction<string | null>>;
  projectUpdatedAt: string | null;
  setProjectUpdatedAt: Dispatch<SetStateAction<string | null>>;
  projectName: string;
  setProjectName: Dispatch<SetStateAction<string>>;
  solverIdentity: SolverIdentity | null;
  resolveCanonicalSpec: () => RequirementSpecPayload | null;
};

export function useReportWorkflow({
  setError,
  form,
  program,
  locks,
  candidates,
  selectedId,
  compareId,
  projectId,
  setProjectId,
  projectUpdatedAt,
  setProjectUpdatedAt,
  projectName,
  setProjectName,
  solverIdentity,
  resolveCanonicalSpec,
}: UseReportWorkflowArgs) {
  const [reportHtml, setReportHtml] = useState<string | null>(null);
  const [reportBusy, setReportBusy] = useState(false);

  const onExportReport = useCallback(async () => {
    if (!program || candidates.length === 0) {
      setError("请先 Generate 再导出报告");
      return;
    }
    if (!selectedId) {
      setError("请先选择要导出的候选");
      return;
    }
    const selected = candidates.find((c) => c.id === selectedId);
    if (selected?.revision_status === "dirty") {
      setError(
        "方案已修改，评价结果已过期。请先重新验证后再导出正式评价报告。",
      );
      return;
    }
    setReportBusy(true);
    setError(null);
    try {
      // 正式报告只引用已保存快照（禁止 client 任意 SVG payload）
      const schema_versions = buildSchemaVersions(solverIdentity, candidates);
      const saved = await saveProjectWithConflictPrompt({
        name: projectName.trim() || "未命名项目",
        id: projectId,
        expected_updated_at: projectId ? projectUpdatedAt : null,
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
      if (!saved) {
        setError("已取消导出");
        return;
      }
      setProjectId(saved.id);
      setProjectName(saved.name);
      setProjectUpdatedAt(saved.updated_at);
      const stored = saved.payload.candidates?.find((c) => c.id === selectedId);
      const revisionId =
        stored?.revision_id ?? selected?.revision_id ?? selectedId;
      const out = await buildReport({
        mode: "final",
        projectId: saved.id,
        candidateId: selectedId,
        revisionId,
        projectName: saved.name,
      });
      if (!out.html) {
        setError("报告未返回 HTML");
        return;
      }
      setReportHtml(out.html);
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
    projectUpdatedAt,
    selectedId,
    form,
    locks,
    compareId,
    solverIdentity,
    resolveCanonicalSpec,
    setProjectId,
    setProjectName,
    setProjectUpdatedAt,
    setError,
  ]);

  return {
    reportHtml,
    setReportHtml,
    reportBusy,
    setReportBusy,
    onExportReport,
  };
}
