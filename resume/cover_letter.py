from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader
import gradio as gr
import os
import glob
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from models import Evaluation, JobDescription
from utils import sanitize_filename

load_dotenv(override=True)


class CoverLetter:
    # Can take all of the following as optional parameters.
    # Pass in the parameters that you want to change from the default values. 
    def __init__(self, 
                creator_model = "gpt-4o", 
                evaluator_model = "o4-mini", 
                name = "Sviatoslav Rutkovskyi", 
                eval_limit = 10,
                summary_path = "../me/summary.txt",
                cover_letter_path = "../me/cover_letter_template.txt",
                resume_path = "../me/resume.pdf",
                system_prompt = "",
                evaluator_prompt = "",
                include_feedback = False
                ):
        
        
        self.creator_model = creator_model
        self.evaluator_model = evaluator_model
        self.eval_limit = eval_limit
        self.include_feedback = include_feedback
        
        # Use empty.pdf for consistent file component sizing
        self.empty_file_path = "resources/empty.pdf"
        
        # Store last job info for PDF filename
        self.last_job_info = None
    
        # AI models 
        self.openai = OpenAI()

        if (system_prompt == "" and evaluator_prompt == ""):
            with open(summary_path, "r", encoding="utf-8") as f:
                summary = f.read()

            with open(cover_letter_path, "r", encoding="utf-8") as f:
                cover_letter_template = f.read()

            reader = PdfReader(resume_path)
            resume = ""

            for page in reader.pages:
                text = page.extract_text()
                if text:
                    resume += text
        # System prompt - Tweak it for the best results. 
        if (system_prompt == ""):
            self.system_prompt =  f"""
You are a proffesional cover letter writer, and your job is to write a cover letter for {name}, highlighting {name}'s skills, experience, and achievements. 
You will be given a job description, and you will need to tailor the cover letter to the job description.
Your responsibility is to represent {name} in the letter as faithfully as possible. 
You are given a summary of {name}'s background and Resume which you can use in the cover letter. 
You are given an example of a cover letter from {name}. Try and use a similar language and style. Do NOT include the placeholder information in the cover letter. 
Be professional and engaging, uing the tone and style suitable for a cover letter.
Do not make up any information, and only use the information provided.
Don't be too verbose, and use a 3 paragraph format.
Avoid filler words and buzzwords such as “passionate,” “thrilled,” “dynamic,” “cutting-edge,” “fast-paced environment,” or “innovative solutions.”
Show confidence through concrete examples, not adjectives
Incorporate keywords and skills from the provided job description to ensure it passes an ATS scan.
Mention technical tools, programming languages, and frameworks naturally within sentences
Focus on relevant achievements and measurable outcomes
Tie experiences directly to the company’s focus or mission — explain why you’re interested, but in one grounded sentence
Respond with a cover letter and nothing else.
Do not include the job description in the cover letter.
Avoid exaggeration, emotional language, or clichés
Do not include the address or contact information. 
You will be evaluated, and if evalutor decides that your cover letter is not up to standart, you will be given your previus cover letter and feedback on it. 
You have to listen to the feedback, and improve your cover letter accordingly to the feedback.
\n\n## Summary:\n{summary}\n\n## Resume:\n{resume}\n\n ## Cover Letter Template:\n{cover_letter_template}\n\n
            """
        else:
            self.system_prompt = system_prompt


        self.updated_system_prompt = self.system_prompt

        # Evaluator prompt - Tweak it for the best results. 
        if (evaluator_prompt == ""):            
            self.evaluator_system_prompt = f"""
You are a professional hiring manager and cover letter evaluator.
Your job is to determine whether a cover letter is acceptable for submission based on its professionalism, clarity, authenticity, and alignment with the job description.
You are provided with:
- The candidate’s summary and resume
- A sample cover letter from the candidate (for tone comparison)
- The job description
- The cover letter to evaluate

Evaluate the cover letter on the following dimensions:
- Professionalism (0–25 pts): Grammar, tone, formatting, and flow are clear and appropriate for a job application
-Engagement & Authenticity (0–25 pts): The letter sounds human, personal, and specific to the applicant — not generic or AI-generated. Watch for overly polished, repetitive, or vague language (e.g., “passionate about innovation,” “dynamic environment,” “cutting-edge solutions”).
- Relevance & Tailoring (0–25 pts): The letter references relevant skills, technologies, or experiences from the candidate’s resume that match the job description. It clearly connects the applicant’s background to the company’s needs.
- Structure & Conciseness (0–25 pts): The letter follows a logical three-paragraph format (intro, body, closing) and stays under 250 words. Sentences are concise and readable.

If the letter appears AI-generated or contains unnatural phrasing (overuse of em dashes, buzzwords, or generic structure), mark it as “AI-generated” and deny it.
Provide a short explanation describing why it seems AI-generated (e.g., “formulaic tone,” “vague enthusiasm,” “no specific details from resume”).

Provide a final verdict: Acceptable: true/false
Provide a numerical score from 0 to 100.
Give brief, actionable feedback (2–4 sentences) that focuses on the highest-impact improvements.
Do not invent or suggest new skills that are not on the resume.

Here's the information:
\n\n## Summary:\n{summary}\n\n## Resume:\n{resume}\n\n ## Cover Letter Template:\n{cover_letter_template}\n\n
                """
