from pydantic import BaseModel, Field
from typing import Literal, Optional
from pathlib import Path

# --- Candidate profile / source JSON ---


class PersonalInfo(BaseModel):
    """Contact block. Omit fields to hide them on the resume."""

    name: str
    location: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    linkedin_label: Optional[str] = None


class TextItem(BaseModel):
    id: int
    text: str


class SkillCategory(BaseModel):
    id: int
    name: str
    skills: list[TextItem]


class Project(BaseModel):
    id: int
    name: str
    date: str
    github_link_names: list[str] = Field(default_factory=list)
    github_links: list[str] = Field(default_factory=list)
    bullet_points: list[TextItem]


class Experience(BaseModel):
    id: int
    company_name: str
    job_title: str
    start_date: str
    end_date: str
    location: str
    bullet_points: list[TextItem]


class EducationEntry(BaseModel):
    id: int
    institution: str
    date_range: str
    degree_line: str
    location: str


class CertificateEntry(BaseModel):
    id: int
    name: str
    issuer: Optional[str] = None
    date: Optional[str] = None
    details: Optional[str] = None


class CandidateProfile(BaseModel):
    """Source JSON for tailoring; do not invent employers, dates, credentials, or bullets not present here."""

    profile: str
    personal: PersonalInfo
    education: list[EducationEntry]
    certificates: list[CertificateEntry] = Field(default_factory=list)
    skills: list[SkillCategory]
    projects: list[Project]
    experiences: list[Experience]


# --- Tailored resume output (model returns IDs + rewritten profile only) ---


class SelectedSkillsCategory(BaseModel):
    category_id: int
    skill_ids: list[int]


class SelectedProject(BaseModel):
    project_id: int
    bullet_ids: list[int]


class SelectedExperience(BaseModel):
    experience_id: int
    bullet_ids: list[int]


class ResumeData(BaseModel):
    profile: str
    selected_education_ids: list[int] = Field(default_factory=list)
    selected_skills: list[SelectedSkillsCategory]
    selected_projects: list[SelectedProject]
    selected_experiences: list[SelectedExperience]
    selected_certificate_ids: list[int] = Field(default_factory=list)
    estimated_resume_lines: float


# --- Resume layout & line estimates (JSON-driven) ---

ResumeSectionId = Literal[
    "profile", "education", "experience", "projects", "skills", "certificates"
]


class ResumeLayoutConfig(BaseModel):
    """Body section order (header is always rendered first, not listed here)."""

    section_order: list[ResumeSectionId]


# Cover letter-related models
class Evaluation(BaseModel):
    is_acceptable: bool
    feedback: str
    score: int


class JobDescription(BaseModel):
    """Structured info extracted from a job posting for resume & cover letter generation."""

    company_name: Optional[str] = None
    job_title: Optional[str] = None

    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    key_phrases: list[str] = Field(default_factory=list)

    responsibilities: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    description_summary: Optional[str] = None

    values: list[str] = Field(default_factory=list)
    culture_text: Optional[str] = None


class AppConfig(BaseModel):
    """App configuration. Paths are interpreted relative to the current working directory."""

    name: str
    candidate_json: Path
    cover_letter_template: Path
    resume_template_tex: Path
    resume_layout_json: Path
    line_estimates_json: Path
    empty_pdf: Path
    cover_letter_example: Path
    personal_summary: Path