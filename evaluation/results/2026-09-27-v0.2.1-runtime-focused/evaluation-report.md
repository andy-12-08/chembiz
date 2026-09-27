# ChemBiz v0.2.1 Runtime Regression

Both operational failures from the v0.2.0 full batch reached `succeeded` status after the runtime fixes:

- MAT-001 completed with a condition-aware answer and explicitly disclosed the unreadable OCR character instead of guessing it.
- MAT-007 received a structured OCR provenance error and completed with the two identifiers it could verify plus an explicit evidence gap. The answer remains scientifically incomplete, but the recoverable tool error no longer crashes the run.

This focused result validates terminal behavior and error recovery only. It is not a substitute for a complete benchmark rerun and does not establish answer completeness for MAT-007.
