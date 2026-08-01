import { afterEach, describe, expect, it, vi } from "vitest";

import { askFixtures, runtimeFixtures } from "../mocks/fixtures";
import {
  apiClient,
  ASK_REQUEST_TIMEOUT_MS,
  cancelRequestTimeoutMs,
  CANCEL_REQUEST_TIMEOUT_MS,
  DEFAULT_REQUEST_TIMEOUT_MS,
} from "./client";
import {
  ApiError,
  isRequestCancelled,
  REQUEST_CANCELLED_CODE,
  REQUEST_TIMEOUT_CODE,
} from "./types";

const askRequest = {
  question: "What is the expense policy?",
  web_search_enabled: true,
  web_fallback_policy: "conservative" as const,
};

function jsonResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response;
}

function invalidJsonResponse(status: number, error: unknown = new SyntaxError("invalid JSON")) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockRejectedValue(error),
  } as unknown as Response;
}

function abortableFetch() {
  return vi.fn((_path: RequestInfo | URL, init?: RequestInit) => {
    return new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener(
        "abort",
        () => reject(new DOMException("browser detail must stay private", "AbortError")),
        { once: true },
      );
    });
  });
}

async function capturedError(promise: Promise<unknown>): Promise<ApiError> {
  const error = await promise.catch((requestError: unknown) => requestError);
  expect(error).toBeInstanceOf(ApiError);
  return error as ApiError;
}

afterEach(() => {
  vi.clearAllTimers();
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("real API client request contract", () => {
  it("returns a valid successful JSON response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(runtimeFixtures.openai)));

    await expect(apiClient.getStatus()).resolves.toEqual(runtimeFixtures.openai);
  });

  it("rejects a successful response whose body is not valid JSON", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(invalidJsonResponse(200)));

    const error = await capturedError(apiClient.getStatus());

    expect(error).toMatchObject({
      status: 200,
      code: "invalid_response",
      payload: null,
      networkError: false,
    });
    expect(error.message).toBe("The backend returned an invalid response.");
  });

  it("uses the expected path, method, headers, and serialized body for every method", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}));
    vi.stubGlobal("fetch", fetchMock);

    await apiClient.ask(askRequest);
    await apiClient.cancelRun();
    await apiClient.getStatus();
    await apiClient.getDocuments();
    await apiClient.getRuns();
    await apiClient.getRun("run/a b?");

    expect(fetchMock).toHaveBeenCalledTimes(6);
    expect(fetchMock.mock.calls.map(([path]) => path)).toEqual([
      "/api/ask",
      "/api/ask/cancel",
      "/api/status",
      "/api/documents",
      "/api/runs",
      "/api/runs/run%2Fa%20b%3F",
    ]);

    const askInit = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(askInit.method).toBe("POST");
    expect(askInit.headers).toEqual({ "Content-Type": "application/json" });
    expect(askInit.body).toBe(JSON.stringify(askRequest));
    expect(askInit.signal).toBeInstanceOf(AbortSignal);

    const cancelInit = fetchMock.mock.calls[1]?.[1] as RequestInit;
    expect(cancelInit.method).toBe("POST");
    expect(cancelInit.headers).toBeUndefined();
    expect(cancelInit.body).toBeUndefined();

    for (const call of fetchMock.mock.calls.slice(2)) {
      const init = call[1] as RequestInit;
      expect(init.method).toBeUndefined();
      expect(init.headers).toBeUndefined();
      expect(init.body).toBeUndefined();
    }
  });

  it("preserves a caller signal by forwarding its cancellation to the composed signal", async () => {
    const caller = new AbortController();
    let fetchSignal: AbortSignal | null = null;
    const fetchMock = vi.fn((_path: RequestInfo | URL, init?: RequestInit) => {
      fetchSignal = init?.signal ?? null;
      return new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener(
          "abort",
          () => reject(new DOMException("aborted", "AbortError")),
          { once: true },
        );
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const request = apiClient.ask(askRequest, { signal: caller.signal });
    expect(fetchSignal).not.toBe(caller.signal);
    expect((fetchSignal as AbortSignal | null)?.aborted).toBe(false);

    caller.abort();
    const error = await capturedError(request);

    expect((fetchSignal as AbortSignal | null)?.aborted).toBe(true);
    expect(error.code).toBe(REQUEST_CANCELLED_CODE);
  });
});

