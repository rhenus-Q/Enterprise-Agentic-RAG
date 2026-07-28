import type { RunStatus } from "../api/types";

interface StatusPillProps {
  status: RunStatus;
  label?: string;
}

const labels: Record<RunStatus, string> = {
  ok: "COMPLETE",
  caveat: "NEEDS REVIEW",
  error: "DEGRADED",
};

export function StatusPill({ status, label }: StatusPillProps) {
  const visibleLabel = status === "ok" ? labels.ok : (label ?? labels[status]);
  return <span className={`status-pill status-pill--${status}`}>{visibleLabel}</span>;
}
