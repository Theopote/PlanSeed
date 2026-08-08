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
    let attempts = 0;
    async function ping() {
      const ok = await checkHealth();
      if (cancelled) return;
      setApiOk(ok);
      // 启动期加快轮询；就绪后降频
      attempts += 1;
      if (!ok && attempts < 40) {
        window.setTimeout(() => {
          if (!cancelled) void ping();
        }, 500);
      }
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
              ? "本地引擎未就绪。请从仓库根目录运行 pnpm dev（或等待 Tauri 自动拉起）"
              : apiOk === null
                ? "正在连接本地引擎…"
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
