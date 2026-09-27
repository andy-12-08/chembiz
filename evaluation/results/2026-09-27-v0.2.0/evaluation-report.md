# ChemBiz v0.2.0 Materials Regression

## Outcome

The generalized chemical-engineering prompt achieved **10/12 operational success** and **24/37 (64.9%) end-to-end evidence completeness**. Among successful runs, completeness was **24/30 (80.0%)**. All 30 persisted atomic claims had tool-backed citations, and manual review found no unsupported persisted claim.

This materials-heavy regression verifies that generalizing the prompt did not destroy evidence grounding. It does not establish broad chemical-engineering validity.

## Per-question assessment

| Question | Score | Strict pass | Finding |
| --- | ---: | --- | --- |
| MAT-001 | 0/3 | No | Client timeout; server run remained active beyond its intended deadline. |
| MAT-002 | 1.5/2 | No | Correct screening conclusion; unreadable lower concentration bound was disclosed rather than guessed. |
| MAT-003 | 2/2 | Yes | Correct passive-film attack and pitting mechanism. |
| MAT-004 | 2/2 | Yes | Correct condition-bounded nitric/sulfuric contrast. |
| MAT-005 | 3/3 | Yes | All requested compatibility categories recovered. |
| MAT-006 | 2/3 | No | Correct electrochemical-series recommendation and galvanic rationale; platings/finishes omitted. |
| MAT-007 | 0/4 | No | Recoverable invalid OCR-page request failed the complete run. |
| MAT-008 | 1.5/3 | No | Brittleness and expansion mismatch recovered; specific shrinkage mechanisms and plastic-seal loading consequence omitted. |
| MAT-009 | 3/3 | Yes | Exact list plus source-wide caveats and screening limitation. |
| MAT-010 | 3/4 | No | Exact condition and groups; table-wide vendor/use limitation not repeated. |
| MAT-011 | 3/4 | No | Exact condition and groups; table-wide vendor/use limitation not repeated. |
| MAT-012 | 3/4 | No | Exact groups and hazard language; table-wide vendor/use limitation not repeated. |

## Failure analysis and corrective changes

MAT-001 showed that `asyncio.wait_for` could wait indefinitely for cancellation of a non-cooperative operation. The runtime now uses a hard status deadline that cancels and detaches overdue work, allowing the run row to reach a terminal failed state promptly.

MAT-007 failed because the agent requested OCR page 2 using a chunk whose canonical pages were 130-132. The provenance guard correctly rejected the request, but the tool exception terminated the run. Expected OCR validation failures now return structured tool errors so the agent can correct the request or answer with an evidence gap.

## Interpretation

The strongest improvement is evidence integrity: successful outputs used canonical document provenance, retained conditions, and avoided fabricated completion. The main remaining weaknesses are operational robustness, retrieval of source-wide qualifications, exact OCR-heavy extraction, and incomplete recovery of explanatory consequences.

These results describe an internally evaluated research prototype. Scientific validation still requires a broader held-out benchmark, independent chemical-engineering reviewers, repeated-run reliability measurement, and a locked release configuration.
