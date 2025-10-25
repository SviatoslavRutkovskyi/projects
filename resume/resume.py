from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader
import subprocess
import os
from latex_generator import LatexGenerator
from models import ResumeData


class Resume:
        # Can take all of the following as optional parameters.
    # Pass in the parameters that you want to change from the default values. 
    def __init__(self, 
                creator_model = "gpt-5-mini", 
                resume_path = "resources/resume_original.pdf",
                projects_path = "resources/projects.txt",
                system_prompt = "",
                ):
        
        self.resume_path = resume_path
        self.creator_model = creator_model
        self.latex_generator = LatexGenerator()

        self.use_last_resume = False
        self.last_resume_content = None
        
    
        # AI models 
        self.openai = OpenAI()
   
        # with open(resume_path, "r") as f:
        #     resume_tex = f.read()
        
        reader = PdfReader(resume_path)
        resume = ""

        for page in reader.pages:
            text = page.extract_text()
            if text:
                resume += text

        with open(projects_path, "r") as f:
            projects = f.read()

        if (system_prompt == ""):
            self.system_prompt = f"""
You are helping tailor a resume to a given job posting.

Here is the current LaTeX resume:
{resume}

Here is the list of projects you can list on the resume:
{projects}

Please:
- Rewrite the Profile section to emphasize alignment with the job.
- Reorder/trim the SKILLS section to highlight the most relevant ones.
- Select the most relevant PROJECTS/EXPERIENCES.
- Return the resume in a JSON format.
- Include 1 - 2 experiences that are relevant to the job posting.
- Include 2 - 3 bullet points for each experience.
- Include 2 - 3 projects that are relevant to the job posting.
- Include 3 - 4 bullet points for each project.
- Do not include markdown formatting, and any other text or comments.
- Do not fake any information, and only use the information provided.
- If you are given addional user instructions, follow them. Do not modify the resume outside of the sections that are specified.
            """    
        else:
            self.system_prompt = system_prompt


    def tailor_resume(self, job_posting, resume_feedback, use_last_resume=False):
        
        # Use last resume as base if checkbox is checked and we have a previous resume
        if use_last_resume and self.last_resume_content:
            print("Using last resume as base for tailoring")
            prompt_with_last_resume = self.system_prompt + f"""

Here is the last generated resume that should be used as the base:
{self.last_resume_content}

Please tailor this existing resume rather than starting from the original template.
"""
            resume_data = self.run(prompt_with_last_resume, "User Instructions  : " + resume_feedback + "\n\nJob Posting: \n" + job_posting)
        elif use_last_resume and not self.last_resume_content:
            print("No previous resume available. Creating a new resume from the original template.")
            resume_data = self.run(self.system_prompt, "User Instructions: " + resume_feedback + "\n\nJob Posting: \n" + job_posting)
        else:
            resume_data = self.run(self.system_prompt, "User Instructions: " + resume_feedback + "\n\nJob Posting: \n" + job_posting)

        # Create output directory
        output_dir = "static/output"
        os.makedirs(output_dir, exist_ok=True)
        tex_path = os.path.join(output_dir, "resume.tex")
        pdf_path = tex_path.replace(".tex", ".pdf")

        # Convert JSON resume data to LaTeX
        latex_content = self.latex_generator.convert_json_to_latex(resume_data)
        
        if latex_content is None:
            print("Failed to create LaTeX from JSON resume data")
            return None

        # Write LaTeX to file
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(latex_content)
        
        filename = os.path.basename(tex_path)  

        # Compile LaTeX to PDF using tectonic
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
            print("LaTeX error details:", result.stderr)
            print("Please check the generated LaTeX file for issues.")
            return None

        # Store the generated resume content for future use
        self.last_resume_content = resume_data.model_dump_json()
        print("Stored last resume content for future tailoring")

        return pdf_path


    def run(self, prompt, job_posting) -> ResumeData:
        messages = [{"role": "system", "content": prompt},
        {"role": "user", "content": job_posting},
        {"role": "user", "content": "Reply ONLY in valid JSON: {\"profile\": \"...\", \"skills\": [{\"name\": \"...\", \"skills\": [\"...\"]}], \"projects\": [{\"name\": \"...\", \"date\": \"MMM YYYY\", \"github_link_names\": [\"...\"], \"github_links\": [\"...\"], \"bullet_points\": [\"...\"]}], \"experiences\": [{\"company_name\": \"...\", \"start_date\": \"MMM YYYY\", \"end_date\": \"MMM YYYY\", \"job_title\": \"...\", \"location\": \"...\", \"bullet_points\": [\"...\"]}]}"}
        ]
        response = self.openai.responses.parse(
            model=self.creator_model,
            input=messages,
            text_format = ResumeData,
            )
        return response.output_parsed   


