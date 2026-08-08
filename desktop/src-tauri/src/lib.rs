//! PlanSeed Tauri shell — setup / commands / RunEvent。
//!
//! 引擎细节见 `engine/`（probe / process / lifecycle / logging）。

mod engine;

use std::sync::atomic::AtomicBool;
use std::sync::Mutex;

use tauri::{Manager, RunEvent};

use engine::{
    append_engine_log, emit_status, engine_host, get_engine_url, preferred_port, probe_engine,
    repo_root_from_manifest, retry_engine, spawn_engine_with_retry, watch_reused_health,
    BackendChild, EngineLifecycle, EngineMeta, EngineOwnership, EngineStatusPayload, PortIdentity,
};

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
            ownership: Mutex::new(None),
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
                    ownership: None,
                },
            );

            match probe_engine(&host, preferred) {
                PortIdentity::PlanseedEngine => {
                    let url = format!("http://{host}:{preferred}");
                    if let Ok(mut g) = handle.state::<EngineMeta>().url.lock() {
                        *g = url.clone();
                    }
                    if let Ok(mut g) = handle.state::<EngineMeta>().ownership.lock() {
                        *g = Some(EngineOwnership::Reused);
                    }
                    append_engine_log(&handle, &format!("REUSED existing PLANSEED at {url}"));
                    emit_status(
                        &handle,
                        EngineStatusPayload {
                            status: EngineLifecycle::Ready,
                            url: url.clone(),
                            error: None,
                            ownership: Some(EngineOwnership::Reused),
                        },
                    );
                    watch_reused_health(handle.clone(), host.clone(), preferred, url);
                }
                identity => {
                    log::info!("preferred {preferred} is {identity:?} → spawn with retry");
                    let root = repo_root_from_manifest();
                    spawn_engine_with_retry(&handle, &host, preferred, &root, true);
                }
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let RunEvent::Exit = event {
                engine::kill_backend(app_handle.state::<BackendChild>().inner());
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
                        ownership: None,
                    },
                );
            }
        });
}
