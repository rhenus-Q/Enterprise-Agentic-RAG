import type {
  AskResponse,
  DocumentsResponse,
  IndexCompatibility,
  IndexStatus,
  RunDetail,
  RunsResponse,
  RuntimeStatus,
} from "../api/types";

const openAiFingerprint = {
  embedding_provider: "openai",
  embedding_model: "text-embedding-ada-002",
};

const localFingerprint = {
  embedding_provider: "ollama",
  embedding_model: "qwen3-embedding:0.6b",
};

export const indexFixtures: Record<IndexCompatibility, IndexStatus> = {
  compatible: {
    persist_directory: "chroma_db",
    collection_name: "agentic_rag_docs",
    exists: true,
    stored_fingerprint: openAiFingerprint,
    expected_fingerprint: openAiFingerprint,
    compatibility: "compatible",
    reindex_required: false,
  },
  legacy_no_fingerprint: {
    persist_directory: "chroma_db",
    collection_name: "agentic_rag_docs",
    exists: true,
    stored_fingerprint: null,
    expected_fingerprint: openAiFingerprint,
    compatibility: "legacy_no_fingerprint",
    reindex_required: false,
  },
  provider_mismatch: {
    persist_directory: "chroma_db",
    collection_name: "agentic_rag_docs",
    exists: true,
    stored_fingerprint: localFingerprint,
    expected_fingerprint: openAiFingerprint,
    compatibility: "provider_mismatch",
    reindex_required: true,
  },
  model_mismatch: {
    persist_directory: "chroma_db_local",
    collection_name: "agentic_rag_docs_local",
    exists: true,
    stored_fingerprint: {
      embedding_provider: "ollama",
      embedding_model: "nomic-embed-text",
    },
    expected_fingerprint: localFingerprint,
    compatibility: "model_mismatch",
    reindex_required: true,
  },
  missing_index: {
    persist_directory: "chroma_db_local",
    collection_name: "agentic_rag_docs_local",
    exists: false,
    stored_fingerprint: null,
    expected_fingerprint: localFingerprint,
    compatibility: "missing_index",
    reindex_required: true,
  },
};

const baseRuntimeStatus: RuntimeStatus = {
  provider: "openai",
  chat_model: "gpt-5-mini",
  embedding_provider: "openai",
  embedding_model: "text-embedding-ada-002",
  privacy_mode: false,
  fully_local_mode: false,
  web_search_enabled_default: true,
  web_search_locked: false,
  web_fallback_policy_default: "conservative",
  budgets: {
    max_llm_calls_per_run: 30,
    max_web_searches_per_run: 5,
    max_web_results_to_grade: 15,
  },
  llm_request_timeout_seconds: 60,
  index: indexFixtures.compatible,
  preflight: { ok: true, message: null },
  config_error: null,
};

export const runtimeFixtures = {
  openai: baseRuntimeStatus,
  privacy: {
    ...baseRuntimeStatus,
    privacy_mode: true,
    web_search_enabled_default: false,
    web_search_locked: true,
  } satisfies RuntimeStatus,
  local: {
    ...baseRuntimeStatus,
    provider: "ollama",
    chat_model: "qwen3:4b-instruct-2507-q4_K_M",
    embedding_provider: "ollama",
    embedding_model: "qwen3-embedding:0.6b",
    fully_local_mode: true,
    web_search_enabled_default: false,
    web_search_locked: true,
    index: {
      ...indexFixtures.compatible,
      persist_directory: "chroma_db_local",
      collection_name: "agentic_rag_docs_local",
      stored_fingerprint: localFingerprint,
      expected_fingerprint: localFingerprint,
    },
  } satisfies RuntimeStatus,
  preflightFailed: {
    ...baseRuntimeStatus,
    preflight: {
      ok: false,
      message: "Startup preflight failed — see the server console for details.",
    },
  } satisfies RuntimeStatus,
  configError: {
    provider: null,
    chat_model: null,
    embedding_provider: null,
    embedding_model: null,
    privacy_mode: null,
    fully_local_mode: null,
    web_search_enabled_default: null,
    web_search_locked: null,
    web_fallback_policy_default: null,
    budgets: null,
    llm_request_timeout_seconds: null,
    index: null,
    preflight: { ok: true, message: null },
    config_error: "Invalid LLM_PROVIDER value 'bogus'.",
  } satisfies RuntimeStatus,
};

