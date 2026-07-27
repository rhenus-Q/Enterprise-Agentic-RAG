import type { AskResponse } from "../api/types";
import { StatusPill } from "./StatusPill";

interface AnswerCardProps {
  response: AskResponse;
}

export function AnswerCard({ response }: AnswerCardProps) {
  return (
    <article className="answer-card" aria-labelledby="answer-heading">
      <div className="section-heading-row">
        <div>
          <p className="eyebrow">Knowledge answer</p>
          <h2 id="answer-heading">Answer</h2>
        </div>
        <StatusPill status={response.status} />
      </div>

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
        <div className="notice notice--warning" role="alert">
          <strong>Answer caveat</strong>
          <span>{response.caveat}</span>
        </div>
      )}

      <div className="answer-footer">
        <span>Run {response.run_id}</span>
        <span>{response.total_duration_ms.toLocaleString()} ms</span>
      </div>
    </article>
  );
}
