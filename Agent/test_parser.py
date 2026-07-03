import io
import os
import json
import logging
from typing import List

import fitz  # PyMuPDF
import docx
from fastapi.testclient import TestClient

# Add current directory to path so we can import modules
import sys
sys.path.insert(0, os.path.dirname(__file__))

from api.main import app
from api.schemas import JDStructuredOutput, ResumeStructuredOutput

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sample JDs
SAMPLE_JDS = [
    {
        "id": "jd1_frontend",
        "text": """
        Software Engineer (Frontend) at Acme Corp (San Francisco, CA)
        We are looking for a Mid-level Frontend Engineer with 3+ years of experience.
        Skills: React, JavaScript, HTML, CSS, TailwindCSS, TypeScript.
        """
    },
    {
        "id": "jd2_devops",
        "text": """
        Senior DevOps Engineer - Cloud Infrastructure
        We are hiring a Senior DevOps Engineer. Must have experience with AWS, Kubernetes, Terraform, Docker, and CI/CD pipelines. 5+ years of experience required.
        """
    },
    {
        "id": "jd3_ml",
        "text": """
        Machine Learning Engineer
        Acme AI is seeking a Staff ML Engineer. Requirements: PyTorch, Python, TensorFlow, Kubernetes, distributed training. Seniority level: staff. Primary domain: ML.
        """
    },
    {
        "id": "jd4_fullstack",
        "text": """
        Fullstack Developer
        Acme Startup is looking for a junior developer to build fullstack web apps. Experience with Node.js, React, PostgreSQL.
        """
    },
    {
        "id": "jd5_backend",
        "text": """
        Backend Engineer
        Meta is seeking a Principal Software Engineer for backend platform. Expert in Go, Python, distributed systems, Kafka, Redis. Seniority: principal. Domain: backend.
        """
    }
]

# Sample Resumes
SAMPLE_RESUMES = [
    {
        "id": "resume1_pdf",
        "format": "pdf",
        "text": """
        John Doe
        john.doe@gmail.com | 123-456-7890 | San Francisco, CA | github: johndoe
        
        EXPERIENCE:
        Senior Backend Engineer at Google (Jan 2022 - Present)
        - Designed and built distributed microservices in Go and Python.
        - Utilized Kafka and PostgreSQL.
        
        EDUCATION:
        Stanford University, BS in Computer Science (2016-2020)
        
        SKILLS: Go, Python, Kafka, PostgreSQL, Docker, AWS
        """
    },
    {
        "id": "resume2_pdf",
        "format": "pdf",
        "text": """
        Jane Smith
        jane.smith@email.com | 987-654-3210 | Seattle, WA | linkedin: janesmith
        
        EXPERIENCE:
        Frontend Developer at Microsoft (Jun 2021 - Present)
        - Built user interfaces using React, TypeScript, HTML, CSS.
        
        EDUCATION:
        UW Seattle, BS in Computer Science (2017-2021)
        
        SKILLS: React, TypeScript, JavaScript, CSS, HTML
        """
    },
    {
        "id": "resume3_pdf",
        "format": "pdf",
        "text": """
        Bob Johnson
        bob.johnson@email.com | Austin, TX
        
        EXPERIENCE:
        DevOps Engineer at Tesla (Jan 2019 - Present)
        - Managed Kubernetes clusters and Terraform infrastructure on AWS.
        
        EDUCATION:
        UT Austin, BS in ECE (2015-2019)
        
        SKILLS: Kubernetes, Terraform, Docker, AWS, Bash, Git
        """
    },
    {
        "id": "resume4_docx",
        "format": "docx",
        "text": """
        Alice Williams
        alice.williams@email.com | New York, NY
        
        EXPERIENCE:
        Data Scientist at FinanceCorp (Feb 2022 - Present)
        - Built machine learning models using PyTorch and Scikit-Learn.
        
        EDUCATION:
        NYU, MS in Data Science (2020-2022)
        
        SKILLS: PyTorch, Python, SQL, Scikit-Learn
        """
    },
    {
        "id": "resume5_docx",
        "format": "docx",
        "text": """
        Charlie Brown
        charlie@email.com | Denver, CO
        
        EXPERIENCE:
        Junior Fullstack Developer at StartupX (Mar 2023 - Present)
        - Worked with Node.js, React, and MongoDB.
        
        EDUCATION:
        CU Boulder, BS in CS (2019-2023)
        
        SKILLS: Node.js, React, MongoDB, JavaScript
        """
    },
    {
        "id": "resume6_docx",
        "format": "docx",
        "text": """
        David Miller
        david.miller@email.com | Boston, MA
        
        EXPERIENCE:
        Staff Software Engineer at Amazon (Jun 2018 - Present)
        - Lead developer for cloud platform services.
        
        SKILLS: Java, Spring Boot, AWS, Docker, Kubernetes
        """
    },
    {
        "id": "resume7_txt",
        "format": "txt",
        "text": """
        Emma Davis
        emma.davis@email.com | Chicago, IL
        
        EXPERIENCE:
        Frontend Engineer at DesignStudio (May 2022 - Present)
        - Created responsive websites with HTML, CSS, React, and Tailwind.
        
        SKILLS: React, Tailwind, JavaScript, HTML, CSS
        """
    },
    {
        "id": "resume8_txt",
        "format": "txt",
        "text": """
        Frank Miller
        frank@email.com | Los Angeles, CA
        
        EXPERIENCE:
        Backend Developer at MediaCorp (Jan 2020 - Present)
        - Developed REST APIs using FastAPI, PostgreSQL, and Redis.
        
        SKILLS: FastAPI, PostgreSQL, Redis, Python
        """
    }
]

