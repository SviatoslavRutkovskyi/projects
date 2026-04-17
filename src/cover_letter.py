from openai import OpenAI
import logging
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from models import AppConfig, Evaluation, JobDescription
from utils import sanitize_filename, load_candidate_data, save_output_file

logger = logging.getLogger(__name__)



class CoverLetter:
    def __init__(
        self,
        config: AppConfig,
        creator_model: str,
        evaluator_model: str,
        eval_limit: int,
        include_feedback: bool,
    ):

        self.config = config
        self.creator_model = creator_model
        self.evaluator_model = evaluator_model
        self.eval_limit = eval_limit
        self.include_feedback = include_feedback
    
        # AI models 
        self.openai = OpenAI()

        with open(self.config.cover_letter_template, encoding="utf-8") as f:
            self.cover_letter_template = f.read()

        candidate_data = load_candidate_data(self.config.candidate_json)
        candidate_json = candidate_data.model_dump_json(indent=2)

        self.system_prompt = f"""
You are a professional cover letter writer writing on behalf of {candidate_data.personal.name}.

You are given {candidate_data.personal.name}'s resume data and a job description.

- Select the most relevant projects and experiences for this specific role
- Use only information from the candidate data — do not fabricate metrics, percentages, or figures not present in the data
- Respond with cover letter text only — no preamble or commentary
- Write between 200 and 300 words

If given a rejected cover letter and feedback, treat each criticism as a specific failure mode to fix, not a suggestion to acknowledge.

## Candidate Data:
{candidate_json}
"""


        self.evaluator_system_prompt = f"""
You are a professional hiring manager evaluating a cover letter for submission.
Your job is to determine whether the cover letter is ready to send based on five dimensions.

You are provided with:
- The candidate's resume data
- The job description
- The cover letter to evaluate

Opening (0–20 pts): The opening connects the candidate's background to this specific role. A strong opening references something concrete from the candidate's experience and ties it to the role or company. A weak opening is purely generic and could have been written by any applicant.

Depth & Framing (0–25 pts): The letter explains why projects were built, what problem was being solved, and how technical decisions affected the user or end customer. It adds perspective the resume cannot. A strong body shows how the candidate thinks, not just what they built. A weak body lists technologies and actions without explaining purpose or impact.

Role Fit (0–25 pts): The letter directly engages with the specific angle of this role using only the candidate's actual experience. Evaluate how well the candidate connects what they have built to what this role requires. Do not penalize for skills or experience absent from the candidate data — only evaluate the strength of the connections that are made.

Company Specificity (0–20 pts): The closing demonstrates genuine understanding of what this company does and connects it to something the candidate has built. If the job description provides limited company or technical context, evaluate whether the candidate makes a reasonable connection to what is available. Do not penalize for specificity that the job description itself cannot support.

Clarity & Professionalism (0–10 pts): The letter is clean, concise, and free of errors. No unfilled placeholders. Uses only information present in the candidate data.

Before scoring, verify every outcome or result claim in the letter against the candidate data:
1. Identify each claim of outcome, impact, or result in the letter
2. Find the corresponding project or experience in the candidate data
3. If the claim cannot be traced directly to the candidate data, it is fabrication — quote what the candidate data actually says about that project and include it in your feedback so the generator can use accurate information instead
Mark acceptable: false if any fabrication is found.


Scoring rules:
- If the letter has clear fixable weaknesses, provide direct feedback of 2-4 sentences ordered by impact and mark acceptable: false
- Otherwise mark acceptable: true
- Do not suggest skills or experience not present in the candidate data
- Do not suggest adding metrics, percentages, or quantified results not present in the candidate data. If no metrics exist, evaluate whether the candidate explains the reasoning behind technical decisions
- If the job description provides insufficient context to identify a specific technical challenge, do not require company-specific technical connections in the closing. A reasonable connection to the company's stated focus is sufficient

## Candidate Data:
{candidate_json}
"""


    def evaluator_cover_letter(self, job_info: JobDescription, cover_letter):
        formatted_job_info = job_info.model_dump_json(indent=2)
        return f"Job Description:\n{formatted_job_info}\n\nCover Letter:\n{cover_letter}"


    def evaluate(self, job_info: JobDescription, cover_letter) -> Evaluation:
        messages = [
            {"role": "system", "content": self.evaluator_system_prompt},
            {"role": "user", "content": self.evaluator_cover_letter(job_info, cover_letter)},
        ]
        response = self.openai.responses.parse(
            model=self.evaluator_model,
            reasoning = {"effort":"medium"},
            input=messages,
            text_format = Evaluation,
            )
        return response.output_parsed


    def run(self, user_message: str) -> str:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_message},
        ]
        response = self.openai.responses.create(
            model=self.creator_model,
            input=messages,
        )
        return response.output_text


    def request_letter(self, job_info: JobDescription):
        logger.info("Requesting cover letter")
        logger.info(f"Job: {job_info.job_title or 'N/A'} at {job_info.company_name or 'N/A'}")

        job_message = "## Job Posting\n" + job_info.model_dump_json(indent=2)
        cover_letter = self.run(
            job_message
            + "\n\n## Cover Letter Template (Use as starting point. Replace all bracketed placeholders with actual content from the candidate data and job description)\n"
            + self.cover_letter_template
        )

        max_score = -1
        best_cover_letter = cover_letter
        best_feedback = ""
        eval_counter = 0

        while eval_counter < self.eval_limit:
            evaluation = self.evaluate(job_info, cover_letter)
            if evaluation.is_acceptable:
                logger.info("Passed evaluation - returning reply")
                logger.info(f"## Score:{evaluation.score}")
                logger.info(f"## Cover Letter:\n{cover_letter}")
                logger.info(f"## Feedback:\n{evaluation.feedback}")
                if self.include_feedback:
                    return cover_letter + "\n\n\n" + evaluation.feedback
                return cover_letter

            else:
                logger.info("Failed evaluation - retrying")
                logger.info(f"## Score:{evaluation.score}")
                logger.info(f"## Cover Letter:\n{cover_letter}")
                logger.info(f"## Feedback:\n{evaluation.feedback}")

            if evaluation.score > max_score:
                max_score = evaluation.score
                best_cover_letter = cover_letter
                best_feedback = evaluation.feedback

            eval_counter += 1

            cover_letter = self.run(
                job_message
                + "\n\n## Previous Attempt (rejected)\n" + cover_letter
                + "\n\n## Feedback\n" + evaluation.feedback
            )

    def convert_cover_letter_to_pdf(self, cover_letter_text: str, *, company_name: str | None = None):
        """Convert cover letter text to PDF."""
        if not cover_letter_text or not cover_letter_text.strip():
            logger.warning("No cover letter text provided for PDF conversion")
            return None

        company_name_sanitized = sanitize_filename(company_name) if company_name else ""
        filename_base = f"cover_letter_{company_name_sanitized}" if company_name_sanitized else "cover_letter"

        try:
            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer, pagesize=letter,
                rightMargin=72, leftMargin=72,
                topMargin=72, bottomMargin=72,
            )

            styles = getSampleStyleSheet()
            normal_style = styles["Normal"]
            normal_style.fontSize = 11
            normal_style.leading = 14
            normal_style.spaceAfter = 12

            story = []
            for para in cover_letter_text.split("\n\n"):
                if para.strip():
                    story.append(Paragraph(para.replace("\n", " "), normal_style))
                    story.append(Spacer(1, 12))

            doc.build(story)
            pdf_path = save_output_file(f"{filename_base}.pdf", buffer.getvalue(), prefix="cover_letter")
            logger.info(f"Cover letter PDF created: {pdf_path}")
            return str(pdf_path)

        except Exception as e:
            logger.error(f"Error creating cover letter PDF: {e}")
            return None