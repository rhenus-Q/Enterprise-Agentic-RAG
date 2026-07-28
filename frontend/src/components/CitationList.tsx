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

function citationDomain(url: string): string | null {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

function shortSourceName(source: string): string {
  return source.split(/[\\/]/).pop() ?? source;
}

function displayCategory(category: string): string {
  if (category.trim().toLowerCase() === "hr") {
    return "HR";
  }

  return category
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function CitationIcon({ citation }: { citation: Citation }) {
  if (citation.kind === "local") {
    return (
      <span className="citation-kind-icon citation-kind-icon--local" aria-hidden="true">
        <svg viewBox="0 0 20 20">
          <path d="M5 2.75h6.25L15 6.5v10.75H5z" />
          <path d="M11.25 2.75V6.5H15M7.5 10h5M7.5 13h4" />
        </svg>
      </span>
    );
  }

  return (
    <span className="citation-kind-icon citation-kind-icon--web" aria-hidden="true">
      <svg viewBox="0 0 20 20">
        <circle cx="10" cy="10" r="6.5" />
        <path d="M3.5 10h13M10 3.5c2 1.8 3 4 3 6.5s-1 4.7-3 6.5c-2-1.8-3-4-3-6.5s1-4.7 3-6.5Z" />
      </svg>
    </span>
  );
}

export function CitationList({ citations }: CitationListProps) {
  if (citations.length === 0) {
    return null;
  }

  return (
    <section className="content-section" aria-labelledby="citations-heading">
      <div className="section-heading-row">
        <div>
          <p className="eyebrow">EVIDENCE USED</p>
          <h2 id="citations-heading">Sources</h2>
        </div>
        <span className="count-badge">{citations.length}</span>
      </div>

      <ol className="citation-list">
        {citations.map((citation, index) => {
          const title = citationTitle(citation);
          const domain = citation.url ? citationDomain(citation.url) : null;
          const filename = citation.source ? shortSourceName(citation.source) : null;

          return (
            <li
              className="citation-item citation-card"
              key={`${citation.kind}-${citation.source ?? citation.url ?? citation.query}-${index}`}
            >
              <div className="citation-title-row">
                <div className="citation-primary">
                  <span className="citation-number">{index + 1}</span>
                  <CitationIcon citation={citation} />
                  <strong className="citation-title">{title}</strong>
                </div>
                <span className={`source-kind source-kind--${citation.kind}`}>
                  {citation.kind === "local"
                    ? "Local"
                    : citation.kind === "web"
                      ? "Web"
                      : "Query"}
                </span>
              </div>

              {citation.snippet && <p className="citation-snippet">{citation.snippet}</p>}
              {citation.query && <p className="citation-snippet">“{citation.query}”</p>}

              <div className="citation-meta">
                {citation.document_category && (
                  <span>{displayCategory(citation.document_category)}</span>
                )}
                {citation.document_category && filename && (
                  <span className="citation-meta-separator" aria-hidden="true">
                    ·
                  </span>
                )}
                {filename && citation.source && (
                  <>
                    <span className="citation-filename" title={citation.source}>
                      {filename}
                    </span>
                    <span className="sr-only">Full source path: {citation.source}</span>
                  </>
                )}
                {domain && <span className="citation-domain">{domain}</span>}
                {domain && citation.url && (
                  <span className="citation-meta-separator" aria-hidden="true">
                    ·
                  </span>
                )}
                {citation.url && (
                  <a
                    className="citation-open-link"
                    href={citation.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    title={citation.url}
                    aria-label={`Open ${title} in new tab`}
                  >
                    Open <span aria-hidden="true">↗</span>
                  </a>
                )}
                {citation.kind === "web_query" && <span>Web search query</span>}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
