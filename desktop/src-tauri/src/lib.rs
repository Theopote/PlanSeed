//! PlanSeed Tauri shell — 拉起 / 关闭本地求解引擎，并向前端暴露引擎 URL。

use std::net::{TcpListener, TcpStream, ToSocketAddrs};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::Duration;

use tauri::{Manager, RunEvent, State};

struct BackendChild(Mutex<Option<Child>>);

struct EngineMeta {
    url: Mutex<String>,
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

fn pick_listen_port(host: &str, preferred: u16) -> u16 {
    if !port_open(host, preferred) {
        // 端口空闲（或无可连服务）→ 优先占用 preferred
        if TcpListener::bind((host, preferred)).is_ok() {
            return preferred;
        }
    } else {
        // 已有服务：复用（多为开发期 pnpm 已起的引擎）
        return preferred;
    }
    // preferred 被非 HTTP 占用等 → 系统分配
    TcpListener::bind((host, 0))
        .ok()
        .and_then(|l| l.local_addr().ok())
        .map(|a| a.port())
        .unwrap_or(preferred)
}

fn wait_for_port(host: &str, port: u16, timeout: Duration) -> bool {
    let deadline = std::time::Instant::now() + timeout;
    while std::time::Instant::now() < deadline {
        if port_open(host, port) {
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
    let name = if cfg!(windows) {
        "planseed-backend.exe"
    } else {
        "planseed-backend"
    };
    if let Ok(dir) = app.path().resource_dir() {
        let candidate = dir.join(name);
        if candidate.exists() {
            return Ok(candidate);
        }
    }
    let mut beside = std::env::current_exe().map_err(|e| e.to_string())?;
    beside.pop();
    beside.push(name);
    if beside.exists() {
        return Ok(beside);
    }
    Err("planseed-backend sidecar not found".into())
}

fn spawn_release_backend(app: &tauri::AppHandle, host: &str, port: u16) -> Result<Child, String> {
    let path = sidecar_path(app)?;
    Command::new(path)
        .env("PLANSEED_HOST", host)
        .env("PLANSEED_PORT", port.to_string())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
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

#[tauri::command]
fn get_engine_url(meta: State<'_, EngineMeta>) -> String {
    meta.url.lock().expect("engine url").clone()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let host = engine_host();
    let preferred = preferred_port();
    // 若 preferred 已有进程在听，复用且不 spawn；否则选端口并 spawn
    let already = port_open(&host, preferred);
    let port = if already {
        preferred
    } else {
        pick_listen_port(&host, preferred)
    };
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

            if already {
                log::info!("reusing engine at {url}");
                return Ok(());
            }

            let root = repo_root_from_manifest();
            let child = if cfg!(debug_assertions) {
                log::info!("starting PlanSeed engine (dev) {url} from {:?}", root);
                spawn_dev_backend(&root, &host, port)
            } else {
                log::info!("starting PlanSeed engine (sidecar) {url}");
                spawn_release_backend(&handle, &host, port)
            };

            match child {
                Ok(c) => {
                    *handle.state::<BackendChild>().0.lock().expect("child") = Some(c);
                    let ready = wait_for_port(&host, port, Duration::from_secs(30));
                    log::info!("engine ready={ready} url={url}");
                }
                Err(e) => {
                    log::error!("engine launch failed: {e}");
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
