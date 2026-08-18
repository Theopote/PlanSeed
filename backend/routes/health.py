"""健康检查 — Engine Identity Probe 契约。"""

from __future__ import annotations

from fastapi import APIRouter
from packages.schema.identity import solver_identity

router = APIRouter(tags=["health"])

# Tauri / 前端复用端口的唯一身份依据；改字段需同步 desktop/src-tauri 探针。
API_VERSION = "1"
ENGINE_VERSION = "0.1.1"
SERVICE_ID = "planseed"


@router.get("/api/health")
def health() -> dict[str, bool | str]:
    body: dict[str, bool | str] = {
        "ok": True,
        "service": SERVICE_ID,
        "api_version": API_VERSION,
        "engine_version": ENGINE_VERSION,
    }
    # 算法契约版本（regression / 历史分数解释）；不参与端口 reuse 判定
    body.update(solver_identity())
    return body
