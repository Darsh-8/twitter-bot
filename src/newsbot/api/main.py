from fastapi import FastAPI

from newsbot.api.routers import admin, config, logs, stories
from newsbot.config.settings import get_settings
from newsbot.logging_config import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(title="AI News Bot Admin API", version="0.1.0")
    app.include_router(stories.router)
    app.include_router(logs.router)
    app.include_router(config.router)
    app.include_router(admin.router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
