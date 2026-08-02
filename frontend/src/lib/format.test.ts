import { describe, expect, it } from "vitest";

import { formatCategoryName, formatProviderName, safeExternalUrl } from "./format";

describe("formatCategoryName", () => {
  it.each([
    ["it_security", "IT Security"],
    ["IT_SECURITY", "IT Security"],
    ["finance", "Finance"],
    ["operations", "Operations"],
    ["compliance", "Compliance"],
    ["hr", "HR"],
    ["Hr", "HR"],
    ["HR", "HR"],
    ["  hr  ", "HR"],
  ])("renders %j as %s", (category, expected) => {
    expect(formatCategoryName(category)).toBe(expected);
  });

  it.each([
    ["Finance", "Finance"],
    ["Compliance", "Compliance"],
    ["Operations", "Operations"],
    ["finance_operations_and_compliance", "Finance Operations And Compliance"],
  ])("preserves the expected display formatting for %s", (category, expected) => {
    expect(formatCategoryName(category)).toBe(expected);
  });

  it.each([null, undefined, "", "   "])(
    "returns the existing empty fallback for %j",
    (category) => {
      expect(formatCategoryName(category)).toBe("");
    },
  );

  it("does not mutate the original category value", () => {
    const category = "  hr  ";

    formatCategoryName(category);

    expect(category).toBe("  hr  ");
  });
});

describe("formatProviderName", () => {
  it.each(["openai", "OpenAI", "OPENAI"])("renders %s as OpenAI", (provider) => {
    expect(formatProviderName(provider)).toBe("OpenAI");
  });

  it("does not mutate the internal provider identifier", () => {
    const provider = "openai";

    formatProviderName(provider);

    expect(provider).toBe("openai");
  });
});

/**
 * Citation URLs come from Tavily web results, which the relevance gate checks
 * for topicality rather than safety. This is the browser half of a defense
 * written twice on purpose — server/app.py::_safe_external_url() is the other,
 * and it is already tested against the same hostile schemes. The two use
 * different mechanisms (urlparse vs. new URL), so each needs its own tests.
 */
describe("safeExternalUrl", () => {
  it.each([
    "javascript:alert(1)",
    "JavaScript:alert(1)",
    "  javascript:alert(1)",
    "\n\tjavascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "vbscript:msgbox(1)",
    "//evil.example",
    "not a url",
    "",
  ])("refuses to hand back %j as a clickable href", (url) => {
    expect(safeExternalUrl(url)).toBeNull();
  });

  it.each([null, undefined])("returns null for %j rather than throwing", (url) => {
    expect(safeExternalUrl(url)).toBeNull();
  });

  it.each([
    "http://intranet.example.com/policies/vpn-access",
    "https://www.nist.gov/publications/zero-trust-architecture",
  ])("returns the ordinary absolute URL %s unchanged", (url) => {
    expect(safeExternalUrl(url)).toBe(url);
  });
});
