//! PlanSeed Tauri shell — 异步拉起本地引擎，窗口先出，就绪后 emit。
//!
//! 端口复用契约：仅当 GET /api/health 返回 ok + service=planseed 时才 reuse；
//! 任意其它进程占用 8787 不得被当成 PlanSeed。

use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream, ToSocketAddrs};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::Duration;

use serde::Serialize;
use tauri::{Emitter, Manager, RunEvent, State};

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

fn port_open(host: &str, port: u16) -> bool {
    let addr = format!("{host}:{port}");
    let Ok(mut addrs) = addr.to_socket_addrs() else {
        return false;
    };
    let Some(sock) = addrs.next() else {
        return false;
    };
    TcpStream::connect_timeout(&sock, Duration::from_millis(200)).is_ok()
}

/// 确认对端是 PlanSeed 引擎（不是任意占着端口的进程）。
fn planseed_alive(host: &str, port: u16) -> bool {
    let addr = format!("{host}:{port}");
    let Ok(mut addrs) = addr.to_socket_addrs() else {
        return false;
    };
    let Some(sock_addr) = addrs.next() else {
        return false;
    };
    let Ok(mut stream) = TcpStream::connect_timeout(&sock_addr, Duration::from_millis(400)) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(600)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(600)));

    let req = format!(
        "GET /api/health HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\nAccept: application/json\r\n\r\n"
    );
    if stream.write_all(req.as_bytes()).is_err() {
        return false;
    }
    let mut buf = Vec::new();
    let _ = stream.read_to_end(&mut buf);
    let text = String::from_utf8_lossy(&buf);
    // 兼容压缩/空白差异：要求 HTTP 成功 + JSON 身份字段
    let ok_status = text.starts_with("HTTP/1.1 200") || text.starts_with("HTTP/1.0 200");
    let body_ok = text.contains("\"ok\"")
        && (text.contains("true") || text.contains(": true"));
    let service_ok = text.contains("\"service\"") && text.contains("planseed");
    ok_status && body_ok && service_ok
}

/// 返回 (port, reuse_existing_planseed)。
fn resolve_engine_endpoint(host: &str, preferred: u16) -> (u16, bool) {
    if planseed_alive(host, preferred) {
        return (preferred, true);
    }
    // preferred 空闲 → 占用它并自启
    if !port_open(host, preferred) {
        if TcpListener::bind((host, preferred)).is_ok() {
            return (preferred, false);
        }
    } else {
        log::warn!(
            "port {preferred} is open but not PlanSeed (/api/health); picking another port"
        );
    }
    // preferred 被外来进程占用，或 bind 失败 → 系统分配
    let port = TcpListener::bind((host, 0))
        .ok()
        .and_then(|l| l.local_addr().ok())
        .map(|a| a.port())
        .unwrap_or(preferred);
    (port, false)
}

fn wait_for_planseed(host: &str, port: u16, timeout: Duration) -> bool {
    let deadline = std::time::Instant::now() + timeout;
    while std::time::Instant::now() < deadline {
        if planseed_alive(host, port) {
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
                log::info!("reusing PlanSeed engine at {url}");
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
