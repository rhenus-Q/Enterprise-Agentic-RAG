import { useEffect, useState } from "react";

import { apiClient } from "../api/client";
import {
  normalizeApiError,
  type ApiClient,
  type ApiError,
  type DocumentsResponse,
} from "../api/types";
import { ContentReveal } from "../components/ContentReveal";
import { ErrorState } from "../components/ErrorState";
import { IndexStatusCard } from "../components/IndexStatusCard";
import {
  formatBytes,
  formatCategoryName,
  formatDate,
  humanizeToken,
} from "../lib/format";

interface DocumentsPageProps {
  api?: ApiClient;
}

const DOCUMENT_CARD_SKELETON_COUNT = 6;

function DocumentsLoadingSkeleton() {
  return (
    <div
      className="documents-loading"
      data-testid="documents-loading-skeleton"
      role="status"
    >
      <span className="sr-only">Loading document metadata…</span>

      <section className="index-card index-card--skeleton" aria-hidden="true">
        <div className="section-heading-row">
          <div className="index-identity">
            <span className="skeleton skeleton--index-mark" />
            <div className="skeleton-heading-copy">
              <span className="skeleton skeleton--eyebrow" />
              <span className="skeleton skeleton--section-title" />
            </div>
          </div>
          <span className="skeleton skeleton--badge" />
        </div>

        <div className="index-grid">
          {Array.from({ length: 6 }, (_, index) => (
            <div className="skeleton-metadata-pair" key={index}>
              <span className="skeleton skeleton--metadata-label" />
              <span className="skeleton skeleton--metadata-value" />
            </div>
          ))}
        </div>
      </section>

      <section className="documents-section documents-section--skeleton" aria-hidden="true">
        <div className="section-heading-row">
          <div className="skeleton-heading-copy">
            <span className="skeleton skeleton--eyebrow" />
            <span className="skeleton skeleton--section-title" />
          </div>
          <span className="skeleton skeleton--count-badge" />
        </div>

        <div className="document-grid">
          {Array.from({ length: DOCUMENT_CARD_SKELETON_COUNT }, (_, index) => (
            <article className="document-card document-card--skeleton" key={index}>
              <div className="document-card-topline">
                <span className="skeleton skeleton--file-mark" />
                <span className="skeleton skeleton--category" />
              </div>
              <span className="skeleton skeleton--document-title" />
              <span className="skeleton skeleton--filename" />
              <span className="skeleton skeleton--document-meta" />
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

export function DocumentsPage({ api = apiClient }: DocumentsPageProps) {
  const [data, setData] = useState<DocumentsResponse | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const loadingPending = loading && !data && !error;

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
        {data ? (
          <div className="page-stat">
            <strong>{data.document_count}</strong>
            <span>DOCUMENTS INDEXED</span>
          </div>
        ) : loadingPending ? (
          <div
            className="page-stat page-stat--loading"
            data-testid="document-count-placeholder"
            aria-hidden="true"
          >
            <span className="skeleton skeleton--stat-value" />
            <span className="skeleton skeleton--stat-label" />
          </div>
        ) : null}
      </header>

      {loadingPending && <DocumentsLoadingSkeleton />}

      {error && (
        <ContentReveal>
          <ErrorState error={error} />
        </ContentReveal>
      )}

      {data && (
        <ContentReveal className="documents-content" testId="documents-loaded-content">
          {data.config_error && (
            <div className="notice notice--warning" role="alert">
              <strong>Index status is unavailable</strong>
              <span>{data.config_error}</span>
            </div>
          )}

          {data.index && <IndexStatusCard index={data.index} />}

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
                <p>
                  Add Markdown source files to the configured corpus before rebuilding the index.
                </p>
              </div>
            ) : (
              <div className="document-grid">
                {data.documents.map((document) => (
                  <article className="document-card" key={document.source}>
                    <div className="document-card-topline">
                      <span className="file-mark" aria-hidden="true">
                        <svg viewBox="0 0 28 32">
                          <path d="M4.5 1.5h12l7 7v22H4.5z" />
                          <path d="M16.5 1.5v7h7M8.5 15.5h11M8.5 20h11M8.5 24.5H16" />
                        </svg>
                        <span>MD</span>
                      </span>
                      <span className="category-label">
                        {formatCategoryName(document.document_category)}
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
        </ContentReveal>
      )}
    </div>
  );
}
