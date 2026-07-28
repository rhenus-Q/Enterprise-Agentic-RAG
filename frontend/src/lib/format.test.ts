import { describe, expect, it } from "vitest";

import { formatProviderName } from "./format";

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
