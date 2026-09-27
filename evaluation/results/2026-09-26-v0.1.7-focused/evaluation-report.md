# ChemBiz v0.1.7 Focused Regression

## Outcome

All five cases that failed in the v0.1.6 full batch completed successfully after the search-budget and timeout changes. The batch finished in approximately 268 seconds. This supports the operational fix, but a full frozen-benchmark rerun is still required.

## Scores

| Question | Score | Strict pass | Finding |
| --- | ---: | --- | --- |
| MAT-002 | 1.5/2 | No | Correct screening conclusion; responsibly reports the illegible lower concentration bound instead of guessing it. |
| MAT-009 | 3/3 | Yes | Exact acetone list plus an appropriate NIOSH/vendor/use caveat. |
| MAT-010 | 3/4 | No | Exact concentration and 8-hour/4-hour groups; vendor/use limitation omitted. |
| MAT-011 | 3/4 | No | Exact concentration and 8-hour/4-hour groups; vendor/use limitation omitted. |
| MAT-012 | 3/4 | No | Exact groups and hazard language; vendor/use limitation omitted. |

Aggregate completeness was **13.5/17 (79.4%)** with **5/5 operational success**. All 16 atomic claims had citations, and manual review found the cited pages directly relevant to all 16 claims.

## Interpretation

The bounded stopping policy recovered the earlier timeout failures without losing the requested table values. The unrelated CDC disinfectant citation seen in v0.1.6 did not recur. However, URL provenance alone remains insufficient as a general semantic-support check, and three safety answers still lost a source-level limitation. A subsequent code patch therefore adds bounded web-result content to the handoff evidence inventory and explicitly requires direct excerpt support and retention of safety-source limitations.

This is an internal focused regression, not independent scientific validation.
