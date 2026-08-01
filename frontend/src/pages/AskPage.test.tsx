import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  isRequestCancelled,
  requestCancelledError,
  type ApiClient,
  type AskOptions,
  type AskRequest,
  type AskResponse,
  type CancelRunResponse,
} from "../api/types";
import {
  askFixtures,
  emptyRunsResponse,
  populatedDocumentsResponse,
  runDetailFixtures,
  runtimeFixtures,
} from "../mocks/fixtures";
import { AskPage } from "./AskPage";

afterEach(cleanup);

function clientWithAsk(
  ask: (request: AskRequest, options?: AskOptions) => Promise<AskResponse>,
): ApiClient {
  return {
    ask,
    cancelRun: vi.fn().mockResolvedValue({ cancelled: true, idle: true }),
    getStatus: vi.fn().mockResolvedValue(runtimeFixtures.openai),
    getDocuments: vi.fn().mockResolvedValue(populatedDocumentsResponse),
    getRuns: vi.fn().mockResolvedValue(emptyRunsResponse),
    getRun: vi.fn().mockResolvedValue(runDetailFixtures.run_01HV7Q2R8W),
  };
}

function enterQuestion() {
  fireEvent.change(screen.getByLabelText("Question"), {
    target: { value: "What is the expense policy?" },
  });
}

function askButton(): HTMLButtonElement {
  return screen.getByRole("button", { name: "Ask" }) as HTMLButtonElement;
}

function suggestionGrid(): HTMLDivElement {
  const grid = document.getElementById("suggestion-card-grid");
  if (!(grid instanceof HTMLDivElement)) {
    throw new Error("Expected the suggestion grid to be rendered.");
  }
  return grid;
}

