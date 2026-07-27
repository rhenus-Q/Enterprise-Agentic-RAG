import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ApiError } from "../api/types";
import { indexFixtures } from "../mocks/fixtures";
import { ErrorState } from "./ErrorState";
import { IndexStatusCard } from "./IndexStatusCard";

afterEach(cleanup);

describe("IndexStatusCard", () => {
  it("shows the reindex command only when the backend says it is required", () => {
    const { rerender } = render(<IndexStatusCard index={indexFixtures.provider_mismatch} />);
    expect(screen.getByText("Reindex required")).not.toBeNull();

    rerender(<IndexStatusCard index={indexFixtures.compatible} />);
    expect(screen.queryByText("Reindex required")).toBeNull();
  });
});

describe("ErrorState", () => {
  it("renders a backend-unreachable state", () => {
    render(
      <ErrorState
        error={
          new ApiError("offline", {
            code: "backend_unreachable",
            networkError: true,
          })
        }
      />,
    );
    expect(screen.getByText("Backend unreachable")).not.toBeNull();
  });

  it("renders sanitized 503 and busy 409 responses", () => {
    const { rerender } = render(
      <ErrorState
        error={
          new ApiError("preflight", {
            status: 503,
            code: "preflight_failed",
            payload: { error: "preflight_failed", message: "Startup preflight failed." },
          })
        }
      />,
    );
    expect(screen.getByText("Startup checks need attention")).not.toBeNull();

    rerender(
      <ErrorState
        error={
          new ApiError("busy", {
            status: 409,
            code: "run_in_progress",
            payload: {
              error: "run_in_progress",
              message: "Another question is currently being processed.",
            },
          })
        }
      />,
    );
    expect(screen.getByText("Question already in progress")).not.toBeNull();
  });
});
