# ============================================================
# tools/resume_tools.py — LangChain tools called by agent nodes
# ============================================================

import httpx
import pdfplumber
import io
from langchain_core.tools import tool
from config.settings import settings


# -------------------------------------------------------
# TOOL 1: Extract text from PDF bytes
# -------------------------------------------------------
@tool
def extract_pdf_text(pdf_bytes_hex: str) -> str:
    """
    Extracts raw text from a PDF resume.
    Input: hex-encoded PDF bytes string.
    Returns: plain text of the resume.
    """
    pdf_bytes = bytes.fromhex(pdf_bytes_hex)
    text_parts = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n\n".join(text_parts) if text_parts else ""


# -------------------------------------------------------
# TOOL 2: Compile LaTeX → PDF via the Tectonic microservice
# -------------------------------------------------------
@tool
def compile_latex(latex_source: str) -> dict:
    """
    Sends LaTeX source to the Tectonic compiler service.
    Returns: {"success": bool, "pdf_hex": str | None, "error": str | None}
    pdf_hex is the hex-encoded PDF bytes on success.
    """
    try:
        response = httpx.post(
            f"{settings.compiler_url}/compile",
            json={"latex": latex_source, "filename": "resume"},
            timeout=settings.compiler_timeout,
        )
        if response.status_code == 200:
            return {
                "success": True,
                "pdf_hex": response.content.hex(),
                "error": None,
            }
        else:
            err = response.json()
            return {
                "success": False,
                "pdf_hex": None,
                "error": err.get("detail", {}).get("compiler_output", str(err)),
            }
    except httpx.ConnectError:
        return {
            "success": False,
            "pdf_hex": None,
            "error": "Cannot connect to compiler service at localhost:8001. Is it running?",
        }
    except Exception as e:
        return {"success": False, "pdf_hex": None, "error": str(e)}


# -------------------------------------------------------
# TOOL 3: Health check on compiler
# -------------------------------------------------------
@tool
def check_compiler_health() -> dict:
    """Pings the Tectonic compiler service health endpoint."""
    try:
        r = httpx.get(f"{settings.compiler_url}/health", timeout=5)
        return r.json()
    except Exception as e:
        return {"status": "error", "detail": str(e)}
