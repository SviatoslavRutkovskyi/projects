from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader
import gradio as gr
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, send_file
import subprocess
import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

load_dotenv(override=True)


class Evaluation(BaseModel):
    is_acceptable: bool
    feedback: str



def scrape_webpage_simple(url, cache=None):
    # Check cache first
    if cache and url in cache:
        print(f"Using cached content for {url}")
        return cache[url]
    
    try:
        print(f"Scraping {url}")
        # Set headers to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0'
        }
        
        # Make the request
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Raise an error for bad status codes
        
        # Parse the HTML
        soup = BeautifulSoup(response.content, 'html.parser')

        # Get all text content
        content = soup.get_text()
        
        # Cache the content
        if cache is not None:
            cache[url] = content
            
        return content
        
    except requests.RequestException:
        return 'error'
    except Exception:
        return 'error'



class ResumeBuilder:
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
        
        # Cache for scraped content to avoid repeated scraping between request_letter and tailor_resume
        self.scraped_content_cache = {}
        
        # Use empty.pdf for consistent file component sizing
        self.empty_file_path = "resources/empty.pdf"
    
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
                You are a professional cover letter editor that decides whethera cover letter is acceptable. 
                You are provided with {name}'s summary and resume, an example of a cover letter from {name}, the job description, and the cover letter. 
                Your task is to evaluate the cover letter, and reply with whether it is acceptable and your feedback. Include a score from 0 to 100 with your feedback.
                You need to ensure if the cover letter is professional, engaging, and tailored to the job description. 
                You need to ensure if the cover letter was likely made by AI, and if it was made by AI, deny it, and provide feedback. Do not allow AI generated cover letters.
                You need to ensure that the cover letter has a strong and engaging opening paragraph. 
                You need to ensure that the cover letter is concise and uses the standard 3 paragraph format.
                Do not focus on adding skills that the user does not have.
                Here's the information:
                \n\n## Summary:\n{summary}\n\n## Resume:\n{resume}\n\n

                With this context, please evaluate the cover letter, replying with whether the cover letter is acceptable and your feedback.
                """
# ## Cover Letter Template:\n{cover_letter_template}\n\n
        else:
            self.evaluator_system_prompt = evaluator_prompt
   
        with open("resources/resume_original.tex", "r") as f:
            resume_tex = f.read()

        with open("resources/projects.txt", "r") as f:
            projects = f.read()

        self.resume_prompt = f"""
            You are helping tailor a LaTeX resume.

            Here is the current LaTeX resume:
            {resume_tex}

            Here is the list of projects you list on the resume:
            {projects}

            Please:
            - Rewrite the Profile section to emphasize alignment with the job.
            - Reorder/trim the SKILLS section to highlight the most relevant ones.
            - Select the most relevant PROJECTS/EXPERIENCES.
            - Return the full LaTeX code for the resume, keeping the formatting intact.
            - Make sure that the resume fills the page, but does not overflow.
            - Do not include markdown formatting, and any other text or comments.
            - Do not modify the resume outside of the sections that are specified.
            - Implement the feedback provided by the user.
            """     
        self.launch()
        

    def launch(self):
        with gr.Blocks(theme=gr.themes.Default(primary_hue="sky")) as ui:
            gr.Markdown("# Cover Letter Builder")
            with gr.Row():
                job_post_textbox = gr.Textbox(label="Paste the job posting text or link here", lines = 20)
                cover_letter_textbox = gr.Textbox(label="Cover Letter", lines=20)
                
            with gr.Row():
                run_button = gr.Button("Run", variant="primary")
                convert_pdf_button = gr.Button("Convert to PDF", variant="secondary")
                cover_letter_file = gr.File(label="Cover Letter PDF", value=self.empty_file_path, visible=False)
            
            run_button.click(fn=self.request_letter, inputs=job_post_textbox, outputs=cover_letter_textbox)
            convert_pdf_button.click(fn=lambda: gr.File(value=self.empty_file_path, visible=True), outputs=cover_letter_file).then(
                fn=self.convert_cover_letter_to_pdf, 
                inputs=cover_letter_textbox, 
                outputs=cover_letter_file
            )


            resume_feedback_textbox = gr.Textbox(label="Resume Feedback", lines=5)
            
            with gr.Row():
                resume_button = gr.Button("Tailor Resume", variant="primary")
                resume_file = gr.File(label="Tailored Resume PDF", value=self.empty_file_path, visible=False)
                               
            
            resume_button.click(fn=lambda: gr.File(value=self.empty_file_path, visible=True), outputs=resume_file).then(
                fn=self.tailor_resume, 
                inputs=[job_post_textbox, resume_feedback_textbox], 
                outputs=resume_file
            )
            job_post_textbox.submit(fn=self.request_letter, inputs=job_post_textbox, outputs=cover_letter_textbox)
        
        ui.launch(inbrowser=True)

    @staticmethod
    def evaluator_cover_letter(job_post, cover_letter):
        return f"""
            Here's the job posting presented by the user: \n\n{job_post}\n\n
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


    def evaluate(self, job_post, cover_letter) -> Evaluation:
        messages = [
            {"role": "system", "content": self.evaluator_system_prompt},
            {"role": "user", "content": self.evaluator_cover_letter(job_post, cover_letter)},
            {"role": "user", "content": "Reply ONLY in valid JSON: {\"is_acceptable\": true/false, \"feedback\": \"...\"}"}
        ]
        response = self.openai.responses.parse(
            model=self.evaluator_model,
            reasoning = {"effort":"medium"},
            input=messages,
            text_format = Evaluation,
            )
        return response.output_parsed


    def run(self, prompt, job_posting):
        messages = [{"role": "system", "content": prompt}] + [{"role": "user", "content": job_posting}]
        response = self.openai.chat.completions.create(model=self.creator_model, messages=messages)
        return response.choices[0].message.content


    def request_letter(self, job_posting):
        page = scrape_webpage_simple(job_posting, self.scraped_content_cache)
        print(page)
        if page == 'error':
            print("Failed to scrape job posting")
        else:
            job_posting = page

        cover_letter = self.run(self.system_prompt, job_posting)
        # evalion limit - you can limit it to avoid expences

        eval_counter = 0
        while eval_counter < self.eval_limit:
            evaluation = self.evaluate(job_posting, cover_letter)
            if evaluation.is_acceptable:
                print("Passed evaluation - returning reply")
                print(f"## Cover Letter:\n{cover_letter}")
                print(f"## Feedback:\n{evaluation.feedback}")
                print(f"## Updated system prompt:\n{self.updated_system_prompt}")
                self.updated_system_prompt = self.system_prompt;
                if self.include_feedback:
                    return cover_letter + "\n\n\n" + evaluation.feedback;
                return cover_letter
            else:
                eval_counter += 1
                print("Failed evaluation - retrying")
                print(f"## Cover Letter:\n{cover_letter}")
                print(f"## Feedback:\n{evaluation.feedback}")
                cover_letter = self.run(self.update_system_prompt(cover_letter, evaluation.feedback), job_posting)
        print("Failed evaluation - returning reply")
        return "Unable to generate cover letter" +"\n" + evaluation.feedback    





    def tailor_resume(self, job_posting, resume_feedback):
        page = scrape_webpage_simple(job_posting, self.scraped_content_cache)
        print(page)
        if page == 'error':
            print("Failed to scrape job posting")
        else:
            job_posting = page
        
        resume = self.run(self.resume_prompt, "Feedback: " + resume_feedback + "\n\nJob Posting: \n" + job_posting)

        output_dir = "static/output"
        os.makedirs(output_dir, exist_ok=True)
        tex_path = os.path.join(output_dir, "resume.tex")
        pdf_path = tex_path.replace(".tex", ".pdf")

        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(resume)
        
        filename = os.path.basename(tex_path)  

        result = subprocess.run(
            ["tectonic", filename],
            cwd=output_dir,
            capture_output=True,
            text=True
        )

        print("Tectonic STDOUT:\n", result.stdout)
        print("Tectonic STDERR:\n", result.stderr)

        # Check if compilation was successful
        if result.returncode != 0:
            print(f"LaTeX compilation failed with return code {result.returncode}")
            print("Attempting to fix LaTeX with AI...")
            
            # Feed the error back to the AI to fix the LaTeX
            error_context = f"LaTeX compilation failed with return code {result.returncode}"
            if result.stderr:
                error_context += f"\nError details: {result.stderr}"
            
            fix_prompt = f"""
                The LaTeX compilation failed. Please fix the LaTeX code and return the corrected version.

                Error: {error_context}

                Current LaTeX code:
                {resume}

                Please return only the corrected LaTeX code, nothing else.
                Do not include markdown formatting, and any other text or comments.
                Do not include "latex" and "```" in the response.
                """
            
            # Get the fixed LaTeX from AI
            fixed_resume = self.run(fix_prompt, "")
            
            # Try compilation again with fixed LaTeX
            with open(tex_path, "w", encoding="utf-8") as f:
                f.write(fixed_resume)
            
            result = subprocess.run(
                ["tectonic", filename],
                cwd=output_dir,
                capture_output=True,
                text=True
            )
            
            print("Tectonic STDOUT (retry):\n", result.stdout)
            print("Tectonic STDERR (retry):\n", result.stderr)
            
            # If it still fails, return the original PDF path (might be empty/corrupted)
            if result.returncode != 0:
                print("LaTeX compilation failed even after AI fix attempt")

        return pdf_path




    def convert_cover_letter_to_pdf(self, cover_letter_text):
        """Convert cover letter text to PDF"""
        try:
            # Check if text is empty
            if not cover_letter_text or not cover_letter_text.strip():
                print("No cover letter text provided for PDF conversion")
                return None
                
            output_dir = "static/output"
            os.makedirs(output_dir, exist_ok=True)
            pdf_path = os.path.join(output_dir, "cover_letter.pdf")
            
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


# runs the code
if __name__ == "__main__":
    ResumeBuilder()    