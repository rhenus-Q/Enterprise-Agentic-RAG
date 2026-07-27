import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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

describe("AskPage", () => {
  it("disables the web-search override when runtime policy locks it", () => {
    render(<AskPage api={clientWithAsk(vi.fn())} status={runtimeFixtures.privacy} />);
    expect((screen.getByRole("checkbox", { name: "Web search" }) as HTMLInputElement).disabled).toBe(
      true,
    );
  });

  it("disables question input while a run is in flight", async () => {
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
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    await waitFor(() => {
      expect((screen.getByLabelText("Question") as HTMLTextAreaElement).disabled).toBe(true);
    });

    await act(async () => {
      resolveRequest?.(askFixtures.localSuccess);
      await pending;
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
  });
});
