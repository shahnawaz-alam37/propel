# ResumeAI – Production-Grade Architecture & Implementation Roadmap

## Executive Summary

ResumeAI is an agentic pipeline that tailors resumes to specific job descriptions (JDs) using LLMs and LaTeX compilation. The current prototype has a single monolithic agent performing JD parsing, resume parsing, LaTeX generation, and compilation error recovery. While functional, it suffers from reliability issues (loops caused by extraneous tokens), lacks cost efficiency, and has no user management, monitoring, or history features.

This document outlines a **modular, production-ready architecture** designed for scalability, cost control, and a rich user experience. We propose splitting the single LLM call into a **multi‑step pipeline** with specialized, cheaper models, introducing **structured outputs**, comprehensive **monitoring**, **user profiles**, **versioned history**, and a **chat‑based refinement** interface. The system is built as a set of loosely coupled microservices, enabling independent scaling and maintenance.

---

## Current System Limitations

- **Single LLM handles all tasks**: expensive and prone to hallucinated or malformed outputs.
- **No structured output validation**: LLM may emit thinking tags (e.g., `[...]`, `</thinking>`) that break the LaTeX or cause infinite retry loops.
- **No user context**: no authentication, session, or personalisation.
- **No persistence**: each run is ephemeral; users cannot revisit or compare previous versions.
- **No monitoring or cost tracking**: usage and performance are invisible.
- **No chat/iteration**: once the PDF is generated, the user cannot request modifications.

---

## Proposed Architecture (High-Level)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             Frontend (React/Next.js)                        │
│  - Authentication (OAuth/Email)                                            │
│  - Dashboard: list of resumes, upload JD & resume, chat interface          │
│  - Version history viewer                                                  │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         API Gateway (FastAPI)                              │
│  - Route requests to appropriate services                                  │
│  - Authenticate & rate-limit                                               │
│  - Aggregate metrics for monitoring                                        │
└───────┬─────────────┬─────────────┬─────────────┬─────────────────────────┘
        │             │             │             │
        ▼             ▼             ▼             ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────────────────────┐
│   User &     │ │  Resume      │ │  JD &        │ │  Tailoring Engine     │
│   Auth       │ │  Storage     │ │  Resume      │ │  (LangGraph-based)    │
│   Service    │ │  Service     │ │  Parsing     │ │  - Orchestrates steps │
│              │ │              │ │  Service     │ │  - State management   │
│              │ │              │ │  (extract    │ │  - LLM calls          │
│              │ │              │ │   structured │ │  - Retry & fallback   │
│              │ │              │ │   data)      │ │                       │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────┬────────────┘
        │             │             │                          │
        └─────────────┼─────────────┼──────────────────────────┘
                      │             │
                      ▼             ▼
         ┌──────────────────────────────┐
         │  LaTeX Generation Service    │
         │  - Template rendering         │
         │  - Validation (lint)          │
         │  - Error fix suggestions      │
         └──────────────┬───────────────┘
                        │
                        ▼
         ┌──────────────────────────────┐
         │  Compilation Microservice    │
         │  (Tectonic / localhost:8001) │
         └──────────────────────────────┘
                        │
                        ▼
         ┌──────────────────────────────┐
         │  Storage (PostgreSQL + S3)   │
         │  - Users, profiles           │
         │  - Resume versions (PDF/TeX) │
         │  - JD metadata               │
         │  - Conversation history      │
         └──────────────────────────────┘
```

---

## Detailed Component Design

### 1. Frontend (React/Next.js)
- **Pages**: Login/Signup, Dashboard (list of resumes), Create New (upload JD + resume), View/Edit (chat interface), Settings.
- **Chat Interface**: Allows users to request changes (e.g., “emphasise leadership”, “shorten summary”). The backend interprets these as new runs with modified instructions.
- **Version Display**: Show a timeline of generated PDFs; allow download and comparison.

### 2. API Gateway & Authentication
- **FastAPI** with JWT authentication (optional OAuth2).
- Rate limiting per user (e.g., 10 requests/minute for heavy tasks).
- Centralised logging and request tracing (correlation IDs).

### 3. User & Auth Service
- Manages user profiles, API keys, quotas (free/paid tiers).
- Stores preferences (e.g., default template, preferred LLM models).

### 4. Resume Storage Service
- **PostgreSQL** tables:
  - `users`, `resumes`, `versions`, `jds`, `conversations`.
  - Each `version` stores a link to the generated PDF (S3) and the LaTeX source (S3 or DB).
- **S3** for large binary files (PDFs, uploaded resumes).

### 5. JD & Resume Parsing Service
- **Structured extraction** using Pydantic models.
- Uses a **cheap, fast model** (e.g., `llama3-70b-8192` on Groq) with **JSON mode** (or function calling) to ensure valid JSON output.
- Extracts: role, seniority, required skills, responsibilities, etc. from JD.
- Extracts: work experience, education, skills, projects from resume.

### 6. Tailoring Engine (LangGraph)
This is the heart of the system, now a directed state graph with explicit nodes:

```
[Start] → [Parse JD] → [Parse Resume] → [Generate LaTeX] → [Validate LaTeX] → [Compile] → [Success]
                     ↑                 ↓                   ↑                ↓
                     └───[Fix LaTeX]──┘ (if invalid)      └──[Fix LaTeX]──┘ (if compile fails)
