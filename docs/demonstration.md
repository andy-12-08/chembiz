# ChemBiz v0.1.0 demonstration record

This document is a reproducible, text-based demonstration record. It links to preserved machine-readable evidence instead of presenting a staged interface screenshot.

## Demonstrated workflow

1. Create a dedicated evaluation user and upload the checksum-matched public corpus.
2. Create one session per frozen question.
3. Submit the exact question text and poll the run to a terminal state.
4. Save both the run record and structured output.
5. Score required evidence points, citations, unsupported claims, and failure modes.

Exact commands and API paths are documented in [the evaluation guide](../evaluation/README.md). The environment template is [`.env.example`](../.env.example).

## Preserved examples

- [MAT-001 structured baseline output](../evaluation/results/2026-09-26-v0.1.0/MAT-001.output.json): condition-bounded stainless-steel evidence with citations.
- [MAT-007 structured baseline output](../evaluation/results/2026-09-26-v0.1.0/MAT-007.output.json): an OCR-heavy failure case retained rather than removed.
- [Baseline per-question report](../evaluation/results/2026-09-26-v0.1.0/evaluation-report.md): all 12 questions, aggregate metrics, and failure analysis.
- [Generalized-agent regression](../evaluation/results/2026-09-27-v0.2.0/evaluation-report.md): configuration regression and operational failures.
- [Focused runtime regression](../evaluation/results/2026-09-27-v0.2.1-runtime-focused/evaluation-report.md): recovery behavior for the two operational failures.

## Interpretation

The preserved artifacts demonstrate an implemented end-to-end workflow and make both successful and failed cases inspectable. They do not demonstrate independent scientific validation, production reliability, or suitability for safety-critical decisions.
