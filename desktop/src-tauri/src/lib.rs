//! PlanSeed Tauri shell — 异步拉起本地引擎，窗口先出，就绪后 emit。
//!
//! Engine Identity Probe（禁止仅靠 TCP open）：
//! - PORT_FREE → spawn PlanSeed（不预占端口；bind 失败则换端口重试）
//! - PLANSEED_ENGINE → reuse（须通过 /api/health 身份契约）+ health 监视
//! - FOREIGN_SERVICE → 换端口 + spawn PlanSeed
//!
//! 就绪判定：poll /api/health + identity/version（应用级），不是 TCP listen。
//! 状态：STARTING | READY | ERROR | STOPPED；唯一事件 engine-status。
//! 崩溃 / reuse health 丢失 → ERROR，用户可 Retry。

use std::fs::{self, OpenOptions};
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream, ToSocketAddrs};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

use serde::Serialize;
use serde_json::Value;
use tauri::{Emitter, Manager, RunEvent, State};

/// 与 backend/routes/health.py 对齐。
const EXPECTED_SERVICE: &str = "planseed";
const EXPECTED_API_VERSION: &str = "1";
const MAX_SPAWN_ATTEMPTS: u32 = 5;
const ATTEMPT_HEALTH_TIMEOUT: Duration = Duration::from_secs(12);

struct BackendChild(Mutex<Option<Child>>);

struct EngineMeta {
    url: Mutex<String>,
    /// 防止并发 spawn / retry 叠成 restart loop
    spawning: AtomicBool,
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "UPPERCASE")]
enum EngineLifecycle {
    Starting,
    Ready,
    Error,
    Stopped,
}

#[derive(Clone, Serialize)]
struct EngineStatusPayload {
    status: EngineLifecycle,
    url: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
}

/// 端口身份三态。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum PortIdentity {
    PortFree,
    PlanseedEngine,
    ForeignService,
}

fn repo_root_from_manifest() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .unwrap_or_else(|_| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../.."))
}

fn engine_host() -> String {
    std::env::var("PLANSEED_HOST").unwrap_or_else(|_| "127.0.0.1".into())
}

