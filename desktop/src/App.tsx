import { useCallback, useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import type {
  LayoutLocks,
  ProgramSummary,
} from "./api/client";
import { CandidateStrip } from "./components/CandidateStrip";
import { ReportPreview } from "./components/ReportPreview";
import { FloorplanView } from "./components/FloorplanView";
import { Inspector } from "./components/Inspector";
import { RequirementsPanel } from "./components/RequirementsPanel";
import {
  useCandidateWorkflow,
  useEngineSession,
  useExportWorkflow,
  useMutationWorkflow,
  useProjectSession,
  useReportWorkflow,
  useRequirementWorkflow,
} from "./hooks";
import "./App.css";

function App() {
  const [error, setError] = useState<string | null>(null);

  const engine = useEngineSession();

  // 跨 hook 依赖：requirement 需在 candidate 之前调用，经 ref 桥接 program/locks
  const programBridge = useRef<{
    getProgram: () => ProgramSummary | null;
    setProgram: Dispatch<SetStateAction<ProgramSummary | null>>;
    setLocks: Dispatch<SetStateAction<LayoutLocks>>;
  }>({
    getProgram: () => null,
    setProgram: () => {},
    setLocks: () => {},
  });

  const getProgram = useCallback(
    () => programBridge.current.getProgram(),
    [],
  );
  const setProgramBridge = useCallback<
    Dispatch<SetStateAction<ProgramSummary | null>>
  >((v) => programBridge.current.setProgram(v), []);
  const setLocksBridge = useCallback<Dispatch<SetStateAction<LayoutLocks>>>(
    (v) => programBridge.current.setLocks(v),
    [],
  );

  const requirement = useRequirementWorkflow({
    setError,
    getProgram,
    setProgram: setProgramBridge,
    setLocks: setLocksBridge,
    setLlmSessionState: engine.setLlmSessionState,
    setLlmStatus: engine.setLlmStatus,
  });

  // candidate.applyResult 需清 mutationHint；mutation hook 稍后挂载
  const mutationHintBridge = useRef<
    Dispatch<SetStateAction<string | null>>
  >(() => {});
  const setMutationHintBridge = useCallback<
    Dispatch<SetStateAction<string | null>>
  >((v) => mutationHintBridge.current(v), []);

  const candidate = useCandidateWorkflow({
    setError,
    form: requirement.form,
    setRequirementSpec: requirement.setRequirementSpec,
    resolveCanonicalSpec: requirement.resolveCanonicalSpec,
    nlText: requirement.nlText,
    setNlBusy: requirement.setNlBusy,
    setNlHint: requirement.setNlHint,
    applyParsedSpec: requirement.applyParsedSpec,
    setLlmSessionState: engine.setLlmSessionState,
    setLlmStatus: engine.setLlmStatus,
    setMutationHint: setMutationHintBridge,
  });

  programBridge.current = {
    getProgram: () => candidate.program,
    setProgram: candidate.setProgram,
    setLocks: candidate.setLocks,
  };

  // mutation.onRevalidate 清 versionHint；project hook 稍后挂载
  const versionHintBridge = useRef<Dispatch<SetStateAction<string | null>>>(
    () => {},
  );
  const setVersionHintBridge = useCallback<
    Dispatch<SetStateAction<string | null>>
  >((v) => versionHintBridge.current(v), []);

  const mutation = useMutationWorkflow({
    setError,
    selected: candidate.selected,
    selectedId: candidate.selectedId,
    program: candidate.program,
    locks: candidate.locks,
    setLocks: candidate.setLocks,
    candidates: candidate.candidates,
    setCandidates: candidate.setCandidates,
    resolveCanonicalSpec: requirement.resolveCanonicalSpec,
    setSolverIdentity: candidate.setSolverIdentity,
    setVersionHint: setVersionHintBridge,
  });

  mutationHintBridge.current = mutation.setMutationHint;

  const project = useProjectSession({
    setError,
    form: requirement.form,
    setForm: requirement.setForm,
    program: candidate.program,
    setProgram: candidate.setProgram,
    setRequirementSpec: requirement.setRequirementSpec,
    setNlText: requirement.setNlText,
    locks: candidate.locks,
    setLocks: candidate.setLocks,
    candidates: candidate.candidates,
    setCandidates: candidate.setCandidates,
    selectedId: candidate.selectedId,
    setSelectedId: candidate.setSelectedId,
    compareId: candidate.compareId,
    setCompareId: candidate.setCompareId,
    setHighlightRoomIds: candidate.setHighlightRoomIds,
    setSelectedRoomId: candidate.setSelectedRoomId,
    setStats: candidate.setStats,
    setRejectedCandidates: candidate.setRejectedCandidates,
    setViolationSummary: candidate.setViolationSummary,
    solverIdentity: candidate.solverIdentity,
    setSolverIdentity: candidate.setSolverIdentity,
    resolveCanonicalSpec: requirement.resolveCanonicalSpec,
  });

  versionHintBridge.current = project.setVersionHint;

  const report = useReportWorkflow({
    setError,
    form: requirement.form,
    program: candidate.program,
    locks: candidate.locks,
    candidates: candidate.candidates,
    selectedId: candidate.selectedId,
    compareId: candidate.compareId,
    projectId: project.projectId,
    setProjectId: project.setProjectId,
    projectName: project.projectName,
    setProjectName: project.setProjectName,
    solverIdentity: candidate.solverIdentity,
    resolveCanonicalSpec: requirement.resolveCanonicalSpec,
  });

  const exportWf = useExportWorkflow({
    setError,
    setReportBusy: report.setReportBusy,
    form: requirement.form,
    program: candidate.program,
    locks: candidate.locks,
    candidates: candidate.candidates,
    selectedId: candidate.selectedId,
    selectedRoomId: candidate.selectedRoomId,
    compareId: candidate.compareId,
    projectId: project.projectId,
    setProjectId: project.setProjectId,
    projectName: project.projectName,
    setProjectName: project.setProjectName,
    solverIdentity: candidate.solverIdentity,
    resolveCanonicalSpec: requirement.resolveCanonicalSpec,
  });

  const emptyHint =
    engine.engineStatus === "ERROR"
      ? engine.engineHint || "本地引擎异常，请重试"
      : engine.engineStatus === "STARTING"
        ? "正在连接本地引擎…"
        : engine.engineStatus === "STOPPED"
          ? "引擎已停止"
          : "Generate → 拖拽/锁定 → Regenerate unlocked / Create Variant → Alt+点比较";

  return (
    <div className="app-shell">
      {project.projectPicker !== null && (
        <div className="project-picker-backdrop" role="presentation">
          <div className="project-picker" role="dialog" aria-label="打开项目">
            <header className="project-picker-head">
              <h3>打开项目</h3>
              <button
                type="button"
                className="secondary"
                onClick={() => project.setProjectPicker(null)}
              >
                关闭
              </button>
            </header>
            {project.projectPicker.length === 0 ? (
              <p className="muted">尚无已保存项目</p>
            ) : (
              <ul className="project-picker-list">
                {project.projectPicker.map((p) => (
                  <li key={p.id}>
                    <button
                      type="button"
                      className="project-picker-item"
                      disabled={project.projectBusy}
                      onClick={() => void project.onLoadProject(p.id)}
                    >
                      <span className="project-picker-name">{p.name}</span>
                      <span className="muted project-picker-time">
                        {p.updated_at.slice(0, 19).replace("T", " ")}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
      {report.reportHtml ? (
        <ReportPreview
          html={report.reportHtml}
          title={`${project.projectName.trim() || "未命名"} · 设计报告`}
          onClose={() => report.setReportHtml(null)}
        />
      ) : null}
      <div className="app-main">
        <RequirementsPanel
          form={requirement.form}
          onChange={requirement.setForm}
          onGenerate={() => void candidate.run("form")}
          onBenchmark={() => void candidate.run("benchmark")}
          nlText={requirement.nlText}
          onNlTextChange={requirement.setNlText}
          onParseNl={() => void requirement.onParseNl()}
          onParseAndGenerate={() => void candidate.onParseAndGenerate()}
          nlBusy={requirement.nlBusy}
          nlHint={requirement.nlHint}
          loading={candidate.loading}
          engineStatus={engine.engineStatus}
          onRetryEngine={() => void engine.onRetryEngine()}
          llmState={engine.displayLlmState}
          llmModel={engine.llmStatus?.model ?? null}
          llmDetail={engine.llmStatus?.detail ?? null}
          program={candidate.program}
          requirementSpec={requirement.requirementSpec}
          onUpdateAssumption={requirement.onUpdateAssumption}
          onRemoveAssumption={requirement.onRemoveAssumption}
          onDismissUnknown={requirement.onDismissUnknown}
          error={error ?? engine.engineHint}
          stats={candidate.stats}
          rejectedCandidates={candidate.rejectedCandidates}
          violationSummary={candidate.violationSummary}
          projectName={project.projectName}
          onProjectNameChange={project.setProjectName}
          onSaveProject={() => void project.onSaveProject()}
          onExportPlanseed={() => void project.onExportPlanseed()}
          onImportPlanseed={(file) => void project.onImportPlanseed(file)}
          onExportReport={() => void report.onExportReport()}
          onExportReportJson={() => void exportWf.onExportReportJson()}
          onExportSvg={(scope) => void exportWf.onExportSvg(scope)}
          onExportPng={(scope, size) => void exportWf.onExportPng(scope, size)}
          onOpenProjects={() => void project.onOpenProjects()}
          projectBusy={project.projectBusy}
          reportBusy={report.reportBusy}
          versionHint={project.versionHint}
        />
        <FloorplanView
          svg={candidate.selected?.svg ?? null}
          emptyHint={emptyHint}
          highlightRoomIds={candidate.highlightRoomIds}
          selectedRoomId={candidate.selectedRoomId}
          lockedRoomIds={[
            ...candidate.locks.rooms.map((r) => r.room_id),
            ...candidate.lockedZoneRoomIds,
            ...(candidate.locks.stair
              ? (candidate.selected?.placements
                  ?.filter((p) => p.room_id.startsWith("stair-"))
                  .map((p) => p.room_id) ?? [])
              : []),
          ]}
          placements={candidate.selected?.placements}
          floorIds={candidate.program?.floors.map((f) => f.id)}
          floorWidth={candidate.program?.site_width}
          floorDepth={candidate.program?.site_depth}
          snapModule={0.3}
          onSelectRoom={candidate.onSelectRoom}
          onProposeMove={candidate.program ? mutation.onProposeMove : undefined}
          onProposeWall={candidate.program ? mutation.onProposeWall : undefined}
          onLivePreview={candidate.program ? mutation.onLivePreview : undefined}
          onLiveWallPreview={
            candidate.program ? mutation.onLiveWallPreview : undefined
          }
          mutationHint={mutation.mutationHint}
        />
        <Inspector
          candidate={candidate.selected}
          compareWith={candidate.compareWith}
          program={candidate.program}
          selectedRoomId={candidate.selectedRoomId}
          highlightRoomIds={candidate.highlightRoomIds}
          locks={candidate.locks}
          lockCount={candidate.lockCount}
          onHighlightRooms={candidate.setHighlightRoomIds}
          onSelectRoom={candidate.onSelectRoom}
          onSelectZone={candidate.onSelectZone}
          onClearCompare={() => candidate.setCompareId(null)}
          onUpdateRoomTargetArea={requirement.onUpdateRoomTargetArea}
          onToggleRoomLock={candidate.onToggleRoomLock}
          onToggleZoneLock={candidate.onToggleZoneLock}
          onClearLocks={candidate.onClearLocks}
          onRegenerate={() => void candidate.run("program")}
          onCreateVariant={() => void candidate.run("variant")}
          onRevalidate={() => void mutation.onRevalidate()}
          regenerating={candidate.loading}
          revalidating={mutation.revalidating}
          canRegenerate={
            !!candidate.program && engine.engineStatus === "READY"
          }
        />
      </div>
      <CandidateStrip
        candidates={candidate.candidates}
        selectedId={candidate.selectedId}
        compareId={candidate.compareId}
        onSelect={candidate.onSelectCandidate}
        onComparePick={candidate.onComparePick}
        onClearCompare={() => candidate.setCompareId(null)}
      />
    </div>
  );
}

export default App;
