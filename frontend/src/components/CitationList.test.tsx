import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Citation } from "../api/types";
import { askFixtures } from "../mocks/fixtures";
import { CitationList } from "./CitationList";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function mockExcerptMeasurements({
  clientHeight,
  scrollHeight,
}: {
  clientHeight: number;
  scrollHeight: number;
}) {
  vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockImplementation(function (
    this: HTMLElement,
  ) {
    return this.classList.contains("citation-snippet") ? clientHeight : 0;
  });
  vi.spyOn(HTMLElement.prototype, "scrollHeight", "get").mockImplementation(function (
    this: HTMLElement,
  ) {
    return this.classList.contains("citation-snippet") ? scrollHeight : 0;
  });
}

function citationWithSnippet(title: string, snippet: string, source: string): Citation {
  return {
    ...askFixtures.localSuccess.citations[0]!,
    title,
    snippet,
    source,
  };
}

describe("CitationList", () => {
  it("uses the reference evidence labels", () => {
    render(<CitationList citations={askFixtures.localSuccess.citations} />);

    expect(screen.getByText("EVIDENCE USED")).not.toBeNull();
    expect(screen.getByRole("heading", { name: "Sources" })).not.toBeNull();
  });

  it("renders each source as an independent card in citation order", () => {
    const { container } = render(
      <CitationList citations={askFixtures.localSuccess.citations} />,
    );
    const cards = Array.from(container.querySelectorAll<HTMLElement>(".citation-card"));

    expect(cards).toHaveLength(2);
    expect(cards[0]?.querySelector(".citation-number")?.textContent).toBe("1");
    expect(cards[0]?.textContent).toContain("Expense Reimbursement Policy");
    expect(cards[1]?.querySelector(".citation-number")?.textContent).toBe("2");
    expect(cards[1]?.textContent).toContain("Employee Onboarding Guide");
  });

  it("keeps local source metadata available while presenting the short filename", () => {
    render(<CitationList citations={askFixtures.localSuccess.citations} />);

    expect(screen.getByText("Expense Reimbursement Policy")).not.toBeNull();
    expect(screen.getByText("Finance")).not.toBeNull();
    expect(screen.getByText("expense_reimbursement_policy.md")).not.toBeNull();
    expect(
      screen.getByText(
        "Full source path: data/acmecorp_internal_docs/expense_reimbursement_policy.md",
      ),
    ).not.toBeNull();
  });

  it("normalizes backend-shaped HR category values without sanitizing the fixture", () => {
    const mockCitation = askFixtures.localSuccess.citations.find(
      (citation) => citation.title === "Employee Onboarding Guide",
    )!;
    expect(mockCitation.document_category).toBe("hr");

    const variations = ["hr", "Hr", "HR", "  hr  "];
    const { rerender } = render(
      <CitationList citations={[{ ...mockCitation, document_category: variations[0]! }]} />,
    );

    for (const variation of variations) {
      rerender(
        <CitationList citations={[{ ...mockCitation, document_category: variation }]} />,
      );
      expect(screen.getByText("HR")).not.toBeNull();
    }
  });

  it("preserves web URLs and safe external-link behavior", () => {
    render(<CitationList citations={askFixtures.webSuccess.citations} />);

    expect(screen.getByText(/remote access requires an enrolled company device/i)).not.toBeNull();
    const link = screen.getByRole("link", {
      name: "Open Zero Trust Architecture in a new tab",
    });
    expect(link.getAttribute("href")).toBe(
      "https://www.nist.gov/publications/zero-trust-architecture",
    );
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toBe("noopener noreferrer");
    expect(screen.getByText("nist.gov")).not.toBeNull();
    expect(screen.getByText(/current remote access zero trust guidance/i)).not.toBeNull();
  });

  it("renders a citation with an unsafe URL as text, never as a clickable link", () => {
    const hostile: Citation = {
      kind: "web",
      title: "Zero Trust Architecture",
      source: null,
      url: "javascript:alert(1)",
      document_category: null,
      query: null,
      snippet: "Remote access requires an enrolled company device.",
    };

    const { container } = render(<CitationList citations={[hostile]} />);

    expect(screen.getByText("Zero Trust Architecture")).not.toBeNull();
    expect(screen.getByText(hostile.snippet!)).not.toBeNull();
    expect(screen.queryAllByRole("link")).toHaveLength(0);
    expect(container.querySelector(".citation-open-link")).toBeNull();
    expect(container.innerHTML).not.toContain("javascript:");
  });

  it("keeps long source metadata in safe wrapping and truncation elements", () => {
    const fullPath =
      "data/acmecorp_internal_docs/policies/finance/very_long_expense_reimbursement_and_approval_policy_filename.md";
    const longCitation: Citation = {
      kind: "local",
      title:
        "Expense Reimbursement and International Manager Approval Requirements for Extended Assignments",
      source: fullPath,
      url: null,
      document_category: "finance_operations_and_compliance",
      query: null,
      snippet:
        "Employees on extended assignments must retain itemized receipts and obtain all required approvals before reimbursement processing can begin.",
    };
    const { container } = render(<CitationList citations={[longCitation]} />);

    const title = container.querySelector<HTMLElement>(".citation-title");
    const filename = container.querySelector<HTMLElement>(".citation-filename");
    expect(title?.textContent).toBe(longCitation.title);
    expect(filename?.textContent).toBe(
      "very_long_expense_reimbursement_and_approval_policy_filename.md",
    );
    expect(filename?.getAttribute("title")).toBe(fullPath);
    expect(screen.getByText(`Full source path: ${fullPath}`)).not.toBeNull();
    expect(screen.getByText(longCitation.snippet ?? "")).not.toBeNull();
  });

  it("does not show a disclosure when the rendered excerpt is not truncated", () => {
    mockExcerptMeasurements({ clientHeight: 32, scrollHeight: 32 });
    const citation = citationWithSnippet(
      "Short policy",
      "A short excerpt that fits within two lines.",
      "data/acmecorp_internal_docs/short_policy.md",
    );

    render(<CitationList citations={[citation]} />);

    const excerpt = screen.getByText(citation.snippet ?? "");
    expect(excerpt.getAttribute("title")).toBe(citation.snippet);
    expect(screen.queryByText("Show more")).toBeNull();
  });

  it("expands and collapses a measured truncated excerpt accessibly", () => {
    mockExcerptMeasurements({ clientHeight: 32, scrollHeight: 80 });
    const citation = citationWithSnippet(
      "Extended policy",
      "This complete supporting excerpt is long enough to exceed the rendered two-line citation limit.",
      "data/acmecorp_internal_docs/extended_policy.md",
    );

    render(<CitationList citations={[citation]} />);

    const showMore = screen.getByRole("button", {
      name: `Show more of ${citation.title}`,
    });
    const excerptId = showMore.getAttribute("aria-controls");
    const excerpt = excerptId ? document.getElementById(excerptId) : null;

    expect(showMore.getAttribute("type")).toBe("button");
    expect(showMore.textContent).toBe("Show more");
    expect(showMore.getAttribute("aria-expanded")).toBe("false");
    expect(excerpt).not.toBeNull();
    expect(excerpt?.textContent).toBe(citation.snippet);
    expect(excerpt?.getAttribute("title")).toBe(citation.snippet);
    expect(excerpt?.classList.contains("citation-snippet--expanded")).toBe(false);

    fireEvent.click(showMore);

    const showLess = screen.getByRole("button", {
      name: `Show less of ${citation.title}`,
    });
    expect(showLess.getAttribute("aria-controls")).toBe(excerptId);
    expect(showLess.getAttribute("aria-expanded")).toBe("true");
    expect(showLess.textContent).toBe("Show less");
    expect(excerpt?.classList.contains("citation-snippet--expanded")).toBe(true);
    expect(excerpt?.textContent).toBe(citation.snippet);

    fireEvent.click(showLess);

    const collapsedButton = screen.getByRole("button", {
      name: `Show more of ${citation.title}`,
    });
    expect(collapsedButton.getAttribute("aria-expanded")).toBe("false");
    expect(excerpt?.classList.contains("citation-snippet--expanded")).toBe(false);
  });

  it("maintains independent expansion state for multiple truncated excerpts", () => {
    mockExcerptMeasurements({ clientHeight: 32, scrollHeight: 80 });
    const citations = [
      citationWithSnippet(
        "First policy",
        "The first complete supporting excerpt remains independent from every other citation.",
        "data/acmecorp_internal_docs/first_policy.md",
      ),
      citationWithSnippet(
        "Second policy",
        "The second complete supporting excerpt has its own disclosure and expansion state.",
        "data/acmecorp_internal_docs/second_policy.md",
      ),
    ];

    render(<CitationList citations={citations} />);

    const firstButton = screen.getByRole("button", {
      name: "Show more of First policy",
    });
    const secondButton = screen.getByRole("button", {
      name: "Show more of Second policy",
    });
    expect(firstButton.getAttribute("aria-controls")).not.toBe(
      secondButton.getAttribute("aria-controls"),
    );

    fireEvent.click(firstButton);

    expect(
      screen
        .getByRole("button", { name: "Show less of First policy" })
        .getAttribute("aria-expanded"),
    ).toBe("true");
    expect(secondButton.getAttribute("aria-expanded")).toBe("false");
  });
});
