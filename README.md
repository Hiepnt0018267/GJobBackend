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
uses native JSON structured output and the final payload is always validated by
Pydantic. This low-level operation does not score candidates, persist prompts or
raw provider responses, expose a generic AI endpoint, or process Builder CVs.

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
