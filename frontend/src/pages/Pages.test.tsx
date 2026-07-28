import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient, DocumentsResponse, RunDetail, RunsResponse } from "../api/types";
import {
  askFixtures,
  emptyRunsResponse,
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
    getStatus: vi.fn().mockResolvedValue(runtimeFixtures.openai),
    getDocuments: vi.fn().mockResolvedValue(populatedDocumentsResponse),
    getRuns: vi.fn().mockResolvedValue(populatedRunsResponse),
    getRun: vi.fn().mockResolvedValue(runDetailFixtures.run_01HV7Q2R8W),
  };
}

describe("DocumentsPage", () => {
  it("renders one card per document with a single metadata line", async () => {
    render(<DocumentsPage api={readOnlyClient()} />);

    expect(await screen.findByText("Data Retention Policy")).not.toBeNull();
    expect(screen.getByText(/6\.1 KB · .* · local corpus/)).not.toBeNull();
  });
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

  it("explains that history is empty rather than showing a bare table", async () => {
    const api = readOnlyClient();
    api.getRuns = vi.fn().mockResolvedValue(emptyRunsResponse);
    render(<RunsPage api={api} />);

    expect(await screen.findByText("No recorded runs yet")).not.toBeNull();
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
});
