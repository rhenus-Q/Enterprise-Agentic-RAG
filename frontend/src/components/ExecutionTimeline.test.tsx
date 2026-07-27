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
});
