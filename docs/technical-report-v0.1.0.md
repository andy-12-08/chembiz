# ChemBiz v0.1.0 technical report

**Release date:** 2026-09-27

**Status:** Research prototype

**Endeavor:** Develop and validate evidence-grounded artificial-intelligence methods that retrieve, compare, and trace public scientific, safety, regulatory, and materials information, helping U.S. chemical and materials professionals make more reliable technical decisions.

## Problem and intended users

Chemical and materials professionals often need to locate condition-specific statements across long technical sources and retain the qualifications that make those statements meaningful. ChemBiz targets evidence retrieval and traceable synthesis for researchers, R&D scientists, chemical and process engineers, and technical analysts. It is not a substitute for engineering judgment, source review, or regulatory and safety review.

## System contribution

ChemBiz combines page-aware document ingestion, hybrid retrieval, bounded web research, durable workflows, and a structured handoff layer. The handoff layer reconstructs citations from tool-returned provenance, removes unsupported identifiers, and records evidence gaps. The architecture is documented in [architecture.md](architecture.md).

## Demonstration and data

The included materials benchmark contains 12 frozen questions, a source manifest, a curated expected-evidence key, per-run JSON, scores, and failure reports. Local source documents are intentionally excluded; the manifest records URLs, retrieval dates, rights notes, and checksums. The benchmark uses public technical sources but item-specific redistribution rights must still be checked.

The broader chemical-engineering dataset under `evaluation/chemical_engineering_v0.1` is a draft and is not reported as validated evidence.

## Quantitative results

The first preserved baseline completed 12/12 runs. Manual scoring reported 93.2% weighted evidence coverage, 62.8% weighted answer completeness, 100% citation completeness, 97.9% citation correctness, and a 2.1% unsupported-claim rate. Only 3/12 questions passed every required point.

The later generalized-agent regression completed 10/12 runs and achieved 64.9% end-to-end evidence completeness. Among successful runs, completeness was 80.0%; all 30 persisted claims had tool-backed citations and manual review judged all 30 supported. A focused runtime regression subsequently showed that the two operational failure cases reached terminal success after deadline and OCR-error handling changes. That focused run validates those runtime behaviors only, not full benchmark performance.

## Reproducibility

The repository preserves questions, keys, manifests, run records, structured outputs, scoring files, and runner instructions. Unit tests exercise deterministic citation and retrieval behavior without external services. A full system reproduction requires the checksum-matched source corpus, Docker services, OpenAI and Tavily credentials, and potentially changing external model/search behavior.

For the release candidate on 2026-09-27, the local test suite completed with **24 passed**. The draft chemical-engineering dataset validator also passed, and all committed JSON evaluation artifacts and `pyproject.toml` parsed successfully. These checks establish software and artifact consistency; they are not independent scientific validation.

The initial v0.1.0 benchmark was executed from a dirty working tree. Its recorded base commit therefore does not identify the exact evaluated source state. This is a material limitation. The release preserves the result as historical prototype evidence; it does not claim that checking out this tag will recreate those exact numerical results.

## Failure analysis

- Retrieval did not always lead to complete final synthesis.
- OCR-degraded identifiers caused omissions and one incorrect alloy/temper association.
- Adjacent decisive pages were sometimes missed.
- Safety and vendor-use qualifications were not consistently retained.
- Some confidence ratings were too high relative to answer completeness.
- The initial evaluation allowed two citations outside its frozen source set.

## Safety, ownership, and licensing

Outputs must be checked against original sources and cannot be the sole basis for laboratory, materials-selection, process-design, compliance, or safety decisions. The repository owner states that ChemBiz is an independent personal project with no employer or client contribution or confidential material. Reachable commits at release preparation use the LSU-associated personal GitHub identity `aokafo3@lsu.edu`.

Original ChemBiz software and documentation are licensed under Apache 2.0. Third-party publications and excerpts retain their respective rights and are not relicensed by inclusion in evaluation artifacts.

## Next work

Over the next 12–24 months, planned work includes locking clean evaluation configurations, completing the broader benchmark, adding repeated-run measurements and configuration comparisons, improving exact OCR extraction and qualification retention, and obtaining independent domain-expert review. Outputs are intended to remain usable beyond one employer through public code, manifests, evaluation protocols, preserved results, and technical reports.
