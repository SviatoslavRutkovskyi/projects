from openai import OpenAI
import subprocess
import os
import json
from latex_generator import LatexGenerator
from models import ResumeData, JobDescription


# Constants
DEFAULT_OUTPUT_DIR = "static/output"


class Resume:
    """Resume tailoring class.""" 
    def __init__(self, 
                creator_model = "gpt-5-mini", 
                candidate_json_path = "resources/candidate.json",
                system_prompt = "",
                temperature = 0.3,
                ):
        
        self.candidate_json_path = candidate_json_path
        self.creator_model = creator_model
        self.temperature = temperature
        self.latex_generator = LatexGenerator()

        self.last_resume_content = None
        
        # Load candidate data eagerly (always needed for tailoring)
        self.candidate_data = self._load_candidate_data()
        
        # Build system prompt with static content (candidate JSON, schema, rules)
        self.system_prompt = system_prompt if system_prompt else self._build_system_prompt()
    
        # AI models 
        self.openai = OpenAI()


    def tailor_resume(self, job_info: JobDescription, resume_feedback, use_last_resume=False):
        """Tailor resume to job posting using structured job information."""
        if use_last_resume and self.last_resume_content:
            print("Using last resume as base for tailoring")
        elif use_last_resume and not self.last_resume_content:
            print("No previous resume available. Creating a new resume from the original template.")
        
        user_message = self._build_user_message(job_info, resume_feedback, use_last_resume)
        resume_data = self.run(self.system_prompt, user_message)

        # Generate PDF
        os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)
        tex_path = os.path.join(DEFAULT_OUTPUT_DIR, "resume.tex")
        pdf_path = tex_path.replace(".tex", ".pdf")

        latex_content = self.latex_generator.convert_json_to_latex(resume_data)
        if latex_content is None:
            print("Failed to create LaTeX from JSON resume data")
            return None

        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(latex_content)
        
        # Compile LaTeX to PDF
        result = subprocess.run(
            ["tectonic", os.path.basename(tex_path)],
            cwd=DEFAULT_OUTPUT_DIR,
            capture_output=True,
            text=True
        )

        print("Tectonic STDOUT:\n", result.stdout)
        print("Tectonic STDERR:\n", result.stderr)

        if result.returncode != 0:
            print(f"LaTeX compilation failed with return code {result.returncode}")
            print("LaTeX error details:", result.stderr)
            return None

        self.last_resume_content = resume_data.model_dump_json()
        return pdf_path

    def run(self, prompt, user_message) -> ResumeData:
        """Run API call."""
        response = self.openai.responses.parse(
            model=self.creator_model,
            input=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_message}
            ],
            text_format=ResumeData,
            temperature=self.temperature,
        )
        return response.output_parsed
    
    def _load_candidate_data(self) -> ResumeData:
        """Load and validate candidate data from JSON file using ResumeData model."""
        try:
            with open(self.candidate_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return ResumeData(**data)
        except FileNotFoundError:
            print(f"Error: Candidate JSON file not found at {self.candidate_json_path}")
            raise
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in candidate file: {e}")
            raise
        except Exception as e:
            print(f"Error: Invalid candidate data structure: {e}")
            print("Expected format matches ResumeData schema (profile, skills, projects, experiences)")
            raise
    
    def _build_system_prompt(self):
        """Build system prompt with candidate JSON, schema, and rules."""
        candidate_json = self.candidate_data.model_dump_json(indent=2)
        json_schema = json.dumps(ResumeData.model_json_schema(), indent=2)
        
        return f"""You are an expert resume tailoring specialist.

Candidate JSON:
{candidate_json}

Return ONLY JSON per this schema:
{json_schema}

Rules:
- Rewrite Profile section to emphasize alignment with the job posting (2-3 sentences, 50-100 words)
- Reorder/trim SKILLS section to prioritize those mentioned in the job posting
- Select 2-3 most relevant PROJECTS that match job requirements (3-4 bullet points each)
- Select 1-2 most relevant EXPERIENCES (2-3 bullet points each)
- Use action verbs and quantify achievements
- Focus on results and impact
- Ensure all dates are in "MMM YYYY" format (e.g., "Jan 2024")
- Do not include markdown formatting or any other text/comments
- Do not fake any information - use only information provided in the Candidate JSON"""
    
    def _build_user_message(self, job_info: JobDescription, resume_feedback, use_last_resume=False):
        """Build user message with structured job information, optional last resume, and feedback."""
        # Format the structured job information into a readable prompt
        formatted_job_info = job_info.model_dump_json(indent=2)
        user_message = f"Job Posting Information:\n{formatted_job_info}"
        
        if use_last_resume and self.last_resume_content:
            user_message += f"\n\nUse this resume as your starting point:\n{self.last_resume_content}"
        
        if resume_feedback:
            user_message += f"\n\nUser Instructions: {resume_feedback}"
        
        return user_message   


