import logging
from dotenv import load_dotenv
import gradio as gr
from resume import Resume
from cover_letter import CoverLetter
from job_processor import JobProcessor
from question_answerer import QuestionAnswerer
from utils import validate_app_config
from models import JobDescription

load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


class Main:
    def __init__(
        self,
        creator_model="gpt-4o",
        evaluator_model="o4-mini",
        eval_limit=10,
        config_file: str = "resources/app_config.json",
        include_feedback=False,
    ):
        self.config = validate_app_config(config_file)
        self.empty_file_path = str(self.config.empty_pdf)

        self.resume_builder = Resume(config=self.config, creator_model=creator_model)
        self.cover_letter_builder = CoverLetter(
            config=self.config,
            evaluator_model=evaluator_model,
            eval_limit=eval_limit,
            include_feedback=include_feedback,
        )
        self.question_answerer = QuestionAnswerer(
            config=self.config,
            creator_model=creator_model,
        )
        self.job_processor = JobProcessor(model=creator_model)

        self.launch()

    def _get_or_parse_job(self, job_posting: str, job_desc: JobDescription | None) -> JobDescription:
        """Return cached job description or parse the posting if not yet parsed."""
        if job_desc is not None:
            logger.info("Using cached job description")
            return job_desc
        return self.job_processor.process_and_extract_job_info(job_posting)

    def _generate_cover_letter(self, job_posting: str, job_desc: JobDescription | None):
        job_desc = self._get_or_parse_job(job_posting, job_desc)
        cover_letter = self.cover_letter_builder.request_letter(job_desc)
        return cover_letter, job_desc

    def _convert_cover_letter_to_pdf(self, cover_letter_text: str):
        return self.cover_letter_builder.convert_cover_letter_to_pdf(cover_letter_text)

    def _tailor_resume(
        self,
        job_posting: str,
        job_desc: JobDescription | None,
        resume_feedback: str,
        use_last_resume: bool,
        last_resume: str | None,
    ):
        job_desc = self._get_or_parse_job(job_posting, job_desc)
        last = last_resume if use_last_resume else None
        result = self.resume_builder.tailor_resume(job_desc, resume_feedback, last)
        if result is None:
            return None, job_desc, last_resume  # keep old last_resume on failure
        pdf_path, resume_json = result
        return pdf_path, job_desc, resume_json

    def _answer_question(
        self,
        job_posting: str,
        job_desc: JobDescription | None,
        question: str,
    ):
        if not question.strip():
            return "Please enter a question.", job_desc
        job_desc = self._get_or_parse_job(job_posting, job_desc)
        answer = self.question_answerer.answer_question(job_desc, question)
        return answer, job_desc

    def launch(self):
        with gr.Blocks(theme=gr.themes.Default(primary_hue="sky")) as ui:

            # --- Session state ---
            job_desc_state = gr.State(None)   # holds parsed JobDescription
            last_resume_state = gr.State(None) # holds last resume JSON

            gr.Markdown("# Cover Letter Builder")

            with gr.Row():
                job_post_textbox = gr.Textbox(
                    label="Paste the job posting text or URL here (URLs will be automatically scraped)",
                    lines=20,
                )
                cover_letter_textbox = gr.Textbox(label="Cover Letter", lines=20)

            with gr.Row():
                run_button = gr.Button("Run", variant="primary")
                convert_pdf_button = gr.Button("Convert to PDF", variant="secondary")
                cover_letter_file = gr.File(
                    label="Cover Letter PDF", value=self.empty_file_path, visible=False
                )

            # Clear cached job description when the posting changes
            job_post_textbox.change(fn=lambda: None, outputs=job_desc_state)

            run_button.click(
                fn=self._generate_cover_letter,
                inputs=[job_post_textbox, job_desc_state],
                outputs=[cover_letter_textbox, job_desc_state],
            )

            job_post_textbox.submit(
                fn=self._generate_cover_letter,
                inputs=[job_post_textbox, job_desc_state],
                outputs=[cover_letter_textbox, job_desc_state],
            )

            convert_pdf_button.click(
                fn=lambda: gr.File(value=self.empty_file_path, visible=True),
                outputs=cover_letter_file,
            ).then(
                fn=self._convert_cover_letter_to_pdf,
                inputs=cover_letter_textbox,
                outputs=cover_letter_file,
            )

            # --- Resume tailoring ---
            gr.Markdown("## Resume Tailoring")
            resume_feedback_textbox = gr.Textbox(label="Resume Feedback", lines=5)

            with gr.Row():
                resume_button = gr.Button("Tailor Resume", variant="primary", scale=2)
                use_last_resume_checkbox = gr.Checkbox(
                    label="Use Last Resume", value=False, visible=False, scale=1
                )
                resume_file = gr.File(
                    label="Tailored Resume PDF", value=self.empty_file_path, visible=False
                )

            resume_button.click(
                fn=lambda: gr.File(value=self.empty_file_path, visible=True),
                outputs=resume_file,
            ).then(
                fn=self._tailor_resume,
                inputs=[
                    job_post_textbox,
                    job_desc_state,
                    resume_feedback_textbox,
                    use_last_resume_checkbox,
                    last_resume_state,
                ],
                outputs=[resume_file, job_desc_state, last_resume_state],
            ).then(
                fn=lambda: gr.Checkbox(visible=True),
                outputs=use_last_resume_checkbox,
            )

            # --- Question answerer ---
            gr.Markdown("## Interview Question Answerer")

            with gr.Row():
                question_textbox = gr.Textbox(
                    label="Enter your question",
                    lines=3,
                    placeholder="e.g., Tell me about yourself, Why are you interested in this role?",
                )
                answer_textbox = gr.Textbox(label="Answer", lines=10)

            answer_button = gr.Button("Answer Question", variant="primary")

            answer_button.click(
                fn=self._answer_question,
                inputs=[job_post_textbox, job_desc_state, question_textbox],
                outputs=[answer_textbox, job_desc_state],
            )

            question_textbox.submit(
                fn=self._answer_question,
                inputs=[job_post_textbox, job_desc_state, question_textbox],
                outputs=[answer_textbox, job_desc_state],
            )

        ui.launch(inbrowser=True)


if __name__ == "__main__":
    Main()