export type WebFallbackPolicy = "conservative" | "aggressive" | "disabled";
export type CitationKind = "local" | "web" | "web_query";
export type RunStatus = "ok" | "caveat" | "error";
export type IndexCompatibility =
  | "compatible"
  | "legacy_no_fingerprint"
  | "provider_mismatch"
  | "model_mismatch"
  | "missing_index";

export interface AskRequest {
  question: string;
  web_search_enabled: boolean | null;
  web_fallback_policy: WebFallbackPolicy | null;
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
  exists: boolean;
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
  fully_local_mode: boolean | null;
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

export interface ApiClient {
  ask(request: AskRequest): Promise<AskResponse>;
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
