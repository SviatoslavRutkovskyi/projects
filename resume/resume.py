from openai import OpenAI
import json
import subprocess
import os
import time
import glob
from pathlib import Path

from latex_generator import LatexGenerator
from models import AppConfig, ResumeData, JobDescription
from utils import sanitize_filename, load_candidate_data


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

        line_path = Path(self.config.line_estimates_json)
        self._line_estimates_prompt_text = line_path.read_text(encoding="utf-8").strip()
        try:
            self._max_page_lines = float(json.loads(self._line_estimates_prompt_text)["max_page_lines"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            raise ValueError(f"Invalid line estimates JSON at {line_path}: {e}") from e

        self.last_resume_content = None

        self.candidate_data = load_candidate_data(self.config.candidate_json)

        self.system_prompt = self._build_system_prompt()

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

        print(
            f"    Model-estimated resume length: {resume_data.estimated_resume_lines:.1f} lines "
            f"(informal budget {self._max_page_lines:.1f} lines)"
        )

        elapsed = time.time() - start_time
        print(f"[3/4] Converting to LaTeX... ({elapsed:.1f}s elapsed)")

        os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)

        for old_file in glob.glob(os.path.join(DEFAULT_OUTPUT_DIR, "resume*")):
            os.remove(old_file)

        company_name_sanitized = sanitize_filename(job_info.company_name) if job_info.company_name else ""
        if company_name_sanitized:
            filename_base = f"resume_{company_name_sanitized}"
        else:
            filename_base = "resume"

        tex_path = os.path.join(DEFAULT_OUTPUT_DIR, f"{filename_base}.tex")
        pdf_path = os.path.join(DEFAULT_OUTPUT_DIR, f"{filename_base}.pdf")

        latex_content = self.latex_generator.convert_to_latex(self.candidate_data, resume_data)
        if latex_content is None:
            print("    ✗ Failed to create LaTeX from resume data")
            return None

        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(latex_content)

        elapsed = time.time() - start_time
        print(f"[4/4] Compiling PDF... ({elapsed:.1f}s elapsed)")
        result = subprocess.run(
            ["tectonic", os.path.basename(tex_path)],
            cwd=DEFAULT_OUTPUT_DIR,
            capture_output=True,
            text=True,
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
                {"role": "user", "content": user_message},
            ],
            text_format=ResumeData,
            temperature=self.temperature,
        )
        return response.output_parsed

    def _build_system_prompt(self):
        """Build system prompt with candidate JSON and line-budget file."""
        candidate_json = self.candidate_data.model_dump_json(indent=2)

        return f"""You are a resume editor. The job posting is in the user message.

Rules:
- Candidate JSON is the only fact source: employers, titles, schools, dates, tools, metrics, and bullet text must trace to it—no invented credentials or roles.
- Choose what to include for fit; use only ids that exist in that JSON. List ids top-to-bottom as they should read on the page.
- One concise opening paragraph aimed at the role; every claim still supported by that JSON.

## Candidate data
{candidate_json}

## Line budget
Each key below is a weight: multiply by how many of that element appear in your output, sum the products, keep that total at or under max_page_lines (in this block).

{self._line_estimates_prompt_text}"""

    def _build_user_message(self, job_info: JobDescription, resume_feedback, use_last_resume=False):
        """Build user message with structured job information, optional last resume, and feedback."""
        formatted_job_info = job_info.model_dump_json(indent=2)
        parts = [f"## Job posting\n{formatted_job_info}"]

        if use_last_resume and self.last_resume_content:
            parts.append(
                f"## Previous resume output\n{self.last_resume_content}\n\n"
                "Use as the starting point; keep selections and bullets unless user notes require changes."
            )

        if resume_feedback:
            parts.append(f"## User notes\n{resume_feedback}")

        return "\n\n".join(parts)
