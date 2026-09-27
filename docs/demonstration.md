# ChemBiz v0.1.1 demonstration record

This document is a reproducible, text-based demonstration record. It links to preserved machine-readable evidence instead of presenting a staged interface screenshot.

## Demonstrated workflow

1. Create a dedicated evaluation user and upload the checksum-matched public corpus.
2. Create one session per frozen question.
3. Submit the exact question text and poll the run to a terminal state.
4. Save both the run record and structured output.
5. Score required evidence points, citations, unsupported claims, and failure modes.

Exact commands and API paths are documented in [the evaluation guide](../evaluation/README.md). The environment template is [`.env.example`](../.env.example).

## Preserved examples

- [MAT-001 structured output](../evaluation/results/2026-09-27-v0.1.1/MAT-001.output.json): a strict-pass example with condition-bounded stainless-steel evidence.
- [MAT-007 structured output](../evaluation/results/2026-09-27-v0.1.1/MAT-007.output.json): an OCR-heavy partial result retained rather than hidden.
- [Per-question evaluation report](../evaluation/results/2026-09-27-v0.1.1/evaluation-report.md): metrics, findings, reproducibility details, and limitations for all 12 questions.
- [Machine-readable scores](../evaluation/results/2026-09-27-v0.1.1/scores.json) and [run metadata](../evaluation/results/2026-09-27-v0.1.1/run-metadata.json): scoring and exact execution record.

## Interpretation

The preserved artifacts demonstrate an implemented end-to-end workflow from a clean, identified commit and make complete and partial answers inspectable. They do not demonstrate independent scientific validation, production reliability, or suitability for safety-critical decisions.