# ## Cover Letter Template:\n{cover_letter_template}\n\n
        else:
            self.evaluator_system_prompt = evaluator_prompt
   


    def evaluator_cover_letter(self, job_info: JobDescription, cover_letter):
        formatted_job_info = job_info.model_dump_json(indent=2)
        return f"""
            Here's the job posting information presented by the user: \n\n{formatted_job_info}\n\n
            Here's the cover letter generated by the agent: \n\n{cover_letter}\n\n
            Please evaluate the response, replying with whether it is acceptable and your extensive feedback.
            """


    def update_system_prompt(self, cover_letter, feedback):
        self.updated_system_prompt = self.system_prompt + f"""
\n\n## Previous cover letter rejected\nYou just tried to create a cover letter, but the quality control rejected your cover letter\n
## Your attempted cover letter:\n{cover_letter}\n\n
## Reason for rejection:\n{feedback}\n\n
            """
        return self.updated_system_prompt;


    def evaluate(self, job_info: JobDescription, cover_letter) -> Evaluation:
        messages = [
            {"role": "system", "content": self.evaluator_system_prompt},
            {"role": "user", "content": self.evaluator_cover_letter(job_info, cover_letter)},
            {"role": "user", "content": "Reply ONLY in valid JSON: {\"is_acceptable\": true/false, \"feedback\": \"...\", \"score\": 0-100}"}
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

        eval_counter = 0
        while eval_counter < self.eval_limit:
            max_score = 0
            best_cover_letter = ""
            evaluation = self.evaluate(job_info, cover_letter)
            if evaluation.is_acceptable:
                print("Passed evaluation - returning reply")
                print(f"## Score:{evaluation.score}")
                print(f"## Cover Letter:\n{cover_letter}")
                print(f"## Feedback:\n{evaluation.feedback}")
                # print(f"## Updated system prompt:\n{self.updated_system_prompt}")
                self.updated_system_prompt = self.system_prompt;
                if self.include_feedback:
                    return cover_letter + "\n\n\n" + evaluation.feedback;
                return cover_letter
            else:
                eval_counter += 1
                print("Failed evaluation - retrying")
                print(f"## Score:{evaluation.score}")
                print(f"## Cover Letter:\n{cover_letter}")
                print(f"## Feedback:\n{evaluation.feedback}")
                cover_letter = self.run(self.update_system_prompt(cover_letter, evaluation.feedback), job_info)
                if evaluation.score > max_score:
                    max_score = evaluation.score
                    best_cover_letter = cover_letter
        print("Failed evaluation - returning reply")
        print(f"## Score:{evaluation.score}")
        print(f"## Cover Letter:\n{cover_letter}")
        print(f"## Feedback:\n{evaluation.feedback}")
        if self.include_feedback:
            return best_cover_letter + "\n\n\n" + evaluation.feedback;
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
                                  topMargin=72, bottomMargin=18)
            
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

 