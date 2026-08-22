import type { RunRuntime, RuntimeStatus } from "../api/types";
import { formatProviderName } from "../lib/format";

interface RuntimeBadgeProps {
  status?: RuntimeStatus | null;
  runtime?: RunRuntime | null;
  loading?: boolean;
}

const PROFILE_NAMES: Record<string, string> = {
  legacy: "Legacy",
  luna_all: "Luna All",
  flash_luna: "Flash + Luna",
  local: "Local",
};

export function RuntimeBadge({ status, runtime, loading = false }: RuntimeBadgeProps) {
  if (loading) {
    return <span className="runtime-badge runtime-badge--loading">Checking runtime…</span>;
  }

  if (runtime) {
    return (
      <span className="runtime-badge" title={`Fallback policy: ${runtime.web_fallback_policy}`}>
        <span className="runtime-dot" />
        <span className="runtime-copy">
          <strong>{formatProviderName(runtime.provider)}</strong>
          <small>{runtime.web_search_enabled ? "Web available" : "Web off"}</small>
        </span>
      </span>
    );
  }

  if (!status) {
    return <span className="runtime-badge runtime-badge--error">Runtime unavailable</span>;
  }

  if (status.config_error || !status.provider) {
    return <span className="runtime-badge runtime-badge--error">Configuration error</span>;
  }

  const isPrivate = status.privacy_mode || status.local_mode;
  const profileName =
    PROFILE_NAMES[status.effective_model_profile ?? ""] ?? formatProviderName(status.provider);

  return (
    <span className={`runtime-badge ${isPrivate ? "runtime-badge--private" : ""}`}>
      <span className="runtime-dot" />
      <span className="runtime-copy">
        <strong>Model · {profileName}</strong>
      </span>
    </span>
  );
}
