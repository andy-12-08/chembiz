# ChemBiz v0.1.1 technical report

## Purpose

ChemBiz is an evidence-grounded research prototype for retrieving and synthesizing public chemical and materials information with traceable citations. Version 0.1.1 packages a clean, reproducible materials-compatibility benchmark as evidence of implemented work.

## Evaluated system

The benchmark ran from clean source commit `dcc704d5c5dfd8fa479c069bb25a5d425c7dacfc`. Four checksum-verified public government documents were ingested into an isolated evaluation account, producing 296 chunks. All 12 frozen questions then ran once in file order through the Docker-hosted API, without selective retries.

The exact checksums, runtime dependencies, parameters, ingestion identifiers, and benchmark-critical container source hashes are recorded in [run-metadata.json](../evaluation/results/2026-09-27-v0.1.1/run-metadata.json).

## Results

- Operational success: 12/12 (100.0%).
- Weighted answer completeness: 29.5/37 (79.7%).
- Strict question passes: 5/12 (41.7%).
- Citation completeness: 52/52 claims (100.0%).
- Internal manual citation correctness: 52/52 claims (100.0%).
- Internal manual unsupported-claim rate: 0/52 claims (0.0%).
- Client-observed duration: 514.1 seconds.

See the [full evaluation report](../evaluation/results/2026-09-27-v0.1.1/evaluation-report.md), [machine-readable scores](../evaluation/results/2026-09-27-v0.1.1/scores.json), and [demonstration record](demonstration.md).

## Interpretation and limitations

The run demonstrates an implemented end-to-end workflow, source-state traceability, claim-level citation attachment, and transparent preservation of partial answers. It does not establish broad chemical-engineering validity, production readiness, or fitness for safety-critical decisions.

The evidence key and scoring were prepared by the repository owner with Codex assistance and have not been independently validated by a domain expert. Several OCR-heavy identifiers, cryogenic mechanism details, and source-wide vendor/use qualifications were omitted. External model services are mutable, so exact answers may differ in a later rerun even when local source and parameters are unchanged.

## Recommended next evidence

The highest-value next step is independent review by a qualified chemical or materials expert who documents what they reviewed, their qualifications, strengths, limitations, and the relevance of traceable retrieval to their field. That review should supplement—not retroactively alter—the preserved results.
