import type { NodeTiming } from "../api/types";

interface ExecutionTimelineProps {
  nodePath: string[];
  timings: NodeTiming[];
  title?: string;
}

const friendlyNodeNames: Record<string, string> = {
  retrieve: "Retrieve documents",
  grade_documents: "Grade documents",
  generate: "Generate answer",
  websearch: "Search the web",
  web_search_disabled_notice: "Record privacy limit",
  web_fallback_disabled_notice: "Record fallback limit",
  max_retries_not_grounded_notice: "Record grounding limit",
  max_retries_not_useful_notice: "Record usefulness limit",
  add_grounding_feedback: "Add grounding feedback",
  rewrite_query: "Rewrite search query",
  budget_exhausted_notice: "Record budget limit",
  tool_error_notice: "Record tool failure",
  clear_transient_tool_error: "Clear transient failure",
};

function friendlyName(node: string): string {
  return (
    friendlyNodeNames[node] ??
    node
      .split("_")
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ")
  );
}

export function ExecutionTimeline({
  nodePath,
  timings,
  title = "Execution path",
}: ExecutionTimelineProps) {
  if (nodePath.length === 0) {
    return null;
  }

  const maxDuration = Math.max(...timings.map((timing) => timing.duration_ms), 1);

  return (
    <section className="content-section" aria-labelledby="execution-heading">
      <div className="section-heading-row">
        <div>
          <p className="eyebrow">Agent trace</p>
          <h2 id="execution-heading">{title}</h2>
        </div>
        <span className="count-badge">{nodePath.length} steps</span>
      </div>

      <ol className="timeline-list">
        {nodePath.map((node, index) => {
          const duration = timings[index]?.duration_ms ?? null;
          const width = duration === null ? 0 : Math.max((duration / maxDuration) * 100, 4);

          return (
            <li className="timeline-row" key={`${node}-${index}`}>
              <span className="timeline-index">{String(index + 1).padStart(2, "0")}</span>
              <div className="timeline-step">
                <div className="timeline-label">
                  <strong>{friendlyName(node)}</strong>
                  <code>{node}</code>
                </div>
                <div className="timeline-track" aria-hidden="true">
                  <span style={{ width: `${width}%` }} />
                </div>
              </div>
              <span className="timeline-duration">
                {duration === null ? "—" : `${duration.toLocaleString()} ms`}
              </span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