```

- **Nodes**:
  - `parse_jd` / `parse_resume`: call the parsing service (or directly call LLM if lightweight).
  - `generate_latex`: uses a **more capable model** (e.g., `gpt-4o-mini` or `claude-3-haiku`) to generate the full `.tex` file from structured data, JD, and user instructions.
  - `validate_latex`: runs a quick syntax check (e.g., `chktex` or a simple regex) to catch obvious errors.
  - `compile`: calls the Tectonic microservice.
  - `fix_latex`: attempts to repair errors by feeding compiler output back to the LLM (using a cheaper model) – limit 3 attempts.
- **Retry logic**: Each node can have its own retry policy and fallback models (e.g., if `gpt-4o-mini` times out, try `gemini-flash`).
- **State**: The graph state holds all extracted data, intermediate LaTeX, compilation logs, and a history of changes.

### 7. LaTeX Generation Service
- **Templating engine** (Jinja2) that uses a base LaTeX template and injects sections.
- **Validator**: runs `tectonic --parse-only` or a custom linter to catch missing `\end{}`, unbalanced braces, etc.
- **Fix suggestions**: for common errors (e.g., missing `\usepackage`), the service can auto‑insert or prompt the LLM.

### 8. Compilation Microservice
- Existing Tectonic service on `localhost:8001`.
- Wrapped with a retry mechanism and timeout (e.g., 30s).
- Returns PDF as base64 or a URL.

### 9. Monitoring & Observability
- **Prometheus** metrics: request count, latency, token usage per user/model.
- **Loki** for structured logging (with correlation IDs).
- **LangSmith** or **LangFuse** for tracing LLM calls – captures prompts, responses, token counts, and latency.
- **Alerting**: set up alerts for high error rates, compilation failures, or quota breaches.

### 10. Token Control & Cost Optimisation
- **Per‑user daily/monthly limits** (enforced by the API gateway).
- **Per‑request max tokens** to prevent runaway generation.
- **Model selection**: use cheaper models for parsing and validation; only use expensive models for critical generation.
- **Caching**: cache parsed JD/resume structures for repeat requests (hash of inputs).
- **Batching**: if multiple users request similar JDs, reuse parsed data.

---

## Data Model (Simplified)

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email TEXT UNIQUE,
    password_hash TEXT,
    full_name TEXT,
    quota_tier TEXT DEFAULT 'free',
    created_at TIMESTAMP
);

CREATE TABLE resumes (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    name TEXT,                     -- user‑given label
    uploaded_resume_url TEXT,      -- S3 link to original PDF/DOCX
    parsed_data JSONB,             -- structured resume data
    created_at TIMESTAMP
);

CREATE TABLE job_descriptions (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    text TEXT,
    parsed_data JSONB,
    created_at TIMESTAMP
);

CREATE TABLE versions (
    id UUID PRIMARY KEY,
    resume_id UUID REFERENCES resumes(id),
    jd_id UUID REFERENCES job_descriptions(id),
    instructions TEXT,              -- user chat history context
    latex_source TEXT,
    pdf_url TEXT,
    compiler_log TEXT,
    status TEXT,                    -- 'pending', 'success', 'failed'
    token_usage JSONB,              -- breakdown per step
    created_at TIMESTAMP
);

CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    resume_id UUID,
    messages JSONB,                 -- array of {role, content}
    created_at TIMESTAMP
);
```

---

## LLM Strategy & Cost Efficiency

