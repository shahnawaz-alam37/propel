from typing import Optional, Literal
from pydantic import BaseModel, Field

# ==============================================================================
# JD Parsing Schemas
# ==============================================================================

class JDStructuredOutput(BaseModel):
    role_title: str = Field(description="The exact title of the job role or position.")
    company: Optional[str] = Field(default="", description="The name of the company hiring, or empty string if not specified.")
    keywords: list[str] = Field(default_factory=list, description="A list of 10-15 technical keywords relevant to the JD.")
    required_skills: list[str] = Field(default_factory=list, description="List of must-have skills or requirements.")
    preferred_skills: list[str] = Field(default_factory=list, description="List of nice-to-have or preferred skills.")
    seniority: Literal["junior", "mid", "senior", "staff", "principal"] = Field(
        description="The seniority level implied or stated in the job description."
    )
    domain: Literal["backend", "frontend", "fullstack", "ml", "data", "devops", "mobile", "other"] = Field(
        description="The primary domain of the job."
    )


# ==============================================================================
# Resume Parsing Schemas
# ==============================================================================

class ExperienceSchema(BaseModel):
    company: str = Field(description="Name of the company or organization.")
    role: str = Field(description="Job title or role held.")
    location: Optional[str] = Field(default="", description="Location of the job (City, State/Country).")
    start_date: Optional[str] = Field(default="", description="Start date of employment (e.g., 'Jan 2022' or '06/2019').")
    end_date: Optional[str] = Field(default="", description="End date of employment (e.g., 'Dec 2021' or 'Present').")
    bullets: list[str] = Field(default_factory=list, description="List of key responsibilities and accomplishments (bullet points).")


class EducationSchema(BaseModel):
    institution: str = Field(description="Name of the school, university, or academy.")
    degree: str = Field(description="Degree, certification, or field of study obtained.")
    location: Optional[str] = Field(default="", description="Location of the institution.")
    start_date: Optional[str] = Field(default="", description="Start date (e.g., '2014' or 'Sep 2014').")
    end_date: Optional[str] = Field(default="", description="End or graduation date (e.g., '2018' or 'May 2018').")
    gpa: Optional[str] = Field(default="", description="Grade Point Average if specified, e.g., '3.8/4.0'.")
    notes: list[str] = Field(default_factory=list, description="Any honors, awards, or special coursework mentioned.")


class ProjectSchema(BaseModel):
    name: str = Field(description="Name of the project.")
    tech_stack: Optional[str] = Field(default="", description="Comma-separated technologies or tools used in the project.")
    year: Optional[str] = Field(default="", description="Year or duration of the project.")
    bullets: list[str] = Field(default_factory=list, description="Details or accomplishments within this project.")


class SkillsSchema(BaseModel):
    languages: list[str] = Field(default_factory=list, description="Programming languages (e.g., Python, TypeScript).")
    frameworks: list[str] = Field(default_factory=list, description="Frameworks and libraries (e.g., FastAPI, React).")
    cloud: list[str] = Field(default_factory=list, description="Cloud platforms (e.g., AWS, GCP).")
    databases: list[str] = Field(default_factory=list, description="Databases used (e.g., PostgreSQL, Redis).")
    tools: list[str] = Field(default_factory=list, description="Developer tools or other infrastructure (e.g., Git, Docker, Kubernetes).")


class ResumeStructuredOutput(BaseModel):
    full_name: str = Field(description="Full name of the candidate.")
    email: Optional[str] = Field(default="", description="Email address.")
    phone: Optional[str] = Field(default="", description="Phone number.")
    location: Optional[str] = Field(default="", description="Current location (City, State/Country).")
    linkedin: Optional[str] = Field(default="", description="LinkedIn handle only, or empty.")
    github: Optional[str] = Field(default="", description="GitHub handle only, or empty.")
    summary: Optional[str] = Field(default="", description="A short professional summary.")
    experiences: list[ExperienceSchema] = Field(default_factory=list, description="Work history.")
    education: list[EducationSchema] = Field(default_factory=list, description="Academic background.")
    projects: list[ProjectSchema] = Field(default_factory=list, description="Side projects or personal works.")
    skills: SkillsSchema = Field(default_factory=SkillsSchema, description="Categorized technical skills.")
