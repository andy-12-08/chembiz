"""Find page-level passages in the frozen chemical-engineering PDF corpus."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pymupdf


def find_passages(pdf_path: Path, phrase: str, context_chars: int) -> list[tuple[int, str]]:
    """Find case-insensitive phrase matches and return compact page excerpts.

    Args:
        pdf_path: PDF file to inspect.
        phrase: Literal phrase to locate, matched case-insensitively.
        context_chars: Characters retained on each side of a match.

    Returns:
        Tuples containing one-based PDF page numbers and normalized excerpts.
    """
    needle = phrase.casefold()
    matches: list[tuple[int, str]] = []
    with pymupdf.open(pdf_path) as document:
        for page_index, page in enumerate(document):
            text = page.get_text("text")
            folded = text.casefold()
            offset = folded.find(needle)
            if offset < 0:
                continue
            start = max(0, offset - context_chars)
            end = min(len(text), offset + len(phrase) + context_chars)
            excerpt = " ".join(text[start:end].split())
            matches.append((page_index + 1, excerpt))
    return matches


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed argument namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("phrase")
    parser.add_argument("--context-chars", type=int, default=500)
    return parser.parse_args()


def main() -> int:
    """Print matching pages and excerpts.

    Returns:
        Zero when at least one match is found, otherwise one.
    """
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = _parse_args()
    matches = find_passages(args.pdf, args.phrase, args.context_chars)
    for page_number, excerpt in matches:
        print(f"PDF page {page_number}: {excerpt}")
    return 0 if matches else 1


if __name__ == "__main__":
    raise SystemExit(main())
