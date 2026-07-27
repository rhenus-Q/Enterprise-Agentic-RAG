import { formatDateTime, formatDuration } from "../lib/format";
import type { RunSummary } from "../api/types";
import { StatusPill } from "./StatusPill";

interface RunsTableProps {
  runs: RunSummary[];
  selectedRunId: string | null;
  onSelect: (runId: string) => void;
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
            <th className="numeric-cell">Duration</th>
            <th>Started</th>
            <th>
              <span className="sr-only">Open run detail</span>
            </th>
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
              <td className="numeric-cell">{formatDuration(run.total_duration_ms)}</td>
              <td>{formatDateTime(run.generated_at)}</td>
              <td className="run-chevron" aria-hidden="true">
                ›
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
