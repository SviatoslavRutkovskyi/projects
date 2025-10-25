from pydantic import BaseModel

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
