import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from cover_letter import CoverLetter
from job_processor import JobProcessor
from models import (
    AnswerQuestionBody,
    AnswerQuestionResponse,
    CoverLetterPdfBody,
    CoverLetterResponse,
    JobDescription,
    JobPostingBody,
    JobContextBody,
    TailorResumeBody,
    TailorResumeResponse,
)
from question_answerer import QuestionAnswerer
from resume import Resume
from utils import validate_app_config

load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


OUTPUT_DIR = Path("static") / "output"


class ApplicationServices:
    """Wires resume, cover letter, Q&A, and job parsing (no UI)."""

    def __init__(
        self,
        creator_model: str = "gpt-4o",
        evaluator_model: str = "o4-mini",
        eval_limit: int = 10,
        fit_limit: int = 5,
        config_file: str = "resources/app_config.json",
        include_feedback: bool = False,
    ):
        self.config = validate_app_config(config_file)

        self.resume_builder = Resume(config=self.config, creator_model=creator_model, fit_limit=fit_limit)
        self.cover_letter_builder = CoverLetter(
            config=self.config,
            creator_model=creator_model,
            evaluator_model=evaluator_model,
            eval_limit=eval_limit,
            include_feedback=include_feedback,
        )
        self.question_answerer = QuestionAnswerer(
            config=self.config,
            creator_model=creator_model,
        )
        self.job_processor = JobProcessor(model=creator_model)

    def get_or_parse_job(
        self, job_posting: str | None, job_desc: JobDescription | None
    ) -> JobDescription:
        if job_desc is not None:
            logger.info("Using client-provided job description")
            return job_desc
        if not job_posting or not job_posting.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide job_posting text/URL or a parsed job_description.",
            )
        return self.job_processor.process_and_extract_job_info(job_posting)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.services = ApplicationServices()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="Job Application Assistant",
    description="Parse job postings, generate cover letters, tailor resumes, and answer application questions.",
    lifespan=lifespan,
)

app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")


@app.exception_handler(ValueError)
async def value_error_handler(_request: Request, exc: ValueError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


def get_services(request: Request) -> ApplicationServices:
    return request.app.state.services


def _safe_output_path(filename: str) -> Path:
    if "/" in filename or "\\" in filename or filename in (".", ".."):
        raise HTTPException(status_code=400, detail="Invalid filename.")
    base = OUTPUT_DIR.resolve()
    candidate = (base / filename).resolve()
    if not candidate.is_relative_to(base):
        raise HTTPException(status_code=400, detail="Invalid filename.")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    return candidate


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return HTMLResponse((Path("frontend") / "index.html").read_text())


@app.post("/api/v1/job/parse", response_model=JobDescription)
def parse_job(body: JobPostingBody, request: Request):
    services = get_services(request)
    return services.job_processor.process_and_extract_job_info(body.job_posting.strip())


@app.post("/api/v1/cover-letter", response_model=CoverLetterResponse)
def generate_cover_letter(body: JobContextBody, request: Request):
    services = get_services(request)
    job_desc = services.get_or_parse_job(body.job_posting, body.job_description)
    cover_letter = services.cover_letter_builder.request_letter(job_desc)
    return CoverLetterResponse(cover_letter=cover_letter, job_description=job_desc)


@app.post("/api/v1/cover-letter/pdf")
def cover_letter_pdf(body: CoverLetterPdfBody, request: Request):
    services = get_services(request)
    company_name = body.job_description.company_name if body.job_description else None
    path = services.cover_letter_builder.convert_cover_letter_to_pdf(
        body.cover_letter_text,
        company_name=company_name,
    )
    if path is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not generate cover letter PDF.",
        )
    return FileResponse(path, media_type="application/pdf", filename=Path(path).name)


@app.post("/api/v1/resume/tailor", response_model=TailorResumeResponse)
def tailor_resume(body: TailorResumeBody, request: Request):
    services = get_services(request)
    job_desc = services.get_or_parse_job(body.job_posting, body.job_description)
    result = services.resume_builder.tailor_resume(job_desc, body.resume_feedback, body.last_resume_json)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Resume tailoring or PDF compilation failed.",
        )
    pdf_path, resume_json = result
    return TailorResumeResponse(
        job_description=job_desc,
        last_resume_json=resume_json,
        pdf_filename=Path(pdf_path).name,
    )


@app.get("/api/v1/outputs/{filename}")
def download_output(filename: str):
    path = _safe_output_path(filename)
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline"},
    )


@app.post("/api/v1/questions/answer", response_model=AnswerQuestionResponse)
def answer_question(body: AnswerQuestionBody, request: Request):
    if not body.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please enter a question.",
        )
    services = get_services(request)
    job_desc = services.get_or_parse_job(body.job_posting, body.job_description)
    answer = services.question_answerer.answer_question(job_desc, body.question)
    return AnswerQuestionResponse(answer=answer, job_description=job_desc)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=7860,
        reload=False,
    )