const baseAskResponse: AskResponse = {
  run_id: "run_01HV7P9F6G",
  question: "What is the reimbursement window for business expenses?",
  input_redacted: false,
  question_sha256: "f3d3a81d9ed2719f7797c8ba11a91f5f61c48880856350396fe123532b37fb68",
  answer:
    "Employees should submit business expenses within 30 days of the purchase. Receipts are required for expenses above $25, and manager approval is required before Finance processes the reimbursement.",
  caveat: null,
  stop_reason: "",
  status: "ok",
  citations: [
    {
      kind: "local",
      title: "Expense Reimbursement Policy",
      source: "data/acmecorp_internal_docs/expense_reimbursement_policy.md",
      url: null,
      document_category: "finance",
      query: null,
      snippet:
        "Employees must submit reimbursable business expenses within 30 calendar days of purchase. Itemized receipts are required for expenses over $25.",
    },
    {
      kind: "local",
      title: "Employee Onboarding Guide",
      source: "data/acmecorp_internal_docs/employee_onboarding_guide.md",
      url: null,
      document_category: "hr",
      query: null,
      snippet:
        "New employees receive access to the expense platform during their first week and should route approvals through their direct manager.",
    },
  ],
  source_lines: [
    "- Local corpus: Expense Reimbursement Policy",
    "- Local corpus: Employee Onboarding Guide",
  ],
  node_path: ["retrieve", "grade_documents", "generate"],
  node_timings_ms: [
    { node: "retrieve", duration_ms: 184.7 },
    { node: "grade_documents", duration_ms: 612.3 },
    { node: "generate", duration_ms: 1048.9 },
  ],
  total_duration_ms: 1845.9,
  retries: 0,
  tracked_llm_calls: 1,
  web_search_count: 0,
  web_result_grading_count: 0,
  runtime: {
    provider: "openai",
    web_search_enabled: true,
    web_fallback_policy: "conservative",
  },
};

function caveatFixture(
  runId: string,
  stopReason: string,
  caveat: string,
  answer = baseAskResponse.answer,
): AskResponse {
  return {
    ...baseAskResponse,
    run_id: runId,
    answer,
    caveat,
    stop_reason: stopReason,
    status: "caveat",
  };
}

