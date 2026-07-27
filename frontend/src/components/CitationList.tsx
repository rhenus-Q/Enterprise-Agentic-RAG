import type { Citation } from "../api/types";

interface CitationListProps {
  citations: Citation[];
}

function citationTitle(citation: Citation): string {
  if (citation.kind === "web_query") {
    return "Web search query";
  }
  return citation.title ?? (citation.kind === "local" ? "Local corpus document" : "Web source");
}

export function CitationList({ citations }: CitationListProps) {
  if (citations.length === 0) {
    return null;
  }

  return (
    <section className="content-section" aria-labelledby="citations-heading">
      <div className="section-heading-row">
        <div>
          <p className="eyebrow">Evidence used</p>
          <h2 id="citations-heading">Sources</h2>
        </div>
        <span className="count-badge">{citations.length}</span>
      </div>

      <ol className="citation-list">
        {citations.map((citation, index) => (
          <li
            className="citation-item"
            key={`${citation.kind}-${citation.source ?? citation.url ?? citation.query}-${index}`}
          >
            <span className="citation-number">{index + 1}</span>
            <div className="citation-content">
              <div className="citation-title-row">
                {citation.url ? (
                  <a href={citation.url} target="_blank" rel="noreferrer">
                    {citationTitle(citation)}
                  </a>
                ) : (
                  <strong>{citationTitle(citation)}</strong>
                )}
                <span className="source-kind">
                  {citation.kind === "local"
                    ? "Local"
                    : citation.kind === "web"
                      ? "Web"
                      : "Query"}
                </span>
              </div>
              {citation.snippet && <p className="citation-snippet">{citation.snippet}</p>}
              {citation.query && <p className="citation-query">“{citation.query}”</p>}
              <div className="citation-meta">
                {citation.document_category && <span>{citation.document_category}</span>}
                {citation.source && <code>{citation.source}</code>}
                {citation.url && <span className="truncate-text">{citation.url}</span>}
              </div>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
