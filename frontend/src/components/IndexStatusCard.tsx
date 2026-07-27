import type { IndexStatus } from "../api/types";

interface IndexStatusCardProps {
  index: IndexStatus;
}

const compatibilityLabels: Record<IndexStatus["compatibility"], string> = {
  compatible: "Compatible",
  legacy_no_fingerprint: "Legacy fingerprint",
  provider_mismatch: "Provider mismatch",
  model_mismatch: "Model mismatch",
  missing_index: "Index missing",
};

function fingerprintValue(
  fingerprint: Record<string, string> | null,
  key: "embedding_provider" | "embedding_model",
): string {
  return fingerprint?.[key] ?? "Not recorded";
}

export function IndexStatusCard({ index }: IndexStatusCardProps) {
  return (
    <section className="index-card" aria-labelledby="index-status-heading">
      <div className="section-heading-row">
        <div>
          <p className="eyebrow">Retrieval index</p>
          <h2 id="index-status-heading">Embedding compatibility</h2>
        </div>
        <span
          className={`compatibility-badge ${
            index.reindex_required ? "compatibility-badge--warning" : ""
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

      <dl className="index-grid">
        <div>
          <dt>Index</dt>
          <dd>
            <code>{index.collection_name}</code>
          </dd>
        </div>
        <div>
          <dt>Location</dt>
          <dd>
            <code>{index.persist_directory}</code>
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
