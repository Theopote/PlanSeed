//! Sidecar 占位 — 仅满足 resources/planseed-backend 存在；正式包用 PyInstaller --onedir 替换整目录。
fn main() {
    eprintln!(
        "planseed-backend stub — run scripts/build_backend_sidecar.ps1 for a real onedir engine"
    );
    std::process::exit(1);
}
