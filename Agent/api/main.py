# ============================================================
# api/main.py — FastAPI app exposing the LangGraph agent
# ============================================================

import asyncio
import logging
import io
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pdfplumber

from agent.graph import resume_graph
from agent.state import ResumeAgentState
from tools.resume_tools import check_compiler_health
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ResumeAI Agent",
    description="Agentic resume tailoring: JD → AI → LaTeX → PDF",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ================================================================
# REQUEST / RESPONSE MODELS
# ================================================================

class TextResumeRequest(BaseModel):
    candidate_text: str          # raw text describing candidate
    job_description: str
    stream_logs: bool = False


class ResumeResponse(BaseModel):
    success: bool
    message: str
    latex_source: Optional[str] = None
    jd_role_title: Optional[str] = None
    jd_company: Optional[str] = None
    keywords: Optional[list[str]] = None
    compile_attempts: int = 0
    logs: list[str] = []


# ================================================================
# HELPER
# ================================================================

def _run_agent(raw_input: str, job_description: str, input_mode: str) -> ResumeAgentState:
    initial_state: ResumeAgentState = {
        "raw_input": raw_input,
        "job_description": job_description,
        "input_mode": input_mode,
        "jd_keywords": [],
        "jd_role_title": "",
        "jd_company": "",
        "candidate_summary": "",
        "latex_source": "",
        "latex_version": 0,
        "compile_attempts": 0,
        "compile_success": False,
        "compile_error": "",
        "pdf_bytes": None,
        "error": "",
        "status": "starting",
        "logs": [],
    }
    final_state = resume_graph.invoke(
        initial_state,
        config={"recursion_limit": settings.max_agent_iterations}
    )
    return final_state


# ================================================================
# ROUTES
# ================================================================

@app.get("/health")
async def health():
    """Health check for this service + the compiler service."""
    compiler_status = check_compiler_health.invoke({})
    return {
        "agent_api": "ok",
        "compiler": compiler_status,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.resolved_model,
    }


@app.post("/generate/from-text")
async def generate_from_text(req: TextResumeRequest):
    """
    Generate a tailored PDF resume from raw text input.
    Returns the PDF file directly.
    """
    try:
        state = await asyncio.get_event_loop().run_in_executor(
            None, _run_agent, req.candidate_text, req.job_description, "text"
        )
    except Exception as e:
        raise HTTPException(500, f"Agent error: {str(e)}")

    if not state["compile_success"] or not state["pdf_bytes"]:
        raise HTTPException(422, {
            "error": "Resume generation failed",
            "last_error": state.get("compile_error", state.get("error", "")),
            "logs": state.get("logs", []),
        })

    return Response(
        content=state["pdf_bytes"],
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=resume.pdf",
            "X-Latex-Version": str(state.get("latex_version", 1)),
            "X-Compile-Attempts": str(state.get("compile_attempts", 1)),
            "X-JD-Role": state.get("jd_role_title", ""),
        }
    )


@app.post("/generate/from-pdf")
async def generate_from_pdf(
    pdf_file: UploadFile = File(...),
    job_description: str = Form(...),
):
    """
    Upload an existing resume PDF + paste a JD.
    Returns a new tailored PDF resume.
    """
    if not pdf_file.filename.endswith(".pdf"):
        raise HTTPException(400, "Only PDF files accepted")

    pdf_bytes = await pdf_file.read()
    pdf_hex = pdf_bytes.hex()   # pass as hex string to tool

    try:
        state = await asyncio.get_event_loop().run_in_executor(
            None, _run_agent, pdf_hex, job_description, "pdf"
        )
    except Exception as e:
        raise HTTPException(500, f"Agent error: {str(e)}")

    if not state["compile_success"] or not state["pdf_bytes"]:
        raise HTTPException(422, {
            "error": "Resume generation failed",
            "last_error": state.get("compile_error", state.get("error", "")),
            "logs": state.get("logs", []),
        })

    return Response(
        content=state["pdf_bytes"],
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=resume_tailored.pdf",
            "X-Compile-Attempts": str(state.get("compile_attempts", 1)),
            "X-JD-Role": state.get("jd_role_title", ""),
        }
    )


@app.post("/generate/latex-only", response_model=ResumeResponse)
async def generate_latex_only(req: TextResumeRequest):
    """
    Returns the LaTeX source + metadata without compiling.
    Useful for previewing / editing before PDF generation.
    """
    try:
        state = await asyncio.get_event_loop().run_in_executor(
            None, _run_agent, req.candidate_text, req.job_description, "text"
        )
    except Exception as e:
        raise HTTPException(500, str(e))

    return ResumeResponse(
        success=state.get("compile_success", False),
        message="LaTeX generated" if state.get("latex_source") else "Generation failed",
        latex_source=state.get("latex_source"),
        jd_role_title=state.get("jd_role_title"),
        jd_company=state.get("jd_company"),
        keywords=state.get("jd_keywords"),
        compile_attempts=state.get("compile_attempts", 0),
        logs=state.get("logs", []),
    )


@app.post("/compile/raw")
async def compile_raw_latex(latex: str = Form(...)):
    """
    Directly compile raw LaTeX source (bypass the agent).
    Useful for manual edits / re-compile after tweaking.
    """
    from tools.resume_tools import compile_latex
    result = compile_latex.invoke({"latex_source": latex})
    if result["success"]:
        return Response(
            content=bytes.fromhex(result["pdf_hex"]),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=resume.pdf"}
        )
    raise HTTPException(422, {"error": result["error"]})


# ================================================================
# ENTRYPOINT
# ================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
    )
