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

// Drawn from the shipped AcmeCorp corpus so a first-time visitor can reach a
// grounded answer without inventing a question.
const suggestedQuestions = [
  {
    category: "Access policy",
    question: "How do I request VPN access?",
  },
  {
    category: "Finance",
    question: "What is the reimbursement window for business expenses?",
  },
  {
    category: "Incident response",
    question: "Who is paged first during a Sev-1 incident?",
  },
  {
    category: "Compliance",
    question: "How long are security event logs retained?",
  },
];

export function AskPage({ api = apiClient, status, statusLoading = false }: AskPageProps) {
  const [question, setQuestion] = useState("");
  const [webSearchEnabled, setWebSearchEnabled] = useState<boolean | null>(null);
  const [fallbackPolicy, setFallbackPolicy] = useState<WebFallbackPolicy | null>(null);
  const [response, setResponse] = useState<AskResponse | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [suggestionsExpanded, setSuggestionsExpanded] = useState(true);

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
      setSuggestionsExpanded(false);
    } catch (requestError) {
      setError(normalizeApiError(requestError));
    } finally {
      setSubmitting(false);
    }
  }

  function updateQuestion(nextQuestion: string) {
    const isEmpty = nextQuestion.trim().length === 0;

    setQuestion(nextQuestion);
    if (isEmpty) {
      setSuggestionsExpanded(true);
    }
  }

  function selectSuggestion(nextQuestion: string) {
    setQuestion(nextQuestion);
  }

  const controlsUnavailable = statusLoading || !status || Boolean(status.config_error);
  const webSearchLocked = status?.web_search_locked === true;
  const hasOutcome = Boolean(response || error);
  const showSuggestionCards = suggestionsExpanded;

  return (
    <div className={`ask-page ${hasOutcome ? "ask-page--answered" : "ask-page--idle"}`}>
      <section className="ask-workspace" aria-labelledby="ask-page-heading">
        <div className="ask-stage">
          <div className="ask-intro">
            <p className="eyebrow">Enterprise knowledge assistant</p>
            <h1 id="ask-page-heading">Ask across your trusted knowledge.</h1>
            <p>
              Retrieves evidence, grades relevance, verifies groundedness, and self-corrects weak
              answers to reduce hallucinations and improve answer reliability.
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
              onChange={(event) => updateQuestion(event.target.value)}
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
                  <span>Fallback policy</span>
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
                className={`primary-button ${submitting ? "is-submitting" : ""}`}
                type="submit"
                disabled={submitting || question.trim().length === 0}
                aria-busy={submitting}
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
            <span>Answers include citations and metadata-only execution details.</span>
          </div>

          {status?.config_error && (
            <div className="notice notice--warning" role="alert">
              <strong>Runtime configuration needs attention</strong>
              <span>{status.config_error}</span>
            </div>
          )}
        </div>

        <section
          className={`suggestions ${showSuggestionCards ? "is-expanded" : "is-collapsed"}`}
          aria-labelledby="suggestions-heading"
        >
          <button
            className="suggestion-disclosure"
            type="button"
            aria-expanded={suggestionsExpanded}
            aria-controls="suggestion-card-grid"
            onClick={() => setSuggestionsExpanded((expanded) => !expanded)}
          >
            <span id="suggestions-heading">
              Suggested questions <span aria-hidden="true">·</span> 4
            </span>
            <span className="suggestion-chevron" aria-hidden="true">
              {suggestionsExpanded ? "−" : "+"}
            </span>
          </button>

          <div
            className="suggestion-grid"
            id="suggestion-card-grid"
            hidden={!showSuggestionCards}
          >
            {suggestedQuestions.map((suggestion) => (
              <button
                className="suggestion-card"
                type="button"
                aria-label={suggestion.question}
                onClick={() => selectSuggestion(suggestion.question)}
                disabled={submitting}
                key={suggestion.question}
              >
                <span className="suggestion-category">{suggestion.category}</span>
                <span className="suggestion-question">{suggestion.question}</span>
              </button>
            ))}
          </div>
        </section>
      </section>

      {error && <ErrorState error={error} />}

      {response && (
        <div className="answer-layout">
          <div className="answer-main">
            <AnswerCard response={response} />
            <CitationList citations={response.citations} />
          </div>
          <aside className="answer-sidebar">
            <ExecutionTimeline
              title="Execution timeline"
              nodePath={response.node_path}
              timings={response.node_timings_ms}
            />
            <section className="run-summary-card">
              <div className="section-heading-row">
                <div>
                  <p className="eyebrow">RESOLVED RUN</p>
                  <h2>Operational counters</h2>
                </div>
                <span
                  className={`web-availability-badge ${
                    response.runtime.web_search_enabled
                      ? ""
                      : "web-availability-badge--unavailable"
                  }`}
                >
                  {response.runtime.web_search_enabled ? "Web available" : "Web off"}
                </span>
              </div>
              <p className="runtime-policy-line">
                Fallback policy <strong>{response.runtime.web_fallback_policy}</strong>
              </p>
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
          </aside>
        </div>
      )}
    </div>
  );
}
