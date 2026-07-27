import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { askFixtures } from "../mocks/fixtures";
import { AnswerCard } from "./AnswerCard";

afterEach(cleanup);

describe("AnswerCard", () => {
  it("shows a caveat for caveat and error outcomes", () => {
    const { rerender } = render(<AnswerCard response={askFixtures.budgetExhausted} />);
    expect(screen.getByText("Answer caveat")).not.toBeNull();

    rerender(<AnswerCard response={askFixtures.generationError} />);
    expect(screen.getByText(/language model call failed/i)).not.toBeNull();
  });

  it("hides the caveat area for a successful answer", () => {
    render(<AnswerCard response={askFixtures.localSuccess} />);
    expect(screen.queryByText("Answer caveat")).toBeNull();
  });

  it("shows the input-redaction notice", () => {
    render(<AnswerCard response={askFixtures.redacted} />);
    expect(screen.getByText(/redacted before this question entered/i)).not.toBeNull();
  });
});
