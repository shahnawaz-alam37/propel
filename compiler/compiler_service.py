"""
compiler_service.py — Tectonic LaTeX → PDF microservice
POST /compile  { "latex": "..full tex source.." }  → PDF bytes
GET  /health   → { "status": "ok" }
"""

import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
import anyio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

app = FastAPI(title="LaTeX Compiler Service", version="1.0.0")

TECTONIC_BIN = "tectonic"
MAX_LATEX_SIZE = int(os.environ.get("MAX_LATEX_SIZE", "160000"))
COMPILER_TIMEOUT = int(os.environ.get("COMPILER_TIMEOUT", "180"))
MAX_FILENAME_LEN = 64
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "ALLOWED_ORIGINS",
        "http://localhost:8002,http://127.0.0.1:8002",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

logger = logging.getLogger("compiler_service")


class CompileRequest(BaseModel):
    latex: str
    filename: str = "resume"


@app.get("/health")
def health():
    return {"status": "ok", "compiler": "tectonic"}


def sanitize_filename(name: str) -> str:
    cleaned = SAFE_FILENAME_RE.sub("_", name).strip("._")
    if not cleaned:
        return "resume"
    return cleaned[:MAX_FILENAME_LEN]


def _run_tectonic(latex_source: str, filename: str) -> bytes:
    """
    Accepts LaTeX source, returns PDF bytes.
    Raises 400 on compile error with stderr details.
    """
    # Work in a temp directory — isolated per request
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = Path(tmpdir) / f"{filename}.tex"
        tex_path.write_text(latex_source, encoding="utf-8")

        try:
            result = subprocess.run(
                [
                    TECTONIC_BIN,
                    "--outdir", tmpdir,
                    "--keep-logs",          # keep for debugging
                    "--print",              # print status to stdout
                    str(tex_path),
                ],
                capture_output=True,
                text=True,
                timeout=COMPILER_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(408, "Compilation timed out")
        except FileNotFoundError:
            raise HTTPException(500, "Tectonic binary not found")

        pdf_path = Path(tmpdir) / f"{filename}.pdf"

        if result.returncode != 0 or not pdf_path.exists():
            # Return LaTeX error details to caller
            error_detail = result.stderr or result.stdout or "Unknown compile error"
            logger.warning("LaTeX compilation failed", extra={"output": error_detail[:3000]})
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "LaTeX compilation failed",
                    "compiler_output": error_detail[:3000],  # cap size
                }
            )

        pdf_bytes = pdf_path.read_bytes()

    return pdf_bytes


@app.post("/compile")
async def compile_latex(req: CompileRequest):
    if len(req.latex) > MAX_LATEX_SIZE:
        raise HTTPException(413, "LaTeX source too large")

    safe_filename = sanitize_filename(req.filename)
    pdf_bytes = await anyio.to_thread.run_sync(_run_tectonic, req.latex, safe_filename)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}.pdf"',
            "X-Compiler": "tectonic",
        }
    )


# -------------------------------------------------------
# Python client helper (call this from your main backend)
# -------------------------------------------------------
# import httpx
#
# async def latex_to_pdf(latex_source: str, filename: str = "resume") -> bytes:
#     async with httpx.AsyncClient() as client:
#         resp = await client.post(
#             "http://compiler-service:8001/compile",
#             json={"latex": latex_source, "filename": filename},
#             timeout=90.0
#         )
#         if resp.status_code != 200:
#             raise Exception(f"Compile failed: {resp.json()}")
#         return resp.content  # PDF bytes