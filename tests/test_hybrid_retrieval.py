"""Unit tests for lightweight lexical scoring used by hybrid retrieval."""

from backend.tools.doc_search.retriever.document_retriever import (
    _lexical_score,
    _lexical_terms,
)


def test_lexical_terms_remove_common_question_words() -> None:
    """Verify normalized terms retain technical concepts rather than boilerplate.

    Returns:
        None.
    """
    terms = _lexical_terms(
        "What material concerns apply to cryogenic disconnects and shrinkage?"
    )

    assert "what" not in terms
    assert "material" not in terms
    assert {"cryogenic", "disconnects", "shrinkage"} <= terms


def test_lexical_score_prefers_decisive_technical_passage() -> None:
    """Verify rare query terms promote the directly responsive source passage.

    Returns:
        None.
    """
    query_terms = _lexical_terms(
        "cryogenic disconnects shrinkage sealing latching releasing mechanisms"
    )
    decisive = (
        "For cryogenic disconnects consider different shrinkage rates in sealing, "
        "latching, and releasing mechanisms."
    )
    tangential = "A general discussion of elastomer lubrication and contamination."

    assert _lexical_score(query_terms, decisive) > _lexical_score(query_terms, tangential)
