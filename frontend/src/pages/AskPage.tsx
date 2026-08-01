import { type FormEvent, useEffect, useRef, useState } from "react";

import { apiClient } from "../api/client";
import {
  BACKEND_UNREACHABLE_CODE,
  ApiError,
  isRequestCancelled,
  isRetryableError,
  normalizeApiError,
  RUN_STILL_STOPPING_CODE,
  type ApiClient,
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
  /**
   * Hides the page without unmounting it. App keeps this page mounted across
   * tab changes so an in-flight run survives navigation — see App.tsx.
   */
  hidden?: boolean;
  /**
   * True when the app-level banner is already reporting an unreachable
   * backend, so this page can stay quiet instead of saying it twice.
   */
  globalNoticeVisible?: boolean;
}

function asFallbackPolicy(value: string | null): WebFallbackPolicy | null {
  return value === "conservative" || value === "aggressive" || value === "disabled"
    ? value
    : null;
}

function runStillStoppingError(): ApiError {
  return new ApiError("The previous run is still stopping.", {
    code: RUN_STILL_STOPPING_CODE,
    payload: {
      error: RUN_STILL_STOPPING_CODE,
      message: "The previous run is still stopping. Please try again shortly.",
    },
  });
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

export function AskPage({
  api = apiClient,
  status,
  statusLoading = false,
  hidden = false,
  globalNoticeVisible = false,
}: AskPageProps) {
  const [question, setQuestion] = useState("");
  const [webSearchEnabled, setWebSearchEnabled] = useState<boolean | null>(null);
  const [fallbackPolicy, setFallbackPolicy] = useState<WebFallbackPolicy | null>(null);
  const [response, setResponse] = useState<AskResponse | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [waitingForIdle, setWaitingForIdle] = useState(false);
  const [suggestionsExpanded, setSuggestionsExpanded] = useState(true);
  // Identifies the run that owns the UI. A stopped or superseded run clears
  // it, which is how a late-arriving response knows not to claim the composer.
  const activeRun = useRef<AbortController | null>(null);
  const errorRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    return () => {
      activeRun.current?.abort();
      activeRun.current = null;
    };
  }, []);

  useEffect(() => {
    if (!error || hidden) {
      return;
    }

    // Best effort: a long answer above can still push the message out of view,
    // and jsdom has no scrollIntoView at all — neither may break rendering.
    const prefersReducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    errorRef.current?.scrollIntoView?.({
      block: "nearest",
      behavior: prefersReducedMotion ? "auto" : "smooth",
    });
  }, [error, hidden]);

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

    const run = new AbortController();
    activeRun.current = run;

    setSubmitting(true);
    setResponse(null);
    setError(null);

    try {
      const result = await api.ask(
        {
          question: cleanedQuestion,
          web_search_enabled: status?.web_search_locked ? false : webSearchEnabled,
          web_fallback_policy: status?.web_search_locked ? null : fallbackPolicy,
        },
        { signal: run.signal },
      );

      if (activeRun.current !== run) {
        return;
      }

      setResponse(result);
      setSuggestionsExpanded(false);
    } catch (requestError) {
      // A stopped run has already returned the composer to idle, and a stop is
      // not a failure — rendering an error state for it would blame the
      // backend for something the user chose.
      if (activeRun.current !== run || isRequestCancelled(requestError)) {
        return;
      }

      setError(normalizeApiError(requestError));
    } finally {
      if (activeRun.current === run) {
        activeRun.current = null;
        setSubmitting(false);
      }
    }
  }

  async function stopRun() {
    const run = activeRun.current;
    if (!run || stopping) {
      return;
    }

    // Disowned before awaiting, not after: the server answers the abandoned
    // request at the same moment it frees the slot, so a late outcome must
    // already read as superseded by the time it lands. Stop means stop —
    // anything that arrives after the click is discarded, including a success.
    activeRun.current = null;

    // The server is asked to stop first and the composer only reopens once it
    // answers. Aborting locally is not enough: the graph keeps running, keeps
    // holding the single-flight slot, and the next question would collide
    // with it.
    let releaseComposer = true;
    setStopping(true);
    try {
      const result = await api.cancelRun();
      if (!result.idle) {
        releaseComposer = false;
        setWaitingForIdle(true);
        setError(runStillStoppingError());
      } else {
        setWaitingForIdle(false);
        setError(null);
      }
    } catch {
      // Best effort — a failed cancel must still release the composer rather
      // than strand the user in a state with no way out.
      setWaitingForIdle(false);
      setError(null);
    } finally {
      run.abort();
      setStopping(false);
      if (releaseComposer) {
        setSubmitting(false);
      }
    }
  }

  async function retryStopReadiness() {
    if (!waitingForIdle || stopping) {
      return;
    }

    let releaseComposer = true;
    setStopping(true);
    try {
      const result = await api.cancelRun();
      if (!result.idle) {
        releaseComposer = false;
        setError(runStillStoppingError());
      } else {
        setWaitingForIdle(false);
        setError(null);
      }
    } catch {
      // Preserve the best-effort escape hatch if readiness cannot be checked:
      // the user must not be left with a permanently locked UI.
      setWaitingForIdle(false);
      setError(null);
    } finally {
      setStopping(false);
      if (releaseComposer) {
        setSubmitting(false);
      }
    }
  }

  function updateQuestion(nextQuestion: string) {
    const isEmpty = nextQuestion.trim().length === 0;

    setQuestion(nextQuestion);
    // Feedback about the previous attempt stops being true the moment the
    // question changes, so it goes rather than lingering as stale alarm.
    setError(null);
    if (isEmpty) {
      setSuggestionsExpanded(true);
    }
  }

  function selectSuggestion(nextQuestion: string) {
    setQuestion(nextQuestion);
    setError(null);
  }

  const controlsUnavailable = statusLoading || !status || Boolean(status.config_error);
  const webSearchLocked = status?.web_search_locked === true;
  // The app-level banner already reports an unreachable backend; saying it a
  // second time here would present one outage as two problems.
  const visibleError =
    error && globalNoticeVisible && error.code === BACKEND_UNREACHABLE_CODE ? null : error;
  const hasOutcome = Boolean(response || visibleError);
  const showSuggestionCards = suggestionsExpanded;

  return (
    <div
      className={`ask-page ${hasOutcome ? "ask-page--answered" : "ask-page--idle"}`}
      hidden={hidden}
    >
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
                    value={webSearchLocked ? "runtime_locked" : (fallbackPolicy ?? "")}
                    onChange={(event) =>
                      setFallbackPolicy(asFallbackPolicy(event.target.value || null))
                    }
                    disabled={controlsUnavailable || webSearchLocked || submitting}
                  >
                    {webSearchLocked ? (
                      <option value="runtime_locked">Not applicable</option>
                    ) : (
                      <>
                        <option value="">Runtime default</option>
                        <option value="conservative">Conservative</option>
                        <option value="aggressive">Aggressive</option>
                        <option value="disabled">Disabled</option>
                      </>
                    )}
                  </select>
                </label>

                {webSearchLocked && <span className="lock-label">Locked by runtime policy</span>}
              </div>

              {/* One control, never two: while a run is in flight the primary
                  action becomes Stop, so the composer always offers a single
                  obvious next step. */}
              {submitting ? (
                <button
                  className="primary-button is-submitting"
                  type="button"
                  onClick={() => void (waitingForIdle ? retryStopReadiness() : stopRun())}
                  disabled={stopping}
                  aria-busy={true}
                >
                  <span className="stop-glyph" aria-hidden="true" />
                  {waitingForIdle
                    ? stopping
                      ? "Checking…"
                      : "Check again"
                    : stopping
                      ? "Stopping…"
                      : "Stop"}
                </button>
              ) : (
                <button
                  className="primary-button"
                  type="submit"
                  disabled={question.trim().length === 0}
                  aria-busy={false}
                >
                  Ask
                  <span aria-hidden="true">→</span>
                </button>
              )}
            </div>
          </form>

          <div className="ask-runtime-line">
            <span>Answers include citations and metadata-only execution details.</span>
          </div>

          {/* Feedback for pressing Ask sits with the composer, above the
              suggestions — at the foot of the page it landed below the fold,
              so the button appeared to do nothing. */}
          {visibleError && (
            <div className="ask-error" ref={errorRef}>
              <ErrorState
                error={visibleError}
                tone={isRetryableError(visibleError) ? "warning" : "danger"}
              />
            </div>
          )}

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
