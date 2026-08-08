//! 本地引擎 runtime：探针 / 进程 / 生命周期 / 日志。
//!
//! ownership：MANAGED（Tauri 子进程）| REUSED（外部 PlanSeed，不 kill）。

mod lifecycle;
mod logging;
mod probe;
mod process;

pub use lifecycle::{
    emit_status, get_engine_url, retry_engine, spawn_engine_with_retry, watch_reused_health,
    EngineLifecycle, EngineMeta, EngineOwnership, EngineStatusPayload,
};
pub use logging::append_engine_log;
pub use probe::{engine_host, preferred_port, probe_engine, PortIdentity};
pub use process::{kill_backend, repo_root_from_manifest, BackendChild};
