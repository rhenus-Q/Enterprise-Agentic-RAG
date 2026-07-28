import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { formatDuration } from "../lib/format";
import { askFixtures } from "../mocks/fixtures";
import { AnswerCard } from "./AnswerCard";

afterEach(cleanup);

describe("AnswerCard", () => {
  it("shows a caveat for caveat and error outcomes", () => {
    const { rerender } = render(<AnswerCard response={askFixtures.budgetExhausted} />);
    expect(screen.getByText("Answer caveat")).not.toBeNull();
    expect(screen.getByText("NEEDS REVIEW")).not.toBeNull();

    rerender(<AnswerCard response={askFixtures.generationError} />);
    expect(screen.getByText(/language model call failed/i)).not.toBeNull();
    expect(screen.getByText("DEGRADED")).not.toBeNull();
  });

  it("hides the caveat area for a successful answer", () => {
    render(<AnswerCard response={askFixtures.localSuccess} />);
    expect(screen.queryByText("Answer caveat")).toBeNull();
    expect(screen.getByText("COMPLETE")).not.toBeNull();
  });

  it("shows the input-redaction notice", () => {
    render(<AnswerCard response={askFixtures.redacted} />);
    expect(screen.getByText(/redacted before this question entered/i)).not.toBeNull();
  });

  it("shows OpenAI and the run ID together with total time aligned last", () => {
    const response = askFixtures.localSuccess;
    const { container } = render(<AnswerCard response={response} />);

    expect(screen.getByText("OpenAI")).not.toBeNull();
    expect(screen.getByText(`Run ID: ${response.run_id}`)).not.toBeNull();
    expect(
      screen.getByText(`Total time: ${formatDuration(response.total_duration_ms)}`),
    ).not.toBeNull();
    expect(screen.getByLabelText(`Run ID: ${response.run_id}`)).not.toBeNull();
    expect(
      screen.getByLabelText(`Total time: ${formatDuration(response.total_duration_ms)}`),
    ).not.toBeNull();

    const footerItems = container.querySelector(".answer-footer")?.children;
    expect(footerItems?.[0]?.textContent).toContain("OpenAI");
    expect(footerItems?.[1]?.textContent).toBe(`Run ID: ${response.run_id}`);
    expect(footerItems?.[2]?.textContent).toBe(
      `Total time: ${formatDuration(response.total_duration_ms)}`,
    );
  });

  it("uses the knowledge answer section label", () => {
    render(<AnswerCard response={askFixtures.localSuccess} />);
    expect(screen.getByText("KNOWLEDGE ANSWER")).not.toBeNull();
  });

  it("renders generated answer text dynamically", () => {
    const answer = "A dynamically generated answer from the current response.";
    render(<AnswerCard response={{ ...askFixtures.localSuccess, answer }} />);

    expect(screen.getByText(answer)).not.toBeNull();
  });

  it("preserves complete long-answer content without truncation", () => {
    const answer = Array.from(
      { length: 24 },
      (_, index) => `Detailed answer segment ${index + 1} remains available to the reader.`,
    ).join(" ");
    const { container } = render(
      <AnswerCard response={{ ...askFixtures.localSuccess, answer }} />,
    );

    const answerCopy = container.querySelector(".answer-copy");
    expect(answerCopy?.textContent).toBe(answer);
    expect(answerCopy?.querySelector("[hidden]")).toBeNull();
    expect(answerCopy?.classList.contains("truncate-text")).toBe(false);
  });
});
