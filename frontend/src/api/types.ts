export type WebFallbackPolicy = "conservative" | "aggressive" | "disabled";
export type CitationKind = "local" | "web" | "web_query";
export type RunStatus = "ok" | "caveat" | "error";
export type IndexCompatibility =
  | "compatible"
  | "legacy_no_fingerprint"
  | "provider_mismatch"
  | "model_mismatch"
  | "missing_index"
  | "index_unreadable";

export interface AskRequest {
  question: string;
  web_search_enabled: boolean | null;
  web_fallback_policy: WebFallbackPolicy | null;
}

export interface AskOptions {
  /**
   * Aborts the HTTP request locally. This is separate from actually stopping
   * the run: `cancelRun()` (ADR 017) tells the backend to cancel the
   * in-flight graph execution, which is what stops it from costing further
   * provider calls or landing in run history. AskPage asks the server to
   * cancel first and only aborts this request afterwards, once the server
   * confirms the run has stopped — so `signal` alone is not "the run was
   * cancelled".
   */
  signal?: AbortSignal;
}

export interface Citation {
  kind: CitationKind;
  title: string | null;
  source: string | null;
  url: string | null;
  document_category: string | null;
  query: string | null;
  snippet: string | null;
}

export interface NodeTiming {
  node: string;
  duration_ms: number;
}

export interface RunRuntime {
  provider: string;
  web_search_enabled: boolean;
  web_fallback_policy: string;
}

export interface AskResponse {
  run_id: string;
  question: string;
  input_redacted: boolean;
  question_sha256: string;
  answer: string;
  caveat: string | null;
  stop_reason: string;
  status: RunStatus;
  citations: Citation[];
  source_lines: string[];
  node_path: string[];
  node_timings_ms: NodeTiming[];
  total_duration_ms: number;
  retries: number;
  tracked_llm_calls: number;
  web_search_count: number;
  web_result_grading_count: number;
  runtime: RunRuntime;
}

export interface IndexStatus {
  persist_directory: string;
  collection_name: string;
  /** null when the index could not be inspected — unknown, not absent. */
  exists: boolean | null;
  stored_fingerprint: Record<string, string> | null;
  expected_fingerprint: Record<string, string>;
  compatibility: IndexCompatibility;
  reindex_required: boolean;
}

export interface PreflightStatus {
  ok: boolean;
  message: string | null;
}

export interface RuntimeStatus {
  provider: string | null;
  chat_model: string | null;
  embedding_provider: string | null;
  embedding_model: string | null;
  privacy_mode: boolean | null;
  /** Effective resolved runtime mode, not the FULLY_LOCAL_MODE variable. */
  local_mode: boolean | null;
  web_search_enabled_default: boolean | null;
  web_search_locked: boolean | null;
  web_fallback_policy_default: string | null;
  budgets: Record<string, number> | null;
  llm_request_timeout_seconds: number | null;
  index: IndexStatus | null;
  preflight: PreflightStatus;
  config_error: string | null;
}

export interface DocumentInfo {
  source: string;
  file_name: string;
  title: string;
  document_category: string;
  source_type: string;
  size_bytes: number;
  modified_at: string;
}

export interface DocumentsResponse {
  documents: DocumentInfo[];
  document_count: number;
  index: IndexStatus | null;
  config_error: string | null;
}

export interface RunSummary {
  run_id: string;
  generated_at: string;
  question_redacted: string;
  status: RunStatus;
  stop_reason: string;
  total_duration_ms: number;
  provider: string;
  retries: number;
  web_search_count: number;
}

export interface RunDetail extends RunSummary {
  question_sha256: string;
  input_redacted: boolean;
  node_path: string[];
  node_timings_ms: NodeTiming[];
  counters: Record<string, number>;
  web_search_enabled: boolean;
  web_fallback_policy: string;
  sources: string[];
}

export interface RunsResponse {
  runs: RunSummary[];
  count: number;
  limit: number;
}

export interface CancelRunResponse {
  cancelled: boolean;
  /** True once the server finished unwinding, so a new question will not 409. */
  idle: boolean;
}

export interface CancelRunOptions {
  /** Resolved backend LLM timeout used to bound its cancellation wait. */
  llmRequestTimeoutSeconds?: number | null;
}

export interface ApiErrorPayload {
  error?: string;
  message?: string;
  exception_type?: string;
}

export class ApiError extends Error {
  readonly status: number | null;
  readonly code: string;
  readonly payload: ApiErrorPayload | null;
  readonly networkError: boolean;

  constructor(
    message: string,
    options: {
      status?: number | null;
      code?: string;
      payload?: ApiErrorPayload | null;
      networkError?: boolean;
    } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = options.status ?? null;
    this.code = options.code ?? "request_failed";
    this.payload = options.payload ?? null;
    this.networkError = options.networkError ?? false;
  }
}

export const REQUEST_CANCELLED_CODE = "request_cancelled";
export const REQUEST_TIMEOUT_CODE = "request_timeout";

/**
 * The backend's code for a run it stopped on request (HTTP 499).
 *
 * Distinct from REQUEST_CANCELLED_CODE only in who noticed first — the browser
 * aborting locally, or the server finishing the cancellation and answering the
 * abandoned request. Both describe the same user action.
 */
export const RUN_CANCELLED_CODE = "run_cancelled";

/**
 * The error both clients raise when the caller aborted the request.
 *
 * Shared so the mock and real clients stay interchangeable: a stop must look
 * identical in both, and must never be mistaken for a connectivity failure.
 */
export function requestCancelledError(): ApiError {
  return new ApiError("The request was stopped.", { code: REQUEST_CANCELLED_CODE });
}

/**
 * True for either shape of "the user stopped this run".
 *
 * Both must be excluded from error rendering: a stop is a choice the user
 * made, and reporting it as a failed request blames the system for it.
 */
export function isRequestCancelled(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    (error.code === REQUEST_CANCELLED_CODE || error.code === RUN_CANCELLED_CODE)
  );
}

export const RUN_IN_PROGRESS_CODE = "run_in_progress";
export const RUN_STILL_STOPPING_CODE = "run_still_stopping";
export const BACKEND_UNREACHABLE_CODE = "backend_unreachable";

/**
 * Codes that mean "try again shortly" rather than "something is broken".
 *
 * Kept apart from the failure codes so a busy server can be answered in a
 * calmer register than an internal error: same copy, different tone.
 */
const RETRYABLE_ERROR_CODES: ReadonlySet<string> = new Set([
  RUN_IN_PROGRESS_CODE,
  RUN_STILL_STOPPING_CODE,
]);

export function isRetryableError(error: ApiError): boolean {
  return RETRYABLE_ERROR_CODES.has(error.code);
}

export interface ApiClient {
  ask(request: AskRequest, options?: AskOptions): Promise<AskResponse>;
  /**
   * Stops the in-flight run server-side. The response's `idle` field reports
   * whether the backend is free for a new question without racing a 409.
   */
  cancelRun(options?: CancelRunOptions): Promise<CancelRunResponse>;
  getStatus(): Promise<RuntimeStatus>;
  getDocuments(): Promise<DocumentsResponse>;
  getRuns(): Promise<RunsResponse>;
  getRun(runId: string): Promise<RunDetail>;
}

export function normalizeApiError(error: unknown): ApiError {
  if (error instanceof ApiError) {
    return error;
  }

  return new ApiError("The application could not complete the request.", {
    code: "request_failed",
  });
}
