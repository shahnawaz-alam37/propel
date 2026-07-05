# ============================================================
# agent/graph.py — the LangGraph agentic workflow
#
# Graph topology:
#
#  START
#    │
#    ▼
#  parse_jd ──────────────────────────────────────────────┐
#    │                                                     │
#    ▼                                                     │
#  parse_candidate                                         │
#    │                                                     │
#    ▼                                                     │
#  generate_latex                                          │
#    │                                                     │
#    ▼                                                     │
#  compile ──[success]──▶ END                              │
#    │                                                     │
#    └──[error + retries left]──▶ fix_latex ──────────────┘
#                                     │
#                            [retries exhausted]──▶ END(error)
# ============================================================

import json
import logging
import re
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

from agent.state import ResumeAgentState
from agent.llm_factory import get_llm
from agent.parser import _call_llm_json, ParsingError
from agent.prompts import (
    GENERATE_LATEX_SYSTEM, GENERATE_LATEX_HUMAN,
    FIX_LATEX_SYSTEM, FIX_LATEX_HUMAN,
)
from api.schemas import JDStructuredOutput, ResumeStructuredOutput
from tools.resume_tools import compile_latex, extract_pdf_text
from config.settings import settings

logger = logging.getLogger(__name__)


# ================================================================
# HELPERS
# ================================================================

def _call_llm(system: str, human: str) -> str:
    """Single LLM call — returns the text response."""
    llm = get_llm()
    messages = [SystemMessage(content=system), HumanMessage(content=human)]
    response = llm.invoke(messages)
    return response.content.strip()


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _strip_think(text: str) -> str:
    return _THINK_RE.sub("", text).strip()


def _strip_fences(text: str) -> str:
    clean = text.strip()
    if clean.startswith("```"):
        lines = clean.split("\n")
        clean = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
    return clean.strip()


def _clean_latex_output(text: str) -> str:
    clean = _strip_fences(_strip_think(text))
    doc_start = clean.find("\\documentclass")
    if doc_start == -1:
        doc_start = clean.find("% RESUME")
    if doc_start > 0:
        clean = clean[doc_start:]
    return clean.strip()


# ================================================================
# NODE 1 — parse_jd
# Extracts structured data from the job description
# ================================================================

def node_parse_jd(state: ResumeAgentState) -> dict:
    logger.info("Node: parse_jd")

    jd_schema_str = json.dumps(JDStructuredOutput.model_json_schema(), indent=2)
    system_prompt = (
        "You are a precise job description analyst.\n"
        "Extract structured information from the job description.\n"
        "You MUST return ONLY valid JSON matching this schema:\n"
        f"{jd_schema_str}\n"
        "Do not return any explanations, markdown code blocks, or preamble. Return ONLY the JSON object."
    )
    human_prompt = f"Extract structured information from this job description:\n\n{state['job_description']}"

    try:
        parsed = _call_llm_json(system_prompt, human_prompt, JDStructuredOutput)
    except ParsingError:
        parsed = {}

    return {
        "jd_keywords": parsed.get("keywords", []),
        "jd_role_title": parsed.get("role_title", "Software Engineer"),
        "jd_company": parsed.get("company", ""),
        "status": "jd_parsed",
        "logs": [f"JD parsed: role={parsed.get('role_title')}, "
                 f"{len(parsed.get('keywords', []))} keywords extracted"],
        "_jd_json": json.dumps(parsed, indent=2),
    }


# ================================================================
# NODE 2 — parse_candidate
# Structures raw resume text or user-provided details
# ================================================================

def node_parse_candidate(state: ResumeAgentState) -> dict:
    logger.info("Node: parse_candidate")

    candidate_text = state["raw_input"]

    if state.get("input_mode") == "pdf":
        pdf_text = extract_pdf_text.invoke({"pdf_bytes_hex": candidate_text})
        candidate_text = pdf_text

    resume_schema_str = json.dumps(ResumeStructuredOutput.model_json_schema(), indent=2)
    system_prompt = (
        "You are a precise resume parser.\n"
        "Extract structured professional information from the resume text.\n"
        "You MUST return ONLY valid JSON matching this schema:\n"
        f"{resume_schema_str}\n"
        "Do not return any explanations, markdown code blocks, or preamble. Return ONLY the JSON object."
    )
    human_prompt = f"Parse this candidate data into structured JSON:\n\n{candidate_text}"

    try:
        parsed = _call_llm_json(system_prompt, human_prompt, ResumeStructuredOutput)
    except ParsingError:
        parsed = {}

    name = parsed.get("full_name", "Candidate")
    return {
        "candidate_summary": json.dumps(parsed, indent=2),
        "status": "candidate_parsed",
        "logs": [f"Candidate parsed: {name}, "
                 f"{len(parsed.get('experiences', []))} jobs, "
                 f"{len(parsed.get('projects', []))} projects"],
    }


