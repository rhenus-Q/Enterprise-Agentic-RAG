import { mockApiClient, mockScenarioController } from "./mock";
import {
  ApiError,
  requestCancelledError,
  type ApiClient,
  type ApiErrorPayload,
  type AskOptions,
  type AskRequest,
  type AskResponse,
  type CancelRunResponse,
  type DocumentsResponse,
  type RunDetail,
  type RunsResponse,
  type RuntimeStatus,
} from "./types";

const USE_MOCKS = false;

function isErrorPayload(value: unknown): value is ApiErrorPayload {
  return typeof value === "object" && value !== null;
}

function wasAborted(error: unknown, signal: AbortSignal | null | undefined): boolean {
  return Boolean(signal?.aborted) || (error instanceof DOMException && error.name === "AbortError");
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;

  try {
    response = await fetch(path, init);
  } catch (error) {
    // An abort is separated from a transport failure before anything else:
    // both surface as a rejected fetch, but telling the user the backend is
    // unreachable because they pressed Stop would be a lie about the system.
    if (wasAborted(error, init?.signal)) {
      throw requestCancelledError();
    }

    throw new ApiError("The backend could not be reached.", {
      code: "backend_unreachable",
      networkError: true,
    });
  }

  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  // Aborting while the body streams leaves an unusable payload behind; report
  // it as the stop it was rather than as a malformed response.
  if (init?.signal?.aborted) {
    throw requestCancelledError();
  }

  if (!response.ok) {
    const errorPayload = isErrorPayload(payload) ? payload : null;
    throw new ApiError(errorPayload?.message ?? "The request was not successful.", {
      status: response.status,
      code: errorPayload?.error ?? "request_failed",
      payload: errorPayload,
    });
  }

  return payload as T;
}

const realApiClient: ApiClient = {
  ask(request: AskRequest, options?: AskOptions): Promise<AskResponse> {
    return requestJson<AskResponse>("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
      signal: options?.signal,
    });
  },
  cancelRun(): Promise<CancelRunResponse> {
    return requestJson<CancelRunResponse>("/api/ask/cancel", { method: "POST" });
  },
  getStatus(): Promise<RuntimeStatus> {
    return requestJson<RuntimeStatus>("/api/status");
  },
  getDocuments(): Promise<DocumentsResponse> {
    return requestJson<DocumentsResponse>("/api/documents");
  },
  getRuns(): Promise<RunsResponse> {
    return requestJson<RunsResponse>("/api/runs");
  },
  getRun(runId: string): Promise<RunDetail> {
    return requestJson<RunDetail>(`/api/runs/${encodeURIComponent(runId)}`);
  },
};

export const apiClient: ApiClient = USE_MOCKS ? mockApiClient : realApiClient;
export const demoScenarioController = USE_MOCKS ? mockScenarioController : null;
