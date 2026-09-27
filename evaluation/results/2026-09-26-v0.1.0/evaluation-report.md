# ChemBiz Materials Evaluation Report

## Summary

ChemBiz completed all 12 frozen questions successfully and preserved exact query snapshots and structured outputs. The system showed strong citation mechanics and high source-retrieval coverage, but materially weaker answer completeness. The main gap is not locating evidence; it is selecting and accurately expressing the decisive evidence after retrieval, particularly when NASA PDF text contains OCR errors.

This is a prototype evaluation against a curated draft key. It is not independent domain-expert validation and should not be represented as such.

## Aggregate results

| Metric | Result |
| --- | ---: |
| Successful runs | 12/12 (100.0%) |
| Exact frozen-query matches | 12/12 (100.0%) |
| Source retrieval success | 12/12 (100.0%) |
| Weighted evidence coverage | 34.5/37 (93.2%) |
| Weighted answer completeness | 23.25/37 (62.8%) |
| Strict question pass rate | 3/12 (25.0%) |
| Citation completeness | 47/47 claims (100.0%) |
| Citation correctness | 46/47 claims (97.9%) |
| Unsupported-claim rate | 1/47 claims (2.1%) |
| Allowed-source compliance | 18/20 unique citations (90.0%) |
| Fully complete among high-confidence outputs | 1/3 (33.3%) |

Fractional evidence scores award 0.5 for a partially satisfied required point. A strict pass requires every required point and no prohibited claim.

## Per-question findings

| ID | Answer score | Strict pass | Finding |
| --- | ---: | :---: | --- |
| MAT-001 | 3/3 | Yes | Correct alloy identification and appropriate limitations. |
| MAT-002 | 1.5/2 | No | Correct main conclusion; omitted the one-half-percent lower concentration bound. |
| MAT-003 | 2/2 | Yes | Correct passive-film and pitting mechanism extraction. |
| MAT-004 | 2/2 | Yes | Correct, source-bounded nitric/sulfuric comparison. |
| MAT-005 | 0/3 | No | Retrieved the decisive NASA passage but answered with unrelated considerations. |
| MAT-006 | 2/3 | No | Correct series/risk answer; omitted platings and finishes. |
| MAT-007 | 0.75/4 | No | Failed exact-list extraction from OCR-degraded text and misassigned H900. |
| MAT-008 | 0.5/3 | No | Missed the decisive NASA page and most requested cryogenic concerns. |
| MAT-009 | 2.5/3 | No | Correct barrier list and useful caution; vendor confirmation not explicit. |
| MAT-010 | 3/4 | No | Exact table extraction; required vendor/use-limitation caveat omitted. |
| MAT-011 | 3/4 | No | Exact table extraction; required vendor/use-limitation caveat omitted. |
| MAT-012 | 3/4 | No | Exact table and hazard extraction; required vendor/use-limitation caveat omitted. |

## What worked

- Every run reached `succeeded`, and every saved query exactly matched the frozen dataset.
- Every material claim in the structured outputs carried at least one validated citation identifier or URL.
- NIST questions MAT-001, MAT-003, and MAT-004 were fully answered.
- NIOSH chemical/barrier rows were extracted accurately, including concentration bounds and hazard wording.
- The system generally lowered confidence or recorded evidence gaps when retrieval or OCR was incomplete.
- Only one material claim was judged to misstate its cited source: MAT-007 associated H900 with 17-4PH; the NASA passage associates H900 with 17-7PH.

## Main weaknesses

1. **Retrieved evidence was not reliably converted into the answer.** MAT-005 and MAT-007 retrieved NASA PDF page 130, which contains the expected answers, but the final synthesis omitted most or all decisive content.
2. **OCR-heavy exact lists need special handling.** MAT-007 demonstrates that a language model should not reconstruct alloy temper codes from damaged OCR without checking another extraction path or page image.
3. **Retrieval missed the decisive adjacent page.** MAT-008 needed NASA PDF page 131, but the cited chunks came from unrelated pages.
4. **Mandatory limitations were inconsistently retained.** MAT-010 through MAT-012 correctly copied table rows but dropped the vendor-confirmation/use-limitation instruction on the same NIOSH page.
5. **Confidence was sometimes too high.** MAT-010 and MAT-011 were labeled high confidence despite omitting a required safety limitation. Only one of three high-confidence outputs was fully complete.
6. **Source constraints were not fully enforced.** MAT-009 cited OSHA and a restored-CDC mirror in addition to the allowed archived NIOSH source. Those citations were relevant, but they were outside the frozen allowed-source set.
7. **Some saved text contains character-encoding artifacts**, such as `150Â°F`, which weakens presentation quality and should be normalized before publication.

## Recommended engineering priorities

1. Add a required-evidence verification pass before finalizing an answer: for each requested list, condition, and caveat, verify that the final claims explicitly contain it.
2. Add page-neighbor retrieval or targeted page-window expansion when a top chunk spans a section boundary.
3. Detect OCR uncertainty in exact identifiers such as alloy/temper codes and trigger a second parser, page-image review, or explicit abstention.
4. Add prompt and validation rules requiring safety and vendor limitations found in the cited source to remain attached to protective-equipment answers.
5. Enforce per-question allowed source IDs/domains during evaluation mode, rather than checking them only during scoring.
6. Calibrate confidence against completeness and unresolved evidence gaps, not only whether at least one citation survived validation.
7. Store full retrieved passages in the evaluation artifact; the current `content_preview` is truncated and limits later retrieval auditing.
8. Normalize UTF-8 text before persistence and add regression tests for degree symbols, en dashes, and smart apostrophes.

## Reproducibility limitations

- The evidence key remains a curated draft pending independent domain-expert review.
- Scoring involved manual judgment for partial evidence points.
- The repository working tree was not clean during the run. Commit `eefe926dffa0a695ec0b05013c2fdad1a04f057b` therefore identifies the base commit, not the full evaluated state.
- MAT-005's run response was initially saved while `running`; it was refreshed from the same local run after completion and now matches its structured output.
- The two local PDFs are checksum-recorded in `evaluation/source_manifest.csv`; archived NIOSH evidence was accessed by URL.

## Conclusion

Version 0.1.0 provides credible evidence that ChemBiz can execute an end-to-end, traceable chemical/materials research workflow with strong citation attachment and low unsupported-claim incidence. It does not yet demonstrate consistently complete scientific synthesis: the 62.8% weighted answer-completeness score and NASA exact-extraction failures are substantive limitations. The result is suitable as an honest prototype baseline and engineering roadmap, not as a claim of validated production readiness.
