"""FastAPI Ask endpoint (Phase 5)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.pipeline.config import load_env
from app.pipeline.orchestrator import ask

load_env()


class AskRequest(BaseModel):
    question: str = Field(default="")


def create_app() -> FastAPI:
    application = FastAPI(title="Mutual Fund FAQ Assistant", version="0.1.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.post("/api/ask")
    def api_ask(body: AskRequest) -> dict:
        response = ask(body.question)
        return response.as_public_dict()

    return application


app = create_app()
