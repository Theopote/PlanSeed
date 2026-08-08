//! 引擎生命周期：状态机 / spawn / retry / watch。
//!
//! ownership：MANAGED（Child watcher）| REUSED（health monitor；不 kill）。

use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::thread;

use serde::Serialize;
use tauri::{Emitter, Manager, State};

use super::logging::append_engine_log;
use super::probe::{
    engine_host, preferred_port, probe_engine, suggest_port, wait_for_engine, PortIdentity,
    ATTEMPT_HEALTH_TIMEOUT, MAX_SPAWN_ATTEMPTS,
};
use super::process::{
    kill_backend, kill_child_owned, repo_root_from_manifest, spawn_dev_backend,
    spawn_release_backend, BackendChild,
};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum EngineOwnership {
    Managed,
    Reused,
}

pub struct EngineMeta {
    pub url: Mutex<String>,
    /// 防止并发 spawn / retry 叠成 restart loop
    pub spawning: AtomicBool,
    pub ownership: Mutex<Option<EngineOwnership>>,
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum EngineLifecycle {
    Starting,
    Ready,
    Error,
    Stopped,
}

#[derive(Clone, Serialize)]
pub struct EngineStatusPayload {
    pub status: EngineLifecycle,
    pub url: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ownership: Option<EngineOwnership>,
}

pub fn emit_status(handle: &tauri::AppHandle, payload: EngineStatusPayload) {
    // 唯一事实源：engine-status（不发 engine-ready）
    if let Err(e) = handle.emit("engine-status", &payload) {
        log::warn!("emit engine-status failed: {e}");
    }
}

fn set_engine_url(meta: &EngineMeta, url: &str) {
    if let Ok(mut g) = meta.url.lock() {
        *g = url.to_string();
    }
}

fn set_ownership(meta: &EngineMeta, ownership: EngineOwnership) {
    if let Ok(mut g) = meta.ownership.lock() {
        *g = Some(ownership);
    }
}

fn clear_ownership(meta: &EngineMeta) {
    if let Ok(mut g) = meta.ownership.lock() {
        *g = None;
    }
}

fn current_ownership(meta: &EngineMeta) -> Option<EngineOwnership> {
    meta.ownership.lock().ok().and_then(|g| *g)
}

fn ready_payload(url: String, ownership: EngineOwnership) -> EngineStatusPayload {
    EngineStatusPayload {
        status: EngineLifecycle::Ready,
        url,
        error: None,
        ownership: Some(ownership),
    }
}

pub fn watch_child_exit(handle: tauri::AppHandle, url: String) {
    thread::spawn(move || {
        loop {
            thread::sleep(std::time::Duration::from_millis(800));
            let exited = {
                let state = handle.state::<BackendChild>();
                let Ok(mut guard) = state.0.lock() else {
                    continue;
                };
                match guard.as_mut() {
                    Some(child) => match child.try_wait() {
                        Ok(Some(status)) => {
                            let _ = guard.take();
                            Some(format!("engine process exited ({status})"))
                        }
                        Ok(None) => None,
                        Err(e) => {
                            let _ = guard.take();
                            Some(format!("engine wait error: {e}"))
                        }
                    },
                    None => {
                        // 无托管子进程（REUSED）→ 交给 watch_reused_health
                        return;
                    }
                }
            };
            if let Some(msg) = exited {
                append_engine_log(&handle, &format!("fatal: {msg}"));
                clear_ownership(handle.state::<EngineMeta>().inner());
                emit_status(
                    &handle,
                    EngineStatusPayload {
                        status: EngineLifecycle::Error,
                        url: url.clone(),
                        error: Some(msg),
                        ownership: Some(EngineOwnership::Managed),
                    },
                );
                return;
            }
        }
    });
}

/// REUSED：连续失败才 ERROR；不 kill 外进程。
pub fn watch_reused_health(handle: tauri::AppHandle, host: String, port: u16, url: String) {
    const FAIL_THRESHOLD: u32 = 3;
    thread::spawn(move || {
        let mut consecutive_failures: u32 = 0;
        loop {
            thread::sleep(std::time::Duration::from_secs(2));
            let has_child = {
                let state = handle.state::<BackendChild>();
                let locked = state.0.lock();
                let flag = match locked {
                    Ok(guard) => guard.is_some(),
                    Err(_) => false,
                };
                flag
            };
            if has_child {
                return;
            }
            // 若 ownership 已切到 MANAGED，退出
            if current_ownership(handle.state::<EngineMeta>().inner())
                == Some(EngineOwnership::Managed)
            {
                return;
            }
            match probe_engine(&host, port) {
                PortIdentity::PlanseedEngine => {
                    consecutive_failures = 0;
                }
                lost => {
                    consecutive_failures = consecutive_failures.saturating_add(1);
                    if consecutive_failures < FAIL_THRESHOLD {
                        log::warn!(
                            "reused engine probe miss ({lost:?}) {consecutive_failures}/{FAIL_THRESHOLD}"
                        );
                        continue;
                    }
                    let msg = format!("reused engine lost ({lost:?}) at {url}");
                    append_engine_log(&handle, &format!("fatal: {msg}"));
                    clear_ownership(handle.state::<EngineMeta>().inner());
                    emit_status(
                        &handle,
                        EngineStatusPayload {
                            status: EngineLifecycle::Error,
                            url: url.clone(),
                            error: Some(msg),
                            ownership: Some(EngineOwnership::Reused),
                        },
                    );
                    return;
                }
            }
        }
    });
}

/// 选 port → spawn 或 reuse → health 失败则换 port。
pub fn spawn_engine_with_retry(
    handle: &tauri::AppHandle,
    host: &str,
    preferred: u16,
    root: &Path,
    // retry 时若仍探测到健康 PlanSeed，允许继续 REUSED；否则强制自启
    allow_reuse: bool,
) {
    let meta = handle.state::<EngineMeta>();
    if meta
        .spawning
        .compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst)
        .is_err()
    {
        log::warn!("spawn already in progress; ignore");
        return;
    }