fn preferred_port() -> u16 {
    std::env::var("PLANSEED_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8787)
}

fn engine_log_path(app: &tauri::AppHandle) -> Option<PathBuf> {
    let dir = app.path().app_log_dir().ok()?;
    let _ = fs::create_dir_all(&dir);
    Some(dir.join("engine.log"))
}

fn append_engine_log(app: &tauri::AppHandle, line: &str) {
    let Some(path) = engine_log_path(app) else {
        return;
    };
    if let Ok(mut f) = OpenOptions::new().create(true).append(true).open(&path) {
        let _ = writeln!(f, "{}", line);
    }
    log::info!("[engine] {line}");
}

fn tcp_connectable(host: &str, port: u16) -> bool {
    let addr = format!("{host}:{port}");
    let Ok(mut addrs) = addr.to_socket_addrs() else {
        return false;
    };
    let Some(sock) = addrs.next() else {
        return false;
    };
    TcpStream::connect_timeout(&sock, Duration::from_millis(200)).is_ok()
}

fn http_get_health_body(host: &str, port: u16) -> Option<String> {
    let addr = format!("{host}:{port}");
    let mut addrs = addr.to_socket_addrs().ok()?;
    let sock_addr = addrs.next()?;
    let mut stream = TcpStream::connect_timeout(&sock_addr, Duration::from_millis(400)).ok()?;
    let _ = stream.set_read_timeout(Some(Duration::from_millis(800)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(800)));

    let req = format!(
        "GET /api/health HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\nAccept: application/json\r\n\r\n"
    );
    stream.write_all(req.as_bytes()).ok()?;
    let mut buf = Vec::new();
    let _ = stream.read_to_end(&mut buf);
    let text = String::from_utf8_lossy(&buf);
    let ok_status = text.starts_with("HTTP/1.1 200") || text.starts_with("HTTP/1.0 200");
    if !ok_status {
        return None;
    }
    let body = text.split("\r\n\r\n").nth(1)?.trim();
    if body.is_empty() {
        return None;
    }
    Some(body.to_string())
}

fn is_planseed_health_json(body: &str) -> bool {
    let Ok(v) = serde_json::from_str::<Value>(body) else {
        return false;
    };
    let ok = v.get("ok").and_then(|x| x.as_bool()) == Some(true);
    let service = v.get("service").and_then(|x| x.as_str()) == Some(EXPECTED_SERVICE);
    let api = v.get("api_version").and_then(|x| x.as_str()) == Some(EXPECTED_API_VERSION);
    let engine = v
        .get("engine_version")
        .and_then(|x| x.as_str())
        .map(|s| !s.is_empty())
        .unwrap_or(false);
    ok && service && api && engine
}

/// 应用级探针：PORT_FREE | PLANSEED_ENGINE | FOREIGN_SERVICE
fn probe_engine(host: &str, port: u16) -> PortIdentity {
    if !tcp_connectable(host, port) {
        return PortIdentity::PortFree;
    }
    match http_get_health_body(host, port) {
        Some(body) if is_planseed_health_json(&body) => PortIdentity::PlanseedEngine,
        _ => PortIdentity::ForeignService,
    }
}

fn suggest_port(host: &str, preferred: u16, attempt: u32) -> u16 {
    if attempt == 0 {
        match probe_engine(host, preferred) {
            PortIdentity::PortFree => preferred,
            PortIdentity::ForeignService => {
                log::warn!("preferred {preferred} is FOREIGN_SERVICE; suggesting another port");
                suggest_ephemeral(host).unwrap_or(preferred.wrapping_add(1))
            }
            PortIdentity::PlanseedEngine => preferred,
        }
    } else {
        suggest_ephemeral(host).unwrap_or(preferred.wrapping_add(attempt as u16))
    }
}

fn suggest_ephemeral(host: &str) -> Option<u16> {
    TcpListener::bind((host, 0))
        .ok()
        .and_then(|l| l.local_addr().ok())
        .map(|a| a.port())
}

fn wait_for_engine(host: &str, port: u16, child: &mut Child, timeout: Duration) -> bool {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        match child.try_wait() {
            Ok(Some(status)) => {
                log::warn!("backend exited before healthy (status={status})");
                return false;
            }
            Err(e) => {
                log::warn!("backend wait error: {e}");
                return false;
            }
            Ok(None) => {}
        }
        if probe_engine(host, port) == PortIdentity::PlanseedEngine {
            return true;
        }
        thread::sleep(Duration::from_millis(250));
    }
    false
}

fn spawn_dev_backend(root: &Path, host: &str, port: u16) -> Result<Child, String> {
    Command::new("uv")
        .args(["run", "python", "-m", "backend"])
        .current_dir(root)
        .env("PLANSEED_HOST", host)
        .env("PLANSEED_PORT", port.to_string())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|e| format!("failed to spawn uv backend: {e}"))
}

fn sidecar_path(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    let exe_name = if cfg!(windows) {
        "planseed-backend.exe"
    } else {
        "planseed-backend"
    };

    let resource_dir = app
        .path()
        .resource_dir()
        .map_err(|e| format!("resource_dir unavailable: {e}"))?;

    let canonical = resource_dir.join("planseed-backend").join(exe_name);
    if canonical.exists() {
        return Ok(canonical);
    }

    #[cfg(debug_assertions)]
    {
        let flat = resource_dir.join(exe_name);
        if flat.exists() {
            log::warn!("using debug-only flat sidecar path: {:?}", flat);
            return Ok(flat);
        }
        if let Ok(mut beside) = std::env::current_exe() {
            beside.pop();
            beside.push("resources");
            beside.push("planseed-backend");
            beside.push(exe_name);
            if beside.exists() {
                log::warn!("using debug-only beside-exe sidecar path: {:?}", beside);
                return Ok(beside);
            }
        }
    }

    Err(format!(
        "PlanSeed engine not found at canonical path: {} \
         (expected onedir under bundle.resources → planseed-backend/{})",
        canonical.display(),
        exe_name
    ))
}

