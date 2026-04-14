from openai import OpenAI
import json
import subprocess
import os
import time
import glob
from pathlib import Path
from uuid import uuid4
import math


from latex_generator import LatexGenerator
from models import AppConfig, ResumeData, JobDescription
from utils import sanitize_filename, load_candidate_data


DEFAULT_OUTPUT_DIR = "static/output"


class Resume:
    """Resume tailoring class."""

    def __init__(
        self,
        config: AppConfig,
        creator_model="o4-mini",
    ):
        self.config = config
        self.creator_model = creator_model
        self.latex_generator = LatexGenerator(config=self.config)

        line_path = Path(self.config.line_estimates_json)
        self._line_estimates_prompt_text = line_path.read_text(encoding="utf-8").strip()
        try:
            self._line_estimates = json.loads(self._line_estimates_prompt_text)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            raise ValueError(f"Invalid line estimates JSON at {line_path}: {e}") from e

        self.last_resume_content = None

        self.candidate_data = load_candidate_data(self.config.candidate_json)

        self.system_prompt = self._build_system_prompt()

        self.openai = OpenAI()

    def tailor_resume(self, job_info: JobDescription, resume_feedback, use_last_resume=False):
        """Tailor resume to job posting using structured job information."""
        start_time = time.time()
        run_id = uuid4()
        print(f"[tailor_resume called] run_id={run_id}")
        print(f"[1/5] Tailoring resume...")
        if use_last_resume and self.last_resume_content:
            print("    Using last resume as base for tailoring")
        elif use_last_resume and not self.last_resume_content:
            print("    No previous resume available. Creating a new resume from the original template.")

        user_message = self._build_user_message(job_info, resume_feedback, use_last_resume)
        elapsed = time.time() - start_time
        print(f"[2/5] Generating tailored resume content... ({elapsed:.1f}s elapsed)")
        resume_data = self.run(self.system_prompt, user_message)

        elapsed = time.time() - start_time
        print(f"[3/5] Verifying resume length... ({elapsed:.1f}s elapsed)")
        for i in range(5):
            lines_calculated = self.calculate_resume_lines(resume_data, self._line_estimates)
            print(
            f"    Model-estimated resume length: {resume_data.estimated_resume_lines} lines "
            f"(informal budget {self._line_estimates['min_page_lines']} to {self._line_estimates['max_page_lines']} lines) "
            f"calculated lines: {lines_calculated}"
            )
            if lines_calculated <= self._line_estimates['max_page_lines'] and lines_calculated >= self._line_estimates['min_page_lines']:
                break
            elapsed = time.time() - start_time
            print(f"[3/5] Ajdusting resume length... ({elapsed:.1f}s elapsed)")
            resume_data = self.run(self.system_prompt, user_message + 
            f"\n\nYour previous resume output:\n{resume_data.model_dump_json()}"
            f"\n\nYour resume has {lines_calculated} lines, which is outside the acceptable range of {self._line_estimates['min_page_lines']} to {self._line_estimates['max_page_lines']}. "
            f"{'Remove' if lines_calculated > self._line_estimates['max_page_lines'] else 'Add'} content until it fits.")
        

        elapsed = time.time() - start_time
        print(f"[4/5] Converting to LaTeX... ({elapsed:.1f}s elapsed)")

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
        print(f"[5/5] Compiling PDF... ({elapsed:.1f}s elapsed)")
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
            
        )
        return response.output_parsed

    def calculate_resume_lines(self, resume_data: ResumeData, estimates: dict) -> float:
        H = estimates["section_heading_line"]

        flat_sections = [
            (resume_data.selected_education_ids,   "education_item_line"),
            (resume_data.selected_certificate_ids, "certificate_item_line"),
            (resume_data.selected_skills,          "skills_category_line"),  # list[SelectedSkillsCategory], counted by len
        ]

        nested_sections = [
            (resume_data.selected_experiences, "experience_item_line", "experience_bullet_line"),
            (resume_data.selected_projects,    "project_item_line",    "project_bullet_line"),
        ]

        total = H
        CHARS_PER_LINE = 115  # calibrated from observed output

        # In calculate_resume_lines:
        total += math.ceil(len(resume_data.profile) / CHARS_PER_LINE)

        for items, item_key in flat_sections:
            if items:
                total += H + len(items) * estimates[item_key]

        for items, item_key, bullet_key in nested_sections:
            if items:
                total += H + sum(
                    estimates[item_key] + len(item.bullet_ids) * estimates[bullet_key]
                    for item in items
                )

        return total

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
Use the weights below to estimate your output size before finalizing selections. Sum all products.
Your estimated_resume_lines field must equal your actual calculated total.
If your total exceeds max_page_lines, remove content until it is less than or equal to max_page_lines.
If your total is less than min_page_lines, add content until it is greater than or equal to min_page_lines.

If you recieve feedback stating your total number of lines, treat it as truth and adjust your output accordingly.

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
