# ResumeAI Agent

Agentic resume tailoring pipeline built with **LangGraph + LangChain**, using any **OpenAI-compatible LLM** (Groq, Gemini, Qwen, OpenAI, future Codex), compiling LaTeX to PDF via the **Tectonic microservice**.

## Project Structure

```
.
├── Agent/                     ← LangGraph agent (FastAPI)
│   ├── agent/
│   │   ├── graph.py          ← LangGraph state machine (the brain)
│   │   ├── state.py          ← Typed state that flows through every node
│   │   ├── llm_factory.py    ← Single place to swap LLM providers
│   │   └── prompts.py        ← All system/human prompts
│   ├── tools/
│   │   └── resume_tools.py   ← LangChain tools: PDF extract, compile, health check
│   ├── api/
│   │   └── main.py           ← FastAPI endpoints (port 8000)
│   ├── config/
│   │   └── settings.py       ← Pydantic settings (reads from .env)
│   ├── test_agent.py         ← Smoke test
│   ├── requirements.txt
│   └── .env
├── compiler/                  ← Tectonic LaTeX → PDF microservice
│   ├── Dockerfile             ← Docker image (port 8001)
│   └── compiler_service.py    ← FastAPI service
├── compiler-testing-ui/       ← Browser UI for testing the compiler
│   ├── serve.py               ← Static file server (port 8002)
│   ├── index.html
│   ├── styles.css
│   └── app.js
└── Readme.md
```

## Setup — Agent API

```bash
# 1. Navigate to the Agent directory
cd Agent

# 2. Create virtualenv
python -m venv .venv && source .venv/bin/activate

# 3. Install deps
pip install -r requirements.txt

# 4. Configure
cp .env.example .env
# Edit .env — set LLM_PROVIDER and LLM_API_KEY

# 5. Run the agent API (after starting the compiler — see below)
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

## Running All Servers

Three services must be running for the full pipeline. Each runs on a different port:

| Service | Port | Directory | Purpose |
|---------|------|-----------|---------|
| Agent API | `8000` | `Agent/` | LangGraph agent with FastAPI endpoints |
| Compiler | `8001` | `compiler/` | Tectonic LaTeX → PDF microservice (Docker) |
| Test UI | `8002` | `compiler-testing-ui/` | Browser UI to manually test the compiler |

### 1. Compiler service (Docker, port 8001)

Build and run the Tectonic compiler container:

```bash
# From the repo root
cd compiler
docker build -t resume-compiler .
docker run --rm -p 8001:8001 resume-compiler
```

Verify: `curl http://localhost:8001/health` → `{"status":"ok","compiler":"tectonic"}`

### 2. Agent API (port 8000)

With the compiler running, start the agent:

```bash
cd Agent
# Ensure .env has COMPILER_URL=http://localhost:8001
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Verify: `curl http://localhost:8000/health` → compiler status should show `"ok"`

### 3. Compiler Test UI (port 8002)

A lightweight browser UI for sending LaTeX to the compiler and downloading the PDF:

```bash
cd compiler-testing-ui
python serve.py
```

Open http://localhost:8002 in a browser.

### Stopping everything

```bash
docker stop <container-id>      # stop the compiler
Ctrl+C                          # stop agent and test UI
```

## Switching LLM Providers

Edit `.env`:

| Provider | LLM_PROVIDER | LLM_API_KEY |
|---|---|---|
| Groq | `groq` | Groq API key |
| Google Gemini | `gemini` | Gemini API key |
| Alibaba Qwen | `qwen` | DashScope API key |
| OpenAI | `openai` | OpenAI API key |
| Future Codex | `codex` | (TBD) |

Example `.env` for Groq:

```bash
LLM_PROVIDER=groq
LLM_MODEL=qwen/qwen3-32b
```

No code changes needed — the `llm_factory.py` handles routing.

## Example Contents for `.env`

```bash
# ---- LLM Provider ----
# Options: groq | gemini | qwen | openai | codex
LLM_PROVIDER=gemini

# API key for the selected provider
LLM_API_KEY=

# (Optional) Override the default model for your provider
# LLM_MODEL=gemini-2.5-flash

# ---- Compiler service ----
COMPILER_URL=http://localhost:8001

# ---- Agent behaviour ----
MAX_COMPILE_RETRIES=3
LLM_TEMPERATURE=0.2

# ---- App ----
APP_PORT=8000
DEBUG=false
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Agent + compiler health |
| POST | `/generate/from-text` | Text input → PDF |
| POST | `/generate/from-pdf` | Uploaded resume PDF + JD → new PDF |
| POST | `/generate/latex-only` | Text input → LaTeX source (no compile) |
| POST | `/compile/raw` | Raw LaTeX → PDF (bypasses agent) |

## Agent Flow

```
START
  ↓
parse_jd          — LLM extracts keywords, role title, seniority from JD
  ↓
parse_candidate   — LLM structures resume text/PDF into JSON
  ↓
generate_latex    — LLM writes complete .tex file, injecting all JD keywords
  ↓
compile           — POST to localhost:8001/compile (Tectonic)
  ↓ success              ↓ error (up to 3 retries)
  END (PDF)         fix_latex → compile → ...
```

## Quick test

```bash
python test_agent.py
# Outputs test_output.pdf (or test_output.tex if compiler not running)
```
