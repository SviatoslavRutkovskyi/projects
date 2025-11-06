from pydantic import BaseModel, Field
from typing import Optional

# Resume-related models
class SkillCategory(BaseModel):
    name: str
    skills: list[str]

class Project(BaseModel):
    name: str
    date: str
    github_link_names: list[str]
    github_links: list[str]
    bullet_points: list[str]

class Experience(BaseModel):
    company_name: str
    start_date: str
    end_date: str
    job_title: str
    location: str
    bullet_points: list[str]

class ResumeData(BaseModel):
    profile: str
    skills: list[SkillCategory]
    projects: list[Project]
    experiences: list[Experience]

# Cover letter-related models
class Evaluation(BaseModel):
    is_acceptable: bool
    feedback: str
    score: int

# Job description-related models
class JobDescription(BaseModel):
    """Structured info extracted from a job posting for resume & cover letter generation."""
    company_name: Optional[str] = None
    job_title: Optional[str] = None

    # Skills & signals for selection/ATS
    required_skills: list[str] = Field(default_factory=list)     # hard must-haves
    preferred_skills: list[str] = Field(default_factory=list)    # nice-to-haves
    key_phrases: list[str] = Field(default_factory=list)         # notable literal terms to sprinkle

    # Content for bullets/CL body
    responsibilities: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)        # qualifications/reqs (keep if you actually use it)
    description_summary: Optional[str] = None                    # 1–3 sentence brief

    # Tone & culture for profile/CL voice
    values: list[str] = Field(default_factory=list)              # e.g., ["customer focus","collaboration"]
    culture_text: Optional[str] = None    