describe("structured HTTP errors", () => {
  it("preserves status, code, message, and payload for a busy 409", async () => {
    const payload = {
      error: "run_in_progress",
      message: "Another question is currently being processed.",
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(payload, 409)));

    const error = await capturedError(apiClient.ask(askRequest));

    expect(error.status).toBe(409);
    expect(error.code).toBe("run_in_progress");
    expect(error.message).toBe(payload.message);
    expect(error.payload).toEqual(payload);
    expect(error.networkError).toBe(false);
  });

  it("recognizes the backend 499 as cancellation", async () => {
    const payload = { error: "run_cancelled" };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(payload, 499)));

    const error = await capturedError(apiClient.ask(askRequest));

    expect(error).toMatchObject({ status: 499, code: "run_cancelled", payload });
    expect(isRequestCancelled(error)).toBe(true);
  });

  it("preserves allowed exception-type metadata for an internal 500", async () => {
    const payload = { error: "internal_error", exception_type: "RuntimeError" };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(payload, 500)));

    const error = await capturedError(apiClient.ask(askRequest));

    expect(error.status).toBe(500);
    expect(error.code).toBe("internal_error");
    expect(error.payload).toEqual(payload);
    expect(error.payload?.exception_type).toBe("RuntimeError");
  });

  it.each([
    ["config_error", "Runtime configuration is invalid — see /api/status for details."],
    ["preflight_failed", "Startup preflight failed — see the server console for details."],
  ])("preserves a structured 503 %s", async (code, message) => {
    const payload = { error: code, message };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(payload, 503)));

    const error = await capturedError(apiClient.ask(askRequest));

    expect(error.status).toBe(503);
    expect(error.code).toBe(code);
    expect(error.message).toBe(message);
    expect(error.payload).toEqual(payload);
  });

  it("maps a non-JSON error body to one fallback ApiError without leaking the parser error", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          invalidJsonResponse(502, new SyntaxError("DO-NOT-LEAK parser internals")),
        ),
    );

    const error = await capturedError(apiClient.getStatus());

    expect(error).toMatchObject({
      status: 502,
      code: "request_failed",
      payload: null,
      networkError: false,
    });
    expect(error.message).toBe("The request was not successful.");
    expect(error.message).not.toContain("DO-NOT-LEAK");
  });
});

