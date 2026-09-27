# Independent Reviewer Guide

## Required reviewer background

Use at least two reviewers with demonstrated chemical-engineering or closely related domain expertise. Record degree, relevant discipline, years of experience, and conflicts of interest. Reviewers should not be involved in developing ChemBiz's prompts, retrieval code, or expected answers.

## Review procedure

Each reviewer independently receives the frozen sources, `questions.json`, and `expected_evidence.json`, but no ChemBiz answers during the first pass. For every question, the reviewer records:

1. whether the question is technically clear and answerable from the allowed sources;
2. whether each required-evidence item is accurate and material;
3. whether any essential condition, unit, assumption, limitation, or safety qualification is missing;
4. whether each prohibited claim is genuinely unsupported or unsafe;
5. suggested corrections with exact source locators.

After the key is reconciled and frozen, reviewers score blinded ChemBiz outputs independently.

## Output-scoring dimensions

Score each dimension from 0 to 2:

- **Technical correctness:** 0 incorrect, 1 partly correct, 2 correct.
- **Completeness:** 0 misses most required evidence, 1 partial, 2 complete.
- **Condition fidelity:** 0 changes or omits material conditions, 1 minor omissions, 2 preserves conditions and units.
- **Evidence support:** 0 unsupported/fabricated, 1 mixed support, 2 every material claim directly supported.
- **Uncertainty calibration:** 0 overclaims, 1 partly calibrated, 2 clearly reports gaps/conflicts and avoids unjustified extrapolation.

Also record binary flags for fabricated citation, fabricated numeric value, unsafe recommendation, and source substitution.

## Agreement and adjudication

Report raw agreement and an appropriate chance-corrected statistic for categorical ratings. Preserve original reviewer scores. Resolve disagreements through a documented adjudication meeting led by a third qualified reviewer when possible; do not silently overwrite ratings.

## Reporting restriction

Until this process is completed, describe the benchmark as a curated draft—not expert-validated ground truth or scientific validation of ChemBiz.
