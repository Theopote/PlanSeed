//! PlanSeed Tauri shell — 异步拉起本地引擎，窗口先出，就绪后 emit。
//!
//! Engine Identity Probe（禁止仅靠 TCP open）：
//! - PORT_FREE → spawn PlanSeed（不预占端口；bind 失败则换端口重试）
//! - PLANSEED_ENGINE → reuse（须通过 /api/health 身份契约）
//! - FOREIGN_SERVICE → 换端口 + spawn PlanSeed
//!
//! 就绪判定：poll /api/health + identity/version（应用级），不是 TCP listen。

use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream, ToSocketAddrs};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
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
}

#[derive(Clone, Serialize)]
struct EngineReadyPayload {
    url: String,
    ready: bool,
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

/// 建议候选端口（不长期持有 bind；真正可用性由 spawn + health 确认）。
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
    // bind→读 port→立即 drop：存在极小竞态，由 spawn 失败 / health 超时后重试消化
    TcpListener::bind((host, 0))
        .ok()
        .and_then(|l| l.local_addr().ok())
        .map(|a| a.port())
}

/// 应用级就绪：poll health 身份；子进程提前退出则失败。
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

/// 正式路径（唯一契约）：
///   `{resource_dir}/planseed-backend/planseed-backend(.exe)`
/// debug 才允许少量兼容探测，避免安装器结构变化时无限加 fallback。
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
        // 仅开发兼容：扁平资源 / 旁路 resources（正式包禁止依赖这些）
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

fn spawn_release_backend(app: &tauri::AppHandle, host: &str, port: u16) -> Result<Child, String> {
    let path = sidecar_path(app)?;
    let workdir = path.parent().map(Path::to_path_buf);
    let mut cmd = Command::new(&path);
    cmd.env("PLANSEED_HOST", host)
        .env("PLANSEED_PORT", port.to_string())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    if let Some(dir) = workdir {
        cmd.current_dir(dir);
    }
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

fn emit_ready(handle: &tauri::AppHandle, payload: EngineReadyPayload) {
    if let Err(e) = handle.emit("engine-ready", payload) {
        log::warn!("emit engine-ready failed: {e}");
    }
}

fn set_engine_url(meta: &EngineMeta, url: &str) {
    if let Ok(mut g) = meta.url.lock() {
        *g = url.to_string();
    }
}

/// 选 port → 立即 spawn → health 失败 / 进程退出 → 换 port 重试。
fn spawn_engine_with_retry(
    handle: &tauri::AppHandle,
    host: &str,
    preferred: u16,
    root: &Path,
) {
    let h = handle.clone();
    let host = host.to_string();
    let root = root.to_path_buf();
    let debug = cfg!(debug_assertions);

    thread::spawn(move || {
        let mut last_error = String::from("engine failed to start");

        for attempt in 0..MAX_SPAWN_ATTEMPTS {
            let port = suggest_port(&host, preferred, attempt);

            // 竞态下可能已被别人占成 FOREIGN，或意外已是 PlanSeed
            match probe_engine(&host, port) {
                PortIdentity::PlanseedEngine => {
                    let url = format!("http://{host}:{port}");
                    set_engine_url(h.state::<EngineMeta>().inner(), &url);
                    log::info!("found PLANSEED_ENGINE at {url} (attempt {attempt})");
                    emit_ready(
                        &h,
                        EngineReadyPayload {
                            url,
                            ready: true,
                            error: None,
                        },
                    );
                    return;
                }
                PortIdentity::ForeignService => {
                    log::warn!("port {port} FOREIGN_SERVICE; skip attempt {attempt}");
                    continue;
                }
                PortIdentity::PortFree => {}
            }

            let url = format!("http://{host}:{port}");
            set_engine_url(h.state::<EngineMeta>().inner(), &url);
            log::info!("spawn attempt {attempt} → {url}");

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
                        log::info!("engine ready via health probe at {url}");
                        emit_ready(
                            &h,
                            EngineReadyPayload {
                                url,
                                ready: true,
                                error: None,
                            },
                        );
                        return;
                    }
                    last_error = format!(
                        "port {port}: backend exited or /api/health identity not ready"
                    );
                    log::warn!("{last_error}; retrying");
                    kill_child(&mut child);
                }
                Err(e) => {
                    last_error = e;
                    log::warn!("spawn failed: {last_error}; retrying");
                }
            }
        }

        let url = format!("http://{host}:{preferred}");
        emit_ready(
            &h,
            EngineReadyPayload {
                url,
                ready: false,
                error: Some(last_error),
            },
        );
    });
}

#[tauri::command]
fn get_engine_url(meta: State<'_, EngineMeta>) -> String {
    meta.url.lock().expect("engine url").clone()
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
        })
        .invoke_handler(tauri::generate_handler![get_engine_url])
        .setup(move |app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            let handle = app.handle().clone();

            // 仅 PLANSEED_ENGINE 才 reuse；否则后台 spawn+health 重试（不预占端口）
            match probe_engine(&host, preferred) {
                PortIdentity::PlanseedEngine => {
                    let url = format!("http://{host}:{preferred}");
                    set_engine_url(handle.state::<EngineMeta>().inner(), &url);
                    log::info!("reusing PLANSEED_ENGINE at {url}");
                    emit_ready(
                        &handle,
                        EngineReadyPayload {
                            url,
                            ready: true,
                            error: None,
                        },
                    );
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
            }
        });
}
