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
OLLAMA_LLM_TIMEOUT_SECONDS=165
OLLAMA_LLM_NUM_CTX=10240
OLLAMA_LLM_NUM_PREDICT=4608
OLLAMA_LLM_SAFETY_MARGIN=256
CV_EXTRACTION_TOTAL_TIMEOUT_SECONDS=230
CV_EXTRACTION_CORRECTION_MIN_SECONDS=60
CV_EXTRACTION_NETWORK_MARGIN_SECONDS=20
```

Structured CV extraction reserves the output cap and safety margin before generation
when authoritative counting is available. Local Windows/Ollama0.34.2 uses render-only
plus the same model's native tokenizer. If unavailable, character estimates are
diagnostic only: a verified runtime enforces `shift=false`, `truncate=false` and
`num_predict`. Unknown runtime safety is a typed readiness error, not a CV-size claim.

The total deadline covers document reading, preflight, generation, validation and at
most one correction, which requires60s remaining. Candidate clients read
`GET /api/v1/candidate/cvs/extraction-policy` for operation/request timeouts (default
230s+20s margin). Context/output/deadline failures are terminal; no automatic limit
increase or bulk retry. Installed Qwen metadata supports40960; extraction now uses
explicit10240 with the same output/deadline budgets. BGE-M3 remains8192/4096.

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
EMBEDDING_NUM_CTX=8192
EMBEDDING_NUM_BATCH=4096
```

For a local smoke check, install Ollama, run `ollama pull bge-m3`, and start the
Ollama service. Automated tests mock the HTTP transport and never require Ollama
or network access.

## Persisted CV/job matches

Candidate and recruiter detail workflows can request an on-demand CV/job match.
The backend stores one current derived result per CV/job pair and reuses it only
while deterministic matching fingerprints, engine versions, provider, model and embedding profile(context included)
remain current. Baseline evidence and raw semantic similarity stay separate.

Only the validated baseline result and semantic scalar/metadata are persisted.
Canonical text and raw embedding vectors are never stored, and this feature does
not require pgvector. Candidate access is limited to an owned CV and approved Job;
Recruiter access is limited to the CV referenced by an application for an owned Job.

## Opt-in recruiter applicant AI ordering

Existing applicant GET endpoints preserve `created_at DESC, id DESC` by default.
`sort=ai_match` orders the complete owner/business-filtered set using cached BGE-M3
vectors and raw cosine, then paginates. No embedding/extraction is performed by GET.
Ranked applicants precede pending/unavailable/error applicants; all remain accessible
unless the caller explicitly supplies `ai_top_n=N`. `page_size` is transport only.
Cosine is NOT a percentage, probability, eligibility rule or hiring decision.

AI page 1 returns `ranking_snapshot`; pass the same token, filters, page_size and
ai_top_n on subsequent pages. Its ten-minute order and availability view stays fixed
when precompute finishes. Membership/status/canonical/profile changes return 409;
restart at page 1. Expiration also returns 409. AI page >1 without token returns 422.
Default pages retain existing semantics and need no token.

After CV create/update, successful extraction/confirmation, and recruiter job
create/update, a best-effort BackgroundTask precomputes ONE entity. It owns a fresh
DB session, closes it before provider work, invokes no extraction, and performs at
most one `/api/embed` request. A cache hit makes no provider request. This is not a
durable queue: failed/crashed work may remain pending/error until another lifecycle
event or an operator invokes `precompute_entity(kind, UUID)` for that one entity.
Old unchanged entities are not automatically backfilled by list requests.

Private production storage: `RANKING_CACHE_ROOT=.cache/recruiter-ranking` (ignored,
never under a public/static directory). Share this root between workers of one
deployment and restrict OS access to the service account; snapshots/vectors are
private derived data. It must NOT point to evaluation caches. Expired snapshots are
removed when accessed; operators should periodically remove expired snapshots and
obsolete vector identities under this dedicated root. Crash leases require verified
operator cleanup, not automatic takeover. No migration or pgvector is required.

`RANKING_MODEL_DIGEST` pins the verified BGE-M3 digest (current default
`7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab`). Precompute verifies
it against local Ollama tags before and after generation. Model replacement requires
an explicit pin update and new cache identities. The shared frozen request remains
8192 context,4096 physical batch,truncate=false,1024 dimensions. List performs no
runtime model discovery; a compatible cached vector is tied to this deployment pin.
