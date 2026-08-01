import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { apiClient, demoScenarioController } from "./api/client";
import type { MockScenario } from "./api/mock";
import {
  normalizeApiError,
  type ApiClient,
  type ApiError,
  type RuntimeStatus,
} from "./api/types";
import { ErrorState } from "./components/ErrorState";
import { RuntimeBadge } from "./components/RuntimeBadge";
import { AskPage } from "./pages/AskPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { RunsPage } from "./pages/RunsPage";

type Page = "ask" | "documents" | "runs";

const pages: Array<{ id: Page; label: string }> = [
  { id: "ask", label: "Ask" },
  { id: "documents", label: "Documents" },
  { id: "runs", label: "Runs" },
];

interface AppProps {
  api?: ApiClient;
}

export default function App({ api = apiClient }: AppProps) {
  const [page, setPage] = useState<Page>("ask");
  const previousPage = useRef<Page>(page);
  const [status, setStatus] = useState<RuntimeStatus | null>(null);
  const [statusError, setStatusError] = useState<ApiError | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [statusRequestVersion, setStatusRequestVersion] = useState(0);
  const [scenarioVersion, setScenarioVersion] = useState(0);
  const [scenario, setScenario] = useState<MockScenario | null>(
    demoScenarioController?.getScenario() ?? null,
  );

  useEffect(() => {
    const controller = demoScenarioController;
    if (!controller) {
      return;
    }

    return controller.subscribe(() => {
      setScenario(controller.getScenario());
      setScenarioVersion((version) => version + 1);
    });
  }, []);

  useEffect(() => {
    let active = true;
    setStatusLoading(true);
    setStatusError(null);

    api
      .getStatus()
      .then((nextStatus) => {
        if (active) {
          setStatus(nextStatus);
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setStatus(null);
          setStatusError(normalizeApiError(error));
        }
      })
      .finally(() => {
        if (active) {
          setStatusLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [api, scenarioVersion, statusRequestVersion]);

  useLayoutEffect(() => {
    if (previousPage.current === page) {
      return;
    }

    previousPage.current = page;
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [page]);

  function changeScenario(nextScenario: MockScenario) {
    const option = demoScenarioController?.options.find((item) => item.id === nextScenario);
    if (option) {
      setPage(option.page);
    }
    demoScenarioController?.setScenario(nextScenario);
  }

  function retryStatus() {
    if (!statusLoading) {
      setStatusRequestVersion((version) => version + 1);
    }
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="header-inner">
          <button className="product-name" type="button" onClick={() => setPage("ask")}>
            <span className="product-mark" aria-hidden="true">
              <svg viewBox="0 0 32 32">
                <path d="M8.5 23.5 16 7.5l7.5 16M11.1 18.5h9.8" />
                <circle cx="16" cy="7.5" r="2.1" />
                <circle cx="8.5" cy="23.5" r="2.1" />
                <circle cx="23.5" cy="23.5" r="2.1" />
              </svg>
            </span>
            <span>
              <strong>Agentic RAG</strong>
              <small>Knowledge workspace</small>
            </span>
          </button>

          <nav className="tab-navigation" aria-label="Primary navigation">
            {pages.map((item) => (
              <button
                className={page === item.id ? "is-active" : ""}
                type="button"
                aria-current={page === item.id ? "page" : undefined}
                onClick={() => setPage(item.id)}
                key={item.id}
              >
                {item.label}
              </button>
            ))}
          </nav>

          <div className="header-actions">
            <RuntimeBadge status={status} loading={statusLoading} />
            {demoScenarioController && scenario && (
              <details className="demo-control">
                <summary>
                  <span className="dev-tag" aria-hidden="true">
                    DEV
                  </span>
                  Preview states
                </summary>
                <label>
                  <span>Mock scenario</span>
                  <select
                    aria-label="Preview mock state"
                    value={scenario}
                    onChange={(event) => changeScenario(event.target.value as MockScenario)}
                  >
                    {demoScenarioController.options.map((option) => (
                      <option value={option.id} key={option.id}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
              </details>
            )}
          </div>
        </div>
      </header>

      {statusError && (
        <div className="global-notice">
          <ErrorState
            error={statusError}
            compact
            actionLabel="Retry"
            onAction={retryStatus}
            actionDisabled={statusLoading}
          />
        </div>
      )}

      <main className={`page-frame page-frame--${page}`}>
        {/* Ask stays mounted and is hidden instead of unmounted: a run takes
            tens of seconds, and unmounting would discard the in-flight request
            and drop its answer when the user looks at another tab. Documents
            and Runs stay conditional, so they keep refetching on tab entry. */}
        <AskPage
          api={api}
          status={status}
          statusLoading={statusLoading}
          hidden={page !== "ask"}
          globalNoticeVisible={Boolean(statusError)}
          key={`ask-${scenarioVersion}`}
        />

        {page === "documents" && (
          <DocumentsPage api={api} key={`documents-${scenarioVersion}`} />
        )}
        {page === "runs" && <RunsPage api={api} key={`runs-${scenarioVersion}`} />}
      </main>
    </div>
  );
}
