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

interface DocumentsPageProps {
  api?: ApiClient;
}

function formatBytes(size: number): string {
  return size < 1024 ? `${size} B` : `${(size / 1024).toFixed(1)} KB`;
}

function formatModifiedAt(timestamp: string): string {
  return new Intl.DateTimeFormat("en", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(new Date(timestamp));
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
        <div className="loading-panel" role="status">
          <span className="spinner" aria-hidden="true" />
          Loading document metadata…
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
                      {document.document_category.replaceAll("_", " ")}
                    </span>
                  </div>
                  <h3>{document.title}</h3>
                  <code>{document.file_name}</code>
                  <dl>
                    <div>
                      <dt>Size</dt>
                      <dd>{formatBytes(document.size_bytes)}</dd>
                    </div>
                    <div>
                      <dt>Modified</dt>
                      <dd>{formatModifiedAt(document.modified_at)}</dd>
                    </div>
                    <div>
                      <dt>Source</dt>
                      <dd>{document.source_type.replaceAll("_", " ")}</dd>
                    </div>
                  </dl>
                </article>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
