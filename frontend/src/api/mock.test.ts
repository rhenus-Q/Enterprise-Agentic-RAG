import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { runDetailFixtures } from "../mocks/fixtures";
import { mockApiClient, mockScenarioController } from "./mock";
import {
  ApiError,
  isRequestCancelled,
  type AskResponse,
  type DocumentsResponse,
  type RunDetail,
  type RunsResponse,
  type RuntimeStatus,
} from "./types";

const askRequest = {
  question: "What is the expense policy?",
  web_search_enabled: true,
  web_fallback_policy: "conservative" as const,
};

const indexScenarioExpectations = {
  "index-compatible": { compatibility: "compatible", reindexRequired: false },
  "index-legacy-openai": { compatibility: "legacy_no_fingerprint", reindexRequired: false },
  "index-legacy-local": { compatibility: "legacy_no_fingerprint", reindexRequired: true },
  "index-provider-mismatch": { compatibility: "provider_mismatch", reindexRequired: true },
  "index-model-mismatch": { compatibility: "model_mismatch", reindexRequired: true },
  "index-missing": { compatibility: "missing_index", reindexRequired: true },
} as const;

async function settle<T>(promise: Promise<T>): Promise<T> {
  await vi.runAllTimersAsync();
  return promise;
}

async function settleError(promise: Promise<unknown>): Promise<ApiError> {
  const outcome = promise.catch((error: unknown) => error);
  await vi.runAllTimersAsync();
  const error = await outcome;
  expect(error).toBeInstanceOf(ApiError);
  return error as ApiError;
}

beforeEach(() => {
  vi.useFakeTimers();
  mockScenarioController.setScenario("ask-local");
});

