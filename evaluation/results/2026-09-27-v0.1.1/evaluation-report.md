# ChemBiz v0.1.1 clean benchmark report

## Summary

ChemBiz completed all 12 frozen questions from a clean, recorded source state. The evaluated source commit was `dcc704d5c5dfd8fa479c069bb25a5d425c7dacfc`; `git status` was clean before corpus ingestion and execution, and benchmark-critical source hashes in both the API and worker containers matched the commit.

The run achieved 100% operational success and 79.7% weighted answer completeness. Every persisted claim carried canonical tool evidence, and internal manual review judged all 52 claim-to-source mappings supported. Five of 12 questions satisfied every required point. This is a reproducible prototype result against a curated draft key, not independent scientific validation.

## Aggregate results

| Metric | Result |
| --- | ---: |
| Successful runs | 12/12 (100.0%) |
| Exact frozen-query matches | 12/12 (100.0%) |
| Weighted answer completeness | 29.5/37 (79.7%) |
| Strict question pass rate | 5/12 (41.7%) |
| Citation completeness | 52/52 claims (100.0%) |
| Manual citation correctness | 52/52 claims (100.0%) |
| Manual unsupported-claim rate | 0/52 claims (0.0%) |
| Allowed-source compliance | 23/23 citation records (100.0%) |
| Client-observed batch duration | 514.1 seconds |

Fractional scores award 0.5 when a required point is only partially satisfied. A strict pass requires every required point and no prohibited claim. Citation judgments were performed by the repository owner with Codex assistance, not an independent domain expert.

## Per-question results

| ID | Score | Strict pass | Finding |
| --- | ---: | :---: | --- |
| MAT-001 | 3/3 | Yes | Correct alloy ranking and condition-dependent limitations. |
| MAT-002 | 1.5/2 | No | Correct screening conclusion; disclosed rather than guessed the OCR-corrupted one-half-percent lower bound. |
| MAT-003 | 2/2 | Yes | Correct passive-film attack and pitting mechanism. |
| MAT-004 | 2/2 | Yes | Correct source-bounded nitric/sulfuric comparison. |
| MAT-005 | 3/3 | Yes | All requested compatibility categories recovered. |
| MAT-006 | 2/3 | No | Correct electrochemical-series recommendation and galvanic rationale; platings and finishes omitted. |
| MAT-007 | 2.5/4 | No | Most alloy families recovered; 2014-T6, exact 17-4PH conditions, and AM350 SCT850 were missing. |
| MAT-008 | 1.5/3 | No | Brittleness and general differential contraction recovered; exact mechanisms and plastic-seal loading consequence omitted. |
| MAT-009 | 3/3 | Yes | Exact list plus vendor, hazard-assessment, and screening qualifications. |
| MAT-010 | 3/4 | No | Exact condition and barrier groups; vendor/use limitation omitted. |
| MAT-011 | 3/4 | No | Exact condition and barrier groups; vendor/use limitation omitted. |
| MAT-012 | 3/4 | No | Exact barrier groups and hazard language; vendor/use limitation omitted. |

## Reproducibility record

- Clean evaluated source commit: `dcc704d5c5dfd8fa479c069bb25a5d425c7dacfc`.
- Isolated evaluation user: `chembiz-eval-v0.1.1-clean-dcc704d`.
- Four source checksums matched `evaluation/source_manifest.csv`.
- All four files ingested successfully into 296 chunks.
- All questions ran once in frozen order with a 900-second per-question limit and no selective retries.
- Exact container dependency versions, source hashes, parameters, checksums, and ingestion identifiers are recorded in `run-metadata.json`.
- Raw structured outputs and the batch manifest are preserved in this directory.

## Remaining limitations

1. The expected-evidence key and scoring remain owner-prepared and await independent expert review.
2. Exact OCR-heavy extraction remains incomplete, especially for alloy/temper identifiers and one sulfuric-acid concentration bound.
3. Source-wide qualifications were still omitted from MAT-010 through MAT-012 despite correct table-row extraction.
4. MAT-008 did not retain all requested cryogenic mechanism details.
5. The runtime used mutable external OpenAI services; future executions may differ even with identical local code and parameters.
6. Qdrant client 1.19.1 connected successfully to Qdrant server 1.12.5 but emitted a version-compatibility warning.

## Conclusion

This clean run closes the earlier source-state provenance gap and provides a substantially stronger reproducibility record. It demonstrates implemented, traceable research behavior with preserved per-question evidence and honest failure reporting. It does not establish production readiness, safety suitability, broad chemical-engineering validity, or independent expert validation.
