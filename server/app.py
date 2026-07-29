"""FastAPI adapter for the existing Agentic RAG engine."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import main
from graph import config, consts, engine, formatting
from server.documents import list_corpus_documents
from server.runs import RunStore
from server.schemas import (
    AskRequest,
    AskResponse,
    Citation,
    DocumentsResponse,
    NodeTiming,
    PreflightStatus,
    RunDetail,
    RunRuntime,
    RunsResponse,
    RunSummary,
    RuntimeStatus,
)
from server.status import build_runtime_status

# Importing the application modules is side-effect-free; configuration is not
# resolved until lifespan startup or a request reaches an endpoint.
load_dotenv()

PREFLIGHT_FAILURE_MESSAGE = "Startup preflight failed — see the server console for details."
RUN_IN_PROGRESS_MESSAGE = "Another question is currently being processed."
LOCAL_SNIPPET_MAX_CHARS = 300

_ERROR_STOP_REASONS = {
    consts.STOP_REASON_RETRIEVAL_ERROR,
    consts.STOP_REASON_WEB_SEARCH_ERROR,
    consts.STOP_REASON_GENERATION_ERROR,
    consts.STOP_REASON_TOOL_ERROR,
}


def _run_status(stop_reason: str) -> str:
    if not stop_reason:
        return "ok"
    if stop_reason in _ERROR_STOP_REASONS:
        return "error"
    return "caveat"


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _build_citations(documents: Any) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[tuple[str, str | None, str | None, str | None, str | None]] = set()

    def append(citation: Citation) -> None:
        key = (
            citation.kind,
            citation.title,
            citation.source,
            citation.url,
            citation.query,
        )
        if key not in seen:
            seen.add(key)
            citations.append(citation)

    for document in documents or []:
        metadata = getattr(document, "metadata", None) or {}

        if metadata.get("source") == consts.WEB_SEARCH_SOURCE:
            found_web_source = False
            for entry in metadata.get("web_sources") or []:
                if not isinstance(entry, dict):
                    continue
                url = _optional_text(entry.get("url"))
                if url is None:
                    continue
                found_web_source = True
                append(
                    Citation(
                        kind="web",
                        title=_optional_text(entry.get("title")),
                        source=None,
                        url=url,
                        document_category=None,
                        query=None,
                        snippet=None,
                    )
                )

            if not found_web_source:
                query = _optional_text(metadata.get("search_query"))
                if query is not None:
                    append(
                        Citation(
                            kind="web_query",
                            title=None,
                            source=None,
                            url=None,
                            document_category=None,
                            query=query,
                            snippet=None,
                        )
                    )
            continue

        page_content = getattr(document, "page_content", None)
        append(
            Citation(
                kind="local",
                title=_optional_text(metadata.get("title")),
                source=_optional_text(metadata.get("source")),
                url=None,
                document_category=_optional_text(metadata.get("document_category")),
                query=None,
                snippet=(
                    str(page_content)[:LOCAL_SNIPPET_MAX_CHARS]
                    if page_content is not None
                    else None
                ),
            )
        )

    return citations


def _build_ask_response(
    result: engine.AnswerResult,
    provider: str,
    status: str,
) -> AskResponse:
    if result.run_id is None:
        raise RuntimeError("AnswerResult is missing a run_id")

    return AskResponse(
        run_id=result.run_id,
        question=result.question,
        input_redacted=result.input_redacted,
        question_sha256=result.question_sha256,
        answer=result.answer,
        caveat=formatting.STOP_REASON_NOTES.get(result.stop_reason),
        stop_reason=result.stop_reason,
        status=status,
        citations=_build_citations(result.raw_state.get("documents", [])),
        source_lines=list(result.sources),
        node_path=list(result.node_path),
        node_timings_ms=[NodeTiming.model_validate(entry) for entry in result.node_timings_ms],
        total_duration_ms=result.total_duration_ms,
        retries=result.retries,
        tracked_llm_calls=result.tracked_llm_calls,
        web_search_count=result.web_search_count,
        web_result_grading_count=result.web_result_grading_count,
        runtime=RunRuntime(
            provider=provider,
            web_search_enabled=result.web_search_enabled,
            web_fallback_policy=result.web_fallback_policy,
        ),
    )


def _internal_error(exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "exception_type": type(exc).__name__,
        },
    )


def create_app() -> FastAPI:
    """Create one isolated FastAPI application instance."""

    @asynccontextmanager
    async def lifespan(running_app: FastAPI) -> AsyncIterator[None]:
        try:
            main.run_startup_preflight()
        except main.PreflightError as exc:
            print(f"Startup preflight failed:\n  {exc}")
            running_app.state.preflight = PreflightStatus(
                ok=False,
                message=PREFLIGHT_FAILURE_MESSAGE,
            )
        else:
            running_app.state.preflight = PreflightStatus(ok=True, message=None)

        yield

    application = FastAPI(lifespan=lifespan)
    application.state.run_store = RunStore()
    application.state.ask_lock = Lock()

    @application.exception_handler(Exception)
    async def unexpected_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        return _internal_error(exc)

    @application.post("/api/ask", response_model=AskResponse)
    def ask(payload: AskRequest, request: Request) -> AskResponse | JSONResponse:
        preflight: PreflightStatus = request.app.state.preflight
        if not preflight.ok:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "preflight_failed",
                    "message": PREFLIGHT_FAILURE_MESSAGE,
                },
            )

        ask_lock = request.app.state.ask_lock
        if not ask_lock.acquire(blocking=False):
            return JSONResponse(
                status_code=409,
                content={
                    "error": "run_in_progress",
                    "message": RUN_IN_PROGRESS_MESSAGE,
                },
            )

        try:
            try:
                result = engine.answer_question(
                    payload.question,
                    engine.AnswerOptions(
                        web_search_enabled=payload.web_search_enabled,
                        web_fallback_policy=payload.web_fallback_policy,
                    ),
                )
            except ValueError as exc:
                return JSONResponse(
                    status_code=503,
                    content={"error": "config_error", "message": str(exc)},
                )
            except Exception as exc:
                return _internal_error(exc)

            try:
                provider = config.llm_provider()
            except ValueError as exc:
                return JSONResponse(
                    status_code=503,
                    content={"error": "config_error", "message": str(exc)},
                )

            try:
                status = _run_status(result.stop_reason)
                response = _build_ask_response(result, provider, status)
                record = engine.build_trace(result)
                record.update(
                    {
                        "provider": provider,
                        "status": status,
                        "retries": result.retries,
                        "web_search_count": result.web_search_count,
                    }
                )
                run_store: RunStore = request.app.state.run_store
                run_store.add(record)
            except Exception as exc:
                return _internal_error(exc)

            return response
        finally:
            ask_lock.release()

    @application.get("/api/status", response_model=RuntimeStatus)
    def get_status(request: Request) -> RuntimeStatus:
        return build_runtime_status(request.app.state.preflight)

    @application.get("/api/documents", response_model=DocumentsResponse)
    def get_documents(request: Request) -> DocumentsResponse:
        runtime = build_runtime_status(request.app.state.preflight)
        documents = list_corpus_documents()
        return DocumentsResponse(
            documents=documents,
            document_count=len(documents),
            index=runtime.index,
            config_error=runtime.config_error,
        )

    @application.get("/api/runs", response_model=RunsResponse)
    def get_runs(request: Request) -> RunsResponse:
        run_store: RunStore = request.app.state.run_store
        runs = run_store.list_summaries()
        return RunsResponse(
            runs=[RunSummary.model_validate(run) for run in runs],
            count=len(runs),
            limit=run_store.limit,
        )

    @application.get("/api/runs/{run_id}", response_model=RunDetail)
    def get_run(run_id: str, request: Request) -> RunDetail | JSONResponse:
        run_store: RunStore = request.app.state.run_store
        record = run_store.get(run_id)
        if record is None:
            return JSONResponse(status_code=404, content={"error": "run_not_found"})
        return RunDetail.model_validate(record)

    frontend_dist = Path("frontend/dist")
    if (frontend_dist / "index.html").is_file():
        application.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

    return application


app = create_app()
