import { type FormEvent, useEffect, useState } from "react";

import { apiClient } from "../api/client";
import {
  normalizeApiError,
  type ApiClient,
  type ApiError,
  type AskResponse,
  type RuntimeStatus,
  type WebFallbackPolicy,
} from "../api/types";
import { AnswerCard } from "../components/AnswerCard";
import { CitationList } from "../components/CitationList";
import { ErrorState } from "../components/ErrorState";
import { ExecutionTimeline } from "../components/ExecutionTimeline";
import { RuntimeBadge } from "../components/RuntimeBadge";

interface AskPageProps {
  api?: ApiClient;
  status: RuntimeStatus | null;
  statusLoading?: boolean;
}

function asFallbackPolicy(value: string | null): WebFallbackPolicy | null {
  return value === "conservative" || value === "aggressive" || value === "disabled"
    ? value
    : null;
}

export function AskPage({ api = apiClient, status, statusLoading = false }: AskPageProps) {
  const [question, setQuestion] = useState("");
  const [webSearchEnabled, setWebSearchEnabled] = useState<boolean | null>(null);
  const [fallbackPolicy, setFallbackPolicy] = useState<WebFallbackPolicy | null>(null);
  const [response, setResponse] = useState<AskResponse | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!status) {
      setWebSearchEnabled(null);
      setFallbackPolicy(null);
      return;
    }

    setWebSearchEnabled(
      status.web_search_locked ? false : (status.web_search_enabled_default ?? null),
    );
    setFallbackPolicy(asFallbackPolicy(status.web_fallback_policy_default));
  }, [status]);

  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanedQuestion = question.trim();
    if (!cleanedQuestion || submitting) {
      return;
    }

    setSubmitting(true);
    setResponse(null);
    setError(null);

    try {
      const result = await api.ask({
        question: cleanedQuestion,
        web_search_enabled: status?.web_search_locked ? false : webSearchEnabled,
        web_fallback_policy: fallbackPolicy,
      });
      setResponse(result);
    } catch (requestError) {
      setError(normalizeApiError(requestError));
    } finally {
      setSubmitting(false);
    }
  }

  const controlsUnavailable = statusLoading || !status || Boolean(status.config_error);
  const webSearchLocked = status?.web_search_locked === true;
  const hasOutcome = Boolean(response || error);

  return (
    <div className={`ask-page ${hasOutcome ? "ask-page--answered" : "ask-page--idle"}`}>
      <section className="ask-workspace" aria-labelledby="ask-page-heading">
        <div className="ask-intro">
          <p className="eyebrow">Enterprise knowledge</p>
          <h1 id="ask-page-heading">Ask your knowledge base</h1>
          <p>
            Search trusted internal documents, with transparent evidence and the agent path that
            produced the answer.
          </p>
        </div>

        <form className="question-composer" onSubmit={submitQuestion}>
          <label className="sr-only" htmlFor="question">
            Question
          </label>
          <textarea
            id="question"
            name="question"
            placeholder="Ask about a policy, process, or internal guide…"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            disabled={submitting}
            maxLength={4000}
            rows={3}
          />

          <div className="composer-toolbar">
            <div className="override-controls" aria-label="Run options">
              <label className={`toggle-control ${webSearchLocked ? "is-locked" : ""}`}>
                <input
                  type="checkbox"
                  checked={webSearchEnabled ?? false}
                  onChange={(event) => setWebSearchEnabled(event.target.checked)}
                  disabled={controlsUnavailable || webSearchLocked || submitting}
                />
                <span className="toggle-track" aria-hidden="true" />
                <span>Web search</span>
              </label>

              <label className="select-control">
                <span>Fallback</span>
                <select
                  aria-label="Web fallback policy"
                  value={fallbackPolicy ?? ""}
                  onChange={(event) =>
                    setFallbackPolicy(asFallbackPolicy(event.target.value || null))
                  }
                  disabled={controlsUnavailable || submitting}
                >
                  <option value="">Runtime default</option>
                  <option value="conservative">Conservative</option>
                  <option value="aggressive">Aggressive</option>
                  <option value="disabled">Disabled</option>
                </select>
              </label>

              {webSearchLocked && <span className="lock-label">Locked by runtime policy</span>}
            </div>

            <button
              className="primary-button"
              type="submit"
              disabled={submitting || question.trim().length === 0}
            >
              {submitting ? (
                <>
                  <span className="spinner" aria-hidden="true" />
                  Running
                </>
              ) : (
                <>
                  Ask
                  <span aria-hidden="true">→</span>
                </>
              )}
            </button>
          </div>
        </form>

        <div className="ask-runtime-line">
          <RuntimeBadge status={status} loading={statusLoading} />
          <span>Answers include citations and metadata-only execution details.</span>
        </div>

        {status?.config_error && (
          <div className="notice notice--warning" role="alert">
            <strong>Runtime configuration needs attention</strong>
            <span>{status.config_error}</span>
          </div>
        )}
      </section>

      {error && <ErrorState error={error} />}

      {response && (
        <div className="answer-layout">
          <div className="answer-main">
            <AnswerCard response={response} />
            <CitationList citations={response.citations} />
          </div>
          <aside className="answer-sidebar">
            <section className="run-summary-card">
              <div className="section-heading-row">
                <div>
                  <p className="eyebrow">Resolved run</p>
                  <h2>Runtime</h2>
                </div>
                <RuntimeBadge runtime={response.runtime} />
              </div>
              <dl className="counter-grid">
                <div>
                  <dt>LLM calls</dt>
                  <dd>{response.tracked_llm_calls}</dd>
                </div>
                <div>
                  <dt>Retries</dt>
                  <dd>{response.retries}</dd>
                </div>
                <div>
                  <dt>Web searches</dt>
                  <dd>{response.web_search_count}</dd>
                </div>
                <div>
                  <dt>Web grades</dt>
                  <dd>{response.web_result_grading_count}</dd>
                </div>
              </dl>
            </section>
            <ExecutionTimeline
              nodePath={response.node_path}
              timings={response.node_timings_ms}
            />
          </aside>
        </div>
      )}
    </div>
  );
}
