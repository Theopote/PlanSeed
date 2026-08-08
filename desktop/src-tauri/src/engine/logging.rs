//! engine.log — startup / port / fatal（不记录用户需求正文）。

use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::PathBuf;

use tauri::Manager;

pub fn engine_log_path(app: &tauri::AppHandle) -> Option<PathBuf> {
    let dir = app.path().app_log_dir().ok()?;
    let _ = fs::create_dir_all(&dir);
    Some(dir.join("engine.log"))
}

pub fn append_engine_log(app: &tauri::AppHandle, line: &str) {
    let Some(path) = engine_log_path(app) else {
        return;
    };
    if let Ok(mut f) = OpenOptions::new().create(true).append(true).open(&path) {
        let _ = writeln!(f, "{}", line);
    }
    log::info!("[engine] {line}");
}
