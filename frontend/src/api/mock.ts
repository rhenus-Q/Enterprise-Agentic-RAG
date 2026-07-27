import {
  askFixtures,
  documentsResponseFor,
  emptyRunsResponse,
  indexFixtures,
  populatedRunsResponse,
  runDetailFixtures,
  runtimeFixtures,
} from "../mocks/fixtures";
import {
  ApiError,
  type ApiClient,
  type AskRequest,
  type AskResponse,
  type DocumentsResponse,
  type IndexStatus,
  type RunDetail,
  type RunsResponse,
  type RuntimeStatus,
} from "./types";

export type MockScenario =
  | "ask-local"
  | "ask-web"
  | "privacy-locked"
  | "local-mode"
  | "web-fallback-disabled"
  | "max-retries"
  | "budget-exhausted"
  | "generation-error"
  | "preflight-error"
  | "config-error"
  | "internal-error"
  | "run-in-progress"
  | "backend-unreachable"
  | "index-compatible"
  | "index-legacy-openai"
  | "index-legacy-local"
  | "index-provider-mismatch"
  | "index-model-mismatch"
  | "index-missing"
  | "runs-populated"
  | "runs-empty";

export interface MockScenarioOption {
  id: MockScenario;
  label: string;
  page: "ask" | "documents" | "runs";
}

const options: MockScenarioOption[] = [
  { id: "ask-local", label: "Ask · local evidence", page: "ask" },
  { id: "ask-web", label: "Ask · web supplement", page: "ask" },
  { id: "privacy-locked", label: "Ask · privacy lock", page: "ask" },
  { id: "local-mode", label: "Ask · fully local mode", page: "ask" },
  { id: "web-fallback-disabled", label: "Ask · fallback disabled", page: "ask" },
  { id: "max-retries", label: "Ask · grounding caveat", page: "ask" },
  { id: "budget-exhausted", label: "Ask · budget exhausted", page: "ask" },
  { id: "generation-error", label: "Ask · generation failure", page: "ask" },
  { id: "preflight-error", label: "Ask · preflight 503", page: "ask" },
  { id: "config-error", label: "Ask · config 503", page: "ask" },
  { id: "internal-error", label: "Ask · internal 500", page: "ask" },
  { id: "run-in-progress", label: "Ask · run in progress", page: "ask" },
  { id: "backend-unreachable", label: "App · backend unreachable", page: "ask" },
  { id: "index-compatible", label: "Documents · compatible", page: "documents" },
  { id: "index-legacy-openai", label: "Documents · legacy accepted", page: "documents" },
  { id: "index-legacy-local", label: "Documents · legacy needs reindex", page: "documents" },
  {
    id: "index-provider-mismatch",
    label: "Documents · provider mismatch",
    page: "documents",
  },
  { id: "index-model-mismatch", label: "Documents · model mismatch", page: "documents" },
  { id: "index-missing", label: "Documents · missing index", page: "documents" },
  { id: "runs-populated", label: "Runs · populated history", page: "runs" },
  { id: "runs-empty", label: "Runs · empty history", page: "runs" },
];

let activeScenario: MockScenario = "ask-local";
const listeners = new Set<() => void>();

function delay<T>(value: T, milliseconds = 180): Promise<T> {
  return new Promise((resolve) => {
    window.setTimeout(() => resolve(value), milliseconds);
  });
}

function reject(error: ApiError, milliseconds = 180): Promise<never> {
  return new Promise((_, rejectPromise) => {
    window.setTimeout(() => rejectPromise(error), milliseconds);
  });
}

function indexForScenario(): IndexStatus {
  switch (activeScenario) {
    case "index-legacy-openai":
      return indexFixtures.legacy_no_fingerprint;
    case "index-legacy-local":
      return {
        ...indexFixtures.legacy_no_fingerprint,
        persist_directory: "chroma_db_local",
        collection_name: "agentic_rag_docs_local",
        expected_fingerprint: {
          embedding_provider: "ollama",
          embedding_model: "qwen3-embedding:0.6b",
        },
        reindex_required: true,
      };
    case "index-provider-mismatch":
      return indexFixtures.provider_mismatch;
    case "index-model-mismatch":
      return indexFixtures.model_mismatch;
    case "index-missing":
      return indexFixtures.missing_index;
    default:
      return indexFixtures.compatible;
  }
}

