from dotenv import load_dotenv
from openai import OpenAI
import os
import glob
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from models import AppConfig, Evaluation, JobDescription
from utils import sanitize_filename, load_candidate_data

load_dotenv(override=True)


class CoverLetter:
    def __init__(
        self,
        config: AppConfig,
        creator_model="gpt-4o",
        evaluator_model="o4-mini",
        eval_limit=10,
        include_feedback=False,
    ):

        self.config = config
        self.creator_model = creator_model
        self.evaluator_model = evaluator_model
        self.eval_limit = eval_limit
        self.include_feedback = include_feedback
        
        # Use empty.pdf for consistent file component sizing
        self.empty_file_path = str(self.config.empty_pdf)
        
        # Store last job info for PDF filename
        self.last_job_info = None
    
        # AI models 
        self.openai = OpenAI()

        with open(self.config.cover_letter_example, encoding="utf-8") as f:
            cover_letter_example = f.read()

        with open(self.config.cover_letter_template, encoding="utf-8") as f:
            cover_letter_template = f.read()

        candidate_data = load_candidate_data(self.config.candidate_json)
        candidate_json = candidate_data.model_dump_json(indent=2)

        self.system_prompt = f"""
You are a professional cover letter writer writing on behalf of {self.config.name}.

You are given {self.config.name}'s resume data, a template showing structure, and an example showing the quality bar to meet.

The template defines what goes in each section. The example shows the tone, depth, and style to match. When they conflict, follow the template for structure and the example for quality.

Your goal is to produce a letter where every sentence is specific enough that it would be false if applied to a different candidate. Do not write sentences that could appear in any candidate's letter. Select the most relevant projects and experiences from the candidate data for this job — do not default to projects mentioned in the example. Address the specific requirements and focus of this role directly.

- Replace all bracketed placeholders with actual values from the candidate data and job description
- The opening line must be a claim or observation — never begin with a thesis statement like "X is a formidable challenge" or "I am applying for"
- Do not echo the job description's language back at the reader — make specific technical connections instead
- The [Other experience that would differentiate the candidate if present] placeholder should only be filled if a specific, non-generic connection to the role exists — otherwise omit it entirely
- Use only information from the resume data — do not fabricate metrics, percentages, or figures not explicitly stated in the candidate data
- Respond with cover letter text only — no preamble or commentary
- Write between 250 and 400 words

If given a rejected cover letter and feedback, treat each criticism as a specific failure mode to fix, not a suggestion to acknowledge.

## Candidate Data:
{candidate_json}

## Cover Letter Template (follow this structure):
{cover_letter_template}

## Example Cover Letter (match this tone, depth, and style):
{cover_letter_example}
"""


        self.evaluator_system_prompt = f"""
You are a professional hiring manager evaluating a cover letter for submission.
Your job is to determine whether the cover letter is ready to send based on five dimensions.

You are provided with:
- The candidate's resume data
- The job description
- The cover letter to evaluate

Opening (0–20 pts): The first sentence makes a specific claim, frames a hard problem, or leads with a strong relevant achievement tied to this role. A strong opening is one that only this candidate could have written for this job.

Depth & Framing (0–25 pts): The letter explains why projects were built, what problem was being solved, and how technical decisions affected the user or end customer. It adds perspective the resume cannot. A strong body section shows how the candidate thinks, not just what they built.

Role Fit (0–25 pts): The letter directly engages with the specific angle of this role using only the candidate's actual experience. Evaluate how well the candidate connects what they have built to what this role requires. Do not penalize for skills or experience absent from the candidate data — only evaluate the strength of the connections that are made.

Company Specificity (0–20 pts): The closing demonstrates genuine understanding of what this company does and connects it to something the candidate has built. If the job description provides limited company or technical context, evaluate whether the candidate makes a reasonable connection to what is available. Do not penalize for specificity that the job description itself cannot support.

Clarity & Professionalism (0–10 pts): The letter is clean, concise, and free of errors. Word count is between 250 and 400 words. No unfilled placeholders. Uses only information present in the candidate data.

Scoring rules:
- If the letter contains any unfilled bracketed placeholders, mark acceptable: false
- If the letter contains fabricated information not present in the candidate data, mark acceptable: false
- If the score is above 75, mark acceptable: true
- If the letter has clear weaknesses that can be fixed using only information present in the candidate data, provide direct specific feedback of 2-4 sentences and mark acceptable: false
- If the letter has no clear weaknesses that can be fixed using only information present in the candidate data, mark acceptable: true
- Do not suggest skills or experience not present in the candidate data.
- Do not suggest adding metrics, percentages, or quantified results not present in the candidate data. If no metrics exist, evaluate whether the candidate explains the reasoning behind technical decisions.
- If the job description provides insufficient context to identify a specific technical challenge, do not require company-specific technical connections in the closing. A reasonable connection to the company's stated focus is sufficient.

## Candidate Data:
{candidate_json}
"""

   

    def evaluator_cover_letter(self, job_info: JobDescription, cover_letter):
        formatted_job_info = job_info.model_dump_json(indent=2)
        return f"Job Description:\n{formatted_job_info}\n\nCover Letter:\n{cover_letter}"


    def update_system_prompt(self, cover_letter, feedback):
        return self.system_prompt + f"""

    ## Previous Attempt (rejected):
    {cover_letter}

    ## Feedback:
    {feedback}
    """


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


    def run(self, prompt, job_info: JobDescription):
        formatted_job_info = job_info.model_dump_json(indent=2)
        messages = [{"role": "system", "content": prompt}] + [{"role": "user", "content": formatted_job_info}]
        response = self.openai.chat.completions.create(model=self.creator_model, messages=messages)
        return response.choices[0].message.content


    def request_letter(self, job_info: JobDescription):
        print("Requesting cover letter")
        print(f"Job: {job_info.job_title or 'N/A'} at {job_info.company_name or 'N/A'}")
        self.last_job_info = job_info  # Store for PDF filename
        cover_letter = self.run(self.system_prompt, job_info)

        max_score = -1
        best_cover_letter = cover_letter
        best_feedback = ""
        eval_counter = 0

        while eval_counter < self.eval_limit:
            evaluation = self.evaluate(job_info, cover_letter)
            if evaluation.is_acceptable:
                print("Passed evaluation - returning reply")
                print(f"## Score:{evaluation.score}")
                print(f"## Cover Letter:\n{cover_letter}")
                print(f"## Feedback:\n{evaluation.feedback}")
                if self.include_feedback:
                    return cover_letter + "\n\n\n" + evaluation.feedback
                return cover_letter

            print("Failed evaluation - retrying")
            print(f"## Score:{evaluation.score}")
            print(f"## Cover Letter:\n{cover_letter}")
            print(f"## Feedback:\n{evaluation.feedback}")

            if evaluation.score > max_score:
                max_score = evaluation.score
                best_cover_letter = cover_letter
                best_feedback = evaluation.feedback

            eval_counter += 1

            cover_letter = self.run(
                self.update_system_prompt(cover_letter, evaluation.feedback),
                job_info,
            )

        print("Failed evaluation - returning best-scoring attempt")
        print(f"## Best score (across attempts):{max_score}")
        print(f"## Cover Letter:\n{best_cover_letter}")
        print(f"## Feedback (for that attempt):\n{best_feedback}")
        if self.include_feedback and best_feedback:
            return best_cover_letter + "\n\n\n" + best_feedback
        return best_cover_letter

    def convert_cover_letter_to_pdf(self, cover_letter_text):
        """Convert cover letter text to PDF"""
        try:
            # Check if text is empty
            if not cover_letter_text or not cover_letter_text.strip():
                print("No cover letter text provided for PDF conversion")
                return None
                
            output_dir = "static/output"
            os.makedirs(output_dir, exist_ok=True)
            
            # Remove old cover letter file (only expecting 1 cover letter file)
            for old_file in glob.glob(os.path.join(output_dir, "cover_letter*")):
                os.remove(old_file)
            
            # Create filename with company name
            company_name = self.last_job_info.company_name if self.last_job_info else None
            if company_name:
                company_name_sanitized = sanitize_filename(company_name)
                if company_name_sanitized:
                    filename_base = f"cover_letter_{company_name_sanitized}"
                else:
                    filename_base = "cover_letter"
            else:
                filename_base = "cover_letter"
            
            pdf_path = os.path.join(output_dir, f"{filename_base}.pdf")
            
            # Create PDF document
            doc = SimpleDocTemplate(pdf_path, pagesize=letter,
                                  rightMargin=72, leftMargin=72,
                                  topMargin=72, bottomMargin=72)
            
            # Get styles
            styles = getSampleStyleSheet()
            normal_style = styles['Normal']
            normal_style.fontSize = 11
            normal_style.leading = 14
            normal_style.spaceAfter = 12
            
            # Build story
            story = []
            
            # Split text into paragraphs and add to story
            paragraphs = cover_letter_text.split('\n\n')
            for para in paragraphs:
                if para.strip():
                    # Replace single line breaks with spaces within paragraphs
                    para = para.replace('\n', ' ')
                    story.append(Paragraph(para, normal_style))
                    story.append(Spacer(1, 12))
            
            # Build PDF
            doc.build(story)
            
            print(f"Cover letter PDF created: {pdf_path}")
            return pdf_path
            
        except Exception as e:
            print(f"Error creating cover letter PDF: {str(e)}")
            return None

 