"""FastAPI application factory (docs/PLAN.md Phase 4)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from loan_ops.config import get_settings

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _usd(value: float) -> str:
    """Filter: currency text (never raw code) for USD amounts."""
    return f"${float(value):,.2f}"


def _usd0(value: float) -> str:
    return f"${float(value):,.0f}"


templates.env.filters["usd"] = _usd
templates.env.filters["usd0"] = _usd0

description = """Local web application that processes loan applications
through the four checks of docs/PROCESS.md and produces exactly one of three
outcomes: approved, denied, or refer."""


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_provider()  # fail fast on bad config (GOALS 5.2)

    from loan_ops.app.routes import api_router, page_router

    app = FastAPI(title=settings.app_name, description=description, version="0.1.0")
    app.mount("/static", StaticFiles(directory=str(TEMPLATES_DIR.parent / "static")), name="static")
    app.include_router(api_router)
    app.include_router(page_router)
    return app