export const askFixtures = {
  localSuccess: baseAskResponse,
  webSuccess: {
    ...baseAskResponse,
    run_id: "run_01HV7Q2R8W",
    question: "What changed recently in remote-access security guidance?",
    answer:
      "The internal VPN policy still requires managed devices and phishing-resistant MFA. Recent public guidance also emphasizes continuous device posture checks and shorter session lifetimes for privileged access.",
    citations: [
      {
        kind: "local",
        title: "VPN Access Policy",
        source: "data/acmecorp_internal_docs/vpn_policy.md",
        url: null,
        document_category: "it_security",
        query: null,
        snippet:
          "Remote access requires an enrolled company device, phishing-resistant MFA, and an approved VPN profile.",
      },
      {
        kind: "web",
        title: "Zero Trust Architecture",
        source: null,
        url: "https://www.nist.gov/publications/zero-trust-architecture",
        document_category: null,
        query: null,
        snippet: null,
      },
      {
        kind: "web",
        title: "CISA Zero Trust Maturity Model",
        source: null,
        url: "https://www.cisa.gov/resources-tools/resources/zero-trust-maturity-model",
        document_category: null,
        query: null,
        snippet: null,
      },
      {
        kind: "web_query",
        title: null,
        source: null,
        url: null,
        document_category: null,
        query: "current remote access zero trust guidance",
        snippet: null,
      },
    ],
    source_lines: [
      "- Local corpus: VPN Access Policy",
      "- Web search: Zero Trust Architecture — https://www.nist.gov/publications/zero-trust-architecture",
      "- Web search: CISA Zero Trust Maturity Model — https://www.cisa.gov/resources-tools/resources/zero-trust-maturity-model",
    ],
    node_path: ["retrieve", "grade_documents", "websearch", "generate"],
    node_timings_ms: [
      { node: "retrieve", duration_ms: 176.2 },
      { node: "grade_documents", duration_ms: 574.5 },
      { node: "websearch", duration_ms: 821.8 },
      { node: "generate", duration_ms: 1218.4 },
    ],
    total_duration_ms: 2790.9,
    tracked_llm_calls: 4,
    web_search_count: 1,
    web_result_grading_count: 3,
  } satisfies AskResponse,
  webSearchDisabled: caveatFixture(
    "run_01HV7Q8P2D",
    "web_search_disabled",
    "Note: Web search is disabled, so I could only use the local knowledge base. I may not have enough information to fully answer this question.",
  ),
  webFallbackDisabled: caveatFixture(
    "run_01HV7QAT4S",
    "web_fallback_disabled",
    "Note: Web fallback is disabled by policy, so I answered only from the local knowledge base. The answer may not fully address your question.",
  ),
  maxRetriesNotGrounded: {
    ...caveatFixture(
      "run_01HV7QEC7N",
      "max_retries_not_grounded",
      "Warning: This answer did not pass the grounding (anti-hallucination) check after the retry limit was reached. It may contain information that is not supported by the source documents, so do not treat it as fully reliable.",
    ),
    retries: 5,
    total_duration_ms: 8129.4,
  } satisfies AskResponse,
  budgetExhausted: {
    ...caveatFixture(
      "run_01HV7QGZ1M",
      "budget_exhausted",
      "Note: This answer stopped because the per-run cost/latency budget was reached. The answer may be incomplete or not fully verified.",
    ),
    tracked_llm_calls: 30,
    total_duration_ms: 12384.5,
  } satisfies AskResponse,
  generationError: {
    ...caveatFixture(
      "run_01HV7QKJ5B",
      "generation_error",
      "Note: The language model call failed before a reliable answer could be generated. Please try again.",
      "A reliable answer could not be generated for this request.",
    ),
    status: "error",
  } satisfies AskResponse,
  redacted: {
    ...baseAskResponse,
    run_id: "run_01HV7QPN9V",
    question: "Can I include api_key=[REDACTED] in a support ticket?",
    input_redacted: true,
  } satisfies AskResponse,
};

const documents = [
  {
    source: "data/acmecorp_internal_docs/data_retention_policy.md",
    file_name: "data_retention_policy.md",
    title: "Data Retention Policy",
    document_category: "compliance",
    source_type: "local_corpus",
    size_bytes: 6284,
    modified_at: "2026-07-18T14:22:10Z",
  },
  {
    source: "data/acmecorp_internal_docs/employee_onboarding_guide.md",
    file_name: "employee_onboarding_guide.md",
    title: "Employee Onboarding Guide",
    document_category: "hr",
    source_type: "local_corpus",
    size_bytes: 5142,
    modified_at: "2026-07-18T14:22:10Z",
  },
  {
    source: "data/acmecorp_internal_docs/expense_reimbursement_policy.md",
    file_name: "expense_reimbursement_policy.md",
    title: "Expense Reimbursement Policy",
    document_category: "finance",
    source_type: "local_corpus",
    size_bytes: 4808,
    modified_at: "2026-07-18T14:22:10Z",
  },
  {
    source: "data/acmecorp_internal_docs/incident_response_playbook.md",
    file_name: "incident_response_playbook.md",
    title: "Incident Response Playbook",
    document_category: "it_security",
    source_type: "local_corpus",
    size_bytes: 7731,
    modified_at: "2026-07-18T14:22:10Z",
  },
  {
    source: "data/acmecorp_internal_docs/on_call_escalation_policy.md",
    file_name: "on_call_escalation_policy.md",
    title: "On-Call Escalation Policy",
    document_category: "operations",
    source_type: "local_corpus",
    size_bytes: 3996,
    modified_at: "2026-07-18T14:22:10Z",
  },
  {
    source: "data/acmecorp_internal_docs/vpn_policy.md",
    file_name: "vpn_policy.md",
    title: "VPN Access Policy",
    document_category: "it_security",
    source_type: "local_corpus",
    size_bytes: 4516,
    modified_at: "2026-07-18T14:22:10Z",
  },
];

export function documentsResponseFor(index: IndexStatus): DocumentsResponse {
  return {
    documents,
    document_count: documents.length,
    index,
    config_error: null,
  };
}

export const populatedDocumentsResponse = documentsResponseFor(indexFixtures.compatible);