fn spawn_release_backend(
    app: &tauri::AppHandle,
    host: &str,
    port: u16,
) -> Result<Child, String> {
    let path = sidecar_path(app)?;
    let workdir = path.parent().map(Path::to_path_buf);
    let mut cmd = Command::new(&path);
    cmd.env("PLANSEED_HOST", host)
        .env("PLANSEED_PORT", port.to_string());
    if let Some(dir) = workdir {
        cmd.current_dir(dir);
    }
    // 进程 stdout/stderr 丢弃；启动/端口/fatal 写 app_log_dir/engine.log（结构化）
    cmd.stdout(Stdio::null()).stderr(Stdio::null());
    cmd.spawn()
        .map_err(|e| format!("failed to spawn sidecar: {e}"))
}

fn kill_child(child: &mut Child) {
    let _ = child.kill();
    let _ = child.wait();
}

fn kill_backend(state: &BackendChild) {
    if let Ok(mut guard) = state.0.lock() {
        if let Some(mut child) = guard.take() {
            kill_child(&mut child);
        }
    }
}

fn emit_status(handle: &tauri::AppHandle, payload: EngineStatusPayload) {
    // 唯一事实源：engine-status（不再双发 engine-ready，避免 STARTING→ERROR）
    if let Err(e) = handle.emit("engine-status", &payload) {
        log::warn!("emit engine-status failed: {e}");
    }
}

fn set_engine_url(meta: &EngineMeta, url: &str) {
    if let Ok(mut g) = meta.url.lock() {
        *g = url.to_string();
    }
}

fn watch_child_exit(handle: tauri::AppHandle, url: String) {
    thread::spawn(move || {
        loop {
            thread::sleep(Duration::from_millis(800));
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
                        // 无托管子进程（reuse）→ 交给 watch_reused_health
                        return;
                    }
                }
            };
            if let Some(msg) = exited {
                append_engine_log(&handle, &format!("fatal: {msg}"));
                emit_status(
                    &handle,
                    EngineStatusPayload {
                        status: EngineLifecycle::Error,
                        url: url.clone(),
                        error: Some(msg),
                    },
                );
                return;
            }
        }
    });
}

/// 复用外部 PlanSeed：无 Child 可 wait，轮询 /api/health 身份。
/// 连续失败才 ERROR（与前端 consecutiveHealthFailures 对齐；不 kill 外进程）。
fn watch_reused_health(handle: tauri::AppHandle, host: String, port: u16, url: String) {
    const FAIL_THRESHOLD: u32 = 3;
    thread::spawn(move || {
        let mut consecutive_failures: u32 = 0;
        loop {
            thread::sleep(Duration::from_secs(2));
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
                    emit_status(
                        &handle,
                        EngineStatusPayload {
                            status: EngineLifecycle::Error,
                            url: url.clone(),
                            error: Some(msg),
                        },
                    );
                    return;
                }
            }
        }
    });
}

