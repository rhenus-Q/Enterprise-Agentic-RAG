import type { IndexStatus } from "../api/types";
import { formatProviderName } from "../lib/format";

interface IndexStatusCardProps {
  index: IndexStatus;
}

const compatibilityLabels: Record<IndexStatus["compatibility"], string> = {
  compatible: "Compatible",
  legacy_no_fingerprint: "Legacy fingerprint",
  provider_mismatch: "Provider mismatch",
  model_mismatch: "Model mismatch",
  missing_index: "Index missing",
  index_unreadable: "Index unreadable",
};

function fingerprintValue(
  fingerprint: Record<string, string> | null,
  key: "embedding_provider" | "embedding_model",
): string {
  const value = fingerprint?.[key];

  if (!value) {
    return "Not recorded";
  }

  return key === "embedding_provider" ? formatProviderName(value) : value;
}

export function IndexStatusCard({ index }: IndexStatusCardProps) {
  const unreadable = index.compatibility === "index_unreadable";

  return (
    <section className="index-card" aria-labelledby="index-status-heading">
      <div className="section-heading-row">
        <div className="index-identity">
          <span className="index-mark" aria-hidden="true">
            <svg viewBox="0 0 36 36">
              <ellipse cx="18" cy="9" rx="11" ry="4" />
              <path d="M7 9v9c0 2.2 4.9 4 11 4s11-1.8 11-4V9M7 18v9c0 2.2 4.9 4 11 4s11-1.8 11-4v-9" />
            </svg>
          </span>
          <div>
            <p className="eyebrow">RETRIEVAL INDEX</p>
            <h2 id="index-status-heading">Embedding compatibility</h2>
          </div>
        </div>
        <span
          className={`compatibility-badge ${
            index.reindex_required || unreadable ? "compatibility-badge--warning" : ""
          }`}
        >
          {compatibilityLabels[index.compatibility]}
        </span>
      </div>

      {index.reindex_required && (
        <div className="notice notice--warning reindex-callout" role="alert">
          <strong>Reindex required</strong>
          <span>
            Run <code>uv run python ingestion.py</code> for the active embedding configuration.
          </span>
        </div>
      )}

      {unreadable && (
        <div className="notice notice--warning reindex-callout" role="alert">
          <strong>Index could not be inspected</strong>
          <span>
            The server could not read the index location, so its compatibility is unknown. Check the
            directory&apos;s permissions. A rebuild may not be necessary.
          </span>
        </div>
      )}

      <dl className="index-grid">
        <div>
          <dt>Index</dt>
          <dd>
            <code className="index-identifier">{index.collection_name}</code>
          </dd>
        </div>
        <div>
          <dt>Location</dt>
          <dd>
            <code className="index-identifier">{index.persist_directory}</code>
          </dd>
        </div>
        <div>
          <dt>Expected provider</dt>
          <dd>{fingerprintValue(index.expected_fingerprint, "embedding_provider")}</dd>
        </div>
        <div>
          <dt>Stored provider</dt>
          <dd>{fingerprintValue(index.stored_fingerprint, "embedding_provider")}</dd>
        </div>
        <div>
          <dt>Expected model</dt>
          <dd>{fingerprintValue(index.expected_fingerprint, "embedding_model")}</dd>
        </div>
        <div>
          <dt>Stored model</dt>
          <dd>{fingerprintValue(index.stored_fingerprint, "embedding_model")}</dd>
        </div>
      </dl>
    </section>
  );
}