const runSummaries: RunsResponse["runs"] = [
  {
    run_id: "run_01HV7Q2R8W",
    generated_at: "2026-07-26T18:42:18Z",
    question_redacted: "What changed recently in remote-access security guidance?",
    status: "ok",
    stop_reason: "",
    total_duration_ms: 2790.9,
    provider: "openai",
    retries: 0,
    web_search_count: 1,
  },
  {
    run_id: "run_01HV7QGZ1M",
    generated_at: "2026-07-26T18:37:04Z",
    question_redacted: "Summarize the current incident escalation process.",
    status: "caveat",
    stop_reason: "budget_exhausted",
    total_duration_ms: 12384.5,
    provider: "openai",
    retries: 3,
    web_search_count: 1,
  },
  {
    run_id: "run_01HV7QKJ5B",
    generated_at: "2026-07-26T18:31:52Z",
    question_redacted: "What is the retention rule for security event logs?",
    status: "error",
    stop_reason: "generation_error",
    total_duration_ms: 972.2,
    // Provider is a process-level mode and history is per-process, so a single
    // session can never mix providers. Local mode is demonstrated through the
    // runtime-mode scenarios instead.
    provider: "openai",
    retries: 0,
    web_search_count: 0,
  },
];

export const populatedRunsResponse: RunsResponse = {
  runs: runSummaries,
  count: runSummaries.length,
  limit: 50,
};

export const emptyRunsResponse: RunsResponse = {
  runs: [],
  count: 0,
  limit: 50,
};

export const runDetailFixtures: Record<string, RunDetail> = {
  run_01HV7Q2R8W: {
    ...runSummaries[0],
    question_sha256: "3ad6045ff8cb9dfc93815672d18822bb8c7321e4d7313e083c379e9df3f7bbda",
    input_redacted: false,
    node_path: ["retrieve", "grade_documents", "websearch", "generate"],
    node_timings_ms: [
      { node: "retrieve", duration_ms: 176.2 },
      { node: "grade_documents", duration_ms: 574.5 },
      { node: "websearch", duration_ms: 821.8 },
      { node: "generate", duration_ms: 1218.4 },
    ],
    counters: {
      retries: 0,
      tracked_llm_calls: 4,
      web_search_count: 1,
      web_result_grading_count: 3,
    },
    web_search_enabled: true,
    web_fallback_policy: "conservative",
    sources: askFixtures.webSuccess.source_lines,
  },
  run_01HV7QGZ1M: {
    ...runSummaries[1],
    question_sha256: "861c85bbbff9bc1778c9a26b31e314e4d92b968ee7c4e9fd16960ef3f45f60c7",
    input_redacted: false,
    node_path: [
      "retrieve",
      "grade_documents",
      "generate",
      "add_grounding_feedback",
      "generate",
      "budget_exhausted_notice",
    ],
    node_timings_ms: [
      { node: "retrieve", duration_ms: 203.1 },
      { node: "grade_documents", duration_ms: 631.9 },
      { node: "generate", duration_ms: 2214.2 },
      { node: "add_grounding_feedback", duration_ms: 688.4 },
      { node: "generate", duration_ms: 3982.5 },
      { node: "budget_exhausted_notice", duration_ms: 25.3 },
    ],
    counters: {
      retries: 3,
      tracked_llm_calls: 30,
      web_search_count: 1,
      web_result_grading_count: 3,
    },
    web_search_enabled: true,
    web_fallback_policy: "conservative",
    sources: ["- Local corpus: Incident Response Playbook"],
  },
  run_01HV7QKJ5B: {
    ...runSummaries[2],
    question_sha256: "f1d9c3d26ff7583a15f35b0556b82d7d0d79dbb9ba8157a962139bb4de11aa82",
    input_redacted: false,
    node_path: ["retrieve", "grade_documents", "generate"],
    node_timings_ms: [
      { node: "retrieve", duration_ms: 144.8 },
      { node: "grade_documents", duration_ms: 731.2 },
      { node: "generate", duration_ms: 96.2 },
    ],
    counters: {
      retries: 0,
      tracked_llm_calls: 1,
      web_search_count: 0,
      web_result_grading_count: 0,
    },
    web_search_enabled: false,
    web_fallback_policy: "disabled",
    sources: ["- Local corpus: Data Retention Policy"],
  },
};
