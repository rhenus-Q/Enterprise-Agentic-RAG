import { formatDuration } from "../lib/format";
import type { AskResponse } from "../api/types";
import { RuntimeBadge } from "./RuntimeBadge";
import { StatusPill } from "./StatusPill";

interface AnswerCardProps {
  response: AskResponse;
}

const PROFILE_LABELS: Record<AskResponse["effective_profile"], string> = {
  legacy: "Legacy",
  luna_all: "Luna All",
  flash_luna: "Flash + Luna",
  local: "Local",
};

export function AnswerCard({ response }: AnswerCardProps) {
  const totalTime = formatDuration(response.total_duration_ms);

  return (
    <article className="answer-card" aria-labelledby="answer-heading">
      <header className="answer-card__header">
        <div>
          <p className="eyebrow">KNOWLEDGE ANSWER</p>
          <h2 id="answer-heading">Answer</h2>
        </div>
        <StatusPill status={response.status} />
      </header>

      {response.input_redacted && (
        <div className="notice notice--private" role="status">
          Sensitive-looking text was redacted before this question entered the workflow.
        </div>
      )}

      <div className="answer-copy">
        {response.answer.split("\n").map((paragraph, index) => (
          <p key={`${paragraph.slice(0, 16)}-${index}`}>{paragraph}</p>
        ))}
      </div>

      {response.status !== "ok" && response.caveat && (
        <div
          className={`notice ${
            response.status === "error" ? "notice--danger" : "notice--warning"
          }`}
          role="alert"
        >
          <strong>Answer caveat</strong>
          <span>{response.caveat}</span>
        </div>
      )}

      <footer className="answer-footer">
        <RuntimeBadge runtime={response.runtime} />
        <span className="answer-footer__run" aria-label={`Run ID: ${response.run_id}`}>
          Run ID: {response.run_id}
        </span>
        <span className="runtime-badge answer-footer__profile">
          <span>{PROFILE_LABELS[response.effective_profile]}</span>
        </span>
        <span className="answer-footer__duration" aria-label={`Total time: ${totalTime}`}>
          Total time: {totalTime}
        </span>
      </footer>
    </article>
  );
}
