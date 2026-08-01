import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, type ApiClient, type RuntimeStatus } from "./api/types";
import {
  askFixtures,
  emptyRunsResponse,
  populatedDocumentsResponse,
  runDetailFixtures,
  runtimeFixtures,
} from "./mocks/fixtures";
import App from "./App";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function appClient(): ApiClient {
  return {
    ask: vi.fn().mockResolvedValue(askFixtures.localSuccess),
    cancelRun: vi.fn().mockResolvedValue({ cancelled: true, idle: true }),
    getStatus: vi.fn().mockResolvedValue(runtimeFixtures.openai),
    getDocuments: vi.fn().mockResolvedValue(populatedDocumentsResponse),
    getRuns: vi.fn().mockResolvedValue(emptyRunsResponse),
    getRun: vi.fn().mockResolvedValue(runDetailFixtures.run_01HV7Q2R8W),
  };
}

describe("Runtime status recovery", () => {
  it("retries a failed status request and restores the runtime state", async () => {
    let resolveRetry: ((status: RuntimeStatus) => void) | undefined;
    const retryPending = new Promise<RuntimeStatus>((resolve) => {
      resolveRetry = resolve;
    });
    const api = appClient();
    api.getStatus = vi
      .fn()
      .mockRejectedValueOnce(
        new ApiError("The backend could not be reached.", {
          code: "backend_unreachable",
          networkError: true,
        }),
      )
      .mockReturnValueOnce(retryPending);

    render(<App api={api} />);

    const retry = await screen.findByRole("button", { name: "Retry" });
    expect(screen.getByRole("alert")).not.toBeNull();
    fireEvent.click(retry);

    await waitFor(() => expect(api.getStatus).toHaveBeenCalledTimes(2));
    expect(screen.getByText("Checking runtime…")).not.toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();

    await act(async () => {
      resolveRetry?.(runtimeFixtures.openai);
      await retryPending;
    });

    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
    expect(screen.getByText(/Connected.*OpenAI/)).not.toBeNull();
  });
});

describe("App scrolling", () => {
  it("resets window scrolling immediately when top-level navigation changes", () => {
    const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);

    render(<App />);
    expect(scrollTo).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Documents" }));
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 0, left: 0, behavior: "auto" });

    scrollTo.mockClear();
    fireEvent.click(screen.getByRole("button", { name: "Runs" }));
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 0, left: 0, behavior: "auto" });

    scrollTo.mockClear();
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 0, left: 0, behavior: "auto" });
  });

  it("retains one non-scrolling app shell across top-level page changes", () => {
    vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
    render(<App />);

    const appShell = document.querySelector<HTMLElement>(".app-shell");
    expect(appShell).not.toBeNull();
    expect(appShell?.style.overflowY).toBe("");

    fireEvent.click(screen.getByRole("button", { name: "Documents" }));
    expect(document.querySelector(".app-shell")).toBe(appShell);
    expect(screen.getByRole("main").parentElement).toBe(appShell);

    fireEvent.click(screen.getByRole("button", { name: "Runs" }));
    expect(document.querySelector(".app-shell")).toBe(appShell);
    expect(screen.getByRole("main").parentElement).toBe(appShell);
  });
});

describe("Ask page persistence", () => {
  it("keeps the same Ask page mounted and hidden while another tab is active", () => {
    vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
    render(<App />);

    const askPage = document.querySelector<HTMLElement>(".ask-page");
    expect(askPage).not.toBeNull();
    expect(askPage!.hidden).toBe(false);

    // Hidden rather than unmounted, so an in-flight run keeps its state and
    // its answer still lands when the request finishes.
    fireEvent.click(screen.getByRole("button", { name: "Documents" }));
    expect(document.querySelector(".ask-page")).toBe(askPage);
    expect(askPage!.hidden).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(document.querySelector(".ask-page")).toBe(askPage);
    expect(askPage!.hidden).toBe(false);
  });
});
