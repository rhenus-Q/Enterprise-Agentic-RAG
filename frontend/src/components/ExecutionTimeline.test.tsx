import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { askFixtures } from "../mocks/fixtures";
import { ExecutionTimeline } from "./ExecutionTimeline";

afterEach(cleanup);

describe("ExecutionTimeline", () => {
  it("renders one timed row for every executed node", () => {
    const response = askFixtures.localSuccess;
    render(
      <ExecutionTimeline nodePath={response.node_path} timings={response.node_timings_ms} />,
    );

    expect(screen.getAllByRole("listitem")).toHaveLength(response.node_path.length);
    expect(screen.getByText("184.7 ms")).not.toBeNull();
  });

  it("keeps the shared eyebrow while allowing context-specific titles", () => {
    const response = askFixtures.localSuccess;
    const { rerender } = render(
      <ExecutionTimeline
        title="Execution timeline"
        nodePath={response.node_path}
        timings={response.node_timings_ms}
      />,
    );
    expect(screen.getByText("Agent trace")).not.toBeNull();
    expect(screen.getByRole("heading", { name: "Execution timeline" })).not.toBeNull();

    rerender(
      <ExecutionTimeline
        title="Node timings"
        nodePath={response.node_path}
        timings={response.node_timings_ms}
      />,
    );
    expect(screen.getByText("Agent trace")).not.toBeNull();
    expect(screen.getByRole("heading", { name: "Node timings" })).not.toBeNull();
  });
});
