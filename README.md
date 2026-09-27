# ChemBiz

ChemBiz is an evidence-grounded AI tool for accelerating chemical and materials research. It retrieves, compares, and synthesizes information from scientific and technical documents while preserving links to the supporting evidence.

## Why ChemBiz

Chemical researchers and technical teams often need to review large collections of literature, safety information, materials data, and other technical documents before they can answer a focused research question. This work is time-consuming, and a generated answer is useful only when its claims can be checked against reliable sources.

ChemBiz is being developed to make that process faster and more traceable. The system combines document ingestion, semantic retrieval, web research, and an AI research agent to produce evidence-grounded answers with structured citations. It is intended to support researchers rather than replace scientific judgment.

## Intended users

- Chemical and materials researchers
- Research and development scientists
- Chemical and process engineers
- Technical analysts
- Industrial research teams

## Initial demonstration

The first planned reproducible demonstration focuses on materials compatibility and selection, including chemical resistance and corrosion behavior, using public, legally shareable technical sources. The demonstration will evaluate whether ChemBiz can:

1. Retrieve relevant evidence for a defined chemical question.
2. Synthesize evidence from multiple technical documents.
3. Link factual claims to the source documents and passages that support them.
4. Identify uncertainty when the available evidence is incomplete or conflicting.

A versioned evaluation package provides 12 questions, a government-source manifest, a curated expected-evidence key, preserved system outputs, and an initial quantitative baseline. Independent domain review remains planned work.

## Current capabilities

- FastAPI endpoints for sessions, document uploads, research runs, and structured outputs
- PDF and document processing with PyMuPDF, Docling, and Unstructured
- Document chunking and OpenAI embeddings
- Qdrant vector retrieval with session and user filtering
- LangGraph-based research-agent orchestration
- Public web search through Tavily
- Temporal workflows for document ingestion and web search
- PostgreSQL persistence and Alembic database migrations
- Structured answers with tool-validated chunk, file, page, and web-source citations
- Extracted facts, evidence gaps, calibrated confidence, and tool traces
- Docker Compose services for the API, worker, PostgreSQL, Qdrant, and Temporal

## Architecture

The detailed component diagram, trust boundaries, and runtime dependencies are documented in [`docs/architecture.md`](docs/architecture.md).

```text
User question and documents
          |
          v
  FastAPI session API
          |
          +------> Document ingestion workflow
          |          -> parse and chunk
          |          -> create embeddings
          |          -> store vectors in Qdrant
          |
          v
  LangGraph DeepSearch agent
          |
          +------> session document retrieval
          +------> Temporal web-search workflow
          |
          v
  Evidence-grounded answer
  + structured citations and tool trace
          |
          v
  PostgreSQL persistence
```

## Project status

ChemBiz is an active research prototype, not a validated production or regulatory system. Its core ingestion, retrieval, orchestration, persistence, and API components are implemented. A draft public materials-research benchmark, an automated local-API runner, and a clean, commit-linked result set are included; independent domain review remains planned work.

## Run with Docker

### Prerequisites

- Docker with Docker Compose
- OpenAI API credentials for embeddings and model inference
- Tavily API credentials for public web search

### Configure the environment

Copy [`.env.example`](.env.example) to `docker/.env`, then replace the placeholder passwords and API keys. The application requires configuration for PostgreSQL, Qdrant, Temporal, OpenAI, and Tavily. Do not commit API keys, passwords, or other credentials.

### Start ChemBiz

```bash
docker compose -f docker/docker-compose.yaml up --build
```

Docker Compose starts the ChemBiz API, Temporal worker, PostgreSQL databases, Qdrant, Temporal server, and Temporal UI.

After the services become healthy, access:

- API: `http://localhost:8000`
- Interactive API documentation: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

Stop the services with:

```bash
docker compose -f docker/docker-compose.yaml down
```

## Responsible-use limitations

ChemBiz may retrieve incomplete, outdated, conflicting, or incorrect information, and AI-generated responses may contain errors. All outputs and citations must be verified against the original sources.

ChemBiz does not replace professional chemical-safety, regulatory, environmental, medical, legal, or engineering review. Do not use its output as the sole basis for laboratory procedures, exposure decisions, materials selection, process design, regulatory compliance, or other safety-critical decisions.

## Evaluation

The [`evaluation`](evaluation/) package defines the first reproducible materials-research benchmark. It includes a source manifest, 12 frozen questions, a curated draft evidence key, scoring rules, and a location for preserved results. The evidence key has not yet received independent domain-expert validation.

The evaluation can currently be run through the Docker-hosted API or Swagger UI. Use a dedicated evaluation `user_id`, upload the frozen document corpus once, and then create a separate session and run for each frozen question. This keeps the query snapshot for every result immutable while allowing ChemBiz's intentional same-user, cross-session retrieval to reuse the uploaded corpus. Preserve both `/runs/{run_id}` and `/runs/{run_id}/output` responses. See [`evaluation/README.md`](evaluation/README.md#running-version-010-today) for the exact procedure and scoring requirements.

The clean release benchmark is preserved in [`evaluation/results/2026-09-27-v0.1.1/evaluation-report.md`](evaluation/results/2026-09-27-v0.1.1/evaluation-report.md). It ran all 12 frozen questions once against clean source commit `dcc704d5c5dfd8fa479c069bb25a5d425c7dacfc`, with no selective retries. It reports 12/12 operational success, 79.7% weighted answer completeness, 5/12 strict question passes, 52/52 claims with citations, and no unsupported claims identified in internal manual review. These are owner-prepared, Codex-assisted prototype results against a curated draft key—not independent domain-expert validation.

See the [`v0.1.1` technical report](docs/technical-report-v0.1.1.md) and [text-based demonstration record](docs/demonstration.md) for the release-level summary and direct evidence links. Historical development runs remain available from the immutable [`v0.1.0` release](https://github.com/andy-12-08/chembiz/releases/tag/v0.1.0).

## Confidentiality and provenance

ChemBiz is an independent personal project. This repository does not contain Deloitte or client confidential information, client data, proprietary client materials, or client code. No employer or client confidential material should be submitted to, tested with, or committed to this repository.

Contributors are responsible for confirming that they have the right to disclose and use every document, dataset, and code contribution. Public demonstrations should use public-domain, openly licensed, or otherwise legally shareable sources.

## Roadmap

- Obtain independent domain-expert review of the public materials-compatibility demonstration and scoring key
- Add a held-out benchmark spanning thermodynamics, kinetics, reactor engineering, separations, transport, process design, materials, and safety
- Independently review the versioned evaluation dataset and scoring key
- Measure retrieval relevance, citation correctness, answer completeness, and failure cases
- Expand automated integration coverage for the external service stack
- Record a short interface demonstration after the release configuration is running

## License

ChemBiz source code and original project documentation are licensed under the [Apache License 2.0](LICENSE).

Third-party publications, quoted passages, search-result content, source documents, and other externally authored material referenced or preserved in evaluation artifacts remain subject to their respective owners' rights and terms. Their inclusion for citation, traceability, or evaluation does not relicense them under Apache 2.0. Review the source manifest and the original source terms before redistributing such material.
