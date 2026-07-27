import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "../api/types";
import {
  askFixtures,
  emptyRunsResponse,
  populatedDocumentsResponse,
  populatedRunsResponse,
  runDetailFixtures,
  runtimeFixtures,
} from "../mocks/fixtures";
import { DocumentsPage } from "./DocumentsPage";
import { RunsPage } from "./RunsPage";

afterEach(cleanup);

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

describe("RunsPage", () => {
  it("formats run durations above one second in seconds", async () => {
    render(<RunsPage api={readOnlyClient()} />);

    // Both the history row and the auto-selected detail panel report the run.
    expect((await screen.findAllByText("2.79 s")).length).toBeGreaterThan(0);
  });

  it("explains that history is empty rather than showing a bare table", async () => {
    const api = readOnlyClient();
    api.getRuns = vi.fn().mockResolvedValue(emptyRunsResponse);
    render(<RunsPage api={api} />);

    expect(await screen.findByText("No recorded runs yet")).not.toBeNull();
  });
});
