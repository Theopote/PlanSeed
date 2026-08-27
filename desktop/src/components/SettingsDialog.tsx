import { useCallback, useEffect, useRef, useState } from "react";
import type {
  LlmSettingsPayload,
  OllamaModelsPayload,
  SettingsPayload,
} from "../api/client";

export type SettingsDialogProps = {
  open: boolean;
  busy?: boolean;
  engineReady?: boolean;
  onClose: () => void;
  onLoad: () => Promise<SettingsPayload>;
  onSave: (llm: LlmSettingsPayload) => Promise<void>;
  onProbeModels: (
    baseUrl: string,
    allowRemote: boolean,
  ) => Promise<OllamaModelsPayload>;
};

const DEFAULT_LLM: LlmSettingsPayload = {
  provider: "ollama",
  ollama_base_url: "http://127.0.0.1:11434",
  ollama_model: "qwen2.5:7b",
  ollama_timeout_s: 120,
  ollama_allow_remote: false,
};

/**
 * 应用设置 — Ollama / 模型 / 超时（local-first，无云端 API Key）。
 */
export function SettingsDialog({
  open,
  busy = false,
  engineReady = false,
  onClose,
  onLoad,
  onSave,
  onProbeModels,
}: SettingsDialogProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const [draft, setDraft] = useState<LlmSettingsPayload>(DEFAULT_LLM);
  const [settingsPath, setSettingsPath] = useState<string>("");
  const [envOverrides, setEnvOverrides] = useState<Record<string, boolean>>({});
  const [persisted, setPersisted] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [models, setModels] = useState<string[]>([]);
  const [modelsDetail, setModelsDetail] = useState<string | null>(null);
  const [probing, setProbing] = useState(false);
  const [loading, setLoading] = useState(false);

  const refreshModels = useCallback(
    async (llm: LlmSettingsPayload) => {
      if (llm.provider !== "ollama") {
        setModels([]);
        setModelsDetail(null);
        return;
      }
      setProbing(true);
      try {
        const result = await onProbeModels(
          llm.ollama_base_url,
          llm.ollama_allow_remote,
        );
        setModels(result.models);
        setModelsDetail(result.reachable ? null : result.detail);
      } catch (e) {
        setModels([]);
        setModelsDetail(e instanceof Error ? e.message : String(e));
      } finally {
        setProbing(false);
      }
    },
    [onProbeModels],
  );

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    setSaveError(null);
    void onLoad()
      .then((settings) => {
        if (cancelled) return;
        setDraft(settings.llm);
        setSettingsPath(settings.settings_path);
        setEnvOverrides(settings.env_overrides);
        setPersisted(settings.persisted);
        void refreshModels(settings.llm);
      })
      .catch((e) => {
        if (cancelled) return;
        setLoadError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, onLoad, refreshModels]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy && !loading) onClose();
    };
    window.addEventListener("keydown", onKey);
    const focusable = panelRef.current?.querySelector<HTMLElement>(
      "input:not([disabled]), select:not([disabled]), button:not([disabled])",
    );
    focusable?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [open, busy, loading, onClose]);

  if (!open) return null;

  function patch<K extends keyof LlmSettingsPayload>(
    key: K,
    value: LlmSettingsPayload[K],
  ) {
    setDraft((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSave() {
    setSaveError(null);
    try {
      await onSave(draft);
      onClose();
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : String(e));
    }
  }

  const envHint = Object.entries(envOverrides).some(([, v]) => v);
  const showRemoteWarn =
    draft.provider === "ollama" &&
    !draft.ollama_base_url.includes("127.0.0.1") &&
    !draft.ollama_base_url.includes("localhost");

  return (
    <div
      className="export-dialog-backdrop"
      role="presentation"
      onClick={() => {
        if (!busy && !loading) onClose();
      }}
    >
      <div
        ref={panelRef}
        className="export-dialog settings-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="设置"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="export-dialog-head">
          <h3>设置</h3>
          <button
            type="button"
            className="secondary"
            onClick={onClose}
            disabled={busy || loading}
          >
            关闭
          </button>
        </header>

        <p className="export-dialog-hint muted">
          PlanSeed 为 local-first：需求解析走本机 Ollama，不连接云端 LLM API。
          保存后写入 {settingsPath || "~/.planseed/settings.json"}，无需重启引擎。
        </p>

        {envHint ? (
          <p className="warn-hint settings-env-hint">
            部分项被进程环境变量覆盖（env_overrides）；UI 保存会写入文件并更新当前进程。
          </p>
        ) : null}
        {!persisted ? (
          <p className="muted tiny settings-env-hint">尚未保存过自定义设置，当前为默认值。</p>
        ) : null}

        {loadError ? <p className="error">{loadError}</p> : null}
        {saveError ? <p className="error">{saveError}</p> : null}

        {loading ? (
          <p className="muted">加载中…</p>
        ) : (
          <form
            className="req-form settings-form"
            onSubmit={(e) => {
              e.preventDefault();
              void handleSave();
            }}
          >
            <section className="export-dialog-section" aria-label="AI 解析">
              <h4>AI 解析（Hybrid Parser）</h4>
              <label>
                Provider
                <select
                  value={draft.provider}
                  disabled={busy || !engineReady}
                  onChange={(e) => {
                    const provider = e.target.value as LlmSettingsPayload["provider"];
                    const next = { ...draft, provider };
                    setDraft(next);
                    void refreshModels(next);
                  }}
                >
                  <option value="ollama">Ollama（本机）</option>
                  <option value="mock">Mock（测试，无真实模型）</option>
                </select>
              </label>

              {draft.provider === "ollama" ? (
                <>
                  <label>
                    Ollama 地址
                    <input
                      type="url"
                      value={draft.ollama_base_url}
                      disabled={busy || !engineReady}
                      onChange={(e) =>
                        patch("ollama_base_url", e.target.value)
                      }
                      placeholder="http://127.0.0.1:11434"
                    />
                  </label>
                  <div className="settings-model-row">
                    <label>
                      模型
                      {models.length > 0 ? (
                        <select
                          value={draft.ollama_model}
                          disabled={busy || !engineReady}
                          onChange={(e) => patch("ollama_model", e.target.value)}
                        >
                          {models.map((m) => (
                            <option key={m} value={m}>
                              {m}
                            </option>
                          ))}
                          {!models.includes(draft.ollama_model) ? (
                            <option value={draft.ollama_model}>
                              {draft.ollama_model}（自定义）
                            </option>
                          ) : null}
                        </select>
                      ) : (
                        <input
                          type="text"
                          value={draft.ollama_model}
                          disabled={busy || !engineReady}
                          onChange={(e) =>
                            patch("ollama_model", e.target.value)
                          }
                          placeholder="qwen2.5:7b"
                        />
                      )}
                    </label>
                    <button
                      type="button"
                      className="secondary settings-probe-btn"
                      disabled={busy || !engineReady || probing}
                      onClick={() => void refreshModels(draft)}
                    >
                      {probing ? "探测中…" : "刷新模型列表"}
                    </button>
                  </div>
                  {modelsDetail ? (
                    <p className="muted tiny settings-probe-hint">{modelsDetail}</p>
                  ) : null}
                  <label>
                    超时（秒）
                    <input
                      type="number"
                      min={5}
                      max={600}
                      step={1}
                      value={draft.ollama_timeout_s}
                      disabled={busy || !engineReady}
                      onChange={(e) =>
                        patch("ollama_timeout_s", Number(e.target.value))
                      }
                    />
                  </label>
                  <label className="check settings-remote-check">
                    <input
                      type="checkbox"
                      checked={draft.ollama_allow_remote}
                      disabled={busy || !engineReady}
                      onChange={(e) =>
                        patch("ollama_allow_remote", e.target.checked)
                      }
                    />
                    允许非本机 Ollama（需明确知情）
                  </label>
                  {showRemoteWarn && !draft.ollama_allow_remote ? (
                    <p className="warn-hint is-live-warn">
                      当前地址非 loopback；未勾选「允许非本机」时解析将被阻止。
                    </p>
                  ) : null}
                  {draft.ollama_allow_remote && showRemoteWarn ? (
                    <p className="warn-hint is-live-warn">
                      REMOTE MODEL WARNING：数据将发往非本机 Ollama，请确认信任该端点。
                    </p>
                  ) : null}
                </>
              ) : (
                <p className="muted tiny">
                  Mock provider 仅用于开发/测试，返回预设 JSON，不调用 Ollama。
                </p>
              )}
            </section>

            <div className="settings-actions">
              <button type="submit" disabled={busy || !engineReady}>
                {busy ? "保存中…" : "保存"}
              </button>
              <button
                type="button"
                className="secondary"
                disabled={busy}
                onClick={onClose}
              >
                取消
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
