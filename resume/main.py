from dotenv import load_dotenv
from pypdf import PdfReader
import gradio as gr
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from resume import Resume
from cover_letter import CoverLetter

load_dotenv(override=True)


class Main:
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
                candidate_json_path = "resources/candidate.json",
                cover_letter_system_prompt = "",
                cover_letter_evaluator_prompt = "",
                resume_system_prompt = "",
                include_feedback = False
                ):
        
        
        # Cache for scraped content to avoid repeated scraping between request_letter and tailor_resume
        self.scraped_content_cache = {}
        
        # Use empty.pdf for consistent file component sizing
        self.empty_file_path = "resources/empty.pdf"
    


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
   
        self.resume_builder = Resume(
            creator_model=creator_model, 
            candidate_json_path=candidate_json_path,
            system_prompt=resume_system_prompt)
        self.cover_letter_builder = CoverLetter(
            evaluator_model=evaluator_model, 
            name = name, 
            eval_limit = eval_limit,
            summary_path = summary_path,
            cover_letter_path = cover_letter_path,
            resume_path = resume_path,
            system_prompt = cover_letter_system_prompt,
            evaluator_prompt = cover_letter_evaluator_prompt,
            include_feedback = include_feedback)
        self.cache = {}

        self.launch()
        

    def launch(self):
        with gr.Blocks(theme=gr.themes.Default(primary_hue="sky")) as ui:
            gr.Markdown("# Cover Letter Builder")
            with gr.Row():
                job_post_textbox = gr.Textbox(label="Paste the job posting text or URL here (URLs will be automatically scraped)", lines = 20)
                cover_letter_textbox = gr.Textbox(label="Cover Letter", lines=20)
                
            with gr.Row():
                run_button = gr.Button("Run", variant="primary")
                convert_pdf_button = gr.Button("Convert to PDF", variant="secondary")
                cover_letter_file = gr.File(label="Cover Letter PDF", value=self.empty_file_path, visible=False)
            
            run_button.click(fn=lambda job_posting: self.cover_letter_builder.request_letter(self.process_job_posting(job_posting)), inputs=job_post_textbox, outputs=cover_letter_textbox)
            
            job_post_textbox.submit(fn=lambda job_posting: self.cover_letter_builder.request_letter(self.process_job_posting(job_posting)), inputs=job_post_textbox, outputs=cover_letter_textbox)

            convert_pdf_button.click(fn=lambda: gr.File(value=self.empty_file_path, visible=True), outputs=cover_letter_file).then(
                fn=self.cover_letter_builder.convert_cover_letter_to_pdf, 
                inputs=cover_letter_textbox, 
                outputs=cover_letter_file
            )
            


            gr.Markdown("## Resume Tailoring")
            resume_feedback_textbox = gr.Textbox(label="Resume Feedback", lines=5)
            
            with gr.Row():
                resume_button = gr.Button("Tailor Resume", variant="primary", scale=2)
                use_last_resume_checkbox = gr.Checkbox(label="Use Last Resume", value=False, visible=False, scale=1)
                resume_file = gr.File(label="Tailored Resume PDF", value=self.empty_file_path, visible=False)
                               
            
            resume_button.click(fn=lambda: gr.File(value=self.empty_file_path, visible=True), outputs=resume_file).then(
                fn=lambda job_posting, resume_feedback, use_last_resume: self.resume_builder.tailor_resume(self.process_job_posting(job_posting), resume_feedback, use_last_resume), 
                inputs=[job_post_textbox, resume_feedback_textbox, use_last_resume_checkbox], 
                outputs=[resume_file]).then(
                fn=lambda: gr.Checkbox(visible=True), 
                outputs=use_last_resume_checkbox)
            
        
        ui.launch(inbrowser=True)

    
    def is_url(self, text):
        """Check if the input text is a valid URL"""
        try:
            result = urlparse(text)
            return all([result.scheme, result.netloc])
        except:
            return False
    
    def scrape_webpage_simple(self, url):
        # Check cache first
        if url in self.cache:
            print(f"Using cached content for {url}")
            return self.cache[url]
        
        try:
            print(f"Scraping {url}")
            # Set headers to mimic a real browser
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # Make the request
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()  # Raise an error for bad status codes
            
            # Parse the HTML
            soup = BeautifulSoup(response.content, 'html.parser')

            # Get all text content
            content = soup.get_text()
            
            # Clean up the content - remove extra whitespace
            content = ' '.join(content.split())
            
            # Cache the content
            self.cache[url] = content
                
            return content
            
        except requests.RequestException as e:
            print(f"Request error for {url}: {e}")
            return None
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None
    
    def process_job_posting(self, job_posting):
        """Process job posting input - scrape if URL, return as-is if text, raise exception if URL scraping fails"""
        if self.is_url(job_posting.strip()):
            print(f"Detected URL: {job_posting}")
            scraped_content = self.scrape_webpage_simple(job_posting.strip())
            if scraped_content is not None:
                print("Successfully scraped webpage content")
                return scraped_content
            else:
                print("Failed to scrape webpage - URL will not be processed")
                raise Exception("Could not scrape the provided URL. Please provide the job description as text instead.")
        else:
            print("Input is text, using as-is")
            return job_posting
    
    # runs the code
if __name__ == "__main__":
    Main()    

