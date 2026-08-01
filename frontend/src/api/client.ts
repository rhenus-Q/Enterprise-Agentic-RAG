import { mockApiClient, mockScenarioController } from "./mock";
import {
  ApiError,
  requestCancelledError,
  REQUEST_TIMEOUT_CODE,
  type ApiClient,
  type ApiErrorPayload,
  type AskOptions,
  type AskRequest,
  type AskResponse,
  type CancelRunOptions,
  type CancelRunResponse,
  type DocumentsResponse,
  type RunDetail,
  type RunsResponse,
  type RuntimeStatus,
} from "./types";

const USE_MOCKS = false;

export const DEFAULT_REQUEST_TIMEOUT_MS = 30_000;
export const ASK_REQUEST_TIMEOUT_MS = 5 * 60_000;
const SERVER_CANCEL_WAIT_MARGIN_MS = 15_000;
const CANCEL_REQUEST_TIMEOUT_BUFFER_MS = 15_000;
// Fallback for callers without resolved runtime status: the server's default
// 60-second LLM timeout, its 15-second unwind margin, and a client buffer.
export const CANCEL_REQUEST_TIMEOUT_MS = 90_000;

interface RequestOptions {
  timeoutMs?: number;
}

function isErrorPayload(value: unknown): value is ApiErrorPayload {
  return typeof value === "object" && value !== null;
}

function wasAborted(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function requestTimeoutError(): ApiError {
  return new ApiError("The request took longer than expected.", {
    code: REQUEST_TIMEOUT_CODE,
  });
}

export function cancelRequestTimeoutMs(
  llmRequestTimeoutSeconds: number | null | undefined,
): number {
  if (
    typeof llmRequestTimeoutSeconds !== "number" ||
    !Number.isFinite(llmRequestTimeoutSeconds) ||
    llmRequestTimeoutSeconds <= 0
  ) {
    return CANCEL_REQUEST_TIMEOUT_MS;
  }

  const configuredServerWait =
    llmRequestTimeoutSeconds * 1_000 + SERVER_CANCEL_WAIT_MARGIN_MS;
  return Math.max(
    CANCEL_REQUEST_TIMEOUT_MS,
    configuredServerWait + CANCEL_REQUEST_TIMEOUT_BUFFER_MS,
  );
}

async function requestJson<T>(
  path: string,
  init: RequestInit = {},
  options: RequestOptions = {},
): Promise<T> {
  const callerSignal = init.signal;
  const requestController = new AbortController();
  let abortCause: "caller" | "timeout" | null = null;

  const abortFromCaller = () => {
    if (abortCause === null) {
      abortCause = "caller";
      requestController.abort();
    }
  };

  if (callerSignal?.aborted) {
    abortFromCaller();
  } else {
    callerSignal?.addEventListener("abort", abortFromCaller, { once: true });
  }

  const timeout = window.setTimeout(() => {
    if (abortCause === null) {
      abortCause = "timeout";
      requestController.abort();
    }
  }, options.timeoutMs ?? DEFAULT_REQUEST_TIMEOUT_MS);

  try {
    let response: Response;

    if (abortCause === "caller") {
      throw requestCancelledError();
    }

    try {
      response = await fetch(path, {
        ...init,
        signal: requestController.signal,
      });
    } catch (error) {
      if (abortCause === "timeout") {
        throw requestTimeoutError();
      }
      // An abort is separated from a transport failure before anything else:
      // both surface as a rejected fetch, but telling the user the backend is
      // unreachable because they pressed Stop would be a lie about the system.
      if (abortCause === "caller" || wasAborted(error)) {
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
    } catch (error) {
      if (abortCause === "timeout") {
        throw requestTimeoutError();
      }
      if (abortCause === "caller" || wasAborted(error)) {
        throw requestCancelledError();
      }

      if (response.ok) {
        throw new ApiError("The backend returned an invalid response.", {
          status: response.status,
          code: "invalid_response",
        });
      }

      payload = null;
    }

    // Aborting while the body streams leaves an unusable payload behind;
    // report the first abort cause rather than a malformed response.
    if (abortCause === "timeout") {
      throw requestTimeoutError();
    }
    if (abortCause === "caller") {
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
  } finally {
    window.clearTimeout(timeout);
    callerSignal?.removeEventListener("abort", abortFromCaller);
  }
}

const realApiClient: ApiClient = {
  ask(request: AskRequest, options?: AskOptions): Promise<AskResponse> {
    return requestJson<AskResponse>(
      "/api/ask",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
        signal: options?.signal,
      },
      { timeoutMs: ASK_REQUEST_TIMEOUT_MS },
    );
  },
  cancelRun(options?: CancelRunOptions): Promise<CancelRunResponse> {
    return requestJson<CancelRunResponse>(
      "/api/ask/cancel",
      { method: "POST" },
      { timeoutMs: cancelRequestTimeoutMs(options?.llmRequestTimeoutSeconds) },
    );
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
