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

### Epic 1: Foundation & Data Layer
- **#1** [Backend] Design database schema (PostgreSQL) – create migrations.
- **#2** [Backend] Implement User & Auth Service (JWT, login/signup).
- **#3** [Backend] Implement Resume Storage Service (S3 integration, version storage).
- **#4** [Backend] Set up base FastAPI project with routing, middleware, health checks.

### Epic 2: Core Pipeline Refactoring
- **#5** [Agent] Refactor single‑LLM pipeline into modular LangGraph workflow.
- **#6** [Agent] Implement JD parsing node with structured JSON output (Groq).
- **#7** [Agent] Implement Resume parsing node with structured JSON output.
- **#8** [Agent] Implement LaTeX generation node with templating and GPT‑4o-mini.
- **#9** [Agent] Implement LaTeX validation node (syntax check).
- **#10** [Agent] Implement compilation node (Tectonic client).
- **#11** [Agent] Implement error recovery loop (fix LaTeX up to 3 attempts).
- **#12** [Agent] Add retry/fallback logic for each node (model switching).

### Epic 3: Chat & Version History
- **#13** [Backend] Create conversation endpoints (save/retrieve messages).
- **#14** [Backend] Version management – list, get, download PDF.
- **#15** [Agent] Integrate conversation context into the tailoring engine (instructions from chat).
- **#16** [Frontend] Build chat UI component with message history and PDF preview.

### Epic 4: Monitoring & Observability
- **#17** [Ops] Set up Prometheus metrics endpoint in FastAPI.
- **#18** [Ops] Integrate Loki for structured logging.
- **#19** [Ops] Add LangSmith/LangFuse tracing for all LLM calls.
- **#20** [Backend] Implement token usage tracking per request/user and expose via admin API.
- **#21** [Backend] Implement per‑user quota enforcement (daily/monthly limits).

### Epic 5: User Interface (Frontend)
- **#22** [Frontend] Authentication pages (login, signup, password reset).
- **#23** [Frontend] Dashboard showing user's resumes and JD list.
- **#24** [Frontend] Upload workflow: drag‑and‑drop for resume + JD, start tailoring.
- **#25** [Frontend] Version view with PDF preview and version timeline.
- **#26** [Frontend] Chat panel to request modifications and see new versions generated.
- **#27** [Frontend] User settings (quota, model preferences).

### Epic 6: Production Readiness
- **#28** [Ops] Dockerize all services (write Dockerfiles and compose files).
- **#29** [Ops] Set up Kubernetes manifests or Helm charts for deployment.
- **#30** [Ops] Configure CI/CD pipeline (GitHub Actions) with tests, security scans, deployment.
- **#31** [Backend] Implement caching for parsed JD/resume (Redis) to reduce LLM calls.
- **#32** [Security] Add input sanitisation for LaTeX, rate limiting, and HTTPS configuration.

### Epic 7: Testing & Documentation
- **#33** [Tests] Write unit tests for each service (parsing, generation, validation).
- **#34** [Tests] Integration tests for the full pipeline (mock LLM).
- **#35** [Docs] API documentation (OpenAPI) and user manual.
- **#36** [Docs] Architecture decision record (ADR) for model selection and cost strategy.

---