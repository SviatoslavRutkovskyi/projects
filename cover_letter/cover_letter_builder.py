from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader
import gradio as gr
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup

load_dotenv(override=True)


class Evaluation(BaseModel):
    is_acceptable: bool
    feedback: str



def scrape_webpage_simple(url):
    try:
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
        return soup.get_text()
        
        
    except requests.RequestException:
        return 'error'
    except Exception:
        return 'error'



class CoverLetterBuilder:



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
            self.system_prompt =  f"""You are a proffesional cover letter writer, and your job is to write a cover letter for {name}, highlighting {name}'s skills, experience, and achievements. 
particularly questions related to {name}'s career, background, skills and experience. 
Your responsibility is to represent {name} in the letter as faithfully as possible. 
You are given a summary of {name}'s background and Resume which you can use in the cover letter. 
You are given an example of a cover letter from {name}. Try and use a similar language and style. Do NOT include the placeholder information in the cover letter. 
Be professional and engaging, uing the tone and style suitable for a cover letter.
Do not make up any information, and only use the information provided.
Don't be too verbose, and use a 3 paragraph format.
Respond with a cover letter and nothing else.
Do not include the address or contact information. 
You will be given a job description, and you will need to tailor the cover letter to the job description.
You will be evaluated, and if evalutor decides that your cover letter is not up to standart, you will be given your previus cover letters and feedback on them. 
You have to listen to the feedback, and improve your cover letter accordingly to the feedback.
\n\n## Summary:\n{summary}\n\n## Resume:\n{resume}\n\n ## Cover Letter Template:\n{cover_letter_template}\n\n
"""
        else:
            self.system_prompt = system_prompt


        self.updated_system_prompt = self.system_prompt

        # Evaluator prompt - Tweak it for the best results. 
        if (evaluator_prompt == ""):            
            self.evaluator_system_prompt = f"""
You are a professional evaluator that decides whether a cover letter is acceptable. 
You are provided with {name}'s summary and resume, an example of a cover letter from {name}, the job description, and the cover letter. 
Your task is to evaluate the cover letter, and reply with whether it is acceptable and your feedback. 
You need to ensure if the cover letter is professional, engaging, and tailored to the job description. 
You need to ensure if the cover letter was likely made by AI, and if it was made by AI, deny it, and provide feedback. Do not allow AI generated cover letters.
You need to ensure that the cover letter has a strong and engaging opening paragraph. 
You need to ensure that the cover letter is concise and uses the standard 3 paragraph format.
Here's the information:
\n\n## Summary:\n{summary}\n\n## Resume:\n{resume}\n\n## Cover Letter Template:\n{cover_letter_template}\n\n
With this context, please evaluate the cover letter, replying with whether the cover letter is acceptable and your feedback.
"""
        else:
            self.evaluator_system_prompt = evaluator_prompt
        
        # UI 
        with gr.Blocks(theme=gr.themes.Default(primary_hue="sky")) as ui:
            gr.Markdown("# Cover Letter Builder")
            with gr.Row():
                job_post_textbox = gr.Textbox(label="Paste the job posting text or link here", lines = 20)
                cover_letter_textbox = gr.Textbox(label="Cover Letter", lines=20)
            
            run_button = gr.Button("Run", variant="primary")
            run_button.click(fn=self.requestLetter, inputs=job_post_textbox, outputs=cover_letter_textbox)
            job_post_textbox.submit(fn=self.requestLetter, inputs=job_post_textbox, outputs=cover_letter_textbox)

        ui.launch(inbrowser=True)
        


    @staticmethod
    def evaluator_cover_letter(job_post, cover_letter):
        return f"""
    Here's the job posting presented by the user: \n\n{job_post}\n\n
    Here's the cover letter generated by the agent: \n\n{cover_letter}\n\n
    Please evaluate the response, replying with whether it is acceptable and your extensive feedback.
    """


    def update_system_prompt(self, cover_letter, feedback):
        self.updated_system_prompt = self.updated_system_prompt + f"""
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


    def requestLetter(self, job_posting):
        page = scrape_webpage_simple(job_posting)
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



# runs the code
if __name__ == "__main__":
    CoverLetterBuilder()    