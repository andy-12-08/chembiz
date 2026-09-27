# ChemBiz v0.1.6 Evaluation Report

## Outcome

The improved system produced materially stronger answers when runs completed, but it did not meet an acceptable operational-reliability threshold. Eight of 12 frozen runs succeeded. Four runs failed under the bounded execution policy: MAT-002, MAT-009, MAT-010, and MAT-011.

This is a development evaluation against a curated draft key, not independent scientific validation.

## Metrics

| Metric | v0.1.0 baseline | v0.1.6 |
| --- | ---: | ---: |
| Operational success | 12/12 (100.0%) | 8/12 (66.7%) |
| End-to-end answer completeness | 23.25/37 (62.8%) | 21/37 (56.8%) |
| Completeness conditional on a successful run | 23.25/37 (62.8%) | 21/24 (87.5%) |
| Strict question passes | 3/12 (25.0%) | 4/12 (33.3%) |
| Citation completeness | 47/47 (100.0%) | 37/37 (100.0%) |
| Estimated citation correctness | 46/47 (97.9%) | 35/37 (94.6%) |
| Estimated unsupported-claim rate | 1/47 (2.1%) | 2/37 (5.4%) |

Failed runs count as zero in end-to-end completeness. Conditional completeness describes answer quality only among successful runs and must not be reported without the operational-success rate.

## Improvements demonstrated

- MAT-005 improved from 0/3 required points to 3/3 after increasing evidence visibility.
- MAT-007 improved from approximately 0.75/4 to 3.5/4 in the full batch and reached 4/4 in the final focused run after authorized page OCR.
- MAT-008 improved from approximately 0.5/3 to 2.5/3 after hybrid retrieval surfaced the decisive NASA passage.
- OCR page requests now require matching Qdrant session, file, chunk, schema, and page metadata.
- All successful outputs retained claim-level citations.
- Indefinitely running jobs were replaced with bounded, terminal failures, and the runner continued subsequent questions.

## Remaining failures

1. **Stopping policy and latency:** MAT-002 and three NIOSH questions exhausted the research-stage execution bound. Stronger completeness instructions encouraged excessive tool use.
2. **Web-source semantic validation:** MAT-012 attached an irrelevant archived CDC disinfectant page to two claims. URL provenance validation proves that a URL was returned by search; it does not prove that the page supports the claim.
3. **Qualification retention:** MAT-006 omitted the source's reference to acceptable platings and finishes. NIOSH vendor-confirmation/use-limitation language remained inconsistent.
4. **Repeatability:** MAT-007 reached a complete answer in a focused run but missed 2014-T6 in the full batch, showing sampling variability.
5. **Encoding quality:** persisted answers still contain mojibake such as `150Â°F` and malformed smart quotes.

## Interpretation

The changes improved the core scientific synthesis behavior but traded away too much operational reliability. v0.1.6 is therefore not a superior end-to-end release despite its much higher conditional completeness. The next version should constrain search/tool loops, preserve explicit failure reasons, and validate semantic claim support for web citations before another complete batch.

## Validation status

These results support an honest claim that ChemBiz is an actively evaluated research prototype with traceable evidence and documented failure analysis. They do not support a claim that the system is scientifically validated. Independent expert review, a held-out dataset, repeated-run analysis, and a clean tagged code state remain required.
