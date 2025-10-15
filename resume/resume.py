from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader
import subprocess
import os


class Resume:
        # Can take all of the following as optional parameters.
    # Pass in the parameters that you want to change from the default values. 
    def __init__(self, 
                creator_model = "gpt-4o", 
                resume_path = "resources/resume_original.tex",
                projects_path = "resources/projects.txt",
                system_prompt = "",
                ):
        
        self.resume_path = resume_path
        self.creator_model = creator_model

        self.use_last_resume = False
        self.last_resume_content = None
        
    
        # AI models 
        self.openai = OpenAI()
   
        with open(resume_path, "r") as f:
            resume_tex = f.read()

        with open(projects_path, "r") as f:
            projects = f.read()

        if (system_prompt == ""):
            self.system_prompt = f"""
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
            resume = self.run(prompt_with_last_resume, "Feedback: " + resume_feedback + "\n\nJob Posting: \n" + job_posting)
        elif use_last_resume and not self.last_resume_content:
            print("No previous resume available. Creating a new resume from the original template.")
            resume = self.run(self.system_prompt, "Feedback: " + resume_feedback + "\n\nJob Posting: \n" + job_posting)
        else:
            resume = self.run(self.system_prompt, "Feedback: " + resume_feedback + "\n\nJob Posting: \n" + job_posting)

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

        # Store the generated resume content for future use
        self.last_resume_content = resume
        print("Stored last resume content for future tailoring")

        return pdf_path


    def run(self, prompt, job_posting):
        messages = [{"role": "system", "content": prompt}] + [{"role": "user", "content": job_posting}]
        response = self.openai.chat.completions.create(model=self.creator_model, messages=messages)
        return response.choices[0].message.content   

