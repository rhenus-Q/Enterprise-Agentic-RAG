"""Pure Pydantic models defining the web application's public API contract."""

from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

Question = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4000),
]
WebFallbackPolicy = Literal["conservative", "aggressive", "disabled"]
CitationKind = Literal["local", "web", "web_query"]


class AskRequest(BaseModel):
    question: Question
    web_search_enabled: bool | None = None
    web_fallback_policy: WebFallbackPolicy | None = None


class Citation(BaseModel):
    kind: CitationKind
    title: str | None
    source: str | None
    url: str | None
    document_category: str | None
    query: str | None
    snippet: str | None


class NodeTiming(BaseModel):
    node: str
    duration_ms: float


class RunRuntime(BaseModel):
    provider: str
    web_search_enabled: bool
    web_fallback_policy: str


class AskResponse(BaseModel):
    run_id: str
    question: str
    input_redacted: bool
    question_sha256: str
    answer: str
    caveat: str | None
    stop_reason: str
    status: str
    citations: list[Citation]
    source_lines: list[str]
    node_path: list[str]
    node_timings_ms: list[NodeTiming]
    total_duration_ms: float
    retries: int
    tracked_llm_calls: int
    web_search_count: int
    web_result_grading_count: int
    runtime: RunRuntime


class IndexStatus(BaseModel):
    persist_directory: str
    collection_name: str
    exists: bool
    stored_fingerprint: dict[str, str] | None
    expected_fingerprint: dict[str, str]
    compatibility: str
    reindex_required: bool


class PreflightStatus(BaseModel):
    ok: bool
    message: str | None


class RuntimeStatus(BaseModel):
    provider: str | None
    chat_model: str | None
    embedding_provider: str | None
    embedding_model: str | None
    privacy_mode: bool | None
    fully_local_mode: bool | None
    web_search_enabled_default: bool | None
    web_search_locked: bool | None
    web_fallback_policy_default: str | None
    budgets: dict[str, int] | None
    llm_request_timeout_seconds: int | None
    index: IndexStatus | None
    preflight: PreflightStatus
    config_error: str | None


class DocumentInfo(BaseModel):
    source: str
    file_name: str
    title: str
    document_category: str
    source_type: str
    size_bytes: int
    modified_at: str


class DocumentsResponse(BaseModel):
    documents: list[DocumentInfo]
    document_count: int
    index: IndexStatus | None
    config_error: str | None


class RunSummary(BaseModel):
    run_id: str
    generated_at: str
    question_redacted: str
    status: str
    stop_reason: str
    total_duration_ms: float
    provider: str
    retries: int
    web_search_count: int


class RunDetail(RunSummary):
    question_sha256: str
    input_redacted: bool
    node_path: list[str]
    node_timings_ms: list[NodeTiming]
    counters: dict[str, int]
    web_search_enabled: bool
    web_fallback_policy: str
    sources: list[str]


class RunsResponse(BaseModel):
    runs: list[RunSummary]
    count: int
    limit: int