function runtimeForScenario(): RuntimeStatus {
  switch (activeScenario) {
    case "privacy-locked":
      return runtimeFixtures.privacy;
    case "local-mode":
    case "index-legacy-local":
    case "index-model-mismatch":
    case "index-missing":
      return { ...runtimeFixtures.local, index: indexForScenario() };
    case "preflight-error":
      return runtimeFixtures.preflightFailed;
    case "config-error":
      return runtimeFixtures.configError;
    default:
      return { ...runtimeFixtures.openai, index: indexForScenario() };
  }
}

function askResponseForScenario(): AskResponse {
  switch (activeScenario) {
    case "ask-web":
      return askFixtures.webSuccess;
    case "privacy-locked":
      return {
        ...askFixtures.webSearchDisabled,
        runtime: {
          provider: "openai",
          web_search_enabled: false,
          web_fallback_policy: "conservative",
        },
      };
    case "local-mode":
      return {
        ...askFixtures.webSearchDisabled,
        runtime: {
          provider: "ollama",
          web_search_enabled: false,
          web_fallback_policy: "conservative",
        },
      };
    case "web-fallback-disabled":
      return askFixtures.webFallbackDisabled;
    case "max-retries":
      return askFixtures.maxRetriesNotGrounded;
    case "budget-exhausted":
      return askFixtures.budgetExhausted;
    case "generation-error":
      return askFixtures.generationError;
    default:
      return askFixtures.localSuccess;
  }
}

function requestErrorForScenario(): ApiError | null {
  switch (activeScenario) {
    case "preflight-error":
      return new ApiError("Startup preflight failed — see the server console for details.", {
        status: 503,
        code: "preflight_failed",
        payload: {
          error: "preflight_failed",
          message: "Startup preflight failed — see the server console for details.",
        },
      });
    case "config-error":
      return new ApiError("The runtime configuration is invalid.", {
        status: 503,
        code: "config_error",
        payload: {
          error: "config_error",
          message: "The runtime configuration is invalid.",
        },
      });
    case "internal-error":
      return new ApiError("The request could not be completed.", {
        status: 500,
        code: "internal_error",
        payload: {
          error: "internal_error",
          exception_type: "RuntimeError",
        },
      });
    case "run-in-progress":
      return new ApiError("Another question is currently being processed.", {
        status: 409,
        code: "run_in_progress",
        payload: {
          error: "run_in_progress",
          message: "Another question is currently being processed.",
        },
      });
    case "backend-unreachable":
      return new ApiError("The backend could not be reached.", {
        code: "backend_unreachable",
        networkError: true,
      });
    default:
      return null;
  }
}

export const mockApiClient: ApiClient = {
  ask(_request: AskRequest): Promise<AskResponse> {
    const error = requestErrorForScenario();
    return error ? reject(error, 320) : delay(askResponseForScenario(), 520);
  },
  getStatus(): Promise<RuntimeStatus> {
    if (activeScenario === "backend-unreachable") {
      return reject(
        new ApiError("The backend could not be reached.", {
          code: "backend_unreachable",
          networkError: true,
        }),
      );
    }
    return delay(runtimeForScenario());
  },
  getDocuments(): Promise<DocumentsResponse> {
    if (activeScenario === "backend-unreachable") {
      return reject(
        new ApiError("The backend could not be reached.", {
          code: "backend_unreachable",
          networkError: true,
        }),
      );
    }
    return delay(documentsResponseFor(indexForScenario()));
  },
  getRuns(): Promise<RunsResponse> {
    if (activeScenario === "backend-unreachable") {
      return reject(
        new ApiError("The backend could not be reached.", {
          code: "backend_unreachable",
          networkError: true,
        }),
      );
    }
    return delay(activeScenario === "runs-empty" ? emptyRunsResponse : populatedRunsResponse);
  },
  getRun(runId: string): Promise<RunDetail> {
    const detail = runDetailFixtures[runId];
    if (!detail) {
      return reject(
        new ApiError("Run not found.", {
          status: 404,
          code: "run_not_found",
          payload: { error: "run_not_found" },
        }),
      );
    }
    return delay(detail, 120);
  },
};

export const mockScenarioController = {
  options,
  getScenario(): MockScenario {
    return activeScenario;
  },
  setScenario(scenario: MockScenario): void {
    activeScenario = scenario;
    listeners.forEach((listener) => listener());
  },
  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};
