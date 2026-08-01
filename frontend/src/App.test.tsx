import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  requestCancelledError,
  type ApiClient,
  type AskResponse,
  type RuntimeStatus,
} from "./api/types";
import {
  askFixtures,
  emptyRunsResponse,
  populatedDocumentsResponse,
  populatedRunsResponse,
  runDetailFixtures,
  runtimeFixtures,
} from "./mocks/fixtures";
import App from "./App";

beforeEach(() => {
  vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function appClient(): ApiClient {
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

function composerAskButton(): HTMLButtonElement {
  const button = document.querySelector<HTMLButtonElement>(".question-composer .primary-button");
  if (!button) {
    throw new Error("Expected the Ask composer action to be rendered.");
  }
  return button;
}

describe("App runtime status", () => {
  it("shows the initial runtime loading state and disables runtime-dependent controls", () => {
    const pending = deferred<RuntimeStatus>();
    const api = appClient();
    api.getStatus = vi.fn().mockReturnValue(pending.promise);

    render(<App api={api} />);

    expect(screen.getByText("Checking runtime…")).not.toBeNull();
    expect((screen.getByRole("checkbox", { name: "Web search" }) as HTMLInputElement).disabled).toBe(
      true,
    );
    expect(
      (screen.getByRole("combobox", { name: "Web fallback policy" }) as HTMLSelectElement).disabled,
    ).toBe(true);
    expect(api.getStatus).toHaveBeenCalledTimes(1);
  });

  it("resolves runtime status and restores runtime-dependent controls", async () => {
    const api = appClient();
    render(<App api={api} />);

    expect(await screen.findByText(/Connected · OpenAI/)).not.toBeNull();
    expect((screen.getByRole("checkbox", { name: "Web search" }) as HTMLInputElement).disabled).toBe(
      false,
    );
    expect(
      (screen.getByRole("combobox", { name: "Web fallback policy" }) as HTMLSelectElement).disabled,
    ).toBe(false);
  });

  it("renders a failed runtime-status request in the global notice", async () => {
    const api = appClient();
    api.getStatus = vi.fn().mockRejectedValue(
      new ApiError("private-host.internal", {
        code: "backend_unreachable",
        networkError: true,
      }),
    );

    render(<App api={api} />);

    const alert = await screen.findByRole("alert");
    expect(screen.getByText("Backend unreachable")).not.toBeNull();
    expect(alert.textContent).not.toContain("private-host.internal");
    expect(screen.getByText("Runtime unavailable")).not.toBeNull();
  });

  it("prevents duplicate Retry requests while pending and clears the error after success", async () => {
    const retry = deferred<RuntimeStatus>();
    const api = appClient();
    api.getStatus = vi
      .fn()
      .mockRejectedValueOnce(
        new ApiError("offline", {
          code: "backend_unreachable",
          networkError: true,
        }),
      )
      .mockReturnValueOnce(retry.promise);

    render(<App api={api} />);

    const retryButton = await screen.findByRole("button", { name: "Retry" });
    fireEvent.click(retryButton);
    fireEvent.click(retryButton);

    await waitFor(() => expect(api.getStatus).toHaveBeenCalledTimes(2));
    expect(screen.getByText("Checking runtime…")).not.toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
    expect((screen.getByRole("checkbox", { name: "Web search" }) as HTMLInputElement).disabled).toBe(
      true,
    );

    await act(async () => {
      retry.resolve(runtimeFixtures.openai);
      await retry.promise;
    });

    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
    expect(screen.getByText(/Connected · OpenAI/)).not.toBeNull();
    expect((screen.getByRole("checkbox", { name: "Web search" }) as HTMLInputElement).disabled).toBe(
      false,
    );
    expect(api.getStatus).toHaveBeenCalledTimes(2);
  });
});

describe("App dependency injection", () => {
  it("uses the same injected client for each active child page and run detail", async () => {
    const api = appClient();
    render(<App api={api} />);
    await screen.findByText(/Connected · OpenAI/);

    fireEvent.click(screen.getByRole("button", { name: "Documents" }));
    await waitFor(() => expect(api.getDocuments).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole("button", { name: "Runs" }));
    await waitFor(() => expect(api.getRuns).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(api.getRun).toHaveBeenCalledWith("run_01HV7Q2R8W"));

    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "Question" } });
    fireEvent.click(composerAskButton());
    await waitFor(() => expect(api.ask).toHaveBeenCalledTimes(1));
  });

  it("uses the injected client for cancellation", async () => {
    const api = appClient();
    api.ask = vi.fn(
      (_request, options) =>
        new Promise<AskResponse>((_resolve, reject) => {
          options?.signal?.addEventListener("abort", () => reject(requestCancelledError()), {
            once: true,
          });
        }),
    );

    render(<App api={api} />);
    await screen.findByText(/Connected · OpenAI/);
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "Question" } });
    fireEvent.click(composerAskButton());
    fireEvent.click(await screen.findByRole("button", { name: "Stop" }));

    await waitFor(() => expect(api.cancelRun).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(composerAskButton()).not.toBeNull());
  });

  it("never calls global fetch when an API client is injected", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<App api={appClient()} />);
    await screen.findByText(/Connected · OpenAI/);
    fireEvent.click(screen.getByRole("button", { name: "Documents" }));
    await screen.findByText("Data Retention Policy");

    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("App navigation and mount identity", () => {
  it("keeps tab navigation correct and scrolls only when the active page changes", async () => {
    const scrollTo = vi.mocked(window.scrollTo);
    render(<App api={appClient()} />);
    await screen.findByText(/Connected · OpenAI/);

    const navigation = screen.getByRole("navigation", { name: "Primary navigation" });
    const askTab = navigation.querySelector<HTMLButtonElement>("button:first-of-type")!;
    const documentsTab = screen.getByRole("button", { name: "Documents" });
    const runsTab = screen.getByRole("button", { name: "Runs" });
    expect(askTab.getAttribute("aria-current")).toBe("page");

    fireEvent.click(documentsTab);
    expect(documentsTab.getAttribute("aria-current")).toBe("page");
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 0, left: 0, behavior: "auto" });

    fireEvent.click(runsTab);
    expect(runsTab.getAttribute("aria-current")).toBe("page");
    fireEvent.click(askTab);
    expect(askTab.getAttribute("aria-current")).toBe("page");
  });

  it("retains the app shell and the same hidden Ask page across tab changes", async () => {
    render(<App api={appClient()} />);
    await screen.findByText(/Connected · OpenAI/);

    const appShell = document.querySelector<HTMLElement>(".app-shell");
    const askPage = document.querySelector<HTMLElement>(".ask-page");
    expect(appShell).not.toBeNull();
    expect(askPage?.hidden).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "Documents" }));
    expect(document.querySelector(".app-shell")).toBe(appShell);
    expect(document.querySelector(".ask-page")).toBe(askPage);
    expect(askPage?.hidden).toBe(true);

    fireEvent.click(
      screen
        .getByRole("navigation", { name: "Primary navigation" })
        .querySelector<HTMLButtonElement>("button:first-of-type")!,
    );
    expect(document.querySelector(".ask-page")).toBe(askPage);
    expect(askPage?.hidden).toBe(false);
  });

  it("keeps Ask unavailable while the global backend-unreachable banner is shown", async () => {
    const unreachable = new ApiError("raw transport detail", {
      code: "backend_unreachable",
      networkError: true,
    });
    const api = appClient();
    api.getStatus = vi.fn().mockRejectedValue(unreachable);
    api.ask = vi.fn().mockRejectedValue(unreachable);

    render(<App api={api} />);
    await screen.findByText("Backend unreachable");
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "Question" } });
    expect(composerAskButton().disabled).toBe(true);
    fireEvent.click(composerAskButton());

    expect(api.ask).not.toHaveBeenCalled();
    expect(screen.getAllByRole("alert")).toHaveLength(1);
  });
});
