import type { RunRuntime, RuntimeStatus } from "../api/types";

interface RuntimeBadgeProps {
  status?: RuntimeStatus | null;
  runtime?: RunRuntime | null;
  loading?: boolean;
}

function providerLabel(provider: string): string {
  return provider === "openai" ? "OpenAI" : provider === "ollama" ? "Ollama" : provider;
}

export function RuntimeBadge({ status, runtime, loading = false }: RuntimeBadgeProps) {
  if (loading) {
    return <span className="runtime-badge runtime-badge--loading">Checking runtime…</span>;
  }

  if (runtime) {
    return (
      <span className="runtime-badge" title={`Fallback policy: ${runtime.web_fallback_policy}`}>
        <span className="runtime-dot" />
        {providerLabel(runtime.provider)} · {runtime.web_search_enabled ? "web available" : "web off"}
      </span>
    );
  }

  if (!status) {
    return <span className="runtime-badge runtime-badge--error">Runtime unavailable</span>;
  }

  if (status.config_error || !status.provider) {
    return <span className="runtime-badge runtime-badge--error">Configuration error</span>;
  }

  const isPrivate = status.privacy_mode || status.fully_local_mode;
  const prefix = status.fully_local_mode ? "Local" : status.privacy_mode ? "Private" : "Connected";

  return (
    <span
      className={`runtime-badge ${isPrivate ? "runtime-badge--private" : ""}`}
      title={status.chat_model ?? undefined}
    >
      <span className="runtime-dot" />
      {prefix} · {providerLabel(status.provider)}
    </span>
  );
}
