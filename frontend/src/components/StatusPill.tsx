import type { RunStatus } from "../api/types";

interface StatusPillProps {
  status: RunStatus;
  /** A nonblank visible-label override. Meaningful whitespace is rendered as supplied. */
  label?: string;
}

const labels: Record<RunStatus, string> = {
  ok: "COMPLETE",
  caveat: "NEEDS REVIEW",
  error: "DEGRADED",
};

export function StatusPill({ status, label }: StatusPillProps) {
  const visibleLabel = label?.trim() ? label : labels[status];
  return <span className={`status-pill status-pill--${status}`}>{visibleLabel}</span>;
}
