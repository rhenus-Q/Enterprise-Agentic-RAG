/**
 * Shared display formatters.
 *
 * Presentation only: these never change a value the API reported, they only
 * decide how it reads. Durations below one second keep millisecond precision
 * (the graph's fast nodes are only legible in ms); anything longer switches to
 * seconds so a 12,384.5 ms run reads as 12.38 s.
 */

export function formatDuration(milliseconds: number): string {
  if (milliseconds >= 1000) {
    return `${(milliseconds / 1000).toFixed(2)} s`;
  }

  return `${milliseconds.toLocaleString()} ms`;
}

export function formatBytes(size: number): string {
  return size < 1024 ? `${size} B` : `${(size / 1024).toFixed(1)} KB`;
}

export function formatDate(timestamp: string): string {
  return new Intl.DateTimeFormat("en", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(new Date(timestamp));
}

export function formatDateTime(timestamp: string): string {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(timestamp));
}

export function formatProviderName(provider: string): string {
  const normalized = provider.trim();

  if (normalized.toLowerCase() === "openai") {
    return "OpenAI";
  }

  if (normalized.toLowerCase() === "ollama") {
    return "Ollama";
  }

  return normalized;
}

export function formatCategoryName(value: string | null | undefined): string {
  const normalized = value?.trim() ?? "";

  if (!normalized) {
    return "";
  }

  if (normalized.toLowerCase() === "hr") {
    return "HR";
  }

  return normalized
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function humanizeToken(value: string): string {
  return value.replaceAll("_", " ");
}
