from openai import OpenAI
import json
import subprocess
import time
import logging
from pathlib import Path
from uuid import uuid4
import math

from latex_generator import LatexGenerator
from models import AppConfig, ResumeData, JobDescription
from utils import sanitize_filename, load_candidate_data, save_output_file

logger = logging.getLogger(__name__)


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

        self.candidate_data = load_candidate_data(self.config.candidate_json)

        self.system_prompt = self._build_system_prompt()

        self.openai = OpenAI()

    def _fit_score(self, lines: float) -> tuple:
        """
        Returns a tuple score where lower is better.
        (0, 0)       = in range (best)
        (1, gap)     = under min (acceptable, larger gap is worse)
        (2, gap)     = over max (worst, larger gap is worse)
        """
        min_l = self._line_estimates['min_page_lines']
        max_l = self._line_estimates['max_page_lines']

        if lines > max_l:
            return (2, lines - max_l)
        if lines < min_l:
            return (1, min_l - lines)
        return (0, 0)

    def tailor_resume(self, job_info: JobDescription, resume_feedback, last_resume_content=None):
        """
        Tailor resume to job posting using structured job information.
        Returns (pdf_path, resume_json) on success, or None on failure.
        """
        start_time = time.time()
        run_id = uuid4()
        logger.info(f"[tailor_resume called] run_id={run_id}")
        logger.info("[1/5] Tailoring resume...")

        if last_resume_content:
            logger.info("    Using last resume as base for tailoring")

        # First attempt — full context including feedback and last resume
        user_message = self._build_user_message(job_info, resume_feedback, last_resume_content)
        elapsed = time.time() - start_time
        logger.info(f"[2/5] Generating tailored resume content... ({elapsed:.1f}s elapsed)")
        resume_data = self.run(self.system_prompt, user_message)

        elapsed = time.time() - start_time
        logger.info(f"[3/5] Verifying resume length... ({elapsed:.1f}s elapsed)")

        best_resume_data = resume_data
        best_score = self._fit_score(self.calculate_resume_lines(resume_data, self._line_estimates))

        for i in range(5):
            lines_calculated = self.calculate_resume_lines(resume_data, self._line_estimates)
            score = self._fit_score(lines_calculated)

            logger.info(
                f"    Attempt {i + 1}: {lines_calculated} lines "
                f"(model estimated: {resume_data.estimated_resume_lines}, "
                f"range: {self._line_estimates['min_page_lines']}–{self._line_estimates['max_page_lines']})"
            )

            if score < best_score:
                best_score = score
                best_resume_data = resume_data

            if score == (0, 0):
                break

            elapsed = time.time() - start_time
            logger.info(f"[3/5] Adjusting resume length... ({elapsed:.1f}s elapsed)")

            # Retries — size correction only, no feedback re-sent
            resume_data = self.run(
                self.system_prompt,
                self._build_retry_message(job_info, resume_data.model_dump_json(), lines_calculated)
            )

        # Use best result found across all attempts
        resume_data = best_resume_data
        final_lines = self.calculate_resume_lines(resume_data, self._line_estimates)

        if self._fit_score(final_lines) != (0, 0):
            if final_lines > self._line_estimates['max_page_lines']:
                logger.warning(f"Resume still over page limit after retries: {final_lines} lines")
            else:
                logger.warning(
                    f"Insufficient content to fill page: {final_lines} lines — returning best available"
                )

        elapsed = time.time() - start_time
        logger.info(f"[4/5] Converting to LaTeX... ({elapsed:.1f}s elapsed)")

        company_name_sanitized = sanitize_filename(job_info.company_name) if job_info.company_name else ""
        filename_base = f"resume_{company_name_sanitized}" if company_name_sanitized else "resume"

        latex_content = self.latex_generator.convert_to_latex(self.candidate_data, resume_data)
        if latex_content is None:
            logger.error("Failed to create LaTeX from resume data")
            return None

        tex_path = save_output_file(f"{filename_base}.tex", latex_content.encode("utf-8"), prefix="resume")
        pdf_path = tex_path.with_suffix(".pdf")

        elapsed = time.time() - start_time
        logger.info(f"[5/5] Compiling PDF... ({elapsed:.1f}s elapsed)")
        result = subprocess.run(
            ["tectonic", tex_path.name],
            cwd=tex_path.parent,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.error(f"LaTeX compilation failed with return code {result.returncode}")
            logger.error(f"LaTeX error details: {result.stderr}")
            return None

        elapsed = time.time() - start_time
        logger.info(f"Resume generated successfully: {pdf_path} ({elapsed:.1f}s elapsed)")
        return str(pdf_path), resume_data.model_dump_json()

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
            (resume_data.selected_skills,          "skills_category_line"),
        ]

        nested_sections = [
            (resume_data.selected_experiences, "experience_item_line", "experience_bullet_line"),
            (resume_data.selected_projects,    "project_item_line",    "project_bullet_line"),
        ]

        total = H
        CHARS_PER_LINE = 115

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

If you receive feedback stating your total number of lines, treat it as truth and adjust your output accordingly.

{self._line_estimates_prompt_text}"""

    def _build_user_message(self, job_info: JobDescription, resume_feedback, last_resume_content=None):
        """Build first-attempt message with full context: job posting, last resume, and feedback."""
        parts = [f"## Job posting\n{job_info.model_dump_json(indent=2)}"]

        if last_resume_content:
            parts.append(
                f"## Previous resume output\n{last_resume_content}\n\n"
                "Use as the starting point; keep selections and bullets unless user notes require changes."
            )

        if resume_feedback:
            parts.append(f"## User notes\n{resume_feedback}")

        return "\n\n".join(parts)

    def _build_retry_message(self, job_info: JobDescription, previous_output: str, lines_calculated: float) -> str:
        """Build retry message for size correction only. No feedback or last resume — those are
        already reflected in the previous output and should not be reinterpreted."""
        min_l = self._line_estimates['min_page_lines']
        max_l = self._line_estimates['max_page_lines']
        direction = "Remove" if lines_calculated > max_l else "Add"

        return (
            f"## Job posting\n{job_info.model_dump_json(indent=2)}\n\n"
            f"## Previous attempt\n{previous_output}\n\n"
            f"## Size correction only\n"
            f"This attempt has {lines_calculated} lines. Acceptable range: {min_l}–{max_l} lines.\n"
            f"{direction} content to fit. Adjust profile length or bullet count. "
            f"Do not change which projects or experiences are included. "
            f"Do not remove bullets that were explicitly added to satisfy user notes."
        )