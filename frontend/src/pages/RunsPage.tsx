import { useEffect, useState } from "react";

import { apiClient } from "../api/client";
import {
  normalizeApiError,
  type ApiClient,
  type ApiError,
  type RunDetail,
  type RunsResponse,
} from "../api/types";
import { ErrorState } from "../components/ErrorState";
import { RunDetailPanel } from "../components/RunDetailPanel";
import { RunsTable } from "../components/RunsTable";

interface RunsPageProps {
  api?: ApiClient;
}

export function RunsPage({ api = apiClient }: RunsPageProps) {
  const [data, setData] = useState<RunsResponse | null>(null);
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [detailError, setDetailError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);

  async function selectRun(runId: string) {
    setSelectedRunId(runId);
    setDetail(null);
    setDetailError(null);
    setDetailLoading(true);

    try {
      setDetail(await api.getRun(runId));
    } catch (requestError) {
      setDetailError(normalizeApiError(requestError));
    } finally {
      setDetailLoading(false);
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
        {data && (
          <div className="page-stat">
            <strong>{data.count}</strong>
            <span>of {data.limit} retained</span>
          </div>
        )}
      </header>

      {loading && (
        <div className="loading-panel" role="status">
          <span className="spinner" aria-hidden="true" />
          Loading execution history…
        </div>
      )}

      {error && <ErrorState error={error} />}

      {data?.runs.length === 0 && (
        <div className="empty-state empty-state--runs">
          <span className="empty-state-mark" aria-hidden="true">
            00
          </span>
          <strong>No recorded runs yet</strong>
          <p>
            History is in-memory and metadata-only. Completed graph results will appear here until
            the backend restarts.
          </p>
        </div>
      )}

      {data && data.runs.length > 0 && (
        <div className="runs-layout">
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

          <div className="run-detail-column">
            {detailLoading && (
              <div className="loading-panel" role="status">
                <span className="spinner" aria-hidden="true" />
                Loading run detail…
              </div>
            )}
            {detailError && <ErrorState error={detailError} compact />}
            {detail && <RunDetailPanel run={detail} />}
          </div>
        </div>
      )}
    </div>
  );
}
