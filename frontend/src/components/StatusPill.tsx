import type { RunStatus } from "../api/types";

interface StatusPillProps {
  status: RunStatus;
  label?: string;
}

const labels: Record<RunStatus, string> = {
  ok: "Complete",
  caveat: "Needs review",
  error: "Degraded",
};

export function StatusPill({ status, label }: StatusPillProps) {
  return <span className={`status-pill status-pill--${status}`}>{label ?? labels[status]}</span>;
}
