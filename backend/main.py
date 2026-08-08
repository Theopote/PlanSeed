"""PlanSeed FastAPI — create_app + 挂载路由。"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes import compare as compare_routes
from backend.routes import generate as generate_routes
from backend.routes import health as health_routes
from backend.routes import projects as projects_routes
from backend.routes import requirements as requirements_routes


def create_app() -> FastAPI:
    app = FastAPI(title="PlanSeed API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:1420",
            "http://127.0.0.1:1420",
            "tauri://localhost",
            "https://tauri.localhost",
            "http://tauri.localhost",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_routes.router)
    app.include_router(generate_routes.router)
    app.include_router(requirements_routes.router)
    app.include_router(compare_routes.router)
    app.include_router(projects_routes.router)
    return app


app = create_app()
