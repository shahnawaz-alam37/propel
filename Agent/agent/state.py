
from typing import Optional, Annotated
from typing_extensions import TypedDict
import operator


class ResumeAgentState(TypedDict):
    # ---- Inputs ----
    raw_input: str                      # plain text from user OR extracted PDF text
    job_description: str                # raw JD pasted by user
    input_mode: str                     # "text" | "pdf"

    # ---- Parsed / enriched data ----
    jd_keywords: list[str]              # top keywords extracted from JD
    jd_role_title: str                  # e.g. "Senior Software Engineer"
    jd_company: str                     # e.g. "Google"
    candidate_summary: str              # structured summary of candidate experience

    # ---- LaTeX generation ----
    latex_source: str                   # current .tex source (evolves across retries)
    latex_version: int                  # increments on each rewrite

    # ---- Compilation ----
    compile_attempts: int               # how many times we've tried to compile
    compile_success: bool               # did the last compile succeed?
    compile_error: str                  # stderr from tectonic if it failed
    pdf_bytes: Optional[bytes]          # final PDF binary

    # ---- Agent control ----
    error: str                          # any fatal error message
    status: str                         # current phase label for the UI
    # Accumulated log messages (append-only via operator.add)
    logs: Annotated[list[str], operator.add]