# ================================================================
# NODE 3 — generate_latex
# Writes the full .tex file tailored to the JD
# ================================================================

def node_generate_latex(state: ResumeAgentState) -> dict:
    logger.info("Node: generate_latex")

    jd_json = state.get("_jd_json", "{}")
    keywords_str = ", ".join(state.get("jd_keywords", []))

    latex = _call_llm(
        GENERATE_LATEX_SYSTEM,
        GENERATE_LATEX_HUMAN.format(
            candidate_json=state["candidate_summary"],
            jd_json=jd_json,
            keywords=keywords_str,
        )
    )

    latex = _clean_latex_output(latex)

    version = state.get("latex_version", 0) + 1
    return {
        "latex_source": latex,
        "latex_version": version,
        "compile_attempts": 0,
        "status": "latex_generated",
        "logs": [f"LaTeX v{version} generated ({len(latex)} chars)"],
    }


# ================================================================
# NODE 4 — compile
# Sends LaTeX to the Tectonic microservice
# ================================================================

def node_compile(state: ResumeAgentState) -> dict:
    logger.info("Node: compile (attempt %d)", state.get("compile_attempts", 0) + 1)

    result = compile_latex.invoke({"latex_source": state["latex_source"]})
    attempts = state.get("compile_attempts", 0) + 1

    if result["success"]:
        pdf_bytes = bytes.fromhex(result["pdf_hex"])
        return {
            "compile_success": True,
            "compile_error": "",
            "compile_attempts": attempts,
            "pdf_bytes": pdf_bytes,
            "status": "compiled",
            "logs": [f"Compile succeeded on attempt {attempts} "
                     f"({len(pdf_bytes):,} bytes PDF)"],
        }
    else:
        return {
            "compile_success": False,
            "compile_error": result["error"],
            "compile_attempts": attempts,
            "pdf_bytes": None,
            "status": "compile_failed",
            "logs": [f"Compile attempt {attempts} failed: "
                     f"{result['error'][:120]}"],
        }


# ================================================================
# NODE 5 — fix_latex
# Self-heals LaTeX errors from compiler stderr
# ================================================================

def node_fix_latex(state: ResumeAgentState) -> dict:
    logger.info("Node: fix_latex")

    fixed = _call_llm(
        FIX_LATEX_SYSTEM,
        FIX_LATEX_HUMAN.format(
            error=state["compile_error"],
            latex_source=state["latex_source"],
        )
    )

    fixed = _clean_latex_output(fixed)

    return {
        "latex_source": fixed,
        "status": "latex_fixed",
        "logs": [f"LaTeX auto-fixed (attempt {state.get('compile_attempts', 0)})"],
    }


# ================================================================
# ROUTING LOGIC
# ================================================================

def route_after_compile(state: ResumeAgentState) -> Literal["fix_latex", "end_success", "end_error"]:
    if state["compile_success"]:
        return "end_success"
    if state.get("compile_attempts", 0) >= settings.max_compile_retries:
        return "end_error"
    return "fix_latex"


def route_after_fix(state: ResumeAgentState) -> Literal["compile", "end_error"]:
    if state.get("compile_attempts", 0) >= settings.max_compile_retries:
        return "end_error"
    return "compile"


# ================================================================
# BUILD THE GRAPH
# ================================================================

def build_graph() -> StateGraph:
    g = StateGraph(ResumeAgentState)

    # Register nodes
    g.add_node("parse_jd", node_parse_jd)
    g.add_node("parse_candidate", node_parse_candidate)
    g.add_node("generate_latex", node_generate_latex)
    g.add_node("compile", node_compile)
    g.add_node("fix_latex", node_fix_latex)

    # Entry
    g.set_entry_point("parse_jd")

    # Linear edges
    g.add_edge("parse_jd", "parse_candidate")
    g.add_edge("parse_candidate", "generate_latex")
    g.add_edge("generate_latex", "compile")

    # Conditional: after compile
    g.add_conditional_edges(
        "compile",
        route_after_compile,
        {
            "end_success": END,
            "end_error": END,
            "fix_latex": "fix_latex",
        }
    )

    # Conditional: after fix
    g.add_conditional_edges(
        "fix_latex",
        route_after_fix,
        {
            "compile": "compile",
            "end_error": END,
        }
    )

    return g.compile()


# Singleton graph instance
resume_graph = build_graph()
