"""python -m backend — 本地引擎入口（端口可被环境变量覆写）。"""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.environ.get("PLANSEED_HOST", "127.0.0.1")
    allow_lan = (os.environ.get("PLANSEED_ALLOW_LAN") or "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if host not in {"127.0.0.1", "localhost", "::1"} and not allow_lan:
        raise SystemExit(
            f"PLANSEED_HOST={host} 非 loopback。绑定局域网前请设置 PLANSEED_ALLOW_LAN=1。"
        )
    port = int(os.environ.get("PLANSEED_PORT", "8787"))
    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        log_level=os.environ.get("PLANSEED_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
