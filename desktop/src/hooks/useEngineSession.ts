import { useCallback, useEffect, useRef, useState } from "react";
import {
  checkHealth,
  fetchLlmStatus,
  resolveEngineBase,
  retryEngine,
  setApiBase,
  type EngineLifecycle,
  type LlmHealthState,
  type LlmStatusPayload,
} from "../api/client";

type EngineStatusPayload = {
  status: EngineLifecycle;
  url: string;
  error?: string;
};

export function useEngineSession() {
  const [engineStatus, setEngineStatus] = useState<EngineLifecycle>("STARTING");
  const [engineHint, setEngineHint] = useState<string | null>(null);
  const [llmStatus, setLlmStatus] = useState<LlmStatusPayload | null>(null);
  const [llmSessionState, setLlmSessionState] = useState<LlmHealthState | null>(
    null,
  );

  const engineStatusRef = useRef<EngineLifecycle>(engineStatus);
  engineStatusRef.current = engineStatus;

  const applyEngineStatus = useCallback(
    (status: EngineLifecycle, errorMsg?: string) => {
      setEngineStatus(status);
      engineStatusRef.current = status;
      if (status === "READY") {
        setEngineHint(null);
      } else if (status === "ERROR") {
        setEngineHint(errorMsg || "本地引擎异常，可点击重试");
      } else if (status === "STOPPED") {
        setEngineHint("引擎已停止");
      } else {
        setEngineHint(null);
      }
    },
    [],
  );

  useEffect(() => {
    let cancelled = false;
    let attempts = 0;
    let unlisten: (() => void) | undefined;
    let inTauri = false;

    async function boot() {
      await resolveEngineBase();

      try {
        const { listen } = await import("@tauri-apps/api/event");
        inTauri = true;
        // 唯一事实源：engine-status（不再听 engine-ready）
        unlisten = await listen<EngineStatusPayload>("engine-status", (ev) => {
          if (cancelled) return;
          const p = ev.payload;
          if (p.url) setApiBase(p.url);
          applyEngineStatus(p.status, p.error);
        });
      } catch {
        /* 浏览器模式：无 Tauri 事件，靠 health 轮询 */
      }

      // 浏览器 / 事件未到前的启动探测；Tauri 下就绪以 engine-status 为准
      async function ping() {
        const ok = await checkHealth();
        if (cancelled) return;
        if (ok) {
          if (!inTauri || engineStatusRef.current === "STARTING") {
            applyEngineStatus("READY");
          }
          return;
        }
        attempts += 1;
        if (attempts < 90) {
          window.setTimeout(() => {
            if (!cancelled) void ping();
          }, 500);
        } else if (!inTauri || engineStatusRef.current === "STARTING") {
          applyEngineStatus("ERROR", "本地引擎启动超时，请重试或检查杀毒拦截");
        }
      }
      void ping();
    }

    void boot();
    // reuse / 失联兜底：连续失败才 ERROR（自启引擎以 Rust watch_child_exit 为准）
    const HEALTH_INTERVAL_MS = 2000;
    const HEALTH_FAIL_THRESHOLD = 3;
    let consecutiveHealthFailures = 0;
    const id = window.setInterval(() => {
      void checkHealth().then((ok) => {
        if (cancelled) return;
        const cur = engineStatusRef.current;
        if (ok) {
          consecutiveHealthFailures = 0;
          if (cur === "READY" || cur === "STARTING") {
            applyEngineStatus("READY");
          }
          return;
        }
        if (cur !== "READY") {
          consecutiveHealthFailures = 0;
          return;
        }
        consecutiveHealthFailures += 1;
        if (consecutiveHealthFailures >= HEALTH_FAIL_THRESHOLD) {
          consecutiveHealthFailures = 0;
          applyEngineStatus("ERROR", "本地引擎连接中断，请重试。");
        }
      });
    }, HEALTH_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
      unlisten?.();
    };
  }, [applyEngineStatus]);

  useEffect(() => {
    if (engineStatus !== "READY") {
      setLlmStatus(null);
      setLlmSessionState(null);
      return;
    }
    let cancelled = false;
    async function refresh() {
      const status = await fetchLlmStatus();
      if (cancelled) return;
      setLlmStatus(status);
      setLlmSessionState((prev) => {
        if (prev === "ParseRunning" || prev === "ParseFailed") return prev;
        return null;
      });
    }
    void refresh();
    const id = window.setInterval(() => {
      void refresh();
    }, 8000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [engineStatus]);

  const displayLlmState: LlmHealthState | null =
    llmSessionState ?? llmStatus?.state ?? null;

  const onRetryEngine = useCallback(async () => {
    applyEngineStatus("STARTING");
    setEngineHint(null);
    try {
      await retryEngine();
      await resolveEngineBase();
    } catch (e) {
      applyEngineStatus(
        "ERROR",
        e instanceof Error ? e.message : "重试失败",
      );
    }
  }, [applyEngineStatus]);

  return {
    engineStatus,
    engineHint,
    llmStatus,
    setLlmStatus,
    llmSessionState,
    setLlmSessionState,
    displayLlmState,
    onRetryEngine,
  };
}
