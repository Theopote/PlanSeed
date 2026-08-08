//! Sidecar 占位程序 — 仅满足 Tauri externalBin 路径存在；正式包请用 PyInstaller 产物替换。
fn main() {
    eprintln!(
        "planseed-backend stub — run scripts/build_backend_sidecar.ps1 for a real engine"
    );
    std::process::exit(1);
}
