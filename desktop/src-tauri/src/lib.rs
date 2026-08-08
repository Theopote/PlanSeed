//! PlanSeed Tauri shell — 负责拉起 / 关闭本地求解引擎（sidecar）。

use std::net::{TcpStream, ToSocketAddrs};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::Duration;

use tauri::{Manager, RunEvent};

struct BackendState(Mutex<Option<Child>>);

fn repo_root_from_manifest() -> PathBuf {
    // desktop/src-tauri → 仓库根
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .unwrap_or_else(|_| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../.."))
}

fn engine_host() -> String {
    std::env::var("PLANSEED_HOST").unwrap_or_else(|_| "127.0.0.1".into())
}

fn engine_port() -> String {
    std::env::var("PLANSEED_PORT").unwrap_or_else(|_| "8787".into())
}

fn port_open() -> bool {
    let addr = format!("{}:{}", engine_host(), engine_port());
    let Ok(mut addrs) = addr.to_socket_addrs() else {
        return false;
    };
    let Some(sock) = addrs.next() else {
        return false;
    };
    TcpStream::connect_timeout(&sock, Duration::from_millis(200)).is_ok()
}

fn wait_for_port(timeout: Duration) -> bool {
    let deadline = std::time::Instant::now() + timeout;
    while std::time::Instant::now() < deadline {
        if port_open() {
            return true;
        }
        thread::sleep(Duration::from_millis(250));
    }
    false
}

fn spawn_dev_backend(root: &Path) -> Result<Child, String> {
    let host = engine_host();
    let port = engine_port();
    Command::new("uv")
        .args(["run", "python", "-m", "backend"])
        .current_dir(root)
        .env("PLANSEED_HOST", &host)
        .env("PLANSEED_PORT", &port)
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

fn spawn_release_backend(app: &tauri::AppHandle) -> Result<Child, String> {
    let path = sidecar_path(app)?;
    let host = engine_host();
    let port = engine_port();
    Command::new(path)
        .env("PLANSEED_HOST", &host)
        .env("PLANSEED_PORT", &port)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|e| format!("failed to spawn sidecar: {e}"))
}

fn kill_backend(state: &BackendState) {
    if let Ok(mut guard) = state.0.lock() {
        if let Some(mut child) = guard.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(BackendState(Mutex::new(None)))
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            let handle = app.handle().clone();
            let root = repo_root_from_manifest();
            let child = if cfg!(debug_assertions) {
                log::info!("starting PlanSeed engine (dev) from {:?}", root);
                spawn_dev_backend(&root)
            } else {
                log::info!("starting PlanSeed engine (sidecar)");
                spawn_release_backend(&handle)
            };

            match child {
                Ok(c) => {
                    *handle.state::<BackendState>().0.lock().expect("backend mutex") = Some(c);
                    let ready = wait_for_port(Duration::from_secs(20));
                    log::info!("engine port ready={}", ready);
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
                kill_backend(app_handle.state::<BackendState>().inner());
            }
        });
}