| Step                        | Model (Cheap)                         | Fallback Model               | Prompt Style          |
|-----------------------------|---------------------------------------|------------------------------|-----------------------|
| JD Parsing                  | `groq/llama3-70b-8192` (JSON mode)    | `gemini-1.5-flash`           | Few‑shot with schema  |
| Resume Parsing              | `groq/llama3-70b-8192` (JSON mode)    | `gemini-1.5-flash`           | Few‑shot with schema  |
| LaTeX Generation            | `openai/gpt-4o-mini`                  | `anthropic/claude-3-haiku`   | Multi‑shot + template |
| LaTeX Fix (error repair)    | `groq/llama3-70b-8192`                | `openai/gpt-3.5-turbo`       | Error+context         |
| Compilation                 | (no LLM)                              | –                            | –                     |

- **JSON mode** ensures structured output, eliminates extraneous text.
- **Temperature = 0** for parsing, **0.2** for generation to balance creativity.
- **Token limit** per call: 4096 for parsing, 8192 for generation.

---

## User Experience: Chat & Iteration

- **Conversation storage**: each thread of messages (user + assistant) is saved.
- **Refinement flow**:
  1. User uploads JD and resume, starts a new chat.
  2. System generates first version (PDF).
  3. User types a request (e.g., “Make the summary more concise”).
  4. The system appends the request to the conversation history, reruns the **tailoring engine** with new instructions, and produces a new version.
  5. The new version is stored as a separate version under the same resume.
- **Version branching**: allow users to revert to any previous version.

---

## Security Considerations

- **HTTPS** everywhere.
- **JWT** with short expiry, refresh tokens.
- **S3 pre‑signed URLs** for secure direct download.
- **Input sanitisation**: strip malicious LaTeX commands (e.g., `\write18`).
- **Rate limiting** to prevent abuse.
- **Compliance**: store user data in accordance with GDPR/CCPA (right to deletion).

---

## CI/CD & Deployment

- **Monorepo** with separate service folders.
- **Docker** containers for each service.
- **Kubernetes** (or Docker Compose for staging) for orchestration.
- **GitHub Actions** for tests, linting, and deployment.
- **Staging environment** mirrors production for pre‑release testing.

---

## GitHub Tickets (Issues)

### #1 – Correct JD & Resume Parsing System (with LLM)

**Goal:** Replace the brittle single‑LLM parsing with a robust, structured extraction service using cheap, JSON‑mode LLMs. Ensure no extra tokens (e.g., `</thinking>`) appear in the output.

**Subtasks:**

1.1 Define strict Pydantic schemas for JD and Resume (skills, experience, education, projects, etc.).

1.2 Build a `parse_jd` endpoint that:
  - Sends the raw JD text to `groq/llama3-70b-8192` with a system prompt enforcing JSON mode.
  - Validates the response against the schema; retry with a fallback model (`gemini-1.5-flash`) if parsing fails.

1.3 Build a `parse_resume` endpoint similarly, accepting PDF/DOCX (convert to text first) and returning structured data.

1.4 Add a caching layer (Redis) keyed by a hash of the input text to avoid repeated LLM calls for identical JDs/resumes.

1.5 Implement unit tests that mock LLM responses to verify validation and error recovery.

**Acceptance Criteria:**
- Both parsers return valid JSON that matches the schema 99% of the time.
- No malformed output (JSON parse errors) in production logs.

---

### #2 – Pass Data to LLM and Get Only LaTeX Code

**Goal:** The generation LLM must output only valid LaTeX (no markdown, no extra prose, no thinking tags). Enforce this via system prompts and post‑processing.

**Subtasks:**

2.1 Design a system prompt that explicitly instructs the model: "Output only the LaTeX source code, nothing else. Do not wrap it in ``` or include explanations."

2.2 Implement a post‑processing step that strips any leading/trailing text (e.g., using regex to extract content between `\begin{document}` and `\end{document}` if needed).

2.3 Add a `temperature=0` and `max_tokens` limit to avoid runaway generation.

