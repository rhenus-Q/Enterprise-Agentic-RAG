import { formatDuration, formatProviderName, humanizeToken } from "../lib/format";
import type { RunDetail } from "../api/types";
import { ExecutionTimeline } from "./ExecutionTimeline";
import { StatusPill } from "./StatusPill";

interface RunDetailPanelProps {
  run: RunDetail;
}

type EvidenceKind = "local" | "web" | "other";

interface EvidenceItem {
  domain: string | null;
  kind: EvidenceKind;
  raw: string;
  title: string;
  url: string | null;
}

function evidenceDomain(url: string): string | null {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

function parseEvidence(source: string): EvidenceItem {
  const raw = source.replace(/^-\s*/, "").trim();
  const lowerSource = raw.toLowerCase();
  const kind: EvidenceKind = lowerSource.startsWith("local corpus:")
    ? "local"
    : lowerSource.startsWith("web search:")
      ? "web"
      : "other";
  const url = raw.match(/https?:\/\/\S+/)?.[0].replace(/[),.;]+$/, "") ?? null;
  let title = raw.replace(/^(Local corpus|Web search):\s*/i, "");

  if (url) {
    title = title.slice(0, title.indexOf(url)).replace(/\s*[—-]\s*$/, "").trim();
  }

  return {
    domain: url ? evidenceDomain(url) : null,
    kind,
    raw,
    title: title || raw,
    url,
  };
}

export function RunDetailPanel({ run }: RunDetailPanelProps) {
  const evidence = run.sources.map(parseEvidence);

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
          <dd>{formatDuration(run.total_duration_ms)}</dd>
        </div>
        <div>
          <dt>Provider</dt>
          <dd>{formatProviderName(run.provider)}</dd>
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
          <dd>{run.stop_reason ? humanizeToken(run.stop_reason) : "—"}</dd>
        </div>
      </dl>

      <ExecutionTimeline nodePath={run.node_path} timings={run.node_timings_ms} title="Node timings" />

      <section className="detail-section" aria-labelledby="run-counters-heading">
        <h3 id="run-counters-heading">Counters</h3>
        <dl className="counter-grid">
          {Object.entries(run.counters).map(([name, value]) => (
            <div key={name}>
              <dt>{humanizeToken(name)}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="detail-section" aria-labelledby="run-sources-heading">
        <h3 id="run-sources-heading">Evidence lines</h3>
        {evidence.length ? (
          <ul className="evidence-list">
            {evidence.map((item) => (
              <li
                className={`evidence-row evidence-row--${item.kind}`}
                key={item.raw}
                title={item.raw}
              >
                <span className={`evidence-kind evidence-kind--${item.kind}`}>
                  {item.kind === "local" ? "Local" : item.kind === "web" ? "Web" : "Source"}
                </span>
                <div className="evidence-content">
                  <div className="evidence-title-row">
                    <strong>{item.title}</strong>
                    {item.url && (
                      <a
                        className="evidence-external"
                        href={item.url}
                        target="_blank"
                        rel="noreferrer"
                        aria-label={`Open ${item.title} in a new tab`}
                        title={item.url}
                      >
                        Open
                        <span aria-hidden="true">↗</span>
                      </a>
                    )}
                  </div>
                  <div className="evidence-meta">
                    <span>
                      {item.kind === "local"
                        ? "Local corpus"
                        : item.domain ?? "Recorded evidence"}
                    </span>
                    {item.url && (
                      <code className="truncate-text" title={item.url}>
                        {item.url}
                      </code>
                    )}
                  </div>
                </div>
              </li>
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