describe("AskPage", () => {
  it("locks web options and submits no fallback override when runtime policy locks them", async () => {
    const ask = vi.fn().mockResolvedValue(askFixtures.localSuccess);

    render(<AskPage api={clientWithAsk(ask)} status={runtimeFixtures.local} />);

    const webSearch = screen.getByRole("checkbox", {
      name: "Web search",
    }) as HTMLInputElement;
    const fallbackPolicy = screen.getByRole("combobox", {
      name: "Web fallback policy",
    }) as HTMLSelectElement;

    expect(webSearch.disabled).toBe(true);
    expect(fallbackPolicy.disabled).toBe(true);
    expect(fallbackPolicy.value).toBe("runtime_locked");
    expect(fallbackPolicy.selectedOptions[0]?.textContent).toBe("Not applicable");

    enterQuestion();
    fireEvent.click(askButton());

    await waitFor(() => expect(ask).toHaveBeenCalledTimes(1));
    expect(ask.mock.calls[0]?.[0]).toMatchObject({
      web_search_enabled: false,
      web_fallback_policy: null,
    });
  });

  it("keeps the configured fallback policy selectable when runtime policy is unlocked", () => {
    render(<AskPage api={clientWithAsk(vi.fn())} status={runtimeFixtures.openai} />);

    const fallbackPolicy = screen.getByRole("combobox", {
      name: "Web fallback policy",
    }) as HTMLSelectElement;

    expect(fallbackPolicy.disabled).toBe(false);
    expect(fallbackPolicy.value).toBe("conservative");
    expect(fallbackPolicy.selectedOptions[0]?.textContent).toBe("Conservative");
  });

  it("disables the Ask button for a blank question", () => {
    render(<AskPage api={clientWithAsk(vi.fn())} status={runtimeFixtures.openai} />);
    expect(askButton().disabled).toBe(true);
  });

  it("disables the Ask button for a whitespace-only question", () => {
    render(<AskPage api={clientWithAsk(vi.fn())} status={runtimeFixtures.openai} />);
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "   \n  " } });
    expect(askButton().disabled).toBe(true);
  });

  it("enables the Ask button for a valid question", () => {
    render(<AskPage api={clientWithAsk(vi.fn())} status={runtimeFixtures.openai} />);
    enterQuestion();
    expect(askButton().disabled).toBe(false);
  });

  it("keeps the disclosure active while the composer is empty", () => {
    render(<AskPage api={clientWithAsk(vi.fn())} status={runtimeFixtures.openai} />);
    expect(suggestionGrid().hidden).toBe(false);
    expect(document.querySelectorAll(".suggestion-card")).toHaveLength(4);

    const disclosure = screen.getByRole("button", { name: /Suggested questions/ });
    fireEvent.click(disclosure);
    expect(suggestionGrid().hidden).toBe(true);
    expect(disclosure.getAttribute("aria-expanded")).toBe("false");

    fireEvent.click(disclosure);
    expect(suggestionGrid().hidden).toBe(false);
    expect(disclosure.getAttribute("aria-expanded")).toBe("true");
  });

  it("keeps the suggestion cards expanded while text exists without an answer", () => {
    render(<AskPage api={clientWithAsk(vi.fn())} status={runtimeFixtures.openai} />);
    enterQuestion();

    expect(suggestionGrid().hidden).toBe(false);
    expect(
      screen.getByRole("button", { name: /Suggested questions/ }).getAttribute("aria-expanded"),
    ).toBe("true");
  });

  it("lets the disclosure row expand and collapse suggestions while text remains", () => {
    render(<AskPage api={clientWithAsk(vi.fn())} status={runtimeFixtures.openai} />);
    enterQuestion();
    const disclosure = screen.getByRole("button", { name: /Suggested questions/ });

    fireEvent.click(disclosure);
    expect(suggestionGrid().hidden).toBe(true);
    expect(disclosure.getAttribute("aria-expanded")).toBe("false");

    fireEvent.click(disclosure);
    expect(suggestionGrid().hidden).toBe(false);
    expect(disclosure.getAttribute("aria-expanded")).toBe("true");
  });

  it("fills the composer from a suggested question and keeps the cards expanded", () => {
    render(<AskPage api={clientWithAsk(vi.fn())} status={runtimeFixtures.openai} />);
    fireEvent.click(screen.getByRole("button", { name: "How do I request VPN access?" }));

    expect((screen.getByLabelText("Question") as HTMLTextAreaElement).value).toBe(
      "How do I request VPN access?",
    );
    expect(suggestionGrid().hidden).toBe(false);
  });

  it("expands the suggestion cards again when the composer is cleared", () => {
    render(<AskPage api={clientWithAsk(vi.fn())} status={runtimeFixtures.openai} />);
    enterQuestion();
    fireEvent.click(screen.getByRole("button", { name: /Suggested questions/ }));
    expect(suggestionGrid().hidden).toBe(true);

    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "" } });
    expect(suggestionGrid().hidden).toBe(false);
  });

  it("swaps the Ask button for an active Stop control during submission", async () => {
    let resolveRequest: ((response: AskResponse) => void) | undefined;
    const pending = new Promise<AskResponse>((resolve) => {
      resolveRequest = resolve;
    });
    render(
      <AskPage
        api={clientWithAsk(() => pending)}
        status={runtimeFixtures.openai}
      />,
    );
    enterQuestion();
    fireEvent.click(askButton());

    await waitFor(() => {
      expect((screen.getByLabelText("Question") as HTMLTextAreaElement).disabled).toBe(true);
      // One control only: Ask is replaced by Stop rather than joined by it.
      const stopButton = screen.getByRole("button", { name: "Stop" });
      expect((stopButton as HTMLButtonElement).disabled).toBe(false);
      expect(stopButton.getAttribute("aria-busy")).toBe("true");
      expect(screen.queryByRole("button", { name: "Ask" })).toBeNull();
      expect(
        (screen.getByRole("button", {
          name: /Suggested questions/,
        }) as HTMLButtonElement).disabled,
      ).toBe(false);
      expect(suggestionGrid().hidden).toBe(false);
    });

    await act(async () => {
      resolveRequest?.(askFixtures.localSuccess);
      await pending;
    });

    expect(suggestionGrid().hidden).toBe(true);
    expect(
      screen.getByRole("button", { name: /Suggested questions/ }).getAttribute("aria-expanded"),
    ).toBe("false");

    expect(screen.getByText("Agent trace")).not.toBeNull();
    expect(screen.getByRole("heading", { name: "Execution timeline" })).not.toBeNull();
    expect(screen.getByText("EVIDENCE USED")).not.toBeNull();
    expect(screen.getByRole("heading", { name: "Sources" })).not.toBeNull();
    expect(screen.getByText("COMPLETE")).not.toBeNull();
    expect(screen.getByText("RESOLVED RUN")).not.toBeNull();

    const counterCard = document.querySelector<HTMLElement>(".run-summary-card");
    expect(counterCard).not.toBeNull();
    expect(within(counterCard!).getByText("Web available")).not.toBeNull();
    expect(within(counterCard!).queryByText("OpenAI")).toBeNull();
  });

  it("shows Web off in the counters badge when web search is unavailable", async () => {
    const response: AskResponse = {
      ...askFixtures.localSuccess,
      runtime: {
        ...askFixtures.localSuccess.runtime,
        web_search_enabled: false,
      },
    };
    render(
      <AskPage
        api={clientWithAsk(() => Promise.resolve(response))}
        status={runtimeFixtures.openai}
      />,
    );
    enterQuestion();
    fireEvent.click(askButton());

    await waitFor(() => {
      const counterCard = document.querySelector<HTMLElement>(".run-summary-card");
      expect(counterCard).not.toBeNull();
      expect(within(counterCard!).getByText("Web off")).not.toBeNull();
    });
  });

  it("asks the server to cancel and reopens the composer only once it confirms", async () => {
    let confirmCancel: (() => void) | undefined;
    const cancelPending = new Promise<CancelRunResponse>((resolve) => {
      confirmCancel = () => resolve({ cancelled: true, idle: true });
    });
    const ask = vi.fn(
      (_request: AskRequest, options?: AskOptions) =>
        new Promise<AskResponse>((_resolve, rejectRequest) => {
          options?.signal?.addEventListener("abort", () => rejectRequest(requestCancelledError()));
        }),
    );
    const api = clientWithAsk(ask);
    api.cancelRun = vi.fn().mockReturnValue(cancelPending);

    render(<AskPage api={api} status={runtimeFixtures.openai} />);
    enterQuestion();
    fireEvent.click(askButton());

    fireEvent.click(await screen.findByRole("button", { name: "Stop" }));

    // Reopening before the backend confirms is what produced a 409 on the
    // next question, so the composer stays shut until then.
    const stoppingButton = await screen.findByRole("button", { name: "Stopping…" });
    expect((stoppingButton as HTMLButtonElement).disabled).toBe(true);
    expect(api.cancelRun).toHaveBeenCalledTimes(1);

    await act(async () => {
      confirmCancel?.();
      await cancelPending;
    });

    await waitFor(() => {
      expect(askButton().disabled).toBe(false);
      expect((screen.getByLabelText("Question") as HTMLTextAreaElement).disabled).toBe(false);
    });
    expect(screen.queryByRole("button", { name: "Stop" })).toBeNull();
    // A stop is the user's choice, not a backend failure.
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("keeps submission locked when cancellation is accepted but the backend is not idle", async () => {
    const ask = vi.fn(
      (_request: AskRequest, options?: AskOptions) =>
        new Promise<AskResponse>((_resolve, rejectRequest) => {
          options?.signal?.addEventListener("abort", () => rejectRequest(requestCancelledError()));
        }),
    );
    const api = clientWithAsk(ask);
    api.cancelRun = vi
      .fn()
      .mockResolvedValueOnce({ cancelled: true, idle: false })
      .mockResolvedValueOnce({ cancelled: false, idle: true });

    render(<AskPage api={api} status={runtimeFixtures.openai} />);
    enterQuestion();
    fireEvent.click(askButton());
    fireEvent.click(await screen.findByRole("button", { name: "Stop" }));

    const checkAgain = await screen.findByRole("button", { name: "Check again" });
    expect((screen.getByLabelText("Question") as HTMLTextAreaElement).disabled).toBe(true);
    expect(screen.queryByRole("button", { name: "Ask" })).toBeNull();
    expect(
      within(screen.getByRole("alert")).getByText(
        "The previous run is still stopping. Please try again shortly.",
      ),
    ).not.toBeNull();

    fireEvent.click(checkAgain);

    await waitFor(() => {
      expect(api.cancelRun).toHaveBeenCalledTimes(2);
      expect(askButton().disabled).toBe(false);
      expect((screen.getByLabelText("Question") as HTMLTextAreaElement).disabled).toBe(false);
    });
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("counts both the local abort and the backend's 499 as cancellations", () => {
    expect(isRequestCancelled(requestCancelledError())).toBe(true);
    expect(isRequestCancelled(new ApiError("stopped", { code: "run_cancelled" }))).toBe(true);
    expect(isRequestCancelled(new ApiError("boom", { code: "internal_error" }))).toBe(false);
  });

  it("treats the backend's 499 for a stopped run as a cancellation, not a failure", async () => {
    let failRequest: (() => void) | undefined;
    const ask = vi.fn(
      () =>
        new Promise<AskResponse>((_resolve, rejectRequest) => {
          failRequest = () =>
            rejectRequest(
              new ApiError("The request was not successful.", {
                status: 499,
                code: "run_cancelled",
                payload: { error: "run_cancelled" },
              }),
            );
        }),
    );
    let confirmCancel: (() => void) | undefined;
    const cancelPending = new Promise<CancelRunResponse>((resolve) => {
      confirmCancel = () => resolve({ cancelled: true, idle: true });
    });
    const api = clientWithAsk(ask);
    api.cancelRun = vi.fn().mockReturnValue(cancelPending);

    render(<AskPage api={api} status={runtimeFixtures.openai} />);
    enterQuestion();
    fireEvent.click(askButton());
    fireEvent.click(await screen.findByRole("button", { name: "Stop" }));

    // The backend answers the abandoned request as it frees the slot, which
    // lands before the cancel call resolves.
    await act(async () => {
      failRequest?.();
      confirmCancel?.();
      await cancelPending;
    });

    await waitFor(() => expect(askButton().disabled).toBe(false));
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("discards an answer that arrives after the run was stopped", async () => {
    let resolveRequest: ((response: AskResponse) => void) | undefined;
    const pending = new Promise<AskResponse>((resolve) => {
      resolveRequest = resolve;
    });
    const api = clientWithAsk(() => pending);

    render(<AskPage api={api} status={runtimeFixtures.openai} />);
    enterQuestion();
    fireEvent.click(askButton());
    fireEvent.click(await screen.findByRole("button", { name: "Stop" }));

    await act(async () => {
      resolveRequest?.(askFixtures.localSuccess);
      await pending;
    });

    // Stop means stop: a result that wins the race is not shown.
    await waitFor(() => expect(askButton().disabled).toBe(false));
    expect(screen.queryByRole("heading", { name: "Execution timeline" })).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("preserves an in-flight run while the page is hidden", async () => {
    let resolveRequest: ((response: AskResponse) => void) | undefined;
    const pending = new Promise<AskResponse>((resolve) => {
      resolveRequest = resolve;
    });
    const props = {
      api: clientWithAsk(() => pending),
      status: runtimeFixtures.openai,
    };

    const { rerender } = render(<AskPage {...props} hidden={false} />);
    enterQuestion();
    fireEvent.click(askButton());
    await screen.findByRole("button", { name: "Stop" });

    // Navigating away and back must not restart or discard the run.
    rerender(<AskPage {...props} hidden />);
    rerender(<AskPage {...props} hidden={false} />);
    expect(screen.getByRole("button", { name: "Stop" })).not.toBeNull();

    await act(async () => {
      resolveRequest?.(askFixtures.localSuccess);
      await pending;
    });

    expect(screen.getByRole("heading", { name: "Execution timeline" })).not.toBeNull();
  });

  it("shows the busy message returned by a 409 response", async () => {
    const api = clientWithAsk(() =>
      Promise.reject(
        new ApiError("busy", {
          status: 409,
          code: "run_in_progress",
          payload: {
            error: "run_in_progress",
            message: "Another question is currently being processed.",
          },
        }),
      ),
    );
    render(<AskPage api={api} status={runtimeFixtures.openai} />);
    enterQuestion();
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("Another question is currently being processed.")).not.toBeNull();
    // A busy server is not a failure, and the message belongs beside the
    // composer rather than at the foot of the page, below the suggestions.
    expect(alert.getAttribute("data-tone")).toBe("warning");
    expect(document.querySelector(".ask-stage .ask-error")).not.toBeNull();
    expect(suggestionGrid().hidden).toBe(false);
  });

  it("uses the danger tone for a failure the user cannot retry away", async () => {
    const api = clientWithAsk(() =>
      Promise.reject(
        new ApiError("boom", {
          status: 500,
          code: "internal_error",
          payload: { error: "internal_error", exception_type: "RuntimeError" },
        }),
      ),
    );
    render(<AskPage api={api} status={runtimeFixtures.openai} />);
    enterQuestion();
    fireEvent.click(askButton());

    expect((await screen.findByRole("alert")).getAttribute("data-tone")).toBe("danger");
  });

  it("stays quiet about an unreachable backend the app banner already reports", async () => {
    const api = clientWithAsk(() =>
      Promise.reject(
        new ApiError("The backend could not be reached.", {
          code: "backend_unreachable",
          networkError: true,
        }),
      ),
    );
    render(<AskPage api={api} status={runtimeFixtures.openai} globalNoticeVisible />);
    enterQuestion();
    fireEvent.click(askButton());

    await waitFor(() => expect(askButton().disabled).toBe(false));
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("clears the previous error once the question is edited", async () => {
    const api = clientWithAsk(() =>
      Promise.reject(new ApiError("boom", { status: 500, code: "internal_error" })),
    );
    render(<AskPage api={api} status={runtimeFixtures.openai} />);
    enterQuestion();
    fireEvent.click(askButton());
    expect(await screen.findByRole("alert")).not.toBeNull();

    fireEvent.change(screen.getByLabelText("Question"), {
      target: { value: "a different question" },
    });
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
