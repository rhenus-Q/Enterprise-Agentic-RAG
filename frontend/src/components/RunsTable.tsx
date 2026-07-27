import type { RunSummary } from "../api/types";
import { StatusPill } from "./StatusPill";

interface RunsTableProps {
  runs: RunSummary[];
  selectedRunId: string | null;
  onSelect: (runId: string) => void;
}

function formatTimestamp(timestamp: string): string {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(timestamp));
}

export function RunsTable({ runs, selectedRunId, onSelect }: RunsTableProps) {
  return (
    <div className="table-shell">
      <table className="runs-table">
        <thead>
          <tr>
            <th>Question</th>
            <th>Status</th>
            <th>Provider</th>
            <th>Duration</th>
            <th>Started</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr className={selectedRunId === run.run_id ? "is-selected" : ""} key={run.run_id}>
              <td>
                <button className="run-select" type="button" onClick={() => onSelect(run.run_id)}>
                  <strong>{run.question_redacted}</strong>
                  <span>{run.run_id}</span>
                </button>
              </td>
              <td>
                <StatusPill status={run.status} />
              </td>
              <td className="table-mono">{run.provider}</td>
              <td className="table-mono">{run.total_duration_ms.toLocaleString()} ms</td>
              <td>{formatTimestamp(run.generated_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
