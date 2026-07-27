import { useEffect, useState } from "react";

import { apiClient } from "../api/client";
import {
  normalizeApiError,
  type ApiClient,
  type ApiError,
  type DocumentsResponse,
} from "../api/types";
import { ErrorState } from "../components/ErrorState";
import { IndexStatusCard } from "../components/IndexStatusCard";
import { formatBytes, formatDate, humanizeToken } from "../lib/format";

interface DocumentsPageProps {
  api?: ApiClient;
}

export function DocumentsPage({ api = apiClient }: DocumentsPageProps) {
  const [data, setData] = useState<DocumentsResponse | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    api
      .getDocuments()
      .then((response) => {
        if (active) {
          setData(response);
        }
      })
      .catch((requestError: unknown) => {
        if (active) {
          setError(normalizeApiError(requestError));
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [api]);

  return (
    <div className="documents-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Knowledge layer</p>
          <h1>Documents and index health</h1>
          <p>
            A read-only view of the local corpus and the embedding configuration used for
            retrieval.
          </p>
        </div>
        {data && (
          <div className="page-stat">
            <strong>{data.document_count}</strong>
            <span>corpus documents</span>
          </div>
        )}
      </header>

      {loading && (
        <div className="skeleton-panel" role="status">
          <span className="sr-only">Loading document metadata…</span>
          <span className="skeleton skeleton--title" aria-hidden="true" />
          <span className="skeleton skeleton--wide" aria-hidden="true" />
          <div className="skeleton-row" aria-hidden="true">
            <span className="skeleton" />
            <span className="skeleton" />
            <span className="skeleton" />
          </div>
          <span className="skeleton skeleton--medium" aria-hidden="true" />
        </div>
      )}

      {error && <ErrorState error={error} />}

      {data?.config_error && (
        <div className="notice notice--warning" role="alert">
          <strong>Index status is unavailable</strong>
          <span>{data.config_error}</span>
        </div>
      )}

      {data?.index && <IndexStatusCard index={data.index} />}

      {data && (
        <section className="documents-section" aria-labelledby="corpus-heading">
          <div className="section-heading-row">
            <div>
              <p className="eyebrow">Local corpus</p>
              <h2 id="corpus-heading">Indexed source files</h2>
            </div>
            <span className="count-badge">{data.document_count} files</span>
          </div>

          {data.documents.length === 0 ? (
            <div className="empty-state">
              <strong>No corpus documents found</strong>
              <p>Add Markdown source files to the configured corpus before rebuilding the index.</p>
            </div>
          ) : (
            <div className="document-grid">
              {data.documents.map((document) => (
                <article className="document-card" key={document.source}>
                  <div className="document-card-topline">
                    <span className="file-mark" aria-hidden="true">
                      MD
                    </span>
                    <span className="category-label">
                      {humanizeToken(document.document_category)}
                    </span>
                  </div>
                  <h3>{document.title}</h3>
                  <code>{document.file_name}</code>
                  <p className="document-meta">
                    {formatBytes(document.size_bytes)} · {formatDate(document.modified_at)} ·{" "}
                    {humanizeToken(document.source_type)}
                  </p>
                </article>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