afterEach(() => {
  mockScenarioController.setScenario("ask-local");
  vi.clearAllTimers();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("mock API public contract", () => {
  it("implements every public ApiClient method directly", async () => {
    const statusPromise: Promise<RuntimeStatus> = mockApiClient.getStatus();
    const askPromise: Promise<AskResponse> = mockApiClient.ask(askRequest);
    const cancelPromise = mockApiClient.cancelRun();
    const documentsPromise: Promise<DocumentsResponse> = mockApiClient.getDocuments();
    const runsPromise: Promise<RunsResponse> = mockApiClient.getRuns();
    const detailPromise: Promise<RunDetail> = mockApiClient.getRun("run_01HV7Q2R8W");

    await vi.runAllTimersAsync();

    expect((await statusPromise).provider).toBe("openai");
    expect((await askPromise).status).toBe("ok");
    expect(await cancelPromise).toEqual({ cancelled: true, idle: true });
    expect((await documentsPromise).document_count).toBeGreaterThan(0);
    expect((await runsPromise).count).toBeGreaterThan(0);
    expect((await detailPromise).run_id).toBe("run_01HV7Q2R8W");
    expect(vi.getTimerCount()).toBe(0);
  });

  it("matches the real-client cancellation contract and clears the delayed response", async () => {
    const controller = new AbortController();
    const request = mockApiClient.ask(askRequest, { signal: controller.signal });
    controller.abort();

    const error = await settleError(request);

    expect(isRequestCancelled(error)).toBe(true);
    expect(error.code).toBe("request_cancelled");
    expect(vi.getTimerCount()).toBe(0);
  });

  it("returns the intended structured 404 for an unknown run", async () => {
    const error = await settleError(mockApiClient.getRun("missing/run"));

    expect(error).toMatchObject({
      status: 404,
      code: "run_not_found",
      payload: { error: "run_not_found" },
    });
  });

  it("isolates mutable results from shared fixtures and later calls", async () => {
    const first = await settle(mockApiClient.getRun("run_01HV7Q2R8W"));
    first.sources.push("mutated source");
    first.counters.retries = 999;

    const second = await settle(mockApiClient.getRun("run_01HV7Q2R8W"));

    expect(second.sources).not.toContain("mutated source");
    expect(second.counters.retries).toBe(runDetailFixtures.run_01HV7Q2R8W.counters.retries);
    expect(runDetailFixtures.run_01HV7Q2R8W.sources).not.toContain("mutated source");
  });

  it("snapshots a response at call time so scenario switches do not leak into it", async () => {
    mockScenarioController.setScenario("ask-web");
    const webRequest = mockApiClient.ask(askRequest);
    mockScenarioController.setScenario("ask-local");
    const localRequest = mockApiClient.ask(askRequest);

    await vi.runAllTimersAsync();

    expect((await webRequest).run_id).not.toBe((await localRequest).run_id);
    expect((await webRequest).citations.some((citation) => citation.kind === "web")).toBe(true);
    expect((await localRequest).citations.every((citation) => citation.kind === "local")).toBe(true);
    expect(mockScenarioController.getScenario()).toBe("ask-local");
  });

  it("notifies subscribers on a switch and stops after unsubscribe", () => {
    const listener = vi.fn();
    const unsubscribe = mockScenarioController.subscribe(listener);

    mockScenarioController.setScenario("runs-empty");
    expect(listener).toHaveBeenCalledTimes(1);
    unsubscribe();
    mockScenarioController.setScenario("ask-local");

    expect(listener).toHaveBeenCalledTimes(1);
  });
});

describe("maintained demo scenarios", () => {
  it.each(mockScenarioController.options)("covers $id", async ({ id, page }) => {
    mockScenarioController.setScenario(id);
    expect(mockScenarioController.getScenario()).toBe(id);

    switch (id) {
      case "ask-local": {
        const response = await settle(mockApiClient.ask(askRequest));
        expect(page).toBe("ask");
        expect(response.status).toBe("ok");
        expect(response.citations.every((citation) => citation.kind === "local")).toBe(true);
        break;
      }
      case "ask-web": {
        const response = await settle(mockApiClient.ask(askRequest));
        expect(response.status).toBe("ok");
        expect(response.web_search_count).toBe(1);
        expect(response.citations.some((citation) => citation.kind === "web")).toBe(true);
        expect(response.citations.some((citation) => citation.kind === "web_query")).toBe(true);
        break;
      }
      case "privacy-locked": {
        const status = await settle(mockApiClient.getStatus());
        const response = await settle(mockApiClient.ask(askRequest));
        expect(status.privacy_mode).toBe(true);
        expect(status.web_search_locked).toBe(true);
        expect(response.runtime.web_search_enabled).toBe(false);
        break;
      }
      case "local-mode": {
        const status = await settle(mockApiClient.getStatus());
        const response = await settle(mockApiClient.ask(askRequest));
        expect(status.local_mode).toBe(true);
        expect(status.provider).toBe("ollama");
        expect(status.chat_model).toContain("qwen3");
        expect(response.runtime.provider).toBe("ollama");
        break;
      }
      case "web-fallback-disabled": {
        const response = await settle(mockApiClient.ask(askRequest));
        expect(response.status).toBe("caveat");
        expect(response.stop_reason).toBe("web_fallback_disabled");
        expect(response.caveat).toContain("disabled by policy");
        break;
      }
      case "max-retries": {
        const response = await settle(mockApiClient.ask(askRequest));
        expect(response.status).toBe("caveat");
        expect(response.stop_reason).toBe("max_retries_not_grounded");
        expect(response.retries).toBe(5);
        break;
      }
      case "budget-exhausted": {
        const response = await settle(mockApiClient.ask(askRequest));
        expect(response.status).toBe("caveat");
        expect(response.stop_reason).toBe("budget_exhausted");
        expect(response.tracked_llm_calls).toBe(30);
        break;
      }
      case "generation-error": {
        const response = await settle(mockApiClient.ask(askRequest));
        expect(response.status).toBe("error");
        expect(response.stop_reason).toBe("generation_error");
        expect(response.caveat).toContain("failed");
        break;
      }
      case "preflight-error": {
        const status = await settle(mockApiClient.getStatus());
        const error = await settleError(mockApiClient.ask(askRequest));
        expect(status.preflight.ok).toBe(false);
        expect(error).toMatchObject({ status: 503, code: "preflight_failed" });
        break;
      }
      case "config-error": {
        const status = await settle(mockApiClient.getStatus());
        const error = await settleError(mockApiClient.ask(askRequest));
        expect(status.provider).toBeNull();
        expect(status.config_error).toContain("LLM_PROVIDER");
        expect(error).toMatchObject({ status: 503, code: "config_error" });
        break;
      }
      case "internal-error": {
        const error = await settleError(mockApiClient.ask(askRequest));
        expect(error).toMatchObject({ status: 500, code: "internal_error" });
        expect(error.payload?.exception_type).toBe("RuntimeError");
        break;
      }
      case "run-in-progress": {
        const error = await settleError(mockApiClient.ask(askRequest));
        expect(error).toMatchObject({ status: 409, code: "run_in_progress" });
        expect(error.payload?.message).toContain("currently being processed");
        break;
      }
      case "backend-unreachable": {
        const error = await settleError(mockApiClient.getStatus());
        expect(error).toMatchObject({ code: "backend_unreachable", networkError: true });
        break;
      }
      case "index-compatible":
      case "index-legacy-openai":
      case "index-legacy-local":
      case "index-provider-mismatch":
      case "index-model-mismatch":
      case "index-missing": {
        const documents = await settle(mockApiClient.getDocuments());
        const expectation = indexScenarioExpectations[id];
        expect(page).toBe("documents");
        expect(documents.index?.compatibility).toBe(expectation.compatibility);
        expect(documents.index?.reindex_required).toBe(expectation.reindexRequired);
        expect(documents.documents.length).toBe(documents.document_count);
        break;
      }
      case "runs-populated": {
        const runs = await settle(mockApiClient.getRuns());
        const detail = await settle(mockApiClient.getRun(runs.runs[0]!.run_id));
        expect(page).toBe("runs");
        expect(runs.count).toBeGreaterThan(0);
        expect(detail.run_id).toBe(runs.runs[0]!.run_id);
        expect(detail.sources.length).toBeGreaterThan(0);
        break;
      }
      case "runs-empty": {
        const runs = await settle(mockApiClient.getRuns());
        expect(page).toBe("runs");
        expect(runs).toMatchObject({ runs: [], count: 0 });
        break;
      }
      default: {
        const exhaustive: never = id;
        throw new Error(`Unhandled mock scenario: ${exhaustive}`);
      }
    }
  });
});