2.4 Create a validation step that compiles with `tectonic --parse-only` to catch syntax errors before actual PDF generation; if it fails, trigger the fix loop (see #3).

2.5 Log all generated LaTeX for debugging and to build a dataset for fine‑tuning.

**Acceptance Criteria:**
- The LLM output can be fed directly to tectonic without manual cleanup in >95% of runs.
- Any remaining syntax errors are caught early and handled by the fix loop.

---

### #3 – New Architecture: Keyword Enrichment → LaTeX Generation

**Goal:** Break the monolithic LLM call into two stages:
- **Stage A** – An LLM enriches the parsed resume with keywords/phrases from the JD (ensuring ATS‑friendliness).
- **Stage B** – Another LLM (or the same, but with a different prompt) takes the enriched data and generates the final LaTeX.

This reduces the prompt complexity and allows using cheaper models for enrichment and a more capable one for generation.

**Subtasks:**

3.1 Design the enrichment prompt: given structured JD and resume, output only a JSON mapping of sections (e.g., "summary", "skills", "experience") with added keywords and rephrased bullets that align with the JD.

3.2 Use a cheap model (e.g., `groq/llama3-70b-8192`) for enrichment; enable JSON mode.

3.3 Design the LaTeX generation prompt: take the enriched JSON and a base LaTeX template, output only the full `.tex` file.

3.4 Use a slightly more capable model (e.g., `gpt-4o-mini` or `claude-3-haiku`) for generation, with post‑processing as in #2.

3.5 Compare quality and cost with the old monolithic approach; document findings (ADR).

3.6 Implement the fix loop that, on compilation error, feeds the error log back to the enrichment model (or a dedicated fix model) to correct the LaTeX.

**Acceptance Criteria:**
- The new architecture produces a valid PDF with equal or better keyword alignment than the old method.
- Cost per run is reduced by at least 30% (tracked via token usage).
- The fix loop handles common errors (missing `\end{}`, misplaced `&` in tables) within 3 attempts.

---

### #4 – UI with Next.js

**Goal:** Build a modern, responsive web interface that allows users to upload JDs and resumes, trigger the pipeline, and view/download the resulting PDF. Also provide a chat interface for iterative refinement.

**Subtasks:**

4.1 Set up a Next.js project with TypeScript, Tailwind CSS, and shadcn/ui components.

4.2 Implement landing page with sign‑up / login (integrate with API).

4.3 Build a dashboard showing the user's saved resumes and JDs, with options to create a new run.

4.4 Create an upload workflow:
  - Drag‑and‑drop for resume (PDF/DOCX) and JD (plain text or file).
  - Form to add optional instructions (e.g., "emphasise leadership").
  - Button to start the tailoring process, with a loading indicator and polling for progress.

4.5 Build a PDF viewer (e.g., using `react-pdf`) to preview the generated resume without downloading.

4.6 Implement a chat panel alongside the PDF preview (see #6) for requesting changes.

**Acceptance Criteria:**
- Users can upload files, start the pipeline, and see the resulting PDF within 2 minutes (UI feedback is smooth).
- The UI is mobile‑friendly and passes basic accessibility checks.

---

### #5 – User Login & Profile

**Goal:** Provide secure authentication and personalisation.

**Subtasks:**

5.1 Implement JWT‑based authentication in the backend (FastAPI) with sign‑up, login, and refresh tokens.

5.2 Add OAuth2 social login (Google, GitHub) using `fastapi-users` or `authlib`.

5.3 Create user profile endpoints (view/update name, email, quota tier).

5.4 In the frontend, protect routes with middleware that checks token validity.

5.5 Store user preferences (e.g., default LaTeX template, preferred model) in the database.

**Acceptance Criteria:**
- Users can register, log in, and stay authenticated across sessions.
- Profile changes are reflected immediately.

---

### #6 – Data Persistence & History with Chat Compilations

**Goal:** Store all user data (resumes, versions, conversations) and allow browsing history, version comparison, and iterative chat‑based refinement.

**Subtasks:**

6.1 Design the database schema (PostgreSQL) for: users, resumes, job_descriptions, versions (with LaTeX source and PDF URL), conversations (message history).

6.2 Implement versioning:
  - Each run creates a new version linked to a resume and a JD.
  - Store the enriched data, the final LaTeX, and the PDF (S3).
  - API endpoints to list versions, download PDF/TeX, and delete.

6.3 Implement conversation storage:
  - When a user chats, each message (user and assistant) is saved.
  - The assistant's messages can reference a specific version.

6.4 In the frontend, display a version timeline with thumbnails, and allow users to switch between versions.

6.5 Implement a chat interface that:
  - Sends user requests (e.g., "shorten the summary") to the backend.
  - The backend appends the request to the conversation history and triggers a new pipeline run with those instructions.
  - The new version appears in the timeline, and the chat updates with the assistant's response.

6.6 Add a "revert to this version" feature that copies a previous version's LaTeX and re‑compiles (without LLM) for quick restoration.

**Acceptance Criteria:**
- All history is persistent; users can see all past versions and conversations.
- Chat‑based modifications produce new versions without losing older ones.
- Performance is acceptable even with hundreds of versions per user (pagination, lazy loading).

---