//! 引擎进程：spawn / kill / sidecar 路径。不 kill REUSED 外部引擎。

use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

use tauri::Manager;

/// Tauri 托管的子进程；None = REUSED 或未启动。
pub struct BackendChild(pub Mutex<Option<Child>>);

pub fn repo_root_from_manifest() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .unwrap_or_else(|_| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../.."))
}

pub fn spawn_dev_backend(root: &Path, host: &str, port: u16) -> Result<Child, String> {
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

pub fn spawn_release_backend(
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
    cmd.stdout(Stdio::null()).stderr(Stdio::null());
    cmd.spawn()
        .map_err(|e| format!("failed to spawn sidecar: {e}"))
}

fn kill_child(child: &mut Child) {
    let _ = child.kill();
    let _ = child.wait();
}

/// 仅杀掉 MANAGED 子进程；REUSED 时 BackendChild 为空，此处 no-op。
pub fn kill_backend(state: &BackendChild) {
    if let Ok(mut guard) = state.0.lock() {
        if let Some(mut child) = guard.take() {
            kill_child(&mut child);
        }
    }
}

pub(crate) fn kill_child_owned(child: &mut Child) {
    kill_child(child);
}