    let h = handle.clone();
    let host = host.to_string();
    let root = root.to_path_buf();
    let debug = cfg!(debug_assertions);

    thread::spawn(move || {
        let preferred_url = format!("http://{host}:{preferred}");
        emit_status(
            &h,
            EngineStatusPayload {
                status: EngineLifecycle::Starting,
                url: preferred_url.clone(),
                error: None,
                ownership: None,
            },
        );
        append_engine_log(
            &h,
            &format!(
                "startup host={host} preferred_port={preferred} debug={debug} allow_reuse={allow_reuse}"
            ),
        );

        let mut last_error = String::from("engine failed to start");

        for attempt in 0..MAX_SPAWN_ATTEMPTS {
            let port = suggest_port(&host, preferred, attempt);

            match probe_engine(&host, port) {
                PortIdentity::PlanseedEngine if allow_reuse => {
                    let url = format!("http://{host}:{port}");
                    let meta = h.state::<EngineMeta>();
                    set_engine_url(meta.inner(), &url);
                    set_ownership(meta.inner(), EngineOwnership::Reused);
                    append_engine_log(&h, &format!("REUSED PLANSEED_ENGINE at {url}"));
                    emit_status(&h, ready_payload(url.clone(), EngineOwnership::Reused));
                    watch_reused_health(h.clone(), host.clone(), port, url);
                    meta.spawning.store(false, Ordering::SeqCst);
                    return;
                }
                PortIdentity::PlanseedEngine => {
                    // retry 且不允许 reuse（或已判定 unhealthy 后应换口）→ 跳过该口
                    append_engine_log(
                        &h,
                        &format!("skip occupied PLANSEED port={port} (force managed spawn)"),
                    );
                    continue;
                }
                PortIdentity::ForeignService => {
                    log::warn!("port {port} FOREIGN_SERVICE; skip attempt {attempt}");
                    append_engine_log(&h, &format!("skip FOREIGN port={port} attempt={attempt}"));
                    continue;
                }
                PortIdentity::PortFree => {}
            }

            let url = format!("http://{host}:{port}");
            set_engine_url(h.state::<EngineMeta>().inner(), &url);
            append_engine_log(&h, &format!("spawn MANAGED attempt={attempt} port={port}"));

            let spawned = if debug {
                spawn_dev_backend(&root, &host, port)
            } else {
                spawn_release_backend(&h, &host, port)
            };

            match spawned {
                Ok(mut child) => {
                    let ready =
                        wait_for_engine(&host, port, &mut child, ATTEMPT_HEALTH_TIMEOUT);
                    if ready {
                        *h.state::<BackendChild>().0.lock().expect("child") = Some(child);
                        set_ownership(
                            h.state::<EngineMeta>().inner(),
                            EngineOwnership::Managed,
                        );
                        append_engine_log(&h, &format!("MANAGED ready port={port} url={url}"));
                        emit_status(
                            &h,
                            ready_payload(url.clone(), EngineOwnership::Managed),
                        );
                        watch_child_exit(h.clone(), url);
                        h.state::<EngineMeta>()
                            .spawning
                            .store(false, Ordering::SeqCst);
                        return;
                    }
                    last_error = format!(
                        "port {port}: backend exited or /api/health identity not ready"
                    );
                    append_engine_log(&h, &format!("fatal: {last_error}"));
                    kill_child_owned(&mut child);
                }
                Err(e) => {
                    last_error = e;
                    append_engine_log(&h, &format!("fatal: spawn failed: {last_error}"));
                }
            }
        }

        clear_ownership(h.state::<EngineMeta>().inner());
        emit_status(
            &h,
            EngineStatusPayload {
                status: EngineLifecycle::Error,
                url: preferred_url,
                error: Some(last_error),
                ownership: None,
            },
        );
        h.state::<EngineMeta>()
            .spawning
            .store(false, Ordering::SeqCst);
    });
}