describe("transport, cancellation, and timeout classification", () => {
  it("maps a fetch rejection to backend_unreachable without exposing its raw message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("private-host.internal DO-NOT-LEAK-SENTINEL")),
    );

    const error = await capturedError(apiClient.getStatus());

    expect(error).toMatchObject({
      status: null,
      code: "backend_unreachable",
      networkError: true,
    });
    expect(error.message).toBe("The backend could not be reached.");
    expect(error.message).not.toContain("private-host.internal");
  });

  it("maps a rejected fetch after caller cancellation to request_cancelled", async () => {
    const caller = new AbortController();
    vi.stubGlobal("fetch", abortableFetch());

    const request = apiClient.ask(askRequest, { signal: caller.signal });
    caller.abort();

    const error = await capturedError(request);
    expect(error.code).toBe(REQUEST_CANCELLED_CODE);
    expect(error.networkError).toBe(false);
    expect(isRequestCancelled(error)).toBe(true);
  });

  it("honors a caller signal that was already aborted", async () => {
    const caller = new AbortController();
    caller.abort();
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const error = await capturedError(apiClient.ask(askRequest, { signal: caller.signal }));

    expect(error.code).toBe(REQUEST_CANCELLED_CODE);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("treats cancellation while reading the response body as request cancellation", async () => {
    const caller = new AbortController();
    vi.stubGlobal(
      "fetch",
      vi.fn((_path: RequestInfo | URL, init?: RequestInit) =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () =>
            new Promise((_resolve, reject) => {
              init?.signal?.addEventListener(
                "abort",
                () => reject(new DOMException("body stream aborted", "AbortError")),
                { once: true },
              );
            }),
        } as Response),
      ),
    );

    const request = apiClient.ask(askRequest, { signal: caller.signal });
    await Promise.resolve();
    caller.abort();

    expect((await capturedError(request)).code).toBe(REQUEST_CANCELLED_CODE);
  });

  it("succeeds when a request resolves before its timeout", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(runtimeFixtures.openai)));

    await expect(apiClient.getStatus()).resolves.toEqual(runtimeFixtures.openai);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("aborts the underlying fetch and throws request_timeout after the bound", async () => {
    vi.useFakeTimers();
    let fetchSignal: AbortSignal | null = null;
    const fetchMock = abortableFetch().mockImplementation(
      (_path: RequestInfo | URL, init?: RequestInit) => {
        fetchSignal = init?.signal ?? null;
        return new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener(
            "abort",
            () => reject(new DOMException("raw timeout detail", "AbortError")),
            { once: true },
          );
        });
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    const request = capturedError(apiClient.getStatus());
    await vi.advanceTimersByTimeAsync(DEFAULT_REQUEST_TIMEOUT_MS);
    const error = await request;

    expect((fetchSignal as AbortSignal | null)?.aborted).toBe(true);
    expect(error).toMatchObject({
      status: null,
      code: REQUEST_TIMEOUT_CODE,
      networkError: false,
    });
    expect(error.message).toBe("The request took longer than expected.");
    expect(isRequestCancelled(error)).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("keeps caller cancellation when it happens before timeout", async () => {
    vi.useFakeTimers();
    const caller = new AbortController();
    vi.stubGlobal("fetch", abortableFetch());

    const request = apiClient.ask(askRequest, { signal: caller.signal });
    caller.abort();
    const error = await capturedError(request);
    await vi.advanceTimersByTimeAsync(ASK_REQUEST_TIMEOUT_MS);

    expect(error.code).toBe(REQUEST_CANCELLED_CODE);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("keeps timeout when it happens before later caller cancellation", async () => {
    vi.useFakeTimers();
    const caller = new AbortController();
    vi.stubGlobal("fetch", abortableFetch());

    const request = capturedError(apiClient.ask(askRequest, { signal: caller.signal }));
    await vi.advanceTimersByTimeAsync(ASK_REQUEST_TIMEOUT_MS);
    const error = await request;
    caller.abort();

    expect(error.code).toBe(REQUEST_TIMEOUT_CODE);
    expect(isRequestCancelled(error)).toBe(false);
  });

  it("keeps network rejection before timeout distinct from timeout", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network internals")));

    const error = await capturedError(apiClient.getStatus());

    expect(error.code).toBe("backend_unreachable");
    expect(error.networkError).toBe(true);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("keeps a structured backend error before timeout distinct from timeout", async () => {
    vi.useFakeTimers();
    const payload = { error: "config_error", message: "Configuration needs attention." };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(payload, 503)));

    const error = await capturedError(apiClient.getStatus());

    expect(error).toMatchObject({ status: 503, code: "config_error", payload });
    expect(error.code).not.toBe(REQUEST_TIMEOUT_CODE);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("uses the endpoint-specific Ask and cancel timeout bounds", async () => {
    vi.useFakeTimers();
    const fetchMock = abortableFetch();
    vi.stubGlobal("fetch", fetchMock);

    const ask = capturedError(apiClient.ask(askRequest));
    await vi.advanceTimersByTimeAsync(ASK_REQUEST_TIMEOUT_MS - 1);
    expect(fetchMock.mock.calls[0]?.[1]?.signal?.aborted).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    expect((await ask).code).toBe(REQUEST_TIMEOUT_CODE);

    const cancel = capturedError(apiClient.cancelRun());
    await vi.advanceTimersByTimeAsync(CANCEL_REQUEST_TIMEOUT_MS - 1);
    expect(fetchMock.mock.calls[1]?.[1]?.signal?.aborted).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    expect((await cancel).code).toBe(REQUEST_TIMEOUT_CODE);
  });

  it("keeps cancellation open beyond a configured backend wait above 90 seconds", async () => {
    vi.useFakeTimers();
    const fetchMock = abortableFetch();
    vi.stubGlobal("fetch", fetchMock);

    const llmRequestTimeoutSeconds = 120;
    const backendCancelWaitMs = (llmRequestTimeoutSeconds + 15) * 1_000;
    const configuredCancelTimeout = cancelRequestTimeoutMs(llmRequestTimeoutSeconds);
    expect(configuredCancelTimeout).toBe(150_000);
    expect(configuredCancelTimeout).toBeGreaterThan(backendCancelWaitMs);

    const cancel = capturedError(
      apiClient.cancelRun({ llmRequestTimeoutSeconds }),
    );
    await vi.advanceTimersByTimeAsync(configuredCancelTimeout - 1);
    expect(fetchMock.mock.calls[0]?.[1]?.signal?.aborted).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    expect((await cancel).code).toBe(REQUEST_TIMEOUT_CODE);
  });

  it("removes the caller abort listener after settlement", async () => {
    const caller = new AbortController();
    const addEventListener = vi.spyOn(caller.signal, "addEventListener");
    const removeEventListener = vi.spyOn(caller.signal, "removeEventListener");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(askFixtures.localSuccess)));

    await apiClient.ask(askRequest, { signal: caller.signal });

    expect(addEventListener).toHaveBeenCalledWith("abort", expect.any(Function), { once: true });
    expect(removeEventListener).toHaveBeenCalledWith("abort", expect.any(Function));
  });
});
