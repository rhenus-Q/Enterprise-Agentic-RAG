import type { RunDetail } from "../api/types";
import { ExecutionTimeline } from "./ExecutionTimeline";
import { StatusPill } from "./StatusPill";

interface RunDetailPanelProps {
  run: RunDetail;
}

export function RunDetailPanel({ run }: RunDetailPanelProps) {
  return (
    <aside className="run-detail" aria-labelledby="run-detail-heading">
      <div className="section-heading-row">
        <div>
          <p className="eyebrow">Run detail</p>
          <h2 id="run-detail-heading">{run.question_redacted}</h2>
        </div>
        <StatusPill status={run.status} />
      </div>

      <dl className="run-facts">
        <div>
          <dt>Total duration</dt>
          <dd>{run.total_duration_ms.toLocaleString()} ms</dd>
        </div>
        <div>
          <dt>Provider</dt>
          <dd>{run.provider}</dd>
        </div>
        <div>
          <dt>Web search</dt>
          <dd>{run.web_search_enabled ? "Enabled" : "Disabled"}</dd>
        </div>
        <div>
          <dt>Fallback policy</dt>
          <dd>{run.web_fallback_policy}</dd>
        </div>
        <div>
          <dt>Retries</dt>
          <dd>{run.retries}</dd>
        </div>
        <div>
          <dt>Stop reason</dt>
          <dd>{run.stop_reason || "None"}</dd>
        </div>
      </dl>

      <ExecutionTimeline nodePath={run.node_path} timings={run.node_timings_ms} title="Node timings" />

      <section className="detail-section" aria-labelledby="run-counters-heading">
        <h3 id="run-counters-heading">Counters</h3>
        <dl className="counter-grid">
          {Object.entries(run.counters).map(([name, value]) => (
            <div key={name}>
              <dt>{name.replaceAll("_", " ")}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="detail-section" aria-labelledby="run-sources-heading">
        <h3 id="run-sources-heading">Evidence lines</h3>
        {run.sources.length ? (
          <ul className="source-lines">
            {run.sources.map((source) => (
              <li key={source}>{source.replace(/^-\s*/, "")}</li>
            ))}
          </ul>
        ) : (
          <p className="muted-copy">No evidence lines were recorded for this run.</p>
        )}
      </section>

      <p className="trace-note">
        History is metadata-only. Answers, snippets, document bodies, prompts, and raw state are not
        stored.
      </p>
    </aside>
  );
}
