# ChemBiz Materials-Research Evaluation

This package defines the first reproducible evaluation of ChemBiz as an evidence-grounded tool for chemical and materials research.

## Evaluation objective

The evaluation asks whether ChemBiz can retrieve and synthesize source-supported information relevant to materials compatibility and selection without overstating what the sources establish.

This is a research-information benchmark, not a material-selection procedure. The questions test evidence retrieval and citation behavior. They do not authorize laboratory work, protective-equipment selection, process design, or safety-critical decisions.

## Scope

Version 0.1 contains 12 questions covering:

- corrosion resistance of nickel-bearing and stainless alloys;
- general material/fluid compatibility considerations;
- stress-corrosion and cryogenic design considerations; and
- chemical-barrier recommendations from NIOSH.

The initial sources are U.S. government publications or government-hosted resources. `source_manifest.csv` records stable identifiers, publishers, URLs, access dates, and rights notes. Source files are not committed at this stage. This avoids silently redistributing material before its item-specific rights are confirmed.

## Files

- `questions.json`: frozen questions and source constraints.
- `expected_evidence.json`: draft evidence key and grading criteria.
- `source_manifest.csv`: source provenance and acquisition information.
- `results/`: preserved outputs and scored run artifacts.

## Ground-truth status

The evidence key is a draft prepared from the cited government sources. It must be reviewed by a qualified materials or chemical-domain reviewer before results are described as expert-validated ground truth. Until then, report it as a curated reference key.

Do not modify the questions or reference key after inspecting a model's answers for a scored run. If corrections are necessary, increment the dataset version and document the change.

## Reproducible workflow

1. Visit each URL in `source_manifest.csv` and confirm the title, publisher, version, and access status.
2. Save a local copy for the evaluation run only where its rights permit. Record the file SHA-256 checksum.
3. Choose a dedicated evaluation user id that has no unrelated documents, such as `chembiz-eval-v0.1.0`.
4. Create an ingestion session for that user and upload the frozen document source set once. Wait for document ingestion to finish before starting scored runs. ChemBiz intentionally permits retrieval from documents in the same user's other sessions.
5. For each entry in `questions.json`, create a new session with the same evaluation user id and the exact frozen question text. A separate session is required because the session query becomes the immutable run query snapshot.
6. Start one run for each question and poll it until its status is `succeeded` or `failed`.
7. Fetch both `/runs/{run_id}` and `/runs/{run_id}/output` for each completed run. The runner uses the status response to build the batch manifest; retain the structured output as the per-question evidence artifact.
8. Save the raw API response and structured output for every question under a timestamped directory in `results/`.
9. Score each response against `expected_evidence.json`.
10. Preserve software commit, model name, retrieval configuration, source checksums, run date, and evaluator identity with the results.

## Running version 0.1.0 today

The recommended method is the automated local-API runner. Swagger remains useful for inspecting or manually reproducing individual calls.

1. Start the complete stack from the repository root:

   ```powershell
   docker compose -f docker/docker-compose.yaml up --build
   ```

2. Open `http://localhost:8000/docs` and confirm `http://localhost:8000/health` succeeds.
3. Download and verify the allowed sources listed in `source_manifest.csv`. The frozen corpus includes the NIST and NASA PDFs plus local HTML snapshots of the official archived NIOSH table and disclaimer. Upload all four files to the dedicated evaluation user so scored extraction does not depend on stochastic web-search discovery. Web evidence remains acceptable only when returned citations resolve to the allowed official URLs.
4. Create a corpus-ingestion session with `POST /sessions/`:

   ```json
   {
     "user_id": "chembiz-eval-v0.1.0",
     "user_query": "Ingest the ChemBiz materials evaluation corpus."
   }
   ```

5. Upload the frozen PDF files to that session with `POST /files/upload`. Preserve the returned filenames, file ids, content hashes, and your independently calculated SHA-256 checksums. Watch the `temporal-worker` logs and do not begin the scored runs until ingestion has completed:

   ```powershell
   docker compose -f docker/docker-compose.yaml logs -f temporal-worker
   ```

6. For each of the 12 entries in `questions.json`:
   - call `POST /sessions/` with the same `user_id` and copy the question exactly into `user_query`;
   - call `POST /runs/` with the returned `session_id` and the same `user_id`;
   - poll `GET /runs/{run_id}` until the status is terminal; and
   - call `GET /runs/{run_id}/output` to capture claims, citations, confidence, evidence gaps, and the tool trace.
7. Save the two JSON responses using the question id, for example `MAT-001.run.json` and `MAT-001.output.json`, under a new directory such as `evaluation/results/2026-09-26-v0.1.0/`.
8. Do not edit a question, retry only a poor answer, add documents midway, or change model/retrieval settings during a scored batch. If a run fails technically, record the failure and any full-batch rerun policy.
9. Review every result against `expected_evidence.json` and report the metrics below. Citation correctness and scientific support require human inspection of the cited passages.

Use a new dedicated `user_id` for a later benchmark version or materially different source corpus. Reusing a normal development user can contaminate retrieval with unrelated documents and makes the result difficult to reproduce.

After the evaluation corpus has been ingested for `chembiz-eval-v0.1.0`, run all frozen questions from the repository root:

```powershell
python evaluation/run_evaluation.py `
  --output-dir evaluation/results/YYYY-MM-DD-full-vNEXT
```

For a focused regression run, repeat `--question-id` for the cases to test:

```powershell
python evaluation/run_evaluation.py `
  --output-dir evaluation/results/YYYY-MM-DD-focused-vNEXT `
  --question-id MAT-005 `
  --question-id MAT-007 `
  --question-id MAT-008
```

The runner refuses to overwrite existing artifacts unless `--overwrite` is supplied. It creates a new session for each exact frozen question, polls the run to a terminal state, saves both endpoint responses, and writes `batch-manifest.json`.

## Minimum metrics

Report both per-question results and aggregate values:

- **Source retrieval success:** the response retrieved at least one required source.
- **Evidence coverage:** required evidence points supported by retrieved passages divided by all required evidence points.
- **Citation correctness:** citations that actually support their associated claims divided by citations checked.
- **Citation completeness:** supported material claims with citations divided by all material claims requiring citations.
- **Answer completeness:** required evidence points correctly addressed divided by all required evidence points.
- **Unsupported-claim rate:** material factual claims not supported by an allowed source divided by all material factual claims.
- **Abstention quality:** whether the system clearly identifies missing conditions or evidence instead of inventing an answer.

## Scoring rules

- A citation counts only if a reviewer can locate the supporting passage in the cited source.
- A source citation alone does not make a claim correct.
- Added specificity not present in the sources counts as unsupported, even if plausible.
- Brand names and generic material categories must not be treated as interchangeable unless the source establishes the equivalence.
- NIOSH protective-clothing recommendations must retain the source's concentration, duration, confirmation, and limitation language.
- Answers should distinguish screening information from a final engineering or safety recommendation.

## Planned next step

Add mechanical scoring and source-constraint checks to the runner. Automated scoring may assist reviewers, but citation correctness and scientific support should receive human review.