#[tauri::command]
pub fn get_engine_url(meta: State<'_, EngineMeta>) -> String {
    meta.url.lock().expect("engine url").clone()
}

/// Retry：MANAGED → kill child 再 spawn；REUSED 仍健康 → 继续 reuse；否则 probe → spawn。
#[tauri::command]
pub fn retry_engine(app: tauri::AppHandle) -> Result<(), String> {
    let host = engine_host();
    let preferred = preferred_port();
    let ownership = current_ownership(app.state::<EngineMeta>().inner());
    append_engine_log(
        &app,
        &format!("user retry_engine ownership={ownership:?}"),
    );

    match ownership {
        Some(EngineOwnership::Managed) => {
            kill_backend(app.state::<BackendChild>().inner());
            clear_ownership(app.state::<EngineMeta>().inner());
            let root = repo_root_from_manifest();
            spawn_engine_with_retry(&app, &host, preferred, &root, false);
        }
        Some(EngineOwnership::Reused) => {
            // 不 kill 外部进程
            match probe_engine(&host, preferred) {
                PortIdentity::PlanseedEngine => {
                    let url = format!("http://{host}:{preferred}");
                    set_engine_url(app.state::<EngineMeta>().inner(), &url);
                    set_ownership(
                        app.state::<EngineMeta>().inner(),
                        EngineOwnership::Reused,
                    );
                    append_engine_log(&app, &format!("retry: REUSED still healthy at {url}"));
                    // 已有 watch_reused_health；只刷新 READY，避免叠监视线程
                    emit_status(&app, ready_payload(url, EngineOwnership::Reused));
                }
                identity => {
                    append_engine_log(
                        &app,
                        &format!("retry: REUSED unhealthy ({identity:?}) → spawn MANAGED"),
                    );
                    clear_ownership(app.state::<EngineMeta>().inner());
                    let root = repo_root_from_manifest();
                    spawn_engine_with_retry(&app, &host, preferred, &root, false);
                }
            }
        }
        None => {
            kill_backend(app.state::<BackendChild>().inner());
            let root = repo_root_from_manifest();
            // 初始 / 未知：允许发现已有健康引擎并 reuse
            spawn_engine_with_retry(&app, &host, preferred, &root, true);
        }
    }
    Ok(())
}
