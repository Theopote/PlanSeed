import { useCallback, useEffect, useState } from "react";
import {
  checkHealth,
  generateBenchmark,
  generateFromForm,
  type CandidatePayload,
  type GenerateResponse,
  type ProgramSummary,
  type RequirementForm,
} from "./api/client";
import { CandidateStrip } from "./components/CandidateStrip";
import { FloorplanView } from "./components/FloorplanView";
import { Inspector } from "./components/Inspector";
import { RequirementsPanel } from "./components/RequirementsPanel";
import "./App.css";

const DEFAULT_FORM: RequirementForm = {
  width: 11,
  depth: 13,
  floor_count: 2,
  bedrooms: 3,
  bathrooms: 2,
  has_garage: true,
  prefer_south_facing_living: true,
};

function App() {
  const [form, setForm] = useState<RequirementForm>(DEFAULT_FORM);
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [program, setProgram] = useState<ProgramSummary | null>(null);
  const [candidates, setCandidates] = useState<CandidatePayload[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [stats, setStats] = useState<{
    generated: number;
    valid: number;
    rejected: number;
  } | null>(null);

  const selected = candidates.find((c) => c.id === selectedId) ?? null;

  useEffect(() => {
    let cancelled = false;
    async function ping() {
      const ok = await checkHealth();
      if (!cancelled) setApiOk(ok);
    }
    void ping();
    const id = window.setInterval(() => void ping(), 8000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  const applyResult = useCallback((data: GenerateResponse) => {
    setProgram(data.program_summary);
    setCandidates(data.candidates);
    setStats({
      generated: data.generated,
      valid: data.valid,
      rejected: data.rejected,
    });
    setSelectedId(data.candidates[0]?.id ?? null);
    setError(null);
  }, []);

  const run = useCallback(
    async (mode: "form" | "benchmark") => {
      setLoading(true);
      setError(null);
      try {
        const data =
          mode === "benchmark"
            ? await generateBenchmark()
            : await generateFromForm(form);
        applyResult(data);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    },
    [applyResult, form],
  );

  return (
    <div className="app-shell">
      <div className="app-main">
        <RequirementsPanel
          form={form}
          onChange={setForm}
          onGenerate={() => void run("form")}
          onBenchmark={() => void run("benchmark")}
          loading={loading}
          apiOk={apiOk}
          program={program}
          error={error}
          stats={stats}
        />
        <FloorplanView
          svg={selected?.svg ?? null}
          emptyHint={
            apiOk === false
              ? "后端未连接。请先启动：uv run uvicorn backend.main:app --port 8787"
              : "点击 Generate 或「基准案例」生成平面"
          }
        />
        <Inspector candidate={selected} />
      </div>
      <CandidateStrip
        candidates={candidates}
        selectedId={selectedId}
        onSelect={setSelectedId}
      />
    </div>
  );
}

export default App;
