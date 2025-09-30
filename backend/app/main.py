from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import router as api_router
from .core.config import get_config
from .db.session import init_db
from .services.auth_service import ensure_initial_admin


def create_app() -> FastAPI:
    config = get_config()
    app = FastAPI(title=config.app_name)

    if config.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.allowed_origins,
            allow_methods=["*"],
            allow_headers=["*"],
            allow_credentials=True,
        )

    app.include_router(api_router, prefix="/api")

    @app.on_event("startup")
    async def on_startup() -> None:
        init_db()
        ensure_initial_admin()

    frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
    if frontend_dir.exists():
        app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

        index_path = frontend_dir / "index.html"
        admin_path = frontend_dir / "admin.html"

        @app.get("/", include_in_schema=False)
        async def serve_index() -> FileResponse:
            return FileResponse(index_path)

        if admin_path.exists():
            @app.get("/admin", include_in_schema=False)
            async def serve_admin() -> FileResponse:
                return FileResponse(admin_path)

    return app


app = create_app()
