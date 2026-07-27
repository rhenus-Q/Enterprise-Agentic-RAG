import { mockApiClient, mockScenarioController } from "./mock";
import {
  ApiError,
  type ApiClient,
  type ApiErrorPayload,
  type AskRequest,
  type AskResponse,
  type DocumentsResponse,
  type RunDetail,
  type RunsResponse,
  type RuntimeStatus,
} from "./types";

const USE_MOCKS = true;

function isErrorPayload(value: unknown): value is ApiErrorPayload {
  return typeof value === "object" && value !== null;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;

  try {
    response = await fetch(path, init);
  } catch {
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
  ask(request: AskRequest): Promise<AskResponse> {
    return requestJson<AskResponse>("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
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
