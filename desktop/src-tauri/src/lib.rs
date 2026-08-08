//! PlanSeed Tauri shell — 异步拉起本地引擎，窗口先出，就绪后 emit。
//!
//! Engine Identity Probe（禁止仅靠 TCP open）：
//! - PORT_FREE → bind + spawn PlanSeed
//! - PLANSEED_ENGINE → reuse（须通过 /api/health 身份契约）
//! - FOREIGN_SERVICE → 换端口 + spawn PlanSeed

use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream, ToSocketAddrs};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::Duration;

use serde::Serialize;
use serde_json::Value;
use tauri::{Emitter, Manager, RunEvent, State};

/// 与 backend/routes/health.py 对齐。
const EXPECTED_SERVICE: &str = "planseed";
const EXPECTED_API_VERSION: &str = "1";

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

/// Engine Identity Probe：PORT_FREE | PLANSEED_ENGINE | FOREIGN_SERVICE
fn probe_port_identity(host: &str, port: u16) -> PortIdentity {
    if !tcp_connectable(host, port) {
        return PortIdentity::PortFree;
    }
    match http_get_health_body(host, port) {
        Some(body) if is_planseed_health_json(&body) => PortIdentity::PlanseedEngine,
        _ => PortIdentity::ForeignService,
    }
}

/// 返回 (port, reuse_existing_planseed)。
fn resolve_engine_endpoint(host: &str, preferred: u16) -> (u16, bool) {
    match probe_port_identity(host, preferred) {
        PortIdentity::PlanseedEngine => {
            log::info!("probe {preferred}: PLANSEED_ENGINE → reuse");
            (preferred, true)
        }
        PortIdentity::PortFree => {
            log::info!("probe {preferred}: PORT_FREE → spawn here");
            // 试绑确认可占用；失败则退到 ephemeral
            if TcpListener::bind((host, preferred)).is_ok() {
                (preferred, false)
            } else {
                log::warn!("preferred port {preferred} became unbindable; picking another");
                (pick_ephemeral_port(host).unwrap_or(preferred), false)
            }
        }
        PortIdentity::ForeignService => {
            log::warn!("probe {preferred}: FOREIGN_SERVICE → pick another port + spawn PlanSeed");
            (pick_ephemeral_port(host).unwrap_or(preferred), false)
        }
    }
}

fn pick_ephemeral_port(host: &str) -> Option<u16> {
    TcpListener::bind((host, 0))
        .ok()
        .and_then(|l| l.local_addr().ok())
        .map(|a| a.port())
}

fn wait_for_planseed(host: &str, port: u16, timeout: Duration) -> bool {
    let deadline = std::time::Instant::now() + timeout;
    while std::time::Instant::now() < deadline {
        if probe_port_identity(host, port) == PortIdentity::PlanseedEngine {
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

/// PyInstaller --onedir：resources/planseed-backend/planseed-backend(.exe)
fn sidecar_path(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    let exe_name = if cfg!(windows) {
        "planseed-backend.exe"
    } else {
        "planseed-backend"
    };
    if let Ok(dir) = app.path().resource_dir() {
        let candidate = dir.join("planseed-backend").join(exe_name);
        if candidate.exists() {
            return Ok(candidate);
        }
        let flat = dir.join(exe_name);
        if flat.exists() {
            return Ok(flat);
        }
    }
    let mut beside = std::env::current_exe().map_err(|e| e.to_string())?;
    beside.pop();
    beside.push("resources");
    beside.push("planseed-backend");
    beside.push(exe_name);
    if beside.exists() {
        return Ok(beside);
    }
    Err("planseed-backend onedir not found under resources/".into())
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

fn kill_backend(state: &BackendChild) {
    if let Ok(mut guard) = state.0.lock() {
        if let Some(mut child) = guard.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

fn emit_ready(handle: &tauri::AppHandle, payload: EngineReadyPayload) {
    if let Err(e) = handle.emit("engine-ready", payload) {
        log::warn!("emit engine-ready failed: {e}");
    }
}

#[tauri::command]
fn get_engine_url(meta: State<'_, EngineMeta>) -> String {
    meta.url.lock().expect("engine url").clone()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let host = engine_host();
    let preferred = preferred_port();
    let (port, reuse) = resolve_engine_endpoint(&host, preferred);
    let url = format!("http://{host}:{port}");

    tauri::Builder::default()
        .manage(BackendChild(Mutex::new(None)))
        .manage(EngineMeta {
            url: Mutex::new(url.clone()),
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
            *handle.state::<EngineMeta>().url.lock().expect("url") = url.clone();

            if reuse {
                log::info!("reusing PLANSEED_ENGINE at {url}");
                emit_ready(
                    &handle,
                    EngineReadyPayload {
                        url: url.clone(),
                        ready: true,
                        error: None,
                    },
                );
                return Ok(());
            }

            let root = repo_root_from_manifest();
            let child = if cfg!(debug_assertions) {
                log::info!("starting PlanSeed engine (dev) {url} from {:?}", root);
                spawn_dev_backend(&root, &host, port)
            } else {
                log::info!("starting PlanSeed engine (onedir sidecar) {url}");
                spawn_release_backend(&handle, &host, port)
            };

            match child {
                Ok(c) => {
                    *handle.state::<BackendChild>().0.lock().expect("child") = Some(c);
                    let h = handle.clone();
                    let host_c = host.clone();
                    let url_c = url.clone();
                    thread::spawn(move || {
                        let ready = wait_for_planseed(&host_c, port, Duration::from_secs(45));
                        log::info!("engine ready={ready} url={url_c}");
                        emit_ready(
                            &h,
                            EngineReadyPayload {
                                url: url_c,
                                ready,
                                error: if ready {
                                    None
                                } else {
                                    Some("engine failed to become ready in time".into())
                                },
                            },
                        );
                    });
                }
                Err(e) => {
                    log::error!("engine launch failed: {e}");
                    emit_ready(
                        &handle,
                        EngineReadyPayload {
                            url: url.clone(),
                            ready: false,
                            error: Some(e),
                        },
                    );
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
