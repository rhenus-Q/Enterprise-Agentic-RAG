import { useEffect, useRef, useState } from "react";

import { apiClient } from "../api/client";
import {
  normalizeApiError,
  type ApiClient,
  type ApiError,
  type RunDetail,
  type RunsResponse,
} from "../api/types";
import { ContentReveal } from "../components/ContentReveal";
import { ErrorState } from "../components/ErrorState";
import { RunDetailPanel } from "../components/RunDetailPanel";
import { RunsTable } from "../components/RunsTable";

interface RunsPageProps {
  api?: ApiClient;
}

function RunDetailLoadingSkeleton() {
  return (
    <aside
      className="run-detail run-detail--skeleton"
      data-testid="run-detail-loading-skeleton"
      aria-hidden="true"
    >
      <div className="section-heading-row">
        <div className="skeleton-heading-copy">
          <span className="skeleton skeleton--eyebrow" />
          <span className="skeleton skeleton--run-title" />
        </div>
        <span className="skeleton skeleton--badge" />
      </div>

      <div className="run-facts">
        {Array.from({ length: 6 }, (_, index) => (
          <div className="skeleton-metadata-pair" key={index}>
            <span className="skeleton skeleton--metadata-label" />
            <span className="skeleton skeleton--metadata-value" />
          </div>
        ))}
      </div>

      <section className="content-section">
        <span className="skeleton skeleton--section-title" />
        <div className="run-timeline-skeleton">
          {Array.from({ length: 4 }, (_, index) => (
            <div className="run-timeline-skeleton-row" key={index}>
              <span className="skeleton skeleton--timeline-node" />
              <span className="skeleton skeleton--timeline-copy" />
            </div>
          ))}
        </div>
      </section>

      <section className="detail-section">
        <span className="skeleton skeleton--section-title" />
        <div className="counter-grid">
          {Array.from({ length: 4 }, (_, index) => (
            <div className="skeleton-metadata-pair" key={index}>
              <span className="skeleton skeleton--metadata-label" />
              <span className="skeleton skeleton--metadata-value" />
            </div>
          ))}
        </div>
      </section>

      <section className="detail-section">
        <span className="skeleton skeleton--section-title" />
        <div className="run-source-skeleton">
          <span className="skeleton skeleton--wide" />
          <span className="skeleton skeleton--medium" />
        </div>
      </section>

      <p className="trace-note">
        <span className="skeleton skeleton--medium" />
      </p>
    </aside>
  );
}

function RunsLoadingSkeleton() {
  return (
    <div
      className="runs-layout runs-loading"
      data-testid="runs-loading-skeleton"
      role="status"
    >
      <span className="sr-only">Loading execution history…</span>

      <section className="runs-list-section" aria-hidden="true">
        <div className="section-heading-row">
          <div className="skeleton-heading-copy">
            <span className="skeleton skeleton--eyebrow" />
            <span className="skeleton skeleton--section-title" />
          </div>
          <span className="skeleton skeleton--count-badge" />
        </div>
        <div className="table-shell runs-table-skeleton">
          <div className="runs-table-skeleton-head">
            {Array.from({ length: 6 }, (_, index) => (
              <span className="skeleton skeleton--table-heading" key={index} />
            ))}
          </div>
          {Array.from({ length: 3 }, (_, rowIndex) => (
            <div className="runs-table-skeleton-row" key={rowIndex}>
              <span className="skeleton skeleton--table-question" />
              {Array.from({ length: 5 }, (_, cellIndex) => (
                <span className="skeleton skeleton--table-cell" key={cellIndex} />
              ))}
            </div>
          ))}
        </div>
      </section>

      <div className="run-detail-column" aria-hidden="true">
        <RunDetailLoadingSkeleton />
      </div>
    </div>
  );
}

export function RunsPage({ api = apiClient }: RunsPageProps) {
  const [data, setData] = useState<RunsResponse | null>(null);
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [detailError, setDetailError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const detailRequestVersion = useRef(0);
  const loadingPending = loading && !data && !error;

  async function selectRun(runId: string) {
    const requestVersion = ++detailRequestVersion.current;
    setSelectedRunId(runId);
    setDetailError(null);
    setDetailLoading(true);

    try {
      const nextDetail = await api.getRun(runId);
      if (detailRequestVersion.current === requestVersion) {
        setDetail(nextDetail);
      }
    } catch (requestError) {
      if (detailRequestVersion.current === requestVersion) {
        setDetailError(normalizeApiError(requestError));
      }
    } finally {
      if (detailRequestVersion.current === requestVersion) {
        setDetailLoading(false);
      }
    }
  }

  useEffect(() => {
    let active = true;

    api
      .getRuns()
      .then((response) => {
        if (!active) {
          return;
        }
        setData(response);
        if (response.runs.length > 0) {
          void selectRun(response.runs[0].run_id);
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
      detailRequestVersion.current += 1;
    };
  }, [api]);

  return (
    <div className="runs-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Execution history</p>
          <h1>Recent agent runs</h1>
          <p>
            Inspect node timings, runtime policy, counters, and evidence metadata for completed graph
            executions.
          </p>
        </div>
        {data ? (
          <div className="page-stat">
            <strong>{data.count}</strong>
            <span>OF {data.limit} RETAINED</span>
          </div>
        ) : loadingPending ? (
          <div
            className="page-stat page-stat--loading"
            aria-hidden="true"
          >
            <span className="skeleton skeleton--stat-value" />
            <span className="skeleton skeleton--stat-label" />
          </div>
        ) : null}
      </header>

      {loadingPending && <RunsLoadingSkeleton />}

      {error && (
        <ContentReveal>
          <ErrorState error={error} />
        </ContentReveal>
      )}

      {data?.runs.length === 0 && (
        <ContentReveal className="empty-state empty-state--runs">
          <span className="empty-state-mark" aria-hidden="true">
            00
          </span>
          <strong>No recorded runs yet</strong>
          <p>
            History is in-memory and metadata-only. Completed graph results will appear here until
            the backend restarts.
          </p>
        </ContentReveal>
      )}

      {data && data.runs.length > 0 && (
        <ContentReveal className="runs-layout" testId="runs-loaded-content">
          <section className="runs-list-section" aria-labelledby="runs-table-heading">
            <div className="section-heading-row">
              <div>
                <p className="eyebrow">Newest first</p>
                <h2 id="runs-table-heading">Run history</h2>
              </div>
              <span className="count-badge">{data.count}</span>
            </div>
            <RunsTable
              runs={data.runs}
              selectedRunId={selectedRunId}
              onSelect={(runId) => void selectRun(runId)}
            />
          </section>

          <div className="run-detail-column" aria-busy={detailLoading}>
            {detailLoading && !detail && (
              <>
                <span className="sr-only" role="status">
                  Loading run detail…
                </span>
                <RunDetailLoadingSkeleton />
              </>
            )}
            {detailLoading && detail && (
              <span className="sr-only" role="status">
                Loading selected run detail…
              </span>
            )}
            {detailError && <ErrorState error={detailError} compact />}
            {detail && (
              <ContentReveal>
                <RunDetailPanel run={detail} />
              </ContentReveal>
            )}
          </div>
        </ContentReveal>
      )}
    </div>
  );
}
