# ChemBiz Chemical-Engineering Benchmark v0.1 (Draft)

This directory defines a domain-balanced successor to the initial materials benchmark. It is intentionally separate from `evaluation/questions.json`, which remains frozen for longitudinal regression.

## Scope

The draft covers:

- thermodynamic systems and energy balances;
- chemical equilibrium and reaction-condition reasoning;
- interpretation of chemical-kinetics records;
- conduction, convection, and radiation;
- fluid-flow regime and head loss;
- separation fundamentals;
- water treatment and ion exchange;
- chemical hazards and engineering limitations.

## Validation status

This is a benchmark-development artifact, not a scored or expert-validated dataset. Before use as evidence of system performance:

1. Download and checksum every source in `source_manifest.csv`.
2. Record exact page and section locators for every required-evidence statement.
3. Have at least two qualified chemical engineers independently review the questions and key.
4. Resolve disagreements and report inter-rater agreement.
5. Freeze the corpus, questions, scoring rubric, model configuration, and retry policy.
6. Keep a held-out subset untouched during system development.

The five DOE PDFs and NIST HTML snapshot have been downloaded and checksummed in `source_manifest.csv`; the binaries are gitignored. `split.json` freezes six development cases and four held-out cases. Run `python validate_dataset.py` from this directory to check IDs, source references, locators, split membership, local source presence, and every recorded SHA-256 digest.

`reviewer_guide.md` and `review_form.csv` provide the independent-review protocol. The benchmark must remain labelled `0.1-draft` until that review is completed and adjudicated.

Questions must test source-grounded synthesis, operating-condition retention, uncertainty, and resistance to unsupported extrapolation. They should not reward memorized textbook prose when the supplied evidence is incomplete.