/// 选 port → 立即 spawn → health 失败 / 进程退出 → 换 port 重试。
fn spawn_engine_with_retry(
    handle: &tauri::AppHandle,
    host: &str,
    preferred: u16,
    root: &Path,
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
            },
        );
        append_engine_log(
            &h,
            &format!("startup host={host} preferred_port={preferred} debug={debug}"),
        );

        let mut last_error = String::from("engine failed to start");

        for attempt in 0..MAX_SPAWN_ATTEMPTS {
            let port = suggest_port(&host, preferred, attempt);

            match probe_engine(&host, port) {
                PortIdentity::PlanseedEngine => {
                    let url = format!("http://{host}:{port}");
                    set_engine_url(h.state::<EngineMeta>().inner(), &url);
                    append_engine_log(&h, &format!("reuse PLANSEED_ENGINE at {url}"));
                    emit_status(
                        &h,
                        EngineStatusPayload {
                            status: EngineLifecycle::Ready,
                            url: url.clone(),
                            error: None,
                        },
                    );
                    watch_reused_health(h.clone(), host.clone(), port, url);
                    h.state::<EngineMeta>()
                        .spawning
                        .store(false, Ordering::SeqCst);
                    return;
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
            append_engine_log(&h, &format!("spawn attempt={attempt} port={port}"));

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
                        append_engine_log(&h, &format!("ready port={port} url={url}"));
                        emit_status(
                            &h,
                            EngineStatusPayload {
                                status: EngineLifecycle::Ready,
                                url: url.clone(),
                                error: None,
                            },
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
                    kill_child(&mut child);
                }
                Err(e) => {
                    last_error = e;
                    append_engine_log(&h, &format!("fatal: spawn failed: {last_error}"));
                }
            }
        }

        emit_status(
            &h,
            EngineStatusPayload {
                status: EngineLifecycle::Error,
                url: preferred_url,
                error: Some(last_error),
            },
        );
        h.state::<EngineMeta>()
            .spawning
            .store(false, Ordering::SeqCst);
    });
}

#[tauri::command]
fn get_engine_url(meta: State<'_, EngineMeta>) -> String {
    meta.url.lock().expect("engine url").clone()
}

#[tauri::command]
fn retry_engine(app: tauri::AppHandle) -> Result<(), String> {
    let host = engine_host();
    let preferred = preferred_port();
    kill_backend(app.state::<BackendChild>().inner());
    let root = repo_root_from_manifest();
    append_engine_log(&app, "user retry_engine");
    spawn_engine_with_retry(&app, &host, preferred, &root);
    Ok(())
}

#[cfg(test)]
mod probe_tests {
    use super::*;

    #[test]
    fn rejects_non_planseed_json() {
        assert!(!is_planseed_health_json(r#"{"ok":true}"#));
        assert!(!is_planseed_health_json(r#"{"ok":true,"service":"other","api_version":"1","engine_version":"1"}"#));
        assert!(is_planseed_health_json(
            r#"{"ok":true,"service":"planseed","api_version":"1","engine_version":"0.1.0"}"#
        ));
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let host = engine_host();
    let preferred = preferred_port();
    let initial_url = format!("http://{host}:{preferred}");

    tauri::Builder::default()
        .manage(BackendChild(Mutex::new(None)))
        .manage(EngineMeta {
            url: Mutex::new(initial_url.clone()),
            spawning: AtomicBool::new(false),
        })
        .invoke_handler(tauri::generate_handler![get_engine_url, retry_engine])
        .setup(move |app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            let handle = app.handle().clone();
            emit_status(
                &handle,
                EngineStatusPayload {
                    status: EngineLifecycle::Starting,
                    url: initial_url.clone(),
                    error: None,
                },
            );

            match probe_engine(&host, preferred) {
                PortIdentity::PlanseedEngine => {
                    let url = format!("http://{host}:{preferred}");
                    set_engine_url(handle.state::<EngineMeta>().inner(), &url);
                    append_engine_log(&handle, &format!("reuse existing PLANSEED at {url}"));
                    emit_status(
                        &handle,
                        EngineStatusPayload {
                            status: EngineLifecycle::Ready,
                            url: url.clone(),
                            error: None,
                        },
                    );
                    watch_reused_health(handle.clone(), host.clone(), preferred, url);
                }
                identity => {
                    log::info!("preferred {preferred} is {identity:?} → spawn with retry");
                    let root = repo_root_from_manifest();
                    spawn_engine_with_retry(&handle, &host, preferred, &root);
                }
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let RunEvent::Exit = event {
                kill_backend(app_handle.state::<BackendChild>().inner());
                let url = app_handle
                    .state::<EngineMeta>()
                    .url
                    .lock()
                    .map(|u| u.clone())
                    .unwrap_or_default();
                emit_status(
                    app_handle,
                    EngineStatusPayload {
                        status: EngineLifecycle::Stopped,
                        url,
                        error: None,
                    },
                );
            }
        });
}
