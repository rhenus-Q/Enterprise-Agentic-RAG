import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { Citation } from "../api/types";
import { askFixtures } from "../mocks/fixtures";
import { CitationList } from "./CitationList";

afterEach(cleanup);

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

  it("uses canonical HR mock data and normalizes any HR case variation", () => {
    const mockCitation = askFixtures.localSuccess.citations.find(
      (citation) => citation.title === "Employee Onboarding Guide",
    )!;
    expect(mockCitation.document_category).toBe("HR");

    const variations = ["hr", "Hr", "HR"];
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
      name: "Open Zero Trust Architecture in new tab",
    });
    expect(link.getAttribute("href")).toBe(
      "https://www.nist.gov/publications/zero-trust-architecture",
    );
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toBe("noopener noreferrer");
    expect(screen.getByText("nist.gov")).not.toBeNull();
    expect(screen.getByText(/current remote access zero trust guidance/i)).not.toBeNull();
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
});
