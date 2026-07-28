import { describe, expect, it } from "vitest";

import { formatCategoryName, formatProviderName } from "./format";

describe("formatCategoryName", () => {
  it.each(["hr", "Hr", "HR", "  hr  "])("renders %j as HR", (category) => {
    expect(formatCategoryName(category)).toBe("HR");
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
