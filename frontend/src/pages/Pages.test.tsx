import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, type ApiClient, type DocumentsResponse, type RunDetail, type RunsResponse } from "../api/types";
import {
  askFixtures,
  documentsResponseFor,
  emptyRunsResponse,
  indexFixtures,
  populatedDocumentsResponse,
  populatedRunsResponse,
  runDetailFixtures,
  runtimeFixtures,
} from "../mocks/fixtures";
import { CONTENT_REVEAL_DURATION_MS } from "../components/ContentReveal";
import { DocumentsPage } from "./DocumentsPage";
import { RunsPage } from "./RunsPage";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function readOnlyClient(): ApiClient {
  return {
    ask: vi.fn().mockResolvedValue(askFixtures.localSuccess),
    cancelRun: vi.fn().mockResolvedValue({ cancelled: true, idle: true }),
    getStatus: vi.fn().mockResolvedValue(runtimeFixtures.openai),
    getDocuments: vi.fn().mockResolvedValue(populatedDocumentsResponse),
    getRuns: vi.fn().mockResolvedValue(populatedRunsResponse),
    getRun: vi.fn().mockResolvedValue(runDetailFixtures.run_01HV7Q2R8W),
  };
}

function deferred<T>() {
  let resolve: (value: T) => void = () => undefined;
  let reject: (reason?: unknown) => void = () => undefined;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

describe("DocumentsPage", () => {
  it("renders one card per document with a single metadata line", async () => {
    render(<DocumentsPage api={readOnlyClient()} />);

    expect(await screen.findByText("Data Retention Policy")).not.toBeNull();
    expect(screen.getByText(/6\.1 KB · .* · local corpus/)).not.toBeNull();
  });
  it("normalizes a backend-shaped HR category without changing the fixture", async () => {
    const hrDocument = populatedDocumentsResponse.documents.find(
      (document) => document.title === "Employee Onboarding Guide",
    );
    expect(hrDocument?.document_category).toBe("hr");

    render(<DocumentsPage api={readOnlyClient()} />);

    expect(await screen.findByText("Employee Onboarding Guide")).not.toBeNull();
    expect(screen.getByText("HR")).not.toBeNull();
  });

  it("renders the existing empty-corpus state", async () => {
    const api = readOnlyClient();
    api.getDocuments = vi.fn().mockResolvedValue({
      documents: [],
      document_count: 0,
      index: indexFixtures.compatible,
      config_error: null,
    });

    render(<DocumentsPage api={api} />);

    expect(await screen.findByText("No corpus documents found")).not.toBeNull();
    expect(screen.getByText(/Add Markdown source files/)).not.toBeNull();
    expect(screen.getByText("0 files")).not.toBeNull();
  });

  it("renders a documents request failure without leaving the skeleton", async () => {
    const api = readOnlyClient();
    api.getDocuments = vi.fn().mockRejectedValue(
      new ApiError("raw transport detail", {
        code: "backend_unreachable",
        networkError: true,
      }),
    );

    render(<DocumentsPage api={api} />);

    expect(await screen.findByText("Backend unreachable")).not.toBeNull();
    expect(screen.queryByTestId("documents-loading-skeleton")).toBeNull();
    expect(screen.queryByText("raw transport detail")).toBeNull();
  });

  it("shows a configuration notice while still rendering corpus data", async () => {
    const api = readOnlyClient();
    api.getDocuments = vi.fn().mockResolvedValue({
      ...populatedDocumentsResponse,
      index: null,
      config_error: "LLM_PROVIDER must be configured.",
    });

    render(<DocumentsPage api={api} />);

    const alert = await screen.findByRole("alert");
    expect(screen.getByText("Index status is unavailable")).not.toBeNull();
    expect(alert.textContent).toContain("LLM_PROVIDER must be configured.");
    expect(screen.queryByRole("heading", { name: "Embedding compatibility" })).toBeNull();
    expect(screen.getByText("Data Retention Policy")).not.toBeNull();
  });

  it("treats index null as unavailable without crashing the document list", async () => {
    const api = readOnlyClient();
    api.getDocuments = vi.fn().mockResolvedValue({
      ...populatedDocumentsResponse,
      index: null,
    });

    render(<DocumentsPage api={api} />);

    expect(await screen.findByText("Data Retention Policy")).not.toBeNull();
    expect(screen.queryByRole("heading", { name: "Embedding compatibility" })).toBeNull();
  });

  it.each([
    ["compatible", "Compatible", false],
    ["legacy_no_fingerprint", "Legacy fingerprint", false],
    ["provider_mismatch", "Provider mismatch", true],
    ["model_mismatch", "Model mismatch", true],
    ["missing_index", "Index missing", true],
    ["index_unreadable", "Index unreadable", false],
  ] as const)(
    "renders the %s compatibility branch as %s",
    async (compatibility, label, reindexRequired) => {
      const api = readOnlyClient();
      api.getDocuments = vi
        .fn()
        .mockResolvedValue(documentsResponseFor(indexFixtures[compatibility]));

      render(<DocumentsPage api={api} />);

      expect(await screen.findByText(label)).not.toBeNull();
      expect(Boolean(screen.queryByText("Reindex required"))).toBe(reindexRequired);

      if (compatibility === "index_unreadable") {
        expect(indexFixtures.index_unreadable.exists).toBeNull();
        expect(screen.getByText("Index could not be inspected")).not.toBeNull();
        expect(screen.getByText(/compatibility is unknown/)).not.toBeNull();
        expect(screen.queryByText(/uv run python ingestion.py/)).toBeNull();
      }
    },
  );
});

describe("DocumentsPage loading", () => {
  it("shows the heading, count footprint, and structural skeleton immediately", () => {
    const api = readOnlyClient();
    api.getDocuments = vi.fn(() => new Promise<DocumentsResponse>(() => undefined));

    render(<DocumentsPage api={api} />);

    expect(screen.getByText("Knowledge layer")).not.toBeNull();
    expect(screen.getByRole("heading", { name: "Documents and index health" })).not.toBeNull();
    expect(
      screen.getByText(
        "A read-only view of the local corpus and the embedding configuration used for retrieval.",
      ),
    ).not.toBeNull();
    expect(screen.getByTestId("document-count-placeholder")).not.toBeNull();
    const skeleton = screen.getByTestId("documents-loading-skeleton");
    expect(screen.getByRole("status")).toBe(skeleton);
    expect(skeleton.querySelector(".index-card")).not.toBeNull();
    expect(skeleton.querySelector(".documents-section")).not.toBeNull();
    expect(skeleton.querySelectorAll(".document-grid .document-card")).toHaveLength(6);
    expect(skeleton.hasAttribute("hidden")).toBe(false);
    expect(skeleton.getAttribute("aria-hidden")).toBeNull();
    expect(skeleton.style.display).not.toBe("none");
  });

  it("replaces the skeleton and completes the content transition after 120ms", async () => {
    vi.useFakeTimers();
    const api = readOnlyClient();
    let resolveDocuments: ((response: typeof populatedDocumentsResponse) => void) | undefined;
    api.getDocuments = vi.fn(
      () =>
        new Promise<DocumentsResponse>((resolve) => {
          resolveDocuments = resolve;
        }),
    );

    render(<DocumentsPage api={api} />);
    expect(screen.getByRole("status")).not.toBeNull();

    await act(async () => {
      resolveDocuments?.(populatedDocumentsResponse);
    });

    expect(screen.queryByTestId("documents-loading-skeleton")).toBeNull();
    expect(screen.getByText("Data Retention Policy")).not.toBeNull();
    const loadedContent = screen.getByTestId("documents-loaded-content");
    expect(loadedContent.getAttribute("data-transitioning")).toBe("true");
    expect(loadedContent.classList.contains("content-reveal")).toBe(true);

    act(() => {
      vi.advanceTimersByTime(CONTENT_REVEAL_DURATION_MS - 1);
    });
    expect(loadedContent.getAttribute("data-transitioning")).toBe("true");

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(loadedContent.getAttribute("data-transitioning")).toBe("false");
    expect(loadedContent.classList.contains("content-reveal")).toBe(false);
  });

  it("skips the content transition when reduced motion is requested", async () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockImplementation((query: string) => ({
        matches: query === "(prefers-reduced-motion: reduce)",
        media: query,
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    );

    render(<DocumentsPage api={readOnlyClient()} />);

    expect(await screen.findByText("Data Retention Policy")).not.toBeNull();
    expect(screen.getAllByText("OpenAI")).toHaveLength(2);
    const documentStat = document.querySelector<HTMLElement>(".documents-page .page-stat");
    expect(documentStat?.querySelector("strong")?.textContent).toBe(
      String(populatedDocumentsResponse.document_count),
    );
    expect(screen.getByText("DOCUMENTS INDEXED")).not.toBeNull();
    const loadedContent = screen.getByTestId("documents-loaded-content");
    expect(loadedContent.getAttribute("data-transitioning")).toBe("false");
    expect(loadedContent.classList.contains("content-reveal")).toBe(false);
  });

  it("cleans up an active content-transition timer on unmount", async () => {
    vi.useFakeTimers();
    const clearTimeout = vi.spyOn(window, "clearTimeout");

    const { unmount } = render(<DocumentsPage api={readOnlyClient()} />);
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByTestId("documents-loaded-content").getAttribute("data-transitioning")).toBe(
      "true",
    );

    unmount();

    expect(clearTimeout).toHaveBeenCalled();
  });
});

describe("RunsPage", () => {
  it("shows its heading and structured skeleton immediately", () => {
    const api = readOnlyClient();
    api.getRuns = vi.fn(() => new Promise<RunsResponse>(() => undefined));

    render(<RunsPage api={api} />);

    expect(screen.getByRole("heading", { name: "Recent agent runs" })).not.toBeNull();
    const skeleton = screen.getByTestId("runs-loading-skeleton");
    expect(screen.getByRole("status")).toBe(skeleton);
    expect(skeleton.querySelector(".runs-list-section")).not.toBeNull();
    expect(skeleton.querySelector(".run-detail")).not.toBeNull();
    expect(skeleton.hasAttribute("hidden")).toBe(false);
    expect(skeleton.getAttribute("aria-hidden")).toBeNull();
  });

  it("replaces the entry skeleton with loaded run history", async () => {
    vi.useFakeTimers();
    const api = readOnlyClient();
    let resolveRuns: ((response: RunsResponse) => void) | undefined;
    api.getRuns = vi.fn(
      () =>
        new Promise<RunsResponse>((resolve) => {
          resolveRuns = resolve;
        }),
    );

    render(<RunsPage api={api} />);
    expect(screen.getByRole("status")).not.toBeNull();

    await act(async () => {
      resolveRuns?.(populatedRunsResponse);
    });

    expect(screen.queryByTestId("runs-loading-skeleton")).toBeNull();
    expect(screen.getByText("Run history")).not.toBeNull();
    const loadedContent = screen.getByTestId("runs-loaded-content");
    expect(loadedContent.getAttribute("data-transitioning")).toBe("true");

    act(() => {
      vi.advanceTimersByTime(CONTENT_REVEAL_DURATION_MS);
    });
    expect(loadedContent.getAttribute("data-transitioning")).toBe("false");
  });

  it("formats run durations above one second in seconds", async () => {
    render(<RunsPage api={readOnlyClient()} />);

    // Both the history row and the auto-selected detail panel report the run.
    expect((await screen.findAllByText("2.79 s")).length).toBeGreaterThan(0);
    const retainedStat = document.querySelector<HTMLElement>(".runs-page .page-stat");
    expect(retainedStat?.querySelector("strong")?.textContent).toBe(
      String(populatedRunsResponse.count),
    );
    expect(screen.getByText(`OF ${populatedRunsResponse.limit} RETAINED`)).not.toBeNull();
  });

  it("uses canonical status and timing terminology without changing grammatical prose", async () => {
    render(<RunsPage api={readOnlyClient()} />);

    await waitFor(() => {
      expect(screen.getAllByText("COMPLETE").length).toBeGreaterThanOrEqual(2);
    });
    expect(screen.getByText("NEEDS REVIEW")).not.toBeNull();
    expect(screen.getByText("DEGRADED")).not.toBeNull();
    expect(screen.getByText("Agent trace")).not.toBeNull();
    expect(screen.getByRole("heading", { name: "Node timings" })).not.toBeNull();
    expect(
      screen.getByText(/evidence metadata for completed graph executions\./),
    ).not.toBeNull();
  });

  it("normalizes provider casing in run history and detail without changing fixtures", async () => {
    const api = readOnlyClient();
    api.getRuns = vi.fn().mockResolvedValue({
      ...populatedRunsResponse,
      runs: populatedRunsResponse.runs.map((run, index) => ({
        ...run,
        provider: ["openai", "OpenAI", "OPENAI"][index]!,
      })),
    });
    api.getRun = vi.fn().mockResolvedValue({
      ...runDetailFixtures.run_01HV7Q2R8W,
      provider: "Openai",
    });

    render(<RunsPage api={api} />);

    await waitFor(() => {
      expect(screen.getAllByText("OpenAI").length).toBeGreaterThanOrEqual(4);
    });
    expect(populatedRunsResponse.runs[0]?.provider).toBe("openai");
    expect(runDetailFixtures.run_01HV7Q2R8W.provider).toBe("openai");
  });

  it("preserves safe external-link behavior in run evidence", async () => {
    render(<RunsPage api={readOnlyClient()} />);

    const link = await screen.findByRole("link", {
      name: "Open Zero Trust Architecture in a new tab",
    });
    expect(link.getAttribute("href")).toBe(
      "https://www.nist.gov/publications/zero-trust-architecture",
    );
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toBe("noopener noreferrer");
  });

  it("explains that history is empty rather than showing a bare table", async () => {
    const api = readOnlyClient();
    api.getRuns = vi.fn().mockResolvedValue(emptyRunsResponse);
    render(<RunsPage api={api} />);

    expect(await screen.findByText("No recorded runs yet")).not.toBeNull();
  });

  it("renders a run-list request failure", async () => {
    const api = readOnlyClient();
    api.getRuns = vi.fn().mockRejectedValue(
      new ApiError("private detail", { status: 500, code: "internal_error" }),
    );

    render(<RunsPage api={api} />);

    expect(await screen.findByText("The run could not be completed")).not.toBeNull();
    expect(screen.queryByTestId("runs-loading-skeleton")).toBeNull();
    expect(screen.queryByText("private detail")).toBeNull();
  });

  it("shows the initial run-detail loading state", async () => {
    const api = readOnlyClient();
    api.getRun = vi.fn(() => new Promise<RunDetail>(() => undefined));

    render(<RunsPage api={api} />);

    expect(await screen.findByText("Run history")).not.toBeNull();
    expect(screen.getByText("Loading run detail…")).not.toBeNull();
    expect(screen.getByTestId("run-detail-loading-skeleton")).not.toBeNull();
    expect(document.querySelector(".run-detail-column")?.getAttribute("aria-busy")).toBe("true");
  });

  it.each([
    [new ApiError("failed", { status: 500, code: "internal_error" }), "The run could not be completed"],
    [
      new ApiError("missing", {
        status: 404,
        code: "run_not_found",
        payload: { error: "run_not_found" },
      }),
      "Run not found",
    ],
  ])("renders a focused run-detail error", async (detailError, heading) => {
    const api = readOnlyClient();
    api.getRun = vi.fn().mockRejectedValue(detailError);

    render(<RunsPage api={api} />);

    expect(await screen.findByText(heading)).not.toBeNull();
    const alert = screen.getByRole("alert");
    expect(alert.classList.contains("error-state--compact")).toBe(true);
    expect(alert.textContent).toContain(`HTTP ${detailError.status}`);
  });

  it("keeps the selected row and resolved detail aligned", async () => {
    const api = readOnlyClient();
    api.getRun = vi.fn((runId: string) => Promise.resolve(runDetailFixtures[runId]!));
    render(<RunsPage api={api} />);

    const firstButton = await screen.findByRole("button", {
      name: /What changed recently in remote-access security guidance\?/,
    });
    expect(firstButton.closest("tr")?.classList.contains("is-selected")).toBe(true);
    expect(
      screen.getByRole("heading", {
        name: "What changed recently in remote-access security guidance?",
      }),
    ).not.toBeNull();

    const secondButton = screen.getByRole("button", {
      name: /Summarize the current incident escalation process\./,
    });
    fireEvent.click(secondButton);

    await screen.findByRole("heading", {
      name: "Summarize the current incident escalation process.",
    });
    expect(secondButton.closest("tr")?.classList.contains("is-selected")).toBe(true);
    expect(firstButton.closest("tr")?.classList.contains("is-selected")).toBe(false);
  });

  it("ignores a stale detail error and stale loading completion", async () => {
    const first = deferred<RunDetail>();
    const second = deferred<RunDetail>();
    const api = readOnlyClient();
    api.getRun = vi.fn((runId: string) =>
      runId === "run_01HV7Q2R8W" ? first.promise : second.promise,
    );

    render(<RunsPage api={api} />);
    await waitFor(() => expect(api.getRun).toHaveBeenCalledWith("run_01HV7Q2R8W"));
    fireEvent.click(
      screen.getByRole("button", {
        name: /Summarize the current incident escalation process\./,
      }),
    );

    await act(async () => {
      second.resolve(runDetailFixtures.run_01HV7QGZ1M);
      await second.promise;
    });
    expect(document.querySelector(".run-detail-column")?.getAttribute("aria-busy")).toBe("false");

    await act(async () => {
      first.reject(new ApiError("stale", { status: 500, code: "internal_error" }));
      await first.promise.catch(() => undefined);
    });

    expect(screen.queryByRole("alert")).toBeNull();
    expect(document.querySelector(".run-detail-column")?.getAttribute("aria-busy")).toBe("false");
    expect(
      screen.getByRole("heading", {
        name: "Summarize the current incident escalation process.",
      }),
    ).not.toBeNull();
  });

  it("does not start detail work when a pending run list completes after unmount", async () => {
    const runs = deferred<RunsResponse>();
    const api = readOnlyClient();
    api.getRuns = vi.fn().mockReturnValue(runs.promise);
    const { unmount } = render(<RunsPage api={api} />);

    unmount();
    await act(async () => {
      runs.resolve(populatedRunsResponse);
      await runs.promise;
    });

    expect(api.getRun).not.toHaveBeenCalled();
  });

  it("ignores pending detail settlement after unmount", async () => {
    const detail = deferred<RunDetail>();
    const api = readOnlyClient();
    api.getRun = vi.fn().mockReturnValue(detail.promise);
    const { unmount } = render(<RunsPage api={api} />);
    await waitFor(() => expect(api.getRun).toHaveBeenCalledTimes(1));

    unmount();
    await act(async () => {
      detail.resolve(runDetailFixtures.run_01HV7Q2R8W);
      await detail.promise;
    });

    expect(document.querySelector(".runs-page")).toBeNull();
  });

  it("keeps the current detail mounted and does not scroll when selecting another run", async () => {
    const api = readOnlyClient();
    let resolveSelectedRun: ((detail: RunDetail) => void) | undefined;
    api.getRun = vi.fn((runId: string) => {
      if (runId === "run_01HV7Q2R8W") {
        return Promise.resolve(runDetailFixtures.run_01HV7Q2R8W);
      }

      return new Promise<RunDetail>((resolve) => {
        resolveSelectedRun = resolve;
      });
    });
    const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);

    render(<RunsPage api={api} />);

    const currentHeading = await screen.findByRole("heading", {
      name: "What changed recently in remote-access security guidance?",
    });
    fireEvent.click(
      screen.getByRole("button", {
        name: /Summarize the current incident escalation process\./,
      }),
    );

    expect(currentHeading.isConnected).toBe(true);
    expect(document.querySelector(".run-detail-column")?.getAttribute("aria-busy")).toBe("true");
    expect(scrollTo).not.toHaveBeenCalled();

    await act(async () => {
      resolveSelectedRun?.(runDetailFixtures.run_01HV7QGZ1M);
    });

    expect(
      await screen.findByRole("heading", {
        name: "Summarize the current incident escalation process.",
      }),
    ).not.toBeNull();
    expect(scrollTo).not.toHaveBeenCalled();
  });

  it("ignores an older run-detail response that resolves after the latest selection", async () => {
    const api = readOnlyClient();
    let resolveRunA: ((detail: RunDetail) => void) | undefined;
    let resolveRunB: ((detail: RunDetail) => void) | undefined;
    api.getRun = vi.fn(
      (runId: string) =>
        new Promise<RunDetail>((resolve) => {
          if (runId === "run_01HV7Q2R8W") {
            resolveRunA = resolve;
          } else if (runId === "run_01HV7QGZ1M") {
            resolveRunB = resolve;
          }
        }),
    );

    render(<RunsPage api={api} />);
    await waitFor(() => expect(api.getRun).toHaveBeenCalledWith("run_01HV7Q2R8W"));

    fireEvent.click(
      screen.getByRole("button", {
        name: /Summarize the current incident escalation process\./,
      }),
    );

    await act(async () => {
      resolveRunB?.(runDetailFixtures.run_01HV7QGZ1M);
    });
    expect(
      screen.getByRole("heading", {
        name: "Summarize the current incident escalation process.",
      }),
    ).not.toBeNull();

    await act(async () => {
      resolveRunA?.(runDetailFixtures.run_01HV7Q2R8W);
    });

    expect(
      screen.getByRole("heading", {
        name: "Summarize the current incident escalation process.",
      }),
    ).not.toBeNull();
    expect(
      screen.queryByRole("heading", {
        name: "What changed recently in remote-access security guidance?",
      }),
    ).toBeNull();
  });
});
