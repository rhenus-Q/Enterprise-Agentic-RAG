from graph.chains.retrieval_grader import get_retrieval_grader
from graph.consts import STOP_REASON_TOOL_ERROR
from graph.state import GraphState


def grade_documents(state: GraphState):
    """
    Grade the relevance of documents returned by retrieve.
    Keep relevant documents; if any document is not relevant, set
    web_search=True so the workflow falls back to web search.

    A grader failure is treated conservatively, like "not relevant": the
    ungraded document is dropped (unvetted content never reaches generation)
    and the web-search fallback is requested. stop_reason records the tool
    failure so the final answer carries an honest caveat — but only when no
    reason is recorded yet: a transient grading failure must never overwrite a
    durable one (retrieval_error / web_search_error), which reports that a
    whole evidence source was unavailable and survives to the end of the run.
    """

    print("---GRADE DOCUMENTS---")

    question = state["question"]
    documents = state["documents"]

    filtered_docs = []
    # Preserve an incoming fallback request (retrieve sets web_search=True
    # when the retriever itself failed); grading can add reasons to search
    # the web, never remove them.
    web_search = state.get("web_search", False)
    grading_error = False

    for doc in documents:
        try:
            score = get_retrieval_grader().invoke(
                {
                    "question": question,
                    "document": doc.page_content,
                }
            )
            grade = score.is_relevant
        except Exception as exc:
            # Log only the exception type: messages may carry secrets.
            print(
                f"---DOCUMENT GRADING FAILED ({type(exc).__name__}): DROPPING UNGRADED DOCUMENT---"
            )
            grading_error = True
            web_search = True
            continue

        if grade:
            print("---DOCUMENT RELEVANT---")
            filtered_docs.append(doc)
        else:
            print("---DOCUMENT NOT RELEVANT---")
            web_search = True

    result = {
        "question": question,
        "documents": filtered_docs,
        "web_search": web_search,
    }
    # Only write stop_reason on failure, and only when none is recorded yet:
    # a normal pass must not clobber a reason recorded by an earlier node, and
    # neither must a transient grading failure. tool_error is the weakest
    # reason in the vocabulary (it is even cleared again on a fully successful
    # answer), so overwriting a durable retrieval_error / web_search_error with
    # it would downgrade the caveat the user sees to a lesser, wrong one.
    if grading_error and not state.get("stop_reason"):
        result["stop_reason"] = STOP_REASON_TOOL_ERROR
    return result
