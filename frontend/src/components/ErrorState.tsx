import type { ApiError } from "../api/types";

interface ErrorStateProps {
  error: ApiError;
  compact?: boolean;
}

interface ErrorCopy {
  title: string;
  detail: string;
}

function copyForError(error: ApiError): ErrorCopy {
  if (error.networkError || error.code === "backend_unreachable") {
    return {
      title: "Backend unreachable",
      detail: "The app could not reach the API. Confirm the backend is running, then try again.",
    };
  }

  switch (error.code) {
    case "run_in_progress":
      return {
        title: "Question already in progress",
        detail: error.payload?.message ?? "Another question is currently being processed.",
      };
    case "preflight_failed":
      return {
        title: "Startup checks need attention",
        detail:
          error.payload?.message ??
          "The backend is available, but its startup checks did not complete successfully.",
      };
    case "config_error":
      return {
        title: "Runtime configuration error",
        detail: error.payload?.message ?? "The runtime configuration must be corrected.",
      };
    case "internal_error":
      return {
        title: "The run could not be completed",
        detail: "The backend returned an internal error without exposing sensitive details.",
      };
    case "run_not_found":
      return {
        title: "Run not found",
        detail: "This run is no longer available in the in-memory history.",
      };
    default:
      return {
        title: "Request unsuccessful",
        detail: error.payload?.message ?? "The request could not be completed. Please try again.",
      };
  }
}

export function ErrorState({ error, compact = false }: ErrorStateProps) {
  const copy = copyForError(error);

  return (
    <div
      className={`error-state ${compact ? "error-state--compact" : ""}`}
      role="alert"
      data-error-code={error.code}
    >
      <span className="error-mark" aria-hidden="true">
        !
      </span>
      <div>
        <strong>{copy.title}</strong>
        <p>{copy.detail}</p>
      </div>
      {error.status && <span className="http-code">HTTP {error.status}</span>}
    </div>
  );
}
