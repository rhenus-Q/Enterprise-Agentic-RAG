import { afterEach, describe, expect, it, vi } from "vitest";

import { runtimeFixtures } from "../mocks/fixtures";
import { apiClient } from "./client";
import { ApiError } from "./types";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("API JSON responses", () => {
  it("returns a successful JSON response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue(runtimeFixtures.openai),
      } satisfies Partial<Response>),
    );

    await expect(apiClient.getStatus()).resolves.toEqual(runtimeFixtures.openai);
  });

  it("rejects a successful response whose body is not valid JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: vi.fn().mockRejectedValue(new SyntaxError("invalid JSON")),
      } satisfies Partial<Response>),
    );

    const error = await apiClient.getStatus().catch((requestError: unknown) => requestError);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 200,
      code: "invalid_response",
    });
  });
});
