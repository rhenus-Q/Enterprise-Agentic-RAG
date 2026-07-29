import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("App scrolling", () => {
  it("resets window scrolling immediately when top-level navigation changes", () => {
    const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);

    render(<App />);
    expect(scrollTo).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Documents" }));
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 0, left: 0, behavior: "auto" });

    scrollTo.mockClear();
    fireEvent.click(screen.getByRole("button", { name: "Runs" }));
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 0, left: 0, behavior: "auto" });

    scrollTo.mockClear();
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 0, left: 0, behavior: "auto" });
  });

  it("retains one non-scrolling app shell across top-level page changes", () => {
    vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
    render(<App />);

    const appShell = document.querySelector<HTMLElement>(".app-shell");
    expect(appShell).not.toBeNull();
    expect(appShell?.style.overflowY).toBe("");

    fireEvent.click(screen.getByRole("button", { name: "Documents" }));
    expect(document.querySelector(".app-shell")).toBe(appShell);
    expect(screen.getByRole("main").parentElement).toBe(appShell);

    fireEvent.click(screen.getByRole("button", { name: "Runs" }));
    expect(document.querySelector(".app-shell")).toBe(appShell);
    expect(screen.getByRole("main").parentElement).toBe(appShell);
  });
});

describe("Ask page persistence", () => {
  it("keeps the same Ask page mounted and hidden while another tab is active", () => {
    vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
    render(<App />);

    const askPage = document.querySelector<HTMLElement>(".ask-page");
    expect(askPage).not.toBeNull();
    expect(askPage!.hidden).toBe(false);

    // Hidden rather than unmounted, so an in-flight run keeps its state and
    // its answer still lands when the request finishes.
    fireEvent.click(screen.getByRole("button", { name: "Documents" }));
    expect(document.querySelector(".ask-page")).toBe(askPage);
    expect(askPage!.hidden).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(document.querySelector(".ask-page")).toBe(askPage);
    expect(askPage!.hidden).toBe(false);
  });
});
