"""Helpers for retaining source-page markers through token-window chunking."""

from __future__ import annotations

import re

_PAGE_MARKER = re.compile(r"\[page\s+(\d+)\]", re.IGNORECASE)


def pages_for_chunk(chunk_text: str, previous_page: int | None) -> tuple[list[int], int | None]:
    """Return ordered page numbers represented by a chunk and the latest page seen.

    Token windows overlap and may begin after the page marker. In that case the
    latest page from the previous window is retained. Explicit markers in the
    current window then extend or replace that context.

    Args:
        chunk_text: Retrieved chunk text that may contain ``[page N]`` markers.
        previous_page: Most recent page observed in the preceding token window.

    Returns:
        A pair containing ordered pages represented by the chunk and the latest
        page available for the next overlapping window.
    """
    explicit = [int(value) for value in _PAGE_MARKER.findall(chunk_text)]
    pages: list[int] = []
    if previous_page is not None:
        pages.append(previous_page)
    for page in explicit:
        if page not in pages:
            pages.append(page)
    latest = explicit[-1] if explicit else previous_page
    return pages, latest
