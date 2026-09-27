# Preserved evaluation results

This directory intentionally retains three evidence-bearing result sets rather than every development iteration:

- `2026-09-26-v0.1.0`: complete 12-question baseline with per-question artifacts, scores, run metadata, quantitative report, and documented failures.
- `2026-09-27-v0.2.0`: complete generalized-agent regression showing both improvements and two operational failures.
- `2026-09-27-v0.2.1-runtime-focused`: focused rerun of those two failures after deadline and OCR-error recovery changes.

Intermediate prompt-tuning and focused development runs were removed from the default branch to reduce duplication and make the evidence trail easier to review. They remain recoverable from the immutable `v0.1.0` release tag.

These results are internal prototype evaluations against a curated draft key. They have not received independent domain-expert validation. The original baseline also ran from a working tree with uncommitted changes, so its recorded base commit does not reproduce the exact evaluated source state. See each report and the release technical report for the complete limitations.
