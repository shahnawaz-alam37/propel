# ResumeAI Agent

Agentic resume tailoring pipeline built with **LangGraph + LangChain**, using any **OpenAI-compatible LLM** (Groq, Gemini, Qwen, OpenAI, future Codex), compiling LaTeX to PDF via the **Tectonic microservice**.

## Project Structure

```
resume_agent/
├── agent/
│   ├── graph.py          ← LangGraph state machine (the brain)
│   ├── state.py          ← Typed state that flows through every node
│   ├── llm_factory.py    ← Single place to swap LLM providers
│   └── prompts.py        ← All system/human prompts
├── tools/
│   └── resume_tools.py   ← LangChain tools: PDF extract, compile, health check
├── api/
│   └── main.py           ← FastAPI endpoints
├── config/
│   └── settings.py       ← Pydantic settings (reads from .env)
├── test_agent.py         ← Smoke test
├── requirements.txt
└── .env.example
```

## Setup

```bash
# 1. Clone / copy this folder
cd resume_agent

# 2. Create virtualenv
python -m venv .venv && source .venv/bin/activate

# 3. Install deps
pip install -r requirements.txt

# 4. Configure
cp .env.example .env
# Edit .env — set LLM_PROVIDER and LLM_API_KEY

# 5. Make sure the Tectonic compiler is running
docker run -p 8001:8001 your-tectonic-image

# 6. Run the agent API
python -m api.main
# or:
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
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
