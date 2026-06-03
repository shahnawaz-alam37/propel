#!/usr/bin/env python3
# ============================================================
# test_agent.py — quick smoke test (no pytest needed)
# Run: python test_agent.py
# ============================================================

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from agent.graph import resume_graph
from agent.state import ResumeAgentState

SAMPLE_CANDIDATE = """
John Doe
john.doe@email.com | +1 555-000-0000 | linkedin: johndoe | github: johndoe | San Francisco, CA

EXPERIENCE
Google — Software Engineer II (Jan 2022 – Present, Mountain View, CA)
- Built real-time data pipelines processing 500M events/day using Kafka and Flink
- Led team of 6 to ship developer tooling feature adopted by 2000+ internal users
- Optimized PostgreSQL queries, cut p99 latency from 800ms to 120ms

Stripe — Software Engineer (Jun 2019 – Dec 2021, Remote)
- Maintained payment reconciliation microservices handling $2B+ annual transaction volume
- Reduced on-call incidents 35% with anomaly detection on metrics dashboards

EDUCATION
UC Berkeley — B.S. Computer Science (2014–2018), GPA 3.8

SKILLS: Python, Java, TypeScript, Go, React, Node.js, FastAPI, Docker, Kubernetes, AWS, PostgreSQL
"""

SAMPLE_JD = """
Senior Software Engineer – Platform Infrastructure
Meta | Menlo Park, CA

We are looking for a Senior Software Engineer to join our Platform Infrastructure team.

Requirements:
- 5+ years of experience with distributed systems
- Strong Python and Go skills
- Experience with Kubernetes, Docker, and cloud infrastructure (AWS/GCP)
- Experience with large-scale data pipelines (Kafka, Spark, or Flink)
- PostgreSQL or other relational database experience
- Strong communication and cross-functional collaboration skills

Nice to have:
- Experience with observability tools (Prometheus, Grafana, OpenTelemetry)
- Contributions to open-source infrastructure projects
- Experience with Terraform or infrastructure-as-code
"""

def main():
    print("=" * 60)
    print("ResumeAI Agent — smoke test")
    print("=" * 60)

    initial_state: ResumeAgentState = {
        "raw_input": SAMPLE_CANDIDATE,
        "job_description": SAMPLE_JD,
        "input_mode": "text",
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

    print("\nRunning agent...\n")
    final = resume_graph.invoke(initial_state, config={"recursion_limit": 10})

    print("\n--- AGENT LOGS ---")
    for log in final.get("logs", []):
        print(f"  {log}")

    print(f"\n--- RESULT ---")
    print(f"  Status         : {final.get('status')}")
    print(f"  JD Role        : {final.get('jd_role_title')}")
    print(f"  JD Company     : {final.get('jd_company')}")
    print(f"  Keywords       : {', '.join(final.get('jd_keywords', [])[:5])}...")
    print(f"  LaTeX version  : {final.get('latex_version')}")
    print(f"  Compile success: {final.get('compile_success')}")
    print(f"  Compile tries  : {final.get('compile_attempts')}")

    if final.get("compile_success") and final.get("pdf_bytes"):
        with open("test_output.pdf", "wb") as f:
            f.write(final["pdf_bytes"])
        print(f"\n  PDF saved to: test_output.pdf ({len(final['pdf_bytes']):,} bytes)")
    elif final.get("latex_source"):
        with open("test_output.tex", "w") as f:
            f.write(final["latex_source"])
        print(f"\n  LaTeX saved to: test_output.tex")
        if final.get("compile_error"):
            print(f"\n  Last compile error:\n{final['compile_error'][:400]}")

if __name__ == "__main__":
    main()
