from openai import OpenAI
import subprocess
import os
import json
import time
import glob
from latex_generator import LatexGenerator
from models import AppConfig, ResumeData, JobDescription
from utils import sanitize_filename, load_candidate_data


# Constants
DEFAULT_OUTPUT_DIR = "static/output"


class Resume:
    """Resume tailoring class."""
    def __init__(
        self,
        config: AppConfig,
        creator_model="gpt-5-mini",
        temperature=0.3,
    ):
        
        self.config = config
        self.creator_model = creator_model
        self.temperature = temperature
        self.latex_generator = LatexGenerator(config=self.config)

        self.last_resume_content = None
        
        # Load candidate data eagerly (always needed for tailoring)
        self.candidate_data = load_candidate_data(self.config.candidate_json)
        
        self.system_prompt = self._build_system_prompt()
    
        # AI models 
        self.openai = OpenAI()

    def tailor_resume(self, job_info: JobDescription, resume_feedback, use_last_resume=False):
        """Tailor resume to job posting using structured job information."""
        start_time = time.time()
        print(f"[1/4] Tailoring resume...")
        if use_last_resume and self.last_resume_content:
            print("    Using last resume as base for tailoring")
        elif use_last_resume and not self.last_resume_content:
            print("    No previous resume available. Creating a new resume from the original template.")
        
        user_message = self._build_user_message(job_info, resume_feedback, use_last_resume)
        elapsed = time.time() - start_time
        print(f"[2/4] Generating tailored resume content... ({elapsed:.1f}s elapsed)")
        resume_data = self.run(self.system_prompt, user_message)

        # Generate PDF
        elapsed = time.time() - start_time
        print(f"[3/4] Converting to LaTeX... ({elapsed:.1f}s elapsed)")
        
        # Create output directory if needed
        os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)
        
        # Remove old resume files (only expecting 1 resume file)
        for old_file in glob.glob(os.path.join(DEFAULT_OUTPUT_DIR, "resume*")):
            os.remove(old_file)
        
        # Create filename with company name
        company_name_sanitized = sanitize_filename(job_info.company_name) if job_info.company_name else ""
        if company_name_sanitized:
            filename_base = f"resume_{company_name_sanitized}"
        else:
            filename_base = "resume"
        
        tex_path = os.path.join(DEFAULT_OUTPUT_DIR, f"{filename_base}.tex")
        pdf_path = os.path.join(DEFAULT_OUTPUT_DIR, f"{filename_base}.pdf")

        latex_content = self.latex_generator.convert_json_to_latex(resume_data)
        if latex_content is None:
            print("    ✗ Failed to create LaTeX from JSON resume data")
            return None

        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(latex_content)
        
        # Compile LaTeX to PDF
        elapsed = time.time() - start_time
        print(f"[4/4] Compiling PDF... ({elapsed:.1f}s elapsed)")
        result = subprocess.run(
            ["tectonic", os.path.basename(tex_path)],
            cwd=DEFAULT_OUTPUT_DIR,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"    ✗ LaTeX compilation failed with return code {result.returncode}")
            print("    LaTeX error details:", result.stderr)
            return None

        self.last_resume_content = resume_data.model_dump_json()
        elapsed = time.time() - start_time
        print(f"    ✓ Resume generated successfully: {pdf_path} ({elapsed:.1f}s elapsed)")
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
    
    def _build_system_prompt(self):
        """Build system prompt with candidate JSON, schema, and rules."""
        candidate_json = self.candidate_data.model_dump_json(indent=2)
        json_schema = json.dumps(ResumeData.model_json_schema(), indent=2)
        
        return f"""You are an expert resume tailoring specialist.

Candidate JSON:
{candidate_json}

Rules:
- Rewrite the Profile section to emphasize alignment with the job posting (2-3 sentences, 50-100 words)
- Reorder the Skills section to prioritize skills mentioned in the job posting; drop skills clearly irrelevant to the role
- Select 2-3 most relevant Projects; include 3-4 bullets each that best match the job requirements
- Select 2-3 most relevant Experiences; include 2-3 bullets each that best match the job requirements
- Prefer bullets that demonstrate measurable outcomes; do not invent or infer numbers not present in the source data
- Do not include markdown formatting or any other text or comments
- Use only information provided in the Candidate JSON — do not fabricate any details"""
    
    def _build_user_message(self, job_info: JobDescription, resume_feedback, use_last_resume=False):
        """Build user message with structured job information, optional last resume, and feedback."""
        # Format the structured job information into a readable prompt
        formatted_job_info = job_info.model_dump_json(indent=2)
        user_message = f"Job Posting Information:\n{formatted_job_info}"
        
        if use_last_resume and self.last_resume_content:
            user_message += f"\n\nPrevious resume output:\n{self.last_resume_content}\n\nUse this as your starting point. Preserve bullet selections and structure unless the user instructions below require changes."
        
        if resume_feedback:
            user_message += f"\n\nUser Instructions: {resume_feedback}"
        
        return user_message   


