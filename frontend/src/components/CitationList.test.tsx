import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { askFixtures } from "../mocks/fixtures";
import { CitationList } from "./CitationList";

afterEach(cleanup);

describe("CitationList", () => {
  it("renders local evidence, linked web evidence, and the web-query fallback", () => {
    render(<CitationList citations={askFixtures.webSuccess.citations} />);

    expect(screen.getByText(/remote access requires an enrolled company device/i)).not.toBeNull();
    expect(
      screen.getByRole("link", { name: "Zero Trust Architecture" }).getAttribute("href"),
    ).toBe("https://www.nist.gov/publications/zero-trust-architecture");
    expect(screen.getByText(/current remote access zero trust guidance/i)).not.toBeNull();
  });
});
