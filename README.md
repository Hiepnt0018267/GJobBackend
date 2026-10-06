## Running backend tests safely

Pytest requires a dedicated PostgreSQL database through `TEST_DATABASE_URL`.
It never falls back to `DATABASE_URL`.

1. Create a separate database whose name ends with `_test`.
2. Copy the example from `.env.test.example` into your local `.env` and use
   the real local credentials.
3. Run `pytest` normally. The test bootstrap validates the target, applies all
   Alembic migrations to the test database, and overrides FastAPI's `get_db`.

Pytest stops before collecting tests if the test URL is missing, resolves to
the development database, or does not follow the `_test` naming policy.

## Uploaded CV text extraction

The backend can internally extract normalized text from uploaded PDF and DOCX
CVs through `CVTextExtractionService`. Raw text stays in memory and is not logged
or persisted. Image-only/scanned PDFs require OCR, which is not supported yet.

## Structured uploaded CV extraction

`CVStructuredExtractionService` converts normalized uploaded-CV text into the
existing Builder-compatible CV shape using the configured AI provider. Gemini
uses native JSON structured output; local Ollama uses `/api/chat` with the same
Pydantic JSON Schema and `qwen3:8b`. The final payload is always validated by
Pydantic. This low-level operation does not score candidates, persist prompts or
raw provider responses, expose a generic AI endpoint, or process Builder CVs.

Choose one generation provider explicitly; there is no silent cross-provider
fallback:

```env
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_LLM_MODEL=qwen3:8b
OLLAMA_LLM_TIMEOUT_SECONDS=90
OLLAMA_LLM_NUM_CTX=8192
```

For the initial 8 GB GPU deployment, run Ollama with `OLLAMA_NUM_PARALLEL=1`.
The API sends `think=false`, `temperature=0`, and rejects a result when Ollama's
reported prompt token count reaches 95% of the configured context. Raw CV text,
prompts, provider bodies, and thinking traces are not logged or persisted.

## Persistent CV extraction drafts

Uploaded CV extraction attempts are stored in `cv_extractions` as owned,
unconfirmed AI drafts. The table stores lifecycle status, validated structured
JSON, provider/model metadata, and safe failure categories. It never stores raw
document text, prompts, raw provider responses, or secrets. Candidate review and
confirmation remain a separate future workflow.

Candidates can explicitly confirm a reviewed successful extraction. Confirmation
atomically replaces the eight structured CV sections and records `confirmed_at`;
the historical AI `structured_result` remains unchanged. Builder CVs, incomplete
attempts, and older extraction attempts cannot use this workflow.

## Canonical CV/JD matching inputs

Future matching consumes deterministic canonical inputs instead of ORM, JSONB,
uploaded-file, or AI-provider shapes. Builder CVs are immediately eligible;
uploaded CVs require candidate-confirmed structured data. Job skills prefer the
normalized `skills`/`job_skills` taxonomy with a legacy array fallback. Semantic
text excludes names, contact details, photos, locations, salary, company identity,
and recruiter data. No score, embedding, external AI call, or persistence is part
of this foundation.

`baseline-v1` builds on those canonical inputs with one defensible component:
explicit normalized Job-skill coverage against CV skills and project technologies.
It returns deterministic matched/missing evidence and factual explanations. Missing
signals are never converted into an arbitrary score. The result is feature
compatibility—not hiring probability, candidate quality, or a hiring recommendation.
The engine performs no database, LLM, embedding, or network operation.

## Semantic CV/JD matching

`semantic-v1` compares the existing privacy-filtered canonical CV and job text
with one ordered embedding batch. The default adapter calls a local Ollama
instance at `POST /api/embed` using `bge-m3`, disables truncation, validates both
vectors strictly, and returns raw cosine similarity in `[-1, 1]`. It does not
persist vectors, expose a raw embedding route, combine scores, or make hiring
decisions.

Optional environment settings:

```env
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=bge-m3
OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING_TIMEOUT_SECONDS=30
```

For a local smoke check, install Ollama, run `ollama pull bge-m3`, and start the
Ollama service. Automated tests mock the HTTP transport and never require Ollama
or network access.

## Persisted CV/job matches

Candidate and recruiter detail workflows can request an on-demand CV/job match.
The backend stores one current derived result per CV/job pair and reuses it only
while deterministic matching fingerprints, engine versions, provider, and model
remain current. Baseline evidence and raw semantic similarity stay separate.

Only the validated baseline result and semantic scalar/metadata are persisted.
Canonical text and raw embedding vectors are never stored, and this feature does
not require pgvector. Candidate access is limited to an owned CV and approved Job;
Recruiter access is limited to the CV referenced by an application for an owned Job.
