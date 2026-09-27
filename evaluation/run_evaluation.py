"""Run frozen ChemBiz evaluation questions through the local HTTP API."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TERMINAL_STATUSES = {"succeeded", "failed"}


def _request_json(
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send one JSON API request and decode its object response.

    Args:
        method: HTTP method such as GET or POST.
        url: Absolute endpoint URL.
        body: Optional JSON request object.

    Returns:
        Decoded JSON response object.

    Raises:
        RuntimeError: The request fails or the response is not a JSON object.
    """
    encoded = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Accept": "application/json"}
    if encoded is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url=url, data=encoded, headers=headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            value = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} returned HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError(f"{method} {url} failed: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{method} {url} returned a non-object JSON response")
    return value


def _load_questions(path: Path, selected_ids: set[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Load the frozen dataset and optionally filter it by question ID.

    Args:
        path: Path to questions.json.
        selected_ids: IDs to retain; an empty set selects every question.

    Returns:
        Dataset metadata and the selected question objects in file order.

    Raises:
        ValueError: A requested ID is absent or the dataset has no selected questions.
    """
    dataset = json.loads(path.read_text(encoding="utf-8"))
    questions = dataset.get("questions") or []
    available = {str(item.get("id")) for item in questions}
    missing = selected_ids - available
    if missing:
        raise ValueError(f"Unknown question IDs: {', '.join(sorted(missing))}")
    selected = [item for item in questions if not selected_ids or item.get("id") in selected_ids]
    if not selected:
        raise ValueError("No evaluation questions were selected")
    return dataset, selected


def _write_json(path: Path, payload: dict[str, Any], overwrite: bool) -> None:
    """Persist one formatted JSON artifact without silently replacing a prior run.

    Args:
        path: Destination file.
        payload: JSON object to serialize.
        overwrite: Whether an existing file may be replaced.

    Returns:
        None.

    Raises:
        FileExistsError: The path exists and overwrite is false.
    """
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing result: {path}")
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _poll_run(
    base_url: str,
    run_id: str,
    poll_seconds: float,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Poll one run until it succeeds, fails, or exceeds the timeout.

    Args:
        base_url: ChemBiz API base URL.
        run_id: Run identifier returned by POST /runs/.
        poll_seconds: Delay between status checks.
        timeout_seconds: Maximum polling duration.

    Returns:
        Terminal run response.

    Raises:
        TimeoutError: The run does not reach a terminal state in time.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        run = _request_json("GET", f"{base_url}/runs/{run_id}")
        if run.get("status") in TERMINAL_STATUSES:
            return run
        time.sleep(poll_seconds)
    raise TimeoutError(f"Run {run_id} did not finish within {timeout_seconds:g} seconds")


def run_question(
    base_url: str,
    user_id: str,
    question: dict[str, Any],
    output_dir: Path,
    poll_seconds: float,
    timeout_seconds: float,
    overwrite: bool,
) -> dict[str, Any]:
    """Create a session, execute one frozen question, and save both API artifacts.

    Args:
        base_url: ChemBiz API base URL.
        user_id: Dedicated evaluation user whose corpus is already indexed.
        question: Frozen question object containing id and question text.
        output_dir: Directory for run and output JSON files.
        poll_seconds: Delay between run-status requests.
        timeout_seconds: Per-question run timeout.
        overwrite: Whether existing artifacts may be replaced.

    Returns:
        Small execution summary containing IDs and terminal status.
    """
    question_id = str(question["id"])
    run_path = output_dir / f"{question_id}.run.json"
    output_path = output_dir / f"{question_id}.output.json"
    if not overwrite and (run_path.exists() or output_path.exists()):
        raise FileExistsError(f"Results already exist for {question_id} in {output_dir}")

    session = _request_json(
        "POST",
        f"{base_url}/sessions/",
        {"user_id": user_id, "user_query": str(question["question"])},
    )
    session_id = str(session["session_id"])
    started = _request_json(
        "POST",
        f"{base_url}/runs/",
        {"session_id": session_id, "user_id": user_id},
    )
    run_id = str(started["run_id"])
    try:
        terminal = _poll_run(base_url, run_id, poll_seconds, timeout_seconds)
    except TimeoutError as exc:
        terminal = _request_json("GET", f"{base_url}/runs/{run_id}")
        terminal["client_timeout"] = str(exc)
        _write_json(run_path, terminal, overwrite)
        return {
            "question_id": question_id,
            "session_id": session_id,
            "run_id": run_id,
            "status": "client_timeout",
        }
    _write_json(run_path, terminal, overwrite)

    if terminal.get("status") == "succeeded":
        output = _request_json("GET", f"{base_url}/runs/{run_id}/output")
        _write_json(output_path, output, overwrite)

    return {
        "question_id": question_id,
        "session_id": session_id,
        "run_id": run_id,
        "status": terminal.get("status"),
    }


def _parse_args() -> argparse.Namespace:
    """Parse command-line options for a local evaluation batch.

    Returns:
        Parsed command-line namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--user-id", default="chembiz-eval-v0.1.0")
    parser.add_argument(
        "--questions",
        type=Path,
        default=Path(__file__).with_name("questions.json"),
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--question-id",
        action="append",
        default=[],
        help="Question ID to run; repeat for multiple IDs. Defaults to all questions.",
    )
    parser.add_argument("--poll-seconds", type=float, default=3.0)
    parser.add_argument("--timeout-seconds", type=float, default=900.0)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    """Run the requested frozen evaluation batch and write a batch manifest.

    Returns:
        Process exit code: zero when every selected run succeeds, otherwise one.
    """
    args = _parse_args()
    base_url = args.base_url.rstrip("/")
    dataset, questions = _load_questions(args.questions, set(args.question_id))
    args.output_dir.mkdir(parents=True, exist_ok=True)

    health = _request_json("GET", f"{base_url}/health")
    if health.get("status") != "ok":
        raise RuntimeError(f"ChemBiz health check did not return ok: {health}")

    results: list[dict[str, Any]] = []
    for question in questions:
        question_id = str(question["id"])
        print(f"Running {question_id}...", flush=True)
        result = run_question(
            base_url=base_url,
            user_id=args.user_id,
            question=question,
            output_dir=args.output_dir,
            poll_seconds=args.poll_seconds,
            timeout_seconds=args.timeout_seconds,
            overwrite=args.overwrite,
        )
        results.append(result)
        print(f"{question_id}: {result['status']}", flush=True)

    manifest = {
        "dataset": dataset.get("dataset"),
        "dataset_version": dataset.get("version"),
        "run_started_from_client_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "user_id": args.user_id,
        "results": results,
    }
    _write_json(args.output_dir / "batch-manifest.json", manifest, args.overwrite)
    return 0 if all(item.get("status") == "succeeded" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
