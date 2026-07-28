import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ApiError } from "../api/types";
import { askFixtures, indexFixtures } from "../mocks/fixtures";
import { ErrorState } from "./ErrorState";
import { IndexStatusCard } from "./IndexStatusCard";
import { RuntimeBadge } from "./RuntimeBadge";
import { StatusPill } from "./StatusPill";

afterEach(cleanup);

describe("IndexStatusCard", () => {
  it("uses the reference retrieval label and full-size dynamic identifiers", () => {
    const { container } = render(<IndexStatusCard index={indexFixtures.compatible} />);

    expect(screen.getByText("RETRIEVAL INDEX")).not.toBeNull();
    const identifiers = Array.from(
      container.querySelectorAll<HTMLElement>(".index-identifier"),
    );
    expect(identifiers).toHaveLength(2);
    expect(identifiers[0]?.textContent).toBe(indexFixtures.compatible.collection_name);
    expect(identifiers[1]?.textContent).toBe(indexFixtures.compatible.persist_directory);
  });

  it("shows the reindex command only when the backend says it is required", () => {
    const { rerender } = render(<IndexStatusCard index={indexFixtures.provider_mismatch} />);
    expect(screen.getByText("Reindex required")).not.toBeNull();

    rerender(<IndexStatusCard index={indexFixtures.compatible} />);
    expect(screen.queryByText("Reindex required")).toBeNull();
  });

  it("normalizes OpenAI provider casing without changing fingerprint data", () => {
    const index = {
      ...indexFixtures.compatible,
      expected_fingerprint: {
        ...indexFixtures.compatible.expected_fingerprint!,
        embedding_provider: "OPENAI",
      },
      stored_fingerprint: {
        ...indexFixtures.compatible.stored_fingerprint!,
        embedding_provider: "OpenAI",
      },
    };

    render(<IndexStatusCard index={index} />);

    expect(screen.getAllByText("OpenAI")).toHaveLength(2);
    expect(indexFixtures.compatible.expected_fingerprint?.embedding_provider).toBe("openai");
  });
});

describe("StatusPill", () => {
  it("uses the canonical success label when no override is supplied", () => {
    render(<StatusPill status="ok" />);
    expect(screen.getByText("COMPLETE")).not.toBeNull();
  });

  it("honors custom labels for successful and non-successful statuses", () => {
    const { rerender } = render(<StatusPill status="ok" label="Completed safely" />);
    expect(screen.getByText("Completed safely")).not.toBeNull();

    rerender(<StatusPill status="caveat" label="Manual review required" />);
    expect(screen.getByText("Manual review required")).not.toBeNull();

    rerender(<StatusPill status="error" label="Unavailable" />);
    expect(screen.getByText("Unavailable")).not.toBeNull();
  });

  it.each([
    ["ok", "", "COMPLETE"],
    ["caveat", "   ", "NEEDS REVIEW"],
    ["error", "\t", "DEGRADED"],
  ] as const)("uses the canonical %s fallback for a blank label", (status, label, fallback) => {
    render(<StatusPill status={status} label={label} />);
    expect(screen.getByText(fallback)).not.toBeNull();
    cleanup();
  });
});

describe("RuntimeBadge", () => {
  it.each(["openai", "OpenAI", "OPENAI"])("renders %s as OpenAI", (provider) => {
    render(
      <RuntimeBadge
        runtime={{
          ...askFixtures.localSuccess.runtime,
          provider,
        }}
      />,
    );

    expect(screen.getByText("OpenAI")).not.toBeNull();
    cleanup();
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
