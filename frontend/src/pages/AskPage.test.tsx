import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  type ApiClient,
  type AskRequest,
  type AskResponse,
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

function clientWithAsk(ask: (request: AskRequest) => Promise<AskResponse>): ApiClient {
  return {
    ask,
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
  it("disables the web-search override when runtime policy locks it", () => {
    render(<AskPage api={clientWithAsk(vi.fn())} status={runtimeFixtures.privacy} />);
    expect((screen.getByRole("checkbox", { name: "Web search" }) as HTMLInputElement).disabled).toBe(
      true,
    );
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

  it("disables the Ask button and preserves its accessible loading state during submission", async () => {
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
      const runningButton = screen.getByRole("button", { name: "Running" });
      expect((runningButton as HTMLButtonElement).disabled).toBe(true);
      expect(runningButton.getAttribute("aria-busy")).toBe("true");
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

    expect(await screen.findByText("Another question is currently being processed.")).not.toBeNull();
    expect(suggestionGrid().hidden).toBe(false);
  });
});
