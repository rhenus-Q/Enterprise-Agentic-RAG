import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../api/types";
import { askFixtures, indexFixtures, runtimeFixtures } from "../mocks/fixtures";
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

  it("covers loading, unavailable, and configuration-error states", () => {
    const { rerender } = render(<RuntimeBadge loading />);
    expect(screen.getByText("Checking runtime…")).not.toBeNull();
    expect(document.querySelector(".runtime-badge--loading")).not.toBeNull();

    rerender(<RuntimeBadge status={null} />);
    expect(screen.getByText("Runtime unavailable")).not.toBeNull();
    expect(document.querySelector(".runtime-badge--error")).not.toBeNull();

    rerender(<RuntimeBadge status={runtimeFixtures.configError} />);
    expect(screen.getByText("Configuration error")).not.toBeNull();
  });

  it.each([
    [runtimeFixtures.openai, "Model · Legacy", false],
    [
      { ...runtimeFixtures.openai, effective_model_profile: "luna_all" },
      "Model · Luna All",
      false,
    ],
    [
      { ...runtimeFixtures.openai, effective_model_profile: "flash_luna" },
      "Model · Flash + Luna",
      false,
    ],
    [runtimeFixtures.privacy, "Model · Legacy", true],
    [runtimeFixtures.local, "Model · Local", true],
  ] as const)("renders the resolved runtime label %s", (status, label, privateMode) => {
    render(<RuntimeBadge status={status} />);

    expect(screen.getByText(label)).not.toBeNull();
    expect(document.querySelector(".runtime-badge")?.classList.contains("runtime-badge--private")).toBe(
      privateMode,
    );
    if (status.web_search_locked) {
      expect(status.web_search_enabled_default).toBe(false);
    }
    cleanup();
  });

  it("renders runtime-result web availability and fallback-policy labels", () => {
    const { rerender } = render(<RuntimeBadge runtime={askFixtures.localSuccess.runtime} />);
    const badge = document.querySelector<HTMLElement>(".runtime-badge");
    expect(screen.getByText("Web available")).not.toBeNull();
    expect(badge?.title).toBe("Fallback policy: conservative");

    rerender(
      <RuntimeBadge
        runtime={{
          provider: "ollama",
          web_search_enabled: false,
          web_fallback_policy: "disabled",
        }}
      />,
    );
    expect(screen.getByText("Ollama")).not.toBeNull();
    expect(screen.getByText("Web off")).not.toBeNull();
    expect(badge?.title).toBe("Fallback policy: disabled");
  });
});

describe("ErrorState", () => {
  it.each([
    ["backend_unreachable", "Backend unreachable", "The app could not reach the API."],
    ["invalid_response", "Unexpected backend response", "The API returned a response"],
    ["request_timeout", "Request timed out", "The request took longer than expected."],
    ["request_failed", "Request unsuccessful", "The request could not be completed."],
    ["run_in_progress", "Question already in progress", "Another question is currently"],
    ["run_still_stopping", "Previous run still stopping", "previous run is still stopping"],
    ["preflight_failed", "Startup checks need attention", "startup checks did not complete"],
    ["config_error", "Runtime configuration error", "runtime configuration must be corrected"],
    ["internal_error", "The run could not be completed", "without exposing sensitive details"],
    ["run_not_found", "Run not found", "no longer available"],
  ])("renders stable %s copy", (code, title, detail) => {
    const error = new ApiError("C:\\private\\raw DO-NOT-LEAK", {
      status: code === "backend_unreachable" || code === "request_timeout" ? null : 500,
      code,
      networkError: code === "backend_unreachable",
    });

    render(<ErrorState error={error} />);

    const alert = screen.getByRole("alert");
    expect(screen.getByText(title)).not.toBeNull();
    expect(alert.textContent).toContain(detail);
    expect(alert.getAttribute("data-error-code")).toBe(code);
    expect(alert.getAttribute("data-tone")).toBe("danger");
    expect(alert.textContent).not.toContain("DO-NOT-LEAK");
    cleanup();
  });

  it("uses sanitized structured messages where the stable code allows them", () => {
    render(
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

    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("Another question is currently being processed.");
    expect(alert.textContent).toContain("HTTP 409");
  });

  it("supports compact warning rendering and a retry action without changing accessibility", () => {
    const action = vi.fn();
    render(
      <ErrorState
        error={new ApiError("busy", { status: 409, code: "run_in_progress" })}
        compact
        tone="warning"
        actionLabel="Retry"
        onAction={action}
      />,
    );

    const alert = screen.getByRole("alert");
    expect(alert.classList.contains("error-state--compact")).toBe(true);
    expect(alert.classList.contains("error-state--warning")).toBe(true);
    expect(alert.getAttribute("data-tone")).toBe("warning");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(action).toHaveBeenCalledTimes(1);
  });

  it("hides the retry action when no complete action contract is provided", () => {
    render(
      <ErrorState
        error={new ApiError("failed", { code: "request_failed" })}
        actionLabel="Retry"
      />,
    );

    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
  });
});
