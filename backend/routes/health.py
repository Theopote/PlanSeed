"""健康检查 — Engine Identity Probe 契约。"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])

# Tauri / 前端复用端口的唯一身份依据；改字段需同步 desktop/src-tauri 探针。
API_VERSION = "1"
ENGINE_VERSION = "0.1.0"
SERVICE_ID = "planseed"


@router.get("/api/health")
def health() -> dict[str, bool | str]:
    return {
        "ok": True,
        "service": SERVICE_ID,
        "api_version": API_VERSION,
        "engine_version": ENGINE_VERSION,
    }
