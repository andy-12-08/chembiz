"""Validate the draft chemical-engineering benchmark's internal consistency."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parents[1]


def _sha256(path: Path) -> str:
    """Calculate the SHA-256 digest of a local benchmark source.

    Args:
        path: Source file whose bytes should be hashed.

    Returns:
        Lowercase hexadecimal SHA-256 digest.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(name: str) -> dict[str, Any]:
    """Load one benchmark JSON object.

    Args:
        name: Filename relative to the benchmark directory.

    Returns:
        Parsed JSON object.

    Raises:
        ValueError: The file's root value is not an object.
    """
    value = json.loads((ROOT / name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{name} must contain a JSON object")
    return value


def validate() -> list[str]:
    """Return all dataset consistency errors.

    Returns:
        Human-readable validation errors; an empty list means valid.
    """
    errors: list[str] = []
    questions = _load_json("questions.json").get("questions") or []
    evidence = _load_json("expected_evidence.json").get("items") or []
    split = _load_json("split.json")

    with (ROOT / "source_manifest.csv").open(encoding="utf-8", newline="") as handle:
        source_rows = list(csv.DictReader(handle))

    question_ids = [str(row.get("id") or "") for row in questions]
    evidence_ids = [str(row.get("question_id") or "") for row in evidence]
    source_ids = {str(row.get("source_id") or "") for row in source_rows}
    development_ids = [str(value) for value in split.get("development_ids") or []]
    held_out_ids = [str(value) for value in split.get("held_out_ids") or []]

    if len(question_ids) != len(set(question_ids)):
        errors.append("questions.json contains duplicate IDs")
    if len(evidence_ids) != len(set(evidence_ids)):
        errors.append("expected_evidence.json contains duplicate question IDs")
    if set(question_ids) != set(evidence_ids):
        errors.append("question and expected-evidence ID sets differ")
    if set(development_ids) & set(held_out_ids):
        errors.append("development and held-out splits overlap")
    if set(development_ids) | set(held_out_ids) != set(question_ids):
        errors.append("split IDs do not form an exact partition of the questions")

    for source in source_rows:
        source_id = str(source.get("source_id") or "<missing source_id>")
        relative_path = str(source.get("local_file") or "")
        expected_hash = str(source.get("sha256") or "").lower()
        if not relative_path:
            errors.append(f"{source_id} has no local source path")
            continue
        source_path = PROJECT_ROOT / relative_path
        if not source_path.is_file():
            errors.append(f"{source_id} source file is missing: {relative_path}")
            continue
        if not expected_hash:
            errors.append(f"{source_id} has no recorded SHA-256 digest")
            continue
        actual_hash = _sha256(source_path)
        if actual_hash != expected_hash:
            errors.append(
                f"{source_id} SHA-256 mismatch: expected {expected_hash}, "
                f"found {actual_hash}"
            )

    for question in questions:
        unknown = set(question.get("required_source_ids") or []) - source_ids
        if unknown:
            errors.append(f"{question.get('id')} references unknown sources: {sorted(unknown)}")
    for item in evidence:
        if not item.get("locator"):
            errors.append(f"{item.get('question_id')} has no source locator")
        if not item.get("required_evidence"):
            errors.append(f"{item.get('question_id')} has no required evidence")

    return errors


def main() -> int:
    """Print validation results and return a process exit code.

    Returns:
        Zero for a valid dataset, otherwise one.
    """
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Benchmark structure is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
