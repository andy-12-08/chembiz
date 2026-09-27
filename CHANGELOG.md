# Changelog

All notable changes to ChemBiz are documented here. The project follows semantic versioning for public releases.

## [0.1.0] - 2026-09-27

### Added

- FastAPI endpoints for sessions, uploads, research runs, and structured outputs.
- Document ingestion through PyMuPDF, Docling, and Unstructured.
- Qdrant-backed semantic and lexical retrieval with user/session provenance.
- LangGraph DeepSearch orchestration with document, page-OCR, and web-search tools.
- Structured claims, citations, evidence gaps, confidence, and tool traces.
- Docker Compose services for the API, worker, PostgreSQL, Qdrant, and Temporal.
- A 12-question materials-compatibility benchmark, source manifest, expected-evidence key, scoring artifacts, and preserved outputs.
- Unit tests for citation sanitization, URL provenance, page mapping, hybrid retrieval, deadlines, and recoverable OCR failures.
- Release documentation covering architecture, trust boundaries, configuration, demonstration artifacts, quantitative results, and limitations.
- Apache License 2.0 for original ChemBiz code and documentation.

### Known limitations

- The benchmark and manual scoring have not received independent domain-expert validation.
- The original v0.1.0 evaluation ran from a working tree with uncommitted changes, so its recorded base commit does not reproduce the exact evaluated code state.
- The benchmark contains 12 questions and is weighted toward materials compatibility; it does not validate broad chemical-engineering performance.
- Results show incomplete synthesis and OCR-related failures despite strong citation attachment.
- External services, model versions, and web content can change run outcomes.

[0.1.0]: https://github.com/andy-12-08/chembiz/releases/tag/v0.1.0