def create_temp_file(filename: str, format_type: str, text: str) -> str:
    path = os.path.join(os.path.dirname(__file__), filename)
    if format_type == "pdf":
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), text)
        doc.save(path)
        doc.close()
    elif format_type == "docx":
        doc = docx.Document()
        for line in text.split("\n"):
            line_strip = line.strip()
            if line_strip:
                doc.add_paragraph(line_strip)
        doc.save(path)
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    return path

def main():
    print("=" * 70)
    print("JD & Resume Parsing Service — Integration Test Suite")
    print("=" * 70)
    
    # Check settings
    print(f"Active LLM Provider: {app.dependency_overrides.get('settings', app).settings.llm_provider}")
    print(f"Active LLM Model: {app.dependency_overrides.get('settings', app).settings.resolved_model}")
    print("-" * 70)
    
    client = TestClient(app)
    
    total_tests = 0
    passed_tests = 0
    
    # ----------------------------------------------------
    # Test 1: JD Parsing (POST /parse-jd)
    # ----------------------------------------------------
    print("\n--- Testing JD Parsing Endpoint (/parse-jd) ---")
    for jd_item in SAMPLE_JDS:
        total_tests += 1
        print(f"Testing JD parsing: {jd_item['id']}...", end=" ", flush=True)
        try:
            response = client.post("/parse-jd", json={"jd_text": jd_item["text"]})
            if response.status_code == 200:
                data = response.json()
                # Validate with Pydantic
                validated = JDStructuredOutput.model_validate(data)
                passed_tests += 1
                print("PASSED")
                print(f"  Result -> Role: {validated.role_title} | Company: {validated.company} | Seniority: {validated.seniority} | Domain: {validated.domain}")
            else:
                print(f"FAILED (Status {response.status_code}): {response.text}")
        except Exception as e:
            print(f"FAILED (Error): {e}")

    # ----------------------------------------------------
    # Test 2: Resume Parsing (POST /parse-resume)
    # ----------------------------------------------------
    print("\n--- Testing Resume Parsing Endpoint (/parse-resume) ---")
    for resume_item in SAMPLE_RESUMES:
        total_tests += 1
        filename = f"temp_{resume_item['id']}.{resume_item['format']}"
        filepath = create_temp_file(filename, resume_item['format'], resume_item['text'])
        print(f"Testing Resume parsing ({resume_item['format'].upper()}): {resume_item['id']}...", end=" ", flush=True)
        try:
            with open(filepath, "rb") as f:
                response = client.post(
                    "/parse-resume",
                    files={"file": (filename, f, f"application/octet-stream")}
                )
            if response.status_code == 200:
                data = response.json()
                # Validate with Pydantic
                validated = ResumeStructuredOutput.model_validate(data)
                passed_tests += 1
                print("PASSED")
                print(f"  Result -> Name: {validated.full_name} | Email: {validated.email} | Jobs count: {len(validated.experiences)} | Skills: {validated.skills.languages[:4]}")
            else:
                print(f"FAILED (Status {response.status_code}): {response.text}")
        except Exception as e:
            print(f"FAILED (Error): {e}")
        finally:
            # Clean up temp file
            if os.path.exists(filepath):
                os.remove(filepath)
                
    # ----------------------------------------------------
    # Summary of Results
    # ----------------------------------------------------
    pass_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print(f"Total Tests Run : {total_tests}")
    print(f"Passed Tests    : {passed_tests}")
    print(f"Failed Tests    : {total_tests - passed_tests}")
    print(f"Success Pass Rate: {pass_rate:.1f}%")
    print("=" * 70)
    
    if pass_rate >= 99.0:
        print("\nSUCCESS: Service meets the 99% JSON validity target!")
        sys.exit(0)
    else:
        print("\nFAILURE: Service does NOT meet the 99% JSON validity target.")
        sys.exit(1)

if __name__ == "__main__":
    main()
